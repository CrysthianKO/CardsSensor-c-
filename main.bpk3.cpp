// Scanner de cartas controlado por outro programa via stdin/stdout.
//
// Comandos (um por linha, recebidos pelo STDIN):
//   LIGAR     abre a câmera, acende o LED e começa a ler
//   DESLIGAR  fecha a câmera e apaga o LED (poupa processamento)
//   SAIR      encerra o programa
//
// Eventos (um por linha, enviados pelo STDOUT, campos separados por ';'):
//   PRONTO                  modelos carregados, aguardando comandos
//   CAMERA_LIGADA / CAMERA_DESLIGADA
//   CARTA;<valor>;<naipe>   ex.: CARTA;10;Espadas
//   CARTA_REMOVIDA
//   ERRO;<mensagem>
//
// Mensagens para humanos (logs) vão para o STDERR, para não misturar com o
// protocolo. Se o STDIN fechar (o outro programa morreu), este programa
// encerra sozinho.
#include <atomic>
#include <chrono>
#include <csignal>
#include <gpiod.hpp>  // Header v2
#include <iostream>
#include <string>
#include <thread>

#include "led.hpp"
#include "simbolo.hpp"

using namespace std;
using namespace cv;
using namespace cartas;

// Ligue para ver as janelas e a leitura atual durante a calibração;
// desligue em produção (janelas custam CPU no Pi).
constexpr bool DEBUG_VISUAL = false;

constexpr int VOTOS_NECESSARIOS = 5;  // leituras iguais seguidas para aceitar
constexpr int PULAR_FRAMES = 3;       // processa 1 a cada 3 frames (~10 fps)
constexpr int MAX_FALHAS = 30;        // leituras vazias seguidas até desistir

static atomic<bool> rodando{true};
static atomic<bool> quer_camera{false};

// Lê os comandos do outro programa. Roda numa thread separada para não
// travar o loop da câmera.
static void threadComandos() {
  string linha;
  while (getline(cin, linha)) {
    while (!linha.empty() && (linha.back() == '\r' || linha.back() == ' '))
      linha.pop_back();
    if (linha == "LIGAR")
      quer_camera = true;
    else if (linha == "DESLIGAR")
      quer_camera = false;
    else if (linha == "SAIR")
      break;
    else if (!linha.empty())
      cerr << "Comando desconhecido: " << linha << endl;
  }
  rodando = false;  // SAIR ou STDIN fechado
}

// Só considera a câmera "aberta" se ela entregar um frame de verdade
// (abrir o dispositivo não garante que existam imagens).
static bool testarFrame(VideoCapture& cap) {
  Mat teste;
  for (int i = 0; i < 30; ++i) {
    if (cap.read(teste) && !teste.empty()) return true;
    this_thread::sleep_for(chrono::milliseconds(50));
  }
  return false;
}

// Tenta primeiro o V4L2 (câmeras USB e CSI em modo legado); se não entregar
// frames, tenta o libcamera via GStreamer (módulo CSI do Raspberry).
static bool abrirCamera(VideoCapture& cap, string& backend) {
  if (cap.open(0, CAP_V4L2)) {
    cap.set(CAP_PROP_FRAME_WIDTH, 640);
    cap.set(CAP_PROP_FRAME_HEIGHT, 480);
    if (testarFrame(cap)) {
      cerr << "Camera aberta via V4L2" << endl;
      backend = "V4L2";
      return true;
    }
    cerr << "V4L2 abriu, mas nao entregou frames" << endl;
    cap.release();
  } else {
    cerr << "V4L2 nao abriu" << endl;
  }

  const string pipeline =
      "libcamerasrc ! video/x-raw,width=640,height=480,framerate=30/1 ! "
      "videoconvert ! video/x-raw,format=BGR ! "
      "appsink drop=true max-buffers=1 sync=false";
  if (cap.open(pipeline, CAP_GSTREAMER)) {
    if (testarFrame(cap)) {
      cerr << "Camera aberta via libcamera (GStreamer)" << endl;
      backend = "libcamera";
      return true;
    }
    cerr << "libcamera abriu, mas nao entregou frames" << endl;
    cap.release();
  } else {
    cerr << "libcamera (GStreamer) nao abriu" << endl;
  }
  return false;
}

static int executar() {
  signal(SIGINT, [](int) { rodando = false; });

  ControladorLed meu_led(17);

  // Os 3 arquivos modelo_*.xml precisam estar na pasta de onde você roda.
  Reconhecedor reconhecedor;
  if (!reconhecedor.carregar()) {
    cout << "ERRO;nao carregou os modelos" << endl;
    return -1;
  }

  thread(threadComandos).detach();
  cout << "PRONTO" << endl;

  VideoCapture cap;
  string backend;
  bool camera_aberta = false;
  bool carta_em_leitura = false;
  string ultima;
  int repeticoes = 0, contador = 0, falhas = 0;
  Mat bruto;

  auto resetar = [&]() {
    carta_em_leitura = false;
    ultima.clear();
    repeticoes = contador = falhas = 0;
  };

  while (rodando) {
    // --- liga/desliga a câmera conforme o último comando recebido ---
    if (quer_camera && !camera_aberta) {
      if (abrirCamera(cap, backend)) {
        camera_aberta = true;
        resetar();
        meu_led.ligar();
        cout << "CAMERA_LIGADA" << endl;
      } else {
        quer_camera = false;
        cout << "ERRO;nenhum backend (V4L2/libcamera) entregou frames" << endl;
      }
    } else if (!quer_camera && camera_aberta) {
      cap.release();
      camera_aberta = false;
      meu_led.desligar();
      resetar();
      cout << "CAMERA_DESLIGADA" << endl;
    }

    // Câmera desligada: não gasta CPU, só espera o próximo comando.
    if (!camera_aberta) {
      this_thread::sleep_for(chrono::milliseconds(100));
      continue;
    }

    // grab() é barato (não decodifica); só processa 1 a cada N frames.
    if (!cap.grab()) {
      this_thread::sleep_for(chrono::milliseconds(30));
      if (++falhas >= MAX_FALHAS) {
        cout << "ERRO;a camera (" << backend << ") nao entregou frames" << endl;
        quer_camera = false;
      }
      continue;
    }
    falhas = 0;
    if (++contador % PULAR_FRAMES != 0) continue;
    if (!cap.retrieve(bruto) || bruto.empty()) continue;

    Mat frame = orientar(bruto);

    const Rect limites(0, 0, frame.cols, frame.rows);
    if ((ROI_NUMERO & limites) != ROI_NUMERO ||
        (ROI_NAIPE & limites) != ROI_NAIPE) {
      cout << "ERRO;ROI fora do frame (resolucao " << frame.cols << "x"
           << frame.rows << ")" << endl;
      quer_camera = false;
      continue;
    }

    Mat recorte_numero = frame(ROI_NUMERO);
    Mat recorte_naipe = frame(ROI_NAIPE);
    string leitura_debug;

    if (carta_em_leitura) {
      // Já leu: só confere (barato) se a carta saiu, sem rodar o SVM.
      if (!haCarta(recorte_numero) || !haCarta(recorte_naipe)) {
        cout << "CARTA_REMOVIDA" << endl;
        resetar();
        carta_em_leitura = false;
      }
    } else {
      string valor = reconhecedor.lerValor(recorte_numero);
      string naipe = reconhecedor.lerNaipe(recorte_naipe);
      leitura_debug = "[" + valor + "] [" + naipe + "]";

      if (!valor.empty() && !naipe.empty() && valor != "?" && naipe != "?") {
        string leitura = valor + ";" + naipe;
        if (leitura == ultima)
          ++repeticoes;
        else {
          ultima = leitura;
          repeticoes = 1;
        }
        if (repeticoes >= VOTOS_NECESSARIOS) {
          cout << "CARTA;" << leitura << endl;
          carta_em_leitura = true;
        }
      } else {
        ultima.clear();
        repeticoes = 0;
      }
    }

    if (DEBUG_VISUAL) {
      rectangle(frame, ROI_NUMERO, Scalar(255, 0, 0), 2);
      rectangle(frame, ROI_NAIPE, Scalar(0, 0, 255), 2);
      putText(frame, carta_em_leitura ? "TRAVADA: " + ultima : leitura_debug,
              Point(8, 24), FONT_HERSHEY_SIMPLEX, 0.6, Scalar(0, 255, 0), 2);
      imshow("Scanner Inteligente", frame);
      if (waitKey(1) == 'q') break;
    }
  }

  if (camera_aberta) cap.release();
  meu_led.desligar();
  return 0;
}

int main() {
  try {
    return executar();
  } catch (const std::exception& e) {
    // Ex.: "error requesting GPIO lines: Device or resource busy"
    cout << "ERRO;" << e.what() << endl;
    return -1;
  }
}

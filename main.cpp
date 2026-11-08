#include <gpiod.hpp>  // Header v2
#include <csignal>
#include <iostream>
#include <string>

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

static volatile sig_atomic_t rodando = 1;

// A câmera do Raspberry (módulo CSI) só é lida pelo OpenCV via GStreamer +
// libcamera. Se não abrir, tenta uma câmera USB comum (V4L2).
static bool abrirCamera(VideoCapture& cap) {
  const string pipeline =
      "libcamerasrc ! video/x-raw,width=640,height=480,framerate=30/1 ! "
      "videoconvert ! video/x-raw,format=BGR ! "
      "appsink drop=true max-buffers=1 sync=false";
  if (cap.open(pipeline, CAP_GSTREAMER)) {
    cout << "Camera aberta via libcamera (GStreamer)" << endl;
    return true;
  }
  if (cap.open(0, CAP_V4L2)) {
    cap.set(CAP_PROP_FRAME_WIDTH, 640);
    cap.set(CAP_PROP_FRAME_HEIGHT, 480);
    cout << "Camera aberta via V4L2 (USB)" << endl;
    return true;
  }
  return false;
}

int main() {
  signal(SIGINT, [](int) { rodando = 0; });

  ControladorLed meu_led(17);

  // Os 3 arquivos modelo_*.xml precisam estar na pasta de onde você roda.
  Reconhecedor reconhecedor;
  if (!reconhecedor.carregar()) return -1;

  VideoCapture cap;
  if (!abrirCamera(cap)) {
    cerr << "Nao consegui abrir a camera (nem libcamera, nem V4L2)." << endl;
    return -1;
  }

  bool carta_em_leitura = false;
  string ultima;
  int repeticoes = 0;
  int contador = 0;

  meu_led.ligar();
  Mat bruto;
  while (rodando) {
    // grab() é barato (não decodifica); só processa 1 a cada N frames.
    if (!cap.grab()) break;
    if (++contador % PULAR_FRAMES != 0) continue;
    if (!cap.retrieve(bruto) || bruto.empty()) break;

    Mat frame = orientar(bruto);

    const Rect limites(0, 0, frame.cols, frame.rows);
    if ((ROI_NUMERO & limites) != ROI_NUMERO ||
        (ROI_NAIPE & limites) != ROI_NAIPE) {
      cerr << "ROI fora do frame (" << frame.cols << "x" << frame.rows
           << "). A resolucao nao e 640x480." << endl;
      break;
    }

    Mat recorte_numero = frame(ROI_NUMERO);
    Mat recorte_naipe = frame(ROI_NAIPE);
    string leitura_debug;

    if (carta_em_leitura) {
      // Já leu: só confere (barato) se a carta saiu, sem rodar o SVM.
      if (!haCarta(recorte_numero) || !haCarta(recorte_naipe)) {
        cout << "--- Carta removida. Aguardando a proxima..." << endl;
        carta_em_leitura = false;
        ultima.clear();
        repeticoes = 0;
      }
    } else {
      string valor = reconhecedor.lerValor(recorte_numero);
      string naipe = reconhecedor.lerNaipe(recorte_naipe);
      leitura_debug = "[" + valor + "] [" + naipe + "]";

      if (!valor.empty() && !naipe.empty() && valor != "?" && naipe != "?") {
        string leitura = valor + " de " + naipe;
        if (leitura == ultima)
          ++repeticoes;
        else {
          ultima = leitura;
          repeticoes = 1;
        }
        if (repeticoes >= VOTOS_NECESSARIOS) {
          cout << ">>> CARTA INSERIDA: " << leitura << endl;
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

  meu_led.desligar();
  return 0;
}

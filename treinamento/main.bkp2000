#include <gpiod.hpp>  // Header v2
#include <csignal>
#include <iostream>
#include <string>

#include "led.hpp"
#include "simbolo.hpp"

using namespace std;
using namespace cv;
using namespace cartas;

// Ligue para ver as janelas durante a calibração; desligue em produção.
constexpr bool DEBUG_VISUAL = false;

constexpr int VOTOS_NECESSARIOS = 5;  // leituras iguais seguidas para aceitar
constexpr int PULAR_FRAMES = 3;       // processa 1 a cada 3 frames (~10 fps)

static volatile sig_atomic_t rodando = 1;

int main() {
  signal(SIGINT, [](int) { rodando = 0; });

  ControladorLed meu_led(17);

  Reconhecedor reconhecedor;
  if (!reconhecedor.carregar()) return -1;

  VideoCapture cap(0, CAP_V4L2);
  if (!cap.isOpened()) return -1;

  cap.set(CAP_PROP_FRAME_WIDTH, 640);
  cap.set(CAP_PROP_FRAME_HEIGHT, 480);

  bool carta_em_leitura = false;
  string ultima;
  int repeticoes = 0;
  int contador = 0;

  meu_led.ligar();
  Mat bruto;
  while (rodando) {
    // grab() é barato (não decodifica); só decodifica 1 a cada N frames.
    if (!cap.grab()) break;
    if (++contador % PULAR_FRAMES != 0) continue;
    if (!cap.retrieve(bruto) || bruto.empty()) break;

    Mat frame = orientar(bruto);
    Mat recorte_numero = frame(ROI_NUMERO);
    Mat recorte_naipe = frame(ROI_NAIPE);

    if (carta_em_leitura) {
      // Já leu: só confere (barato) se a carta saiu, sem rodar o SVM.
      if (!haCarta(recorte_numero) || !haCarta(recorte_naipe)) {
        cout << "--- Carta removida. Aguardando a próxima..." << endl;
        carta_em_leitura = false;
        ultima.clear();
        repeticoes = 0;
      }
    } else {
      string valor = reconhecedor.lerValor(recorte_numero);
      string naipe = reconhecedor.lerNaipe(recorte_naipe);

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
      imshow("Scanner Inteligente", frame);
      if (waitKey(1) == 'q') break;
    }
  }

  meu_led.desligar();
  return 0;
}

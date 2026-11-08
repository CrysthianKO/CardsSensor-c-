#include <gpiod.hpp>  // Header v2
#include <iostream>
#include <opencv2/ml.hpp>
#include <opencv2/opencv.hpp>
#include <string>
#include <vector>

#include "led.hpp"

using namespace std;
using namespace cv;
using namespace cv::ml;

const vector<string> NOME_SIMBOLOS = {
    "A",  "2", "3", "4", "5",     "6",     "7",       "8",   "9",
    "10", "J", "Q", "K", "Copas", "Ouros", "Espadas", "Paus"};

string identificarSimbolo(const Mat& recorte, Ptr<SVM> modelo_svm) {
  Mat cinza, binaria, redimensionada;

  cvtColor(recorte, cinza, COLOR_BGR2GRAY);

  // === 1. GATILHO DE SOFTWARE (VERIFICA SE HÁ CARTA) ===
  // Calcula a média de brilho do recorte.
  // Uma carta branca refletindo o LED terá uma média alta (ex: > 100).
  // O buraco escuro sem carta terá uma média baixa (ex: < 40).
  Scalar media_iluminacao = mean(cinza);

  // AJUSTE AQUI: Se a leitura fantasma continuar, aumente este valor (ex: 60).
  // Se ele ignorar cartas reais, diminua (ex: 30).
  if (media_iluminacao[0] < 50.0) {
    return "Vazio";
  }

  // Se passou do gatilho, continua o processo normal
  threshold(cinza, binaria, 128, 255, THRESH_BINARY_INV);
  resize(binaria, redimensionada, Size(20, 20));
  Mat linha_pixels = redimensionada.reshape(1, 1);

  Mat entrada_svm;
  linha_pixels.convertTo(entrada_svm, CV_32F);

  float previsao = modelo_svm->predict(entrada_svm);
  int indice = static_cast<int>(previsao);

  if (indice >= 0 && indice < NOME_SIMBOLOS.size()) {
    return NOME_SIMBOLOS[indice];
  }

  return "Erro";
}

int main() {
  ControladorLed meu_led(17);

  Ptr<SVM> svm = SVM::load("modelo_cartas.xml");
  if (svm->empty()) return -1;

  VideoCapture cap(0, CAP_V4L2);
  if (!cap.isOpened()) return -1;

  cap.set(CAP_PROP_FRAME_WIDTH, 640);
  cap.set(CAP_PROP_FRAME_HEIGHT, 480);

  // === 2. AJUSTE DO RECORTE (ROI) ===
  // Valores em Pixels: (Margem_Esquerda, Margem_Topo, Largura, Altura)
  Rect ROI_NUMERO(220, 291, 75, 91);
  Rect ROI_NAIPE(220, 190, 75, 91);

  Mat frame_bruto, frame;

  // Variáveis da Máquina de Estados
  bool carta_em_leitura = false;

  meu_led.ligar();
  while (true) {
    cap >> frame_bruto;
    if (frame_bruto.empty()) break;

    // === 3. ROTAÇÃO DA CÂMERA ===
    // Gira 90 graus para a direita (sentido horário).
    // Se a sua câmera estiver virada para o outro lado, mude para
    // ROTATE_90_COUNTERCLOCKWISE
    rotate(frame_bruto, frame, ROTATE_90_CLOCKWISE);

    // Recorta
    Mat recorte_numero = frame(ROI_NUMERO);
    Mat recorte_naipe = frame(ROI_NAIPE);

    // Identifica
    string valor = identificarSimbolo(recorte_numero, svm);
    string naipe = identificarSimbolo(recorte_naipe, svm);

    // === 4. LÓGICA DE DETECÇÃO ÚNICA ===
    if (valor != "Vazio" && naipe != "Vazio") {
      // Se tem uma carta, mas ainda não tínhamos registrado ela
      if (!carta_em_leitura) {
        string resultado_final = valor + " de " + naipe;
        cout << ">>> CARTA INSERIDA: " << resultado_final << endl;

        // Trava o estado para não imprimir 30 vezes por segundo
        carta_em_leitura = true;
      }
    } else {
      // Se a média de luz caiu, a pessoa puxou a carta da máquina
      if (carta_em_leitura) {
        cout << "--- Carta removida. Aguardando a próxima..." << endl;
        // Destrava o estado
        carta_em_leitura = false;
      }
    }

    // Desenha na tela apenas para calibração
    rectangle(frame, ROI_NUMERO, Scalar(255, 0, 0), 2);
    rectangle(frame, ROI_NAIPE, Scalar(0, 0, 255), 2);
    imshow("Scanner Inteligente", frame);

    if (waitKey(1) == 'q') break;
  }

  meu_led.desligar();
  return 0;
}

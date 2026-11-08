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

// Adicionamos o parametro 'nome_janela' para debug visual
string identificarSimbolo(const Mat& recorte, Ptr<SVM> modelo_svm,
                          string nome_janela) {
  Mat cinza, binaria, redimensionada;

  cvtColor(recorte, cinza, COLOR_BGR2GRAY);

  // === 1. A MÁGICA DA ILUMINAÇÃO (OTSU) ===
  // Ao invés do 128 fixo, passamos 0 e a flag THRESH_OTSU.
  // O OpenCV calcula automaticamente a melhor separação de tinta/fundo para
  // esta exata iluminação.
  threshold(cinza, binaria, 0, 255, THRESH_BINARY_INV | THRESH_OTSU);

  resize(binaria, redimensionada, Size(20, 20));

  // === 2. A JANELA DE RAIO-X (DEBUG) ===
  // Ampliamos a minúscula imagem de 20x20 para 200x200 SEM borrar
  // (INTER_NEAREST) para você conseguir ver a olho nu os pixels quadrados que o
  // SVM vai julgar.
  Mat visao_ampliada;
  resize(redimensionada, visao_ampliada, Size(200, 200), 0, 0, INTER_NEAREST);
  imshow("Raio-X: " + nome_janela, visao_ampliada);

  // Converte e manda para o modelo
  Mat linha_pixels = redimensionada.reshape(1, 1);
  Mat entrada_svm;
  linha_pixels.convertTo(entrada_svm, CV_32F);

  float previsao = modelo_svm->predict(entrada_svm);
  int indice = static_cast<int>(previsao);

  if (indice >= 0 && indice < NOME_SIMBOLOS.size())
    return NOME_SIMBOLOS[indice];
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
  Rect ROI_NUMERO(196, 255, 78, 91);
  Rect ROI_NAIPE(196, 348, 75, 91);

  Mat frame_bruto, frame;

  // Variáveis da Máquina de Estados
  bool carta_em_leitura = false;

  meu_led.ligar();
  while (true) {
    cap >> frame_bruto;
    if (frame_bruto.empty()) break;

    Mat frame_girado;
    rotate(frame_bruto, frame_girado, ROTATE_90_COUNTERCLOCKWISE);
    flip(frame_girado, frame, 1);

    // Recorta
    Mat recorte_numero = frame(ROI_NUMERO);
    Mat recorte_naipe = frame(ROI_NAIPE);

    // Identifica
    string valor = identificarSimbolo(recorte_numero, svm, "Numero");
    string naipe = identificarSimbolo(recorte_naipe, svm, "Naipe");

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

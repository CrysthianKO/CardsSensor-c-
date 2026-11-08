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
  Mat cinza, binaria;
  cvtColor(recorte, cinza, COLOR_BGR2GRAY);

  // Gatilho de presença
  if (mean(cinza)[0] < 50.0) return "Vazio";

  // 1. Separação de cores (Otsu)
  threshold(cinza, binaria, 0, 255, THRESH_BINARY_INV | THRESH_OTSU);

  // === 2. A LIXA DIGITAL (EROSÃO) ===
  // Cria um 'esfregão' de 2x2 pixels.
  // Se o símbolo continuar grosso, aumente para Size(3, 3).
  // Se ficar fino demais e sumir pedaços, diminua para Size(1, 1) ou comente
  // essas duas linhas.
  Mat elemento_lixa = getStructuringElement(MORPH_RECT, Size(2, 2));
  erode(binaria, binaria, elemento_lixa);

  // === 3. ENCONTRANDO A TINTA (BOUNDING BOX) ===
  vector<vector<Point>> contornos;
  // Procura todas as ilhas de pixels brancos na imagem
  findContours(binaria, contornos, RETR_EXTERNAL, CHAIN_APPROX_SIMPLE);

  if (contornos.empty()) return "Vazio";

  // Acha o maior contorno (ignora pequenas sujeiras no papel)
  double maior_area = 0;
  Rect caixa_tinta;
  for (const auto& contorno : contornos) {
    double area = contourArea(contorno);
    if (area > maior_area) {
      maior_area = area;
      caixa_tinta = boundingRect(contorno);
    }
  }

  // Se o maior contorno for um cisco, ignora
  if (maior_area < 20) return "Vazio";

  // Recorta a imagem cirurgicamente na borda exata do símbolo
  Mat apenas_tinta = binaria(caixa_tinta);

  // === 4. CENTRALIZANDO SEM DISTORCER (ASPECT RATIO) ===
  // Descobre qual é o maior lado do símbolo para escalá-lo sem esmagar
  int maior_lado = max(apenas_tinta.cols, apenas_tinta.rows);
  Mat imagem_quadrada = Mat::zeros(maior_lado, maior_lado, CV_8UC1);

  // Calcula onde colar a tinta para ela ficar exatamente no centro do quadrado
  int x_offset = (maior_lado - apenas_tinta.cols) / 2;
  int y_offset = (maior_lado - apenas_tinta.rows) / 2;

  // Cola a tinta no quadrado preto
  apenas_tinta.copyTo(imagem_quadrada(
      Rect(x_offset, y_offset, apenas_tinta.cols, apenas_tinta.rows)));

  // Agora sim, redimensionamos um quadrado perfeito para 20x20
  Mat redimensionada;
  resize(imagem_quadrada, redimensionada, Size(20, 20));

  // Janela de Debug para calibração visual (Raio-X)
  Mat visao_ampliada;
  resize(redimensionada, visao_ampliada, Size(200, 200), 0, 0, INTER_NEAREST);
  imshow("Raio-X: " + nome_janela, visao_ampliada);

  // Prepara para o SVM e faz a previsão
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
  Rect ROI_NUMERO(207, 255, 78, 91);
  Rect ROI_NAIPE(207, 348, 75, 91);

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

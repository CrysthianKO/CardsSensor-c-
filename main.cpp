#include <cstdlib>
#include <iostream>
#include <opencv2/ml.hpp>
#include <opencv2/opencv.hpp>
#include <string>
#include <vector>

#include "led.hpp"

using namespace std;
using namespace cv;
using namespace cv::ml;

// 1. Os Gabaritos exatos que você usou no treinamento do Python
const vector<string> LABELS_VALORES = {"A", "2", "3",  "4", "5", "6", "7",
                                       "8", "9", "10", "J", "Q", "K"};
const vector<string> LABELS_VERMELHOS = {"Copas", "Ouros"};
const vector<string> LABELS_PRETOS = {"Espadas", "Paus"};

// Estrutura para trafegar os dados processados da imagem
struct DadosProcessados {
  Mat matriz_svm;  // A linha de 400 pixels para o SVM
  bool valido;     // Se tem uma carta válida na imagem
  bool is_red;     // A cor da tinta
};

// 2. A Fábrica de Tratamento de Imagem (Faz tudo antes do SVM)
DadosProcessados prepararImagem(const Mat& recorte_bgr, string nome_janela) {
  DadosProcessados resultado = {Mat(), false, false};
  Mat cinza, binaria;

  cvtColor(recorte_bgr, cinza, COLOR_BGR2GRAY);

  // Gatilho de presença (Fundo escuro sem carta)
  if (mean(cinza)[0] < 50.0) return resultado;

  // Binarização Otsu
  threshold(cinza, binaria, 0, 255, THRESH_BINARY_INV | THRESH_OTSU);

  // A Lixa Digital (Erosão) - Deixa a espessura igual a do treinamento
  Mat elemento_lixa = getStructuringElement(MORPH_RECT, Size(2, 2));
  erode(binaria, binaria, elemento_lixa);

  // Encontrando a Borda (Bounding Box)
  vector<vector<Point>> contornos;
  findContours(binaria, contornos, RETR_EXTERNAL, CHAIN_APPROX_SIMPLE);

  if (contornos.empty()) return resultado;

  double maior_area = 0;
  Rect caixa_tinta;
  for (const auto& contorno : contornos) {
    double area = contourArea(contorno);
    if (area > maior_area) {
      maior_area = area;
      caixa_tinta = boundingRect(contorno);
    }
  }

  if (maior_area < 20) return resultado;

  // Recorta exatamente na borda da tinta
  Mat apenas_tinta_bin = binaria(caixa_tinta);
  Mat apenas_tinta_bgr =
      recorte_bgr(caixa_tinta);  // Usaremos esse para ver a cor

  // === FILTRO DE COR (A MÁGICA) ===
  // Calcula a média das cores (B, G, R) APENAS onde o 'apenas_tinta_bin' é
  // branco
  Scalar cor_media = mean(apenas_tinta_bgr, apenas_tinta_bin);
  // cor_media[0] = Azul, cor_media[1] = Verde, cor_media[2] = Vermelho

  // Se o canal vermelho for 15 tons mais forte que o azul e verde, é carta
  // vermelha
  if (cor_media[2] > cor_media[0] + 15 && cor_media[2] > cor_media[1] + 15) {
    resultado.is_red = true;
  }

  // === CENTRALIZANDO A TINTA NO QUADRADO (ASPECT RATIO) ===
  int maior_lado = max(apenas_tinta_bin.cols, apenas_tinta_bin.rows);
  Mat imagem_quadrada = Mat::zeros(maior_lado, maior_lado, CV_8UC1);

  int x_offset = (maior_lado - apenas_tinta_bin.cols) / 2;
  int y_offset = (maior_lado - apenas_tinta_bin.rows) / 2;
  apenas_tinta_bin.copyTo(imagem_quadrada(
      Rect(x_offset, y_offset, apenas_tinta_bin.cols, apenas_tinta_bin.rows)));

  // Redimensiona, achata e converte
  Mat redimensionada;
  resize(imagem_quadrada, redimensionada, Size(20, 20));

  // DEBUG: Mostra o Raio-X visualmente
  Mat visao_ampliada;
  resize(redimensionada, visao_ampliada, Size(200, 200), 0, 0, INTER_NEAREST);
  imshow("Raio-X: " + nome_janela, visao_ampliada);

  Mat linha_pixels = redimensionada.reshape(1, 1);
  linha_pixels.convertTo(resultado.matriz_svm, CV_32F);

  resultado.valido = true;
  return resultado;
}

int main() {
  ControladorLed meu_led(17);
  cout << "Carregando a Inteligência Artificial (Cascata)..." << endl;

  // 3. Carrega os Três Modelos de uma vez
  Ptr<SVM> svm_valores = SVM::load("modelo_valores.xml");
  Ptr<SVM> svm_vermelhos = SVM::load("modelo_naipes_vermelhos.xml");
  Ptr<SVM> svm_pretos = SVM::load("modelo_naipes_pretos.xml");

  if (svm_valores->empty() || svm_vermelhos->empty() || svm_pretos->empty()) {
    cout << "ERRO: Um dos arquivos .xml não foi encontrado!" << endl;
    return -1;
  }

  meu_led.ligar();

  VideoCapture cap(0, CAP_V4L2);
  if (!cap.isOpened()) return -1;
  cap.set(CAP_PROP_FRAME_WIDTH, 640);
  cap.set(CAP_PROP_FRAME_HEIGHT, 480);

  // Ajuste estes Rects conforme a calibração física do seu gabinete
  Rect ROI_NUMERO(179, 250, 79, 101);
  Rect ROI_NAIPE(179, 352, 82, 86);

  Mat frame_bruto, frame;
  bool carta_em_leitura = false;

  cout << "Scanner Operacional. Insira as cartas." << endl;

  while (true) {
    cap >> frame_bruto;
    if (frame_bruto.empty()) break;

    // 4. Correção do Espelho Ótico e Orientação da Câmera
    Mat frame_girado;
    rotate(frame_bruto, frame_girado, ROTATE_90_COUNTERCLOCKWISE);
    flip(frame_girado, frame, 1);

    Mat recorte_numero = frame(ROI_NUMERO);
    Mat recorte_naipe = frame(ROI_NAIPE);

    // Prepara matematicamente as imagens e checa a cor
    DadosProcessados dados_numero = prepararImagem(recorte_numero, "Numero");
    DadosProcessados dados_naipe = prepararImagem(recorte_naipe, "Naipe");

    // === 5. A LÓGICA EM CASCATA ===
    if (dados_numero.valido && dados_naipe.valido) {
      if (!carta_em_leitura) {
        // Inferência do Valor
        int id_valor = svm_valores->predict(dados_numero.matriz_svm);
        string str_valor = LABELS_VALORES[id_valor];

        // Inferência do Naipe baseada na Cor
        string str_naipe;
        if (dados_naipe.is_red) {
          int id_naipe = svm_vermelhos->predict(dados_naipe.matriz_svm);
          str_naipe = LABELS_VERMELHOS[id_naipe];
        } else {
          int id_naipe = svm_pretos->predict(dados_naipe.matriz_svm);
          str_naipe = LABELS_PRETOS[id_naipe];
        }

        cout << ">>> LEITURA: " << str_valor << " de " << str_naipe << endl;
        carta_em_leitura = true;
      }
    } else {
      if (carta_em_leitura) {
        cout << "--- Gaveta vazia. Aguardando..." << endl;
        carta_em_leitura = false;
      }
    }

    // Desenha na tela para calibração
    rectangle(frame, ROI_NUMERO, Scalar(255, 0, 0), 2);
    rectangle(frame, ROI_NAIPE, Scalar(0, 0, 255), 2);

    // Se houver uma carta, adiciona o indicador visual de cor para debug
    if (carta_em_leitura) {
      Scalar cor_texto =
          dados_naipe.is_red ? Scalar(0, 0, 255) : Scalar(0, 0, 0);
      putText(frame, dados_naipe.is_red ? "Cor: VERMELHO" : "Cor: PRETO",
              Point(10, 30), FONT_HERSHEY_SIMPLEX, 0.8, cor_texto, 2);
    }

    imshow("Scanner Inteligente", frame);

    if (waitKey(1) == 'q') break;
  }

  meu_led.desligar();
  return 0;
}

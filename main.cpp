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

// Este é o "gabarito". Os índices aqui precisam ser EXATAMENTE
// iguais à ordem da lista CARACTERES que você usou no Python.
const vector<string> NOME_SIMBOLOS = {
    "A",  "2", "3", "4", "5",     "6",     "7",       "8",   "9",
    "10", "J", "Q", "K", "Copas", "Ouros", "Espadas", "Paus"};

// Função que pega um recorte da imagem e passa pelo "Cérebro"
string identificarSimbolo(const Mat& recorte, Ptr<SVM> modelo_svm) {
  Mat cinza, binaria, redimensionada;

  cvtColor(recorte, cinza, COLOR_BGR2GRAY);
  threshold(cinza, binaria, 128, 255,
            THRESH_BINARY_INV);  // Fundo preto, letra branca

  // 2. Garante que a imagem tenha exatos 20x20 pixels
  resize(binaria, redimensionada, Size(20, 20));

  // 3. O "Moedor de Carne": Achatamento (Flatten)
  // reshape(canais, linhas). Queremos 1 canal e 1 única linha (400 colunas)
  Mat linha_pixels = redimensionada.reshape(1, 1);

  // 4. Converte para o formato matemático que o SVM entende (Float 32 bits)
  Mat entrada_svm;
  linha_pixels.convertTo(entrada_svm, CV_32F);

  // 5. A Mágica: Pergunta ao modelo qual é o resultado
  // O predict retorna um número de ponto flutuante (ex: 12.0)
  float previsao_numerica = modelo_svm->predict(entrada_svm);

  // Converte o número de volta para inteiro (ex: 12)
  int indice = static_cast<int>(previsao_numerica);

  // Retorna o nome humano daquele índice (ex: "K")
  if (indice >= 0 && indice < NOME_SIMBOLOS.size()) {
    return NOME_SIMBOLOS[indice];
  }

  return "Desconhecido";
}

int main() {
  ControladorLed meu_led(17);

  cout << "Carregando a Inteligencia Artificial..." << endl;

  // Carrega o arquivo XML treinado no PC
  Ptr<SVM> svm = SVM::load("modelo_cartas.xml");

  if (svm->empty()) {
    cout << "ERRO: Arquivo modelo_cartas.xml nao encontrado!" << endl;
    return -1;
  }
  cout << "Modelo carregado com sucesso!" << endl;

  VideoCapture cap(0, CAP_V4L2);
  if (!cap.isOpened()) {
    cout << "ERRO: Nao foi possivel abrir a camera." << endl;
    return -1;
  }

  // Configura para rodar super leve e rápido
  cap.set(CAP_PROP_FRAME_WIDTH, 640);
  cap.set(CAP_PROP_FRAME_HEIGHT, 480);
  cap.set(CAP_PROP_FPS, 30);

  // Defina as posições fixas onde o Número e o Naipe vão aparecer na abertura
  // (Ajuste os valores X, Y, Largura, Altura de acordo com o seu projeto
  // físico)
  Rect ROI_NUMERO(120, 50, 40, 60);
  Rect ROI_NAIPE(120, 120, 40, 60);

  Mat frame;
  cout << "Iniciando scanner. Pressione 'q' para sair." << endl;
  meu_led.ligar();
  while (true) {
    cap >> frame;  // Captura imagem
    if (frame.empty()) break;

    // Recorta as regiões fixas da imagem
    Mat recorte_numero = frame(ROI_NUMERO);
    Mat recorte_naipe = frame(ROI_NAIPE);

    // Manda os recortes para o modelo analisar
    string valor_carta = identificarSimbolo(recorte_numero, svm);
    string naipe_carta = identificarSimbolo(recorte_naipe, svm);

    // Monta a string final (Ex: "A de Copas")
    string resultado_final = valor_carta + " de " + naipe_carta;

    // Desenha na tela para feedback
    rectangle(frame, ROI_NUMERO, Scalar(255, 0, 0), 2);
    rectangle(frame, ROI_NAIPE, Scalar(0, 0, 255), 2);
    putText(frame, resultado_final, Point(ROI_NUMERO.x, ROI_NUMERO.y - 10),
            FONT_HERSHEY_SIMPLEX, 0.8, Scalar(0, 255, 0), 2);

    imshow("Scanner Inteligente", frame);

    if (waitKey(1) == 'q') break;
  }

  meu_led.desligar();

  return 0;
}

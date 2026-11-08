#pragma once
// Código compartilhado entre coleta.cpp, treino.cpp e main.cpp.
// Tudo que afeta a imagem do símbolo fica AQUI, para que coleta, treino e
// reconhecimento usem exatamente o mesmo pré-processamento.
// Compile com -std=c++17.

#include <algorithm>
#include <iostream>
#include <opencv2/ml.hpp>
#include <opencv2/opencv.hpp>
#include <string>
#include <vector>

namespace cartas {

// ---------------------------------------------------------------- Config ---
// Os nomes abaixo também são os nomes das pastas do dataset.
inline const std::vector<std::string> NOMES_VALORES = {
    "A", "2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K"};
inline const std::vector<std::string> NOMES_NAIPES_VERMELHOS = {"Copas",
                                                                "Ouros"};
inline const std::vector<std::string> NOMES_NAIPES_PRETOS = {"Espadas", "Paus"};

// ROIs com folga (x, y, largura, altura) no frame JÁ girado/espelhado.
// Ajuste olhando a janela da coleta: o símbolo inteiro (incluindo o "10" e a
// ponta do espadas) precisa caber com uma pequena borda.
inline const cv::Rect ROI_NUMERO(179, 250, 79, 101);
inline const cv::Rect ROI_NAIPE(179, 352, 82, 86);

constexpr double LIMIAR_PRESENCA = 50.0;  // brilho médio mínimo com carta
constexpr double LIMIAR_VERMELHO = 30.0;  // R - (G+B)/2 médio da tinta
constexpr double AREA_MIN = 15.0;         // ignora ciscos (pixels)
constexpr int LADO = 32;                  // imagem final LADO x LADO

// ---------------------------------------------------------------- Imagem ---
// Mesma orientação que o main.cpp original usava.
inline cv::Mat orientar(const cv::Mat& bruto) {
  cv::Mat girado, frame;
  cv::rotate(bruto, girado, cv::ROTATE_90_COUNTERCLOCKWISE);
  cv::flip(girado, frame, 1);
  return frame;
}

// Teste barato de presença da carta (só o brilho médio do recorte).
inline bool haCarta(const cv::Mat& recorte) {
  cv::Mat cinza;
  cv::cvtColor(recorte, cinza, cv::COLOR_BGR2GRAY);
  return cv::mean(cinza)[0] >= LIMIAR_PRESENCA;
}

struct Simbolo {
  cv::Mat img;            // LADO x LADO, CV_8UC1, tinta branca em fundo preto
  bool vermelho = false;  // cor da tinta (para separar os naipes)
};

// Extrai o símbolo do recorte. Retorna false se não houver símbolo.
inline bool extrairSimbolo(const cv::Mat& recorte, Simbolo& saida) {
  cv::Mat cinza, binaria;
  cv::cvtColor(recorte, cinza, cv::COLOR_BGR2GRAY);
  if (cv::mean(cinza)[0] < LIMIAR_PRESENCA) return false;

  // Blur leve em vez de erosão: não afina o símbolo e reduz ruído do Otsu.
  cv::GaussianBlur(cinza, cinza, cv::Size(3, 3), 0);
  cv::threshold(cinza, binaria, 0, 255,
                cv::THRESH_BINARY_INV | cv::THRESH_OTSU);

  std::vector<std::vector<cv::Point>> contornos;
  cv::findContours(binaria, contornos, cv::RETR_EXTERNAL,
                   cv::CHAIN_APPROX_SIMPLE);

  // União das caixas de TODOS os contornos relevantes: junta o "1" e o "0"
  // do "10" e as partes do espadas. Descarta ciscos e blobs gigantes (fundo).
  const double area_max = 0.5 * static_cast<double>(recorte.total());
  cv::Rect caixa;
  bool achou = false;
  for (const auto& c : contornos) {
    double a = cv::contourArea(c);
    if (a < AREA_MIN || a > area_max) continue;
    cv::Rect r = cv::boundingRect(c);
    caixa = achou ? (caixa | r) : r;
    achou = true;
  }
  if (!achou) return false;

  // Cola a tinta no centro de um quadrado (sem distorcer) com uma margem.
  cv::Mat tinta = binaria(caixa);
  int lado = std::max(tinta.cols, tinta.rows);
  int margem = std::max(2, lado / 8);
  cv::Mat quadrado =
      cv::Mat::zeros(lado + 2 * margem, lado + 2 * margem, CV_8UC1);
  int ox = margem + (lado - tinta.cols) / 2;
  int oy = margem + (lado - tinta.rows) / 2;
  tinta.copyTo(quadrado(cv::Rect(ox, oy, tinta.cols, tinta.rows)));
  cv::resize(quadrado, saida.img, cv::Size(LADO, LADO), 0, 0, cv::INTER_AREA);

  // Cor da tinta (BGR) usando a própria máscara binária como filtro.
  cv::Scalar m = cv::mean(recorte(caixa), binaria(caixa));
  saida.vermelho = (m[2] - 0.5 * (m[0] + m[1])) > LIMIAR_VERMELHO;
  return true;
}

// Vetor de características HOG (1 x N, CV_32F). Bem mais robusto que pixels
// crus e barato: 324 valores para 32x32.
inline cv::Mat calcularHOG(const cv::Mat& img) {
  static const cv::HOGDescriptor hog(cv::Size(LADO, LADO), cv::Size(16, 16),
                                     cv::Size(8, 8), cv::Size(8, 8), 9);
  std::vector<float> d;
  hog.compute(img, d);
  return cv::Mat(d).clone().reshape(1, 1);
}

// ---------------------------------------------------------- Reconhecedor ---
// Três SVMs pequenos: valores (13 classes), naipes vermelhos (Copas/Ouros) e
// naipes pretos (Espadas/Paus). A cor decide qual modelo de naipe usar.
struct Reconhecedor {
  cv::Ptr<cv::ml::SVM> valores, vermelhos, pretos;

  bool carregar() {
    try {
      valores = cv::ml::SVM::load("modelo_valores.xml");
      vermelhos = cv::ml::SVM::load("modelo_naipes_vermelhos.xml");
      pretos = cv::ml::SVM::load("modelo_naipes_pretos.xml");
    } catch (const cv::Exception& e) {
      std::cerr << "Erro ao carregar modelos: " << e.what() << std::endl;
      return false;
    }
    return !valores.empty() && !vermelhos.empty() && !pretos.empty();
  }

  // "" = sem símbolo, "?" = índice inválido
  std::string lerValor(const cv::Mat& recorte) const {
    Simbolo s;
    if (!extrairSimbolo(recorte, s)) return "";
    int i = static_cast<int>(valores->predict(calcularHOG(s.img)));
    return (i >= 0 && i < static_cast<int>(NOMES_VALORES.size()))
               ? NOMES_VALORES[i]
               : "?";
  }

  std::string lerNaipe(const cv::Mat& recorte) const {
    Simbolo s;
    if (!extrairSimbolo(recorte, s)) return "";
    const auto& modelo = s.vermelho ? vermelhos : pretos;
    const auto& nomes =
        s.vermelho ? NOMES_NAIPES_VERMELHOS : NOMES_NAIPES_PRETOS;
    int i = static_cast<int>(modelo->predict(calcularHOG(s.img)));
    return (i >= 0 && i < static_cast<int>(nomes.size())) ? nomes[i] : "?";
  }
};

}  // namespace cartas

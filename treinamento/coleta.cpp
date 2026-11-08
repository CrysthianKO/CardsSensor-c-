// Coleta de amostras para treino.
//
// Uso:  ./coleta valores     (grava o recorte do NÚMERO)
//       ./coleta naipes      (grava o recorte do NAIPE)
//
// Teclas (modo valores): a 2 3 4 5 6 7 8 9, 0 = "10", j q k
// Teclas (modo naipes):  c = Copas, o = Ouros, e = Espadas, p = Paus
//   ESPAÇO = grava uma rajada de amostras da classe escolhida
//   x      = desfaz a última rajada
//   ESC    = sai
//
// As imagens (32x32) vão para dataset/<valores|naipes>/<classe>/N.png
// e já passam pelo MESMO pré-processamento do reconhecimento.

#include <filesystem>
#include <iostream>
#include <map>

#include "simbolo.hpp"

using namespace std;
using namespace cv;
using namespace cartas;
namespace fs = std::filesystem;

static int contarImagens(const fs::path& pasta) {
  if (!fs::exists(pasta)) return 0;
  int n = 0;
  for (const auto& e : fs::directory_iterator(pasta))
    if (e.path().extension() == ".png") ++n;
  return n;
}

static string novoCaminho(const fs::path& pasta) {
  fs::create_directories(pasta);
  for (int i = 0;; ++i) {
    fs::path p = pasta / (to_string(i) + ".png");
    if (!fs::exists(p)) return p.string();
  }
}

int main(int argc, char** argv) {
  if (argc < 2 || (string(argv[1]) != "valores" && string(argv[1]) != "naipes")) {
    cerr << "Uso: ./coleta valores|naipes\n";
    return 1;
  }
  const bool modo_valores = string(argv[1]) == "valores";
  const Rect roi = modo_valores ? ROI_NUMERO : ROI_NAIPE;
  const fs::path raiz = fs::path("dataset") / argv[1];
  const int TAM_RAJADA = 20;

  map<int, string> teclas;
  if (modo_valores) {
    teclas = {{'a', "A"}, {'2', "2"}, {'3', "3"}, {'4', "4"}, {'5', "5"},
              {'6', "6"}, {'7', "7"}, {'8', "8"}, {'9', "9"}, {'0', "10"},
              {'j', "J"}, {'q', "Q"}, {'k', "K"}};
  } else {
    teclas = {{'c', "Copas"}, {'o', "Ouros"}, {'e', "Espadas"}, {'p', "Paus"}};
  }

  VideoCapture cap(0, CAP_V4L2);
  if (!cap.isOpened()) {
    cerr << "Não abriu a câmera\n";
    return 1;
  }
  cap.set(CAP_PROP_FRAME_WIDTH, 640);
  cap.set(CAP_PROP_FRAME_HEIGHT, 480);

  string atual;                 // classe escolhida
  map<string, int> contagem;    // imagens por classe
  vector<string> lote;          // arquivos da última rajada (para desfazer)
  string lote_classe;
  int rajada = 0;               // amostras que ainda faltam gravar

  Mat bruto;
  while (true) {
    cap >> bruto;
    if (bruto.empty()) break;
    Mat frame = orientar(bruto);

    if ((roi & Rect(0, 0, frame.cols, frame.rows)) != roi) {
      cerr << "ROI fora do frame (" << frame.cols << "x" << frame.rows << ")\n";
      return 1;
    }

    Simbolo s;
    bool ok = extrairSimbolo(frame(roi), s);

    bool cor_ok = true;  // no modo naipes, a cor tem que bater com a classe
    if (ok && !modo_valores && !atual.empty()) {
      bool esperado_vermelho = (atual == "Copas" || atual == "Ouros");
      cor_ok = (s.vermelho == esperado_vermelho);
    }

    if (rajada > 0 && ok && cor_ok && !atual.empty()) {
      string caminho = novoCaminho(raiz / atual);
      imwrite(caminho, s.img);
      lote.push_back(caminho);
      lote_classe = atual;
      ++contagem[atual];
      --rajada;
    }

    // --- interface ---
    Mat tela = frame.clone();
    rectangle(tela, roi, Scalar(0, 255, 0), 2);
    auto texto = [&](const string& t, int linha, Scalar cor) {
      putText(tela, t, Point(8, 22 + 22 * linha), FONT_HERSHEY_SIMPLEX, 0.55,
              cor, 2);
    };
    texto(atual.empty() ? "Escolha a classe (teclas)"
                        : "Classe: " + atual + " (" +
                              to_string(contagem[atual]) + " imgs)",
          0, Scalar(255, 255, 0));
    texto(ok ? string("Simbolo OK - ") + (s.vermelho ? "vermelho" : "preto")
             : "Simbolo NAO detectado",
          1, ok ? Scalar(0, 255, 0) : Scalar(0, 0, 255));
    if (!cor_ok) texto("COR NAO BATE COM A CLASSE", 2, Scalar(0, 0, 255));
    if (rajada > 0) texto("Gravando... faltam " + to_string(rajada), 3, Scalar(0, 255, 255));
    texto("ESPACO=gravar x=desfazer ESC=sair", 27, Scalar(255, 255, 255));
    imshow("Coleta", tela);

    Mat previa = Mat::zeros(160, 160, CV_8UC1);
    if (ok) resize(s.img, previa, Size(160, 160), 0, 0, INTER_NEAREST);
    imshow("Simbolo (32x32 ampliado)", previa);

    int k = waitKey(rajada > 0 ? 80 : 1);
    if (k >= 0) k = tolower(k & 0xFF);
    if (k == 27) break;

    if (k == ' ') {
      if (!atual.empty()) {
        rajada = TAM_RAJADA;
        lote.clear();
      }
    } else if (k == 'x') {
      for (const auto& p : lote) fs::remove(p);
      if (!lote_classe.empty()) contagem[lote_classe] -= static_cast<int>(lote.size());
      lote.clear();
      rajada = 0;
    } else if (teclas.count(k)) {
      atual = teclas[k];
      rajada = 0;
      if (!contagem.count(atual)) contagem[atual] = contarImagens(raiz / atual);
    }
  }
  return 0;
}

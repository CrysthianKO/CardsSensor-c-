// Treino dos modelos a partir do dataset gerado pelo ./coleta.
//
// Uso:  ./treino [pasta_dataset]      (padrão: ./dataset)
//
// Gera na pasta atual:
//   modelo_valores.xml
//   modelo_naipes_vermelhos.xml   (Copas x Ouros)
//   modelo_naipes_pretos.xml      (Espadas x Paus)
//
// Rode no PC (não no Pi): o trainAuto testa vários parâmetros e é pesado.
// Depois copie os 3 .xml para a pasta do programa no Raspberry.

#include <filesystem>
#include <iostream>
#include <map>

#include "simbolo.hpp"

using namespace std;
using namespace cv;
using namespace cv::ml;
using namespace cartas;
namespace fs = std::filesystem;

constexpr int N_AUMENTOS = 6;     // variações geradas por imagem de treino
constexpr int MIN_POR_CLASSE = 10;

struct Amostra {
  Mat img;
  int rotulo;
};

static vector<Amostra> carregar(const string& pasta, const vector<string>& classes) {
  vector<Amostra> v;
  for (size_t c = 0; c < classes.size(); ++c) {
    fs::path dir = fs::path(pasta) / classes[c];
    int n = 0;
    if (fs::exists(dir)) {
      for (const auto& e : fs::directory_iterator(dir)) {
        if (e.path().extension() != ".png") continue;
        Mat img = imread(e.path().string(), IMREAD_GRAYSCALE);
        if (img.empty() || img.size() != Size(LADO, LADO)) continue;
        v.push_back({img, static_cast<int>(c)});
        ++n;
      }
    }
    cout << "  " << classes[c] << ": " << n << " imagens\n";
  }
  return v;
}

// Pequenas variações de posição/escala/rotação (a carta nunca entra
// exatamente no mesmo lugar).
static Mat aumentar(const Mat& img, RNG& rng) {
  double ang = rng.uniform(-6.0, 6.0);
  double esc = rng.uniform(0.9, 1.1);
  double dx = rng.uniform(-2.0, 2.0), dy = rng.uniform(-2.0, 2.0);
  Mat M = getRotationMatrix2D(Point2f(LADO / 2.f, LADO / 2.f), ang, esc);
  M.at<double>(0, 2) += dx;
  M.at<double>(1, 2) += dy;
  Mat out;
  warpAffine(img, out, M, img.size(), INTER_LINEAR, BORDER_CONSTANT, Scalar(0));
  return out;
}

static void montar(const vector<Amostra>& amostras, int n_aug, RNG& rng, Mat& X, Mat& y) {
  X.release();
  y.release();
  for (const auto& a : amostras) {
    X.push_back(calcularHOG(a.img));
    y.push_back(a.rotulo);
    for (int i = 0; i < n_aug; ++i) {
      X.push_back(calcularHOG(aumentar(a.img, rng)));
      y.push_back(a.rotulo);
    }
  }
}

// Divisão estratificada: 80% treino / 20% validação, por classe.
static void dividir(const vector<Amostra>& todas, double frac_val, RNG& rng,
                    vector<Amostra>& treino, vector<Amostra>& val) {
  map<int, vector<size_t>> por_classe;
  for (size_t i = 0; i < todas.size(); ++i) por_classe[todas[i].rotulo].push_back(i);
  for (auto& [classe, idx] : por_classe) {
    for (size_t i = idx.size(); i > 1; --i)
      swap(idx[i - 1], idx[rng.uniform(0, static_cast<int>(i))]);
    size_t n_val = max<size_t>(1, static_cast<size_t>(idx.size() * frac_val));
    for (size_t i = 0; i < idx.size(); ++i)
      (i < n_val ? val : treino).push_back(todas[idx[i]]);
  }
}

static Ptr<SVM> novoSVM() {
  Ptr<SVM> svm = SVM::create();
  svm->setType(SVM::C_SVC);
  svm->setKernel(SVM::RBF);
  svm->setTermCriteria(TermCriteria(TermCriteria::MAX_ITER + TermCriteria::EPS, 2000, 1e-6));
  return svm;
}

static void avaliar(const Ptr<SVM>& svm, const vector<Amostra>& val,
                    const vector<string>& classes) {
  int n = static_cast<int>(classes.size());
  vector<vector<int>> conf(n, vector<int>(n, 0));
  int acertos = 0;
  for (const auto& a : val) {
    int p = static_cast<int>(svm->predict(calcularHOG(a.img)));
    if (p >= 0 && p < n) conf[a.rotulo][p]++;
    if (p == a.rotulo) ++acertos;
  }
  cout << "  Validação: " << acertos << "/" << val.size() << " ("
       << (100.0 * acertos / max<size_t>(1, val.size())) << "%)\n";
  for (int i = 0; i < n; ++i)
    for (int j = 0; j < n; ++j)
      if (i != j && conf[i][j] > 0)
        cout << "    " << classes[i] << " lido como " << classes[j] << ": "
             << conf[i][j] << "x\n";
}

static bool treinarGrupo(const string& titulo, const string& pasta,
                         const vector<string>& classes, const string& saida) {
  cout << "== " << titulo << " ==\n";
  vector<Amostra> todas = carregar(pasta, classes);

  vector<int> por_classe(classes.size(), 0);
  for (const auto& a : todas) por_classe[a.rotulo]++;
  for (size_t c = 0; c < classes.size(); ++c) {
    if (por_classe[c] < MIN_POR_CLASSE) {
      cerr << "  ERRO: '" << classes[c] << "' tem só " << por_classe[c]
           << " imagens (mínimo " << MIN_POR_CLASSE << ").\n";
      return false;
    }
  }

  RNG rng(12345);
  vector<Amostra> treino, val;
  dividir(todas, 0.2, rng, treino, val);

  // 1) treina só com 80%, escolhendo C e gamma por validação cruzada
  Mat X, y;
  montar(treino, N_AUMENTOS, rng, X, y);
  Ptr<SVM> svm = novoSVM();
  cout << "  Treinando (" << X.rows << " vetores)... pode demorar alguns minutos\n";
  svm->trainAuto(TrainData::create(X, ROW_SAMPLE, y), 5);
  cout << "  C=" << svm->getC() << " gamma=" << svm->getGamma() << "\n";
  avaliar(svm, val, classes);

  // 2) retreina com TODAS as amostras usando os mesmos parâmetros
  Mat Xt, yt;
  montar(todas, N_AUMENTOS, rng, Xt, yt);
  Ptr<SVM> final_svm = novoSVM();
  final_svm->setC(svm->getC());
  final_svm->setGamma(svm->getGamma());
  final_svm->train(Xt, ROW_SAMPLE, yt);
  final_svm->save(saida);
  cout << "  Salvo em " << saida << " ("
       << final_svm->getSupportVectors().rows << " vetores de suporte)\n\n";
  return true;
}

int main(int argc, char** argv) {
  string raiz = argc > 1 ? argv[1] : "dataset";

  bool ok = true;
  ok &= treinarGrupo("Valores", raiz + "/valores", NOMES_VALORES, "modelo_valores.xml");
  ok &= treinarGrupo("Naipes vermelhos", raiz + "/naipes", NOMES_NAIPES_VERMELHOS,
                     "modelo_naipes_vermelhos.xml");
  ok &= treinarGrupo("Naipes pretos", raiz + "/naipes", NOMES_NAIPES_PRETOS,
                     "modelo_naipes_pretos.xml");
  return ok ? 0 : 1;
}

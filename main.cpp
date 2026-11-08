#include <opencv2/opencv.hpp>
#include <iostream>
#include <filesystem>
#include <map>
#include <string>

// Usamos namespace para não precisar escrever std:: toda hora
namespace fs = std::filesystem;
using namespace std;
using namespace cv;

// 1. Função para carregar os templates na memória
// Retorna um "mapa" (equivalente ao dicionário do Python) ligando o nome à imagem
map<string, Mat> carregarTemplates(const string& pasta) {
    map<string, Mat> templates_salvos;
    
    // Itera por todos os arquivos dentro da pasta
    for (const auto& entrada : fs::directory_iterator(pasta)) {
        if (entrada.path().extension() == ".png") {
            string nome = entrada.path().stem().string(); // Pega nome sem o .png
            string caminho = entrada.path().string();
            
            // Carrega em tons de cinza
            Mat img_template = imread(caminho, IMREAD_GRAYSCALE);
            
            // Verifica se a imagem foi encontrada
            if (img_template.empty()) {
                cout << "Erro ao carregar: " << caminho << endl;
                continue;
            }
            
            // Binarização: Pixels escuros viram pretos (0), claros viram brancos (255)
            Mat template_binario;
            threshold(img_template, template_binario, 128, 255, THRESH_BINARY_INV);
            
            templates_salvos[nome] = template_binario;
            cout << "Template carregado: " << nome << endl;
        }
    }
    return templates_salvos;
}

// Estrutura para retornar múltiplos valores (equivalente ao return nome, valor do Python)
struct ResultadoIdentificacao {
    string nome;
    double confianca;
};

// 2. Função de Identificação
ResultadoIdentificacao identificarSimbolo(const Mat& recorte_camera, const map<string, Mat>& templates) {
    ResultadoIdentificacao melhor_resultado = {"Desconhecido", 0.0};
    
    Mat gray, img_binaria;
    // Converte o recorte da câmera para cinza e binariza
    cvtColor(recorte_camera, gray, COLOR_BGR2GRAY);
    threshold(gray, img_binaria, 128, 255, THRESH_BINARY_INV);

    // Compara com cada template do nosso "dicionário"
    for (const auto& par : templates) {
        string nome_molde = par.first;
        Mat img_molde = par.second;
        
        Mat matriz_resultado;
        // Faz o Template Matching
        matchTemplate(img_binaria, img_molde, matriz_resultado, TM_CCOEFF_NORMED);
        
        double min_val, max_val;
        // Encontra o pico de similaridade na matriz de resultados
        minMaxLoc(matriz_resultado, &min_val, &max_val);
        
        // Atualiza se achar algo com maior similaridade
        if (max_val > melhor_resultado.confianca) {
            melhor_resultado.confianca = max_val;
            melhor_resultado.nome = nome_molde;
        }
    }
    
    // Taxa de confiança (70%)
    if (melhor_resultado.confianca > 0.7) {
        return melhor_resultado;
    }
    
    return {"Desconhecido", 0.0};
}

int main() {
    cout << "Iniciando sistema em C++..." << endl;
    
    // Carrega imagens da pasta "templates"
    map<string, Mat> templates = carregarTemplates("templates/");
    
    if(templates.empty()){
        cout << "Nenhum template encontrado. Encerrando." << endl;
        return -1;
    }

    // Inicializa a câmera usando V4L2 (Video4Linux2) para comunicação direta
    VideoCapture cap(0, CAP_V4L2);
    
    if (!cap.isOpened()) {
        cout << "Erro ao abrir a câmera!" << endl;
        return -1;
    }

    // Configuração de resolução (baixa resolução = alto desempenho)
    cap.set(CAP_PROP_FRAME_WIDTH, 640);
    cap.set(CAP_PROP_FRAME_HEIGHT, 480);
    // Configura 30 frames por segundo
    cap.set(CAP_PROP_FPS, 30);

    // Define a Região de Interesse (ROI) - X, Y, Largura, Altura
    Rect ROI_CARTA(100, 50, 60, 120);

    Mat frame, recorte;
    
    cout << "Varredura iniciada. Pressione 'q' para sair." << endl;

    // Loop contínuo
    while (true) {
        // Captura o frame direto do buffer de hardware
        cap >> frame; 
        
        if (frame.empty()) break;

        // Extrai a sub-matriz (apenas a área da carta) sem copiar dados na memória (super rápido!)
        recorte = frame(ROI_CARTA);

        // Processa o recorte
        ResultadoIdentificacao res = identificarSimbolo(recorte, templates);

        // Feedback Visual
        rectangle(frame, ROI_CARTA, Scalar(0, 255, 0), 2);
        
        string texto = res.nome + " (" + to_string(res.confianca).substr(0, 4) + ")";
        putText(frame, texto, Point(ROI_CARTA.x, ROI_CARTA.y - 10), 
                FONT_HERSHEY_SIMPLEX, 0.6, Scalar(0, 255, 0), 2);
        
        imshow("Scanner Otimizado C++", frame);

        // Espera 1ms por tecla, sai se for 'q'
        if (waitKey(1) == 'q') {
            break;
        }
    }

    // Limpa a memória e fecha janelas (Boa prática no C++)
    cap.release();
    destroyAllWindows();
    
    return 0;
}

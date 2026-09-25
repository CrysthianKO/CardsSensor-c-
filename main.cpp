#include <opencv2/opencv.hpp>
#include <iostream>

int main() {
    // PASSO 1: O "Olho" da Máquina
    // O número '0' indica a câmera padrão. O 'CAP_V4L2' é o driver do Linux.
    cv::VideoCapture cap(0, cv::CAP_V4L2);

    if (!cap.isOpened()) {
        std::cerr << "ERRO: A fábrica não conseguiu ligar a câmera!" << std::endl;
        return -1;
    }

    // PASSO 2: A Física da Luz
    // Reduzimos a resolução para que o Pi 3 consiga processar muitos quadros por segundo
    cap.set(cv::CAP_PROP_FRAME_WIDTH, 640);
    cap.set(cv::CAP_PROP_FRAME_HEIGHT, 480);

    // O C++ tenta forçar a exposição na câmera usando o padrão V4L2.
    // *Aviso de Hardware:* Dependendo da versão do sistema operacional do seu Pi,
    // o driver 'libcamera' pode bloquear essa alteração via OpenCV. 
    cap.set(cv::CAP_PROP_EXPOSURE, 1500); // Ajuste este valor numérico depois

    std::cout << "Câmera ligada! Pressione 'ESC' na janela de video para sair." << std::endl;

    // A memória onde os quadros vão morar
    cv::Mat frame_colorido, frame_cinza, frame_binario;
    std::vector<std::vector<cv::Point>> contornos;

    // PASSO 3: A Esteira da Linha de Montagem (Loop Infinito)
    while (true) {
        // "Puxa" um frame físico da câmera e empurra para a variável de memória
        cap >> frame_colorido;

        if (frame_colorido.empty()) {
            std::cerr << "ERRO: O frame veio vazio." << std::endl;
            break;
        }

        // O Daltônico: Convertemos para cinza porque a Visão Computacional
        // procura por bordas e contrastes, não por cores. Isso poupa memória.
        cv::cvtColor(frame_colorido, frame_cinza, cv::COLOR_BGR2GRAY);

        //Ajustar o 3º parametro para luz ideal
        cv::threshold(frame_cinza, frame_binario, 127, 255, cv::THRESH_BINARY);
    
        //Aqui ele ta finding os contournos
        cv::findContours(frame_binario, contornos, cv::RETR_EXTERNAL, cv::CHAIN_APPROX_SIMPLE);

        for(std::vector<cv::Point> contorno_atual : contornos){
            double area = cv::contourArea(contorno_atual);
            if(area < 15000) continue;
            cv::Rect caixa_da_carta = cv::boundingRect(contorno_atual);
                std:std::cout << "Carta x: " << caixa_da_carta.x << ",y: " << caixa_da_carta.y <<
                ",altura: "<< caixa_da_carta.height << ",largura: " << caixa_da_carta.width << std::endl;
        }

        // Mostra o resultado na tela do Raspberry Pi
        cv::imshow("Visao do Robo (Cinza)", frame_binario);

        // Espera 1 milissegundo. Se a tecla pressionada for 'ESC' (código 27), para a esteira.
        if (cv::waitKey(1) == 27) {
            break;
        }
    }

    // PASSO 4: Fechando a Fábrica e limpando a memória
    cap.release();
    cv::destroyAllWindows();
    return 0;
}

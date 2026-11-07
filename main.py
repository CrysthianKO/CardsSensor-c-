import cv2
from gpiozero import LED  # Importa apenas a ferramenta de LED da biblioteca de hardware

# 1. SETUP DE HARDWARE: Instancia o LED no GPIO 17 (pino físico 11)
# O gpiozero configura automaticamente como OUTPUT
led = LED(17)

# 2. INÍCIO DO EXPEDIENTE
print("Ligando o sistema...")
led.on()  # Envia 3.3V para o pino 17

# Inicia a conexão com a câmera
cap = cv2.VideoCapture(0)

# O Bloco 'try' é a nossa rede de segurança
try:
    if not cap.isOpened():
        print("Erro: Não foi possível acessar a câmera.")
        # Se falhar, o código pula para o 'finally' lá embaixo
    else:
        print("Câmera operando. Pressione 'q' na janela para encerrar.")

        # Definição do recorte (Y_inicial:Y_final, X_inicial:X_final)
        y_inicial, y_final = 200, 350
        x_inicial, x_final = 300, 400

        # TURNO DE TRABALHO: Loop contínuo
        while True:
            ret, frame = cap.read()
            if not ret:
                break

            # Processamento: Fatiamento, Tom de Cinza e Binarização
            roi = frame[y_inicial:y_final, x_inicial:x_final]
            frame_cinza = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
            _, imagem_binaria = cv2.threshold(
                frame_cinza, 128, 255, cv2.THRESH_BINARY_INV
            )

            # Janela de exibição
            cv2.imshow("Scanner (Aperte Q para sair)", imagem_binaria)

            # Verifica o botão de saída
            if cv2.waitKey(30) & 0xFF == ord("q"):
                break

# 3. FIM DO EXPEDIENTE (Garantido pelo bloco 'finally')
finally:
    print("Encerrando rotinas e desligando equipamentos...")
    # As linhas abaixo serão executadas MESMO SE o código der erro
    cap.release()
    cv2.destroyAllWindows()
    led.off()  # Corta a energia do pino 17 (0V)
    print("Sistema encerrado com segurança.")

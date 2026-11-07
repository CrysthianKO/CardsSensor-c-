import cv2
import time
from gpiozero import LED

# ==========================================
# 1. FÍSICA E ENERGIA (Setup do Hardware)
# ==========================================
# Instancia o controle do pino físico 11 (GPIO 17)
led = LED(17)

print("Energizando componentes...")
led.on()  # Dispara 3.3V no pino para acender a iluminação da carta

# Abre a comunicação direta com o Kernel do Linux via V4L2
cap = cv2.VideoCapture(0, cv2.CAP_V4L2)

# O Contrato de Memória: Força a alocação de uma matriz VGA
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

# ==========================================
# 2. A REDE DE SEGURANÇA (Garantia de Desligamento)
# ==========================================
try:
    if not cap.isOpened():
        print("ERRO CRÍTICO: Falha física ao acessar o módulo da câmera.")
    else:
        # A Sangria do Sistema (Buffer Flush)
        print("Limpando ruído elétrico inicial do sensor fotossensível...")
        sucesso_inicial = False

        # Tenta ler a matriz até 10 vezes (1 segundo de tolerância)
        for tentativa in range(10):
            ret, frame_teste = cap.read()
            if ret and frame_teste is not None:
                sucesso_inicial = True
                altura, largura, _ = frame_teste.shape
                print(
                    f"Sinal limpo na tentativa {tentativa + 1}! Câmera estabilizada em: {largura}x{altura}px."
                )
                break  # Quebra o loop de tentativas, pois a imagem é válida
            time.sleep(0.1)

        if not sucesso_inicial:
            print("FALHA DO SENSOR: Nenhuma matriz válida recebida após 10 tentativas.")
        else:
            # ==========================================
            # 3. A MATEMÁTICA (Processamento de Imagem)
            # ==========================================
            print("Scanner online. Pressione 'q' na janela para encerrar.")

            # Coordenadas do Recorte / "Buraco da Fechadura"
            # Importante: Como travamos a câmera em 640x480, esses valores
            # nunca podem ser maiores que 480 (em Y) e 640 (em X).
            y_inicial, y_final = 200, 350
            x_inicial, x_final = 300, 400

            while True:
                ret, frame = cap.read()

                # Se ocorrer uma falha repentina (ex: mau contato no cabo durante a execução)
                if not ret:
                    print("Aviso: Falha repentina de leitura do hardware.")
                    break

                # Fatiamento da Matriz Numérica (Slicing)
                roi = frame[y_inicial:y_final, x_inicial:x_final]

                # Conversão para escala de cinza e aplicação do filtro de Alto Contraste
                frame_cinza = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
                _, imagem_binaria = cv2.threshold(
                    frame_cinza, 128, 255, cv2.THRESH_BINARY_INV
                )

                # Renderização Visual
                cv2.imshow("Scanner de Cartas (Aperte Q para sair)", imagem_binaria)

                # O gatilho de saída amigável do loop principal
                if cv2.waitKey(30) & 0xFF == ord("q"):
                    break

# ==========================================
# 4. LIBERAÇÃO DE RECURSOS (Limpeza de Memória)
# ==========================================
finally:
    print("\nDesligando sistema de escaneamento...")
    cap.release()  # Devolve a porta de vídeo para o sistema operacional
    cv2.destroyAllWindows()  # Limpa os ponteiros de janela da memória RAM
    led.off()  # Corta a tensão de 3.3V do pino 17
    print("Componentes elétricos desativados com segurança.")

import cv2
import time
from gpiozero import LED

# ==========================================
# 1. SETUP DE HARDWARE E LUZ
# ==========================================
# Configura o pino 17 (físico 11) como saída de energia
led = LED(17)

print("Ligando o sistema...")
led.on()  # Acende o LED branco para iluminar a abertura da carta

# ==========================================
# 2. INICIALIZAÇÃO DA CÂMERA (A "Vacina" V4L2)
# ==========================================
# Força o OpenCV a falar diretamente com o Kernel do Linux (CAP_V4L2)
cap = cv2.VideoCapture(0, cv2.CAP_V4L2)

# Tempo de "Warm-up": Congela o código por 2 segundos para o sensor
# fotossensível medir a luz do seu LED branco e focar a imagem.
print("Aguardando o aquecimento e ajuste de luz do sensor...")
time.sleep(2.0)

# A Rede de Segurança: Garante que o LED apague no final, independente do que aconteça
try:
    if not cap.isOpened():
        print("ERRO CRÍTICO: Não foi possível acessar a porta da câmera.")
    else:
        # TESTE DE DIAGNÓSTICO: Tira uma foto "invisível" só para checar a resolução
        ret_teste, frame_teste = cap.read()
        if ret_teste:
            altura, largura, canais = frame_teste.shape
            print(
                f"Sucesso! Câmera operando na resolução física: {largura}x{altura} pixels."
            )

        print("Pressione 'q' na janela de vídeo para encerrar corretamente.")

        # Definição do recorte matemático (O "Buraco da Fechadura")
        # Y = Altura (Linhas), X = Largura (Colunas)
        y_inicial, y_final = 200, 350
        x_inicial, x_final = 300, 400

        # ==========================================
        # 3. TURNO DE TRABALHO (Loop Principal)
        # ==========================================
        while True:
            # Captura o quadro atual
            ret, frame = cap.read()

            # Diagnóstico da Saída Silenciosa
            if not ret:
                print(
                    "FALHA NA CAPTURA: A porta está aberta, mas o hardware parou de enviar a matriz de pixels."
                )
                break

            # Aplica o Fatiamento (Slicing) para isolar a carta
            roi = frame[y_inicial:y_final, x_inicial:x_final]

            # Vacina contra erro de resolução: Se a ROI ficar vazia, avisa o usuário
            if roi.size == 0:
                print(
                    "ERRO DE MATEMÁTICA: As coordenadas do recorte (ROI) estão maiores que a resolução da câmera!"
                )
                break

            # Visão Clássica: Converte para Cinza (1 canal) e aplica o Alto Contraste
            frame_cinza = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
            _, imagem_binaria = cv2.threshold(
                frame_cinza, 128, 255, cv2.THRESH_BINARY_INV
            )

            # Exibe a interface
            cv2.imshow("Scanner de Cartas (Aperte Q para sair)", imagem_binaria)
            # Dica: Se quiser ver a câmera original para ajudar a calibrar, descomente a linha abaixo:
            # cv2.imshow("Camera Completa", frame)

            # Aguarda 30ms. Se a tecla pressionada for 'q', o loop quebra.
            if cv2.waitKey(30) & 0xFF == ord("q"):
                break

# ==========================================
# 4. FIM DO EXPEDIENTE
# ==========================================
finally:
    print("\nEncerrando rotinas e desligando equipamentos...")
    cap.release()
    cv2.destroyAllWindows()
    led.off()  # Corta a energia de 3.3V do Raspberry Pi
    print("Sistema desligado com segurança.")

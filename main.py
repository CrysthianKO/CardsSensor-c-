import cv2
from picamera2 import Picamera2

# 1. Inicializa a câmera
picam2 = Picamera2()

# 2. Configura para modo de vídeo (fluxo contínuo)
config = picam2.create_video_configuration(main={"size": (640, 480)})
picam2.configure(config)
picam2.start()

print("Pressione a tecla 'q' na janela de vídeo para sair.")

try:
    while True:
        # Pega o frame atual da câmera como uma matriz de dados
        frame = picam2.capture_array()

        # O OpenCV desenha essa matriz em uma janela de software comum
        cv2.imshow("Visão do Raspberry Pi", frame)

        # Espera 1 milissegundo e verifica se a tecla 'q' foi pressionada
        if cv2.waitKey(1) & 0xFF == ord("q"):
            break
finally:
    # Garante que a câmera e as janelas sejam fechadas mesmo se houver erro
    picam2.stop()
    cv2.destroyAllWindows()

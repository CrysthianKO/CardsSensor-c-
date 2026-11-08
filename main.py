# 1. Importamos o 'tradutor' da câmera e o controlador de tempo
from picamera import PiCamera2
from time import sleep

# 2. Inicializamos a câmera (o sensor liga neste momento)
camera = PiCamera()

# 3. Ligamos a transmissão de imagem na tela
camera.start_preview()

# 4. Deixamos a transmissão rodando por 5 segundos
sleep(5)

# 5. Fechamos a transmissão de imagem
camera.stop_preview()

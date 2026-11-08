# 1. Importamos o 'tradutor' da câmera e o controlador de tempo
from picamera2 import Picamera2
from time import sleep

# 2. Inicializamos a câmera (o sensor liga neste momento)
camera = Picamera2()

# 3. Ligamos a transmissão de imagem na tela
camera.start_preview()

# 4. Deixamos a transmissão rodando por 5 segundos
sleep(20)

# 5. Fechamos a transmissão de imagem
camera.stop_preview()

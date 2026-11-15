import time
from sensor_ir import SensorInfravermelho

# 1. Instancia o sensor no GPIO 17
sensor = SensorInfravermelho(pino_gpio=17)


# OPÇÃO A: Por Evento / Interrupção (ideal para pontuar, pular ou disparar ações)
def gatilho_pontuacao():
    print("Evento: Objeto passou pelo sensor! +10 pontos")


sensor.ao_detectar(gatilho_pontuacao)

# Loop principal do seu jogo (ex: Pygame, Flet, terminal, etc.)
try:
    while True:
        # OPÇÃO B: Consulta de Estado Contínua (ideal para verificar se algo está parado na frente)
        if sensor.objeto_detectado:
            print("Detectado")
            # Lógica contínua enquanto o objeto estiver bloqueando o feixe
            pass
        print("Vazio")
        time.sleep(0.016)  # Simula ~60 FPS do seu jogo

except KeyboardInterrupt:
    sensor.fechar()

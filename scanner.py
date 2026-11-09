#!/usr/bin/env python3
"""Scanner de cartas em Python (alternativa ao main.cpp quando o OpenCV em
C++ não consegue ler a câmera do Raspberry).

Fala exatamente o mesmo protocolo do main.cpp, então o controle.py funciona
sem mudanças:  python3 controle.py scanner.py

Comandos (um por linha, no STDIN):  LIGAR | DESLIGAR | SAIR
Eventos (um por linha, no STDOUT):  PRONTO | CAMERA_LIGADA | CAMERA_DESLIGADA
                                    CARTA;<valor>;<naipe> | CARTA_REMOVIDA
                                    ERRO;<mensagem>
Logs para humanos vão para o STDERR.

Precisa estar na mesma pasta que coleta.py e treino.py (reaproveita o
pré-processamento do símbolo e o HOG, para ser idêntico ao do dataset e do
treino) e dos três modelo_*.xml (lidos da pasta de trabalho).

Instalação no Pi:  sudo apt install python3-picamera2 python3-opencv python3-libgpiod
"""

import sys
import threading
import time

import cv2

from coleta import LIMIAR_PRESENCA, ROI_NAIPE, ROI_NUMERO, extrair_simbolo, orientar
from treino import (
    NOMES_NAIPES_PRETOS,
    NOMES_NAIPES_VERMELHOS,
    NOMES_VALORES,
    calcular_hog,
)

VOTOS_NECESSARIOS = 5  # leituras iguais seguidas para aceitar a carta
INTERVALO = 0.1  # segundos entre leituras (~10 por segundo)
PINO_LED = 17
CHIP_LED = "/dev/gpiochip0"  # em alguns modelos do Pi pode ser outro

estado = {"quer_camera": False, "rodando": True}


def log(msg):
    print(msg, file=sys.stderr, flush=True)


def evento(msg):
    print(msg, flush=True)


# --------------------------------------------------------------------- LED
class Led:
    """LED opcional via libgpiod v2. Sem a biblioteca, segue sem LED."""

    def __init__(self, pino, chip):
        self.pino = pino
        self.req = None
        try:
            import gpiod
            from gpiod.line import Direction, Value

            self._valor = Value
            self.req = gpiod.request_lines(
                chip,
                consumer="scanner",
                config={
                    pino: gpiod.LineSettings(
                        direction=Direction.OUTPUT, output_value=Value.INACTIVE
                    )
                },
            )
        except Exception as e:
            log(f"LED indisponível ({e}); seguindo sem LED")

    def ligar(self):
        if self.req:
            self.req.set_value(self.pino, self._valor.ACTIVE)

    def desligar(self):
        if self.req:
            self.req.set_value(self.pino, self._valor.INACTIVE)

    def fechar(self):
        if self.req:
            self.desligar()
            self.req.release()


# ------------------------------------------------------------------ Câmera
def abrir_camera():
    from picamera2 import Picamera2

    if not Picamera2.global_camera_info():
        raise RuntimeError("o libcamera nao detectou nenhuma camera")
    cam = Picamera2()
    # Em picamera2, "RGB888" entrega o array na ordem B,G,R (a do OpenCV).
    cam.configure(
        cam.create_video_configuration(main={"size": (640, 480), "format": "RGB888"})
    )
    cam.start()
    time.sleep(1.0)  # exposição e balanço de branco estabilizarem
    return cam


def fechar_camera(cam):
    try:
        cam.stop()
    finally:
        cam.close()  # libera a câmera e para de gastar CPU


# ----------------------------------------------------------- Reconhecimento
def ha_carta(recorte):
    return cv2.mean(cv2.cvtColor(recorte, cv2.COLOR_BGR2GRAY))[0] >= LIMIAR_PRESENCA


def prever(modelo, nomes, img):
    _, r = modelo.predict(calcular_hog(img).reshape(1, -1))
    i = int(r[0][0])
    return nomes[i] if 0 <= i < len(nomes) else "?"


def carregar_modelos():
    try:
        return (
            cv2.ml.SVM_load("modelo_valores.xml"),
            cv2.ml.SVM_load("modelo_naipes_vermelhos.xml"),
            cv2.ml.SVM_load("modelo_naipes_pretos.xml"),
        )
    except cv2.error as e:
        evento("ERRO;nao carregou os modelos (rode na pasta dos .xml)")
        log(str(e))
        return None


def recortar(frame, roi):
    x, y, w, h = roi
    return frame[y : y + h, x : x + w]


# ---------------------------------------------------------------- Comandos
def ler_comandos():
    for linha in sys.stdin:
        cmd = linha.strip()
        if cmd == "LIGAR":
            estado["quer_camera"] = True
        elif cmd == "DESLIGAR":
            estado["quer_camera"] = False
        elif cmd == "SAIR":
            break
        elif cmd:
            log(f"Comando desconhecido: {cmd}")
    estado["rodando"] = False  # SAIR ou STDIN fechado (o outro programa morreu)


def main():
    modelos = carregar_modelos()
    if modelos is None:
        return 1
    svm_valores, svm_vermelhos, svm_pretos = modelos

    led = Led(PINO_LED, CHIP_LED)
    threading.Thread(target=ler_comandos, daemon=True).start()
    evento("PRONTO")

    cam = None
    carta_em_leitura = False
    ultima, repeticoes = None, 0

    try:
        while estado["rodando"]:
            # --- liga/desliga a câmera conforme o último comando recebido ---
            if estado["quer_camera"] and cam is None:
                try:
                    cam = abrir_camera()
                    led.ligar()
                    carta_em_leitura, ultima, repeticoes = False, None, 0
                    evento("CAMERA_LIGADA")
                except Exception as e:
                    estado["quer_camera"] = False
                    evento(f"ERRO;nao abriu a camera ({e})")
            elif not estado["quer_camera"] and cam is not None:
                fechar_camera(cam)
                cam = None
                led.desligar()
                evento("CAMERA_DESLIGADA")

            # Câmera desligada: não gasta CPU, só espera o próximo comando.
            if cam is None:
                time.sleep(0.1)
                continue

            inicio = time.time()
            try:
                bruto = cam.capture_array("main")
            except Exception as e:
                evento(f"ERRO;falha ao capturar frame ({e})")
                estado["quer_camera"] = False
                continue

            frame = orientar(bruto)
            rec_numero = recortar(frame, ROI_NUMERO)
            rec_naipe = recortar(frame, ROI_NAIPE)
            if rec_numero.shape[:2] != (
                ROI_NUMERO[3],
                ROI_NUMERO[2],
            ) or rec_naipe.shape[:2] != (ROI_NAIPE[3], ROI_NAIPE[2]):
                evento(f"ERRO;ROI fora do frame ({frame.shape[1]}x{frame.shape[0]})")
                estado["quer_camera"] = False
                continue

            if carta_em_leitura:
                # Já leu: só confere (barato) se a carta saiu, sem rodar o SVM.
                if not ha_carta(rec_numero) or not ha_carta(rec_naipe):
                    evento("CARTA_REMOVIDA")
                    carta_em_leitura, ultima, repeticoes = False, None, 0
            else:
                res_valor = extrair_simbolo(rec_numero)
                res_naipe = extrair_simbolo(rec_naipe)
                valor = naipe = ""
                if res_valor is not None:
                    valor = prever(svm_valores, NOMES_VALORES, res_valor[0])
                if res_naipe is not None:
                    img, vermelho = res_naipe
                    if vermelho:
                        naipe = prever(svm_vermelhos, NOMES_NAIPES_VERMELHOS, img)
                    else:
                        naipe = prever(svm_pretos, NOMES_NAIPES_PRETOS, img)

                if valor and naipe and valor != "?" and naipe != "?":
                    leitura = (valor, naipe)
                    repeticoes = repeticoes + 1 if leitura == ultima else 1
                    ultima = leitura
                    if repeticoes >= VOTOS_NECESSARIOS:
                        evento(f"CARTA;{valor};{naipe}")
                        carta_em_leitura = True
                else:
                    ultima, repeticoes = None, 0

            # Mantém ~10 leituras por segundo para poupar a CPU do Pi.
            resto = INTERVALO - (time.time() - inicio)
            if resto > 0:
                time.sleep(resto)
    finally:
        if cam is not None:
            fechar_camera(cam)
        led.fechar()
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(0)
    except Exception as e:
        evento(f"ERRO;{e}")
        sys.exit(1)

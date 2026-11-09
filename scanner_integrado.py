import sys
import threading
import time
import cv2
import numpy as np

# Configurações de ROI (x, y, largura, altura) para recortes no frame já orientado
ROI_NUMERO = (179, 250, 79, 101)
ROI_NAIPE = (179, 352, 82, 86)

LIMIAR_PRESENCA = 100.0  # Teste aumentar de 50.0 para 100.0 ou 120.0
LIMIAR_VERMELHO = 30.0
AREA_MIN = 15.0
LADO = 32

NOMES_VALORES = ["A", "2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K"]
NOMES_NAIPES_VERMELHOS = ["Copas", "Ouros"]
NOMES_NAIPES_PRETOS = ["Espadas", "Paus"]

# Estado global compartilhado com a thread de comandos
estado = {"quer_camera": False, "rodando": True}


def log(msg):
    # Logs para debug vão para o STDERR para não sujar o STDOUT que é usado no IPC
    print(msg, file=sys.stderr, flush=True)


def evento(msg):
    # Eventos de IPC vão para o STDOUT
    print(msg, flush=True)


class Led:
    def __init__(self, pino):
        self.pino = pino
        try:
            import gpiod

            self.chip = gpiod.Chip("gpiochip0")
            self.linha = self.chip.get_line(pino)
            self.linha.request(consumer="scanner", type=gpiod.LINE_REQ_DIR_OUT)
            self.ativo = True
        except Exception as e:
            self.ativo = False
            log(f"LED indisponível ({e}); seguindo sem controle de iluminação.")

    def ligar(self):
        if self.ativo:
            self.linha.set_value(1)

    def desligar(self):
        if self.ativo:
            self.linha.set_value(0)


def orientar(bruto):
    # Rotaciona 90 graus anti-horário e espelha horizontalmente (equivalente ao main.cpp)
    girado = cv2.rotate(bruto, cv2.ROTATE_90_COUNTERCLOCKWISE)
    return cv2.flip(girado, 1)


def calcular_hog(img):
    # Extração de características (mesmos parâmetros do C++)
    hog = cv2.HOGDescriptor((32, 32), (16, 16), (8, 8), (8, 8), 9)
    return hog.compute(img).reshape(1, -1)


def extrair_simbolo(recorte):
    # Implementação baseada no 'simbolo.hpp'
    cinza = cv2.cvtColor(recorte, cv2.COLOR_BGR2GRAY)
    if cv2.mean(cinza)[0] < LIMIAR_PRESENCA:
        return None

    cinza_blur = cv2.GaussianBlur(cinza, (3, 3), 0)
    _, binaria = cv2.threshold(
        cinza_blur, 0, 255, cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU
    )

    contornos, _ = cv2.findContours(binaria, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    area_max = 0.5 * recorte.size / 3  # recorte.size é o total de pixels por canal
    x_min, y_min, x_max, y_max = 9999, 9999, -1, -1
    achou = False

    for c in contornos:
        a = cv2.contourArea(c)
        if a < AREA_MIN or a > area_max:
            continue
        x, y, w, h = cv2.boundingRect(c)
        x_min = min(x_min, x)
        y_min = min(y_min, y)
        x_max = max(x_max, x + w)
        y_max = max(y_max, y + h)
        achou = True

    if not achou:
        return None

    tinta = binaria[y_min:y_max, x_min:x_max]
    lado_sq = max(tinta.shape[1], tinta.shape[0])
    margem = max(2, lado_sq // 8)

    quadrado = np.zeros((lado_sq + 2 * margem, lado_sq + 2 * margem), dtype=np.uint8)
    ox = margem + (lado_sq - tinta.shape[1]) // 2
    oy = margem + (lado_sq - tinta.shape[0]) // 2
    quadrado[oy : oy + tinta.shape[0], ox : ox + tinta.shape[1]] = tinta

    img_redim = cv2.resize(quadrado, (LADO, LADO), interpolation=cv2.INTER_AREA)

    # Análise de cor da tinta (Verificação se é vermelho)
    mascara = binaria[y_min:y_max, x_min:x_max]
    recorte_roi = recorte[y_min:y_max, x_min:x_max]
    media_bgr = cv2.mean(recorte_roi, mask=mascara)
    vermelho = (media_bgr[2] - 0.5 * (media_bgr[0] + media_bgr[1])) > LIMIAR_VERMELHO

    return img_redim, vermelho


def ha_carta(recorte):
    cinza = cv2.cvtColor(recorte, cv2.COLOR_BGR2GRAY)
    return cv2.mean(cinza)[0] >= LIMIAR_PRESENCA


def prever(modelo, nomes, img):
    caracteristicas = np.float32(calcular_hog(img))
    _, r = modelo.predict(caracteristicas)
    i = int(r[0][0])
    return nomes[i] if 0 <= i < len(nomes) else "?"


def ler_comandos():
    # Loop bloqueante para escutar comandos do aplicativo pai no STDIN
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
    estado["rodando"] = False


def main():
    try:
        svm_valores = cv2.ml.SVM_load("modelo_valores.xml")
        svm_vermelhos = cv2.ml.SVM_load("modelo_naipes_vermelhos.xml")
        svm_pretos = cv2.ml.SVM_load("modelo_naipes_pretos.xml")
    except Exception as e:
        evento("ERRO;Nao foi possivel carregar os modelos XML. Rode na mesma pasta.")
        return 1

    led = Led(17)

    # Inicia a thread que escuta comandos
    threading.Thread(target=ler_comandos, daemon=True).start()
    evento("PRONTO")

    cap = None
    carta_em_leitura = False
    ultima, repeticoes = None, 0
    VOTOS_NECESSARIOS = 5

    try:
        while estado["rodando"]:
            # Controle de estado da câmera para o CABO FLAT (CSI) via picamera2
            if estado["quer_camera"] and cap is None:
                from picamera2 import Picamera2

                cap = Picamera2()
                cap.configure(
                    cap.create_video_configuration(
                        main={"size": (640, 480), "format": "RGB888"}
                    )
                )
                cap.start()
                time.sleep(1.0)  # Tempo vital para a lente ajustar foco e exposição
                led.ligar()
                carta_em_leitura, ultima, repeticoes = False, None, 0
                evento("CAMERA_LIGADA")

            elif not estado["quer_camera"] and cap is not None:
                cap.stop()
                cap.close()
                cap = None
                led.desligar()
                evento("CAMERA_DESLIGADA")

            if cap is None:
                time.sleep(0.1)
                continue

            # Captura de frame específica da biblioteca picamera2
            try:
                bruto = cap.capture_array("main")
            except Exception as e:
                log(f"ERRO: Falha ao capturar frame da câmera plana: {e}")
                time.sleep(0.1)
                continue

            frame = orientar(bruto)
            rx, ry, rw, rh = ROI_NUMERO
            nx, ny, nw, nh = ROI_NAIPE
            rec_num = frame[ry : ry + rh, rx : rx + rw]
            rec_nai = frame[ny : ny + nh, nx : nx + nw]

            if carta_em_leitura:
                if not ha_carta(rec_num) or not ha_carta(rec_nai):
                    evento("CARTA_REMOVIDA")
                    carta_em_leitura, ultima, repeticoes = False, None, 0
            else:
                res_v = extrair_simbolo(rec_num)
                res_n = extrair_simbolo(rec_nai)
                valor = naipe = ""

                if res_v is not None:
                    valor = prever(svm_valores, NOMES_VALORES, res_v[0])
                if res_n is not None:
                    img_n, is_red = res_n
                    naipe = (
                        prever(svm_vermelhos, NOMES_NAIPES_VERMELHOS, img_n)
                        if is_red
                        else prever(svm_pretos, NOMES_NAIPES_PRETOS, img_n)
                    )

                if valor and naipe and valor != "?" and naipe != "?":
                    leitura = (valor, naipe)
                    repeticoes = repeticoes + 1 if leitura == ultima else 1
                    ultima = leitura
                    if repeticoes >= VOTOS_NECESSARIOS:
                        evento(f"CARTA;{valor};{naipe}")
                        carta_em_leitura = True
                else:
                    ultima, repeticoes = None, 0

            # Janela de Raio-X para centralização da carta
            cv2.rectangle(frame, (rx, ry), (rx + rw, ry + rh), (255, 0, 0), 2)
            cv2.rectangle(frame, (nx, ny), (nx + nw, ny + nh), (0, 0, 255), 2)
            cv2.imshow("Raio-X do Scanner", frame)
            cv2.waitKey(1)

            time.sleep(0.1)
    finally:
        if cap is not None:
            cap.stop()
            cap.close()
        led.desligar()


if __name__ == "__main__":
    main()

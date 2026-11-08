#!/usr/bin/env python3
"""Coleta de amostras para treino (versão Python da coleta.cpp).

Uso:  python3 coleta.py valores [indice_camera]   (grava o recorte do NÚMERO)
      python3 coleta.py naipes  [indice_camera]   (grava o recorte do NAIPE)

Teclas (modo valores): a 2 3 4 5 6 7 8 9, 0 = "10", j q k
Teclas (modo naipes):  c = Copas, o = Ouros, e = Espadas, p = Paus
  ESPAÇO = grava uma rajada de amostras da classe escolhida
  x      = desfaz a última rajada
  ESC    = sai

As imagens (32x32) vão para dataset/<valores|naipes>/<classe>/N.png.

ATENÇÃO: o pré-processamento abaixo é uma cópia fiel de simbolo.hpp
(extrairSimbolo). Se você mudar um, mude o outro.

No Raspberry, instale com:  sudo apt install python3-opencv
"""
import sys
import time
from pathlib import Path

import cv2
import numpy as np

# ------------------------------------------------ Config (igual ao simbolo.hpp)
LADO = 32
LIMIAR_PRESENCA = 50.0
LIMIAR_VERMELHO = 30.0
AREA_MIN = 15.0
ROI_NUMERO = (195, 245, 100, 105)  # (x, y, largura, altura) no frame girado
ROI_NAIPE = (195, 340, 100, 115)
TAM_RAJADA = 20

TECLAS_VALORES = {
    "a": "A", "2": "2", "3": "3", "4": "4", "5": "5", "6": "6", "7": "7",
    "8": "8", "9": "9", "0": "10", "j": "J", "q": "Q", "k": "K",
}
TECLAS_NAIPES = {"c": "Copas", "o": "Ouros", "e": "Espadas", "p": "Paus"}


# ------------------------------------------------------------------ Imagem
def orientar(bruto):
    girado = cv2.rotate(bruto, cv2.ROTATE_90_COUNTERCLOCKWISE)
    return cv2.flip(girado, 1)


def extrair_simbolo(recorte):
    """Retorna (imagem 32x32, vermelho) ou None se não houver símbolo."""
    cinza = cv2.cvtColor(recorte, cv2.COLOR_BGR2GRAY)
    if cv2.mean(cinza)[0] < LIMIAR_PRESENCA:
        return None

    cinza = cv2.GaussianBlur(cinza, (3, 3), 0)
    _, binaria = cv2.threshold(
        cinza, 0, 255, cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU
    )

    contornos = cv2.findContours(binaria, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)[-2]

    # União das caixas de todos os contornos relevantes ("10", espadas...).
    area_max = 0.5 * recorte.shape[0] * recorte.shape[1]
    caixa = None  # (x0, y0, x1, y1)
    for c in contornos:
        area = cv2.contourArea(c)
        if area < AREA_MIN or area > area_max:
            continue
        x, y, w, h = cv2.boundingRect(c)
        if caixa is None:
            caixa = (x, y, x + w, y + h)
        else:
            caixa = (min(caixa[0], x), min(caixa[1], y),
                     max(caixa[2], x + w), max(caixa[3], y + h))
    if caixa is None:
        return None

    x0, y0, x1, y1 = caixa
    tinta = binaria[y0:y1, x0:x1]
    h, w = tinta.shape
    lado = max(w, h)
    margem = max(2, lado // 8)
    quadrado = np.zeros((lado + 2 * margem, lado + 2 * margem), dtype=np.uint8)
    ox = margem + (lado - w) // 2
    oy = margem + (lado - h) // 2
    quadrado[oy:oy + h, ox:ox + w] = tinta
    img = cv2.resize(quadrado, (LADO, LADO), interpolation=cv2.INTER_AREA)

    b, g, r, _ = cv2.mean(recorte[y0:y1, x0:x1], mask=binaria[y0:y1, x0:x1])
    vermelho = (r - 0.5 * (b + g)) > LIMIAR_VERMELHO
    return img, vermelho


# ------------------------------------------------------------------ Câmera
def abrir_camera(indice):
    """Tenta várias configurações e devolve a primeira que entrega frames."""
    tentativas = [
        ("V4L2 640x480", cv2.CAP_V4L2, True, False),
        ("V4L2 sem definir resolução", cv2.CAP_V4L2, False, False),
        ("V4L2 MJPG 640x480", cv2.CAP_V4L2, True, True),
        ("backend automático", cv2.CAP_ANY, True, False),
    ]
    for nome, backend, definir, mjpg in tentativas:
        cap = cv2.VideoCapture(indice, backend)
        if not cap.isOpened():
            print(f"  [{nome}] não abriu")
            cap.release()
            continue
        if mjpg:
            cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
        if definir:
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        for _ in range(30):
            ok, frame = cap.read()
            if ok and frame is not None and frame.size:
                print(f"  [{nome}] OK, frame {frame.shape[1]}x{frame.shape[0]}")
                return cap
            time.sleep(0.05)
        print(f"  [{nome}] abriu, mas não entregou frames")
        cap.release()
        time.sleep(0.5)
    return None


# -------------------------------------------------------------------- Dados
def contar_imagens(pasta):
    return len(list(pasta.glob("*.png"))) if pasta.is_dir() else 0


def novo_caminho(pasta):
    pasta.mkdir(parents=True, exist_ok=True)
    i = 0
    while (pasta / f"{i}.png").exists():
        i += 1
    return pasta / f"{i}.png"


def main():
    if len(sys.argv) < 2 or sys.argv[1] not in ("valores", "naipes"):
        print("Uso: python3 coleta.py valores|naipes [indice_camera]")
        sys.exit(1)
    modo_valores = sys.argv[1] == "valores"
    indice = int(sys.argv[2]) if len(sys.argv) > 2 else 0
    roi = ROI_NUMERO if modo_valores else ROI_NAIPE
    teclas = TECLAS_VALORES if modo_valores else TECLAS_NAIPES
    raiz = Path("dataset") / sys.argv[1]

    print(f"Abrindo a câmera {indice}...")
    cap = abrir_camera(indice)
    if cap is None:
        print("Nenhuma configuração entregou frames. Se isso também falhar aqui,"
              " o problema está na câmera/driver/alimentação, não no código.")
        sys.exit(1)
    print("Câmera pronta. Escolha a classe pelas teclas (ESC sai).")

    atual = ""
    contagem = {}
    lote, lote_classe = [], ""
    rajada = 0
    falhas = 0

    while True:
        ok_leitura, bruto = cap.read()
        if not ok_leitura or bruto is None or bruto.size == 0:
            falhas += 1
            if falhas >= 30:
                print("Perdi a câmera (30 leituras vazias seguidas).")
                break
            time.sleep(0.05)
            continue
        falhas = 0

        frame = orientar(bruto)
        x, y, w, h = roi
        if x + w > frame.shape[1] or y + h > frame.shape[0]:
            print(f"ROI fora do frame ({frame.shape[1]}x{frame.shape[0]}). "
                  "A resolução não é 640x480; ajuste os ROIs.")
            break

        resultado = extrair_simbolo(frame[y:y + h, x:x + w])
        ok = resultado is not None
        img, vermelho = resultado if ok else (None, False)

        cor_ok = True  # no modo naipes, a cor tem que bater com a classe
        if ok and not modo_valores and atual:
            cor_ok = vermelho == (atual in ("Copas", "Ouros"))

        if rajada > 0 and ok and cor_ok and atual:
            caminho = novo_caminho(raiz / atual)
            cv2.imwrite(str(caminho), img)
            lote.append(caminho)
            lote_classe = atual
            contagem[atual] = contagem.get(atual, 0) + 1
            rajada -= 1

        # --- interface (só ASCII: as fontes do OpenCV não têm acentos) ---
        tela = frame.copy()
        cv2.rectangle(tela, (x, y), (x + w, y + h), (0, 255, 0), 2)

        def texto(t, linha, cor):
            cv2.putText(tela, t, (8, 22 + 22 * linha),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.55, cor, 2)

        if atual:
            texto(f"Classe: {atual} ({contagem.get(atual, 0)} imgs)", 0, (255, 255, 0))
        else:
            texto("Escolha a classe (teclas)", 0, (255, 255, 0))
        if ok:
            texto("Simbolo OK - " + ("vermelho" if vermelho else "preto"), 1, (0, 255, 0))
        else:
            texto("Simbolo NAO detectado", 1, (0, 0, 255))
        if not cor_ok:
            texto("COR NAO BATE COM A CLASSE", 2, (0, 0, 255))
        if rajada > 0:
            texto(f"Gravando... faltam {rajada}", 3, (0, 255, 255))
        texto("ESPACO=gravar x=desfazer ESC=sair", 27, (255, 255, 255))
        cv2.imshow("Coleta", tela)

        previa = np.zeros((160, 160), dtype=np.uint8)
        if ok:
            previa = cv2.resize(img, (160, 160), interpolation=cv2.INTER_NEAREST)
        cv2.imshow("Simbolo (32x32 ampliado)", previa)

        k = cv2.waitKey(80 if rajada > 0 else 1)
        if k == -1:
            continue
        k &= 0xFF
        if k == 27:
            break
        ch = chr(k).lower() if k < 128 else ""

        if ch == " ":
            if atual:
                rajada = TAM_RAJADA
                lote = []
        elif ch == "x":
            for p in lote:
                p.unlink(missing_ok=True)
            if lote_classe:
                contagem[lote_classe] = contagem.get(lote_classe, 0) - len(lote)
            lote = []
            rajada = 0
        elif ch in teclas:
            atual = teclas[ch]
            rajada = 0
            if atual not in contagem:
                contagem[atual] = contar_imagens(raiz / atual)

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()

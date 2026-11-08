#!/usr/bin/env python3
"""Coleta de amostras usando a câmera do Raspberry via picamera2.

Uso:  python3 coleta_picamera2.py valores   (grava o recorte do NÚMERO)
      python3 coleta_picamera2.py naipes    (grava o recorte do NAIPE)

Teclas (modo valores): a 2 3 4 5 6 7 8 9, 0 = "10", j q k
Teclas (modo naipes):  c = Copas, o = Ouros, e = Espadas, p = Paus
  ESPAÇO = grava uma rajada de amostras da classe escolhida
  x      = desfaz a última rajada
  ESC    = sai

Precisa estar na MESMA pasta que o coleta.py: o pré-processamento do símbolo
(extrair_simbolo), os ROIs e as teclas vêm de lá, para existir uma única cópia.

Instalação (Raspberry Pi OS):
  sudo apt install python3-picamera2 python3-opencv
Se usar venv, crie com:  python3 -m venv --system-site-packages venv
"""

import sys
import time
from pathlib import Path

import cv2
import numpy as np
from picamera2 import Picamera2

from coleta import (
    ROI_NAIPE,
    ROI_NUMERO,
    TAM_RAJADA,
    TECLAS_NAIPES,
    TECLAS_VALORES,
    contar_imagens,
    extrair_simbolo,
    novo_caminho,
    orientar,
)


def iniciar_camera():
    if not Picamera2.global_camera_info():
        print(
            "O libcamera não detectou nenhuma câmera. Teste antes com "
            "'rpicam-hello' (ou 'libcamera-hello') e confira o cabo flat."
        )
        return None
    picam2 = Picamera2()
    # Em picamera2, o formato "RGB888" entrega o array na ordem B,G,R, que é a
    # ordem que o OpenCV espera. (O formato "BGR888" entregaria R,G,B.)
    config = picam2.create_video_configuration(
        main={"size": (640, 480), "format": "RGB888"}
    )
    picam2.configure(config)
    picam2.start()
    time.sleep(1.0)  # deixa exposição e balanço de branco estabilizarem
    return picam2


def main():
    if len(sys.argv) < 2 or sys.argv[1] not in ("valores", "naipes"):
        print("Uso: python3 coleta_picamera2.py valores|naipes")
        sys.exit(1)
    modo_valores = sys.argv[1] == "valores"
    roi = ROI_NUMERO if modo_valores else ROI_NAIPE
    teclas = TECLAS_VALORES if modo_valores else TECLAS_NAIPES
    raiz = Path("dataset") / sys.argv[1]

    picam2 = iniciar_camera()
    if picam2 is None:
        sys.exit(1)
    print("Câmera pronta. Escolha a classe pelas teclas (ESC sai).")

    atual = ""
    contagem = {}
    lote, lote_classe = [], ""
    rajada = 0

    try:
        while True:
            bruto = picam2.capture_array("main")
            frame = orientar(bruto)

            x, y, w, h = roi
            if x + w > frame.shape[1] or y + h > frame.shape[0]:
                print(
                    f"ROI fora do frame ({frame.shape[1]}x{frame.shape[0]}). "
                    "Ajuste os ROIs no coleta.py."
                )
                break

            resultado = extrair_simbolo(frame[y : y + h, x : x + w])
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
                cv2.putText(
                    tela,
                    t,
                    (8, 22 + 22 * linha),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.55,
                    cor,
                    2,
                )

            if atual:
                texto(
                    f"Classe: {atual} ({contagem.get(atual, 0)} imgs)", 0, (255, 255, 0)
                )
            else:
                texto("Escolha a classe (teclas)", 0, (255, 255, 0))
            if ok:
                texto(
                    "Simbolo OK - " + ("vermelho" if vermelho else "preto"),
                    1,
                    (0, 255, 0),
                )
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
    finally:
        picam2.stop()
        picam2.close()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()

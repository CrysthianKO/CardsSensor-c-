#!/usr/bin/env python3
"""Treino dos modelos a partir do dataset (imagens 32x32 em PNG).

Uso:  python3 treino.py [pasta_dataset]      (padrão: ./dataset)

Estrutura esperada:
  dataset/valores/<A,2,...,10,J,Q,K>/N.png
  dataset/naipes/<Copas,Ouros,Espadas,Paus>/N.png

Gera na pasta atual (formato XML do OpenCV, lido direto pelo main.cpp):
  modelo_valores.xml
  modelo_naipes_vermelhos.xml   (Copas x Ouros)
  modelo_naipes_pretos.xml      (Espadas x Paus)

Requisitos: pip install opencv-python numpy
Rode no PC (não no Pi): o trainAuto testa vários parâmetros e é pesado.
"""
import sys
from pathlib import Path

import cv2
import numpy as np

# ------------------------------------------------ Config (igual ao simbolo.hpp)
LADO = 32
N_AUMENTOS = 6  # variações geradas por imagem de treino
MIN_POR_CLASSE = 10
FRACAO_VALIDACAO = 0.2

NOMES_VALORES = ["A", "2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K"]
NOMES_NAIPES_VERMELHOS = ["Copas", "Ouros"]
NOMES_NAIPES_PRETOS = ["Espadas", "Paus"]

# Os parâmetros do HOG TÊM que ser idênticos aos do simbolo.hpp:
# janela 32x32, bloco 16x16, passo 8x8, célula 8x8, 9 bins -> 324 valores.
HOG = cv2.HOGDescriptor((LADO, LADO), (16, 16), (8, 8), (8, 8), 9)


def calcular_hog(img):
    return HOG.compute(img).reshape(-1).astype(np.float32)


# ------------------------------------------------------------------- Dados
def carregar(pasta, classes):
    """Retorna lista de (imagem, rotulo)."""
    amostras = []
    for rotulo, nome in enumerate(classes):
        n = 0
        diretorio = Path(pasta) / nome
        if diretorio.is_dir():
            for arquivo in sorted(diretorio.glob("*.png")):
                img = cv2.imread(str(arquivo), cv2.IMREAD_GRAYSCALE)
                if img is None or img.shape != (LADO, LADO):
                    continue
                amostras.append((img, rotulo))
                n += 1
        print(f"  {nome}: {n} imagens")
    return amostras


def aumentar(img, rng):
    """Pequenas variações de rotação/escala/posição (a carta nunca entra
    exatamente no mesmo lugar)."""
    ang = rng.uniform(-6.0, 6.0)
    esc = rng.uniform(0.9, 1.1)
    dx, dy = rng.uniform(-2.0, 2.0, size=2)
    M = cv2.getRotationMatrix2D((LADO / 2, LADO / 2), ang, esc)
    M[0, 2] += dx
    M[1, 2] += dy
    return cv2.warpAffine(
        img, M, (LADO, LADO),
        flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=0,
    )


def montar(amostras, n_aug, rng):
    X, y = [], []
    for img, rotulo in amostras:
        X.append(calcular_hog(img))
        y.append(rotulo)
        for _ in range(n_aug):
            X.append(calcular_hog(aumentar(img, rng)))
            y.append(rotulo)
    return np.array(X, dtype=np.float32), np.array(y, dtype=np.int32)


def dividir(amostras, frac_val, rng):
    """Divisão estratificada por classe."""
    por_classe = {}
    for i, (_, rotulo) in enumerate(amostras):
        por_classe.setdefault(rotulo, []).append(i)
    treino, val = [], []
    for idx in por_classe.values():
        idx = list(rng.permutation(idx))
        n_val = max(1, int(len(idx) * frac_val))
        val += [amostras[i] for i in idx[:n_val]]
        treino += [amostras[i] for i in idx[n_val:]]
    return treino, val


# --------------------------------------------------------------------- SVM
def novo_svm():
    svm = cv2.ml.SVM_create()
    svm.setType(cv2.ml.SVM_C_SVC)
    svm.setKernel(cv2.ml.SVM_RBF)
    svm.setTermCriteria(
        (cv2.TERM_CRITERIA_MAX_ITER + cv2.TERM_CRITERIA_EPS, 2000, 1e-6)
    )
    return svm


def avaliar(svm, val, classes):
    X, y = montar(val, 0, None)  # sem aumento na validação
    _, pred = svm.predict(X)
    pred = pred.reshape(-1).astype(int)
    acertos = int((pred == y).sum())
    print(f"  Validação: {acertos}/{len(y)} ({100.0 * acertos / max(1, len(y)):.1f}%)")
    erros = {}
    for esperado, lido in zip(y, pred):
        if esperado != lido:
            erros[(esperado, lido)] = erros.get((esperado, lido), 0) + 1
    for (esperado, lido), n in sorted(erros.items()):
        nome_lido = classes[lido] if 0 <= lido < len(classes) else "?"
        print(f"    {classes[esperado]} lido como {nome_lido}: {n}x")


def treinar_grupo(titulo, pasta, classes, saida):
    print(f"== {titulo} ==")
    todas = carregar(pasta, classes)

    contagem = [0] * len(classes)
    for _, rotulo in todas:
        contagem[rotulo] += 1
    for nome, n in zip(classes, contagem):
        if n < MIN_POR_CLASSE:
            print(f"  ERRO: '{nome}' tem só {n} imagens (mínimo {MIN_POR_CLASSE}).")
            return False

    rng = np.random.default_rng(12345)
    treino, val = dividir(todas, FRACAO_VALIDACAO, rng)

    # 1) treina só com ~80%, escolhendo C e gamma por validação cruzada
    X, y = montar(treino, N_AUMENTOS, rng)
    svm = novo_svm()
    print(f"  Treinando ({len(X)} vetores)... pode demorar alguns minutos")
    svm.trainAuto(X, cv2.ml.ROW_SAMPLE, y, 5)
    print(f"  C={svm.getC():.4g} gamma={svm.getGamma():.4g}")
    avaliar(svm, val, classes)

    # 2) retreina com TODAS as amostras usando os mesmos parâmetros
    Xt, yt = montar(todas, N_AUMENTOS, rng)
    final = novo_svm()
    final.setC(svm.getC())
    final.setGamma(svm.getGamma())
    final.train(Xt, cv2.ml.ROW_SAMPLE, yt)
    final.save(saida)
    print(f"  Salvo em {saida} ({final.getSupportVectors().shape[0]} vetores de suporte)\n")
    return True


def main():
    raiz = sys.argv[1] if len(sys.argv) > 1 else "dataset"
    ok = True
    ok &= treinar_grupo("Valores", f"{raiz}/valores", NOMES_VALORES, "modelo_valores.xml")
    ok &= treinar_grupo("Naipes vermelhos", f"{raiz}/naipes", NOMES_NAIPES_VERMELHOS,
                        "modelo_naipes_vermelhos.xml")
    ok &= treinar_grupo("Naipes pretos", f"{raiz}/naipes", NOMES_NAIPES_PRETOS,
                        "modelo_naipes_pretos.xml")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()

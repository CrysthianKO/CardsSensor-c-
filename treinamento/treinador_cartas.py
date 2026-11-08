import cv2
import numpy as np
import os
import random

# Estrutura de pastas para salvar as fotos reais
DATASET_DIR = "dataset_real"
CATEGORIAS = {
    "valores": ["A", "2", "3", "4", "5", "6", "7", "8", "9", "0", "J", "Q", "K"],
    "vermelhos": ["Copas", "Ouros"],
    "pretos": ["Espadas", "Paus"],
}


def preparar_pastas():
    for grupo, simbolos in CATEGORIAS.items():
        for simb in simbolos:
            os.makedirs(f"{DATASET_DIR}/{grupo}/{simb}", exist_ok=True)


# Aplica EXATAMENTE o mesmo tratamento de imagem que o seu C++ usará na leitura
def processar_imagem_para_treino(recorte_bruto):
    cinza = cv2.cvtColor(recorte_bruto, cv2.COLOR_BGR2GRAY)
    _, binaria = cv2.threshold(cinza, 0, 255, cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU)

    # Encontra a tinta (Bounding Box)
    contornos, _ = cv2.findContours(binaria, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contornos:
        return None

    maior_area = 0
    caixa_tinta = None
    for c in contornos:
        area = cv2.contourArea(c)
        if area > maior_area:
            maior_area = area
            caixa_tinta = cv2.boundingRect(c)

    if maior_area < 20:
        return None

    # Recorta e centraliza
    apenas_tinta = binaria[
        caixa_tinta[1] : caixa_tinta[1] + caixa_tinta[3],
        caixa_tinta[0] : caixa_tinta[0] + caixa_tinta[2],
    ]

    maior_lado = max(apenas_tinta.shape)
    img_quadrada = np.zeros((maior_lado, maior_lado), dtype=np.uint8)

    x_off = (maior_lado - apenas_tinta.shape[1]) // 2
    y_off = (maior_lado - apenas_tinta.shape[0]) // 2
    img_quadrada[
        y_off : y_off + apenas_tinta.shape[0], x_off : x_off + apenas_tinta.shape[1]
    ] = apenas_tinta

    return cv2.resize(img_quadrada, (20, 20))


def modo_captura(grupo):
    simbolos = CATEGORIAS[grupo]
    print(f"\n--- Coletando {grupo.upper()} ---")
    print("Opções:", ", ".join(simbolos))
    alvo = input("Qual símbolo você vai colocar na câmera agora? (ou 'sair'): ").strip()

    if alvo.lower() == "sair" or alvo not in simbolos:
        return

    cap = cv2.VideoCapture(0, cv2.CAP_V4L2)
    # Lembre-se de ajustar este Rect para bater com a posição física do seu gabinete
    ROI = (150, 100, 60, 80)

    print(f"\n[INSTRUÇÕES] Coloque o {alvo} na máquina.")
    print(
        "Pressione 'C' várias vezes para capturar fotos (mova a carta milímetros para os lados para gerar variações reais)."
    )
    print("Pressione 'Q' para voltar ao menu.")

    contador = 0
    pasta_destino = f"{DATASET_DIR}/{grupo}/{alvo}"

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        # Simula a mesma rotação/espelhamento que você configurou no C++
        frame = cv2.rotate(frame, cv2.ROTATE_90_COUNTERCLOCKWISE)
        frame = cv2.flip(frame, 1)

        x, y, w, h = ROI
        recorte = frame[y : y + h, x : x + w]

        processada = processar_imagem_para_treino(recorte)

        # Interface Visual
        cv2.rectangle(frame, (x, y), (x + w, y + h), (255, 0, 0), 2)
        cv2.putText(
            frame,
            f"Capturas: {contador}",
            (10, 30),
            cv2.FONT_HERSHEY_SIMPLEX,
            1,
            (0, 255, 0),
            2,
        )
        cv2.imshow("Captura", frame)

        if processada is not None:
            # Raio-X ampliado
            cv2.imshow(
                "Raio-X (Treino)",
                cv2.resize(processada, (200, 200), interpolation=cv2.INTER_NEAREST),
            )

        tecla = cv2.waitKey(1) & 0xFF
        if tecla == ord("c") and processada is not None:
            caminho_arquivo = f"{pasta_destino}/{contador}.png"
            cv2.imwrite(caminho_arquivo, processada)
            contador += 1
            print(f"[{contador}] Imagem salva em {caminho_arquivo}")
        elif tecla == ord("q"):
            break

    cap.release()
    cv2.destroyAllWindows()


def treinar_modelo_svm(grupo, nome_arquivo_xml):
    print(f"\nTreinando {nome_arquivo_xml}...")
    dados, labels = [], []
    simbolos = CATEGORIAS[grupo]

    for idx, simb in enumerate(simbolos):
        pasta = f"{DATASET_DIR}/{grupo}/{simb}"
        arquivos = [f for f in os.listdir(pasta) if f.endswith(".png")]

        for arquivo in arquivos:
            img = cv2.imread(f"{pasta}/{arquivo}", cv2.IMREAD_GRAYSCALE)

            # Adiciona dados sintéticos extras a partir da sua foto real (Data Augmentation)
            for _ in range(5):
                angulo = random.uniform(-10, 10)
                escala = random.uniform(0.9, 1.1)
                matriz_rot = cv2.getRotationMatrix2D((10, 10), angulo, escala)
                img_distorcida = cv2.warpAffine(img, matriz_rot, (20, 20))
                _, binaria = cv2.threshold(img_distorcida, 128, 255, cv2.THRESH_BINARY)

                dados.append(binaria.flatten())
                labels.append(idx)

    if not dados:
        print(f"Sem dados suficientes para {grupo}.")
        return

    matriz_dados = np.array(dados, dtype=np.float32)
    matriz_labels = np.array(labels, dtype=np.int32)

    svm = cv2.ml.SVM_create()
    svm.setType(cv2.ml.SVM_C_SVC)
    svm.setKernel(cv2.ml.SVM_LINEAR)
    svm.train(matriz_dados, cv2.ml.ROW_SAMPLE, matriz_labels)
    svm.save(nome_arquivo_xml)
    print(f"Sucesso! {nome_arquivo_xml} gerado. (Classes: {simbolos})")


preparar_pastas()
while True:
    print("\n=== ESTÚDIO DE TREINAMENTO ===")
    print("1. Coletar Valores (A, 2-9, 0, J, Q, K)")
    print("2. Coletar Naipes Vermelhos (Copas, Ouros)")
    print("3. Coletar Naipes Pretos (Espadas, Paus)")
    print("4. Treinar os 3 Modelos XML")
    print("5. Sair")

    escolha = input("Escolha uma opção: ")
    if escolha == "1":
        modo_captura("valores")
    elif escolha == "2":
        modo_captura("vermelhos")
    elif escolha == "3":
        modo_captura("pretos")
    elif escolha == "4":
        treinar_modelo_svm("valores", "modelo_valores.xml")
        treinar_modelo_svm("vermelhos", "modelo_naipes_vermelhos.xml")
        treinar_modelo_svm("pretos", "modelo_naipes_pretos.xml")
    elif escolha == "5":
        break

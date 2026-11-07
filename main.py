import cv2
import os


# 1. Carregar os templates na memória (roda apenas uma vez na inicialização)
def load_templates(folder_path):
    templates = {}
    for filename in os.listdir(folder_path):
        if filename.endswith(".png"):
            nome_molde = filename.split(".")[0]
            caminho = os.path.join(folder_path, filename)
            # Carrega em tons de cinza
            img_template = cv2.imread(caminho, cv2.IMREAD_GRAYSCALE)
            # Aplica binarização (tudo que for escuro vira preto, o resto branco)
            _, template_binario = cv2.threshold(
                img_template, 128, 255, cv2.THRESH_BINARY_INV
            )
            templates[nome_molde] = template_binario
    return templates


# Dicionário em memória com todas as referências
templates_salvos = load_templates("templates/")

# Configuração da câmera e área de interesse (ajuste estes valores empíricamente)
# ROI = (X_inicial, Y_inicial, Largura, Altura)
ROI_CARTA = (100, 50, 60, 120)

cap = cv2.VideoCapture(0)  # Inicializa a câmera


def identificar_simbolo(imagem_cortada, templates):
    melhor_match = None
    maior_valor = -1

    # Prepara o recorte da câmera da mesma forma que os templates
    gray = cv2.cvtColor(imagem_cortada, cv2.COLOR_BGR2GRAY)
    _, img_binaria = cv2.threshold(gray, 128, 255, cv2.THRESH_BINARY_INV)

    # Compara a câmera com cada template salvo
    for nome, template_img in templates.items():
        # TM_CCOEFF_NORMED retorna um valor de -1.0 a 1.0 (onde 1.0 é 100% igual)
        resultado = cv2.matchTemplate(img_binaria, template_img, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, _ = cv2.minMaxLoc(resultado)

        if max_val > maior_valor:
            maior_valor = max_val
            melhor_match = nome

    # Define uma taxa de confiança mínima (ex: 70% de similaridade)
    if maior_valor > 0.7:
        return melhor_match, maior_valor
    return "Desconhecido", 0


while True:
    ret, frame = cap.read()
    if not ret:
        break

    # 2. Cortar apenas a região onde os símbolos aparecem (ROI)
    x, y, w, h = ROI_CARTA
    recorte = frame[y : y + h, x : x + w]

    # 3. Identificar o que tem no recorte
    simbolo, confianca = identificar_simbolo(recorte, templates_salvos)

    # Exibe o resultado na tela (Remover em produção para economizar processamento)
    cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)
    cv2.putText(
        frame,
        f"{simbolo} ({confianca:.2f})",
        (x, y - 10),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.6,
        (0, 255, 0),
        2,
    )

    cv2.imshow("Scanner de Cartas", frame)
    cv2.imshow("Recorte Binarizado", recorte)

    if cv2.waitKey(1) & 0xFF == ord("q"):
        break

cap.release()
cv2.destroyAllWindows()

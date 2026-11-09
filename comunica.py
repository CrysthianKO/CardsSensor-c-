import subprocess
import threading


def ler_eventos_do_scanner(processo):
    # Fica lendo o que o scanner joga na saída padrão (stdout)
    for linha in processo.stdout:
        evento = linha.decode("utf-8").strip()
        print(f"[App Principal] Recebido do Scanner: {evento}")

        # Aqui você reage ao que o scanner mandou:
        if evento.startswith("CARTA;"):
            _, valor, naipe = evento.split(";")
            print(f"!!! O jogador colocou um {valor} de {naipe} na mesa !!!")
        elif evento == "CARTA_REMOVIDA":
            print("Carta retirada. Aguardando a próxima...")


# 1. Inicia o scanner como um processo filho
scanner = subprocess.Popen(
    ["python3", "scanner_integrado.py"],
    stdin=subprocess.PIPE,
    stdout=subprocess.PIPE,
    stderr=sys.stderr,  # Deixa os logs de erro aparecerem no terminal
)

# 2. Inicia uma thread para ler as cartas sem travar a sua aplicação
thread_leitura = threading.Thread(
    target=ler_eventos_do_scanner, args=(scanner,), daemon=True
)
thread_leitura.start()

# 3. Mandando comandos para ligar e desligar a câmera quando quiser:
print("Ligando o scanner...")
scanner.stdin.write(b"LIGAR\n")
scanner.stdin.flush()

# (Faça sua lógica principal / simulação aqui...)

# Quando quiser parar de usar:
# scanner.stdin.write(b"DESLIGAR\n")
# scanner.stdin.flush()

# Para fechar o scanner ao encerrar seu programa:
# scanner.stdin.write(b"SAIR\n")
# scanner.stdin.flush()
# scanner.wait()

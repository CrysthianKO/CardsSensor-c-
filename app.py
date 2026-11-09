import subprocess
import threading
import sys
import time


def ler_eventos_do_scanner(processo):
    """Lê a saída do scanner em tempo real sem travar o programa principal."""
    for linha in processo.stdout:
        evento = linha.decode("utf-8").strip()

        # Ignora linhas vazias
        if not evento:
            continue

        print(f"\n[Scanner] {evento}")

        # Lógica do seu jogo/aplicação com base no evento
        if evento.startswith("CARTA;"):
            partes = evento.split(";")
            if len(partes) == 3:
                valor = partes[1]
                naipe = partes[2]
                print(
                    f">>> AÇÃO DO JOGO: Jogador colocou a carta {valor} de {naipe} na mesa!"
                )

        elif evento == "CARTA_REMOVIDA":
            print(">>> AÇÃO DO JOGO: A mesa está livre novamente.")


def main():
    print("Iniciando o sistema principal...")

    # 1. Inicia o scanner como um subprocesso
    # O stderr=sys.stderr garante que os logs de erro do OpenCV apareçam no seu terminal
    scanner = subprocess.Popen(
        [sys.executable, "scanner_integrado.py"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=sys.stderr,
    )

    # 2. Inicia a thread que vai escutar as cartas
    thread_leitura = threading.Thread(
        target=ler_eventos_do_scanner, args=(scanner,), daemon=True
    )
    thread_leitura.start()

    # Dá um tempo breve para o scanner carregar os modelos XML
    time.sleep(2)

    # 3. Manda o comando para ligar a câmera e os LEDs
    print("Enviando comando para LIGAR a câmera...")
    scanner.stdin.write(b"LIGAR\n")
    scanner.stdin.flush()

    # Loop principal da sua aplicação (simulando um jogo rodando)
    try:
        print("Jogo rodando. Pressione Ctrl+C para sair.")
        while True:
            # Aqui rodaria a lógica do seu jogo (Pygame, renderização, regras, etc.)
            time.sleep(1)

    except KeyboardInterrupt:
        print("\nEncerrando a aplicação...")
    finally:
        # Garante que o scanner seja desligado corretamente ao fechar o jogo
        print("Desligando o scanner...")
        if scanner.poll() is None:  # Se o processo ainda estiver vivo
            scanner.stdin.write(b"SAIR\n")
            scanner.stdin.flush()
            scanner.wait(timeout=5)
        print("Sistema encerrado.")


if __name__ == "__main__":
    main()

import socket
import threading
import subprocess
import sys
import json
import time

# Dicionários para traduzir do formato do Scanner para o formato do App Flet
MAPA_VALORES = {"10": "T", "A": "A", "J": "J", "Q": "Q", "K": "K"}
MAPA_NAIPES = {"Copas": "h", "Ouros": "d", "Espadas": "s", "Paus": "c"}

clientes_conectados = []
cartas_na_mao = 0
cartas_na_mesa = 0


def traduzir_carta(valor, naipe):
    """Converte '10' e 'Ouros' para 'Td'"""
    v = MAPA_VALORES.get(valor, valor)  # Se for 2..9, mantém igual
    n = MAPA_NAIPES.get(naipe, "")
    return f"{v}{n}"


def enviar_para_celulares(pacote_dict):
    """Gera o JSON e envia via socket para todos os celulares conectados"""
    pacote_str = json.dumps(pacote_dict) + "\n"
    for conn in clientes_conectados:
        try:
            conn.sendall(pacote_str.encode("utf-8"))
        except Exception as e:
            pass


def gerenciar_leitura_scanner(processo_scanner):
    global cartas_na_mao, cartas_na_mesa
    for linha in processo_scanner.stdout:
        evento = linha.decode("utf-8").strip()
        if not evento:
            continue

        print(f"[Scanner] {evento}")

        if evento.startswith("CARTA;"):
            _, valor, naipe = evento.split(";")
            carta_traduzida = traduzir_carta(valor, naipe)

            # Regra de distribuição (Dealer automático)
            if cartas_na_mao < 2:
                enviar_para_celulares({"tipo": "carta_mao", "carta": carta_traduzida})
                cartas_na_mao += 1
                print(f"-> Enviada para a MÃO do jogador: {carta_traduzida}")

            elif cartas_na_mesa < 5:
                enviar_para_celulares({"tipo": "carta_mesa", "carta": carta_traduzida})
                cartas_na_mesa += 1
                print(f"-> Enviada para a MESA: {carta_traduzida}")

            else:
                print("-> Mesa cheia! Reiniciando a rodada...")
                enviar_para_celulares({"tipo": "nova_rodada"})
                enviar_para_celulares({
                    "tipo": "estado_mesa",
                    "msg": "Nova rodada iniciada!",
                })
                cartas_na_mao = 0
                cartas_na_mesa = 0


def iniciar_servidor_sockets():
    HOST = "0.0.0.0"  # Aceita conexão de qualquer IP na rede local
    PORT = 5000

    servidor = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    servidor.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    servidor.bind((HOST, PORT))
    servidor.listen()

    print(f"\n[Rede] Servidor Poker aguardando celulares na porta {PORT}...")
    print("[Rede] Descubra o IP deste computador e digite no aplicativo Flet.\n")

    while True:
        conn, addr = servidor.accept()
        print(f"[Rede] Celular conectado: {addr}")
        clientes_conectados.append(conn)

        try:
            # Recebe pacote de registro inicial do Flet {"tipo": "registro"...}
            dados = conn.recv(1024).decode("utf-8")
            if dados:
                jogador = json.loads(dados.strip())
                print(
                    f"[Rede] Jogador registrado: {jogador.get('nome')} com R${jogador.get('saldo')}"
                )

                # Manda boas vindas
                enviar_para_celulares({
                    "tipo": "estado_mesa",
                    "pote": 0,
                    "seu_saldo": jogador.get("saldo"),
                    "msg": "Passe as cartas no scanner físico...",
                })
        except Exception as e:
            print(f"[Rede] Erro no handshake: {e}")


def main():
    # 1. Inicia a rede em uma thread separada para não travar o programa
    threading.Thread(target=iniciar_servidor_sockets, daemon=True).start()

    # 2. Inicia o scanner físico
    scanner = subprocess.Popen(
        [sys.executable, "scanner_integrado.py"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=sys.stderr,
    )

    # 3. Escuta as cartas do scanner
    threading.Thread(
        target=gerenciar_leitura_scanner, args=(scanner,), daemon=True
    ).start()

    # Dá tempo para o OpenCV carregar e liga a câmera
    time.sleep(2)
    scanner.stdin.write(b"LIGAR\n")
    scanner.stdin.flush()

    # Mantém o sistema rodando
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nEncerrando sistema...")
        scanner.stdin.write(b"SAIR\n")
        scanner.stdin.flush()


if __name__ == "__main__":
    main()

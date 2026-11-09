#!/usr/bin/env python3
"""Exemplo simples de como um programa Python controla o scanner em C++.

Uso:  python3 controle.py [caminho_do_executavel] [pasta_dos_modelos]
      (padrão: ./main; os modelo_*.xml são lidos da pasta do executável,
       a menos que você informe outra pasta)

O Python inicia o executável e conversa com ele por texto, uma linha por vez:
  Python -> C++ (stdin):  LIGAR | DESLIGAR | SAIR
  C++ -> Python (stdout): PRONTO | CAMERA_LIGADA | CAMERA_DESLIGADA
                          CARTA;<valor>;<naipe> | CARTA_REMOVIDA | ERRO;<msg>

Cada carta lida é salva em cartas.csv (data_hora, valor, naipe).
A classe Scanner pode ser importada por outro programa (ex.: seu servidor):
    from controle import Scanner
    s = Scanner("./main"); s.esperar_pronto(); s.ligar() ...
"""

import csv
import subprocess
import sys
import threading
import time
from datetime import datetime
from pathlib import Path


class Scanner:
    def __init__(self, executavel="./main", arquivo="cartas.csv", pasta_modelos=None):
        self.arquivo = Path(arquivo).resolve()
        self.ultima_carta = None  # (valor, naipe) da carta que está na máquina
        self._pronto = threading.Event()

        exe = Path(executavel).resolve()
        if not exe.is_file():
            raise SystemExit(
                f"Executável não encontrado: {exe}\n"
                "Compile o main.cpp e passe o caminho do programa gerado, "
                "ex.: python3 controle.py ./build/main"
            )
        # O C++ lê os modelo_*.xml da pasta de trabalho. Por padrão é a pasta do
        # executável; se os .xml estiverem em outro lugar, passe pasta_modelos.
        cwd = Path(pasta_modelos).resolve() if pasta_modelos else exe.parent
        self.proc = subprocess.Popen(
            [str(exe)],
            cwd=str(cwd),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            text=True,
            bufsize=1,  # uma linha por vez, sem esperar encher o buffer
        )
        # stderr não é redirecionado: os logs do C++ aparecem no seu terminal.
        threading.Thread(target=self._ler_eventos, daemon=True).start()

    # ------------------------------------------------------------ comandos
    def _enviar(self, comando):
        self.proc.stdin.write(comando + "\n")
        self.proc.stdin.flush()

    def ligar(self):
        """Liga a câmera e começa a receber as cartas."""
        self._enviar("LIGAR")

    def desligar(self):
        """Desliga a câmera (e o LED) para poupar processamento."""
        self._enviar("DESLIGAR")

    def sair(self):
        try:
            self._enviar("SAIR")
        except (BrokenPipeError, OSError):
            pass  # o C++ já tinha encerrado
        try:
            self.proc.stdin.close()
        except (BrokenPipeError, OSError):
            pass
        try:
            self.proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self.proc.kill()

    def esperar_pronto(self, timeout=15):
        """True se o C++ avisou PRONTO; False se ele morreu ou demorou demais."""
        fim = time.time() + timeout
        while time.time() < fim:
            if self._pronto.wait(0.2):
                return True
            if self.proc.poll() is not None:
                return False
        return False

    # ------------------------------------------------------------- eventos
    def _ler_eventos(self):
        for linha in self.proc.stdout:
            linha = linha.strip()
            if not linha:
                continue
            campos = linha.split(";")
            evento = campos[0]

            if evento == "CARTA" and len(campos) == 3:
                valor, naipe = campos[1], campos[2]
                self.ultima_carta = (valor, naipe)
                self._salvar(valor, naipe)
                print(f"[carta] {valor} de {naipe} (salva em {self.arquivo.name})")
            elif evento == "CARTA_REMOVIDA":
                self.ultima_carta = None
                print("[carta removida]")
            elif evento == "PRONTO":
                self._pronto.set()
                print("[scanner pronto]")
            elif evento == "ERRO":
                print(f"[erro] {';'.join(campos[1:])}")
            else:
                print(f"[{evento.lower()}]")

    def _salvar(self, valor, naipe):
        novo = not self.arquivo.exists()
        with open(self.arquivo, "a", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            if novo:
                w.writerow(["data_hora", "valor", "naipe"])
            w.writerow([datetime.now().isoformat(timespec="seconds"), valor, naipe])


def main():
    exe = sys.argv[1] if len(sys.argv) > 1 else "./main"
    pasta_modelos = sys.argv[2] if len(sys.argv) > 2 else None
    scanner = Scanner(exe, pasta_modelos=pasta_modelos)

    if not scanner.esperar_pronto():
        print("O scanner não ficou pronto (veja os erros acima).")
        scanner.sair()
        sys.exit(1)

    print("Comandos: l = ligar câmera | d = desligar câmera | q = sair")
    try:
        while True:
            cmd = input("> ").strip().lower()
            if cmd == "l":
                scanner.ligar()
            elif cmd == "d":
                scanner.desligar()
            elif cmd == "q":
                break
    except (EOFError, KeyboardInterrupt):
        pass
    finally:
        scanner.sair()


if __name__ == "__main__":
    main()

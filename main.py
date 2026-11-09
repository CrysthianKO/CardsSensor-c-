import socket
import threading
import json
import os
from itertools import combinations
import flet as ft

# --- AVALIADOR DE MÃOS NO FORMATO "As", "Td", "9h" ---
VALORES_MAP = {
    "2": 2,
    "3": 3,
    "4": 4,
    "5": 5,
    "6": 6,
    "7": 7,
    "8": 8,
    "9": 9,
    "T": 10,
    "J": 11,
    "Q": 12,
    "K": 13,
    "A": 14,
}
NAIPES_SIMBOLOS = {"s": "♠", "h": "♥", "d": "♦", "c": "♣"}
NOMES_COMBINACOES = [
    "Carta Alta",
    "Um Par",
    "Dois Pares",
    "Trinca",
    "Sequência (Straight)",
    "Flush",
    "Full House",
    "Quadra (Four of a Kind)",
    "Straight Flush",
]


def formatar_carta_visual(carta_str):
    if len(carta_str) < 2:
        return carta_str
    valor = "10" if carta_str[0].upper() == "T" else carta_str[0].upper()
    naipe = NAIPES_SIMBOLOS.get(carta_str[1].lower(), carta_str[1])
    return f"{valor}{naipe}"


def avaliar_5(cinco_cartas):
    valores = sorted([VALORES_MAP[c[0].upper()] for c in cinco_cartas], reverse=True)
    naipes = [c[1].lower() for c in cinco_cartas]
    eh_flush = len(set(naipes)) == 1
    eh_straight = (valores == list(range(valores[0], valores[0] - 5, -1))) or (
        valores == [14, 5, 4, 3, 2]
    )
    if valores == [14, 5, 4, 3, 2]:
        valores = [5, 4, 3, 2, 1]

    contagem = sorted([(valores.count(v), v) for v in set(valores)], reverse=True)
    freq = [p[0] for p in contagem]
    desempate = [p[1] for p in contagem]

    if eh_straight and eh_flush:
        return (8, desempate)
    if freq == [4, 1]:
        return (7, desempate)
    if freq == [3, 2]:
        return (6, desempate)
    if eh_flush:
        return (5, desempate)
    if eh_straight:
        return (4, desempate)
    if freq == [3, 1, 1]:
        return (3, desempate)
    if freq == [2, 2, 1]:
        return (2, desempate)
    if freq == [2, 1, 1, 1]:
        return (1, desempate)
    return (0, desempate)


def descobrir_combinacao(cartas_mao, cartas_mesa):
    todas = [
        c
        for c in (cartas_mao + cartas_mesa)
        if len(c) >= 2 and c[0].upper() in VALORES_MAP
    ]
    if not todas:
        return "Aguardando cartas..."
    if len(todas) < 5:
        valores = [VALORES_MAP[c[0].upper()] for c in todas]
        contagem = sorted([valores.count(v) for v in set(valores)], reverse=True)
        if contagem[0] == 4:
            return "Quadra"
        if contagem[0] == 3:
            return "Trinca"
        if contagem[:2] == [2, 2]:
            return "Dois Pares"
        if contagem[0] == 2:
            return "Um Par"
        return "Carta Alta"
    melhor = max(avaliar_5(comb) for comb in combinations(todas, 5))
    return NOMES_COMBINACOES[melhor[0]]


# --- APLICATIVO DO CELULAR ---
class AppPokerJogador:
    def __init__(self, page: ft.Page):
        self.page = page
        self.page.title = "Poker - Jogador"
        self.page.theme_mode = ft.ThemeMode.DARK
        self.page.padding = 15

        self.sock = None
        self.conectado = False
        self.nome = ""
        self.saldo = 0
        self.pote_mesa = 0
        self.valor_call_atual = 0
        self.cartas_mao = []
        self.cartas_mesa = []

        self.construir_tela_login()

    def construir_tela_login(self, msg_aviso=""):
        self.page.controls.clear()
        self.in_ip = ft.TextField(
            label="IP do Computador Central", value="192.168.1.10"
        )
        self.in_porta = ft.TextField(
            label="Porta", value="5000", keyboard_type=ft.KeyboardType.NUMBER
        )
        self.in_nome = ft.TextField(
            label="Seu Nome na Mesa", value=self.nome, hint_text="Ex: Vitor"
        )
        self.in_saldo = ft.TextField(
            label="Dinheiro Inicial (R$)",
            value=str(self.saldo or 500),
            keyboard_type=ft.KeyboardType.NUMBER,
        )
        self.lbl_erro = ft.Text(msg_aviso, color="red400")

        btn_entrar = ft.Button(
            content=ft.Text("Conectar à Mesa"),
            bgcolor="green700",
            color="white",
            width=280,
            height=45,
            on_click=self.conectar_servidor,
        )

        btn_sair_app = ft.Button(
            content=ft.Text("Fechar Aplicativo"),
            width=280,
            on_click=self.fechar_aplicativo,
        )

        self.page.add(
            ft.Column(
                [
                    ft.Text("Mesa de Poker", size=24, weight=ft.FontWeight.BOLD),
                    self.in_ip,
                    self.in_porta,
                    self.in_nome,
                    self.in_saldo,
                    btn_entrar,
                    btn_sair_app,
                    self.lbl_erro,
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=12,
            )
        )
        self.page.update()

    def construir_tela_jogo(self):
        self.page.controls.clear()

        self.lbl_info_jogador = ft.Text(
            f"Jogador: {self.nome}", size=18, weight=ft.FontWeight.BOLD
        )
        self.lbl_saldo = ft.Text(
            f"Saldo: R$ {self.saldo}",
            size=20,
            color="green400",
            weight=ft.FontWeight.BOLD,
        )
        self.lbl_pote = ft.Text(
            f"Pote da Mesa: R$ {self.pote_mesa}", size=18, color="amber400"
        )

        self.lbl_cartas_mao = ft.Text(
            "Sua Mão: [ ? ] [ ? ]", size=26, weight=ft.FontWeight.BOLD
        )
        self.lbl_cartas_mesa = ft.Text("Mesa: Nenhuma carta", size=20)
        self.lbl_combinacao = ft.Text(
            "Jogo Atual: Aguardando...",
            size=20,
            color="cyan300",
            weight=ft.FontWeight.BOLD,
        )
        self.lbl_status_turno = ft.Text(
            "Conectado! Aguardando cartas...", size=15, color="grey400"
        )

        # Botões de jogada
        self.btn_fold = ft.Button(
            "Fold",
            bgcolor="red700",
            color="white",
            disabled=True,
            on_click=lambda e: self.enviar_acao("FOLD", 0),
        )
        self.btn_check = ft.Button(
            "Check",
            bgcolor="blue700",
            color="white",
            disabled=True,
            on_click=lambda e: self.enviar_acao("CHECK", 0),
        )
        self.btn_call = ft.Button(
            "Call",
            bgcolor="green700",
            color="white",
            disabled=True,
            on_click=lambda e: self.enviar_acao("CALL", self.valor_call_atual),
        )

        self.in_valor_raise = ft.TextField(
            label="Valor Raise",
            value="20",
            width=130,
            disabled=True,
            keyboard_type=ft.KeyboardType.NUMBER,
        )
        self.btn_raise = ft.Button(
            "Raise",
            bgcolor="orange700",
            color="white",
            disabled=True,
            on_click=self.acao_raise,
        )

        # Botões para desconectar da partida ou fechar o app
        btn_desconectar = ft.Button(
            content=ft.Text("Desconectar da Mesa"), on_click=self.acao_desconectar
        )
        btn_sair_jogo = ft.Button(
            content=ft.Text("Sair do App"),
            bgcolor="red900",
            color="white",
            on_click=self.fechar_aplicativo,
        )

        self.page.add(
            ft.Row(
                [self.lbl_info_jogador, self.lbl_saldo],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            ),
            self.lbl_pote,
            ft.Divider(),
            self.lbl_cartas_mao,
            self.lbl_cartas_mesa,
            self.lbl_combinacao,
            ft.Divider(),
            self.lbl_status_turno,
            ft.Row(
                [self.btn_fold, self.btn_check, self.btn_call],
                alignment=ft.MainAxisAlignment.SPACE_EVENLY,
            ),
            ft.Row(
                [self.in_valor_raise, self.btn_raise],
                alignment=ft.MainAxisAlignment.CENTER,
            ),
            ft.Divider(),
            ft.Row(
                [btn_desconectar, btn_sair_jogo],
                alignment=ft.MainAxisAlignment.SPACE_EVENLY,
            ),
        )
        self.page.update()

    def conectar_servidor(self, e):
        ip = self.in_ip.value.strip()
        porta = int(self.in_porta.value.strip())
        self.nome = self.in_nome.value.strip()

        try:
            self.saldo = int(self.in_saldo.value.strip())
        except ValueError:
            self.lbl_erro.value = "Digite um valor numérico válido para o dinheiro."
            self.page.update()
            return

        if not self.nome:
            self.lbl_erro.value = "Informe seu nome antes de conectar."
            self.page.update()
            return

        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.settimeout(5)
            self.sock.connect((ip, porta))
            self.sock.settimeout(None)
            self.conectado = True
            self.cartas_mao.clear()
            self.cartas_mesa.clear()

            pacote = (
                json.dumps({"tipo": "registro", "nome": self.nome, "saldo": self.saldo})
                + "\n"
            )
            self.sock.sendall(pacote.encode("utf-8"))

            self.construir_tela_jogo()
            threading.Thread(target=self.loop_escuta, daemon=True).start()

        except Exception as erro:
            self.lbl_erro.value = f"Falha ao conectar: {erro}"
            self.page.update()

    def loop_escuta(self):
        buffer = ""
        try:
            while self.conectado:
                dados = self.sock.recv(1024).decode("utf-8")
                if not dados:
                    break
                buffer += dados
                while "\n" in buffer:
                    linha, buffer = buffer.split("\n", 1)
                    if linha.strip():
                        self.processar_pacote(json.loads(linha))
        except Exception:
            pass
        finally:
            if self.conectado:
                self.conectado = False
                self.construir_tela_login("Conexão encerrada pelo servidor.")

    def processar_pacote(self, pacote):
        tipo = pacote.get("tipo")

        if tipo == "nova_rodada":
            self.cartas_mao.clear()
            self.cartas_mesa.clear()
            self.bloquear_botoes("Cartas limpas. Nova rodada iniciada!")
            self.atualizar_visuais_cartas()

        elif tipo == "carta_mao":
            self.cartas_mao.append(pacote.get("carta"))
            self.atualizar_visuais_cartas()

        elif tipo == "carta_mesa":
            self.cartas_mesa.append(pacote.get("carta"))
            self.atualizar_visuais_cartas()

        elif tipo == "estado_mesa":
            self.pote_mesa = pacote.get("pote", self.pote_mesa)
            self.saldo = pacote.get("seu_saldo", self.saldo)
            msg = pacote.get("msg", "")
            self.lbl_pote.value = f"Pote da Mesa: R$ {self.pote_mesa}"
            self.lbl_saldo.value = f"Saldo: R$ {self.saldo}"
            if msg:
                self.lbl_status_turno.value = msg
            self.page.update()

        elif tipo == "sua_vez":
            self.valor_call_atual = pacote.get("valor_call", 0)
            min_raise = pacote.get("min_raise", 20)
            self.habilitar_turno(self.valor_call_atual, min_raise)

    def atualizar_visuais_cartas(self):
        mao_fmt = (
            "  ".join(formatar_carta_visual(c) for c in self.cartas_mao)
            or "[ ? ] [ ? ]"
        )
        mesa_fmt = (
            "  ".join(formatar_carta_visual(c) for c in self.cartas_mesa)
            or "Nenhuma carta"
        )
        self.lbl_cartas_mao.value = f"Sua Mão: {mao_fmt}"
        self.lbl_cartas_mesa.value = f"Mesa: {mesa_fmt}"
        self.lbl_combinacao.value = (
            f"Jogo Atual: {descobrir_combinacao(self.cartas_mao, self.cartas_mesa)}"
        )
        self.page.update()

    def habilitar_turno(self, valor_call, min_raise):
        self.lbl_status_turno.value = "SUA VEZ DE JOGAR!"
        self.lbl_status_turno.color = "green400"
        self.btn_fold.disabled = False

        if valor_call == 0:
            self.btn_check.disabled = False
            self.btn_call.disabled = True
            self.btn_call.content = ft.Text("Call")
        else:
            self.btn_check.disabled = True
            self.btn_call.disabled = False
            self.btn_call.content = ft.Text(f"Call ({valor_call})")

        self.in_valor_raise.value = str(min_raise)
        self.in_valor_raise.disabled = False
        self.btn_raise.disabled = False
        self.page.update()

    def bloquear_botoes(self, mensagem_status):
        self.btn_fold.disabled = True
        self.btn_check.disabled = True
        self.btn_call.disabled = True
        self.in_valor_raise.disabled = True
        self.btn_raise.disabled = True
        self.lbl_status_turno.value = mensagem_status
        self.lbl_status_turno.color = "grey400"
        self.page.update()

    def acao_raise(self, e):
        try:
            valor = int(self.in_valor_raise.value.strip())
            self.enviar_acao("RAISE", valor)
        except ValueError:
            self.lbl_status_turno.value = "Valor de Raise inválido!"
            self.page.update()

    def enviar_acao(self, tipo_acao, valor):
        if self.conectado and self.sock:
            pacote = (
                json.dumps({"tipo": "acao", "acao": tipo_acao, "valor": valor}) + "\n"
            )
            self.sock.sendall(pacote.encode("utf-8"))
            self.bloquear_botoes(f"Você enviou {tipo_acao}. Aguardando mesa...")

    def acao_desconectar(self, e):
        """Desconecta do servidor e retorna para a tela de login."""
        if self.conectado and self.sock:
            try:
                pacote = json.dumps({"tipo": "desconectar", "nome": self.nome}) + "\n"
                self.sock.sendall(pacote.encode("utf-8"))
                self.sock.close()
            except Exception:
                pass
        self.conectado = False
        self.construir_tela_login("Você desconectou da mesa.")

    def fechar_aplicativo(self, e):
        """Fecha o socket se estiver aberto e encerra o aplicativo."""
        if self.conectado and self.sock:
            try:
                self.sock.close()
            except Exception:
                pass
        self.conectado = False
        try:
            self.page.window.close()
        except Exception:
            pass
        os._exit(0)


def main(page: ft.Page):
    AppPokerJogador(page)


if __name__ == "__main__":
    ft.run(main)

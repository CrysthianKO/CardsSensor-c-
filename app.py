import socket
import threading
import json
import flet as ft


def main(page: ft.Page):
    page.title = "Poker Mesa Física"
    page.theme_mode = ft.ThemeMode.DARK
    page.padding = 16
    page.scroll = ft.ScrollMode.AUTO

    sock_cliente = None
    conectado = False

    # Conexão
    input_ip = ft.TextField(label="IP Raspberry", value="192.168.1.100", expand=True)
    input_nome = ft.TextField(label="Nome", value="Jogador 1", expand=True)
    txt_status = ft.Text("Desconectado", color=ft.Colors.RED_400, size=12)

    # Informações da mesa
    txt_fase = ft.Text("Fase: AGUARDANDO", weight=ft.FontWeight.BOLD)
    txt_saldo = ft.Text(
        "Saldo: R$ 1000", size=16, weight=ft.FontWeight.BOLD, color=ft.Colors.AMBER_300
    )
    txt_pote = ft.Text(
        "Pote: R$ 0", size=16, weight=ft.FontWeight.BOLD, color=ft.Colors.GREEN_300
    )
    txt_turno = ft.Text("Vez de: -", size=15, weight=ft.FontWeight.BOLD)
    txt_info = ft.Text("Conecte-se ao servidor para começar.", size=14)

    # Áreas de cartas
    row_mao = ft.Row(spacing=10)
    row_mesa = ft.Row(spacing=8, wrap=True)

    # Controles de aposta
    input_raise = ft.TextField(
        label="Valor Raise (R$)",
        value="50",
        width=140,
        keyboard_type=ft.KeyboardType.NUMBER,
    )

    def enviar_json(pacote: dict):
        if conectado and sock_cliente:
            try:
                sock_cliente.sendall((json.dumps(pacote) + "\n").encode("utf-8"))
            except Exception as ex:
                txt_info.value = f"Falha ao enviar comando: {ex}"
                page.update()

    def criar_carta_ui(codigo: str, cor: str):
        return ft.Container(
            content=ft.Text(codigo, size=22, weight=ft.FontWeight.BOLD),
            padding=ft.padding.symmetric(horizontal=14, vertical=10),
            bgcolor=cor,
            border_radius=8,
        )

    def atualizar_botoes(sua_vez: bool, a_pagar: float):
        btn_fold.disabled = not sua_vez
        btn_check_call.disabled = not sua_vez
        btn_raise.disabled = not sua_vez
        btn_check_call.text = (
            f"Pagar R${a_pagar:.0f}" if a_pagar > 0 else "Passar (Check)"
        )

    def processar_pacote(pacote: dict):
        tipo = pacote.get("tipo")

        if tipo == "estado_mesa":
            txt_fase.value = f"Fase: {pacote.get('fase', '-')}"
            txt_pote.value = f"Pote: R$ {pacote.get('pote', 0):.0f}"
            txt_saldo.value = f"Saldo: R$ {pacote.get('seu_saldo', 0):.0f}"
            txt_info.value = pacote.get("msg", "")

            sua_vez = pacote.get("sua_vez", False)
            a_pagar = pacote.get("a_pagar", 0.0)
            txt_turno.value = (
                "SUA VEZ DE AGIR!"
                if sua_vez
                else f"Vez de: {pacote.get('jogador_vez', '-')}"
            )
            txt_turno.color = ft.Colors.GREEN_400 if sua_vez else ft.Colors.GREY_400

            atualizar_botoes(sua_vez, a_pagar)

        elif tipo == "carta_mao":
            row_mao.controls.append(
                criar_carta_ui(pacote.get("carta", "?"), ft.Colors.BLUE_900)
            )

        elif tipo == "carta_mesa":
            row_mesa.controls.append(
                criar_carta_ui(pacote.get("carta", "?"), ft.Colors.GREEN_900)
            )

        elif tipo == "nova_rodada":
            row_mao.controls.clear()
            row_mesa.controls.clear()

        elif tipo == "erro":
            txt_info.value = f"Aviso: {pacote.get('msg', '')}"

        page.update()

    def escutar_servidor():
        nonlocal conectado
        buffer = ""
        try:
            while conectado and sock_cliente:
                dados = sock_cliente.recv(1024).decode("utf-8")
                if not dados:
                    break
                buffer += dados
                while "\n" in buffer:
                    linha, buffer = buffer.split("\n", 1)
                    if linha.strip():
                        processar_pacote(json.loads(linha))
        except Exception as e:
            txt_status.value = f"Desconectado: {e}"
            txt_status.color = ft.Colors.RED_400
            conectado = False
            page.update()

    def conectar(e):
        nonlocal sock_cliente, conectado
        if conectado:
            return
        try:
            sock_cliente = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock_cliente.connect((input_ip.value.strip(), 5000))
            conectado = True

            enviar_json({
                "tipo": "registro",
                "nome": input_nome.value.strip(),
                "saldo": 1000,
            })

            txt_status.value = "Conectado"
            txt_status.color = ft.Colors.GREEN_400
            btn_nova_rodada.disabled = False
            page.update()

            threading.Thread(target=escutar_servidor, daemon=True).start()
        except Exception as ex:
            txt_status.value = f"Erro: {ex}"
            txt_status.color = ft.Colors.RED_400
            page.update()

    def on_raise(e):
        try:
            val = float(input_raise.value)
            enviar_json({"tipo": "acao", "acao": "raise", "valor": val})
        except ValueError:
            txt_info.value = "Digite um número válido para o Raise."
            page.update()

    btn_conectar = ft.ElevatedButton("Conectar", on_click=conectar)
    btn_nova_rodada = ft.OutlinedButton(
        "Nova Rodada",
        disabled=True,
        on_click=lambda e: enviar_json({"tipo": "iniciar_rodada"}),
    )

    btn_fold = ft.ElevatedButton(
        "Correr (Fold)",
        bgcolor=ft.Colors.RED_800,
        color=ft.Colors.WHITE,
        disabled=True,
        on_click=lambda e: enviar_json({"tipo": "acao", "acao": "fold"}),
    )
    btn_check_call = ft.ElevatedButton(
        "Passar (Check)",
        bgcolor=ft.Colors.BLUE_800,
        color=ft.Colors.WHITE,
        disabled=True,
        on_click=lambda e: enviar_json({
            "tipo": "acao",
            "acao": "call" if "Pagar" in btn_check_call.text else "check",
        }),
    )
    btn_raise = ft.ElevatedButton(
        "Apostar (Raise)",
        bgcolor=ft.Colors.GREEN_800,
        color=ft.Colors.WHITE,
        disabled=True,
        on_click=on_raise,
    )

    page.add(
        ft.Row([input_ip, input_nome]),
        ft.Row(
            [btn_conectar, btn_nova_rodada, txt_status],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        ),
        ft.Divider(),
        ft.Row(
            [txt_fase, txt_pote, txt_saldo],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        ),
        txt_turno,
        ft.Container(
            content=txt_info,
            padding=10,
            bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
            border_radius=6,
        ),
        ft.Text("Suas Cartas Privadas:", weight=ft.FontWeight.BOLD),
        row_mao,
        ft.Text("Cartas Comunitárias (Mesa):", weight=ft.FontWeight.BOLD),
        row_mesa,
        ft.Divider(),
        ft.Text("Ações:", weight=ft.FontWeight.BOLD),
        ft.Row([btn_fold, btn_check_call], spacing=10),
        ft.Row([input_raise, btn_raise], spacing=10),
    )


if __name__ == "__main__":
    ft.app(target=main)

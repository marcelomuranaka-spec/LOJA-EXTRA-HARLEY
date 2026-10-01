"""Ficha do cliente (/clientes/<id>): a visão 360º."""

import reflex as rx

from ..components.botao_imprimir import botao_imprimir
from ..components.layout import page
from ..components.moto_cliente import card_moto, dialogo_moto, dialogo_ver_moto
from ..components.ui import (aviso_ativacao, campo, cartao_indicador, dialogo, entrada, mensagem_erro,
                             secao, selecao, tabela, vazio)
from ..state.cliente_detalhe_state import ClienteDetalheState as D
from ..state.clientes_state import ClientesState
from ..state.motos_state import MotosState
from .clientes import formulario_cliente


def _dado(rotulo: str, valor) -> rx.Component:
    return rx.vstack(
        rx.text(rotulo, size="1", color=rx.color("gray", 10)),
        rx.text(rx.cond(valor != "", valor, "—"), size="2", weight="medium"),
        spacing="0",
        align="start",
        flex="1 1 180px",
        min_width="0",
    )


def _cabecalho() -> rx.Component:
    c = D.cliente
    return rx.vstack(
        rx.link(rx.hstack(rx.icon("arrow-left", size=14), rx.text("Clientes", size="2"), spacing="1",
                          align="center"), href="/clientes", underline="none", color=rx.color("gray", 10)),
        rx.flex(
            rx.hstack(
                rx.heading(c["nome_cliente"], size="7"),
                rx.badge(c["status"], color_scheme=c["status_cor"].to(str), variant="soft", size="2"),
                align="center",
                spacing="3",
                flex_wrap="wrap",
            ),
            rx.spacer(),
            rx.flex(
                rx.button(rx.icon("pencil", size=14), "Editar", variant="soft",
                          on_click=ClientesState.abrir_editar(D.cliente_id_atual.to(str))),
                rx.cond(c["whatsapp_link"] != "",
                        rx.link(rx.button(rx.icon("message-circle", size=14), "WhatsApp", variant="soft",
                                          color_scheme="green"),
                                href=c["whatsapp_link"].to(str), is_external=True)),
                rx.button(rx.icon("mail", size=14), "Enviar e-mail", variant="soft", color_scheme="gray",
                          on_click=D.abrir_email),
                rx.button(rx.icon("message-square-plus", size=14), "Registrar interação",
                          on_click=D.abrir_interacao("")),
                gap="0.5rem",
                flex_wrap="wrap",
            ),
            gap="0.75rem",
            flex_wrap="wrap",
            width="100%",
            align="center",
        ),
        spacing="2",
        width="100%",
        align="start",
    )


def _dados() -> rx.Component:
    c = D.cliente
    return secao(
        "Dados do cliente",
        rx.flex(
            _dado("CPF/CNPJ", c["cpf_cnpj"]),
            _dado("Telefone", c["telefone"]),
            _dado("WhatsApp", c["whatsapp"]),
            _dado("E-mail", c["email"]),
            _dado("Endereço", c["endereco"]),
            _dado("Cidade", c["cidade"]),
            _dado("Cliente desde", c["data_cadastro"]),
            gap="0.9rem",
            flex_wrap="wrap",
            width="100%",
        ),
        rx.cond(
            c["observacoes"] != "",
            rx.vstack(
                rx.text("Observações", size="1", color=rx.color("gray", 10)),
                rx.text(c["observacoes"], size="2", white_space="pre-wrap"),
                spacing="1",
                align="start",
            ),
        ),
        icone="id-card",
    )


def _indicadores() -> rx.Component:
    return rx.grid(
        cartao_indicador("Compras", D.qtd_compras, "shopping-bag"),
        cartao_indicador("Total gasto", D.total_gasto, "wallet"),
        cartao_indicador("Última compra", D.ultima_compra, "calendar"),
        cartao_indicador("Motos", D.motos.length(), "bike"),
        columns=rx.breakpoints(initial="2", md="4"),
        spacing="3",
        width="100%",
    )


def _motos() -> rx.Component:
    return secao(
        "Motos do cliente",
        rx.cond(
            D.motos.length() > 0,
            rx.grid(rx.foreach(D.motos, lambda m: card_moto(m, True)),
                    columns=rx.breakpoints(initial="1", sm="2", lg="3"), spacing="3", width="100%"),
            vazio("Nenhuma moto cadastrada para este cliente."),
        ),
        icone="bike",
        contador=D.motos.length(),
        acao=rx.button(rx.icon("plus", size=14), "Adicionar moto", size="2",
                       on_click=MotosState.abrir_novo_para_cliente(D.cliente_id_atual)),
    )


def _compra(c: dict) -> rx.Component:
    return rx.table.row(
        rx.table.cell(rx.text("nº ", c["id"])),
        rx.table.cell(c["data"]),
        rx.table.cell(rx.text(c["itens"], size="2")),
        rx.table.cell(rx.text(c["total"], weight="medium")),
        rx.table.cell(rx.cond(c["cancelada"], rx.badge("Cancelada", color_scheme="red", variant="soft"),
                              rx.badge("Ativa", color_scheme="green", variant="soft"))),
        rx.table.cell(botao_imprimir("venda", c["id"])),
    )


def _ordem(o: dict) -> rx.Component:
    return rx.table.row(
        rx.table.cell(rx.text("nº ", o["id"])),
        rx.table.cell(o["data"]),
        rx.table.cell(o["moto"]),
        rx.table.cell(rx.badge(o["status"], variant="soft")),
        rx.table.cell(botao_imprimir("os", o["id"])),
    )


def _interacao(i: dict) -> rx.Component:
    return rx.hstack(
        rx.icon("message-circle", size=16, color=rx.color("orange", 9), flex_shrink="0", margin_top="0.2rem"),
        rx.vstack(
            rx.text(rx.text.strong(i["tipo"]), " · ", i["data"], size="2"),
            rx.text(i["descricao"], size="2", white_space="pre-wrap", color=rx.color("gray", 11)),
            spacing="0",
            align="start",
        ),
        spacing="2",
        align="start",
        width="100%",
    )


def _email(e: dict) -> rx.Component:
    return rx.table.row(
        rx.table.cell(e["data"]),
        rx.table.cell(e["assunto"]),
        rx.table.cell(e["destinatario"]),
        rx.table.cell(rx.badge(e["status"], color_scheme=rx.cond(e["status"] == "Enviado", "green", "red"),
                               variant="soft")),
        rx.table.cell(rx.text(e["erro"], size="1", color=rx.color("gray", 10))),
    )


def _icone_evento(nome) -> rx.Component:
    return rx.match(
        nome,
        *[(n, rx.icon(n, size=16, color=rx.color("orange", 9)))
          for n in ("user-plus", "shopping-cart", "wrench", "message-circle", "mail")],
        rx.icon("circle", size=16, color=rx.color("orange", 9)),
    )


def _evento(e: dict) -> rx.Component:
    return rx.hstack(
        rx.box(_icone_evento(e["icone"]), flex_shrink="0", margin_top="0.15rem"),
        rx.vstack(
            rx.text(e["data"], size="1", color=rx.color("gray", 10)),
            rx.text(e["titulo"], size="2", weight="medium"),
            rx.cond(e["texto"] != "", rx.text(e["texto"], size="2", color=rx.color("gray", 11))),
            spacing="0",
            align="start",
        ),
        spacing="3",
        align="start",
        width="100%",
        padding_bottom="0.6rem",
        border_bottom=f"1px solid {rx.color('gray', 4)}",
    )


def _abas() -> rx.Component:
    aviso_interacoes = aviso_ativacao(
        "Interações aguardando o Xano",
        "O registro de interações e orçamentos está pronto e funciona assim que a tabela "
        "interacoes for criada no Xano.")
    return rx.tabs.root(
        rx.tabs.list(
            rx.tabs.trigger("Linha do tempo", value="tempo"),
            rx.tabs.trigger(rx.text("Compras (", D.compras.length(), ")"), value="compras"),
            rx.tabs.trigger(rx.text("Ordens de serviço (", D.ordens.length(), ")"), value="os"),
            rx.tabs.trigger(rx.text("Orçamentos (", D.orcamentos.length(), ")"), value="orcamentos"),
            rx.tabs.trigger(rx.text("Interações (", D.interacoes.length(), ")"), value="interacoes"),
            rx.tabs.trigger(rx.text("E-mails (", D.emails.length(), ")"), value="emails"),
            overflow_x="auto",
        ),
        rx.tabs.content(
            rx.cond(D.linha_do_tempo.length() > 0,
                    rx.vstack(rx.foreach(D.linha_do_tempo, _evento), spacing="2", width="100%"),
                    vazio("Nada registrado ainda.")),
            value="tempo", padding_top="1rem",
        ),
        rx.tabs.content(
            rx.cond(D.compras.length() > 0,
                    tabela(["Venda", "Data", "Itens", "Total", "Situação", ""], rx.foreach(D.compras, _compra)),
                    vazio("Nenhuma compra registrada para este cliente.")),
            rx.link(rx.button(rx.icon("shopping-cart", size=14), "Nova venda para este cliente", variant="soft",
                              margin_top="0.75rem"), href="/vendas", underline="none"),
            value="compras", padding_top="1rem",
        ),
        rx.tabs.content(
            rx.cond(D.ordens.length() > 0,
                    tabela(["OS", "Abertura", "Moto", "Situação", ""], rx.foreach(D.ordens, _ordem)),
                    vazio("Nenhuma ordem de serviço para as motos deste cliente.")),
            value="os", padding_top="1rem",
        ),
        rx.tabs.content(
            rx.cond(
                D.tem_interacoes,
                rx.vstack(
                    rx.button(rx.icon("file-plus", size=14), "Registrar orçamento enviado", variant="soft",
                              on_click=D.abrir_interacao("Orçamento enviado")),
                    rx.cond(D.orcamentos.length() > 0,
                            rx.vstack(rx.foreach(D.orcamentos, _interacao), spacing="3", width="100%"),
                            vazio("Nenhum orçamento registrado.")),
                    spacing="3", width="100%",
                ),
                aviso_interacoes,
            ),
            value="orcamentos", padding_top="1rem",
        ),
        rx.tabs.content(
            rx.cond(
                D.tem_interacoes,
                rx.cond(D.interacoes.length() > 0,
                        rx.vstack(rx.foreach(D.interacoes, _interacao), spacing="3", width="100%"),
                        vazio("Nenhuma interação registrada.")),
                aviso_interacoes,
            ),
            value="interacoes", padding_top="1rem",
        ),
        rx.tabs.content(
            rx.cond(
                D.tem_emails,
                rx.cond(D.emails.length() > 0,
                        tabela(["Data", "Assunto", "Para", "Situação", "Erro"], rx.foreach(D.emails, _email)),
                        vazio("Nenhum e-mail enviado para este cliente.")),
                aviso_ativacao("Histórico de e-mails aguardando o Xano",
                               "O histórico aparece aqui quando a tabela emails for criada no Xano."),
            ),
            value="emails", padding_top="1rem",
        ),
        default_value="tempo",
        width="100%",
    )


def _dialogo_interacao() -> rx.Component:
    return dialogo(
        D.dialogo_interacao,
        D.fechar_interacao,
        "Registrar interação",
        campo("Tipo", selecao(D.tipos_interacao, D.int_tipo, D.set_int_tipo)),
        campo("O que aconteceu", rx.text_area(value=D.int_descricao, on_change=D.set_int_descricao,
                                              width="100%", rows="4",
                                              placeholder="Ex.: cliente pediu orçamento de revisão dos 10.000 km")),
        mensagem_erro(D.erro_int),
        rx.hstack(
            rx.button("Cancelar", variant="soft", color_scheme="gray", on_click=D.fechar_interacao),
            rx.button(rx.icon("check", size=16), "Salvar", on_click=D.salvar_interacao),
            spacing="3", justify="end", width="100%",
        ),
        largura="520px",
    )


def _dialogo_email() -> rx.Component:
    return dialogo(
        D.dialogo_email,
        D.fechar_email,
        "Enviar e-mail",
        rx.text("Para: ", rx.text.strong(D.cliente["email"]), size="2"),
        rx.cond(~D.sendgrid_ok,
                rx.callout("O SendGrid ainda não está configurado: a tentativa fica registrada, mas o e-mail "
                           "não é enviado (ver Configuração do sistema).", icon="triangle-alert",
                           color_scheme="orange", size="1", width="100%")),
        campo("Assunto", entrada(D.email_assunto, D.set_email_assunto)),
        campo("Mensagem", rx.text_area(value=D.email_mensagem, on_change=D.set_email_mensagem, width="100%",
                                       rows="8")),
        mensagem_erro(D.erro_email),
        rx.hstack(
            rx.button("Cancelar", variant="soft", color_scheme="gray", on_click=D.fechar_email),
            rx.button(rx.icon("send", size=16), "Enviar", on_click=D.enviar_email),
            spacing="3", justify="end", width="100%",
        ),
        largura="560px",
    )


def cliente_detalhe_page() -> rx.Component:
    return page(
        rx.cond(
            D.encontrado,
            rx.vstack(
                _cabecalho(),
                _indicadores(),
                _dados(),
                _motos(),
                secao("Histórico", _abas(), icone="history"),
                spacing="4",
                width="100%",
            ),
            rx.vstack(
                vazio("Cliente não encontrado."),
                rx.link("Voltar para a lista de clientes", href="/clientes"),
                width="100%",
            ),
        ),
        formulario_cliente(),
        dialogo_moto(),
        dialogo_ver_moto(),
        _dialogo_interacao(),
        _dialogo_email(),
        title="Ficha do cliente",
    )

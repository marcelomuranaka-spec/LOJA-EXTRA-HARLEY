"""
Janelas de moto do cliente (cadastrar/editar e visualizar), usadas pela
página /motos e pela ficha do cliente. Estado: `MotosState`.
"""

import reflex as rx

from ..state.motos_state import MotosState
from .foto import campo_foto, miniatura, src_foto
from .ui import campo, dialogo, entrada, linha, mensagem_erro, selecao


def dialogo_moto() -> rx.Component:
    extras = rx.cond(
        MotosState.tem_extras,
        rx.vstack(
            linha(
                campo("Marca", entrada(MotosState.marca, MotosState.set_marca, "Ex.: Harley-Davidson")),
                campo("Ano", entrada(MotosState.ano, MotosState.set_ano, "Ex.: 2021"),
                      largura_min="110px"),
                campo("Cor", entrada(MotosState.cor, MotosState.set_cor), largura_min="140px"),
            ),
            linha(
                campo("Quilometragem", entrada(MotosState.quilometragem, MotosState.set_quilometragem,
                                               "Ex.: 12500")),
            ),
            campo("Observações", rx.text_area(value=MotosState.observacoes, on_change=MotosState.set_observacoes,
                                              width="100%", rows="3")),
            spacing="3",
            width="100%",
        ),
        rx.callout("Marca, ano, cor, km e observações aparecem aqui depois que os campos forem criados "
                   "no Xano (ver Configuração do sistema).", icon="plug-zap", color_scheme="orange",
                   size="1", width="100%"),
    )
    return dialogo(
        MotosState.dialogo_aberto,
        MotosState.fechar_dialogo,
        rx.cond(MotosState.form_id, "Editar moto do cliente", "Nova moto do cliente"),
        rx.cond(
            MotosState.cliente_travado,
            rx.hstack(rx.icon("user", size=16), rx.text("Cliente: ", rx.text.strong(MotosState.cliente_selecionado.split(" - ")[1])),
                      align="center", spacing="2"),
            campo("Cliente (dono da moto) *", selecao(MotosState.clientes_opcoes, MotosState.cliente_selecionado,
                                                      MotosState.set_cliente_selecionado, "Escolha o cliente")),
        ),
        linha(
            campo("Modelo *", entrada(MotosState.modelo, MotosState.set_modelo, "Ex.: Fat Boy 114")),
            campo("Placa *", entrada(MotosState.placa, MotosState.set_placa, "ABC1D23"), largura_min="140px"),
        ),
        campo("Chassi *", entrada(MotosState.chassi, MotosState.set_chassi)),
        extras,
        campo_foto("Foto da moto", "upload_imagem_moto", MotosState.imagem_url, MotosState.imagem_local,
                   MotosState.handle_upload_imagem, MotosState.remover_imagem, MotosState.erro_imagem, "bike"),
        mensagem_erro(MotosState.erro_form),
        rx.hstack(
            rx.button("Cancelar", variant="soft", color_scheme="gray", on_click=MotosState.fechar_dialogo),
            rx.button(rx.icon("check", size=16), "Salvar", on_click=MotosState.salvar),
            spacing="3",
            justify="end",
            width="100%",
        ),
    )


def _dado(rotulo: str, valor) -> rx.Component:
    return rx.vstack(
        rx.text(rotulo, size="1", color=rx.color("gray", 10)),
        rx.text(rx.cond(valor != "", valor, "—"), size="2", weight="medium"),
        spacing="0",
        align="start",
        min_width="120px",
        flex="1 1 120px",
    )


def dialogo_ver_moto() -> rx.Component:
    m = MotosState.moto_vista
    return dialogo(
        MotosState.dialogo_ver,
        MotosState.fechar_ver,
        rx.cond(m["titulo"] != "", m["titulo"], "Moto do cliente"),
        rx.cond(
            (m["foto_url"] != "") | (m["foto_local"] != ""),
            rx.image(src=src_foto(m["foto_url"].to(str), m["foto_local"].to(str)), width="100%",
                     max_height="320px", object_fit="cover", border_radius="0.6rem"),
        ),
        rx.flex(
            _dado("Cliente", m["cliente_nome"]),
            _dado("Placa", m["placa"]),
            _dado("Chassi", m["chassi"]),
            _dado("Marca", m["marca"]),
            _dado("Modelo", m["modelo"]),
            _dado("Ano", m["ano"]),
            _dado("Cor", m["cor"]),
            _dado("Quilometragem", m["quilometragem"]),
            _dado("Cadastrada em", m["data_cadastro"]),
            gap="0.75rem",
            flex_wrap="wrap",
            width="100%",
        ),
        rx.cond(m["observacoes"] != "", rx.text(m["observacoes"], size="2", white_space="pre-wrap")),
        rx.hstack(
            rx.link(rx.button(rx.icon("user", size=14), "Abrir ficha do cliente", variant="soft"),
                    href="/clientes/" + m["id_cliente"].to(str), underline="none"),
            rx.button(rx.icon("pencil", size=14), "Editar", on_click=[MotosState.fechar_ver,
                                                                       MotosState.abrir_editar(m["id"].to(str))]),
            spacing="3",
            justify="end",
            width="100%",
            flex_wrap="wrap",
        ),
        largura="560px",
    )


def card_moto(m: dict, na_ficha: bool = False) -> rx.Component:
    """Card com foto, usado na ficha do cliente."""
    return rx.card(
        rx.hstack(
            miniatura(m["foto_url"], m["foto_local"], "84px", "84px", "bike"),
            rx.vstack(
                rx.text("🏍 ", m["titulo"], weight="bold"),
                rx.text(m["placa"], " · ", rx.cond(m["ano"] != "", m["ano"], "ano —"), size="2",
                        color=rx.color("gray", 10)),
                rx.hstack(
                    rx.button(rx.icon("eye", size=14), "Ver", size="1", variant="soft", color_scheme="gray",
                              on_click=MotosState.visualizar(m["id"])),
                    rx.button(rx.icon("pencil", size=14), "Editar", size="1", variant="soft",
                              on_click=MotosState.abrir_editar(m["id"], na_ficha)),
                    spacing="2",
                    flex_wrap="wrap",
                ),
                spacing="1",
                align="start",
                min_width="0",
            ),
            spacing="3",
            align="center",
        ),
        width="100%",
    )

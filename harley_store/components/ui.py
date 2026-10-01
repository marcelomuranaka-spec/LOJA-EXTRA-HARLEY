"""
Peças visuais reaproveitadas pelas telas: campos com rótulo, linhas de
formulário que quebram no celular, seções, tabelas com rolagem lateral,
paginação, janelas (diálogos) e avisos.

Regra de responsividade: em vez de `rx.hstack` com larguras fixas (que
estoura a tela do celular), os formulários usam `linha(...)`, que coloca os
campos lado a lado no computador e um embaixo do outro em telas estreitas.
"""

from __future__ import annotations

from typing import Any

import reflex as rx

from .tema import BORDA, LARANJA, LARANJA_SUAVE, PRETO_CARTAO


def campo(rotulo: str, componente: rx.Component, ajuda: str = "", largura_min: str = "200px") -> rx.Component:
    filhos = [rx.text(rotulo, size="2", weight="medium", color=rx.color("gray", 11)), componente]
    if ajuda:
        filhos.append(rx.text(ajuda, size="1", color=rx.color("gray", 9)))
    return rx.vstack(*filhos, spacing="1", align="start", flex=f"1 1 {largura_min}", min_width="0", width="100%")


def linha(*filhos: rx.Component, **props) -> rx.Component:
    return rx.flex(*filhos, gap="0.75rem", flex_wrap="wrap", width="100%", align="end", **props)


def entrada(valor: rx.Var, ao_mudar: Any, placeholder: str = "", tipo: str = "text", **props) -> rx.Component:
    return rx.input(value=valor, on_change=ao_mudar, placeholder=placeholder, type=tipo, width="100%", **props)


def selecao(opcoes: rx.Var | list, valor: rx.Var, ao_mudar: Any, placeholder: str = "Selecione...", **props) -> rx.Component:
    return rx.select(opcoes, value=valor, on_change=ao_mudar, placeholder=placeholder, width="100%", **props)


def secao(titulo: str, *filhos: rx.Component, icone: str = "", acao: rx.Component | None = None,
          contador: rx.Var | None = None) -> rx.Component:
    cabecalho = [
        rx.icon(icone, size=18, color=LARANJA) if icone else rx.fragment(),
        rx.heading(titulo, size="4"),
    ]
    if contador is not None:
        cabecalho.append(rx.badge(contador, variant="soft", color_scheme="gray"))
    cabecalho.append(rx.spacer())
    if acao is not None:
        cabecalho.append(acao)
    return rx.card(
        rx.vstack(
            rx.hstack(*cabecalho, align="center", spacing="2", width="100%", flex_wrap="wrap"),
            *filhos,
            spacing="3",
            align="start",
            width="100%",
        ),
        width="100%",
    )


def tabela(cabecalhos: list, corpo: rx.Component) -> rx.Component:
    """`cabecalhos`: textos, ou componentes prontos (ex.: coluna condicional
    `rx.cond(tem_x, rx.table.column_header_cell("X"))`)."""
    return rx.box(
        rx.table.root(
            rx.table.header(rx.table.row(*[
                rx.table.column_header_cell(c) if isinstance(c, str) else c for c in cabecalhos
            ])),
            rx.table.body(corpo),
            width="100%",
            variant="surface",
            size="2",
        ),
        width="100%",
        overflow_x="auto",
    )


def vazio(texto: str) -> rx.Component:
    return rx.center(
        rx.text(texto, color=rx.color("gray", 10), size="2"),
        padding="1.5rem",
        width="100%",
        border=f"1px dashed {BORDA}",
        border_radius="0.5rem",
    )


def paginacao(pagina: rx.Var, total_paginas: rx.Var, total: rx.Var, anterior: Any, proxima: Any) -> rx.Component:
    return rx.hstack(
        rx.text(total, " registro(s)", size="2", color=rx.color("gray", 10)),
        rx.spacer(),
        rx.button(rx.icon("chevron-left", size=14), "Anterior", size="1", variant="soft",
                  color_scheme="gray", on_click=anterior, disabled=pagina <= 1),
        rx.text("Página ", pagina, " de ", total_paginas, size="2"),
        rx.button("Próxima", rx.icon("chevron-right", size=14), size="1", variant="soft",
                  color_scheme="gray", on_click=proxima, disabled=pagina >= total_paginas),
        align="center",
        spacing="2",
        width="100%",
        flex_wrap="wrap",
    )


def dialogo(aberto: rx.Var, ao_fechar: Any, titulo: rx.Var | str, *conteudo: rx.Component,
            largura: str = "640px") -> rx.Component:
    """Janela modal, fechada pelo X ou pelos botões do conteúdo. Clicar fora não
    fecha, de propósito: não perde um formulário preenchido por engano."""
    return rx.dialog.root(
        rx.dialog.content(
            rx.hstack(
                rx.dialog.title(titulo, margin="0"),
                rx.spacer(),
                rx.icon_button(rx.icon("x", size=16), variant="ghost", color_scheme="gray", on_click=ao_fechar),
                align="center",
                width="100%",
                padding_bottom="0.5rem",
            ),
            rx.vstack(*conteudo, spacing="3", align="start", width="100%"),
            max_width=largura,
            width="95vw",
            max_height="90vh",
            overflow_y="auto",
        ),
        open=aberto,
    )


def mensagem_erro(texto: rx.Var) -> rx.Component:
    return rx.cond(
        texto != "",
        rx.callout(texto, icon="triangle-alert", color_scheme="red", size="1", width="100%"),
    )


def aviso_ativacao(titulo: str, texto: str) -> rx.Component:
    """Recurso pronto no app, que depende de tabela/campo novo no Xano."""
    return rx.callout.root(
        rx.callout.icon(rx.icon("plug-zap", size=18)),
        rx.vstack(
            rx.text(titulo, weight="bold", size="2"),
            rx.text(texto, size="2"),
            rx.link("Ver o passo a passo em Configuração do sistema", href="/configuracao", size="2"),
            spacing="1",
            align="start",
        ),
        color_scheme="orange",
        variant="surface",
        width="100%",
    )


def cartao_indicador(titulo: str, valor: rx.Var | str, icone: str, detalhe: rx.Var | str = "",
                     href: str = "", cor: str = LARANJA) -> rx.Component:
    corpo = rx.card(
        rx.hstack(
            rx.center(rx.icon(icone, size=22, color=cor), background=LARANJA_SUAVE,
                      border_radius="0.6rem", width="44px", height="44px", flex_shrink="0"),
            rx.vstack(
                rx.text(titulo, size="2", color=rx.color("gray", 10)),
                # componente (ex.: rx.text) não pode ir dentro de outro <p>
                rx.box(valor, font_size="1.5rem", font_weight="700", line_height="1.2")
                if isinstance(valor, rx.Component) else rx.text(valor, size="6", weight="bold"),
                rx.text(detalhe, size="1", color=rx.color("gray", 10)) if (not isinstance(detalhe, str) or detalhe)
                else rx.fragment(),
                spacing="0",
                align="start",
                min_width="0",
            ),
            spacing="3",
            align="center",
        ),
        width="100%",
        background=PRETO_CARTAO,
        _hover={"border_color": cor} if href else {},
    )
    return rx.link(corpo, href=href, underline="none", width="100%") if href else corpo


def foto(url: rx.Var, altura: str = "120px", icone: str = "image") -> rx.Component:
    return rx.cond(
        url != "",
        rx.image(src=url, width="100%", height=altura, object_fit="cover", border_radius="0.5rem"),
        rx.center(rx.icon(icone, size=28, color=rx.color("gray", 8)), width="100%", height=altura,
                  background=rx.color("gray", 3), border_radius="0.5rem"),
    )

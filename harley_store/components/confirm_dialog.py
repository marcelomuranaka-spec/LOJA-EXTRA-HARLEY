"""
Botões com confirmação (rx.alert_dialog).

`confirm_delete_button` é usado em todas as telas de cadastro no lugar de um
botão de exclusão direto, para evitar apagar um registro sem querer com um
clique único. `confirmar_acao` faz o mesmo para qualquer outra ação que
mereça confirmação (mudar perfil, cancelar, converter...).
"""

from typing import Any

import reflex as rx


def confirmar_acao(
    gatilho: rx.Component,
    titulo: str,
    texto: Any,
    ao_confirmar: Any,
    rotulo_confirmar: str = "Confirmar",
    cor: str = "orange",
) -> rx.Component:
    return rx.alert_dialog.root(
        rx.alert_dialog.trigger(gatilho),
        rx.alert_dialog.content(
            rx.alert_dialog.title(titulo),
            rx.alert_dialog.description(texto),
            rx.hstack(
                rx.alert_dialog.cancel(
                    rx.button("Voltar", variant="soft", color_scheme="gray"),
                ),
                rx.alert_dialog.action(
                    rx.button(rotulo_confirmar, color_scheme=cor, on_click=ao_confirmar),
                ),
                spacing="3",
                justify="end",
                width="100%",
                padding_top="0.5rem",
            ),
        ),
    )


def confirm_delete_button(on_confirm: Any, item_label: str = "este registro") -> rx.Component:
    return confirmar_acao(
        rx.button(
            rx.icon("trash-2", size=14),
            "Excluir",
            size="1",
            variant="soft",
            color_scheme="red",
        ),
        titulo="Confirmar exclusão",
        texto=f"Tem certeza que deseja excluir {item_label}? Essa ação não pode ser desfeita.",
        ao_confirmar=on_confirm,
        rotulo_confirmar="Excluir",
        cor="red",
    )

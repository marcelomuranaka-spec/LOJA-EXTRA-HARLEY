"""
Fotos nas telas: miniatura (cards, tabelas, detalhes) e campo de envio
(cadastro/edição). Uma foto pode estar no Xano (URL) ou na pasta local do
servidor (nome do arquivo) — ver `imagens.py`; os states entregam as duas
partes (`*_url` e `*_local`) e aqui se monta o endereço certo.
"""

from __future__ import annotations

from typing import Any

import reflex as rx

ACEITOS = {"image/png": [".png"], "image/jpeg": [".jpg", ".jpeg"], "image/webp": [".webp"]}


def src_foto(url: rx.Var, local: rx.Var) -> rx.Var:
    return rx.cond(url != "", url, rx.cond(local != "", rx.get_upload_url(local), ""))


def miniatura(url: rx.Var, local: rx.Var, largura: str = "56px", altura: str = "56px",
              icone: str = "image") -> rx.Component:
    return rx.cond(
        (url != "") | (local != ""),
        rx.image(src=src_foto(url, local), width=largura, height=altura, object_fit="cover",
                 border_radius="0.5rem", flex_shrink="0"),
        rx.center(rx.icon(icone, size=22, color=rx.color("gray", 8)), width=largura, height=altura,
                  background=rx.color("gray", 3), border_radius="0.5rem", flex_shrink="0"),
    )


def campo_foto(rotulo: str, upload_id: str, url: rx.Var, local: rx.Var, ao_enviar: Any,
               ao_remover: Any, erro: rx.Var, icone: str = "image") -> rx.Component:
    return rx.vstack(
        rx.text(rotulo, size="2", weight="medium", color=rx.color("gray", 11)),
        rx.hstack(
            miniatura(url, local, "96px", "96px", icone),
            rx.vstack(
                rx.upload(
                    rx.hstack(rx.icon("upload", size=16), rx.text("Escolher ou trocar foto", size="2"),
                              spacing="2", align="center"),
                    id=upload_id,
                    accept=ACEITOS,
                    max_files=1,
                    multiple=False,
                    on_drop=ao_enviar(rx.upload_files(upload_id=upload_id)),
                    border=f"1px dashed {rx.color('gray', 7)}",
                    border_radius="0.5rem",
                    padding="0.6rem 0.9rem",
                    cursor="pointer",
                ),
                rx.text("PNG, JPG ou WEBP, até 5 MB.", size="1", color=rx.color("gray", 9)),
                rx.cond(
                    (url != "") | (local != ""),
                    rx.button("Remover foto", size="1", variant="ghost", color_scheme="gray", on_click=ao_remover),
                ),
                spacing="1",
                align="start",
            ),
            spacing="4",
            align="center",
            flex_wrap="wrap",
        ),
        rx.cond(erro != "", rx.text(erro, color="red", size="2")),
        spacing="2",
        align="start",
        width="100%",
    )

import reflex as rx

from ..components.confirm_dialog import confirm_delete_button
from ..components.layout import page
from ..state.produtos_state import ProdutosState


def _miniatura(row: dict) -> rx.Component:
    return rx.cond(
        row["imagem"] != "",
        rx.image(
            src=rx.get_upload_url(row["imagem"]),
            width="42px",
            height="42px",
            border_radius="0.4rem",
            object_fit="cover",
        ),
        rx.box(
            rx.icon("image", size=18, color=rx.color("gray", 8)),
            width="42px",
            height="42px",
            border_radius="0.4rem",
            background=rx.color("gray", 3),
            display="flex",
            align_items="center",
            justify_content="center",
        ),
    )


def _linha(row: dict) -> rx.Component:
    return rx.table.row(
        rx.table.cell(_miniatura(row)),
        rx.table.cell(row["nome_produto"]),
        rx.table.cell(row["categoria"]),
        rx.table.cell(
            rx.cond(
                row["estoque_baixo"],
                rx.badge(row["estoque_qtd"], color_scheme="red", variant="soft"),
                rx.text(row["estoque_qtd"]),
            )
        ),
        rx.table.cell(rx.text("R$ ", row["preco_venda"])),
        rx.table.cell(
            rx.hstack(
                rx.button(
                    rx.icon("pencil", size=14),
                    "Editar",
                    size="1",
                    variant="soft",
                    on_click=ProdutosState.editar(row),
                ),
                confirm_delete_button(
                    ProdutosState.excluir(row["id"]),
                    item_label=f"o produto “{row['nome_produto']}”",
                ),
                spacing="2",
            )
        ),
    )


def _campo_imagem() -> rx.Component:
    return rx.vstack(
        rx.text("Foto do produto (opcional)", size="2", weight="bold"),
        rx.hstack(
            rx.cond(
                ProdutosState.imagem != "",
                rx.image(
                    src=rx.get_upload_url(ProdutosState.imagem),
                    width="90px",
                    height="90px",
                    border_radius="0.6rem",
                    object_fit="cover",
                ),
                rx.box(
                    rx.icon("image", size=28, color=rx.color("gray", 8)),
                    width="90px",
                    height="90px",
                    border_radius="0.6rem",
                    background=rx.color("gray", 3),
                    display="flex",
                    align_items="center",
                    justify_content="center",
                ),
            ),
            rx.vstack(
                rx.upload(
                    rx.hstack(
                        rx.icon("upload", size=16),
                        rx.text("Selecionar foto"),
                        spacing="2",
                        align="center",
                    ),
                    id="upload_imagem_produto",
                    accept={
                        "image/png": [".png"],
                        "image/jpeg": [".jpg", ".jpeg"],
                        "image/webp": [".webp"],
                        "image/gif": [".gif"],
                    },
                    max_files=1,
                    multiple=False,
                    on_drop=ProdutosState.handle_upload_imagem(
                        rx.upload_files(upload_id="upload_imagem_produto")
                    ),
                    border=f"1px dashed {rx.color('gray', 7)}",
                    border_radius="0.5rem",
                    padding="0.6rem 0.9rem",
                    cursor="pointer",
                ),
                rx.cond(
                    ProdutosState.imagem != "",
                    rx.button(
                        "Remover foto",
                        size="1",
                        variant="ghost",
                        color_scheme="gray",
                        on_click=ProdutosState.remover_imagem,
                    ),
                ),
                spacing="2",
                align="start",
            ),
            spacing="4",
            align="center",
        ),
        rx.cond(
            ProdutosState.erro_imagem != "",
            rx.text(ProdutosState.erro_imagem, color="red", size="2"),
        ),
        spacing="2",
        align="start",
        width="100%",
    )


def _formulario() -> rx.Component:
    return rx.card(
        rx.vstack(
            rx.heading(rx.cond(ProdutosState.form_id, "Editar produto", "Novo produto"), size="4"),
            rx.hstack(
                rx.input(
                    placeholder="Nome do produto",
                    value=ProdutosState.nome_produto,
                    on_change=ProdutosState.set_nome_produto,
                    width="100%",
                ),
                rx.input(
                    placeholder="Categoria (ex.: Peças, Acessórios, Vestuário)",
                    value=ProdutosState.categoria,
                    on_change=ProdutosState.set_categoria,
                    width="100%",
                ),
                spacing="3",
                width="100%",
            ),
            rx.input(
                placeholder="Descrição (opcional)",
                value=ProdutosState.descricao,
                on_change=ProdutosState.set_descricao,
                width="100%",
            ),
            rx.hstack(
                rx.input(
                    placeholder="Estoque",
                    type="number",
                    value=ProdutosState.estoque_qtd,
                    on_change=ProdutosState.set_estoque_qtd,
                    width="150px",
                ),
                rx.input(
                    placeholder="Preço de venda",
                    type="number",
                    value=ProdutosState.preco_venda,
                    on_change=ProdutosState.set_preco_venda,
                    width="180px",
                ),
                spacing="3",
            ),
            _campo_imagem(),
            rx.hstack(
                rx.button(rx.icon("check", size=16), "Salvar", on_click=ProdutosState.salvar),
                rx.button(
                    rx.icon("x", size=16),
                    "Cancelar",
                    variant="soft",
                    color_scheme="gray",
                    on_click=ProdutosState.novo,
                ),
                spacing="3",
            ),
            spacing="3",
            align="start",
            width="100%",
        ),
        width="100%",
    )


def produtos_page() -> rx.Component:
    return page(
        _formulario(),
        rx.hstack(
            rx.input(
                placeholder="Buscar por nome...",
                value=ProdutosState.busca,
                on_change=ProdutosState.definir_busca,
                max_width="320px",
            ),
            rx.hstack(
                rx.switch(
                    checked=ProdutosState.somente_estoque_baixo,
                    on_change=ProdutosState.alternar_filtro_estoque_baixo,
                ),
                rx.text("Só estoque baixo"),
                spacing="2",
                align="center",
            ),
            spacing="5",
            align="center",
        ),
        rx.table.root(
            rx.table.header(
                rx.table.row(
                    rx.table.column_header_cell("Foto"),
                    rx.table.column_header_cell("Produto"),
                    rx.table.column_header_cell("Categoria"),
                    rx.table.column_header_cell("Estoque"),
                    rx.table.column_header_cell("Preço"),
                    rx.table.column_header_cell("Ações"),
                )
            ),
            rx.table.body(rx.foreach(ProdutosState.produtos, _linha)),
            width="100%",
            variant="surface",
        ),
        title="Produtos",
        subtitle="Catálogo e estoque de peças, acessórios e itens vendidos na loja.",
    )

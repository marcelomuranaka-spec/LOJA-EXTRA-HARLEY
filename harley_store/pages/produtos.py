import reflex as rx

from ..components.confirm_dialog import confirm_delete_button
from ..components.formulario import campo, lista_vazia, mensagem_erro
from ..components.layout import page
from ..state.produtos_state import ProdutosState


def _miniatura(row: dict) -> rx.Component:
    return rx.cond(
        row["imagem"] != "",
        rx.image(
            src=row["imagem_url"],
            alt=row["nome_produto"],
            loading="lazy",
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
                rx.button(
                    rx.icon("history", size=14),
                    "Histórico",
                    size="1",
                    variant="soft",
                    color_scheme="gray",
                    on_click=ProdutosState.abrir_historico(row["id"], row["nome_produto"]),
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
                    src=ProdutosState.imagem_url,
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
                        rx.cond(ProdutosState.enviando_imagem, rx.spinner(size="2"), rx.icon("upload", size=16)),
                        rx.text(rx.cond(ProdutosState.enviando_imagem, "Enviando...", "Selecionar foto")),
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
            rx.flex(
                campo(
                    "Nome do produto",
                    rx.input(
                        placeholder="Ex.: Óleo Screamin' Eagle 20W50",
                        value=ProdutosState.nome_produto,
                        on_change=ProdutosState.set_nome_produto,
                        max_length=120,
                        width="100%",
                    ),
                    obrigatorio=True,
                ),
                campo(
                    "Categoria",
                    rx.input(
                        placeholder="Escolha ou digite uma nova",
                        value=ProdutosState.categoria,
                        on_change=ProdutosState.set_categoria,
                        custom_attrs={"list": "lista-categorias"},
                        max_length=60,
                        width="100%",
                    ),
                    rx.el.datalist(
                        rx.foreach(ProdutosState.categorias, lambda c: rx.el.option(value=c)),
                        id="lista-categorias",
                    ),
                    obrigatorio=True,
                ),
                gap="3",
                width="100%",
                flex_direction=["column", "column", "row"],
            ),
            campo(
                "Descrição",
                rx.input(
                    placeholder="Opcional",
                    value=ProdutosState.descricao,
                    on_change=ProdutosState.set_descricao,
                    width="100%",
                ),
            ),
            rx.flex(
                campo(
                    "Estoque (unidades)",
                    rx.input(
                        type="number",
                        min=0,
                        step=1,
                        value=ProdutosState.estoque_qtd,
                        on_change=ProdutosState.set_estoque_qtd,
                        width="100%",
                    ),
                    obrigatorio=True,
                    largura=["100%", "100%", "180px"],
                ),
                campo(
                    "Preço de venda (R$)",
                    rx.input(
                        placeholder="0,00",
                        input_mode="decimal",
                        value=ProdutosState.preco_venda,
                        on_change=ProdutosState.set_preco_venda,
                        width="100%",
                    ),
                    obrigatorio=True,
                    largura=["100%", "100%", "200px"],
                ),
                gap="3",
                width="100%",
                flex_direction=["column", "row"],
            ),
            _campo_imagem(),
            mensagem_erro(ProdutosState.erro_form),
            rx.hstack(
                rx.button(rx.icon("check", size=16), "Salvar", on_click=ProdutosState.salvar, disabled=ProdutosState.enviando_imagem),
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
        id="form-produto",
        width="100%",
    )


def _linha_historico(m: dict) -> rx.Component:
    return rx.table.row(
        rx.table.cell(m["data"]),
        rx.table.cell(m["origem"]),
        rx.table.cell(m["referencia"]),
        rx.table.cell(rx.text(m["quantidade"], color=rx.cond(m["entrada"], "#4ade80", "#ff6b6b"), weight="bold")),
        rx.table.cell(m["saldo"]),
        rx.table.cell(m["usuario"]),
    )


def _dialogo_historico() -> rx.Component:
    return rx.dialog.root(
        rx.dialog.content(
            rx.dialog.title(rx.text("Histórico de estoque — ", ProdutosState.historico_produto)),
            rx.cond(
                ProdutosState.historico_aviso != "",
                rx.callout(ProdutosState.historico_aviso, icon="info", size="1"),
            ),
            rx.box(
                rx.table.root(
                    rx.table.header(rx.table.row(
                        *[rx.table.column_header_cell(t) for t in ("Data", "Origem", "Documento", "Qtd.", "Saldo", "Usuário")]
                    )),
                    rx.table.body(rx.foreach(ProdutosState.historico, _linha_historico)),
                    width="100%",
                    size="1",
                ),
                max_height="60vh",
                overflow_y="auto",
                overflow_x="auto",
                width="100%",
            ),
            rx.flex(
                rx.dialog.close(rx.button("Fechar", variant="soft", color_scheme="gray")),
                justify="end",
                padding_top="0.75rem",
            ),
            max_width="min(860px, 95vw)",
        ),
        open=ProdutosState.historico_produto != "",
        on_open_change=ProdutosState.fechar_historico,
    )


def produtos_page() -> rx.Component:
    return page(
        _formulario(),
        rx.flex(
            rx.input(
                rx.input.slot(rx.icon("search", size=16)),
                placeholder="Buscar por nome ou descrição...",
                value=ProdutosState.busca,
                on_change=ProdutosState.definir_busca,
                width=["100%", "100%", "320px"],
            ),
            rx.select(
                ProdutosState.filtros_categoria,
                value=ProdutosState.filtro_categoria,
                on_change=ProdutosState.definir_filtro_categoria,
                aria_label="Filtrar por categoria",
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
            gap="4",
            align="center",
            wrap="wrap",
            width="100%",
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
        lista_vazia(ProdutosState.produtos, "Nenhum produto encontrado com esses filtros."),
        _dialogo_historico(),
        title="Produtos",
        subtitle="Catálogo e estoque de peças, acessórios e itens vendidos na loja.",
    )

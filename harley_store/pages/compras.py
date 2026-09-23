import reflex as rx

from ..components.confirm_dialog import confirm_delete_button
from ..components.layout import page
from ..state.compras_state import ComprasState


def _linha_item_atual(item: dict, indice: int) -> rx.Component:
    return rx.table.row(
        rx.table.cell(item["produto_nome"]),
        rx.table.cell(item["quantidade"]),
        rx.table.cell(rx.text("R$ ", item["valor_unitario"])),
        rx.table.cell(rx.text("R$ ", item["subtotal"])),
        rx.table.cell(
            rx.button(
                "Remover",
                size="1",
                variant="soft",
                color_scheme="red",
                on_click=ComprasState.remover_item(indice),
            )
        ),
    )


def _linha_historico(row: dict) -> rx.Component:
    return rx.table.row(
        rx.table.cell(row["data_entrada"]),
        rx.table.cell(row["fornecedor_nome"]),
        rx.table.cell(row["qtd_itens"]),
        rx.table.cell(rx.text("R$ ", row["valor_total"])),
        rx.table.cell(
            confirm_delete_button(
                ComprasState.excluir_entrada(row["id"]),
                item_label="esta compra e todos os seus itens",
            )
        ),
    )


def _formulario() -> rx.Component:
    return rx.card(
        rx.vstack(
            rx.heading("Nova compra (entrada de mercadoria)", size="4"),
            rx.cond(
                ComprasState.fornecedores_opcoes.length() == 0,
                rx.callout("Cadastre um fornecedor primeiro.", icon="triangle_alert", color_scheme="amber"),
                rx.select(
                    ComprasState.fornecedores_opcoes,
                    placeholder="Fornecedor",
                    value=ComprasState.fornecedor_selecionado,
                    on_change=ComprasState.set_fornecedor_selecionado,
                    width="100%",
                ),
            ),
            rx.divider(),
            rx.text("Adicionar item à compra", size="2", weight="bold"),
            rx.hstack(
                rx.select(
                    ComprasState.produtos_opcoes,
                    placeholder="Produto",
                    value=ComprasState.item_produto_selecionado,
                    on_change=ComprasState.set_item_produto_selecionado,
                    flex="1",
                ),
                rx.input(
                    placeholder="Qtd.",
                    type="number",
                    value=ComprasState.item_quantidade,
                    on_change=ComprasState.set_item_quantidade,
                    width="110px",
                    flex_shrink="0",
                ),
                rx.input(
                    placeholder="Valor unit. (R$)",
                    type="number",
                    value=ComprasState.item_valor_unitario,
                    on_change=ComprasState.set_item_valor_unitario,
                    width="160px",
                    flex_shrink="0",
                ),
                rx.button(
                    "Adicionar item",
                    variant="soft",
                    on_click=ComprasState.adicionar_item,
                    flex_shrink="0",
                ),
                spacing="3",
                width="100%",
            ),
            rx.cond(
                ComprasState.itens_atual.length() > 0,
                rx.vstack(
                    rx.table.root(
                        rx.table.header(
                            rx.table.row(
                                rx.table.column_header_cell("Produto"),
                                rx.table.column_header_cell("Qtd."),
                                rx.table.column_header_cell("Valor unit."),
                                rx.table.column_header_cell("Subtotal"),
                                rx.table.column_header_cell(""),
                            )
                        ),
                        rx.table.body(rx.foreach(ComprasState.itens_atual, _linha_item_atual)),
                        width="100%",
                        variant="surface",
                    ),
                    rx.hstack(
                        rx.text("Total da compra:", weight="bold"),
                        rx.text("R$ ", ComprasState.total_atual, weight="bold"),
                        spacing="2",
                    ),
                    width="100%",
                    spacing="3",
                ),
            ),
            rx.button(
                rx.icon("check", size=16),
                "Finalizar compra",
                on_click=ComprasState.finalizar_compra,
                size="3",
            ),
            spacing="3",
            align="start",
            width="100%",
        ),
        width="100%",
    )


def compras_page() -> rx.Component:
    return page(
        _formulario(),
        rx.heading("Últimas compras", size="4"),
        rx.table.root(
            rx.table.header(
                rx.table.row(
                    rx.table.column_header_cell("Data"),
                    rx.table.column_header_cell("Fornecedor"),
                    rx.table.column_header_cell("Itens"),
                    rx.table.column_header_cell("Valor total"),
                    rx.table.column_header_cell("Ações"),
                )
            ),
            rx.table.body(rx.foreach(ComprasState.historico, _linha_historico)),
            width="100%",
            variant="surface",
        ),
        title="Compras",
        subtitle="Entrada de mercadoria dos fornecedores — dá baixa automática no estoque.",
    )

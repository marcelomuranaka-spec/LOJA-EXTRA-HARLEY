import reflex as rx

from ..components.confirm_dialog import confirm_delete_button
from ..components.layout import page
from ..models import TIPOS_TRANSACAO
from ..state.vendas_state import VendasState


def _linha(row: dict) -> rx.Component:
    return rx.table.row(
        rx.table.cell(row["data_transacao"]),
        rx.table.cell(rx.badge(row["tipo_transacao"], variant="soft")),
        rx.table.cell(row["funcionario_nome"]),
        rx.table.cell(row["cliente_nome"]),
        rx.table.cell(rx.text("R$ ", row["valor_total"])),
        rx.table.cell(
            confirm_delete_button(
                VendasState.excluir(row["id"]),
                item_label="esta venda",
            )
        ),
    )


def _formulario() -> rx.Component:
    return rx.card(
        rx.vstack(
            rx.heading("Registrar venda", size="4"),
            rx.hstack(
                rx.select(
                    TIPOS_TRANSACAO,
                    value=VendasState.tipo_transacao,
                    on_change=VendasState.definir_tipo,
                    width="200px",
                ),
                rx.select(
                    VendasState.funcionarios_opcoes,
                    placeholder="Funcionário responsável",
                    value=VendasState.funcionario_selecionado,
                    on_change=VendasState.set_funcionario_selecionado,
                    width="100%",
                ),
                spacing="3",
                width="100%",
            ),
            rx.hstack(
                rx.select(
                    VendasState.clientes_opcoes,
                    value=VendasState.cliente_selecionado,
                    on_change=VendasState.set_cliente_selecionado,
                    flex="1",
                ),
                rx.select(
                    VendasState.motos_opcoes,
                    value=VendasState.moto_selecionada,
                    on_change=VendasState.set_moto_selecionada,
                    flex="1",
                ),
                spacing="3",
                width="100%",
            ),
            rx.divider(),
            rx.text(
                "Opcional: escolha um produto para calcular o valor e baixar o estoque automaticamente.",
                size="2",
                color=rx.color("gray", 10),
            ),
            rx.hstack(
                rx.select(
                    VendasState.produtos_opcoes,
                    value=VendasState.produto_selecionado,
                    on_change=VendasState.definir_produto,
                    flex="1",
                ),
                rx.input(
                    placeholder="Qtd.",
                    type="number",
                    value=VendasState.quantidade,
                    on_change=VendasState.definir_quantidade,
                    width="100px",
                    flex_shrink="0",
                ),
                spacing="3",
                width="100%",
            ),
            rx.hstack(
                rx.text("Valor total da venda (R$)", size="2", weight="bold"),
                rx.input(
                    value=VendasState.valor_total,
                    on_change=VendasState.set_valor_total,
                    type="number",
                    width="160px",
                ),
                spacing="3",
                align="center",
            ),
            rx.hstack(
                rx.button(rx.icon("check", size=16), "Registrar venda", on_click=VendasState.salvar),
                rx.button(
                    rx.icon("x", size=16),
                    "Limpar",
                    variant="soft",
                    color_scheme="gray",
                    on_click=VendasState.nova_venda,
                ),
                spacing="3",
            ),
            spacing="3",
            align="start",
            width="100%",
        ),
        width="100%",
    )


def vendas_page() -> rx.Component:
    return page(
        _formulario(),
        rx.heading("Últimas vendas", size="4"),
        rx.table.root(
            rx.table.header(
                rx.table.row(
                    rx.table.column_header_cell("Data"),
                    rx.table.column_header_cell("Tipo"),
                    rx.table.column_header_cell("Funcionário"),
                    rx.table.column_header_cell("Cliente"),
                    rx.table.column_header_cell("Valor"),
                    rx.table.column_header_cell("Ações"),
                )
            ),
            rx.table.body(rx.foreach(VendasState.transacoes, _linha)),
            width="100%",
            variant="surface",
        ),
        title="Vendas / Balcão",
        subtitle="Registro rápido de vendas de moto, peças e balcão.",
    )

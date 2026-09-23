import reflex as rx

from ..components.confirm_dialog import confirm_delete_button
from ..components.layout import page
from ..state.clientes_state import ClientesState


def _linha(row: dict) -> rx.Component:
    return rx.table.row(
        rx.table.cell(row["nome_cliente"]),
        rx.table.cell(row["cpf_cnpj"]),
        rx.table.cell(row["telefone"]),
        rx.table.cell(row["email"]),
        rx.table.cell(
            rx.hstack(
                rx.button(
                    rx.icon("pencil", size=14),
                    "Editar",
                    size="1",
                    variant="soft",
                    on_click=ClientesState.editar(row),
                ),
                confirm_delete_button(
                    ClientesState.excluir(row["id"]),
                    item_label=f"o cliente “{row['nome_cliente']}”",
                ),
                spacing="2",
            )
        ),
    )


def _formulario() -> rx.Component:
    return rx.card(
        rx.vstack(
            rx.heading(rx.cond(ClientesState.form_id, "Editar cliente", "Novo cliente"), size="4"),
            rx.hstack(
                rx.input(
                    placeholder="Nome do cliente",
                    value=ClientesState.nome_cliente,
                    on_change=ClientesState.set_nome_cliente,
                    width="100%",
                ),
                rx.input(
                    placeholder="CPF ou CNPJ",
                    value=ClientesState.cpf_cnpj,
                    on_change=ClientesState.set_cpf_cnpj,
                    width="220px",
                ),
                spacing="3",
                width="100%",
            ),
            rx.hstack(
                rx.input(
                    placeholder="Telefone",
                    value=ClientesState.telefone,
                    on_change=ClientesState.set_telefone,
                    width="100%",
                ),
                rx.input(
                    placeholder="E-mail",
                    value=ClientesState.email,
                    on_change=ClientesState.set_email,
                    width="100%",
                ),
                spacing="3",
                width="100%",
            ),
            rx.input(
                placeholder="Endereço",
                value=ClientesState.endereco,
                on_change=ClientesState.set_endereco,
                width="100%",
            ),
            rx.hstack(
                rx.button(rx.icon("check", size=16), "Salvar", on_click=ClientesState.salvar),
                rx.button(
                    rx.icon("x", size=16),
                    "Cancelar",
                    variant="soft",
                    color_scheme="gray",
                    on_click=ClientesState.novo,
                ),
                spacing="3",
            ),
            spacing="3",
            align="start",
            width="100%",
        ),
        width="100%",
    )


def clientes_page() -> rx.Component:
    return page(
        _formulario(),
        rx.input(
            placeholder="Buscar por nome...",
            value=ClientesState.busca,
            on_change=ClientesState.definir_busca,
            max_width="320px",
        ),
        rx.table.root(
            rx.table.header(
                rx.table.row(
                    rx.table.column_header_cell("Cliente"),
                    rx.table.column_header_cell("CPF/CNPJ"),
                    rx.table.column_header_cell("Telefone"),
                    rx.table.column_header_cell("E-mail"),
                    rx.table.column_header_cell("Ações"),
                )
            ),
            rx.table.body(rx.foreach(ClientesState.clientes, _linha)),
            width="100%",
            variant="surface",
        ),
        title="Clientes",
        subtitle="Cadastro de clientes da loja e da oficina.",
    )

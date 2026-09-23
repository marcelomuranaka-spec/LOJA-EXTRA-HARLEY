import reflex as rx

from ..components.confirm_dialog import confirm_delete_button
from ..components.layout import page
from ..state.auth_state import AuthState
from ..state.usuarios_state import UsuariosState


def _linha(row: dict) -> rx.Component:
    eh_voce = AuthState.auth_user_id.to(str) == row["id"]
    return rx.table.row(
        rx.table.cell(
            rx.hstack(
                rx.text(row["nome"]),
                rx.cond(eh_voce, rx.badge("você", variant="soft", color_scheme="orange")),
                spacing="2",
                align="center",
            )
        ),
        rx.table.cell(
            rx.input(
                placeholder="email@exemplo.com",
                default_value=row["email"],
                on_blur=UsuariosState.atualizar_email(row["id"]),
                size="1",
                width="100%",
            )
        ),
        rx.table.cell(
            confirm_delete_button(
                UsuariosState.excluir(row["id"]),
                item_label=f"a conta de “{row['nome']}”",
            )
        ),
    )


def _formulario() -> rx.Component:
    return rx.card(
        rx.vstack(
            rx.heading("Novo usuário", size="4"),
            rx.input(
                placeholder="Nome completo",
                value=UsuariosState.novo_nome_completo,
                on_change=UsuariosState.set_novo_nome_completo,
                width="100%",
            ),
            rx.input(
                placeholder="Email (usado para redefinir a senha)",
                type="email",
                value=UsuariosState.novo_email,
                on_change=UsuariosState.set_novo_email,
                width="100%",
            ),
            rx.hstack(
                rx.input(
                    placeholder="Senha",
                    type="password",
                    value=UsuariosState.nova_senha,
                    on_change=UsuariosState.set_nova_senha,
                    width="100%",
                ),
                rx.input(
                    placeholder="Confirmar senha",
                    type="password",
                    value=UsuariosState.nova_confirmar_senha,
                    on_change=UsuariosState.set_nova_confirmar_senha,
                    width="100%",
                ),
                spacing="3",
                width="100%",
            ),
            rx.cond(
                UsuariosState.erro != "",
                rx.text(UsuariosState.erro, color="red", size="2"),
            ),
            rx.hstack(
                rx.button(rx.icon("check", size=16), "Salvar", on_click=UsuariosState.salvar),
                rx.button(
                    rx.icon("x", size=16),
                    "Limpar",
                    variant="soft",
                    color_scheme="gray",
                    on_click=UsuariosState.limpar_formulario,
                ),
                spacing="3",
            ),
            spacing="3",
            align="start",
            width="100%",
        ),
        width="100%",
    )


def usuarios_page() -> rx.Component:
    return page(
        _formulario(),
        rx.table.root(
            rx.table.header(
                rx.table.row(
                    rx.table.column_header_cell("Nome completo"),
                    rx.table.column_header_cell("Email"),
                    rx.table.column_header_cell("Ações"),
                )
            ),
            rx.table.body(rx.foreach(UsuariosState.usuarios, _linha)),
            width="100%",
            variant="surface",
        ),
        title="Usuários do sistema",
        subtitle="Contas de acesso ao sistema — criar novas contas ou remover acessos.",
    )

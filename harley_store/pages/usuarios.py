import reflex as rx

from ..components.confirm_dialog import confirmar_acao, confirm_delete_button
from ..components.layout import page
from ..components.ui import campo, dialogo, entrada, linha, mensagem_erro, tabela
from ..state.usuarios_state import UsuariosState


def _perfil(row: dict) -> rx.Component:
    return rx.cond(
        row["eh_admin"],
        rx.badge(rx.icon("shield-check", size=12), "Administrador", color_scheme="orange", variant="solid"),
        rx.badge(rx.icon("user", size=12), "Funcionário", color_scheme="gray", variant="soft"),
    )


def _linha(row: dict) -> rx.Component:
    return rx.table.row(
        rx.table.cell(
            rx.vstack(
                rx.hstack(
                    rx.text(row["nome"], weight="medium"),
                    rx.cond(row["eh_voce"], rx.badge("você", variant="soft", color_scheme="orange")),
                    spacing="2",
                    align="center",
                ),
                rx.cond(row["eh_servico"],
                        rx.text("Conta usada pelo servidor do sistema — não excluir", size="1",
                                color=rx.color("gray", 10))),
                rx.text("Criada em ", row["criado_em"], size="1", color=rx.color("gray", 9)),
                spacing="0",
                align="start",
            )
        ),
        rx.table.cell(
            rx.input(
                placeholder="email@exemplo.com",
                default_value=row["email"],
                on_blur=UsuariosState.atualizar_email(row["id"]),
                size="1",
                min_width="200px",
                disabled=row["eh_servico"],
            )
        ),
        rx.table.cell(_perfil(row)),
        rx.table.cell(
            rx.cond(
                row["eh_servico"],
                rx.text("—", color=rx.color("gray", 9)),
                rx.flex(
                    confirmar_acao(
                        rx.button(
                            rx.cond(row["eh_admin"], rx.icon("shield-minus", size=14), rx.icon("shield-plus", size=14)),
                            rx.cond(row["eh_admin"], "Remover administrador", "Tornar administrador"),
                            size="1", variant="soft", color_scheme=rx.cond(row["eh_admin"], "gray", "orange"),
                        ),
                        titulo="Mudar perfil",
                        texto=rx.cond(
                            row["eh_admin"],
                            "Esta conta deixará de ser administradora e não poderá mais gerenciar usuários "
                            "nem a configuração do sistema. Continuar?",
                            "Esta conta poderá gerenciar usuários (inclusive definir outros administradores) "
                            "e a configuração do sistema. Continuar?",
                        ),
                        ao_confirmar=UsuariosState.alternar_perfil(row["id"]),
                        rotulo_confirmar="Confirmar",
                    ),
                    rx.button(rx.icon("key-round", size=14), "Definir senha", size="1", variant="soft",
                              color_scheme="gray", on_click=UsuariosState.abrir_senha(row["id"])),
                    rx.cond(
                        row["eh_voce"],
                        rx.fragment(),
                        confirm_delete_button(UsuariosState.excluir(row["id"]),
                                              item_label=f"a conta de “{row['nome']}”"),
                    ),
                    gap="0.5rem",
                    flex_wrap="wrap",
                ),
            )
        ),
    )


def _dialogo_novo() -> rx.Component:
    return dialogo(
        UsuariosState.dialogo_novo,
        UsuariosState.fechar_novo,
        "Novo usuário",
        campo("Nome completo", entrada(UsuariosState.novo_nome_completo, UsuariosState.set_novo_nome_completo)),
        campo("E-mail (usado para entrar no sistema)",
              entrada(UsuariosState.novo_email, UsuariosState.set_novo_email, tipo="email")),
        linha(
            campo("Senha", entrada(UsuariosState.nova_senha, UsuariosState.set_nova_senha, tipo="password")),
            campo("Confirmar senha", entrada(UsuariosState.nova_confirmar_senha,
                                             UsuariosState.set_nova_confirmar_senha, tipo="password")),
        ),
        rx.text("Mínimo de 8 caracteres, com letras e números.", size="1", color=rx.color("gray", 10)),
        rx.hstack(
            rx.switch(checked=UsuariosState.novo_eh_admin, on_change=UsuariosState.set_novo_eh_admin),
            rx.text("Administrador (pode gerenciar usuários e a configuração do sistema)", size="2"),
            spacing="2",
            align="center",
        ),
        mensagem_erro(UsuariosState.erro),
        rx.hstack(
            rx.button("Cancelar", variant="soft", color_scheme="gray", on_click=UsuariosState.fechar_novo),
            rx.button(rx.icon("check", size=16), "Criar conta", on_click=UsuariosState.salvar_novo),
            spacing="3",
            justify="end",
            width="100%",
        ),
        largura="520px",
    )


def _dialogo_senha() -> rx.Component:
    return dialogo(
        UsuariosState.dialogo_senha,
        UsuariosState.fechar_senha,
        "Definir nova senha",
        rx.text("Nova senha para ", rx.text.strong(UsuariosState.senha_usuario_nome),
                ". Depois, avise a pessoa da senha nova.", size="2"),
        linha(
            campo("Nova senha", entrada(UsuariosState.senha_nova, UsuariosState.set_senha_nova, tipo="password")),
            campo("Repetir", entrada(UsuariosState.senha_confirmar, UsuariosState.set_senha_confirmar,
                                     tipo="password")),
        ),
        rx.text("Mínimo de 8 caracteres, com letras e números.", size="1", color=rx.color("gray", 10)),
        mensagem_erro(UsuariosState.erro_senha),
        rx.hstack(
            rx.button("Cancelar", variant="soft", color_scheme="gray", on_click=UsuariosState.fechar_senha),
            rx.button(rx.icon("check", size=16), "Salvar senha", on_click=UsuariosState.salvar_senha),
            spacing="3",
            justify="end",
            width="100%",
        ),
        largura="480px",
    )


def usuarios_page() -> rx.Component:
    return page(
        rx.callout.root(
            rx.callout.icon(rx.icon("info", size=18)),
            rx.callout.text(
                rx.text.strong("Administrador"), ": acessa esta tela e a Configuração do sistema, cria contas, "
                "define senhas e decide quem mais é administrador. ",
                rx.text.strong("Funcionário"), ": usa todas as telas da loja. "
                "Quem esquecer a senha pede a um administrador, que define uma nova aqui.",
            ),
            color_scheme="gray",
            width="100%",
        ),
        rx.hstack(
            rx.spacer(),
            rx.button(rx.icon("user-plus", size=16), "Novo usuário", on_click=UsuariosState.abrir_novo),
            width="100%",
        ),
        mensagem_erro(UsuariosState.erro_lista),
        tabela(["Nome", "E-mail", "Perfil", "Ações"], rx.foreach(UsuariosState.usuarios, _linha)),
        _dialogo_novo(),
        _dialogo_senha(),
        title="Usuários do sistema",
        subtitle="Contas de acesso, perfis (Administrador ou Funcionário) e senhas.",
    )

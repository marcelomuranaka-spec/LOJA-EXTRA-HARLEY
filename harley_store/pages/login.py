import reflex as rx

from ..components.tema import LARANJA, LARANJA_ESCURO, LOGO, PRETO, PRETO_CARTAO
from ..state.auth_state import AuthState


def _campo(rotulo: str, value: rx.Var, on_change, tipo: str = "text") -> rx.Component:
    return rx.vstack(
        rx.text(rotulo, size="2", weight="bold", color="white"),
        rx.input(
            value=value,
            on_change=on_change,
            type=tipo,
            width="100%",
            size="3",
            style={
                "backgroundColor": "#0d0d0d",
                "color": "#ffffff",
                "border": "1px solid #3a3a3a",
                "caretColor": LARANJA,
            },
            _focus={"border_color": LARANJA, "outline": "none"},
        ),
        spacing="1",
        width="100%",
        align="start",
    )


def _formulario_entrar() -> rx.Component:
    return rx.vstack(
        _campo("Email", AuthState.login_email, AuthState.set_login_email, tipo="email"),
        _campo("Senha", AuthState.login_senha, AuthState.set_login_senha, tipo="password"),
        rx.cond(
            AuthState.login_erro != "",
            rx.text(AuthState.login_erro, color="#ff6b6b", size="2"),
        ),
        rx.button(
            "Entrar",
            type="submit",
            width="100%",
            size="3",
            background=LARANJA,
            color="white",
            _hover={"background": LARANJA_ESCURO},
        ),
        rx.hstack(
            rx.icon("info", size=14, color="#888888", flex_shrink="0"),
            rx.text(
                "Esqueceu a senha ou precisa de acesso? Fale com o administrador do sistema.",
                size="1",
                color="#888888",
            ),
            spacing="2",
            align="center",
        ),
        spacing="3",
        width="100%",
    )


def login_page() -> rx.Component:
    return rx.theme(
        rx.box(
            rx.center(
                rx.vstack(
                    rx.link(
                        rx.image(
                            src=LOGO,
                            alt="Harley-Davidson",
                            width="260px",
                            height="auto",
                            style={"mixBlendMode": "lighten"},
                        ),
                        href="/",
                        title="Voltar à tela inicial",
                    ),
                    rx.text(
                        "Sistema da loja e da oficina",
                        color="#999999",
                        size="2",
                        padding_bottom="1.5rem",
                    ),
                    rx.box(
                        rx.heading("Entrar", size="5", color="white", padding_bottom="1rem"),
                        rx.form(_formulario_entrar(), on_submit=AuthState.enviar_login, reset_on_submit=False),
                        background=PRETO_CARTAO,
                        border=f"1px solid {LARANJA}",
                        border_radius="0.75rem",
                        padding="2rem",
                        width="100%",
                        max_width="380px",
                        box_shadow="0 0 40px rgba(247, 101, 17, 0.15)",
                    ),
                    spacing="1",
                    align="center",
                    width="100%",
                    padding_x="1rem",
                ),
                width="100%",
                height="100vh",
            ),
            width="100%",
            height="100vh",
            background=f"radial-gradient(circle at 50% 20%, #1f1f1f 0%, {PRETO} 60%)",
        ),
        appearance="dark",
        accent_color="orange",
        radius="medium",
        has_background=False,
    )

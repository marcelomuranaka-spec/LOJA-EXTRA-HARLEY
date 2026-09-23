"""
Ponto de entrada do app. Aqui só se registram as páginas — a lógica de
cada uma vive em `pages/` (visual) e `state/` (dados e regras).

Para adicionar uma página nova:
    1. crie `state/minha_pagina_state.py` e `pages/minha_pagina.py`
    2. importe a função da página aqui embaixo
    3. adicione uma linha em `app.add_page(...)` — toda página que exige
       login deve incluir `AuthState.exigir_login` como PRIMEIRO item da
       lista de `on_load` (veja os exemplos abaixo).
    4. adicione o link em `components/layout.py` (MENU_ITEMS)
"""

import reflex as rx

from .pages.clientes import clientes_page
from .pages.compras import compras_page
from .pages.dashboard import dashboard_page
from .pages.fornecedores import fornecedores_page
from .pages.funcionarios import funcionarios_page
from .pages.inicio import inicio_page
from .pages.login import login_page
from .pages.motos import motos_page
from .pages.motos_loja import motos_loja_page
from .pages.ordens_servico import ordens_servico_page
from .pages.produtos import produtos_page
from .pages.usuarios import usuarios_page
from .pages.vendas import vendas_page
from .state.auth_state import AuthState
from .state.clientes_state import ClientesState
from .state.compras_state import ComprasState
from .state.dashboard_state import DashboardState
from .state.fornecedores_state import FornecedoresState
from .state.funcionarios_state import FuncionariosState
from .state.motos_loja_state import MotosLojaState
from .state.motos_state import MotosState
from .state.os_state import OrdensServicoState
from .state.produtos_state import ProdutosState
from .state.usuarios_state import UsuariosState
from .state.vendas_state import VendasState

app = rx.App(
    theme=rx.theme(
        # Visual Harley-Davidson: fundo preto + laranja (cores em components/tema.py)
        appearance="dark",
        accent_color="orange",
        gray_color="gray",
        radius="medium",
    ),
    # Tags de PWA — permitem instalar o app na tela de início do iPhone
    # (Safari > Compartilhar > "Adicionar à Tela de Início").
    head_components=[
        rx.el.link(rel="manifest", href="/manifest.json"),
        rx.el.link(rel="apple-touch-icon", href="/icons/apple-touch-icon.png"),
        rx.el.meta(name="theme-color", content="#0b0b0b"),
        rx.el.meta(name="apple-mobile-web-app-capable", content="yes"),
        rx.el.meta(name="apple-mobile-web-app-status-bar-style", content="black-translucent"),
        rx.el.meta(name="apple-mobile-web-app-title", content="Harley Store"),
        # Spinner redondo em qualquer botão enquanto a ação roda no servidor
        # (assets/carregando.js). Precisa carregar antes do app conectar.
        rx.el.script(src="/carregando.js"),
    ],
    # Visual do spinner (o Reflex só publica .css de assets/ por aqui)
    stylesheets=["/carregando.css"],
)

app.add_page(
    inicio_page,
    route="/",
    title="Harley-Davidson — Harley Store",
)
app.add_page(
    login_page,
    route="/login",
    title="Entrar — Harley Store",
    on_load=AuthState.redirecionar_se_ja_logado,
)
app.add_page(
    dashboard_page,
    route="/painel",
    title="Painel — Harley Store",
    on_load=[AuthState.exigir_login, DashboardState.carregar],
)
app.add_page(
    motos_loja_page,
    route="/motos-loja",
    title="Motos da loja — Harley Store",
    on_load=[AuthState.exigir_login, MotosLojaState.carregar, MotosLojaState.novo],
)
app.add_page(
    produtos_page,
    route="/produtos",
    title="Produtos — Harley Store",
    on_load=[AuthState.exigir_login, ProdutosState.carregar],
)
app.add_page(
    clientes_page,
    route="/clientes",
    title="Clientes — Harley Store",
    on_load=[AuthState.exigir_login, ClientesState.carregar],
)
app.add_page(
    motos_page,
    route="/motos",
    title="Motos — Harley Store",
    on_load=[AuthState.exigir_login, MotosState.carregar],
)
app.add_page(
    vendas_page,
    route="/vendas",
    title="Vendas — Harley Store",
    on_load=[AuthState.exigir_login, VendasState.carregar],
)
app.add_page(
    ordens_servico_page,
    route="/ordens-servico",
    title="Ordens de Serviço — Harley Store",
    on_load=[AuthState.exigir_login, OrdensServicoState.carregar],
)
app.add_page(
    compras_page,
    route="/compras",
    title="Compras — Harley Store",
    on_load=[AuthState.exigir_login, ComprasState.carregar],
)
app.add_page(
    fornecedores_page,
    route="/fornecedores",
    title="Fornecedores — Harley Store",
    on_load=[AuthState.exigir_login, FornecedoresState.carregar],
)
app.add_page(
    funcionarios_page,
    route="/funcionarios",
    title="Funcionários — Harley Store",
    on_load=[AuthState.exigir_login, FuncionariosState.carregar],
)
app.add_page(
    usuarios_page,
    route="/usuarios",
    title="Usuários — Harley Store",
    on_load=[AuthState.exigir_login, UsuariosState.carregar],
)

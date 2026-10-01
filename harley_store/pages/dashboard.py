import reflex as rx

from ..components.layout import page
from ..components.tema import BORDA, LARANJA, LARANJA_SUAVE, PRETO_CARTAO, TEXTO_SECUNDARIO
from ..state.auth_state import AuthState
from ..state.dashboard_state import DashboardState


def _cartao(titulo: str, valor, icone: str, alerta: bool = False, href: str = "") -> rx.Component:
    """Indicador do painel. Todos usam o laranja da marca; só os de alerta
    (ex.: estoque baixo) usam vermelho — sempre com ícone + texto."""
    cor_icone = rx.color("red", 10) if alerta else LARANJA
    fundo_icone = rx.color("red", 3) if alerta else LARANJA_SUAVE
    conteudo = rx.hstack(
        rx.center(
            rx.icon(icone, size=20, color=cor_icone),
            width="42px",
            height="42px",
            flex_shrink="0",
            border_radius="0.6rem",
            background=fundo_icone,
        ),
        rx.vstack(
            rx.text(titulo, size="2", color=TEXTO_SECUNDARIO),
            rx.heading(valor, size="6", color="white"),
            spacing="0",
            align="start",
        ),
        spacing="3",
        align="center",
        padding="1rem",
        background=PRETO_CARTAO,
        border=f"1px solid {BORDA}",
        border_radius="0.75rem",
        width="100%",
        height="100%",
        transition="border-color 0.15s",
        _hover={"border_color": LARANJA} if href else {},
    )
    return rx.link(conteudo, href=href, underline="none", width="100%") if href else conteudo


def _secao(titulo: str, *filhos: rx.Component) -> rx.Component:
    return rx.vstack(
        rx.text(titulo, size="1", weight="bold", color=LARANJA, letter_spacing="0.15em"),
        *filhos,
        spacing="2",
        width="100%",
        align="start",
    )


def _grafico_faturamento() -> rx.Component:
    return rx.box(
        rx.text("Faturamento por mês — últimos 12 meses (R$)", size="3", weight="bold", color="white"),
        rx.recharts.bar_chart(
            rx.recharts.cartesian_grid(vertical=False, stroke=BORDA, stroke_dasharray="3 3"),
            rx.recharts.x_axis(data_key="mes", stroke=TEXTO_SECUNDARIO, tick_line=False, axis_line=False),
            rx.recharts.y_axis(stroke=TEXTO_SECUNDARIO, tick_line=False, axis_line=False, width=70),
            rx.recharts.graphing_tooltip(
                cursor={"fill": "rgba(255,255,255,0.04)"},
                content_style={"background": PRETO_CARTAO, "border": f"1px solid {BORDA}", "borderRadius": "8px"},
                label_style={"color": "white"},
                item_style={"color": "white"},
            ),
            rx.recharts.bar(
                data_key="valor",
                name="Faturamento",
                fill=LARANJA,
                radius=[4, 4, 0, 0],
                max_bar_size=48,
                is_animation_active=False,
            ),
            data=DashboardState.faturamento_12_meses,
            width="100%",
            height=240,
            margin={"top": 16, "right": 8, "left": 0, "bottom": 0},
        ),
        padding="1rem",
        background=PRETO_CARTAO,
        border=f"1px solid {BORDA}",
        border_radius="0.75rem",
        width="100%",
    )


def _linha_atividade(row: dict) -> rx.Component:
    return rx.table.row(
        rx.table.cell(row["data"]),
        rx.table.cell(
            rx.badge(
                row["origem"],
                variant="soft",
                color_scheme=rx.cond(
                    row["origem"] == "Venda", "orange",
                    rx.cond(row["origem"] == "Compra", "gray", "red"),  # "Venda (cancelada)"
                ),
            )
        ),
        rx.table.cell(row["tipo"]),
        rx.table.cell(row["quem"]),
        rx.table.cell(rx.text("R$ ", row["valor"]), text_align="right"),
    )


def _venda_recente(v: dict) -> rx.Component:
    return rx.hstack(
        rx.vstack(
            rx.text("nº ", v["id"], " · ", v["data"], size="1", color=TEXTO_SECUNDARIO),
            rx.cond(v["cliente_id"] != "0",
                    rx.link(v["cliente"], href=f"/clientes/{v['cliente_id']}", size="2"),
                    rx.text(v["cliente"], size="2")),
            spacing="0",
            align="start",
            min_width="0",
        ),
        rx.spacer(),
        rx.cond(v["cancelada"], rx.badge("cancelada", color_scheme="red", variant="soft")),
        rx.text("R$ ", v["valor"], size="2", weight="bold", white_space="nowrap"),
        align="center",
        width="100%",
        padding_y="0.35rem",
        border_bottom=f"1px solid {BORDA}",
    )


def _lead_recente(l: dict) -> rx.Component:
    return rx.hstack(
        rx.vstack(
            rx.text(l["data"], " · ", rx.cond(l["origem"] != "", l["origem"], "origem —"), size="1",
                    color=TEXTO_SECUNDARIO),
            rx.text(l["nome"], size="2"),
            spacing="0",
            align="start",
            min_width="0",
        ),
        rx.spacer(),
        rx.badge(l["status"], color_scheme=l["status_cor"].to(str), variant="soft"),
        align="center",
        width="100%",
        padding_y="0.35rem",
        border_bottom=f"1px solid {BORDA}",
    )


def _quadro(titulo: str, href: str, *filhos: rx.Component) -> rx.Component:
    return rx.vstack(
        rx.hstack(
            rx.text(titulo, size="3", weight="bold", color="white"),
            rx.spacer(),
            rx.link("ver tudo", href=href, size="2"),
            width="100%",
            align="center",
        ),
        *filhos,
        spacing="1",
        padding="1rem",
        background=PRETO_CARTAO,
        border=f"1px solid {BORDA}",
        border_radius="0.75rem",
        width="100%",
        align="start",
    )


def dashboard_page() -> rx.Component:
    D = DashboardState
    return page(
        rx.cond(
            AuthState.eh_admin & (D.recursos_pendentes > 0),
            rx.callout.root(
                rx.callout.icon(rx.icon("sparkles", size=18)),
                rx.callout.text(
                    "O sistema ganhou novidades. ", D.recursos_pendentes,
                    " recurso(s) já estão prontos e só aguardam tabelas/campos no Xano. ",
                    rx.link("Ver o que mudou e o passo a passo", href="/configuracao"),
                ),
                color_scheme="orange",
                width="100%",
            ),
        ),
        _secao(
            "ATENDIMENTO",
            rx.grid(
                _cartao("Clientes", D.total_clientes, "users", href="/clientes"),
                _cartao("Clientes novos no mês", D.clientes_novos_mes, "user-plus", href="/clientes"),
                _cartao("Leads novos", D.leads_novos, "user-search", href="/leads"),
                _cartao("Leads em atendimento", D.leads_abertos, "messages-square", href="/leads"),
                columns=rx.breakpoints(initial="2", md="4"),
                spacing="4",
                width="100%",
            ),
        ),
        _secao(
            "VENDAS E FATURAMENTO",
            rx.grid(
                _cartao("Faturamento de hoje", rx.text("R$ ", D.faturamento_hoje), "wallet", href="/vendas"),
                _cartao("Faturamento do mês", rx.text("R$ ", D.faturamento_mes), "chart-line", href="/vendas"),
                _cartao("Vendas no mês", D.vendas_mes, "shopping-cart", href="/vendas"),
                _cartao("Ticket médio do mês", rx.text("R$ ", D.ticket_medio_mes), "receipt", href="/vendas"),
                columns=rx.breakpoints(initial="2", md="4"),
                spacing="4",
                width="100%",
            ),
            _grafico_faturamento(),
        ),
        _secao(
            "MOTOS DA LOJA",
            rx.grid(
                _cartao("Motos disponíveis", D.motos_disponiveis, "bike", href="/motos-loja"),
                _cartao("Valor das disponíveis", rx.text("R$ ", D.valor_estoque_motos), "gem", href="/motos-loja"),
                _cartao("Vendidas no mês", D.motos_vendidas_mes, "badge-dollar-sign", href="/motos-loja"),
                _cartao("Vendidas (total)", D.motos_vendidas_total, "trophy", href="/motos-loja"),
                columns=rx.breakpoints(initial="2", md="4"),
                spacing="4",
                width="100%",
            ),
        ),
        _secao(
            "ESTOQUE E OFICINA",
            rx.grid(
                _cartao("Produtos ativos", D.total_produtos, "package", href="/produtos"),
                _cartao("Produtos com estoque", D.produtos_em_estoque, "boxes", href="/produtos"),
                _cartao("Estoque baixo", D.produtos_estoque_baixo, "triangle-alert", alerta=True, href="/produtos"),
                _cartao("OS em aberto", D.os_em_aberto, "wrench", href="/ordens-servico"),
                columns=rx.breakpoints(initial="2", md="4"),
                spacing="4",
                width="100%",
            ),
        ),
        rx.grid(
            _quadro("Vendas recentes", "/vendas",
                    rx.cond(D.vendas_recentes.length() > 0, rx.foreach(D.vendas_recentes, _venda_recente),
                            rx.text("Nenhuma venda ainda.", size="2", color=TEXTO_SECUNDARIO))),
            _quadro("Leads recentes", "/leads",
                    rx.cond(D.tem_leads,
                            rx.cond(D.leads_recentes.length() > 0, rx.foreach(D.leads_recentes, _lead_recente),
                                    rx.text("Nenhum lead cadastrado.", size="2", color=TEXTO_SECUNDARIO)),
                            rx.text("Aguardando a tabela leads no Xano.", size="2", color=TEXTO_SECUNDARIO))),
            columns=rx.breakpoints(initial="1", md="2"),
            spacing="4",
            width="100%",
        ),
        _secao(
            "MOVIMENTO RECENTE (VENDAS E COMPRAS)",
            rx.box(rx.table.root(
                rx.table.header(
                    rx.table.row(
                        rx.table.column_header_cell("Data"),
                        rx.table.column_header_cell("Origem"),
                        rx.table.column_header_cell("Tipo"),
                        rx.table.column_header_cell("Quem"),
                        rx.table.column_header_cell("Valor", text_align="right"),
                    )
                ),
                rx.table.body(rx.foreach(DashboardState.atividades_recentes, _linha_atividade)),
                width="100%",
                variant="surface",
            ), width="100%", overflow_x="auto"),
        ),
        title="Painel",
        subtitle="Visão geral da loja, da oficina e do estoque de motos.",
    )

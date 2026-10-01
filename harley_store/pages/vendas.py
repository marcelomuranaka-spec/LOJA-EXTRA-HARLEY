import reflex as rx

from ..components.botao_imprimir import botao_imprimir
from ..components.layout import page
from ..components.ui import campo, linha, paginacao, selecao, tabela, vazio
from ..state.vendas_state import VendasState as V


# ------------------------------------------------------------------ cancelamento

def _dialogo_cancelar(gatilho: rx.Component, titulo, descricao, ao_confirmar) -> rx.Component:
    """Confirmação de cancelamento com motivo opcional (individual ou em lote)."""
    return rx.alert_dialog.root(
        rx.alert_dialog.trigger(gatilho),
        rx.alert_dialog.content(
            rx.alert_dialog.title(titulo),
            rx.alert_dialog.description(descricao),
            rx.input(
                placeholder="Motivo do cancelamento (opcional)",
                value=V.motivo_cancelamento,
                on_change=V.set_motivo_cancelamento,
                width="100%",
                margin_top="0.75rem",
            ),
            rx.hstack(
                rx.alert_dialog.cancel(rx.button("Voltar", variant="soft", color_scheme="gray")),
                rx.alert_dialog.action(rx.button("Cancelar venda", color_scheme="red", on_click=ao_confirmar)),
                spacing="3",
                justify="end",
                width="100%",
                padding_top="0.75rem",
            ),
        ),
    )


def _situacao(row: dict) -> rx.Component:
    return rx.cond(
        row["cancelada"],
        rx.vstack(
            rx.badge(rx.icon("ban", size=12), "Cancelada", color_scheme="red", variant="soft"),
            rx.text(row["data_cancelamento"], size="1", color=rx.color("gray", 10)),
            spacing="1",
            align="start",
            title=row["motivo"],
        ),
        rx.badge(rx.icon("circle-check", size=12), "Ativa", color_scheme="green", variant="soft"),
    )


def _linha(row: dict) -> rx.Component:
    return rx.table.row(
        rx.table.cell(
            rx.cond(
                row["cancelada"],
                rx.box(width="16px"),
                rx.checkbox(
                    checked=V.selecionadas.contains(row["id"]),
                    on_change=lambda _: V.alternar_selecao(row["id"]),
                ),
            )
        ),
        rx.table.cell(rx.text("nº ", row["id"], size="2", color=rx.color("gray", 10))),
        rx.table.cell(row["data_transacao"]),
        rx.table.cell(rx.badge(row["tipo_transacao"], variant="soft")),
        rx.table.cell(row["funcionario_nome"]),
        rx.table.cell(rx.cond(row["cliente_id"] != "0",
                              rx.link(row["cliente_nome"], href=f"/clientes/{row['cliente_id']}"),
                              rx.text("—"))),
        rx.cond(V.tem_pagamento, rx.table.cell(rx.cond(row["forma_pagamento"] != "", row["forma_pagamento"], "—"))),
        rx.table.cell(row["qtd_itens"], text_align="center"),
        rx.table.cell(rx.text("R$ ", row["valor_total"]), white_space="nowrap"),
        rx.table.cell(_situacao(row)),
        rx.table.cell(
            rx.hstack(
                botao_imprimir("venda", row["id"]),
                rx.cond(
                    row["cancelada"],
                    rx.fragment(),
                    _dialogo_cancelar(
                        rx.button(rx.icon("ban", size=14), "Cancelar", size="1", variant="soft",
                                  color_scheme="red", on_click=V.preparar_cancelamento),
                        "Cancelar venda",
                        "A venda continuará no histórico como cancelada, sairá do faturamento, os "
                        "produtos voltarão ao estoque e a moto da loja (se houver) voltará a ficar disponível.",
                        V.cancelar(row["id"]),
                    ),
                ),
                spacing="2",
            )
        ),
        opacity=rx.cond(row["cancelada"], "0.55", "1"),
    )


# ------------------------------------------------------------------ carrinho

def _linha_carrinho(item: dict, indice: int) -> rx.Component:
    return rx.table.row(
        rx.table.cell(
            rx.hstack(
                rx.match(
                    item["tipo"],
                    ("moto", rx.badge(rx.icon("bike", size=12), "moto", variant="soft", color_scheme="orange")),
                    ("avulso", rx.badge("avulso", variant="soft", color_scheme="gray")),
                    rx.fragment(),
                ),
                rx.text(item["descricao"]),
                spacing="2",
                align="center",
            )
        ),
        rx.table.cell(item["quantidade"], text_align="center"),
        rx.table.cell(rx.text("R$ ", item["valor_unitario"]), white_space="nowrap"),
        rx.table.cell(rx.text("R$ ", item["subtotal"]), white_space="nowrap"),
        rx.table.cell(
            rx.button(rx.icon("x", size=14), size="1", variant="soft", color_scheme="red",
                      on_click=V.remover_item(indice), title="Remover item")
        ),
    )


def _passo(numero: str, titulo: str, *filhos: rx.Component) -> rx.Component:
    return rx.vstack(
        rx.hstack(
            rx.center(rx.text(numero, size="1", weight="bold"), width="22px", height="22px", border_radius="50%",
                      background=rx.color("orange", 9), color="white", flex_shrink="0"),
            rx.text(titulo, size="3", weight="bold"),
            spacing="2",
            align="center",
        ),
        *filhos,
        spacing="2",
        width="100%",
        align="start",
    )


def _busca(lista_id: str, opcoes, valor, ao_mudar, placeholder: str) -> rx.Component:
    """Campo com sugestões: digite parte do nome e escolha na lista."""
    return rx.box(
        rx.input(rx.input.slot(rx.icon("search", size=14)), value=valor, on_change=ao_mudar,
                 placeholder=placeholder, list=lista_id, width="100%"),
        rx.el.datalist(rx.foreach(opcoes, lambda o: rx.el.option(value=o)), id=lista_id),
        width="100%",
    )


def _formulario() -> rx.Component:
    return rx.card(
        rx.vstack(
            rx.heading("Nova venda", size="4"),
            _passo(
                "1", "Cliente",
                linha(
                    campo("Cliente", _busca("lista-clientes-venda", V.clientes_opcoes, V.cliente_selecionado,
                                            V.definir_cliente, "Nome ou CPF (vazio = venda de balcão)"),
                          largura_min="260px"),
                    campo("Moto do cliente (oficina)", selecao(V.motos_do_cliente, V.moto_selecionada,
                                                               V.set_moto_selecionada)),
                ),
                linha(
                    campo("Vendedor", selecao(V.funcionarios_opcoes, V.funcionario_selecionado,
                                              V.set_funcionario_selecionado)),
                    campo("Tipo", selecao(V.tipos_transacao, V.tipo_transacao, V.set_tipo_transacao),
                          largura_min="140px"),
                ),
            ),
            rx.divider(),
            _passo(
                "2", "Produtos e serviços",
                linha(
                    campo("Produto do estoque", _busca("lista-produtos-venda", V.produtos_opcoes,
                                                       V.produto_selecionado, V.definir_produto,
                                                       "Digite parte do nome"), largura_min="240px"),
                    campo("Qtd.", rx.input(value=V.item_quantidade, on_change=V.set_item_quantidade,
                                           type="number", min=1, width="100%"), largura_min="80px"),
                    campo("Preço unit. (R$)", rx.input(value=V.item_preco, on_change=V.set_item_preco,
                                                       width="100%"), largura_min="110px"),
                    rx.button(rx.icon("plus", size=16), "Adicionar", on_click=V.adicionar_produto, variant="soft"),
                ),
                rx.cond(
                    V.motos_loja_opcoes.length() > 0,
                    linha(
                        campo("Moto da loja", selecao(V.motos_loja_opcoes, V.moto_loja_selecionada,
                                                      V.definir_moto_loja, "Escolha a moto vendida"),
                              largura_min="260px"),
                        campo("Preço da moto (R$)", rx.input(value=V.moto_loja_preco, on_change=V.set_moto_loja_preco,
                                                             width="100%"), largura_min="130px"),
                        rx.button(rx.icon("bike", size=16), "Adicionar moto", on_click=V.adicionar_moto_loja,
                                  variant="soft", color_scheme="orange"),
                    ),
                ),
                linha(
                    campo("Item avulso (sem estoque)", rx.input(placeholder="Ex.: Mão de obra",
                                                                value=V.avulso_descricao,
                                                                on_change=V.set_avulso_descricao, width="100%"),
                          largura_min="240px"),
                    campo("Qtd.", rx.input(value=V.avulso_quantidade, on_change=V.set_avulso_quantidade,
                                           type="number", min=1, width="100%"), largura_min="80px"),
                    campo("Valor unit. (R$)", rx.input(value=V.avulso_valor, on_change=V.set_avulso_valor,
                                                       width="100%"), largura_min="110px"),
                    rx.button(rx.icon("plus", size=16), "Adicionar", on_click=V.adicionar_avulso,
                              variant="soft", color_scheme="gray"),
                ),
                rx.cond(
                    V.carrinho.length() > 0,
                    tabela(["Item", "Qtd.", "Unitário", "Subtotal", ""], rx.foreach(V.carrinho, _linha_carrinho)),
                    vazio("Nenhum item adicionado."),
                ),
            ),
            rx.divider(),
            _passo(
                "3", "Fechamento",
                linha(
                    campo("Desconto", rx.hstack(
                        rx.input(value=V.desconto_valor, on_change=V.set_desconto_valor, placeholder="0",
                                 width="100%"),
                        rx.segmented_control.root(
                            rx.segmented_control.item("R$", value="R$"),
                            rx.segmented_control.item("%", value="%"),
                            value=V.desconto_tipo,
                            on_change=V.definir_desconto_tipo,
                        ),
                        spacing="2", width="100%", align="center",
                    ), largura_min="200px"),
                    rx.cond(V.tem_pagamento,
                            campo("Forma de pagamento *", selecao(V.formas_pagamento, V.forma_pagamento,
                                                                  V.set_forma_pagamento, "Escolha"))),
                ),
                rx.card(
                    rx.vstack(
                        rx.hstack(rx.text("Subtotal"), rx.spacer(), rx.text("R$ ", V.subtotal_carrinho), width="100%"),
                        rx.hstack(rx.text("Desconto"), rx.spacer(), rx.text("− R$ ", V.desconto_carrinho,
                                                                          color=rx.color("red", 10)), width="100%"),
                        rx.divider(),
                        rx.hstack(rx.text("Total", size="5", weight="bold"), rx.spacer(),
                                  rx.text("R$ ", V.total_carrinho, size="6", weight="bold"), width="100%"),
                        spacing="2",
                        width="100%",
                    ),
                    width="100%",
                    max_width="420px",
                ),
            ),
            rx.cond(V.erro_venda != "",
                    rx.callout(V.erro_venda, icon="triangle_alert", color_scheme="red", size="1", width="100%")),
            rx.cond(V.sucesso_venda != "",
                    rx.callout.root(
                        rx.callout.icon(rx.icon("circle-check")),
                        rx.hstack(rx.text(V.sucesso_venda, size="2"),
                                  botao_imprimir("venda", V.ultima_venda_id, "Imprimir comprovante"),
                                  spacing="3", align="center", flex_wrap="wrap"),
                        color_scheme="green", size="1", width="100%",
                    )),
            rx.flex(
                rx.button(rx.icon("check", size=18), "Finalizar venda", on_click=V.salvar, size="3",
                          disabled=V.carrinho.length() == 0),
                rx.button(rx.icon("x", size=16), "Limpar", variant="soft", color_scheme="gray", size="3",
                          on_click=V.nova_venda),
                gap="0.75rem",
                flex_wrap="wrap",
            ),
            spacing="4",
            align="start",
            width="100%",
        ),
        width="100%",
    )


def _barra_lote() -> rx.Component:
    return rx.flex(
        rx.heading("Vendas registradas", size="4"),
        rx.spacer(),
        rx.cond(
            V.qtd_selecionadas > 0,
            rx.hstack(
                rx.button("Limpar seleção", size="2", variant="ghost", color_scheme="gray",
                          on_click=V.limpar_selecao),
                _dialogo_cancelar(
                    rx.button(rx.icon("ban", size=16), "Cancelar selecionadas (", V.qtd_selecionadas, ")",
                              color_scheme="red", on_click=V.preparar_cancelamento),
                    "Cancelar vendas selecionadas",
                    "As vendas selecionadas continuarão no histórico como canceladas, sairão do faturamento "
                    "e os produtos voltarão ao estoque.",
                    V.cancelar_selecionadas,
                ),
                spacing="3",
                align="center",
            ),
        ),
        width="100%",
        align="center",
        gap="0.5rem",
        flex_wrap="wrap",
    )


def vendas_page() -> rx.Component:
    return page(
        rx.cond(V.aviso_itens != "",
                rx.callout(V.aviso_itens, icon="triangle_alert", color_scheme="amber", width="100%")),
        _formulario(),
        _barra_lote(),
        rx.cond(
            V.resultado_cancelamento.length() > 0,
            rx.callout.root(
                rx.callout.icon(rx.icon("info")),
                rx.vstack(
                    rx.foreach(V.resultado_cancelamento, lambda texto: rx.text(texto, size="2")),
                    rx.button("OK", size="1", variant="soft", on_click=V.fechar_resultado),
                    spacing="1",
                    align="start",
                ),
                color_scheme="blue",
                width="100%",
            ),
        ),
        linha(
            campo("Pesquisar", rx.input(rx.input.slot(rx.icon("search", size=14)),
                                        placeholder="Nº da venda, cliente ou vendedor",
                                        value=V.busca_lista, on_change=V.definir_busca_lista, width="100%"),
                  largura_min="240px"),
            campo("Situação", selecao(V.situacoes_lista, V.filtro_situacao, V.definir_filtro_situacao),
                  largura_min="140px"),
        ),
        rx.cond(
            V.total_lista > 0,
            rx.vstack(
                tabela(["", "Nº", "Data", "Tipo", "Vendedor", "Cliente",
                        rx.cond(V.tem_pagamento, rx.table.column_header_cell("Pagamento")),
                        "Itens", "Valor", "Situação", "Ações"],
                       rx.foreach(V.transacoes, _linha)),
                paginacao(V.pagina, V.total_paginas, V.total_lista, V.pagina_anterior, V.proxima_pagina),
                width="100%",
                spacing="3",
            ),
            vazio("Nenhuma venda encontrada."),
        ),
        title="Vendas / Balcão",
        subtitle="Venda rápida com produtos, moto da loja, desconto e forma de pagamento. "
                 "Canceladas ficam no histórico e devolvem o estoque.",
    )

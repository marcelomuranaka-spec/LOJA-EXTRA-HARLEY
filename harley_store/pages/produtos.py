import reflex as rx

from ..components.confirm_dialog import confirm_delete_button
from ..components.foto import campo_foto, miniatura
from ..components.layout import page
from ..components.ui import (aviso_ativacao, campo, dialogo, entrada, linha, mensagem_erro, paginacao,
                             selecao, tabela, vazio)
from ..state.produtos_state import ProdutosState as P


def _estoque(row: dict) -> rx.Component:
    return rx.vstack(
        rx.cond(
            row["estoque_baixo"],
            rx.badge(rx.icon("triangle-alert", size=12), row["estoque_qtd"], color_scheme="red", variant="soft"),
            rx.text(row["estoque_qtd"], weight="medium"),
        ),
        rx.text("mín. ", row["estoque_minimo"], size="1", color=rx.color("gray", 9)),
        spacing="0",
        align="start",
    )


def _linha(row: dict) -> rx.Component:
    return rx.table.row(
        rx.table.cell(miniatura(row["foto_url"], row["foto_local"], "48px", "48px", "package")),
        rx.table.cell(
            rx.vstack(
                rx.hstack(
                    rx.text(row["nome_produto"], weight="medium"),
                    rx.cond(row["ativo"], rx.fragment(), rx.badge("Inativo", color_scheme="gray", variant="soft")),
                    spacing="2",
                    align="center",
                ),
                rx.cond(row["sku"] != "", rx.text("SKU ", row["sku"], size="1", color=rx.color("gray", 10))),
                spacing="0",
                align="start",
            )
        ),
        rx.table.cell(row["categoria"]),
        rx.table.cell(_estoque(row)),
        rx.cond(P.tem_extras,
                rx.table.cell(rx.cond(row["preco_custo"] != "", rx.text("R$ ", row["preco_custo"]), rx.text("—")))),
        rx.table.cell(
            rx.vstack(
                rx.text("R$ ", row["preco_venda"], weight="medium"),
                rx.cond(row["margem"] != "",
                        rx.text("margem ", row["margem"], size="1", color=rx.color("gray", 10))),
                spacing="0",
                align="start",
            )
        ),
        rx.table.cell(
            rx.flex(
                rx.button(rx.icon("pencil", size=14), "Editar", size="1", variant="soft",
                          on_click=P.editar(row["id"])),
                rx.button(rx.icon("arrow-up-down", size=14), "Estoque", size="1", variant="soft",
                          color_scheme="gray", on_click=P.abrir_ajuste(row["id"])),
                confirm_delete_button(P.excluir(row["id"]), item_label=f"o produto “{row['nome_produto']}”"),
                gap="0.5rem",
                flex_wrap="wrap",
            )
        ),
    )


def _categoria_campo() -> rx.Component:
    return rx.cond(
        P.usa_tabela_categorias,
        campo("Categoria *", selecao(P.categorias_opcoes, P.categoria, P.set_categoria, "Escolha a categoria")),
        campo(
            "Categoria *",
            rx.vstack(
                rx.input(value=P.categoria, on_change=P.set_categoria,
                         placeholder="Ex.: Peças, Acessórios, Capacetes", width="100%",
                         list="categorias-existentes"),
                rx.el.datalist(rx.foreach(P.categorias_opcoes, lambda c: rx.el.option(value=c)),
                               id="categorias-existentes"),
                spacing="0",
                width="100%",
            ),
        ),
    )


def _formulario() -> rx.Component:
    return dialogo(
        P.dialogo_aberto,
        P.fechar_dialogo,
        rx.cond(P.form_id, "Editar produto", "Novo produto"),
        linha(
            campo("Nome *", entrada(P.nome_produto, P.set_nome_produto), largura_min="260px"),
            _categoria_campo(),
        ),
        campo("Descrição", entrada(P.descricao, P.set_descricao)),
        rx.cond(
            P.tem_extras,
            linha(
                campo("Código / SKU", entrada(P.sku, P.set_sku)),
                campo("Preço de custo (R$)", entrada(P.preco_custo, P.set_preco_custo, "0,00")),
                campo("Preço de venda (R$) *", entrada(P.preco_venda, P.set_preco_venda, "0,00")),
            ),
            linha(campo("Preço de venda (R$) *", entrada(P.preco_venda, P.set_preco_venda, "0,00"))),
        ),
        linha(
            rx.cond(
                P.form_id,
                campo("Estoque atual",
                      rx.text(P.estoque_atual, " un. — para mudar, use o botão Estoque na lista",
                              size="2", padding_y="0.4rem")),
                campo("Estoque inicial", entrada(P.estoque_inicial, P.set_estoque_inicial, "0")),
            ),
            rx.cond(
                P.tem_extras,
                campo("Estoque mínimo", entrada(P.estoque_minimo, P.set_estoque_minimo, "5"),
                      ajuda="Alerta quando o saldo ficar igual ou abaixo disto (vazio = 5)."),
            ),
        ),
        rx.cond(
            P.tem_extras,
            rx.hstack(rx.switch(checked=P.ativo, on_change=P.set_ativo),
                      rx.text("Produto ativo (aparece nas vendas)", size="2"), spacing="2", align="center"),
        ),
        campo_foto("Foto do produto", "upload_imagem_produto", P.imagem_url, P.imagem_local,
                   P.handle_upload_imagem, P.remover_imagem, P.erro_imagem, "package"),
        mensagem_erro(P.erro_form),
        rx.hstack(
            rx.button("Cancelar", variant="soft", color_scheme="gray", on_click=P.fechar_dialogo),
            rx.button(rx.icon("check", size=16), "Salvar", on_click=P.salvar),
            spacing="3",
            justify="end",
            width="100%",
        ),
    )


def _ajuste() -> rx.Component:
    return dialogo(
        P.dialogo_ajuste,
        P.fechar_ajuste,
        "Ajustar estoque",
        rx.text(rx.text.strong(P.ajuste_nome), " — saldo atual: ", rx.text.strong(P.ajuste_saldo), " un.",
                size="2"),
        linha(
            campo("Tipo de ajuste", selecao(P.tipos_ajuste, P.ajuste_tipo, P.set_ajuste_tipo)),
            campo("Quantidade", entrada(P.ajuste_qtd, P.set_ajuste_qtd, "0"), largura_min="120px"),
        ),
        rx.text("Vendas, ordens de serviço e compras já mexem no estoque sozinhas. Use o ajuste para "
                "correções, perdas ou contagem do inventário.", size="1", color=rx.color("gray", 10)),
        mensagem_erro(P.erro_ajuste),
        rx.hstack(
            rx.button("Cancelar", variant="soft", color_scheme="gray", on_click=P.fechar_ajuste),
            rx.button(rx.icon("check", size=16), "Aplicar", on_click=P.salvar_ajuste),
            spacing="3",
            justify="end",
            width="100%",
        ),
        largura="480px",
    )


def produtos_page() -> rx.Component:
    return page(
        rx.flex(
            rx.cond(
                P.qtd_estoque_baixo > 0,
                rx.button(rx.icon("triangle-alert", size=16), P.qtd_estoque_baixo,
                          " produto(s) com estoque baixo", color_scheme="red", variant="soft",
                          on_click=P.ver_estoque_baixo),
            ),
            rx.spacer(),
            rx.link(rx.button(rx.icon("tags", size=16), "Categorias", variant="soft", color_scheme="gray"),
                    href="/categorias", underline="none"),
            rx.button(rx.icon("plus", size=16), "Novo produto", on_click=P.novo),
            gap="0.5rem",
            flex_wrap="wrap",
            width="100%",
        ),
        rx.cond(
            P.tem_extras,
            rx.fragment(),
            aviso_ativacao("Cadastro completo de produtos aguardando o Xano",
                           "SKU, preço de custo, estoque mínimo por produto e ativo/inativo já estão prontos "
                           "e aparecem quando os campos forem criados na tabela produtos."),
        ),
        linha(
            campo("Pesquisar",
                  rx.input(rx.input.slot(rx.icon("search", size=16)), placeholder="Nome, SKU ou descrição",
                           value=P.busca, on_change=P.definir_busca, width="100%"),
                  largura_min="240px"),
            campo("Categoria", selecao(P.categorias_filtro, P.filtro_categoria, P.definir_filtro_categoria),
                  largura_min="160px"),
            rx.cond(P.tem_extras,
                    campo("Situação", selecao(P.situacoes, P.filtro_situacao, P.definir_filtro_situacao),
                          largura_min="130px")),
            rx.hstack(rx.switch(checked=P.somente_estoque_baixo, on_change=P.alternar_filtro_estoque_baixo),
                      rx.text("Só estoque baixo", size="2"), spacing="2", align="center",
                      padding_bottom="0.4rem"),
        ),
        rx.cond(
            P.total > 0,
            rx.vstack(
                tabela(["Foto", "Produto", "Categoria", "Estoque",
                        rx.cond(P.tem_extras, rx.table.column_header_cell("Custo")), "Preço", "Ações"],
                       rx.foreach(P.produtos, _linha)),
                paginacao(P.pagina, P.total_paginas, P.total, P.pagina_anterior, P.proxima_pagina),
                width="100%",
                spacing="3",
            ),
            vazio("Nenhum produto encontrado com esses filtros."),
        ),
        _formulario(),
        _ajuste(),
        title="Produtos",
        subtitle="Catálogo e estoque de peças, acessórios e itens vendidos na loja.",
    )

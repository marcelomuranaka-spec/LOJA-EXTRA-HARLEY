import reflex as rx

from ..components.confirm_dialog import confirm_delete_button
from ..components.layout import page
from ..components.ui import aviso_ativacao, campo, dialogo, entrada, mensagem_erro, secao, tabela, vazio
from ..state.categorias_state import CategoriasState as C


def _linha(row: dict) -> rx.Component:
    return rx.table.row(
        rx.table.cell(rx.text(row["nome"], weight="medium")),
        rx.table.cell(rx.text(row["qtd"], " produto(s)")),
        rx.table.cell(rx.cond(row["ativo"], rx.badge("Ativa", color_scheme="green", variant="soft"),
                              rx.badge("Desativada", color_scheme="gray", variant="soft"))),
        rx.table.cell(
            rx.flex(
                rx.button(rx.icon("pencil", size=14), "Renomear", size="1", variant="soft",
                          on_click=C.abrir_editar(row["id"])),
                rx.button(rx.cond(row["ativo"], "Desativar", "Ativar"), size="1", variant="soft",
                          color_scheme="gray", on_click=C.alternar_ativo(row["id"])),
                rx.cond(row["qtd"].to(int) == 0,
                        confirm_delete_button(C.excluir(row["id"]), item_label=f"a categoria “{row['nome']}”")),
                gap="0.5rem",
                flex_wrap="wrap",
            )
        ),
    )


def _texto(row: dict) -> rx.Component:
    return rx.table.row(rx.table.cell(row["nome"]), rx.table.cell(rx.text(row["qtd"], " produto(s)")))


def categorias_page() -> rx.Component:
    return page(
        rx.cond(
            C.tabela_existe,
            rx.vstack(
                rx.flex(
                    rx.cond(
                        C.pendentes_importacao > 0,
                        rx.button(rx.icon("download", size=16), "Importar categorias dos produtos",
                                  variant="soft", on_click=C.importar,
                                  title="Cria as categorias já usadas nos produtos (e as sugeridas) "
                                        "e liga cada produto à sua"),
                    ),
                    rx.spacer(),
                    rx.button(rx.icon("plus", size=16), "Nova categoria", on_click=C.abrir_novo),
                    gap="0.5rem",
                    flex_wrap="wrap",
                    width="100%",
                ),
                rx.cond(
                    C.pode_ligar,
                    rx.fragment(),
                    aviso_ativacao("Ligação produto → categoria aguardando o Xano",
                                   "Crie o campo categoria_id na tabela produtos para cada produto apontar "
                                   "para a sua categoria. Até lá, a ligação é pelo nome."),
                ),
                rx.cond(
                    C.categorias.length() > 0,
                    tabela(["Categoria", "Produtos", "Situação", "Ações"], rx.foreach(C.categorias, _linha)),
                    vazio("Nenhuma categoria cadastrada. Use “Importar categorias dos produtos” para começar."),
                ),
                spacing="3",
                width="100%",
            ),
            rx.vstack(
                aviso_ativacao("Cadastro de categorias aguardando o Xano",
                               "Crie a tabela categorias no Xano. Depois, um clique em “Importar categorias "
                               "dos produtos” cria as categorias abaixo (mais Peças, Acessórios, Capacetes, "
                               "Vestuário, Lubrificantes e Outros) sem digitar nada."),
                secao("Categorias usadas hoje nos produtos (texto)",
                      tabela(["Categoria", "Produtos"], rx.foreach(C.categorias_texto, _texto)), icone="tags"),
                spacing="3",
                width="100%",
            ),
        ),
        rx.text("Excluir só é possível quando nenhum produto usa a categoria; caso contrário, desative-a "
                "(ela deixa de aparecer no cadastro de produtos).", size="1", color=rx.color("gray", 10)),
        dialogo(
            C.dialogo_aberto,
            C.fechar_dialogo,
            rx.cond(C.form_id, "Renomear categoria", "Nova categoria"),
            campo("Nome", entrada(C.nome, C.set_nome, "Ex.: Capacetes")),
            mensagem_erro(C.erro_form),
            rx.hstack(
                rx.button("Cancelar", variant="soft", color_scheme="gray", on_click=C.fechar_dialogo),
                rx.button(rx.icon("check", size=16), "Salvar", on_click=C.salvar),
                spacing="3",
                justify="end",
                width="100%",
            ),
            largura="420px",
        ),
        title="Categorias",
        subtitle="Categorias dos produtos (peças, acessórios, capacetes...).",
    )

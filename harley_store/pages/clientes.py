import reflex as rx

from ..components.confirm_dialog import confirm_delete_button
from ..components.layout import page
from ..components.ui import (aviso_ativacao, campo, dialogo, entrada, linha, mensagem_erro, paginacao,
                             selecao, tabela, vazio)
from ..state.clientes_state import ClientesState


def _status(row: dict) -> rx.Component:
    return rx.badge(row["status"], color_scheme=row["status_cor"], variant="soft")


def _linha(row: dict) -> rx.Component:
    return rx.table.row(
        rx.table.cell(
            rx.link(
                rx.vstack(
                    rx.text(row["nome_cliente"], weight="medium"),
                    rx.text(row["cpf_cnpj"], size="1", color=rx.color("gray", 10)),
                    spacing="0",
                    align="start",
                ),
                href=f"/clientes/{row['id']}",
                underline="none",
                color="inherit",
            )
        ),
        rx.table.cell(
            rx.vstack(
                rx.text(rx.cond(row["telefone"] != "", row["telefone"], "—"), size="2"),
                rx.cond(row["email"] != "", rx.text(row["email"], size="1", color=rx.color("gray", 10))),
                spacing="0",
                align="start",
            )
        ),
        rx.cond(ClientesState.tem_cidade, rx.table.cell(rx.cond(row["cidade"] != "", row["cidade"], "—"))),
        rx.cond(ClientesState.tem_status, rx.table.cell(_status(row))),
        rx.table.cell(rx.text(row["qtd_motos"], " moto(s) · ", row["qtd_compras"], " compra(s)", size="2")),
        rx.table.cell(
            rx.flex(
                rx.link(rx.button(rx.icon("eye", size=14), "Visualizar", size="1", variant="soft",
                                  color_scheme="gray"),
                        href=f"/clientes/{row['id']}", underline="none"),
                rx.button(rx.icon("pencil", size=14), "Editar", size="1", variant="soft",
                          on_click=ClientesState.abrir_editar(row["id"])),
                rx.cond(
                    row["whatsapp_link"] != "",
                    rx.link(rx.button(rx.icon("message-circle", size=14), size="1", variant="soft",
                                      color_scheme="green", title="Abrir WhatsApp"),
                            href=row["whatsapp_link"], is_external=True),
                ),
                confirm_delete_button(ClientesState.excluir(row["id"]),
                                      item_label=f"o cliente “{row['nome_cliente']}”"),
                gap="0.5rem",
                flex_wrap="wrap",
            )
        ),
    )


def formulario_cliente() -> rx.Component:
    return dialogo(
        ClientesState.dialogo_aberto,
        ClientesState.fechar_dialogo,
        rx.cond(ClientesState.form_id, "Editar cliente", "Novo cliente"),
        linha(
            campo("Nome *", entrada(ClientesState.nome_cliente, ClientesState.set_nome_cliente,
                                    "Nome completo ou razão social"), largura_min="260px"),
            campo("CPF ou CNPJ *", entrada(ClientesState.cpf_cnpj, ClientesState.set_cpf_cnpj,
                                           "000.000.000-00")),
        ),
        linha(
            campo("Telefone", entrada(ClientesState.telefone, ClientesState.set_telefone, "(11) 99999-9999")),
            rx.cond(ClientesState.tem_whatsapp,
                    campo("WhatsApp", entrada(ClientesState.whatsapp, ClientesState.set_whatsapp,
                                              "(11) 99999-9999"))),
            campo("E-mail", entrada(ClientesState.email, ClientesState.set_email, "cliente@email.com",
                                    tipo="email")),
        ),
        linha(
            campo("Endereço", entrada(ClientesState.endereco, ClientesState.set_endereco,
                                      "Rua, número - bairro"), largura_min="260px"),
            rx.cond(ClientesState.tem_cidade,
                    campo("Cidade", entrada(ClientesState.cidade, ClientesState.set_cidade))),
        ),
        rx.cond(ClientesState.tem_status,
                campo("Status", selecao(ClientesState.opcoes_status, ClientesState.status,
                                        ClientesState.set_status))),
        rx.cond(ClientesState.tem_observacoes,
                campo("Observações", rx.text_area(value=ClientesState.observacoes,
                                                  on_change=ClientesState.set_observacoes, width="100%",
                                                  rows="3"))),
        rx.cond(ClientesState.campos_extras_pendentes,
                rx.callout("WhatsApp, cidade, status, observações e data de cadastro aparecem aqui depois que "
                           "os campos forem criados no Xano (ver Configuração do sistema).",
                           icon="plug-zap", color_scheme="orange", size="1", width="100%")),
        mensagem_erro(ClientesState.erro_form),
        rx.hstack(
            rx.button("Cancelar", variant="soft", color_scheme="gray", on_click=ClientesState.fechar_dialogo),
            rx.button(rx.icon("check", size=16), "Salvar", on_click=ClientesState.salvar),
            spacing="3",
            justify="end",
            width="100%",
        ),
    )


def _filtros() -> rx.Component:
    return linha(
        campo("Pesquisar", rx.input(rx.input.slot(rx.icon("search", size=16)),
                                    placeholder="Nome, CPF/CNPJ, telefone, e-mail ou cidade",
                                    value=ClientesState.busca, on_change=ClientesState.definir_busca,
                                    width="100%"), largura_min="260px"),
        rx.cond(ClientesState.tem_status,
                campo("Status", selecao(ClientesState.filtros_status, ClientesState.filtro_status,
                                        ClientesState.definir_filtro_status), largura_min="150px")),
        rx.cond(ClientesState.tem_cidade,
                campo("Cidade", selecao(ClientesState.cidades, ClientesState.filtro_cidade,
                                        ClientesState.definir_filtro_cidade), largura_min="150px")),
        campo("Ordenar por", selecao(ClientesState.ordens, ClientesState.ordem, ClientesState.definir_ordem),
              largura_min="150px"),
        rx.button(rx.icon("eraser", size=14), "Limpar", variant="soft", color_scheme="gray",
                  on_click=ClientesState.limpar_filtros),
    )


def clientes_page() -> rx.Component:
    return page(
        rx.hstack(
            rx.spacer(),
            rx.button(rx.icon("user-plus", size=16), "Novo cliente", on_click=ClientesState.abrir_novo),
            width="100%",
        ),
        rx.cond(ClientesState.campos_extras_pendentes,
                aviso_ativacao("Ficha completa do cliente aguardando o Xano",
                               "WhatsApp, cidade, status, observações e data de cadastro já estão prontos "
                               "no sistema e aparecem assim que os campos forem criados na tabela clientes.")),
        _filtros(),
        rx.cond(
            ClientesState.total > 0,
            rx.vstack(
                tabela(
                    ["Cliente", "Contato",
                     rx.cond(ClientesState.tem_cidade, rx.table.column_header_cell("Cidade")),
                     rx.cond(ClientesState.tem_status, rx.table.column_header_cell("Status")),
                     "Histórico", "Ações"],
                    rx.foreach(ClientesState.clientes, _linha),
                ),
                paginacao(ClientesState.pagina, ClientesState.total_paginas, ClientesState.total,
                          ClientesState.pagina_anterior, ClientesState.proxima_pagina),
                width="100%",
                spacing="3",
            ),
            vazio("Nenhum cliente encontrado com esses filtros."),
        ),
        formulario_cliente(),
        title="Clientes",
        subtitle="Cadastro de clientes da loja e da oficina. Clique no nome para ver a ficha completa.",
    )

import reflex as rx

from ..components.confirm_dialog import confirm_delete_button
from ..components.layout import page
from ..components.ui import (aviso_ativacao, campo, dialogo, entrada, linha, mensagem_erro, selecao, tabela,
                             vazio)
from ..state.leads_state import LeadsState as L


def _etapa_funil(item: dict) -> rx.Component:
    return rx.button(
        rx.text(item["status"], size="1"),
        rx.badge(item["qtd"], color_scheme=item["cor"].to(str), variant="solid"),
        variant=rx.cond(L.filtro_status == item["status"], "solid", "soft"),
        color_scheme="gray",
        size="2",
        on_click=L.definir_filtro_status(item["status"].to(str)),
    )


def _status(row: dict) -> rx.Component:
    return rx.select(
        L.opcoes_status,
        value=row["status"],
        on_change=lambda valor: L.mudar_status(row["id"], valor),
        size="1",
        variant="soft",
    )


def _linha(row: dict) -> rx.Component:
    return rx.table.row(
        rx.table.cell(
            rx.vstack(
                rx.link(row["nome"], on_click=L.visualizar(row["id"]), cursor="pointer", weight="medium"),
                rx.text(row["data"], " · ", rx.cond(row["origem"] != "", row["origem"], "origem —"), size="1",
                        color=rx.color("gray", 10)),
                spacing="0",
                align="start",
            )
        ),
        rx.table.cell(
            rx.vstack(
                rx.text(rx.cond(row["telefone"] != "", row["telefone"], row["telegram"]), size="2"),
                rx.cond(row["email"] != "", rx.text(row["email"], size="1", color=rx.color("gray", 10))),
                spacing="0",
                align="start",
            )
        ),
        rx.table.cell(rx.vstack(rx.text(row["interesse"], size="2"),
                                rx.cond(row["moto"] != "", rx.text("🏍 ", row["moto"], size="1",
                                                                   color=rx.color("gray", 10))),
                                spacing="0", align="start")),
        rx.table.cell(rx.cond(row["status"] == "Convertido",
                              rx.link(rx.badge("Convertido", color_scheme="green", variant="soft"),
                                      href=f"/clientes/{row['cliente_id']}"),
                              _status(row))),
        rx.table.cell(
            rx.flex(
                rx.button(rx.icon("eye", size=14), "Abrir", size="1", variant="soft", color_scheme="gray",
                          on_click=L.visualizar(row["id"])),
                rx.cond(row["telegram_link"] != "",
                        rx.link(rx.button(rx.icon("send", size=14), size="1", variant="soft",
                                          color_scheme="sky", title="Telegram"),
                                href=row["telegram_link"], is_external=True)),
                gap="0.5rem",
                flex_wrap="wrap",
            )
        ),
    )


def _formulario() -> rx.Component:
    return dialogo(
        L.dialogo_aberto,
        L.fechar_dialogo,
        rx.cond(L.form_id, "Editar lead", "Novo lead"),
        campo("Nome *", entrada(L.nome, L.set_nome)),
        linha(
            campo("Telefone", entrada(L.telefone, L.set_telefone, "(11) 99999-9999")),
            campo("Telegram", entrada(L.telegram, L.set_telegram, "@usuario ou (11) 99999-9999")),
            campo("E-mail", entrada(L.email, L.set_email, tipo="email")),
        ),
        linha(
            campo("Origem", selecao(L.origens, L.origem, L.set_origem)),
            campo("Interesse", selecao(L.interesses, L.interesse, L.set_interesse)),
            campo("Status", selecao(L.opcoes_status, L.status, L.set_status)),
        ),
        linha(
            campo("Moto da loja de interesse", selecao(L.motos_opcoes, L.moto_id, L.set_moto_id)),
            campo("Ou descreva a moto", entrada(L.moto_interesse, L.set_moto_interesse, "Ex.: Street Glide 2022")),
        ),
        campo("Observação", rx.text_area(value=L.observacao, on_change=L.set_observacao, width="100%", rows="3")),
        mensagem_erro(L.erro_form),
        rx.hstack(
            rx.button("Cancelar", variant="soft", color_scheme="gray", on_click=L.fechar_dialogo),
            rx.button(rx.icon("check", size=16), "Salvar", on_click=L.salvar),
            spacing="3", justify="end", width="100%",
        ),
    )


def _interacao(i: dict) -> rx.Component:
    return rx.vstack(
        rx.text(rx.text.strong(i["tipo"]), " · ", i["data"], size="2"),
        rx.text(i["descricao"], size="2", color=rx.color("gray", 11), white_space="pre-wrap"),
        spacing="0", align="start", width="100%",
        padding_bottom="0.5rem", border_bottom=f"1px solid {rx.color('gray', 4)}",
    )


def _dado(rotulo: str, valor) -> rx.Component:
    return rx.vstack(rx.text(rotulo, size="1", color=rx.color("gray", 10)),
                     rx.text(rx.cond(valor != "", valor, "—"), size="2", weight="medium"),
                     spacing="0", align="start", flex="1 1 160px")


def _ficha() -> rx.Component:
    lead = L.lead
    return dialogo(
        L.dialogo_ver,
        L.fechar_ver,
        rx.hstack(rx.text(lead["nome"]), rx.badge(lead["status"], color_scheme=lead["status_cor"].to(str),
                                                  variant="soft"), spacing="2", align="center"),
        rx.flex(
            _dado("Telefone", lead["telefone"]),
            _dado("Telegram", lead["telegram"]),
            _dado("E-mail", lead["email"]),
            _dado("Origem", lead["origem"]),
            _dado("Interesse", lead["interesse"]),
            _dado("Moto", lead["moto"]),
            _dado("Cadastrado em", lead["data"]),
            gap="0.75rem", flex_wrap="wrap", width="100%",
        ),
        rx.cond(lead["observacao"] != "", rx.text(lead["observacao"], size="2", white_space="pre-wrap")),
        rx.flex(
            rx.cond(
                lead["status"] == "Convertido",
                rx.link(rx.button(rx.icon("user", size=14), "Abrir ficha do cliente", color_scheme="green"),
                        href=f"/clientes/{lead['cliente_id']}", underline="none"),
                rx.button(rx.icon("user-check", size=14), "Converter em cliente", color_scheme="green",
                          on_click=L.abrir_converter),
            ),
            rx.button(rx.icon("pencil", size=14), "Editar", variant="soft", on_click=L.abrir_editar(lead["id"].to(str))),
            rx.cond(lead["telegram_link"] != "",
                    rx.link(rx.button(rx.icon("send", size=14), "Telegram", variant="soft",
                                      color_scheme="sky"), href=lead["telegram_link"].to(str), is_external=True)),
            rx.button(rx.icon("mail", size=14), "E-mail", variant="soft", color_scheme="gray", on_click=L.abrir_email),
            confirm_delete_button(L.excluir(lead["id"].to(str)), item_label="este lead"),
            gap="0.5rem", flex_wrap="wrap",
        ),
        rx.divider(),
        rx.heading("Interações", size="3"),
        rx.cond(
            L.tem_interacoes,
            rx.vstack(
                linha(
                    campo("Tipo", selecao(L.tipos_interacao, L.int_tipo, L.set_int_tipo), largura_min="160px"),
                    campo("O que aconteceu", entrada(L.int_descricao, L.set_int_descricao,
                                                     "Ex.: ligou pedindo condições de financiamento"),
                          largura_min="240px"),
                    rx.button(rx.icon("plus", size=14), "Registrar", on_click=L.salvar_interacao),
                ),
                mensagem_erro(L.erro_int),
                rx.cond(L.interacoes.length() > 0,
                        rx.vstack(rx.foreach(L.interacoes, _interacao), spacing="2", width="100%"),
                        vazio("Nenhuma interação registrada.")),
                spacing="2", width="100%",
            ),
            aviso_ativacao("Interações aguardando o Xano", "Crie a tabela interacoes para registrar o histórico."),
        ),
        rx.cond(L.emails.length() > 0,
                rx.vstack(rx.heading("E-mails", size="3"),
                          tabela(["Data", "Assunto", "Situação"],
                                 rx.foreach(L.emails, lambda e: rx.table.row(rx.table.cell(e["data"]),
                                                                             rx.table.cell(e["assunto"]),
                                                                             rx.table.cell(e["status"])))),
                          spacing="2", width="100%")),
        largura="760px",
    )


def _converter() -> rx.Component:
    return dialogo(
        L.dialogo_converter,
        L.fechar_converter,
        "Converter lead em cliente",
        rx.text("Os dados do lead (nome, telefone, Telegram, e-mail e observação) vão para o cadastro do cliente. "
                "Se já existir um cliente com o mesmo CPF/CNPJ, o lead é só ligado a ele — nada é duplicado.",
                size="2"),
        campo("CPF ou CNPJ do cliente *", entrada(L.conv_documento, L.set_conv_documento, "000.000.000-00")),
        mensagem_erro(L.erro_conv),
        rx.hstack(
            rx.button("Cancelar", variant="soft", color_scheme="gray", on_click=L.fechar_converter),
            rx.button(rx.icon("user-check", size=16), "Converter", color_scheme="green", on_click=L.converter),
            spacing="3", justify="end", width="100%",
        ),
        largura="480px",
    )


def _email() -> rx.Component:
    return dialogo(
        L.dialogo_email,
        L.fechar_email,
        "Enviar e-mail",
        rx.text("Para: ", rx.text.strong(L.lead["email"]), size="2"),
        rx.cond(~L.sendgrid_ok,
                rx.callout("O SendGrid ainda não está configurado: a tentativa fica registrada, mas não é enviada.",
                           icon="triangle-alert", color_scheme="orange", size="1", width="100%")),
        campo("Assunto", entrada(L.email_assunto, L.set_email_assunto)),
        campo("Mensagem", rx.text_area(value=L.email_mensagem, on_change=L.set_email_mensagem, width="100%",
                                       rows="8")),
        mensagem_erro(L.erro_email),
        rx.hstack(
            rx.button("Cancelar", variant="soft", color_scheme="gray", on_click=L.fechar_email),
            rx.button(rx.icon("send", size=16), "Enviar", on_click=L.enviar_email),
            spacing="3", justify="end", width="100%",
        ),
        largura="560px",
    )


def leads_page() -> rx.Component:
    return page(
        rx.cond(
            L.tabela_existe,
            rx.vstack(
                rx.flex(
                    rx.flex(rx.foreach(L.funil, _etapa_funil), gap="0.5rem", flex_wrap="wrap"),
                    rx.spacer(),
                    rx.button(rx.icon("user-plus", size=16), "Novo lead", on_click=L.abrir_novo),
                    gap="0.75rem", flex_wrap="wrap", width="100%", align="center",
                ),
                linha(
                    campo("Pesquisar", rx.input(rx.input.slot(rx.icon("search", size=16)),
                                                placeholder="Nome, telefone, e-mail, interesse ou moto",
                                                value=L.busca, on_change=L.definir_busca, width="100%"),
                          largura_min="240px"),
                    campo("Status", selecao(L.filtros_status, L.filtro_status, L.definir_filtro_status),
                          largura_min="160px"),
                    campo("Origem", selecao(L.filtros_origem, L.filtro_origem, L.definir_filtro_origem),
                          largura_min="160px"),
                ),
                rx.cond(L.leads.length() > 0,
                        tabela(["Lead", "Contato", "Interesse", "Status", "Ações"], rx.foreach(L.leads, _linha)),
                        vazio("Nenhum lead com esses filtros.")),
                spacing="3", width="100%",
            ),
            rx.vstack(
                aviso_ativacao("Controle de leads aguardando o Xano",
                               "A tela de leads (funil de atendimento, interações e conversão em cliente) está "
                               "pronta e funciona assim que a tabela leads for criada no Xano. Os leads que o "
                               "bot do Telegram coleta hoje ficam na tabela leads_telegram do n8n."),
                spacing="3", width="100%",
            ),
        ),
        _formulario(),
        _ficha(),
        _converter(),
        _email(),
        title="Leads",
        subtitle="Pessoas interessadas que ainda não são clientes: acompanhe o atendimento e converta em cliente.",
    )

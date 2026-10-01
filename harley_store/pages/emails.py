import reflex as rx

from ..components.layout import page
from ..components.ui import aviso_ativacao, campo, linha, selecao, tabela, vazio
from ..state.emails_state import EmailsState as E


def _linha(e: dict) -> rx.Component:
    return rx.table.row(
        rx.table.cell(rx.text(e["data"], white_space="nowrap")),
        rx.table.cell(e["destinatario"]),
        rx.table.cell(e["assunto"]),
        rx.table.cell(
            rx.cond(e["cliente_nome"] != "",
                    rx.link(e["cliente_nome"], href=f"/clientes/{e['cliente_id']}"),
                    rx.cond(e["lead_nome"] != "", rx.text("Lead: ", e["lead_nome"]), rx.text("—")))
        ),
        rx.table.cell(rx.badge(e["status"], color_scheme=rx.cond(e["status"] == "Enviado", "green",
                                                                 rx.cond(e["status"] == "Falhou", "red", "amber")),
                               variant="soft")),
        rx.table.cell(rx.text(e["erro"], size="1", color=rx.color("gray", 10))),
    )


def emails_page() -> rx.Component:
    return page(
        rx.cond(
            E.sendgrid_ok,
            rx.callout("SendGrid configurado. Os e-mails são enviados só quando alguém clica em “Enviar e-mail” "
                       "na ficha de um cliente ou lead — nada é enviado sozinho.", icon="circle-check",
                       color_scheme="green", width="100%"),
            rx.callout("SendGrid ainda não configurado: as tentativas ficam registradas como “Não configurado”. "
                       "Veja como configurar em Configuração do sistema (administrador).", icon="triangle-alert",
                       color_scheme="orange", width="100%"),
        ),
        rx.cond(
            E.tabela_existe,
            rx.vstack(
                linha(
                    campo("Pesquisar", rx.input(rx.input.slot(rx.icon("search", size=16)),
                                                placeholder="Destinatário, assunto ou cliente",
                                                value=E.busca, on_change=E.definir_busca, width="100%"),
                          largura_min="240px"),
                    campo("Situação", selecao(E.situacoes, E.filtro_status, E.definir_filtro_status),
                          largura_min="160px"),
                ),
                rx.cond(E.emails.length() > 0,
                        tabela(["Data", "Para", "Assunto", "Cliente / lead", "Situação", "Erro"],
                               rx.foreach(E.emails, _linha)),
                        vazio("Nenhum e-mail registrado.")),
                spacing="3",
                width="100%",
            ),
            aviso_ativacao("Histórico de e-mails aguardando o Xano",
                           "Crie a tabela emails no Xano para guardar cada envio (destinatário, assunto, data, "
                           "situação e erro)."),
        ),
        title="E-mails",
        subtitle="Histórico de e-mails enviados a clientes e leads.",
    )

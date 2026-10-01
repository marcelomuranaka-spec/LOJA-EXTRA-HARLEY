import reflex as rx

from ..components.confirm_dialog import confirm_delete_button
from ..components.foto import miniatura
from ..components.layout import page
from ..components.moto_cliente import dialogo_moto, dialogo_ver_moto
from ..components.ui import aviso_ativacao, campo, linha, tabela, vazio
from ..state.motos_state import MotosState


def _linha(row: dict) -> rx.Component:
    return rx.table.row(
        rx.table.cell(miniatura(row["foto_url"], row["foto_local"], "56px", "56px", "bike")),
        rx.table.cell(
            rx.vstack(
                rx.text(row["titulo"], weight="medium"),
                rx.text(rx.cond(row["ano"] != "", row["ano"], ""), " ", row["cor"], size="1",
                        color=rx.color("gray", 10)),
                spacing="0",
                align="start",
            )
        ),
        rx.table.cell(rx.vstack(rx.text(row["placa"]), rx.text(row["chassi"], size="1", color=rx.color("gray", 10)),
                                spacing="0", align="start")),
        rx.table.cell(rx.link(row["cliente_nome"], href=f"/clientes/{row['id_cliente']}")),
        rx.table.cell(
            rx.flex(
                rx.button(rx.icon("eye", size=14), "Visualizar", size="1", variant="soft", color_scheme="gray",
                          on_click=MotosState.visualizar(row["id"])),
                rx.button(rx.icon("pencil", size=14), "Editar", size="1", variant="soft",
                          on_click=MotosState.abrir_editar(row["id"], False)),
                confirm_delete_button(MotosState.excluir(row["id"]), item_label=f"a moto “{row['titulo']}”"),
                gap="0.5rem",
                flex_wrap="wrap",
            )
        ),
    )


def motos_page() -> rx.Component:
    return page(
        rx.hstack(
            rx.spacer(),
            rx.button(rx.icon("plus", size=16), "Nova moto de cliente", on_click=MotosState.abrir_novo),
            width="100%",
        ),
        rx.cond(~MotosState.tem_extras,
                aviso_ativacao("Ficha completa da moto aguardando o Xano",
                               "Marca, ano, cor, quilometragem, observações e data de cadastro já estão prontos "
                               "e aparecem quando os campos forem criados na tabela motos_clientes.")),
        linha(
            campo("Pesquisar", rx.input(rx.input.slot(rx.icon("search", size=16)),
                                        placeholder="Modelo, placa, chassi ou cliente",
                                        value=MotosState.busca, on_change=MotosState.definir_busca,
                                        width="100%"), largura_min="260px"),
        ),
        rx.cond(
            MotosState.motos.length() > 0,
            tabela(["Foto", "Moto", "Placa / chassi", "Cliente", "Ações"], rx.foreach(MotosState.motos, _linha)),
            vazio("Nenhuma moto encontrada."),
        ),
        dialogo_moto(),
        dialogo_ver_moto(),
        title="Motos dos clientes",
        subtitle="Motos que pertencem aos clientes (oficina). Toda moto é ligada a um cliente.",
    )

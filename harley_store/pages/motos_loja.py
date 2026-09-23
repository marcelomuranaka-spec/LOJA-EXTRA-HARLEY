import reflex as rx

from ..components.botao_imprimir import botao_imprimir
from ..components.confirm_dialog import confirm_delete_button
from ..components.layout import page
from ..components.tema import BORDA, LARANJA, PRETO_CARTAO
from ..state.motos_loja_state import MotosLojaState

# Cada status tem cor + ícone + texto (nunca só a cor).
_STATUS_VISUAL = {
    "Em estoque": ("green", "circle-check"),
    "Reservada": ("amber", "clock"),
    "Consignada": ("blue", "handshake"),
    "Vendida": ("gray", "badge-dollar-sign"),
}


def _badge_status(status: rx.Var) -> rx.Component:
    return rx.match(
        status,
        *[
            # "solid" para ficar legível por cima da foto
            (nome, rx.badge(rx.icon(icone, size=12), nome, color_scheme=cor, variant="solid", high_contrast=True))
            for nome, (cor, icone) in _STATUS_VISUAL.items()
        ],
        rx.badge(status, variant="soft"),
    )


def _foto(url: rx.Var, altura: str) -> rx.Component:
    return rx.cond(
        url != "",
        rx.image(src=url, width="100%", height=altura, object_fit="cover"),
        rx.center(
            rx.icon("bike", size=40, color=rx.color("gray", 8)),
            width="100%",
            height=altura,
            background=rx.color("gray", 3),
        ),
    )


def _cartao_moto(row: dict) -> rx.Component:
    return rx.box(
        rx.box(
            _foto(row["foto_url"], "170px"),
            rx.box(_badge_status(row["status"]), position="absolute", top="0.6rem", left="0.6rem"),
            position="relative",
        ),
        rx.vstack(
            rx.text(row["marca"], size="1", color=LARANJA, weight="bold", letter_spacing="0.08em"),
            rx.heading(row["modelo"], size="4"),
            rx.hstack(
                rx.text(row["ano"], size="2", color=rx.color("gray", 10)),
                rx.text("•", size="2", color=rx.color("gray", 8)),
                rx.text(row["cor"], size="2", color=rx.color("gray", 10)),
                rx.text("•", size="2", color=rx.color("gray", 8)),
                rx.text(row["quilometragem"], " km", size="2", color=rx.color("gray", 10)),
                spacing="2",
                wrap="wrap",
            ),
            rx.hstack(
                rx.text("Placa ", rx.code(row["placa"], variant="ghost"), size="1", color=rx.color("gray", 10)),
                rx.cond(
                    row["cliente_nome"] != "",
                    rx.text("Cliente: ", row["cliente_nome"], size="1", color=rx.color("gray", 10)),
                ),
                spacing="3",
                wrap="wrap",
            ),
            rx.heading(rx.text("R$ ", row["preco_venda"]), size="5", padding_top="0.25rem"),
            rx.hstack(
                rx.button(
                    rx.icon("pencil", size=14),
                    "Editar",
                    size="1",
                    variant="soft",
                    on_click=MotosLojaState.editar(row["id"]),
                ),
                botao_imprimir(
                    "moto", row["id"],
                    rx.cond(row["status"] == "Vendida", "Recibo", "Ficha"),
                ),
                confirm_delete_button(
                    MotosLojaState.excluir(row["id"]),
                    item_label=f"a moto “{row['modelo']}” ({row['chassi']})",
                ),
                spacing="2",
                padding_top="0.25rem",
            ),
            spacing="1",
            align="start",
            padding="0.9rem 1rem 1rem",
        ),
        background=PRETO_CARTAO,
        border=f"1px solid {BORDA}",
        border_radius="0.75rem",
        overflow="hidden",
        transition="border-color 0.15s, transform 0.15s",
        _hover={"border_color": LARANJA, "transform": "translateY(-2px)"},
    )


def _rotulado(rotulo: str, campo: rx.Component) -> rx.Component:
    return rx.vstack(
        rx.text(rotulo, size="1", weight="bold", color=rx.color("gray", 10)),
        campo,
        spacing="1",
        width="100%",
        align="start",
    )


def _input(rotulo: str, valor, on_change, placeholder: str = "", tipo: str = "text") -> rx.Component:
    return _rotulado(
        rotulo,
        rx.input(value=valor, on_change=on_change, placeholder=placeholder, type=tipo, width="100%"),
    )


def _campo_foto() -> rx.Component:
    return rx.vstack(
        rx.text("Foto da moto", size="1", weight="bold", color=rx.color("gray", 10)),
        rx.hstack(
            rx.box(_foto(MotosLojaState.foto_url, "110px"), width="160px", border_radius="0.6rem", overflow="hidden"),
            rx.vstack(
                rx.upload(
                    rx.hstack(
                        rx.cond(MotosLojaState.enviando_foto, rx.spinner(size="2"), rx.icon("upload", size=16)),
                        rx.text(rx.cond(MotosLojaState.enviando_foto, "Enviando...", "Selecionar foto")),
                        spacing="2",
                        align="center",
                    ),
                    id="upload_foto_moto_loja",
                    accept={"image/png": [".png"], "image/jpeg": [".jpg", ".jpeg"], "image/webp": [".webp"]},
                    max_files=1,
                    multiple=False,
                    on_drop=MotosLojaState.handle_upload_foto(rx.upload_files(upload_id="upload_foto_moto_loja")),
                    border=f"1px dashed {rx.color('gray', 7)}",
                    border_radius="0.5rem",
                    padding="0.6rem 0.9rem",
                    cursor="pointer",
                ),
                rx.cond(
                    MotosLojaState.foto_url != "",
                    rx.button(
                        "Remover foto",
                        size="1",
                        variant="ghost",
                        color_scheme="gray",
                        on_click=MotosLojaState.remover_foto,
                    ),
                ),
                spacing="2",
                align="start",
            ),
            spacing="4",
            align="center",
            wrap="wrap",
        ),
        rx.cond(
            MotosLojaState.erro_foto != "",
            rx.callout(MotosLojaState.erro_foto, icon="info", color_scheme="amber", size="1"),
        ),
        spacing="2",
        align="start",
        width="100%",
    )


def _formulario() -> rx.Component:
    return rx.card(
        rx.vstack(
            rx.heading(rx.cond(MotosLojaState.form_id, "Editar moto", "Nova moto no estoque"), size="4"),
            rx.grid(
                _input("Marca *", MotosLojaState.marca, MotosLojaState.set_marca),
                _input("Modelo *", MotosLojaState.modelo, MotosLojaState.set_modelo, "ex.: Fat Boy 114"),
                _input("Ano", MotosLojaState.ano, MotosLojaState.set_ano, "2026", "number"),
                _input("Cor", MotosLojaState.cor, MotosLojaState.set_cor, "Vivid Black"),
                _input("Placa", MotosLojaState.placa, MotosLojaState.set_placa, "ABC1D23"),
                _input("Chassi *", MotosLojaState.chassi, MotosLojaState.set_chassi),
                _input("Quilometragem", MotosLojaState.quilometragem, MotosLojaState.set_quilometragem, "0", "number"),
                _rotulado(
                    "Status",
                    rx.select(
                        MotosLojaState.status_opcoes,
                        value=MotosLojaState.status,
                        on_change=MotosLojaState.set_status,
                        width="100%",
                    ),
                ),
                _input("Preço de compra (R$)", MotosLojaState.preco_compra, MotosLojaState.set_preco_compra, "135.000,00"),
                _input("Preço de venda (R$)", MotosLojaState.preco_venda, MotosLojaState.set_preco_venda, "150.000,00"),
                _input("Data de entrada", MotosLojaState.data_entrada, MotosLojaState.set_data_entrada, tipo="date"),
                _input("Data de saída", MotosLojaState.data_saida, MotosLojaState.set_data_saida, tipo="date"),
                columns=rx.breakpoints(initial="1", sm="2", md="4"),
                spacing="3",
                width="100%",
            ),
            _rotulado(
                "Cliente (comprador / reserva)",
                rx.select(
                    MotosLojaState.clientes_opcoes,
                    value=MotosLojaState.cliente_selecionado,
                    on_change=MotosLojaState.set_cliente_selecionado,
                    width="100%",
                ),
            ),
            _rotulado(
                "Observações",
                rx.text_area(
                    value=MotosLojaState.observacoes,
                    on_change=MotosLojaState.set_observacoes,
                    placeholder="Brindes, revisões feitas, acessórios...",
                    width="100%",
                    rows="2",
                ),
            ),
            _campo_foto(),
            rx.hstack(
                rx.button(
                    rx.icon("check", size=16),
                    "Salvar",
                    on_click=MotosLojaState.salvar,
                    disabled=MotosLojaState.enviando_foto,
                ),
                rx.button(
                    rx.icon("x", size=16),
                    "Cancelar",
                    variant="soft",
                    color_scheme="gray",
                    on_click=MotosLojaState.novo,
                ),
                spacing="3",
            ),
            spacing="3",
            align="start",
            width="100%",
        ),
        id="form-moto-loja",
        width="100%",
    )


def motos_loja_page() -> rx.Component:
    return page(
        _formulario(),
        rx.hstack(
            rx.input(
                rx.input.slot(rx.icon("search", size=16)),
                placeholder="Buscar por modelo, placa ou chassi...",
                value=MotosLojaState.busca,
                on_change=MotosLojaState.definir_busca,
                width="320px",
                max_width="100%",
            ),
            rx.segmented_control.root(
                rx.foreach(
                    MotosLojaState.filtros_status,
                    lambda s: rx.segmented_control.item(s, value=s),
                ),
                value=MotosLojaState.filtro_status,
                on_change=MotosLojaState.definir_filtro_status,
            ),
            spacing="3",
            wrap="wrap",
            width="100%",
        ),
        rx.cond(
            MotosLojaState.motos.length() == 0,
            rx.center(
                rx.text("Nenhuma moto encontrada.", color=rx.color("gray", 10)),
                width="100%",
                padding="2rem",
            ),
            rx.grid(
                rx.foreach(MotosLojaState.motos, _cartao_moto),
                columns=rx.breakpoints(initial="1", sm="2", lg="3"),
                spacing="4",
                width="100%",
            ),
        ),
        title="Motos da loja",
        subtitle="Estoque de motos à venda — cadastro sincronizado com a tabela motos do Xano.",
    )

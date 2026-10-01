import reflex as rx

from ..components.botao_imprimir import botao_imprimir
from ..components.confirm_dialog import confirm_delete_button
from ..components.foto import ACEITOS
from ..components.layout import page
from ..components.tema import BORDA, LARANJA, PRETO_CARTAO
from ..components.ui import campo, cartao_indicador, dialogo, entrada, linha, mensagem_erro, selecao, vazio
from ..state.motos_loja_state import MotosLojaState as M

# Cada situação tem cor + ícone + texto (nunca só a cor).
_ICONES = {"Disponível": "circle-check", "Reservada": "clock", "Consignada": "handshake",
           "Em manutenção": "wrench", "Fora de estoque": "circle-slash", "Vendida": "badge-dollar-sign"}
_CORES = {"Disponível": "green", "Reservada": "amber", "Consignada": "blue", "Em manutenção": "purple",
          "Fora de estoque": "gray", "Vendida": "red"}


def _badge_status(rotulo: rx.Var) -> rx.Component:
    return rx.match(
        rotulo,
        *[
            # "solid" para ficar legível por cima da foto
            (nome, rx.badge(rx.icon(icone, size=12), nome, color_scheme=_CORES[nome], variant="solid",
                            high_contrast=True))
            for nome, icone in _ICONES.items()
        ],
        rx.badge(rotulo, variant="soft"),
    )


def _foto(url: rx.Var, altura: str) -> rx.Component:
    return rx.cond(
        url != "",
        rx.image(src=url, width="100%", height=altura, object_fit="cover"),
        rx.center(rx.icon("bike", size=40, color=rx.color("gray", 8)), width="100%", height=altura,
                  background=rx.color("gray", 3)),
    )


def _cartao_moto(row: dict) -> rx.Component:
    return rx.box(
        rx.box(
            rx.box(_foto(row["foto_url"], "170px"), on_click=M.visualizar(row["id"]), cursor="pointer"),
            rx.box(_badge_status(row["status_rotulo"]), position="absolute", top="0.6rem", left="0.6rem"),
            rx.cond(row["qtd_fotos"].to(int) > 1,
                    rx.badge(rx.icon("images", size=12), row["qtd_fotos"], variant="solid", color_scheme="gray",
                             position="absolute", top="0.6rem", right="0.6rem")),
            position="relative",
        ),
        rx.vstack(
            rx.text(row["marca"], size="1", color=LARANJA, weight="bold", letter_spacing="0.08em"),
            rx.heading(row["modelo"], size="4"),
            rx.hstack(
                rx.text(rx.cond(row["ano"] != "", row["ano"], "ano —"), size="2", color=rx.color("gray", 10)),
                rx.text("•", size="2", color=rx.color("gray", 8)),
                rx.text(rx.cond(row["cor"] != "", row["cor"], "cor —"), size="2", color=rx.color("gray", 10)),
                rx.text("•", size="2", color=rx.color("gray", 8)),
                rx.text(row["quilometragem"], " km", size="2", color=rx.color("gray", 10)),
                spacing="2",
                wrap="wrap",
            ),
            rx.hstack(
                rx.text("Placa ", rx.code(rx.cond(row["placa"] != "", row["placa"], "—"), variant="ghost"),
                        size="1", color=rx.color("gray", 10)),
                rx.cond(row["cliente_nome"] != "",
                        rx.text("Cliente: ", row["cliente_nome"], size="1", color=rx.color("gray", 10))),
                spacing="3",
                wrap="wrap",
            ),
            rx.heading("R$ ", row["preco_venda"], size="5", padding_top="0.25rem"),
            rx.flex(
                rx.button(rx.icon("eye", size=14), "Ver", size="1", variant="soft", color_scheme="gray",
                          on_click=M.visualizar(row["id"])),
                rx.button(rx.icon("pencil", size=14), "Editar", size="1", variant="soft",
                          on_click=M.editar(row["id"])),
                botao_imprimir("moto", row["id"], rx.cond(row["status"] == "Vendida", "Recibo", "Ficha")),
                confirm_delete_button(M.excluir(row["id"]),
                                      item_label=f"a moto “{row['modelo']}” ({row['chassi']})"),
                gap="0.5rem",
                flex_wrap="wrap",
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


def _campo_foto() -> rx.Component:
    return rx.vstack(
        rx.text("Foto principal", size="2", weight="medium", color=rx.color("gray", 11)),
        rx.hstack(
            rx.box(_foto(M.foto_url, "110px"), width="160px", border_radius="0.6rem", overflow="hidden"),
            rx.vstack(
                rx.upload(
                    rx.hstack(
                        rx.cond(M.enviando_foto, rx.spinner(size="2"), rx.icon("upload", size=16)),
                        rx.text(rx.cond(M.enviando_foto, "Enviando...", "Escolher ou trocar foto")),
                        spacing="2",
                        align="center",
                    ),
                    id="upload_foto_moto_loja",
                    accept=ACEITOS,
                    max_files=1,
                    multiple=False,
                    on_drop=M.handle_upload_foto(rx.upload_files(upload_id="upload_foto_moto_loja")),
                    border=f"1px dashed {rx.color('gray', 7)}",
                    border_radius="0.5rem",
                    padding="0.6rem 0.9rem",
                    cursor="pointer",
                ),
                rx.text("PNG, JPG ou WEBP, até 5 MB. Fotos adicionais: botão Ver.", size="1",
                        color=rx.color("gray", 9)),
                rx.cond(M.foto_url != "",
                        rx.button("Remover foto", size="1", variant="ghost", color_scheme="gray",
                                  on_click=M.remover_foto)),
                spacing="2",
                align="start",
            ),
            spacing="4",
            align="center",
            wrap="wrap",
        ),
        rx.cond(M.erro_foto != "", rx.callout(M.erro_foto, icon="info", color_scheme="amber", size="1")),
        spacing="2",
        align="start",
        width="100%",
    )


def _formulario() -> rx.Component:
    return dialogo(
        M.dialogo_aberto,
        M.fechar_dialogo,
        rx.cond(M.form_id, "Editar moto", "Nova moto no estoque"),
        linha(
            campo("Marca *", entrada(M.marca, M.set_marca)),
            campo("Modelo *", entrada(M.modelo, M.set_modelo, "ex.: Fat Boy 114")),
        ),
        linha(
            campo("Ano", entrada(M.ano, M.set_ano, "2026"), largura_min="100px"),
            campo("Cor", entrada(M.cor, M.set_cor, "Vivid Black"), largura_min="140px"),
            campo("Quilometragem", entrada(M.quilometragem, M.set_quilometragem, "0"), largura_min="120px"),
        ),
        linha(
            campo("Placa", entrada(M.placa, M.set_placa, "ABC1D23"), largura_min="130px"),
            campo("Chassi *", entrada(M.chassi, M.set_chassi), largura_min="220px"),
        ),
        linha(
            campo("Situação", selecao(M.status_opcoes, M.status, M.set_status), largura_min="160px"),
            campo("Preço de compra (R$)", entrada(M.preco_compra, M.set_preco_compra, "135.000,00")),
            campo("Preço de venda (R$)", entrada(M.preco_venda, M.set_preco_venda, "150.000,00")),
        ),
        linha(
            campo("Data de entrada", entrada(M.data_entrada, M.set_data_entrada, tipo="date")),
            campo("Data de saída", entrada(M.data_saida, M.set_data_saida, tipo="date")),
        ),
        campo("Cliente (comprador / reserva)", selecao(M.clientes_opcoes, M.cliente_selecionado,
                                                       M.set_cliente_selecionado)),
        campo("Observações", rx.text_area(value=M.observacoes, on_change=M.set_observacoes,
                                          placeholder="Brindes, revisões feitas, acessórios...", width="100%",
                                          rows="2")),
        _campo_foto(),
        rx.text("Dica: para vender, use Vendas / Balcão → Moto da loja. A moto passa a Vendida sozinha.",
                size="1", color=rx.color("gray", 10)),
        mensagem_erro(M.erro_form),
        rx.hstack(
            rx.button("Cancelar", variant="soft", color_scheme="gray", on_click=M.fechar_dialogo),
            rx.button(rx.icon("check", size=16), "Salvar", on_click=M.salvar, disabled=M.enviando_foto),
            spacing="3",
            justify="end",
            width="100%",
        ),
        largura="720px",
    )


def _dado(rotulo: str, valor) -> rx.Component:
    return rx.vstack(
        rx.text(rotulo, size="1", color=rx.color("gray", 10)),
        rx.text(rx.cond(valor != "", valor, "—"), size="2", weight="medium"),
        spacing="0", align="start", flex="1 1 140px",
    )


def _foto_galeria(url: rx.Var) -> rx.Component:
    return rx.box(
        rx.link(rx.image(src=url, width="100%", height="140px", object_fit="cover", border_radius="0.5rem"),
                href=url, is_external=True),
        rx.cond(url != M.moto_vista["foto_url"].to(str),
                rx.icon_button(rx.icon("x", size=12), size="1", color_scheme="red", variant="solid",
                               position="absolute", top="0.3rem", right="0.3rem",
                               on_click=M.remover_foto_adicional(url), title="Remover foto adicional")),
        position="relative",
    )


def _visualizar() -> rx.Component:
    m = M.moto_vista
    return dialogo(
        M.dialogo_ver,
        M.fechar_ver,
        rx.text(m["marca"], " ", m["modelo"]),
        rx.cond(
            M.fotos_vista.length() > 0,
            rx.grid(rx.foreach(M.fotos_vista, _foto_galeria), columns=rx.breakpoints(initial="2", sm="3"),
                    spacing="2", width="100%"),
            vazio("Sem fotos."),
        ),
        rx.upload(
            rx.hstack(rx.cond(M.enviando_foto, rx.spinner(size="2"), rx.icon("image-plus", size=16)),
                      rx.text("Adicionar fotos (até 6 por vez)", size="2"), spacing="2", align="center"),
            id="upload_fotos_adicionais",
            accept=ACEITOS,
            max_files=6,
            multiple=True,
            on_drop=M.adicionar_fotos(rx.upload_files(upload_id="upload_fotos_adicionais")),
            border=f"1px dashed {rx.color('gray', 7)}",
            border_radius="0.5rem",
            padding="0.5rem 0.9rem",
            cursor="pointer",
        ),
        rx.cond(M.erro_fotos != "", rx.callout(M.erro_fotos, icon="info", color_scheme="amber", size="1")),
        rx.flex(
            _dado("Situação", m["status_rotulo"]),
            _dado("Ano", m["ano"]),
            _dado("Cor", m["cor"]),
            _dado("Km", m["quilometragem"]),
            _dado("Placa", m["placa"]),
            _dado("Chassi", m["chassi"]),
            _dado("Preço de venda", m["preco_venda"]),
            _dado("Entrada", m["data_entrada"]),
            _dado("Saída", m["data_saida"]),
            _dado("Cliente", m["cliente_nome"]),
            gap="0.75rem",
            flex_wrap="wrap",
            width="100%",
        ),
        rx.cond(m["observacoes"] != "", rx.text(m["observacoes"], size="2", white_space="pre-wrap")),
        rx.hstack(
            rx.button(rx.icon("pencil", size=14), "Editar", on_click=M.editar(m["id"].to(str))),
            spacing="3",
            justify="end",
            width="100%",
        ),
        largura="720px",
    )


def _filtros() -> rx.Component:
    return rx.vstack(
        linha(
            campo("Pesquisar", rx.input(rx.input.slot(rx.icon("search", size=16)),
                                        placeholder="Marca, modelo, placa, chassi ou cor",
                                        value=M.busca, on_change=M.definir_busca, width="100%"),
                  largura_min="240px"),
            campo("Situação", selecao(M.filtros_status, M.filtro_status, M.definir_filtro_status),
                  largura_min="150px"),
            campo("Marca", selecao(M.marcas, M.filtro_marca, M.definir_filtro_marca), largura_min="150px"),
        ),
        linha(
            campo("Ano de", rx.input(value=M.ano_min, on_change=M.definir_ano_min, placeholder="2015",
                                     width="100%"), largura_min="90px"),
            campo("até", rx.input(value=M.ano_max, on_change=M.definir_ano_max, placeholder="2026",
                                  width="100%"), largura_min="90px"),
            campo("Preço de (R$)", rx.input(value=M.preco_min, on_change=M.definir_preco_min, placeholder="0",
                                            width="100%"), largura_min="120px"),
            campo("até (R$)", rx.input(value=M.preco_max, on_change=M.definir_preco_max,
                                       placeholder="200.000", width="100%"), largura_min="120px"),
            campo("Ordenar", selecao(M.ordens, M.ordem, M.definir_ordem), largura_min="150px"),
            rx.button(rx.icon("eraser", size=14), "Limpar", variant="soft", color_scheme="gray",
                      on_click=M.limpar_filtros),
        ),
        spacing="2",
        width="100%",
    )


def motos_loja_page() -> rx.Component:
    return page(
        rx.grid(
            cartao_indicador("Disponíveis", M.resumo["disponiveis"], "bike"),
            cartao_indicador("Valor à venda", rx.text("R$ ", M.resumo["valor"]), "wallet"),
            cartao_indicador("Vendidas", M.resumo["vendidas"], "badge-dollar-sign"),
            columns=rx.breakpoints(initial="1", sm="3"),
            spacing="3",
            width="100%",
        ),
        rx.hstack(
            rx.spacer(),
            rx.button(rx.icon("plus", size=16), "Nova moto", on_click=M.abrir_novo),
            width="100%",
        ),
        _filtros(),
        rx.cond(
            M.motos.length() == 0,
            vazio("Nenhuma moto encontrada com esses filtros."),
            rx.grid(
                rx.foreach(M.motos, _cartao_moto),
                columns=rx.breakpoints(initial="1", sm="2", lg="3"),
                spacing="4",
                width="100%",
            ),
        ),
        _formulario(),
        _visualizar(),
        title="Motos da loja",
        subtitle="Estoque de motos à venda, com fotos. Clique na foto para ver detalhes e fotos adicionais.",
    )

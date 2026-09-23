"""State de Ordens de Serviço (OrdemServico + ItemOrdemServico). Dados vêm do backend Xano."""

import reflex as rx

from .. import xano_client as xano

TABELA_OS = "ordens_servico"
TABELA_ITENS = "itens_ordem_servico"
TABELA_MOTOS = "motos_clientes"
TABELA_FUNCIONARIOS = "funcionarios"
TABELA_PRODUTOS = "produtos"


class OrdensServicoState(rx.State):
    ordens: list[dict] = []

    motos_opcoes: list[str] = []
    mecanicos_opcoes: list[str] = []
    produtos_opcoes: list[str] = []

    moto_selecionada: str = ""
    mecanico_selecionado: str = ""
    itens_atual: list[dict] = []  # [{produto_id, produto_nome, quantidade, valor_total_item}]

    item_produto_selecionado: str = ""
    item_quantidade: str = "1"
    item_valor_total: str = "0.00"

    @rx.var
    def total_atual(self) -> str:
        total = sum(float(item["valor_total_item"]) for item in self.itens_atual)
        return f"{total:.2f}"

    @rx.event
    async def carregar(self):
        motos = sorted(await xano.listar(TABELA_MOTOS), key=lambda m: m["modelo"])
        todos_funcionarios = await xano.listar(TABELA_FUNCIONARIOS)
        mecanicos = sorted(
            [f for f in todos_funcionarios if f["tipo"] == "MECANICO"],
            key=lambda f: f["nome_funcionario"],
        )
        produtos = sorted(await xano.listar(TABELA_PRODUTOS), key=lambda p: p["nome_produto"])

        self.motos_opcoes = [f"{m['id']} - {m['modelo']} ({m['placa']})" for m in motos]
        self.mecanicos_opcoes = [f"{f['id']} - {f['nome_funcionario']}" for f in mecanicos]
        self.produtos_opcoes = [f"{p['id']} - {p['nome_produto']}" for p in produtos]
        if not self.moto_selecionada and self.motos_opcoes:
            self.moto_selecionada = self.motos_opcoes[0]
        if not self.mecanico_selecionado and self.mecanicos_opcoes:
            self.mecanico_selecionado = self.mecanicos_opcoes[0]
        if not self.item_produto_selecionado and self.produtos_opcoes:
            self.item_produto_selecionado = self.produtos_opcoes[0]

        nomes_moto = {m["id"]: f"{m['modelo']} ({m['placa']})" for m in motos}
        # também pode haver mecânicos já cadastrados com outro tipo em OS antigas
        nomes_mecanico = {f["id"]: f["nome_funcionario"] for f in todos_funcionarios}

        registros = sorted(await xano.listar(TABELA_OS), key=lambda o: o["data_abertura"], reverse=True)[:30]
        qtd_itens_por_os: dict[int, int] = {}
        valor_por_os: dict[int, float] = {}
        for item in await xano.listar(TABELA_ITENS):
            qtd_itens_por_os[item["id_os"]] = qtd_itens_por_os.get(item["id_os"], 0) + 1
            valor_por_os[item["id_os"]] = valor_por_os.get(item["id_os"], 0.0) + item["valor_total_item"]

        self.ordens = [
            {
                "id": str(o["id"]),
                "data_abertura": xano.epoch_ms_para_datetime(o["data_abertura"]).strftime("%d/%m/%Y %H:%M"),
                "moto_nome": nomes_moto.get(o["id_moto_cliente"], "—"),
                "mecanico_nome": nomes_mecanico.get(o["id_funcionario"], "—"),
                "status": o["status"],
                "qtd_itens": str(qtd_itens_por_os.get(o["id"], 0)),
                "valor_total": f"{valor_por_os.get(o['id'], 0.0):.2f}",
            }
            for o in registros
        ]

    @rx.event
    def adicionar_item(self):
        if not self.item_produto_selecionado:
            return rx.window_alert("Cadastre uma peça (produto) antes de lançar na OS.")
        try:
            quantidade = int(self.item_quantidade or 0)
            valor_total_item = float(str(self.item_valor_total).replace(",", "."))
        except ValueError:
            return rx.window_alert("Quantidade e valor precisam ser números válidos.")
        if quantidade <= 0:
            return rx.window_alert("Quantidade precisa ser maior que zero.")
        if valor_total_item < 0:
            return rx.window_alert("Valor não pode ser negativo.")

        produto_id, produto_nome = self.item_produto_selecionado.split(" - ", 1)
        self.itens_atual = self.itens_atual + [
            {
                "produto_id": produto_id,
                "produto_nome": produto_nome,
                "quantidade": str(quantidade),
                "valor_total_item": f"{valor_total_item:.2f}",
            }
        ]
        self.item_quantidade = "1"
        self.item_valor_total = "0.00"

    @rx.event
    def remover_item(self, indice: int):
        self.itens_atual = [item for i, item in enumerate(self.itens_atual) if i != indice]

    @rx.event
    async def abrir_os(self):
        if not self.moto_selecionada:
            return rx.window_alert("Cadastre uma moto do cliente antes de abrir uma OS.")
        if not self.mecanico_selecionado:
            return rx.window_alert("Cadastre um funcionário do tipo MECANICO antes de abrir uma OS.")

        id_moto = int(self.moto_selecionada.split(" - ")[0])
        id_mecanico = int(self.mecanico_selecionado.split(" - ")[0])

        os_nova = await xano.criar(
            TABELA_OS,
            {
                "id_moto_cliente": id_moto,
                "id_funcionario": id_mecanico,
                "data_abertura": xano.datetime_para_epoch_ms(),
                "status": "ABERTA",
            },
        )

        for item in self.itens_atual:
            produto_id = int(item["produto_id"])
            quantidade = int(item["quantidade"])
            valor_total_item = float(item["valor_total_item"])

            await xano.criar(
                TABELA_ITENS,
                {
                    "id_os": os_nova["id"],
                    "id_produto": produto_id,
                    "quantidade": quantidade,
                    "valor_total_item": valor_total_item,
                },
            )
            produto = await xano.buscar(TABELA_PRODUTOS, produto_id)
            if produto is not None:
                produto["estoque_qtd"] = max(0, produto["estoque_qtd"] - quantidade)
                await xano.atualizar(TABELA_PRODUTOS, produto_id, {k: v for k, v in produto.items() if k != "id"})

        self.itens_atual = []
        await self.carregar()

    @rx.event
    async def mudar_status(self, os_id: str, novo_status: str):
        registro = await xano.buscar(TABELA_OS, int(os_id))
        if registro is not None:
            registro["status"] = novo_status
            await xano.atualizar(TABELA_OS, int(os_id), {k: v for k, v in registro.items() if k != "id"})
        await self.carregar()

    @rx.event
    async def excluir_os(self, os_id: str):
        for item in await xano.listar(TABELA_ITENS):
            if item["id_os"] == int(os_id):
                await xano.excluir(TABELA_ITENS, item["id"])
        await xano.excluir(TABELA_OS, int(os_id))
        await self.carregar()

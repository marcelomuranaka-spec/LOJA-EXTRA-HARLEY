"""
State de Compras (Entrada de Mercadoria + Itens de Compra em Estoque).

Este é o padrão a seguir para telas de "cabeçalho + itens" (a mesma ideia
se repete em `os_state.py` para Ordens de Serviço): a compra inteira é
montada em memória (`itens_atual`) e só é gravada no banco de uma vez,
em `finalizar_compra`, quando o usuário confirma — criando primeiro o
cabeçalho (EntradaMercadoria) e depois uma linha (ItemCompraEstoque)
para cada item, além de já dar entrada no estoque de cada produto.

Dados vêm do backend Xano.
"""

import asyncio

import reflex as rx

from .. import estoque
from .. import xano_client as xano

TABELA_ENTRADA = "entrada_mercadoria"
TABELA_ITENS = "itens_compra_estoque"
TABELA_FORNECEDORES = "fornecedores"
TABELA_PRODUTOS = "produtos"


class ComprasState(rx.State):
    historico: list[dict] = []

    fornecedores_opcoes: list[str] = []
    produtos_opcoes: list[str] = []

    fornecedor_selecionado: str = ""
    itens_atual: list[dict] = []  # [{produto_id, produto_nome, quantidade, valor_unitario, subtotal}]

    item_produto_selecionado: str = ""
    item_quantidade: str = "1"
    item_valor_unitario: str = "0.00"

    @rx.var
    def total_atual(self) -> str:
        total = sum(float(item["subtotal"]) for item in self.itens_atual)
        return f"{total:.2f}"

    @rx.event
    async def carregar(self):
        # As 4 tabelas são buscadas em paralelo.
        fornecedores, produtos, entradas_todas, itens = await asyncio.gather(
            xano.listar(TABELA_FORNECEDORES), xano.listar(TABELA_PRODUTOS),
            xano.listar(TABELA_ENTRADA), xano.listar(TABELA_ITENS),
        )
        fornecedores.sort(key=lambda f: f["nome_fornecedor"])
        produtos.sort(key=lambda p: p["nome_produto"])
        self.fornecedores_opcoes = [f"{f['id']} - {f['nome_fornecedor']}" for f in fornecedores]
        self.produtos_opcoes = [f"{p['id']} - {p['nome_produto']}" for p in produtos]
        if not self.fornecedor_selecionado and self.fornecedores_opcoes:
            self.fornecedor_selecionado = self.fornecedores_opcoes[0]
        if not self.item_produto_selecionado and self.produtos_opcoes:
            self.item_produto_selecionado = self.produtos_opcoes[0]

        nomes_fornecedor = {f["id"]: f["nome_fornecedor"] for f in fornecedores}

        entradas = sorted(entradas_todas, key=lambda e: e["data_entrada"], reverse=True)[:30]
        qtd_itens_por_entrada: dict[int, int] = {}
        for item in itens:
            qtd_itens_por_entrada[item["id_entrada"]] = qtd_itens_por_entrada.get(item["id_entrada"], 0) + 1

        self.historico = [
            {
                "id": str(e["id"]),
                "data_entrada": xano.epoch_ms_para_datetime(e["data_entrada"]).strftime("%d/%m/%Y %H:%M"),
                "fornecedor_nome": nomes_fornecedor.get(e["id_fornecedor"], "—"),
                "valor_total": f"{e['valor_total']:.2f}",
                "qtd_itens": str(qtd_itens_por_entrada.get(e["id"], 0)),
            }
            for e in entradas
        ]

    @rx.event
    def adicionar_item(self):
        if not self.item_produto_selecionado:
            return rx.toast.error("Cadastre um produto antes de lançar uma compra.")
        try:
            quantidade = int(self.item_quantidade or 0)
            valor_unitario = float(str(self.item_valor_unitario).replace(",", "."))
        except ValueError:
            return rx.toast.error("Quantidade e valor unitário precisam ser números válidos.")
        if quantidade <= 0:
            return rx.toast.error("Quantidade precisa ser maior que zero.")
        if valor_unitario < 0:
            return rx.toast.error("Valor unitário não pode ser negativo.")

        produto_id, produto_nome = self.item_produto_selecionado.split(" - ", 1)
        self.itens_atual = self.itens_atual + [
            {
                "produto_id": produto_id,
                "produto_nome": produto_nome,
                "quantidade": str(quantidade),
                "valor_unitario": f"{valor_unitario:.2f}",
                "subtotal": f"{quantidade * valor_unitario:.2f}",
            }
        ]
        self.item_quantidade = "1"
        self.item_valor_unitario = "0.00"

    @rx.event
    def remover_item(self, indice: int):
        self.itens_atual = [item for i, item in enumerate(self.itens_atual) if i != indice]

    @rx.event
    async def finalizar_compra(self):
        if not self.fornecedor_selecionado:
            return rx.toast.error("Selecione o fornecedor.")
        if not self.itens_atual:
            return rx.toast.error("Adicione ao menos um item à compra.")

        id_fornecedor = int(self.fornecedor_selecionado.split(" - ")[0])
        total = sum(float(item["subtotal"]) for item in self.itens_atual)

        entrada = await xano.criar(
            TABELA_ENTRADA,
            {
                "id_fornecedor": id_fornecedor,
                "data_entrada": xano.datetime_para_epoch_ms(),
                "valor_total": total,
            },
        )

        entradas_estoque: dict[int, int] = {}
        for item in self.itens_atual:
            produto_id = int(item["produto_id"])
            quantidade = int(item["quantidade"])
            valor_unitario = float(item["valor_unitario"])

            await xano.criar(
                TABELA_ITENS,
                {
                    "id_entrada": entrada["id"],
                    "id_produto": produto_id,
                    "quantidade": quantidade,
                    "valor_unitario": valor_unitario,
                },
            )
            entradas_estoque[produto_id] = entradas_estoque.get(produto_id, 0) + quantidade

        self.itens_atual = []
        # Mesmo caminho das vendas (trava por produto e saldo lido direto do
        # Xano): somar sobre o saldo do cache podia apagar a baixa de uma
        # venda feita ao mesmo tempo.
        try:
            await estoque.movimentar(entradas_estoque)
        except Exception:
            await self.carregar()
            return rx.toast.error(
                f"Compra nº {entrada['id']} registrada, mas o estoque não pôde ser atualizado. "
                "Ajuste as quantidades na página Produtos."
            )
        await self.carregar()
        return rx.toast.success(f"Compra nº {entrada['id']} registrada e estoque atualizado.")

    @rx.event
    async def excluir_entrada(self, entrada_id: str):
        # Exclui o cabeçalho e os itens da compra. Não desfaz o estoque que
        # já entrou — ajuste manualmente na página Produtos se necessário.
        for item in await xano.listar(TABELA_ITENS):
            if item["id_entrada"] == int(entrada_id):
                await xano.excluir(TABELA_ITENS, item["id"])
        await xano.excluir(TABELA_ENTRADA, int(entrada_id))
        await self.carregar()

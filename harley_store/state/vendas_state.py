"""
State de Vendas / Balcão (tabela Transacoes).

Atenção — limitação herdada do banco original: a tabela `Transacoes` só
guarda o valor total da venda, sem uma tabela de itens (diferente de
Compras e Ordens de Serviço, que têm `Itens_Compra_Estoque` e
`Itens_Ordem_Servico`). Por isso, aqui embaixo o campo "produto vendido"
é só um AJUDANTE de cálculo: ele soma o valor e baixa o estoque na hora,
mas não fica gravado de forma permanente qual produto foi vendido em
qual transação — só o valor total.

Se no futuro você quiser guardar o detalhe de cada item vendido no
balcão (recomendado!), crie uma tabela `ItensTransacao` igual à
`ItemOrdemServico`, com id_transacao + id_produto + quantidade +
valor_unitario, e repita o padrão usado em `compras_state.py`.

Dados vêm do backend Xano. Observação: o schema da tabela `transacoes`
no Xano foi criado por importação de CSV, então `id_cliente` e
`id_moto_cliente` são inteiros não-opcionais — "sem cliente/moto" é
representado como `0`, não `null`.
"""

from typing import Optional

import reflex as rx

from ..models import TIPOS_TRANSACAO
from .. import xano_client as xano

TABELA = "transacoes"
TABELA_FUNCIONARIOS = "funcionarios"
TABELA_CLIENTES = "clientes"
TABELA_MOTOS = "motos_clientes"
TABELA_PRODUTOS = "produtos"

SEM_CLIENTE = "— nenhum —"
SEM_MOTO = "— nenhuma —"
SEM_PRODUTO = "— nenhum (informar valor manualmente) —"


class VendasState(rx.State):
    transacoes: list[dict] = []

    funcionarios_opcoes: list[str] = []
    clientes_opcoes: list[str] = []
    motos_opcoes: list[str] = []
    produtos_opcoes: list[str] = []

    tipo_transacao: str = TIPOS_TRANSACAO[0]
    funcionario_selecionado: str = ""
    cliente_selecionado: str = SEM_CLIENTE
    moto_selecionada: str = SEM_MOTO
    produto_selecionado: str = SEM_PRODUTO
    quantidade: str = "1"
    valor_total: str = "0.00"

    @rx.event
    async def carregar(self):
        funcionarios = sorted(await xano.listar(TABELA_FUNCIONARIOS), key=lambda f: f["nome_funcionario"])
        clientes = sorted(await xano.listar(TABELA_CLIENTES), key=lambda c: c["nome_cliente"])
        motos = sorted(await xano.listar(TABELA_MOTOS), key=lambda m: m["modelo"])
        produtos = sorted(await xano.listar(TABELA_PRODUTOS), key=lambda p: p["nome_produto"])

        self.funcionarios_opcoes = [f"{f['id']} - {f['nome_funcionario']}" for f in funcionarios]
        self.clientes_opcoes = [SEM_CLIENTE] + [f"{c['id']} - {c['nome_cliente']}" for c in clientes]
        self.motos_opcoes = [SEM_MOTO] + [f"{m['id']} - {m['modelo']} ({m['placa']})" for m in motos]
        self.produtos_opcoes = [SEM_PRODUTO] + [
            f"{p['id']} - {p['nome_produto']} — estoque {p['estoque_qtd']} — R$ {p['preco_venda']:.2f}"
            for p in produtos
        ]

        nomes_funcionario = {f["id"]: f["nome_funcionario"] for f in funcionarios}
        nomes_cliente = {c["id"]: c["nome_cliente"] for c in clientes}

        registros = sorted(await xano.listar(TABELA), key=lambda t: t["data_transacao"], reverse=True)[:50]

        self.transacoes = [
            {
                "id": str(t["id"]),
                "tipo_transacao": t["tipo_transacao"],
                "funcionario_nome": nomes_funcionario.get(t["id_funcionario"], "—"),
                "cliente_nome": nomes_cliente.get(t["id_cliente"], "—") if t.get("id_cliente") else "—",
                "data_transacao": xano.epoch_ms_para_datetime(t["data_transacao"]).strftime("%d/%m/%Y %H:%M"),
                "valor_total": f"{t['valor_total']:.2f}",
            }
            for t in registros
        ]

        if not self.funcionario_selecionado and self.funcionarios_opcoes:
            self.funcionario_selecionado = self.funcionarios_opcoes[0]

    @rx.event
    def definir_tipo(self, valor: str):
        self.tipo_transacao = valor

    @rx.event
    async def definir_produto(self, valor: str):
        self.produto_selecionado = valor
        await self._recalcular_valor()

    @rx.event
    async def definir_quantidade(self, valor: str):
        self.quantidade = valor
        await self._recalcular_valor()

    async def _recalcular_valor(self):
        if self.produto_selecionado == SEM_PRODUTO or not self.produto_selecionado:
            return
        try:
            produto_id = int(self.produto_selecionado.split(" - ")[0])
            qtd = int(self.quantidade or 0)
        except ValueError:
            return
        produto = await xano.buscar(TABELA_PRODUTOS, produto_id)
        if produto:
            self.valor_total = f"{produto['preco_venda'] * qtd:.2f}"

    @rx.event
    def nova_venda(self):
        self.tipo_transacao = TIPOS_TRANSACAO[0]
        self.cliente_selecionado = SEM_CLIENTE
        self.moto_selecionada = SEM_MOTO
        self.produto_selecionado = SEM_PRODUTO
        self.quantidade = "1"
        self.valor_total = "0.00"

    @rx.event
    async def salvar(self):
        if not self.funcionario_selecionado:
            return rx.window_alert("Cadastre um funcionário antes de registrar uma venda.")
        try:
            valor = float(str(self.valor_total).replace(",", "."))
        except ValueError:
            return rx.window_alert("Valor total inválido.")
        if valor < 0:
            return rx.window_alert("O valor total não pode ser negativo.")

        id_funcionario = int(self.funcionario_selecionado.split(" - ")[0])
        id_cliente = 0 if self.cliente_selecionado == SEM_CLIENTE else int(self.cliente_selecionado.split(" - ")[0])
        id_moto = 0 if self.moto_selecionada == SEM_MOTO else int(self.moto_selecionada.split(" - ")[0])

        produto_id: Optional[int] = None
        quantidade = 0
        if self.produto_selecionado != SEM_PRODUTO and self.produto_selecionado:
            produto_id = int(self.produto_selecionado.split(" - ")[0])
            try:
                quantidade = int(self.quantidade or 0)
            except ValueError:
                return rx.window_alert("Quantidade inválida.")
            if quantidade <= 0:
                return rx.window_alert("Quantidade precisa ser maior que zero.")

        if produto_id is not None:
            produto = await xano.buscar(TABELA_PRODUTOS, produto_id)
            if produto is None:
                return rx.window_alert("Produto não encontrado.")
            if produto["estoque_qtd"] < quantidade:
                return rx.window_alert(
                    f"Estoque insuficiente: só há {produto['estoque_qtd']} unidade(s) de {produto['nome_produto']}."
                )
            produto["estoque_qtd"] -= quantidade
            await xano.atualizar(TABELA_PRODUTOS, produto_id, {k: v for k, v in produto.items() if k != "id"})

        await xano.criar(
            TABELA,
            {
                "tipo_transacao": self.tipo_transacao,
                "id_funcionario": id_funcionario,
                "id_cliente": id_cliente,
                "id_moto_cliente": id_moto,
                "data_transacao": xano.datetime_para_epoch_ms(),
                "valor_total": valor,
            },
        )

        self.nova_venda()
        await self.carregar()

    @rx.event
    async def excluir(self, transacao_id: str):
        # Observação: excluir uma venda aqui NÃO devolve o produto ao estoque
        # automaticamente (o vínculo com o produto não é guardado, ver nota
        # no topo do arquivo). Ajuste o estoque manualmente na página Produtos
        # se for o caso.
        await xano.excluir(TABELA, int(transacao_id))
        await self.carregar()

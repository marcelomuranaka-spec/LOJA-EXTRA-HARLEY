"""
State de Vendas / Balcão (tabelas transacoes + itens_transacao).

Uma venda tem vários itens (carrinho): produtos do estoque ou itens avulsos
(sem estoque, ex.: mão de obra). Vendas não são apagadas: são CANCELADAS,
continuam na lista, saem do faturamento e devolvem o estoque. As regras
(ordem das gravações, travas de estoque, compensação de falhas) ficam em
`vendas_servico.py`; aqui fica só o que a tela precisa.

Vendas registradas antes dos itens existirem não têm itens gravados: são
exibidas com o valor total e, se canceladas, o sistema avisa para conferir o
estoque manualmente.

Observação: por causa da importação por CSV, "sem cliente/moto" em
`transacoes` é `0`, não `null`.
"""

import asyncio

import reflex as rx

from .. import vendas_servico as servico
from .. import xano_client as xano
from ..constantes import TIPOS_TRANSACAO
from .auth_state import AuthState

TABELA = "transacoes"
TABELA_ITENS = "itens_transacao"
TABELA_FUNCIONARIOS = "funcionarios"
TABELA_CLIENTES = "clientes"
TABELA_MOTOS = "motos_clientes"
TABELA_PRODUTOS = "produtos"

SEM_CLIENTE = "— nenhum —"
SEM_MOTO = "— nenhuma —"


def _numero(texto: str) -> float:
    texto = (texto or "").strip().replace("R$", "").replace(" ", "")
    if "," in texto:
        texto = texto.replace(".", "").replace(",", ".")
    return float(texto) if texto else 0.0


def _moeda(valor: float) -> str:
    return f"{valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _data_cancelamento(valor) -> str:
    """O campo pode ser timestamp (epoch ms) ou date ('AAAA-MM-DD') no Xano."""
    if not valor:
        return ""
    if isinstance(valor, (int, float)):
        return xano.epoch_ms_para_datetime(valor).strftime("%d/%m/%Y %H:%M")
    partes = str(valor)[:10].split("-")
    return "/".join(reversed(partes)) if len(partes) == 3 else str(valor)


class VendasState(rx.State):
    transacoes: list[dict] = []
    aviso_itens: str = ""  # tabela de itens indisponível no Xano

    funcionarios_opcoes: list[str] = []
    clientes_opcoes: list[str] = []
    motos_opcoes: list[str] = []
    produtos_opcoes: list[str] = []

    # cabeçalho da venda
    tipo_transacao: str = TIPOS_TRANSACAO[0]
    funcionario_selecionado: str = ""
    cliente_selecionado: str = SEM_CLIENTE
    moto_selecionada: str = SEM_MOTO

    # carrinho: [{id_produto, descricao, quantidade, valor_unitario, subtotal}] (strings para a tela)
    carrinho: list[dict] = []
    produto_selecionado: str = ""
    item_quantidade: str = "1"
    item_preco: str = ""
    avulso_descricao: str = ""
    avulso_quantidade: str = "1"
    avulso_valor: str = ""

    erro_venda: str = ""
    sucesso_venda: str = ""

    # cancelamento
    selecionadas: list[str] = []
    motivo_cancelamento: str = ""
    resultado_cancelamento: list[str] = []

    _precos: dict[int, float] = {}
    _estoques: dict[int, int] = {}
    _nomes: dict[int, str] = {}

    @rx.var
    def total_carrinho(self) -> str:
        total = sum(int(i["quantidade"]) * _numero(i["valor_unitario"]) for i in self.carrinho)
        return _moeda(total)

    @rx.var
    def qtd_selecionadas(self) -> int:
        return len(self.selecionadas)

    # ------------------------------------------------------------ carregar

    @rx.event
    async def carregar(self):
        funcionarios, clientes, motos, produtos, transacoes = await asyncio.gather(
            xano.listar(TABELA_FUNCIONARIOS), xano.listar(TABELA_CLIENTES), xano.listar(TABELA_MOTOS),
            xano.listar(TABELA_PRODUTOS), xano.listar(TABELA),
        )
        try:
            itens = await xano.listar(TABELA_ITENS)
            self.aviso_itens = ""
        except Exception:
            itens = []
            self.aviso_itens = ("A tabela itens_transacao não está disponível no Xano: "
                                "não é possível registrar nem cancelar vendas com devolução de estoque.")
        funcionarios.sort(key=lambda f: f["nome_funcionario"])
        clientes.sort(key=lambda c: c["nome_cliente"])
        motos.sort(key=lambda m: m["modelo"])
        produtos.sort(key=lambda p: p["nome_produto"])
        self._precos = {p["id"]: float(p["preco_venda"] or 0) for p in produtos}
        self._estoques = {p["id"]: int(p["estoque_qtd"] or 0) for p in produtos}
        self._nomes = {p["id"]: p["nome_produto"] for p in produtos}

        self.funcionarios_opcoes = [f"{f['id']} - {f['nome_funcionario']}" for f in funcionarios]
        self.clientes_opcoes = [SEM_CLIENTE] + [f"{c['id']} - {c['nome_cliente']}" for c in clientes]
        self.motos_opcoes = [SEM_MOTO] + [f"{m['id']} - {m['modelo']} ({m['placa']})" for m in motos]
        self.produtos_opcoes = [
            f"{p['id']} - {p['nome_produto']} — estoque {p['estoque_qtd']}" for p in produtos
        ]
        if not self.funcionario_selecionado and self.funcionarios_opcoes:
            self.funcionario_selecionado = self.funcionarios_opcoes[0]

        nomes_funcionario = {f["id"]: f["nome_funcionario"] for f in funcionarios}
        nomes_cliente = {c["id"]: c["nome_cliente"] for c in clientes}
        itens_por_venda: dict[int, int] = {}
        for item in itens:
            vid = int(item.get(servico.CAMPO_VENDA) or 0)
            itens_por_venda[vid] = itens_por_venda.get(vid, 0) + 1

        registros = sorted(transacoes, key=lambda t: t["data_transacao"] or 0, reverse=True)[:50]
        self.transacoes = [
            {
                "id": str(t["id"]),
                "tipo_transacao": t["tipo_transacao"],
                "funcionario_nome": nomes_funcionario.get(t["id_funcionario"], "—"),
                "cliente_nome": nomes_cliente.get(t["id_cliente"], "—") if t.get("id_cliente") else "—",
                "data_transacao": xano.epoch_ms_para_datetime(t["data_transacao"]).strftime("%d/%m/%Y %H:%M"),
                "valor_total": _moeda(float(t["valor_total"] or 0)),
                "cancelada": servico.esta_cancelada(t),
                "data_cancelamento": _data_cancelamento(t.get("data_cancelamento")),
                "motivo": t.get("motivo_cancelamento") or "",
                "qtd_itens": str(itens_por_venda[t["id"]]) if t["id"] in itens_por_venda else "—",
            }
            for t in registros
        ]
        ativas = {t["id"] for t in self.transacoes if not t["cancelada"]}
        self.selecionadas = [i for i in self.selecionadas if i in ativas]

    # ------------------------------------------------------------ carrinho

    @rx.event
    def definir_produto(self, valor: str):
        self.produto_selecionado = valor
        try:
            pid = int(valor.split(" - ")[0])
            self.item_preco = _moeda(self._precos.get(pid, 0.0))
        except ValueError:
            pass

    @rx.event
    def adicionar_produto(self):
        self.erro_venda = self.sucesso_venda = ""
        if not self.produto_selecionado:
            self.erro_venda = "Escolha um produto."
            return
        try:
            pid = int(self.produto_selecionado.split(" - ")[0])
            qtd = int(self.item_quantidade or 0)
            preco = _numero(self.item_preco)
        except ValueError:
            self.erro_venda = "Quantidade e preço precisam ser números."
            return
        if qtd <= 0 or preco < 0:
            self.erro_venda = "A quantidade precisa ser maior que zero e o preço não pode ser negativo."
            return
        ja_no_carrinho = sum(int(i["quantidade"]) for i in self.carrinho if int(i["id_produto"]) == pid)
        disponivel = self._estoques.get(pid, 0)
        if ja_no_carrinho + qtd > disponivel:
            self.erro_venda = f"Estoque insuficiente de {self._nomes.get(pid, 'produto')}: há {disponivel}."
            return
        self.carrinho = self.carrinho + [{
            "id_produto": str(pid),
            "descricao": self._nomes.get(pid, f"Produto {pid}"),
            "quantidade": str(qtd),
            "valor_unitario": _moeda(preco),
            "subtotal": _moeda(qtd * preco),
        }]
        self.item_quantidade = "1"

    @rx.event
    def adicionar_avulso(self):
        self.erro_venda = self.sucesso_venda = ""
        descricao = self.avulso_descricao.strip()
        try:
            qtd = int(self.avulso_quantidade or 0)
            valor = _numero(self.avulso_valor)
        except ValueError:
            self.erro_venda = "Quantidade e valor precisam ser números."
            return
        if not descricao or qtd <= 0 or valor < 0:
            self.erro_venda = "Informe a descrição, uma quantidade maior que zero e um valor válido."
            return
        self.carrinho = self.carrinho + [{
            "id_produto": "0",
            "descricao": descricao,
            "quantidade": str(qtd),
            "valor_unitario": _moeda(valor),
            "subtotal": _moeda(qtd * valor),
        }]
        self.avulso_descricao, self.avulso_quantidade, self.avulso_valor = "", "1", ""

    @rx.event
    def remover_item(self, indice: int):
        self.carrinho = [item for i, item in enumerate(self.carrinho) if i != indice]

    @rx.event
    def nova_venda(self):
        self.tipo_transacao = TIPOS_TRANSACAO[0]
        self.cliente_selecionado = SEM_CLIENTE
        self.moto_selecionada = SEM_MOTO
        self.carrinho = []
        self.produto_selecionado = ""
        self.item_quantidade, self.item_preco = "1", ""
        self.avulso_descricao, self.avulso_quantidade, self.avulso_valor = "", "1", ""
        self.erro_venda = ""

    @rx.event
    async def salvar(self):
        self.erro_venda = self.sucesso_venda = ""
        if not self.funcionario_selecionado:
            self.erro_venda = "Cadastre um funcionário antes de registrar uma venda."
            return
        if not self.carrinho:
            self.erro_venda = "Adicione ao menos um item à venda."
            return
        itens = [
            {"id_produto": int(i["id_produto"]), "descricao": i["descricao"],
             "quantidade": int(i["quantidade"]), "valor_unitario": _numero(i["valor_unitario"])}
            for i in self.carrinho
        ]
        id_cliente = 0 if self.cliente_selecionado == SEM_CLIENTE else int(self.cliente_selecionado.split(" - ")[0])
        id_moto = 0 if self.moto_selecionada == SEM_MOTO else int(self.moto_selecionada.split(" - ")[0])
        try:
            venda_id = await servico.registrar_venda(
                self.tipo_transacao, int(self.funcionario_selecionado.split(" - ")[0]),
                id_cliente, id_moto, itens, (await self.get_state(AuthState)).usuario_logado,
            )
        except servico.FalhaVenda as erro:
            self.erro_venda = str(erro)
            await self.carregar()
            return
        total = self.total_carrinho
        self.nova_venda()
        self.sucesso_venda = f"Venda nº {venda_id} registrada: R$ {total}."
        await self.carregar()

    # -------------------------------------------------------- cancelamento

    @rx.event
    def preparar_cancelamento(self):
        self.motivo_cancelamento = ""

    @rx.event
    def alternar_selecao(self, venda_id: str):
        if venda_id in self.selecionadas:
            self.selecionadas = [i for i in self.selecionadas if i != venda_id]
        else:
            self.selecionadas = self.selecionadas + [venda_id]

    @rx.event
    def limpar_selecao(self):
        self.selecionadas = []

    def _resumir(self, resultados: list[dict]):
        canceladas = [r for r in resultados if r["situacao"] == "cancelada"]
        linhas = []
        if canceladas:
            linhas.append(f"{len(canceladas)} vendas canceladas." if len(canceladas) > 1
                          else f"Venda nº {canceladas[0]['id']} cancelada.")
        linhas += [r["mensagem"] for r in resultados if r["mensagem"]]
        self.resultado_cancelamento = linhas

    @rx.event
    async def cancelar(self, venda_id: str):
        usuario = (await self.get_state(AuthState)).usuario_logado
        resultado = await servico.cancelar_venda(int(venda_id), self.motivo_cancelamento, usuario)
        resultado["id"] = int(venda_id)
        self._resumir([resultado])
        self.selecionadas = [i for i in self.selecionadas if i != venda_id]
        await self.carregar()

    @rx.event
    async def cancelar_selecionadas(self):
        ids = [int(i) for i in self.selecionadas]
        if not ids:
            return
        usuario = (await self.get_state(AuthState)).usuario_logado
        resultados = await servico.cancelar_varias(ids, self.motivo_cancelamento, usuario)
        self._resumir(resultados)
        self.selecionadas = []
        await self.carregar()

    @rx.event
    def fechar_resultado(self):
        self.resultado_cancelamento = []

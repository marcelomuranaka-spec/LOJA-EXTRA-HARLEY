"""
State de Vendas / Balcão (tabelas transacoes + itens_transacao).

Fluxo rápido de venda: cliente → produtos (com quantidade e preço) → moto da
loja (quando for o caso) → itens avulsos → desconto (R$ ou %) → subtotal,
desconto e total → forma de pagamento → finalizar.

Toda a gravação acontece no servidor, em `vendas_servico.registrar_venda`:
baixa de estoque com trava (nunca pelo navegador), moto passada a Vendida,
venda e itens gravados, e tudo desfeito se algo falhar no meio. Vendas não
são apagadas: são CANCELADAS, continuam na lista, saem do faturamento e
devolvem o estoque (e a moto, quando o Xano tem o campo `moto_id`).

Observação: por causa da importação por CSV, "sem cliente/moto" em
`transacoes` é `0`, não `null`.
"""

import asyncio
import math

import reflex as rx

from .. import formatacao as fmt
from .. import motos_loja_servico as motos_loja
from .. import recursos
from .. import vendas_servico as servico
from .. import xano_client as xano
from ..models import TIPOS_TRANSACAO
from .auth_state import AuthState

TABELA = "transacoes"
TABELA_ITENS = "itens_transacao"
SEM_CLIENTE = "— sem cliente (balcão) —"
SEM_MOTO = "— nenhuma —"
FORMAS_PADRAO = ["Dinheiro", "PIX", "Cartão de débito", "Cartão de crédito"]
POR_PAGINA = 20
SITUACOES_LISTA = ["Todas", "Ativas", "Canceladas"]


def _id(opcao: str) -> int:
    try:
        return int((opcao or "").split(" - ")[0])
    except ValueError:
        return 0


class VendasState(rx.State):
    transacoes: list[dict] = []
    total_lista: int = 0
    pagina: int = 1
    busca_lista: str = ""
    filtro_situacao: str = "Todas"
    aviso_itens: str = ""  # tabela de itens indisponível no Xano

    funcionarios_opcoes: list[str] = []
    clientes_opcoes: list[str] = []
    motos_opcoes: list[str] = []
    produtos_opcoes: list[str] = []
    motos_loja_opcoes: list[str] = []
    formas_pagamento: list[str] = FORMAS_PADRAO

    # recursos do Xano
    tem_pagamento: bool = False
    tem_moto_id: bool = False
    tem_usuario: bool = False
    formas_configuraveis: bool = False

    # cabeçalho da venda
    tipo_transacao: str = "BALCAO"
    funcionario_selecionado: str = ""
    cliente_selecionado: str = SEM_CLIENTE
    moto_selecionada: str = SEM_MOTO

    # itens
    carrinho: list[dict] = []
    produto_selecionado: str = ""
    item_quantidade: str = "1"
    item_preco: str = ""
    moto_loja_selecionada: str = ""
    moto_loja_preco: str = ""
    avulso_descricao: str = ""
    avulso_quantidade: str = "1"
    avulso_valor: str = ""

    # fechamento
    desconto_valor: str = ""
    desconto_tipo: str = "R$"
    forma_pagamento: str = ""

    erro_venda: str = ""
    sucesso_venda: str = ""
    ultima_venda_id: str = ""

    # cancelamento
    selecionadas: list[str] = []
    motivo_cancelamento: str = ""
    resultado_cancelamento: list[str] = []

    _precos: dict[int, float] = {}
    _estoques: dict[int, int] = {}
    _nomes: dict[int, str] = {}
    _motos_cliente: list[dict] = []
    _linhas: list[dict] = []

    # ------------------------------------------------------------- totais

    def _subtotal(self) -> float:
        return round(sum(int(i["quantidade"]) * fmt.numero(i["valor_unitario"]) for i in self.carrinho), 2)

    def _desconto(self) -> float:
        try:
            valor = fmt.numero(self.desconto_valor)
        except ValueError:
            return 0.0
        if self.desconto_tipo == "%":
            valor = self._subtotal() * valor / 100
        return round(max(0.0, valor), 2)

    @rx.var
    def subtotal_carrinho(self) -> str:
        return fmt.moeda(self._subtotal())

    @rx.var
    def desconto_carrinho(self) -> str:
        return fmt.moeda(self._desconto())

    @rx.var
    def total_carrinho(self) -> str:
        return fmt.moeda(max(0.0, self._subtotal() - self._desconto()))

    @rx.var
    def tem_moto_no_carrinho(self) -> bool:
        return any(i["tipo"] == "moto" for i in self.carrinho)

    @rx.var
    def qtd_selecionadas(self) -> int:
        return len(self.selecionadas)

    @rx.var
    def total_paginas(self) -> int:
        return max(1, math.ceil(self.total_lista / POR_PAGINA))

    @rx.var
    def situacoes_lista(self) -> list[str]:
        return SITUACOES_LISTA

    @rx.var
    def tipos_transacao(self) -> list[str]:
        return TIPOS_TRANSACAO

    @rx.var
    def motos_do_cliente(self) -> list[str]:
        cid = _id(self.cliente_selecionado)
        return [SEM_MOTO] + [o for o, dono in ((m["opcao"], m["cliente"]) for m in self._motos_cliente) if dono == cid]

    # ------------------------------------------------------------ carregar

    @rx.event
    async def carregar(self):
        funcionarios, clientes, motos, produtos, transacoes, motos_loja_lista, formas, campos = await asyncio.gather(
            xano.listar("funcionarios"), xano.listar("clientes"), xano.listar("motos_clientes"),
            xano.listar("produtos"), xano.listar(TABELA), xano.listar("motos"),
            xano.listar_se_existir("formas_pagamento"), recursos.campos_disponiveis("transacoes"),
        )
        try:
            itens = await xano.listar(TABELA_ITENS)
            self.aviso_itens = ""
        except Exception:
            itens = []
            self.aviso_itens = ("A tabela itens_transacao não está disponível no Xano: "
                                "não é possível registrar nem cancelar vendas com devolução de estoque.")
        self.tem_pagamento = "forma_pagamento" in campos
        self.tem_moto_id = "moto_id" in campos
        self.tem_usuario = "usuario_id" in campos
        self.formas_configuraveis = formas is not None
        ativas = [f["nome"] for f in (formas or []) if f.get("ativo") is not False and f.get("nome")]
        self.formas_pagamento = sorted(ativas) if ativas else FORMAS_PADRAO

        funcionarios.sort(key=lambda f: f["nome_funcionario"].lower())
        clientes.sort(key=lambda c: c["nome_cliente"].lower())
        motos.sort(key=lambda m: m["modelo"])
        produtos = [p for p in produtos if p.get("ativo") is not False]
        produtos.sort(key=lambda p: p["nome_produto"].lower())
        self._precos = {p["id"]: float(p["preco_venda"] or 0) for p in produtos}
        self._estoques = {p["id"]: int(p["estoque_qtd"] or 0) for p in produtos}
        self._nomes = {p["id"]: p["nome_produto"] for p in produtos}

        self.funcionarios_opcoes = [f"{f['id']} - {f['nome_funcionario']}" for f in funcionarios]
        self.clientes_opcoes = [SEM_CLIENTE] + [f"{c['id']} - {c['nome_cliente']} ({c['cpf_cnpj']})" for c in clientes]
        self._motos_cliente = [
            {"opcao": f"{m['id']} - {m['modelo']} ({m['placa']})", "cliente": int(m.get("id_cliente") or 0)}
            for m in motos
        ]
        self.motos_opcoes = [SEM_MOTO] + [m["opcao"] for m in self._motos_cliente]
        self.produtos_opcoes = [f"{p['id']} - {p['nome_produto']} — estoque {p['estoque_qtd'] or 0}" for p in produtos]
        self.motos_loja_opcoes = [
            motos_loja.opcao_venda(m)
            for m in sorted(motos_loja_lista, key=lambda m: motos_loja.descricao(m))
            if motos_loja.situacao(m) in motos_loja.VENDAVEIS
        ]
        if not self.funcionario_selecionado and self.funcionarios_opcoes:
            self.funcionario_selecionado = self.funcionarios_opcoes[0]

        nomes_funcionario = {f["id"]: f["nome_funcionario"] for f in funcionarios}
        nomes_cliente = {c["id"]: c["nome_cliente"] for c in clientes}
        itens_por_venda: dict[int, int] = {}
        for item in itens:
            vid = int(item.get(servico.CAMPO_VENDA) or 0)
            itens_por_venda[vid] = itens_por_venda.get(vid, 0) + 1

        registros = sorted(transacoes, key=lambda t: t["data_transacao"] or 0, reverse=True)[:200]
        self._linhas = [
            {
                "id": str(t["id"]),
                "tipo_transacao": t["tipo_transacao"],
                "funcionario_nome": nomes_funcionario.get(t["id_funcionario"], "—"),
                "cliente_id": str(t.get("id_cliente") or 0),
                "cliente_nome": nomes_cliente.get(t["id_cliente"], "—") if t.get("id_cliente") else "—",
                "data_transacao": fmt.data_hora(t["data_transacao"]),
                "valor_total": fmt.moeda(float(t["valor_total"] or 0)),
                "forma_pagamento": t.get("forma_pagamento") or "",
                "cancelada": servico.esta_cancelada(t),
                "data_cancelamento": _data_cancelamento(t.get("data_cancelamento")),
                "motivo": t.get("motivo_cancelamento") or "",
                "qtd_itens": str(itens_por_venda[t["id"]]) if t["id"] in itens_por_venda else "—",
            }
            for t in registros
        ]
        ativas_ids = {t["id"] for t in self._linhas if not t["cancelada"]}
        self.selecionadas = [i for i in self.selecionadas if i in ativas_ids]
        self._aplicar_lista()

    def _aplicar_lista(self):
        termo = self.busca_lista.strip().lower()
        linhas = [
            l for l in self._linhas
            if (self.filtro_situacao == "Todas"
                or (self.filtro_situacao == "Ativas") == (not l["cancelada"]))
            and (not termo or termo in l["cliente_nome"].lower() or termo == l["id"]
                 or termo in l["funcionario_nome"].lower())
        ]
        self.total_lista = len(linhas)
        self.pagina = min(max(1, self.pagina), max(1, math.ceil(self.total_lista / POR_PAGINA)))
        inicio = (self.pagina - 1) * POR_PAGINA
        self.transacoes = linhas[inicio:inicio + POR_PAGINA]

    @rx.event
    def definir_busca_lista(self, valor: str):
        self.busca_lista, self.pagina = valor, 1
        self._aplicar_lista()

    @rx.event
    def definir_filtro_situacao(self, valor: str):
        self.filtro_situacao, self.pagina = valor, 1
        self._aplicar_lista()

    @rx.event
    def pagina_anterior(self):
        self.pagina -= 1
        self._aplicar_lista()

    @rx.event
    def proxima_pagina(self):
        self.pagina += 1
        self._aplicar_lista()

    # ------------------------------------------------------------ carrinho

    @rx.event
    def definir_cliente(self, valor: str):
        self.cliente_selecionado = valor
        self.moto_selecionada = SEM_MOTO

    @rx.event
    def definir_desconto_tipo(self, valor: str | list[str]):
        # o segmented_control declara str | list[str]; aqui é sempre um só valor
        self.desconto_tipo = valor[0] if isinstance(valor, list) else valor

    @rx.event
    def definir_produto(self, valor: str):
        self.produto_selecionado = valor
        pid = _id(valor)
        if pid in self._precos:
            self.item_preco = fmt.moeda(self._precos[pid])

    @rx.event
    def definir_moto_loja(self, valor: str):
        self.moto_loja_selecionada = valor
        self.moto_loja_preco = valor.rsplit("R$ ", 1)[-1] if "R$ " in valor else ""

    @rx.event
    def adicionar_produto(self):
        self.erro_venda = self.sucesso_venda = ""
        pid = _id(self.produto_selecionado)
        if pid not in self._nomes:
            self.erro_venda = "Escolha um produto da lista (digite parte do nome e clique na sugestão)."
            return
        try:
            qtd = fmt.inteiro(self.item_quantidade)
            preco = fmt.numero(self.item_preco)
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
            "tipo": "produto",
            "id_produto": str(pid),
            "id_moto": "0",
            "descricao": self._nomes[pid],
            "quantidade": str(qtd),
            "valor_unitario": fmt.moeda(preco),
            "subtotal": fmt.moeda(qtd * preco),
        }]
        self.produto_selecionado = ""
        self.item_quantidade, self.item_preco = "1", ""

    @rx.event
    def adicionar_moto_loja(self):
        self.erro_venda = self.sucesso_venda = ""
        mid = _id(self.moto_loja_selecionada)
        if not mid or self.moto_loja_selecionada not in self.motos_loja_opcoes:
            self.erro_venda = "Escolha uma moto da loja disponível."
            return
        try:
            preco = fmt.numero(self.moto_loja_preco)
        except ValueError:
            self.erro_venda = "Preço da moto inválido."
            return
        if preco <= 0:
            self.erro_venda = "Informe o preço de venda da moto."
            return
        descricao = self.moto_loja_selecionada.split(" - ", 1)[1].rsplit(" — R$", 1)[0]
        sem_moto = [i for i in self.carrinho if i["tipo"] != "moto"]  # uma moto por venda
        self.carrinho = sem_moto + [{
            "tipo": "moto",
            "id_produto": "0",
            "id_moto": str(mid),
            "descricao": "Moto: " + descricao,
            "quantidade": "1",
            "valor_unitario": fmt.moeda(preco),
            "subtotal": fmt.moeda(preco),
        }]
        self.tipo_transacao = "MOTO"
        self.moto_loja_selecionada, self.moto_loja_preco = "", ""

    @rx.event
    def adicionar_avulso(self):
        self.erro_venda = self.sucesso_venda = ""
        descricao = self.avulso_descricao.strip()
        try:
            qtd = fmt.inteiro(self.avulso_quantidade)
            valor = fmt.numero(self.avulso_valor)
        except ValueError:
            self.erro_venda = "Quantidade e valor precisam ser números."
            return
        if not descricao or qtd <= 0 or valor < 0:
            self.erro_venda = "Informe a descrição, uma quantidade maior que zero e um valor válido."
            return
        self.carrinho = self.carrinho + [{
            "tipo": "avulso",
            "id_produto": "0",
            "id_moto": "0",
            "descricao": descricao,
            "quantidade": str(qtd),
            "valor_unitario": fmt.moeda(valor),
            "subtotal": fmt.moeda(qtd * valor),
        }]
        self.avulso_descricao, self.avulso_quantidade, self.avulso_valor = "", "1", ""

    @rx.event
    def remover_item(self, indice: int):
        removido = self.carrinho[indice] if 0 <= indice < len(self.carrinho) else None
        self.carrinho = [item for i, item in enumerate(self.carrinho) if i != indice]
        if removido and removido["tipo"] == "moto" and self.tipo_transacao == "MOTO":
            self.tipo_transacao = "BALCAO"

    @rx.event
    def nova_venda(self):
        self.tipo_transacao = "BALCAO"
        self.cliente_selecionado = SEM_CLIENTE
        self.moto_selecionada = SEM_MOTO
        self.carrinho = []
        self.produto_selecionado = ""
        self.item_quantidade, self.item_preco = "1", ""
        self.moto_loja_selecionada, self.moto_loja_preco = "", ""
        self.avulso_descricao, self.avulso_quantidade, self.avulso_valor = "", "1", ""
        self.desconto_valor, self.desconto_tipo = "", "R$"
        self.forma_pagamento = ""
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
        id_cliente = 0 if self.cliente_selecionado == SEM_CLIENTE else _id(self.cliente_selecionado)
        if self.cliente_selecionado != SEM_CLIENTE and self.cliente_selecionado not in self.clientes_opcoes:
            self.erro_venda = "Cliente não encontrado: escolha um da lista (ou deixe sem cliente)."
            return
        try:
            fmt.numero(self.desconto_valor)
        except ValueError:
            self.erro_venda = "Desconto inválido."
            return
        desconto = self._desconto()
        if desconto > self._subtotal():
            self.erro_venda = "O desconto não pode ser maior que o subtotal."
            return
        if self.tem_pagamento and self.forma_pagamento not in self.formas_pagamento:
            self.erro_venda = "Escolha a forma de pagamento."
            return
        moto = next((i for i in self.carrinho if i["tipo"] == "moto"), None)
        itens = [
            {"id_produto": int(i["id_produto"]), "descricao": i["descricao"],
             "quantidade": int(i["quantidade"]), "valor_unitario": fmt.numero(i["valor_unitario"])}
            for i in self.carrinho if i["tipo"] != "moto"
        ]
        id_moto = 0 if self.moto_selecionada == SEM_MOTO else _id(self.moto_selecionada)
        auth = await self.get_state(AuthState)
        try:
            venda_id = await servico.registrar_venda(
                self.tipo_transacao, _id(self.funcionario_selecionado), id_cliente, id_moto, itens,
                desconto=desconto, forma_pagamento=self.forma_pagamento, usuario_id=auth.usuario_id,
                moto_loja={"id": int(moto["id_moto"]), "valor": fmt.numero(moto["valor_unitario"])} if moto else None,
                campos_venda=await recursos.campos_disponiveis("transacoes"),
            )
        except servico.FalhaVenda as erro:
            self.erro_venda = str(erro)
            await self.carregar()
            return
        total = self.total_carrinho
        self.nova_venda()
        self.sucesso_venda = f"Venda nº {venda_id} registrada: R$ {total}."
        self.ultima_venda_id = str(venda_id)
        await self.carregar()
        return rx.toast.success(f"Venda nº {venda_id} registrada.")

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
        resultado = await servico.cancelar_venda(int(venda_id), self.motivo_cancelamento)
        resultado["id"] = int(venda_id)
        self._resumir([resultado])
        self.selecionadas = [i for i in self.selecionadas if i != venda_id]
        await self.carregar()

    @rx.event
    async def cancelar_selecionadas(self):
        ids = [int(i) for i in self.selecionadas]
        if not ids:
            return
        resultados = await servico.cancelar_varias(ids, self.motivo_cancelamento)
        self._resumir(resultados)
        self.selecionadas = []
        await self.carregar()

    @rx.event
    def fechar_resultado(self):
        self.resultado_cancelamento = []


def _data_cancelamento(valor) -> str:
    """O campo pode ser timestamp (epoch ms) ou date ('AAAA-MM-DD') no Xano."""
    if not valor:
        return ""
    if isinstance(valor, (int, float)):
        return fmt.data_hora(valor)
    partes = str(valor)[:10].split("-")
    return "/".join(reversed(partes)) if len(partes) == 3 else str(valor)

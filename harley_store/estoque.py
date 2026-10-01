"""
Movimentação de estoque protegida contra operações simultâneas.

Toda baixa (venda) e devolução (cancelamento) de estoque de vendas passa por
`movimentar()`. Sem isso, duas vendas do mesmo produto ao mesmo tempo liam o
mesmo saldo e gravavam por cima uma da outra, e uma das baixas se perdia.

Como funciona:
- uma trava (asyncio.Lock) por produto, adquiridas sempre em ordem crescente
  de id: duas operações com os mesmos produtos nunca ficam esperando uma pela
  outra em ciclo (deadlock);
- com as travas na mão, cada produto é relido DIRETO do Xano (sem cache);
- se qualquer produto ficar com estoque negativo, nada é alterado;
- os PATCHs são aplicados um a um; se um falhar, os já aplicados são desfeitos.

PRESSUPOSTO IMPORTANTE: as travas vivem na memória de UM processo. A produção
roda com 1 worker de backend (sem Redis, o Reflex 0.7 usa 1 worker). Se um
dia houver Redis ou mais workers, esta proteção precisa migrar para o Xano
(função com transação). O ambiente de desenvolvimento é outro processo: não é
protegido contra a produção, por isso a regra de testes do README.
"""

from __future__ import annotations

import asyncio

from . import xano_client as xano

TABELA_PRODUTOS = "produtos"

_travas: dict[int, asyncio.Lock] = {}


class EstoqueInsuficiente(Exception):
    """Algum produto ficaria com estoque negativo. `produtos` = nomes."""

    def __init__(self, produtos: list[str]):
        self.produtos = produtos
        super().__init__("Estoque insuficiente: " + ", ".join(produtos))


class ProdutoInexistente(Exception):
    pass


async def _ler_produto(produto_id: int) -> dict | None:
    """Leitura direta do Xano, sem cache: dentro da trava o saldo precisa ser o real."""
    resposta = await xano._request_xano("GET", f"{xano.BASE_URL}/{TABELA_PRODUTOS}/{produto_id}")
    if resposta.status_code == 404:
        return None
    resposta.raise_for_status()
    return resposta.json()


async def _gravar_estoque(produto: dict, novo_estoque: int) -> None:
    dados = {k: v for k, v in produto.items() if k != "id"}  # PATCH do Xano exige o registro completo
    dados["estoque_qtd"] = novo_estoque
    await xano.atualizar(TABELA_PRODUTOS, produto["id"], dados)


async def movimentar(ajustes: dict[int, int]) -> None:
    """Aplica variações de estoque: {id_produto: variação}. Negativa = baixa,
    positiva = devolução. Tudo ou nada: levanta EstoqueInsuficiente (nada é
    alterado) ou a exceção da falha de gravação (o que foi aplicado é desfeito)."""
    ajustes = {int(pid): int(qtd) for pid, qtd in ajustes.items() if int(qtd) != 0}
    if not ajustes:
        return
    ordem = sorted(ajustes)
    travas = [_travas.setdefault(pid, asyncio.Lock()) for pid in ordem]
    for trava in travas:
        await trava.acquire()
    try:
        produtos = {}
        for pid in ordem:
            produto = await _ler_produto(pid)
            if produto is None:
                raise ProdutoInexistente(f"Produto {pid} não existe mais.")
            produtos[pid] = produto

        faltando = [
            f"{produtos[pid]['nome_produto']} (há {produtos[pid]['estoque_qtd']})"
            for pid in ordem
            if (produtos[pid].get("estoque_qtd") or 0) + ajustes[pid] < 0
        ]
        if faltando:
            raise EstoqueInsuficiente(faltando)

        aplicados: list[int] = []
        try:
            for pid in ordem:
                anterior = produtos[pid].get("estoque_qtd") or 0
                await _gravar_estoque(produtos[pid], anterior + ajustes[pid])
                aplicados.append(pid)
        except Exception:
            # desfaz, na medida do possível, o que já tinha sido gravado
            for pid in reversed(aplicados):
                try:
                    await _gravar_estoque(produtos[pid], produtos[pid].get("estoque_qtd") or 0)
                except Exception:
                    pass
            raise
    finally:
        for trava in reversed(travas):
            trava.release()


async def _com_trava(produto_id: int):
    trava = _travas.setdefault(int(produto_id), asyncio.Lock())
    await trava.acquire()
    return trava


async def editar_produto(produto_id: int, alteracoes: dict) -> dict:
    """Altera o cadastro de um produto (nome, preço, categoria...) SEM mexer no
    saldo: relê o produto com a trava na mão e regrava o registro completo
    com o saldo atual. Assim uma venda feita enquanto o formulário estava
    aberto não é desfeita ao salvar."""
    alteracoes = {k: v for k, v in alteracoes.items() if k not in ("id", "estoque_qtd")}
    trava = await _com_trava(produto_id)
    try:
        produto = await _ler_produto(int(produto_id))
        if produto is None:
            raise ProdutoInexistente(f"Produto {produto_id} não existe mais.")
        dados = {k: v for k, v in produto.items() if k != "id"}
        dados.update(alteracoes)
        return await xano.atualizar(TABELA_PRODUTOS, int(produto_id), dados)
    finally:
        trava.release()


async def definir_saldo(produto_id: int, novo_saldo: int) -> tuple[int, int]:
    """Correção de inventário: põe o saldo num valor exato. Devolve
    (saldo anterior, saldo novo). Levanta ValueError se negativo."""
    if int(novo_saldo) < 0:
        raise ValueError("O estoque não pode ficar negativo.")
    trava = await _com_trava(produto_id)
    try:
        produto = await _ler_produto(int(produto_id))
        if produto is None:
            raise ProdutoInexistente(f"Produto {produto_id} não existe mais.")
        anterior = int(produto.get("estoque_qtd") or 0)
        await _gravar_estoque(produto, int(novo_saldo))
        return anterior, int(novo_saldo)
    finally:
        trava.release()

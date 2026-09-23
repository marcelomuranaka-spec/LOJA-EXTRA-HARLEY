"""
Regras de negócio de vendas: registrar uma venda com vários itens e cancelar
vendas (uma ou várias), devolvendo o estoque.

Separado do state da tela (state/vendas_state.py) para poder ser testado
diretamente. Ordem das operações e motivos: ver
openspec/changes/vendas-com-itens-e-cancelamento/design.md (D3 e D4).

Tabelas no Xano:
- transacoes: + status ("ATIVA"/"CANCELADA"; vazio = ativa, vendas antigas),
  data_cancelamento, motivo_cancelamento;
- itens_transacao: transacao_id, produto_id (0 = item avulso), descricao,
  quantidade, valor_unitario. Os nomes seguem a convenção do projeto
  (xano/knowledge/agents.md: chave estrangeira com sufixo _id). ATENÇÃO: o Xano
  ignora em silêncio um campo com nome errado, gravando 0; use as constantes.
"""

from __future__ import annotations

import asyncio

from . import estoque
from . import xano_client as xano

TABELA = "transacoes"
TABELA_ITENS = "itens_transacao"
STATUS_ATIVA = "ATIVA"
STATUS_CANCELADA = "CANCELADA"
MOTIVO_FALHA = "Falha ao registrar os itens da venda"
CAMPO_VENDA = "transacao_id"    # itens_transacao -> transacoes
CAMPO_PRODUTO = "produto_id"    # itens_transacao -> produtos (0 = avulso)

_travas_venda: dict[int, asyncio.Lock] = {}


class FalhaVenda(Exception):
    """Erro com mensagem pronta para mostrar ao funcionário."""


def esta_cancelada(transacao: dict) -> bool:
    return (transacao.get("status") or "").strip().upper() == STATUS_CANCELADA


async def _ler_direto(caminho: str):
    """Leitura sem cache: usada dentro das travas, onde o dado precisa ser o atual."""
    resposta = await xano._request("GET", f"{xano.BASE_URL}/{caminho}")
    if resposta.status_code == 404:
        return None
    resposta.raise_for_status()
    return resposta.json()


async def _itens_da_venda(venda_id: int) -> list[dict]:
    itens = await _ler_direto(TABELA_ITENS) or []
    return [i for i in itens if int(i.get(CAMPO_VENDA) or 0) == venda_id]


async def _marcar_cancelada(venda: dict, motivo: str) -> None:
    dados = {k: v for k, v in venda.items() if k != "id"}  # PATCH do Xano exige o registro completo
    dados["status"] = STATUS_CANCELADA
    dados["data_cancelamento"] = xano.datetime_para_epoch_ms()
    dados["motivo_cancelamento"] = (motivo or "").strip() or None
    await xano.atualizar(TABELA, venda["id"], dados)


# ---------------------------------------------------------------- registro

async def registrar_venda(
    tipo: str, id_funcionario: int, id_cliente: int, id_moto: int, itens: list[dict]
) -> int:
    """itens: [{id_produto (0 = avulso), descricao, quantidade, valor_unitario}].
    Devolve o id da venda. Levanta FalhaVenda com mensagem para o usuário."""
    if not itens:
        raise FalhaVenda("Adicione ao menos um item à venda.")

    baixas: dict[int, int] = {}
    for item in itens:
        if int(item["id_produto"]):
            baixas[int(item["id_produto"])] = baixas.get(int(item["id_produto"]), 0) - int(item["quantidade"])
    total = round(sum(int(i["quantidade"]) * float(i["valor_unitario"]) for i in itens), 2)

    # 1) baixa todo o estoque, ou nada
    try:
        await estoque.movimentar(baixas)
    except estoque.EstoqueInsuficiente as erro:
        raise FalhaVenda("Estoque insuficiente: " + ", ".join(erro.produtos) + ". Nada foi alterado.")
    except estoque.ProdutoInexistente as erro:
        raise FalhaVenda(f"{erro} Remova o item e tente de novo.")
    except Exception:
        raise FalhaVenda("Não foi possível conectar ao banco. Nada foi alterado; tente de novo.")

    devolucao = {pid: -qtd for pid, qtd in baixas.items()}

    # 2) cria a venda ativa
    try:
        venda = await xano.criar(TABELA, {
            "tipo_transacao": tipo,
            "id_funcionario": id_funcionario,
            "id_cliente": id_cliente,
            "id_moto_cliente": id_moto,
            "data_transacao": xano.datetime_para_epoch_ms(),
            "valor_total": total,
            "status": STATUS_ATIVA,
            "data_cancelamento": None,
            "motivo_cancelamento": None,
        })
    except Exception:
        await _devolver_sem_falhar(devolucao)
        raise FalhaVenda("A venda não pôde ser registrada (falha de conexão). O estoque foi devolvido; tente de novo.")

    # 3) grava os itens
    try:
        for item in itens:
            gravado = await xano.criar(TABELA_ITENS, {
                CAMPO_VENDA: venda["id"],
                CAMPO_PRODUTO: int(item["id_produto"]),
                "descricao": item["descricao"],
                "quantidade": int(item["quantidade"]),
                "valor_unitario": float(item["valor_unitario"]),
            })
            # O Xano ignora em silêncio campos com nome diferente do schema e
            # grava 0: confere que o item ficou mesmo ligado à venda.
            if int(gravado.get(CAMPO_VENDA) or 0) != int(venda["id"]):
                raise RuntimeError(f"item gravado sem vínculo com a venda ({CAMPO_VENDA})")
    except Exception:
        await _devolver_sem_falhar(devolucao)
        try:
            await _marcar_cancelada(venda, MOTIVO_FALHA)
        except Exception:
            pass
        raise FalhaVenda(
            f"Os itens da venda nº {venda['id']} não puderam ser gravados (falha de conexão). "
            "O estoque foi devolvido e a venda ficou cancelada; registre-a de novo."
        )
    return int(venda["id"])


async def _devolver_sem_falhar(ajustes: dict[int, int]) -> None:
    try:
        await estoque.movimentar(ajustes)
    except Exception:
        pass


# ------------------------------------------------------------ cancelamento

async def cancelar_venda(venda_id: int, motivo: str = "") -> dict:
    """Devolve {"situacao": "cancelada"|"ja_cancelada"|"erro", "mensagem": str}.
    Marca a venda como cancelada ANTES de devolver o estoque: uma nova
    tentativa nunca devolve em dobro (design D4)."""
    venda_id = int(venda_id)
    async with _travas_venda.setdefault(venda_id, asyncio.Lock()):
        try:
            venda = await _ler_direto(f"{TABELA}/{venda_id}")
        except Exception:
            return {"situacao": "erro", "mensagem": f"Venda nº {venda_id}: falha de conexão, tente de novo."}
        if venda is None:
            return {"situacao": "erro", "mensagem": f"Venda nº {venda_id} não existe."}
        if esta_cancelada(venda):
            return {"situacao": "ja_cancelada", "mensagem": f"Venda nº {venda_id} já estava cancelada."}

        try:
            await _marcar_cancelada(venda, motivo)
        except Exception:
            return {"situacao": "erro", "mensagem": f"Venda nº {venda_id}: falha de conexão, nada foi alterado."}

        try:
            itens = await _itens_da_venda(venda_id)
        except Exception:
            return {"situacao": "cancelada", "mensagem":
                    f"Venda nº {venda_id} cancelada, mas os itens não puderam ser lidos: confira o estoque manualmente."}
        if not itens:
            return {"situacao": "cancelada", "mensagem":
                    f"Venda nº {venda_id} cancelada. Ela é anterior ao registro de itens: confira o estoque manualmente."}

        devolucao: dict[int, int] = {}
        for item in itens:
            pid = int(item.get(CAMPO_PRODUTO) or 0)
            if pid:
                devolucao[pid] = devolucao.get(pid, 0) + int(item.get("quantidade") or 0)
        try:
            await estoque.movimentar(devolucao)
        except Exception:
            nomes = ", ".join(sorted({i.get("descricao") or f"produto {i.get(CAMPO_PRODUTO)}" for i in itens
                                      if int(i.get(CAMPO_PRODUTO) or 0)}))
            return {"situacao": "cancelada", "mensagem":
                    f"Venda nº {venda_id} cancelada, mas o estoque não pôde ser devolvido ({nomes}): ajuste manualmente."}
        return {"situacao": "cancelada", "mensagem": ""}


async def cancelar_varias(ids: list[int], motivo: str = "") -> list[dict]:
    """Uma de cada vez (não estoura o limite de requisições do Xano Free)."""
    resultados = []
    for venda_id in ids:
        resultado = await cancelar_venda(venda_id, motivo)
        resultado["id"] = int(venda_id)
        resultados.append(resultado)
    return resultados

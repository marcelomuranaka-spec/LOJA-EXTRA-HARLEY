"""
Regras das motos da loja (tabela `motos`): situação (status), venda e
desfazer venda, com trava por moto.

Situações. A tela mostra "Disponível", mas o valor gravado continua sendo
"Em estoque": o bot do Telegram (n8n/workflows/consultar_motos.json) e
registros antigos usam esse valor, e trocá-lo exigiria migrar dados.
    gravado            na tela
    Em estoque         Disponível
    Reservada          Reservada
    Consignada         Consignada        (moto de terceiro à venda na loja)
    Em manutenção      Em manutenção
    Fora de estoque    Fora de estoque
    Vendida            Vendida

O campo `em_estoque` (usado no Painel) acompanha a situação: só "Vendida" e
"Fora de estoque" ficam fora do estoque.

Venda pelo balcão: a moto precisa estar Disponível, Reservada ou Consignada.
`marcar_vendida` relê a moto direto do Xano com a trava na mão (duas vendas
da mesma moto ao mesmo tempo: só uma passa) e devolve o registro anterior,
para `desfazer` restaurar se a venda falhar ou for cancelada.
"""

from __future__ import annotations

import asyncio

from . import formatacao as fmt
from . import xano_client as xano

TABELA = "motos"
DISPONIVEL = "Em estoque"
VENDIDA = "Vendida"
SITUACOES = [
    (DISPONIVEL, "Disponível"),
    ("Reservada", "Reservada"),
    ("Consignada", "Consignada"),
    ("Em manutenção", "Em manutenção"),
    ("Fora de estoque", "Fora de estoque"),
    (VENDIDA, "Vendida"),
]
ROTULOS = dict(SITUACOES)
VALORES = {rotulo: valor for valor, rotulo in SITUACOES}
VENDAVEIS = {DISPONIVEL, "Reservada", "Consignada"}
FORA_DO_ESTOQUE = {VENDIDA, "Fora de estoque"}
CORES = {DISPONIVEL: "green", "Reservada": "amber", "Consignada": "blue", "Em manutenção": "purple",
         "Fora de estoque": "gray", VENDIDA: "red"}

_travas: dict[int, asyncio.Lock] = {}


class MotoIndisponivel(Exception):
    """Mensagem pronta para o usuário."""


def situacao(registro: dict) -> str:
    valor = (registro.get("status") or "").strip()
    return valor if valor in ROTULOS else DISPONIVEL


def rotulo(registro: dict) -> str:
    return ROTULOS[situacao(registro)]


def em_estoque(status: str) -> bool:
    return status not in FORA_DO_ESTOQUE


def descricao(registro: dict) -> str:
    partes = [registro.get("marca") or "", registro.get("modelo") or ""]
    if registro.get("ano"):
        partes.append(str(registro["ano"]))
    texto = " ".join(p for p in partes if p).strip() or f"Moto nº {registro.get('id')}"
    return f"{texto} ({registro['placa']})" if registro.get("placa") else texto


async def marcar_vendida(moto_id: int, cliente_id: int) -> dict:
    """Marca a moto como vendida para o cliente. Devolve o registro ANTERIOR.
    Levanta MotoIndisponivel."""
    trava = _travas.setdefault(int(moto_id), asyncio.Lock())
    async with trava:
        atual = await xano.ler_direto(TABELA, moto_id)
        if atual is None:
            raise MotoIndisponivel("Essa moto não existe mais.")
        if situacao(atual) not in VENDAVEIS:
            raise MotoIndisponivel(f"A moto {descricao(atual)} está como {rotulo(atual)} e não pode ser vendida.")
        dados = {k: v for k, v in atual.items() if k != "id"}
        dados.update({
            "status": VENDIDA,
            "em_estoque": False,
            "data_saida": xano.datetime_para_epoch_ms(),
            "cliente_id": int(cliente_id or 0),
        })
        await xano.atualizar(TABELA, moto_id, dados)
        return atual


async def desfazer(moto_id: int, anterior: dict | None = None) -> None:
    """Devolve a moto à situação anterior (ou Disponível, sem cliente e sem
    data de saída, quando a anterior não é conhecida — cancelamento)."""
    trava = _travas.setdefault(int(moto_id), asyncio.Lock())
    async with trava:
        atual = await xano.ler_direto(TABELA, moto_id)
        if atual is None:
            return
        dados = {k: v for k, v in atual.items() if k != "id"}
        if anterior:
            for campo in ("status", "em_estoque", "data_saida", "cliente_id"):
                dados[campo] = anterior.get(campo)
        else:
            dados.update({"status": DISPONIVEL, "em_estoque": True, "data_saida": 0, "cliente_id": 0})
        await xano.atualizar(TABELA, moto_id, dados)


def opcao_venda(registro: dict) -> str:
    """Texto do seletor no balcão: "2 - Harley-Davidson Fat Boy 2020 (ABC1D23) — R$ 95.000,00"."""
    return f"{registro['id']} - {descricao(registro)} — R$ {fmt.moeda(registro.get('preco_venda') or 0)}"

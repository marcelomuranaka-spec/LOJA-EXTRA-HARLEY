"""
State do Painel (dashboard).

A lista `atividades_recentes` reproduz em Python a ideia da view SQL
original `vw_resumo_operacoes` (que juntava Transacoes + Entrada de
Mercadoria num só extrato) — um bom exemplo de como combinar duas
tabelas num só relatório dentro de um State, caso você queira montar
outros relatórios parecidos no futuro.

Dados vêm do backend Xano.
"""

import asyncio
import datetime

import reflex as rx

from .. import xano_client as xano
from ..vendas_servico import esta_cancelada

LIMITE_ESTOQUE_BAIXO = 5
MESES = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]


def _moeda(valor: float) -> str:
    """1234.5 -> "1.234,50" (formato brasileiro)."""
    return f"{valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


class DashboardState(rx.State):
    total_produtos: int = 0
    produtos_estoque_baixo: int = 0
    total_clientes: int = 0
    os_em_aberto: int = 0
    faturamento_hoje: str = "0,00"
    faturamento_mes: str = "0,00"
    atividades_recentes: list[dict] = []

    # Motos da loja (tabela `motos`)
    motos_em_estoque: int = 0
    valor_estoque_motos: str = "0,00"
    motos_vendidas_mes: int = 0

    # Gráfico: faturamento por mês, últimos 12 meses ({"mes": "set/26", "valor": 1234.5})
    faturamento_12_meses: list[dict] = []

    @rx.event
    async def carregar(self):
        hoje = datetime.date.today()
        inicio_hoje = datetime.datetime.combine(hoje, datetime.time.min)
        inicio_mes = datetime.datetime.combine(hoje.replace(day=1), datetime.time.min)

        # As 8 tabelas são buscadas em paralelo: em sequência o painel levava
        # ~12 s para abrir (cada chamada ao Xano Free leva 1–2 s). Se o Xano
        # devolver 429 (limite por minuto), `_request` já refaz a chamada.
        (
            produtos, lista_clientes, motos, ordens, transacoes,
            lista_funcionarios, lista_fornecedores, entradas,
        ) = await asyncio.gather(
            *(
                xano.listar(tabela)
                for tabela in (
                    "produtos", "clientes", "motos", "ordens_servico", "transacoes",
                    "funcionarios", "fornecedores", "entrada_mercadoria",
                )
            )
        )

        self.total_produtos = len(produtos)
        self.produtos_estoque_baixo = sum(1 for p in produtos if p["estoque_qtd"] <= LIMITE_ESTOQUE_BAIXO)

        self.total_clientes = len(lista_clientes)

        em_estoque = [m for m in motos if m.get("em_estoque")]
        self.motos_em_estoque = len(em_estoque)
        valor = sum(m.get("preco_venda") or 0 for m in em_estoque)
        self.valor_estoque_motos = _moeda(valor)
        self.motos_vendidas_mes = sum(
            1
            for m in motos
            if m.get("status") == "Vendida"
            and m.get("data_saida")
            and xano.epoch_ms_para_datetime(m["data_saida"]) >= inicio_mes
        )

        self.os_em_aberto = sum(1 for o in ordens if o["status"] in ("ABERTA", "EM_ANDAMENTO"))

        transacoes_com_data = [
            (t, xano.epoch_ms_para_datetime(t["data_transacao"])) for t in transacoes
        ]
        # Vendas canceladas continuam no histórico, mas não entram no faturamento.
        validas = [(t, d) for t, d in transacoes_com_data if not esta_cancelada(t)]
        self.faturamento_hoje = _moeda(sum(t["valor_total"] or 0 for t, d in validas if d >= inicio_hoje))
        self.faturamento_mes = _moeda(sum(t["valor_total"] or 0 for t, d in validas if d >= inicio_mes))

        por_mes = {}
        for i in range(11, -1, -1):
            ano, mes = divmod(hoje.year * 12 + hoje.month - 1 - i, 12)
            por_mes[(ano, mes + 1)] = 0.0
        for t, d in validas:
            if (d.year, d.month) in por_mes:
                por_mes[(d.year, d.month)] += t["valor_total"] or 0
        self.faturamento_12_meses = [
            {"mes": f"{MESES[m - 1]}/{a % 100:02d}", "valor": round(v, 2)} for (a, m), v in por_mes.items()
        ]

        funcionarios = {f["id"]: f["nome_funcionario"] for f in lista_funcionarios}
        clientes = {c["id"]: c["nome_cliente"] for c in lista_clientes}
        fornecedores = {f["id"]: f["nome_fornecedor"] for f in lista_fornecedores}

        atividades = [
            {
                "origem": "Venda (cancelada)" if esta_cancelada(t) else "Venda",
                "tipo": t["tipo_transacao"],
                "quem": clientes.get(t.get("id_cliente"), funcionarios.get(t["id_funcionario"], "—")),
                "data": d,
                "valor": t["valor_total"],
            }
            for t, d in transacoes_com_data
        ] + [
            {
                "origem": "Compra",
                "tipo": "ENTRADA ESTOQUE",
                "quem": fornecedores.get(e["id_fornecedor"], "—"),
                "data": xano.epoch_ms_para_datetime(e["data_entrada"]),
                "valor": e["valor_total"],
            }
            for e in entradas
        ]
        atividades.sort(key=lambda a: a["data"], reverse=True)

        self.atividades_recentes = [
            {
                "origem": a["origem"],
                "tipo": a["tipo"],
                "quem": a["quem"],
                "data": a["data"].strftime("%d/%m/%Y %H:%M"),
                "valor": _moeda(a["valor"]),
            }
            for a in atividades[:12]
        ]

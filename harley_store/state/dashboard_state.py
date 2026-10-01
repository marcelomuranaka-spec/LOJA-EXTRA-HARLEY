"""
State do Painel (dashboard). Todos os números vêm do Xano (nenhum é fictício).

A lista `atividades_recentes` reproduz em Python a ideia da view SQL
original `vw_resumo_operacoes` (que juntava Transacoes + Entrada de
Mercadoria num só extrato). Vendas canceladas continuam no histórico, mas
não entram no faturamento nem nas contagens de vendas.

Indicadores que dependem de tabelas novas (leads) mostram "—" enquanto a
tabela não existe no Xano.
"""

import asyncio
import datetime

import reflex as rx

from .. import formatacao as fmt
from .. import leads_servico, motos_loja_servico, produtos_servico, recursos
from .. import xano_client as xano
from ..vendas_servico import esta_cancelada
from .auth_state import AuthState

MESES = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]


def _moeda(valor: float) -> str:
    """1234.5 -> "1.234,50" (formato brasileiro)."""
    return fmt.moeda(valor)


class DashboardState(rx.State):
    total_produtos: int = 0
    produtos_em_estoque: int = 0
    unidades_em_estoque: int = 0
    produtos_estoque_baixo: int = 0
    total_clientes: int = 0
    clientes_novos_mes: str = "—"
    os_em_aberto: int = 0
    faturamento_hoje: str = "0,00"
    faturamento_mes: str = "0,00"
    vendas_hoje: int = 0
    vendas_mes: int = 0
    ticket_medio_mes: str = "0,00"
    atividades_recentes: list[dict] = []
    vendas_recentes: list[dict] = []

    # Motos da loja (tabela `motos`)
    motos_disponiveis: int = 0
    motos_em_estoque: int = 0
    valor_estoque_motos: str = "0,00"
    motos_vendidas_mes: int = 0
    motos_vendidas_total: int = 0

    # Leads (tabela nova `leads`)
    tem_leads: bool = False
    leads_novos: str = "—"
    leads_abertos: str = "—"
    leads_recentes: list[dict] = []

    # Recursos aguardando o Xano (só para administradores)
    recursos_pendentes: int = 0

    # Gráfico: faturamento por mês, últimos 12 meses ({"mes": "set/26", "valor": 1234.5})
    faturamento_12_meses: list[dict] = []

    @rx.event
    async def carregar(self):
        hoje = datetime.date.today()
        inicio_hoje = datetime.datetime.combine(hoje, datetime.time.min)
        inicio_mes = datetime.datetime.combine(hoje.replace(day=1), datetime.time.min)

        # As tabelas são lidas em paralelo, do cache do servidor (ver xano_client).
        (
            produtos, lista_clientes, motos, ordens, transacoes,
            lista_funcionarios, lista_fornecedores, entradas, leads,
        ) = await asyncio.gather(
            *(xano.listar(tabela) for tabela in (
                "produtos", "clientes", "motos", "ordens_servico", "transacoes",
                "funcionarios", "fornecedores", "entrada_mercadoria",
            )),
            xano.listar_se_existir("leads"),
        )

        ativos = [p for p in produtos if produtos_servico.ativo(p)]
        self.total_produtos = len(ativos)
        self.produtos_em_estoque = sum(1 for p in ativos if int(p.get("estoque_qtd") or 0) > 0)
        self.unidades_em_estoque = sum(max(0, int(p.get("estoque_qtd") or 0)) for p in ativos)
        self.produtos_estoque_baixo = sum(1 for p in ativos if produtos_servico.estoque_baixo(p))

        self.total_clientes = len(lista_clientes)
        if any("created_at" in c for c in lista_clientes):
            self.clientes_novos_mes = str(sum(
                1 for c in lista_clientes
                if c.get("created_at") and xano.epoch_ms_para_datetime(c["created_at"]) >= inicio_mes))
        else:
            self.clientes_novos_mes = "—"

        disponiveis = [m for m in motos if motos_loja_servico.situacao(m) in motos_loja_servico.VENDAVEIS]
        self.motos_disponiveis = len(disponiveis)
        self.motos_em_estoque = sum(1 for m in motos if m.get("em_estoque"))
        self.valor_estoque_motos = _moeda(sum(m.get("preco_venda") or 0 for m in disponiveis))
        vendidas = [m for m in motos if motos_loja_servico.situacao(m) == motos_loja_servico.VENDIDA]
        self.motos_vendidas_total = len(vendidas)
        self.motos_vendidas_mes = sum(
            1 for m in vendidas
            if m.get("data_saida") and xano.epoch_ms_para_datetime(m["data_saida"]) >= inicio_mes
        )

        self.os_em_aberto = sum(1 for o in ordens if o["status"] in ("ABERTA", "EM_ANDAMENTO"))

        transacoes_com_data = [
            (t, xano.epoch_ms_para_datetime(t["data_transacao"])) for t in transacoes
        ]
        # Vendas canceladas continuam no histórico, mas não entram no faturamento.
        validas = [(t, d) for t, d in transacoes_com_data if not esta_cancelada(t)]
        do_mes = [t for t, d in validas if d >= inicio_mes]
        faturado_mes = sum(t["valor_total"] or 0 for t in do_mes)
        self.faturamento_hoje = _moeda(sum(t["valor_total"] or 0 for t, d in validas if d >= inicio_hoje))
        self.faturamento_mes = _moeda(faturado_mes)
        self.vendas_hoje = sum(1 for _, d in validas if d >= inicio_hoje)
        self.vendas_mes = len(do_mes)
        self.ticket_medio_mes = _moeda(faturado_mes / len(do_mes) if do_mes else 0)

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

        self.vendas_recentes = [
            {
                "id": str(t["id"]),
                "data": d.strftime("%d/%m %H:%M"),
                "cliente_id": str(t.get("id_cliente") or 0),
                "cliente": clientes.get(t.get("id_cliente"), "Balcão (sem cliente)"),
                "valor": _moeda(t["valor_total"] or 0),
                "cancelada": esta_cancelada(t),
            }
            for t, d in sorted(transacoes_com_data, key=lambda par: par[1], reverse=True)[:8]
        ]

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

        self.tem_leads = leads is not None
        if leads is not None:
            linhas = [leads_servico.linha_lead(l) for l in leads]
            self.leads_novos = str(sum(1 for l in linhas if l["status"] == "Novo"))
            self.leads_abertos = str(sum(1 for l in linhas if l["aberto"]))
            self.leads_recentes = sorted(linhas, key=lambda l: (l["criado_em"], int(l["id"])), reverse=True)[:6]
        else:
            self.leads_novos = self.leads_abertos = "—"
            self.leads_recentes = []

        auth = await self.get_state(AuthState)
        if auth.admin_confirmado():
            itens = await recursos.situacao(conferir_upload=False)
            # o endpoint de upload não é conferido aqui (custaria uma requisição a cada abertura do painel)
            self.recursos_pendentes = sum(1 for i in itens if not i["ativo"] and i["tipo"] != "endpoint")
        else:
            self.recursos_pendentes = 0

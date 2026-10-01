"""
State do histórico de e-mails (/emails): todos os envios e tentativas, com
destinatário, assunto, data, situação, erro e cliente/lead relacionado.

O envio em si acontece na ficha do cliente ou do lead (sempre manual), pelo
`email_servico.py`. Depende da tabela `emails` no Xano.
"""

import asyncio

import reflex as rx

from .. import email_servico, recursos
from .. import formatacao as fmt
from .. import xano_client as xano

SITUACOES = ["Todas", email_servico.ENVIADO, email_servico.FALHOU, email_servico.NAO_CONFIGURADO]


class EmailsState(rx.State):
    tabela_existe: bool = True
    sendgrid_ok: bool = False
    emails: list[dict] = []
    busca: str = ""
    filtro_status: str = "Todas"
    _linhas: list[dict] = []

    @rx.var
    def situacoes(self) -> list[str]:
        return SITUACOES

    @rx.event
    async def carregar(self):
        registros, clientes, leads = await asyncio.gather(
            xano.listar_se_existir(email_servico.TABELA), xano.listar("clientes"), xano.listar_se_existir("leads"))
        self.tabela_existe = registros is not None
        self.sendgrid_ok = recursos.sendgrid_configurado()
        nomes_clientes = {c["id"]: c["nome_cliente"] for c in clientes}
        nomes_leads = {l["id"]: l.get("nome") or "" for l in (leads or [])}
        self._linhas = [
            {
                "id": str(r["id"]),
                "data": fmt.data_hora(r.get("created_at")),
                "epoch": fmt.epoch(r.get("created_at")),
                "destinatario": r.get("destinatario") or "",
                "assunto": r.get("assunto") or "",
                "status": r.get("status") or "",
                "erro": r.get("erro") or "",
                "cliente_id": str(r.get("cliente_id") or 0),
                "cliente_nome": nomes_clientes.get(int(r.get("cliente_id") or 0), ""),
                "lead_nome": nomes_leads.get(int(r.get("lead_id") or 0), ""),
            }
            for r in (registros or [])
        ]
        self._linhas.sort(key=lambda l: (l["epoch"], int(l["id"])), reverse=True)
        self._aplicar()

    def _aplicar(self):
        termo = self.busca.strip().lower()
        self.emails = [
            l for l in self._linhas
            if (self.filtro_status == "Todas" or l["status"] == self.filtro_status)
            and (not termo or termo in f"{l['destinatario']} {l['assunto']} {l['cliente_nome']} {l['lead_nome']}".lower())
        ][:200]

    @rx.event
    def definir_busca(self, valor: str):
        self.busca = valor
        self._aplicar()

    @rx.event
    def definir_filtro_status(self, valor: str):
        self.filtro_status = valor
        self._aplicar()

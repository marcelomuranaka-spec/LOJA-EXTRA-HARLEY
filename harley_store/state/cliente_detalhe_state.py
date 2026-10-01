"""
State da ficha do cliente (/clientes/<id>) — a visão 360º: dados, motos,
compras, ordens de serviço, orçamentos, interações, e-mails, observações e
uma linha do tempo com tudo junto.

Interações e e-mails dependem das tabelas `interacoes` e `emails` no Xano
(ver `recursos.py`); sem elas, a ficha mostra o resto normalmente.
Orçamentos são interações do tipo "Orçamento enviado".
"""

import asyncio

import reflex as rx

from .. import clientes_servico as servico
from .. import email_servico, recursos
from .. import formatacao as fmt
from .. import xano_client as xano
from .auth_state import AuthState

TIPO_ORCAMENTO = "Orçamento enviado"
TIPOS_INTERACAO = ["Contato", "Solicitou informações", TIPO_ORCAMENTO, "Visita à loja", "Test ride",
                   "Negociação", "Pós-venda", "Reclamação", "Outro"]


class ClienteDetalheState(rx.State):
    cliente_id_atual: int = 0
    encontrado: bool = True
    cliente: dict = servico.CLIENTE_VAZIO
    motos: list[dict] = []
    compras: list[dict] = []
    ordens: list[dict] = []
    interacoes: list[dict] = []
    orcamentos: list[dict] = []
    emails: list[dict] = []
    linha_do_tempo: list[dict] = []
    total_gasto: str = "R$ 0,00"
    qtd_compras: int = 0
    ultima_compra: str = "—"

    tem_interacoes: bool = False
    tem_emails: bool = False
    sendgrid_ok: bool = False

    dialogo_interacao: bool = False
    int_tipo: str = TIPOS_INTERACAO[0]
    int_descricao: str = ""
    erro_int: str = ""

    dialogo_email: bool = False
    email_assunto: str = ""
    email_mensagem: str = ""
    erro_email: str = ""

    @rx.var
    def tipos_interacao(self) -> list[str]:
        return TIPOS_INTERACAO

    @rx.event
    async def carregar(self):
        bruto = self.router.page.params.get("cliente_id", "")
        if not str(bruto).isdigit():
            self.encontrado = False
            return
        cliente_id = int(bruto)
        self.cliente_id_atual = cliente_id
        clientes, motos, transacoes, itens, ordens, interacoes, emails, leads = await asyncio.gather(
            xano.listar(servico.TABELA), xano.listar(servico.TABELA_MOTOS), xano.listar("transacoes"),
            xano.listar("itens_transacao"), xano.listar("ordens_servico"),
            xano.listar_se_existir("interacoes"), xano.listar_se_existir("emails"),
            xano.listar_se_existir("leads"),
        )
        registro = next((c for c in clientes if c["id"] == cliente_id), None)
        if registro is None:
            self.encontrado = False
            return
        self.encontrado = True
        self.tem_interacoes = interacoes is not None
        self.tem_emails = emails is not None
        self.sendgrid_ok = recursos.sendgrid_configurado()

        self.cliente = servico.linha_cliente(registro)
        motos_do_cliente = [m for m in motos if int(m.get("id_cliente") or 0) == cliente_id]
        self.motos = [servico.linha_moto(m, registro["nome_cliente"])
                      for m in sorted(motos_do_cliente, key=lambda m: m.get("modelo") or "")]
        compras = servico.montar_compras(cliente_id, transacoes, itens)
        self.compras = compras
        validas = [c for c in compras if not c["cancelada"]]
        self.qtd_compras = len(validas)
        self.total_gasto = fmt.reais(sum(c["valor"] for c in validas))
        self.ultima_compra = validas[0]["data"].split(" ")[0] if validas else "—"
        self.ordens = servico.montar_ordens(motos_do_cliente, ordens)
        # interações do lead que virou este cliente também contam na história dele
        leads_do_cliente = {int(l["id"]) for l in (leads or []) if int(l.get("cliente_id") or 0) == cliente_id}
        interacoes_cliente = [
            {**i, "cliente_id": cliente_id} for i in (interacoes or [])
            if int(i.get("cliente_id") or 0) == cliente_id or int(i.get("lead_id") or 0) in leads_do_cliente
        ]
        self.interacoes = servico.montar_interacoes(interacoes_cliente, "cliente_id", cliente_id)
        self.orcamentos = [i for i in self.interacoes if i["tipo"] == TIPO_ORCAMENTO]
        self.emails = servico.montar_emails(emails or [], "cliente_id", cliente_id)
        self.linha_do_tempo = servico.montar_linha_do_tempo(registro, compras, self.ordens,
                                                            self.interacoes, self.emails)

    # ----------------------------------------------------------- interação

    @rx.event
    def abrir_interacao(self, tipo: str = ""):
        self.int_tipo = tipo or TIPOS_INTERACAO[0]
        self.int_descricao = ""
        self.erro_int = ""
        self.dialogo_interacao = True

    @rx.event
    def fechar_interacao(self):
        self.dialogo_interacao = False

    @rx.event
    async def salvar_interacao(self):
        descricao = self.int_descricao.strip()
        if not descricao:
            self.erro_int = "Descreva o que aconteceu."
            return
        if self.int_tipo not in TIPOS_INTERACAO:
            self.erro_int = "Escolha o tipo."
            return
        auth = await self.get_state(AuthState)
        try:
            await xano.criar("interacoes", {
                "cliente_id": self.cliente_id_atual, "lead_id": 0, "tipo": self.int_tipo,
                "descricao": descricao, "usuario_id": auth.usuario_id,
            })
        except xano.TabelaInexistente:
            self.erro_int = "A tabela de interações ainda não existe no Xano (ver Configuração)."
            return
        except Exception:
            self.erro_int = "Não foi possível salvar (falha de conexão). Tente de novo."
            return
        self.dialogo_interacao = False
        await self.carregar()
        return rx.toast.success("Interação registrada.")

    # -------------------------------------------------------------- e-mail

    @rx.event
    def abrir_email(self):
        if not self.cliente.get("email"):
            return rx.toast.error("Este cliente não tem e-mail cadastrado. Edite o cadastro primeiro.")
        self.email_assunto = ""
        self.email_mensagem = f"Olá, {self.cliente.get('nome_cliente', '').split(' ')[0]}!\n\n"
        self.erro_email = ""
        self.dialogo_email = True

    @rx.event
    def fechar_email(self):
        self.dialogo_email = False

    @rx.event
    async def enviar_email(self):
        auth = await self.get_state(AuthState)
        resultado = await email_servico.enviar(
            self.cliente.get("email", ""), self.email_assunto, self.email_mensagem,
            cliente_id=self.cliente_id_atual, usuario_id=auth.usuario_id,
        )
        if not resultado.enviado:
            self.erro_email = f"{resultado.status}: {resultado.erro}." + (
                " A tentativa ficou registrada no histórico." if resultado.registrado else "")
            if resultado.registrado:
                await self.carregar()
            return
        self.dialogo_email = False
        await self.carregar()
        return rx.toast.success("E-mail enviado." + ("" if resultado.registrado else
                                " (O histórico de e-mails ainda não existe no Xano.)"))

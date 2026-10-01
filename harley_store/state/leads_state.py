"""
State de Leads (/leads): funil, cadastro, ficha do lead com interações,
conversão em cliente e envio de e-mail.

Depende da tabela `leads` no Xano; sem ela a tela mostra como ativar.
Interações do lead usam a tabela `interacoes` (campo lead_id) e e-mails, a
tabela `emails`. Regras: `leads_servico.py`.
"""

import asyncio
from typing import Optional

import reflex as rx

from .. import clientes_servico, email_servico, recursos
from .. import leads_servico as servico
from .. import motos_loja_servico as motos_loja
from .. import xano_client as xano
from .auth_state import AuthState

TIPOS_INTERACAO = ["Contato", "Solicitou informações", "Orçamento enviado", "Visita à loja", "Test ride",
                   "Negociação", "Outro"]


class LeadsState(rx.State):
    tabela_existe: bool = True
    tem_interacoes: bool = False
    sendgrid_ok: bool = False
    leads: list[dict] = []
    funil: list[dict] = []
    busca: str = ""
    filtro_status: str = "Em aberto"
    filtro_origem: str = "Todas"
    motos_opcoes: list[str] = []

    # formulário
    dialogo_aberto: bool = False
    form_id: Optional[int] = None
    nome: str = ""
    telefone: str = ""
    telegram: str = ""
    email: str = ""
    origem: str = servico.ORIGENS[0]
    interesse: str = servico.INTERESSES[0]
    moto_interesse: str = ""
    moto_id: str = ""
    observacao: str = ""
    status: str = "Novo"
    erro_form: str = ""

    # ficha do lead
    dialogo_ver: bool = False
    lead: dict = servico.LEAD_VAZIO
    interacoes: list[dict] = []
    emails: list[dict] = []
    int_tipo: str = TIPOS_INTERACAO[0]
    int_descricao: str = ""
    erro_int: str = ""

    # conversão
    dialogo_converter: bool = False
    conv_documento: str = ""
    erro_conv: str = ""

    # e-mail
    dialogo_email: bool = False
    email_assunto: str = ""
    email_mensagem: str = ""
    erro_email: str = ""

    _linhas: list[dict] = []

    @rx.var
    def opcoes_status(self) -> list[str]:
        return servico.STATUS_LEAD

    @rx.var
    def filtros_status(self) -> list[str]:
        return ["Em aberto", "Todos", *servico.STATUS_LEAD]

    @rx.var
    def origens(self) -> list[str]:
        return servico.ORIGENS

    @rx.var
    def filtros_origem(self) -> list[str]:
        return ["Todas", *servico.ORIGENS]

    @rx.var
    def interesses(self) -> list[str]:
        return servico.INTERESSES

    @rx.var
    def tipos_interacao(self) -> list[str]:
        return TIPOS_INTERACAO

    # ------------------------------------------------------------ listagem

    @rx.event
    async def carregar(self):
        leads, motos, clientes, interacoes = await asyncio.gather(
            xano.listar_se_existir(servico.TABELA), xano.listar("motos"), xano.listar("clientes"),
            xano.listar_se_existir("interacoes"),
        )
        self.tabela_existe = leads is not None
        self.tem_interacoes = interacoes is not None
        self.sendgrid_ok = recursos.sendgrid_configurado()
        motos_por_id = {m["id"]: motos_loja.descricao(m) for m in motos}
        self.motos_opcoes = ["0 - nenhuma"] + [
            f"{m['id']} - {motos_loja.descricao(m)}" for m in motos if motos_loja.situacao(m) in motos_loja.VENDAVEIS
        ]
        clientes_por_id = {c["id"]: c["nome_cliente"] for c in clientes}
        self._linhas = [servico.linha_lead(r, motos_por_id, clientes_por_id) for r in (leads or [])]
        self.funil = servico.contagem_funil(self._linhas)
        self._aplicar()
        if self.dialogo_ver and self.lead.get("id"):
            await self._carregar_ficha(self.lead["id"])

    def _aplicar(self):
        self.leads = servico.filtrar(self._linhas, self.busca, self.filtro_status, self.filtro_origem)

    @rx.event
    def definir_busca(self, valor: str):
        self.busca = valor
        self._aplicar()

    @rx.event
    def definir_filtro_status(self, valor: str):
        self.filtro_status = valor
        self._aplicar()

    @rx.event
    def definir_filtro_origem(self, valor: str):
        self.filtro_origem = valor
        self._aplicar()

    # ---------------------------------------------------------- formulário

    def _preencher(self, linha: dict | None):
        linha = linha or {}
        self.form_id = int(linha["id"]) if linha.get("id") else None
        self.nome = linha.get("nome", "")
        self.telefone = linha.get("telefone", "")
        self.telegram = linha.get("telegram", "")
        self.email = linha.get("email", "")
        self.origem = linha.get("origem") or servico.ORIGENS[0]
        self.interesse = linha.get("interesse") or servico.INTERESSES[0]
        self.moto_interesse = linha.get("moto_interesse", "")
        mid = linha.get("moto_id", "0")
        self.moto_id = next((o for o in self.motos_opcoes if o.startswith(f"{mid} - ")), self.motos_opcoes[0]
                            if self.motos_opcoes else "")
        self.observacao = linha.get("observacao", "")
        self.status = linha.get("status", "Novo")
        self.erro_form = ""

    @rx.event
    def abrir_novo(self):
        self._preencher(None)
        self.dialogo_aberto = True

    @rx.event
    def abrir_editar(self, lead_id: str):
        linha = next((l for l in self._linhas if l["id"] == lead_id), None)
        if linha is None:
            return
        self._preencher(linha)
        self.dialogo_ver = False
        self.dialogo_aberto = True

    @rx.event
    def fechar_dialogo(self):
        self.dialogo_aberto = False

    @rx.event
    async def salvar(self):
        form = {"nome": self.nome, "telefone": self.telefone, "telegram": self.telegram, "email": self.email,
                "origem": self.origem, "interesse": self.interesse, "moto_interesse": self.moto_interesse,
                "moto_id": self.moto_id, "observacao": self.observacao, "status": self.status}
        try:
            dados = servico.validar_lead(form)
        except servico.ErroValidacao as erro:
            self.erro_form = str(erro)
            return
        try:
            if self.form_id is None:
                dados["usuario_id"] = (await self.get_state(AuthState)).usuario_id
                dados["cliente_id"] = 0
                await xano.criar(servico.TABELA, dados)
            else:
                await xano.atualizar_mesclando(servico.TABELA, self.form_id, dados)
        except xano.TabelaInexistente:
            self.erro_form = "A tabela leads ainda não existe no Xano (ver Configuração do sistema)."
            return
        except Exception:
            self.erro_form = "Não foi possível salvar (falha de conexão com o Xano). Tente de novo."
            return
        novo = self.form_id is None
        self.dialogo_aberto = False
        await self.carregar()
        return rx.toast.success("Lead cadastrado." if novo else "Lead atualizado.")

    @rx.event
    async def mudar_status(self, lead_id: str, status: str):
        if status not in servico.STATUS_LEAD:
            return
        if status == "Convertido":
            return [rx.toast.info("Para converter, use o botão Converter em cliente."),
                    LeadsState.visualizar(lead_id)]
        try:
            await xano.atualizar_mesclando(servico.TABELA, int(lead_id), {"status": status})
        except Exception:
            return rx.toast.error("Não foi possível mudar o status (falha de conexão).")
        await self.carregar()
        return rx.toast.success(f"Lead agora está em: {status}.")

    @rx.event
    async def excluir(self, lead_id: str):
        from .. import integridade
        encontrados = await integridade.dependentes(servico.TABELA, int(lead_id))
        if encontrados:
            return rx.toast.error(integridade.mensagem_bloqueio("este lead", encontrados)
                                  + " Marque-o como Perdido.")
        await xano.excluir(servico.TABELA, int(lead_id))
        self.dialogo_ver = False
        await self.carregar()
        return rx.toast.success("Lead excluído.")

    # ------------------------------------------------------------ ficha

    async def _carregar_ficha(self, lead_id: str):
        linha = next((l for l in self._linhas if l["id"] == str(lead_id)), None)
        if linha is None:
            self.dialogo_ver = False
            return
        self.lead = linha
        interacoes, emails = await asyncio.gather(xano.listar_se_existir("interacoes"),
                                                  xano.listar_se_existir("emails"))
        self.interacoes = clientes_servico.montar_interacoes(interacoes or [], "lead_id", int(lead_id))
        self.emails = clientes_servico.montar_emails(emails or [], "lead_id", int(lead_id))

    @rx.event
    async def visualizar(self, lead_id: str):
        await self._carregar_ficha(lead_id)
        self.int_tipo, self.int_descricao, self.erro_int = TIPOS_INTERACAO[0], "", ""
        self.dialogo_ver = True

    @rx.event
    def fechar_ver(self):
        self.dialogo_ver = False

    @rx.event
    async def salvar_interacao(self):
        descricao = self.int_descricao.strip()
        if not descricao:
            self.erro_int = "Descreva o que aconteceu."
            return
        auth = await self.get_state(AuthState)
        try:
            await xano.criar("interacoes", {
                "cliente_id": int(self.lead.get("cliente_id") or 0), "lead_id": int(self.lead["id"]),
                "tipo": self.int_tipo, "descricao": descricao, "usuario_id": auth.usuario_id,
            })
        except xano.TabelaInexistente:
            self.erro_int = "A tabela de interações ainda não existe no Xano (ver Configuração)."
            return
        except Exception:
            self.erro_int = "Não foi possível salvar (falha de conexão)."
            return
        self.int_descricao, self.erro_int = "", ""
        # contato registrado com lead "Novo" = já está em atendimento
        if self.lead.get("status") == "Novo":
            try:
                await xano.atualizar_mesclando(servico.TABELA, int(self.lead["id"]), {"status": "Em atendimento"})
            except Exception:
                pass
        await self.carregar()
        return rx.toast.success("Interação registrada.")

    # -------------------------------------------------------- conversão

    @rx.event
    def abrir_converter(self):
        self.conv_documento, self.erro_conv = "", ""
        self.dialogo_converter = True

    @rx.event
    def fechar_converter(self):
        self.dialogo_converter = False

    @rx.event
    async def converter(self):
        auth = await self.get_state(AuthState)
        try:
            cliente_id, criado = await servico.converter(int(self.lead["id"]), self.conv_documento, auth.usuario_id)
        except (servico.ErroValidacao, clientes_servico.ErroValidacao) as erro:
            self.erro_conv = str(erro)
            return
        except Exception:
            self.erro_conv = "Não foi possível converter (falha de conexão com o Xano). Tente de novo."
            return
        self.dialogo_converter = False
        self.dialogo_ver = False
        await self.carregar()
        return [
            rx.toast.success("Cliente criado a partir do lead." if criado
                             else "Lead ligado ao cliente que já tinha esse CPF/CNPJ."),
            rx.redirect(f"/clientes/{cliente_id}"),
        ]

    # ----------------------------------------------------------- e-mail

    @rx.event
    def abrir_email(self):
        if not self.lead.get("email"):
            return rx.toast.error("Este lead não tem e-mail cadastrado.")
        self.email_assunto = ""
        self.email_mensagem = f"Olá, {self.lead.get('nome', '').split(' ')[0]}!\n\n"
        self.erro_email = ""
        self.dialogo_email = True

    @rx.event
    def fechar_email(self):
        self.dialogo_email = False

    @rx.event
    async def enviar_email(self):
        auth = await self.get_state(AuthState)
        resultado = await email_servico.enviar(
            self.lead.get("email", ""), self.email_assunto, self.email_mensagem,
            cliente_id=int(self.lead.get("cliente_id") or 0), lead_id=int(self.lead.get("id") or 0),
            usuario_id=auth.usuario_id,
        )
        if not resultado.enviado:
            self.erro_email = f"{resultado.status}: {resultado.erro}." + (
                " A tentativa ficou registrada no histórico." if resultado.registrado else "")
            return
        self.dialogo_email = False
        await self.carregar()
        return rx.toast.success("E-mail enviado.")

"""
State da Configuração do sistema (/configuracao) — só administradores.

- Situação de cada recurso novo (ativo ou aguardando o Xano), com o passo a
  passo do que criar no painel do Xano (lista em `recursos.py`);
- formas de pagamento do balcão (tabela `formas_pagamento`);
- SendGrid: se está configurado e um envio de teste para o próprio e-mail.
"""

import reflex as rx

from .. import email_servico, recursos
from .. import xano_client as xano
from ..seguranca import admin_ok
from .auth_state import AuthState

TABELA_FORMAS = "formas_pagamento"
FORMAS_PADRAO = ["Dinheiro", "PIX", "Cartão de débito", "Cartão de crédito", "Boleto", "Financiamento"]


class ConfiguracaoState(rx.State):
    itens: list[dict] = []
    ativos: int = 0
    total: int = 0
    conta_servico: str = ""
    sendgrid_ok: bool = False
    remetente: str = ""

    formas_existe: bool = False
    formas: list[dict] = []
    nova_forma: str = ""

    @rx.event
    async def carregar(self):
        if not await admin_ok(self):
            return
        self.itens = await recursos.situacao()
        self.total = len(self.itens)
        self.ativos = sum(1 for i in self.itens if i["ativo"])
        self.conta_servico = xano.email_conta_servico()
        chave, remetente = email_servico.configuracao()
        self.sendgrid_ok = bool(chave and remetente)
        self.remetente = remetente
        await self._carregar_formas()

    async def _carregar_formas(self):
        formas = await xano.listar_se_existir(TABELA_FORMAS)
        self.formas_existe = formas is not None
        self.formas = [
            {"id": str(f["id"]), "nome": f.get("nome") or "", "ativo": f.get("ativo") is not False}
            for f in sorted(formas or [], key=lambda f: (f.get("nome") or "").lower())
        ]

    @rx.event
    async def verificar_agora(self):
        """Depois de criar tabelas/campos no Xano: confere sem esperar o cache."""
        xano.limpar_cache()
        xano.esquecer_ausencias()
        await self.carregar()
        return rx.toast.success(f"{self.ativos} de {self.total} recursos ativos.")

    # ------------------------------------------------ formas de pagamento

    @rx.event
    async def adicionar_forma(self):
        if not await admin_ok(self):
            return
        nome = " ".join(self.nova_forma.split())
        if not nome:
            return rx.toast.error("Digite o nome da forma de pagamento.")
        if any(f["nome"].lower() == nome.lower() for f in self.formas):
            return rx.toast.error("Essa forma de pagamento já existe.")
        await xano.criar(TABELA_FORMAS, {"nome": nome, "ativo": True})
        self.nova_forma = ""
        await self._carregar_formas()
        return rx.toast.success(f"{nome} adicionada.")

    @rx.event
    async def criar_formas_padrao(self):
        if not await admin_ok(self):
            return
        existentes = {f["nome"].lower() for f in self.formas}
        criadas = 0
        for nome in FORMAS_PADRAO:
            if nome.lower() not in existentes:
                await xano.criar(TABELA_FORMAS, {"nome": nome, "ativo": True})
                criadas += 1
        await self._carregar_formas()
        return rx.toast.success(f"{criadas} forma(s) de pagamento criada(s).")

    @rx.event
    async def alternar_forma(self, forma_id: str):
        if not await admin_ok(self):
            return
        forma = next((f for f in self.formas if f["id"] == forma_id), None)
        if forma is None:
            return
        await xano.atualizar_mesclando(TABELA_FORMAS, int(forma_id), {"ativo": not forma["ativo"]})
        await self._carregar_formas()

    @rx.event
    async def excluir_forma(self, forma_id: str):
        if not await admin_ok(self):
            return
        # As vendas guardam o NOME da forma de pagamento: excluir não apaga histórico.
        await xano.excluir(TABELA_FORMAS, int(forma_id))
        await self._carregar_formas()
        return rx.toast.success("Forma de pagamento excluída (as vendas antigas continuam mostrando o nome).")

    # -------------------------------------------------------------- e-mail

    @rx.event
    async def testar_email(self):
        if not await admin_ok(self):
            return
        auth = await self.get_state(AuthState)
        destino = auth._email_usuario
        resultado = await email_servico.enviar(
            destino, "Teste do Harley Store",
            "Este é um e-mail de teste enviado pela tela Configuração do sistema.",
            usuario_id=auth.usuario_id,
        )
        if resultado.enviado:
            return rx.toast.success(f"E-mail de teste enviado para {destino}.")
        return rx.toast.error(f"{resultado.status}: {resultado.erro}")

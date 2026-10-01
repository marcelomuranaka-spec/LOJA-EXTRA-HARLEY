"""
State de Usuários do sistema (contas de login na tabela `user` do Xano) —
diferente de Funcionários (que é cadastro de RH). Tela só de administradores.

O administrador cria contas, define o perfil de cada uma (Administrador ou
Funcionário), define uma senha nova quando alguém esquece a dele, troca
e-mails e exclui contas. As chamadas ao Xano vão com o token do
administrador logado (ver `xano_admin_client.py`).

Regras de proteção:
- o sistema sempre fica com pelo menos um administrador;
- ninguém exclui a própria conta (outro administrador faz isso);
- a conta de serviço do servidor (`XANO_EMAIL` do .env) não pode ser
  excluída nem virar administradora: sem ela as telas param de carregar.
"""

from __future__ import annotations

import re

import reflex as rx

from .. import xano_admin_client as admin
from .. import xano_client
from ..seguranca import admin_ok
from ..xano_admin_client import PERFIL_ADMIN, PERFIL_FUNCIONARIO
from ..xano_auth_client import XanoAuthError
from .auth_state import AuthState, _MENSAGEM_SENHA_INVALIDA, _senha_valida

_EMAIL_REGEX = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def bloqueio_mudar_perfil(usuarios: list[dict], usuario: dict) -> str:
    """"" se pode trocar o perfil desta conta; senão, o motivo."""
    if usuario["eh_admin"] and sum(1 for u in usuarios if u["eh_admin"]) <= 1:
        return "O sistema precisa de pelo menos um administrador. Torne outra conta administradora antes."
    if not usuario["eh_admin"] and usuario["eh_servico"]:
        return "A conta de serviço do sistema não pode ser administradora."
    return ""


def bloqueio_excluir(usuarios: list[dict], usuario: dict) -> str:
    """"" se pode excluir esta conta; senão, o motivo."""
    if usuario["eh_voce"]:
        return "Você não pode excluir a própria conta. Peça a outro administrador."
    if usuario["eh_servico"]:
        return "Esta é a conta de serviço do sistema: sem ela as telas param de carregar."
    if usuario["eh_admin"] and sum(1 for u in usuarios if u["eh_admin"]) <= 1:
        return "O sistema precisa de pelo menos um administrador."
    return ""


class UsuariosState(rx.State):
    usuarios: list[dict] = []
    erro_lista: str = ""

    # novo usuário
    dialogo_novo: bool = False
    novo_nome_completo: str = ""
    novo_email: str = ""
    nova_senha: str = ""
    nova_confirmar_senha: str = ""
    novo_eh_admin: bool = False
    erro: str = ""

    # definir senha
    dialogo_senha: bool = False
    senha_usuario_id: str = ""
    senha_usuario_nome: str = ""
    senha_nova: str = ""
    senha_confirmar: str = ""
    erro_senha: str = ""

    async def _token_admin(self) -> str | None:
        if not await admin_ok(self):
            return None
        return (await self.get_state(AuthState)).auth_token

    @rx.event
    async def carregar(self):
        token = await self._token_admin()
        if token is None:
            return
        auth = await self.get_state(AuthState)
        try:
            registros = await admin.listar_usuarios(token)
            self.erro_lista = ""
        except Exception:
            self.erro_lista = "Não foi possível carregar as contas. Tente novamente em instantes."
            return
        servico = xano_client.email_conta_servico()
        self.usuarios = [
            {
                "id": str(r["id"]),
                "nome": r.get("name", "") or "",
                "email": r.get("email", "") or "",
                "perfil": r.get("role") or PERFIL_FUNCIONARIO,
                "perfil_nome": admin.nome_perfil(r.get("role")),
                "eh_admin": (r.get("role") or "") == PERFIL_ADMIN,
                "eh_voce": int(r["id"]) == auth.usuario_id,
                "eh_servico": bool(servico) and (r.get("email") or "").lower() == servico,
                "criado_em": xano_client.epoch_ms_para_datetime(r["created_at"]).strftime("%d/%m/%Y")
                if r.get("created_at") else "—",
            }
            # administradores primeiro, depois por nome
            for r in sorted(registros, key=lambda r: ((r.get("role") or "") != PERFIL_ADMIN, (r.get("name") or "").lower()))
        ]

    def _usuario(self, usuario_id: str) -> dict | None:
        return next((u for u in self.usuarios if u["id"] == usuario_id), None)

    # ---------------------------------------------------------- novo usuário

    @rx.event
    def abrir_novo(self):
        self.novo_nome_completo = ""
        self.novo_email = ""
        self.nova_senha = ""
        self.nova_confirmar_senha = ""
        self.novo_eh_admin = False
        self.erro = ""
        self.dialogo_novo = True

    @rx.event
    def fechar_novo(self):
        self.dialogo_novo = False

    @rx.event
    async def salvar_novo(self):
        token = await self._token_admin()
        if token is None:
            return
        nome = self.novo_nome_completo.strip()
        email = self.novo_email.strip().lower()
        senha = self.nova_senha
        if not nome or not email or not senha:
            self.erro = "Preencha nome, e-mail e senha."
            return
        if not _EMAIL_REGEX.match(email):
            self.erro = "E-mail inválido."
            return
        if not _senha_valida(senha):
            self.erro = _MENSAGEM_SENHA_INVALIDA
            return
        if senha != self.nova_confirmar_senha:
            self.erro = "As senhas não coincidem."
            return
        try:
            novo_id = await admin.criar_usuario(token, nome, email, senha)
        except XanoAuthError as falha:
            self.erro = ("Esse e-mail já está cadastrado." if "already exists" in str(falha).lower()
                         else "O Xano recusou a criação da conta. Confira os dados.")
            return
        except Exception:
            self.erro = "Não foi possível conectar. Tente novamente em instantes."
            return
        aviso = ""
        if self.novo_eh_admin:
            try:
                await admin.definir_perfil(token, novo_id, PERFIL_ADMIN)
            except Exception:
                aviso = " A conta foi criada como Funcionário: tente torná-la administradora de novo."
        self.dialogo_novo = False
        await self.carregar()
        perfil = "Administrador" if self.novo_eh_admin and not aviso else "Funcionário"
        return rx.toast.success(f"Conta de {nome} criada ({perfil}).{aviso}")

    # --------------------------------------------------------------- perfil

    @rx.event
    async def alternar_perfil(self, usuario_id: str):
        token = await self._token_admin()
        if token is None:
            return
        usuario = self._usuario(usuario_id)
        if usuario is None:
            return
        motivo = bloqueio_mudar_perfil(self.usuarios, usuario)
        if motivo:
            return rx.toast.error(motivo)
        novo = PERFIL_FUNCIONARIO if usuario["eh_admin"] else PERFIL_ADMIN
        try:
            await admin.definir_perfil(token, int(usuario_id), novo)
        except Exception:
            return rx.toast.error("O Xano recusou a mudança de perfil. Tente novamente.")

        if usuario["eh_voce"]:
            # Deixou de ser administrador: confere de novo e sai desta tela.
            auth = await self.get_state(AuthState)
            await auth.validar_sessao(forcar=True)
            return [rx.redirect("/painel"), rx.toast.info("Você agora é Funcionário.")]
        await self.carregar()
        return rx.toast.success(f"{usuario['nome']} agora é {admin.nome_perfil(novo)}.")

    # ---------------------------------------------------------------- senha

    @rx.event
    def abrir_senha(self, usuario_id: str):
        usuario = self._usuario(usuario_id)
        if usuario is None:
            return
        self.senha_usuario_id = usuario_id
        self.senha_usuario_nome = usuario["nome"]
        self.senha_nova = ""
        self.senha_confirmar = ""
        self.erro_senha = ""
        self.dialogo_senha = True

    @rx.event
    def fechar_senha(self):
        self.dialogo_senha = False

    @rx.event
    async def salvar_senha(self):
        token = await self._token_admin()
        if token is None:
            return
        if not _senha_valida(self.senha_nova):
            self.erro_senha = _MENSAGEM_SENHA_INVALIDA
            return
        if self.senha_nova != self.senha_confirmar:
            self.erro_senha = "As senhas não coincidem."
            return
        usuario = self._usuario(self.senha_usuario_id)
        if usuario and usuario["eh_servico"]:
            self.erro_senha = ("Esta é a conta de serviço do sistema: trocar a senha aqui faz as telas "
                               "pararem de carregar. Use scripts\\configurar_xano.ps1.")
            return
        try:
            await admin.definir_senha(token, int(self.senha_usuario_id), self.senha_nova)
        except Exception:
            self.erro_senha = "O Xano recusou a nova senha. Tente novamente."
            return
        self.dialogo_senha = False
        return rx.toast.success(f"Senha de {self.senha_usuario_nome} alterada. Avise a pessoa.")

    # ------------------------------------------------------- e-mail e excluir

    @rx.event
    async def atualizar_email(self, usuario_id: str, novo_email: str):
        token = await self._token_admin()
        if token is None:
            return
        usuario = self._usuario(usuario_id)
        novo_email = (novo_email or "").strip().lower()
        if usuario is None or novo_email == usuario["email"].lower():
            return
        if usuario["eh_servico"]:
            await self.carregar()
            return rx.toast.error("O e-mail da conta de serviço não pode ser trocado por aqui.")
        if not _EMAIL_REGEX.match(novo_email):
            await self.carregar()
            return rx.toast.error("E-mail inválido; nada foi alterado.")
        try:
            await admin.atualizar_email(token, int(usuario_id), novo_email)
        except Exception:
            await self.carregar()
            return rx.toast.error("O Xano recusou o e-mail (talvez já esteja em uso).")
        await self.carregar()
        return rx.toast.success("E-mail atualizado.")

    @rx.event
    async def excluir(self, usuario_id: str):
        token = await self._token_admin()
        if token is None:
            return
        usuario = self._usuario(usuario_id)
        if usuario is None:
            return
        motivo = bloqueio_excluir(self.usuarios, usuario)
        if motivo:
            return rx.toast.error(motivo)
        try:
            await admin.excluir_usuario(token, int(usuario_id))
        except Exception:
            return rx.toast.error("O Xano recusou a exclusão. Tente novamente.")
        await self.carregar()
        return rx.toast.success(f"Conta de {usuario['nome']} excluída.")

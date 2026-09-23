"""
State de Usuários do sistema (contas de login na tabela `user` do Xano) —
diferente de Funcionários (que é cadastro de RH). Aqui é possível criar
novas contas de acesso e excluir contas existentes.
"""

from __future__ import annotations

import reflex as rx

from .. import xano_admin_client
from ..xano_auth_client import XanoAuthError, signup
from .auth_state import AuthState, _MENSAGEM_SENHA_INVALIDA, _senha_valida


class UsuariosState(rx.State):
    usuarios: list[dict] = []

    novo_nome_completo: str = ""
    novo_email: str = ""
    nova_senha: str = ""
    nova_confirmar_senha: str = ""
    erro: str = ""

    @rx.event
    async def carregar(self):
        registros = await xano_admin_client.listar_usuarios()
        self.usuarios = [
            {
                "id": str(r["id"]),
                "nome": r.get("name", ""),
                "email": r.get("email", "") or "",
            }
            for r in sorted(registros, key=lambda r: r.get("name", ""))
        ]

    @rx.event
    def limpar_formulario(self):
        self.novo_nome_completo = ""
        self.novo_email = ""
        self.nova_senha = ""
        self.nova_confirmar_senha = ""
        self.erro = ""

    @rx.event
    async def salvar(self):
        nome_completo = self.novo_nome_completo.strip()
        email = self.novo_email.strip()
        senha = self.nova_senha
        if not nome_completo or not email or not senha:
            self.erro = "Preencha todos os campos."
            return
        if not _senha_valida(senha):
            self.erro = _MENSAGEM_SENHA_INVALIDA
            return
        if senha != self.nova_confirmar_senha:
            self.erro = "As senhas não coincidem."
            return

        try:
            await signup(nome_completo, email, senha)
        except XanoAuthError as erro:
            if "already exists" in str(erro).lower():
                self.erro = "Esse email já está cadastrado."
            else:
                self.erro = "Não foi possível criar a conta. Verifique os dados e tente novamente."
            return
        except Exception:
            self.erro = "Não foi possível conectar. Tente novamente em instantes."
            return

        self.limpar_formulario()
        await self.carregar()

    @rx.event
    async def atualizar_email(self, usuario_id: str, novo_email: str):
        await xano_admin_client.atualizar_email(int(usuario_id), novo_email.strip())
        await self.carregar()

    @rx.event
    async def excluir(self, usuario_id: str):
        total = len(await xano_admin_client.listar_usuarios())
        if total <= 1:
            return rx.window_alert("Não é possível excluir o único usuário do sistema.")

        await xano_admin_client.excluir_usuario(int(usuario_id))

        auth = await self.get_state(AuthState)
        if str(auth.auth_user_id) == usuario_id:
            auth.auth_token = ""
            auth.auth_user_id = 0
            auth.usuario_logado = ""
            await self.carregar()
            return rx.redirect("/login")

        await self.carregar()

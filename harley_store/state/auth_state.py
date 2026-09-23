"""
State de autenticação (login / cadastro de usuário).

Login e cadastro usam a tabela `user` do Xano (grupo "Authentication" —
ver `xano_auth_client.py`), não um banco local. Quem está logado é
lembrado através de três cookies (`rx.Cookie`): `usuario_logado` (nome
pra exibir), `auth_token` (token do Xano) e `auth_user_id` (id numérico
do Xano) — por isso todo `on_load` de página protegida chama primeiro
`AuthState.exigir_login`, que redireciona para `/login` se não houver
token.
"""

from __future__ import annotations

import re

import reflex as rx

from .. import xano_auth_client
from ..xano_auth_client import XanoAuthError

_SENHA_REGEX = re.compile(r"^(?=.*[A-Za-z])(?=.*\d).{8,}$")


def _senha_valida(senha: str) -> bool:
    """Mesma regra de senha exigida pelo Xano: 8+ caracteres, com letra e número."""
    return bool(_SENHA_REGEX.match(senha))


_MENSAGEM_SENHA_INVALIDA = "A senha precisa ter pelo menos 8 caracteres, com letras e números."


class AuthState(rx.State):
    # Guarda o nome do usuário logado (só pra exibição); "" significa deslogado.
    usuario_logado: str = rx.Cookie("", name="hs_usuario")
    auth_token: str = rx.Cookie("", name="hs_auth_token")
    # É um id numérico do Xano — tipado como int (não str) porque o
    # Reflex, ao reidratar o cookie no navegador, sempre interpreta um
    # valor com cara de número como int; manter isso como str fazia esse
    # aviso de tipo aparecer a cada login, mesmo com um cookie novo.
    auth_user_id: int = rx.Cookie(0, name="hs_auth_user_id_v2")

    # Campos do formulário de login
    login_email: str = ""
    login_senha: str = ""
    login_erro: str = ""

    # Campos do formulário de cadastro
    cad_nome_completo: str = ""
    cad_email: str = ""
    cad_senha: str = ""
    cad_confirmar_senha: str = ""
    cad_erro: str = ""

    # Campos do formulário "Esqueci minha senha"
    rec_email: str = ""
    rec_senha: str = ""
    rec_confirmar_senha: str = ""
    rec_erro: str = ""

    # Mensagem verde mostrada na aba "Entrar" (ex.: depois de redefinir a senha)
    login_sucesso: str = ""

    aba_atual: str = "entrar"  # "entrar" | "cadastrar" | "esqueci"

    @rx.var
    def esta_logado(self) -> bool:
        return bool(self.auth_token)

    @rx.event
    def exigir_login(self):
        """Chamar no on_load de toda página protegida."""
        if not self.auth_token:
            return rx.redirect("/login")

    @rx.event
    def redirecionar_se_ja_logado(self):
        """Chamar no on_load da página de login — se já estiver logado, pula para o painel."""
        if self.auth_token:
            return rx.redirect("/painel")

    @rx.event
    def definir_aba(self, aba: str):
        self.aba_atual = aba
        self.login_erro = ""
        self.cad_erro = ""
        self.rec_erro = ""
        self.login_sucesso = ""
        if aba == "esqueci":
            # já traz o email que a pessoa tentou usar no login
            self.rec_email = self.login_email
            self.rec_senha = ""
            self.rec_confirmar_senha = ""

    @rx.event
    async def redefinir_senha(self):
        email = self.rec_email.strip().lower()
        senha = self.rec_senha
        if not email or not senha or not self.rec_confirmar_senha:
            self.rec_erro = "Preencha todos os campos."
            return
        if not _senha_valida(senha):
            self.rec_erro = _MENSAGEM_SENHA_INVALIDA
            return
        if senha != self.rec_confirmar_senha:
            self.rec_erro = "As senhas não coincidem."
            return

        try:
            await xano_auth_client.redefinir_senha(email, senha)
        except XanoAuthError as erro:
            if "no user found" in str(erro).lower():
                self.rec_erro = "Não há nenhuma conta cadastrada com esse email."
            else:
                self.rec_erro = "Não foi possível redefinir a senha. Tente novamente."
            return
        except Exception:
            self.rec_erro = "Não foi possível conectar. Tente novamente em instantes."
            return

        self.rec_senha = ""
        self.rec_confirmar_senha = ""
        self.rec_erro = ""
        self.login_email = email
        self.login_senha = ""
        self.login_erro = ""
        self.aba_atual = "entrar"
        self.login_sucesso = "Senha alterada! Entre com a nova senha."

    @rx.event
    async def fazer_login(self):
        email = self.login_email.strip()
        senha = self.login_senha
        if not email or not senha:
            self.login_erro = "Preencha email e senha."
            return

        try:
            resultado = await xano_auth_client.login(email, senha)
        except XanoAuthError:
            self.login_erro = "Email ou senha incorretos."
            return
        except Exception:
            self.login_erro = "Não foi possível conectar. Tente novamente em instantes."
            return

        self.login_erro = ""
        self.login_sucesso = ""
        self.login_senha = ""
        self.auth_token = resultado["authToken"]
        self.auth_user_id = int(resultado["user_id"])
        self.usuario_logado = resultado.get("name") or email
        return rx.redirect("/painel")

    @rx.event
    async def cadastrar(self):
        nome_completo = self.cad_nome_completo.strip()
        email = self.cad_email.strip()
        senha = self.cad_senha
        confirmar = self.cad_confirmar_senha

        if not nome_completo or not email or not senha:
            self.cad_erro = "Preencha todos os campos."
            return
        if not _senha_valida(senha):
            self.cad_erro = _MENSAGEM_SENHA_INVALIDA
            return
        if senha != confirmar:
            self.cad_erro = "As senhas não coincidem."
            return

        try:
            resultado = await xano_auth_client.signup(nome_completo, email, senha)
        except XanoAuthError as erro:
            if "already exists" in str(erro).lower():
                self.cad_erro = "Esse email já está cadastrado."
            else:
                self.cad_erro = "Não foi possível criar a conta. Verifique os dados e tente novamente."
            return
        except Exception:
            self.cad_erro = "Não foi possível conectar. Tente novamente em instantes."
            return

        self.cad_erro = ""
        self.cad_senha = ""
        self.cad_confirmar_senha = ""
        self.auth_token = resultado["authToken"]
        self.auth_user_id = int(resultado["user_id"])
        self.usuario_logado = nome_completo
        return rx.redirect("/painel")

    @rx.event
    def sair(self):
        self.auth_token = ""
        self.auth_user_id = 0
        self.usuario_logado = ""
        return rx.redirect("/login")


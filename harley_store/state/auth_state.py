"""
State de autenticação (login, sessão e perfil de acesso).

Login usa a tabela `user` do Xano (grupo "Authentication" — ver
`xano_auth_client.py`), não um banco local. O navegador guarda só o token do
Xano e o nome para exibição, em cookies (`rx.Cookie`).

Cookie não prova nada (pode ser inventado no navegador). Por isso a sessão é
CONFERIDA NO XANO (`auth/me`) no login e de tempos em tempos (a cada
`REVALIDAR_SEGUNDOS`), e o resultado — id da conta, e-mail e perfil — fica
em variáveis só do servidor (`_usuario_id`, `_perfil`...), que o navegador
não vê nem consegue alterar. Todo `on_load` de página protegida chama
primeiro `AuthState.exigir_login` (ou `exigir_admin`), e o middleware em
`seguranca.py` recusa qualquer ação de tela sem sessão conferida.

Perfis: "admin" (Administrador) e "member" (Funcionário), no campo `role`
da tabela `user`. Quem define o perfil de cada conta é um administrador, na
tela "Usuários do sistema".
"""

from __future__ import annotations

import re
import time

import reflex as rx

from .. import xano_auth_client
from ..xano_admin_client import PERFIL_ADMIN, PERFIL_FUNCIONARIO, nome_perfil
from ..xano_auth_client import SessaoInvalida, XanoAuthError

_SENHA_REGEX = re.compile(r"^(?=.*[A-Za-z])(?=.*\d).{8,}$")

# De quanto em quanto tempo a sessão é conferida de novo no Xano (pega conta
# excluída ou perfil alterado sem esperar o token de 24 h vencer).
REVALIDAR_SEGUNDOS = 600


def _senha_valida(senha: str) -> bool:
    """Mesma regra de senha exigida pelo Xano: 8+ caracteres, com letra e número."""
    return bool(_SENHA_REGEX.match(senha))


_MENSAGEM_SENHA_INVALIDA = "A senha precisa ter pelo menos 8 caracteres, com letras e números."


class AuthState(rx.State):
    # Nome do usuário logado (só pra exibição); "" significa deslogado.
    usuario_logado: str = rx.Cookie("", name="hs_usuario")
    auth_token: str = rx.Cookie("", name="hs_auth_token")

    # Campos do formulário de login
    login_email: str = ""
    login_senha: str = ""
    login_erro: str = ""

    # Sessão conferida no Xano — só no servidor (o "_" esconde do navegador).
    _sessao_token: str = ""
    _sessao_validada_em: float = 0.0
    _usuario_id: int = 0
    _perfil: str = ""
    _email_usuario: str = ""

    @rx.var
    def esta_logado(self) -> bool:
        return bool(self.auth_token)

    @rx.var
    def eh_admin(self) -> bool:
        """Para a tela (mostrar ou esconder menus). As permissões de verdade
        são conferidas no servidor por `admin_confirmado()`."""
        return self._perfil == PERFIL_ADMIN

    @rx.var
    def perfil_nome(self) -> str:
        return nome_perfil(self._perfil) if self._usuario_id else ""

    @rx.var
    def usuario_id(self) -> int:
        return self._usuario_id

    # ------------------------------------------------------ sessão (servidor)

    def sessao_valida(self) -> bool:
        """Sessão já conferida no Xano para o token atual. Sem rede: é o que o
        middleware usa a cada ação."""
        return bool(self.auth_token) and self._sessao_token == self.auth_token and self._usuario_id > 0

    def admin_confirmado(self) -> bool:
        return self.sessao_valida() and self._perfil == PERFIL_ADMIN

    def _aplicar_identidade(self, conta: dict) -> None:
        self._sessao_token = self.auth_token
        self._sessao_validada_em = time.monotonic()
        self._usuario_id = int(conta["id"])
        self._perfil = conta.get("role") or PERFIL_FUNCIONARIO
        self._email_usuario = conta.get("email") or ""
        self.usuario_logado = conta.get("name") or self._email_usuario

    def _limpar_sessao(self) -> None:
        self.auth_token = ""
        self.usuario_logado = ""
        self._sessao_token = ""
        self._sessao_validada_em = 0.0
        self._usuario_id = 0
        self._perfil = ""
        self._email_usuario = ""

    async def validar_sessao(self, forcar: bool = False) -> bool:
        if not self.auth_token:
            self._limpar_sessao()
            return False
        recente = time.monotonic() - self._sessao_validada_em < REVALIDAR_SEGUNDOS
        if self.sessao_valida() and recente and not forcar:
            return True
        try:
            conta = await xano_auth_client.quem_sou(self.auth_token)
        except SessaoInvalida:
            self._limpar_sessao()
            return False
        except Exception:
            # Xano fora do ar ou lento: mantém uma sessão que já foi conferida
            # para este mesmo token; uma sessão nunca conferida não entra.
            return self.sessao_valida()
        self._aplicar_identidade(conta)
        return True

    # ------------------------------------------------------------- eventos

    @rx.event
    async def exigir_login(self):
        """Chamar no on_load de toda página protegida."""
        tinha_token = bool(self.auth_token)
        if not await self.validar_sessao():
            if tinha_token:
                self.login_erro = "Sua sessão terminou. Entre novamente."
            return rx.redirect("/login")

    @rx.event
    async def exigir_admin(self):
        """on_load das telas de administração (no lugar de exigir_login)."""
        tinha_token = bool(self.auth_token)
        if not await self.validar_sessao():
            if tinha_token:
                self.login_erro = "Sua sessão terminou. Entre novamente."
            return rx.redirect("/login")
        if self._perfil != PERFIL_ADMIN:
            return [
                rx.redirect("/painel"),
                rx.toast.warning("Essa tela é só para administradores."),
            ]

    @rx.event
    async def redirecionar_se_ja_logado(self):
        """on_load da página de login — se já estiver logado, pula para o painel."""
        if self.auth_token and await self.validar_sessao():
            return rx.redirect("/painel")

    @rx.event
    async def fazer_login(self):
        email = self.login_email.strip()
        senha = self.login_senha
        if not email or not senha:
            self.login_erro = "Preencha email e senha."
            return

        try:
            resultado = await xano_auth_client.login(email, senha)
            self.auth_token = resultado["authToken"]
            conta = await xano_auth_client.quem_sou(self.auth_token)
        except XanoAuthError:
            self._limpar_sessao()
            self.login_erro = "Email ou senha incorretos."
            return
        except Exception:
            self._limpar_sessao()
            self.login_erro = "Não foi possível conectar. Tente novamente em instantes."
            return

        self._aplicar_identidade(conta)
        self.login_erro = ""
        self.login_senha = ""
        return rx.redirect("/painel")

    @rx.event
    async def enviar_login(self, _dados: dict):
        """Enter no formulário de login (os campos já estão no state)."""
        return await self.fazer_login()

    @rx.event
    def sair(self):
        self._limpar_sessao()
        self.login_erro = ""
        return rx.redirect("/login")

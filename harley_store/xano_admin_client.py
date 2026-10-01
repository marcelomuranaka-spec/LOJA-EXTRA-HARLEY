"""
Cliente HTTP para o grupo "Admin" do Xano — endpoints da tela "Usuários do
sistema" (listar contas, criar, mudar perfil, definir senha, trocar email e
excluir, na tabela `user`).

Grupo separado do "Authentication" (login/reset) porque é um grupo de API
diferente no Xano, com sua própria base URL.

As chamadas vão com o token de QUEM ESTÁ LOGADO (o administrador), e não com
o da conta de serviço do servidor: assim o próprio Xano confere se a conta
tem permissão, e a conta de serviço não precisa ser administradora. A
retentativa em erro 429 é a de `xano_client._request`.

Perfis (campo `role` da tabela `user`): "admin" (Administrador) e "member"
(Funcionário). O cadastro pelo `auth/signup` sempre cria "member".
"""

from __future__ import annotations

from . import xano_client
from .xano_auth_client import XanoAuthError

BASE_URL = "https://x8ki-letl-twmt.n7.xano.io/api:KegVKtiw"

PERFIL_ADMIN = "admin"
PERFIL_FUNCIONARIO = "member"
NOMES_PERFIL = {PERFIL_ADMIN: "Administrador", PERFIL_FUNCIONARIO: "Funcionário"}


def nome_perfil(perfil: str | None) -> str:
    return NOMES_PERFIL.get(perfil or "", "Funcionário")


async def _chamar(token: str, metodo: str, url: str, **kwargs):
    resposta = await xano_client._request(metodo, url, headers={"Authorization": f"Bearer {token}"}, **kwargs)
    if resposta.status_code >= 400:
        try:
            mensagem = resposta.json().get("message", "")
        except ValueError:
            mensagem = ""
        if resposta.status_code in (401, 403):
            mensagem = mensagem or "Acesso negado pelo Xano."
        raise XanoAuthError(mensagem or f"Erro {resposta.status_code} no Xano")
    return resposta.json() if resposta.content else None


async def listar_usuarios(token: str) -> list[dict]:
    return await _chamar(token, "GET", f"{BASE_URL}/user/list") or []


async def criar_usuario(token: str, nome: str, email: str, senha: str) -> int:
    """Cria a conta (perfil Funcionário) e devolve o id. O `auth/signup` exige
    login no Xano; o token novo que ele devolve é descartado (o administrador
    continua logado como ele mesmo)."""
    resposta = await _chamar(
        token, "POST", f"{xano_client.AUTH_URL}/auth/signup",
        json={"name": nome, "email": email, "password": senha},
    )
    return int(resposta["user_id"])


async def definir_perfil(token: str, usuario_id: int, perfil: str) -> None:
    if perfil not in NOMES_PERFIL:
        raise ValueError(f"Perfil inválido: {perfil}")
    await _chamar(token, "POST", f"{BASE_URL}/user/set-role", json={"id": usuario_id, "role": perfil})


async def definir_senha(token: str, usuario_id: int, senha: str) -> None:
    await _chamar(token, "POST", f"{BASE_URL}/user/set-password", json={"id": usuario_id, "password": senha})


async def atualizar_email(token: str, usuario_id: int, novo_email: str) -> dict:
    return await _chamar(
        token, "POST", f"{BASE_URL}/user/update-email", json={"id": usuario_id, "email": novo_email}
    )


async def excluir_usuario(token: str, usuario_id: int) -> None:
    await _chamar(token, "POST", f"{BASE_URL}/user/delete", json={"id": usuario_id})

"""
Cliente HTTP para o grupo "Authentication" do Xano (login e cadastro na
tabela `user`).

É um módulo separado de `xano_client.py` porque o grupo Authentication tem
uma base URL própria (canonical diferente do grupo de CRUD genérico usado
pelas outras tabelas do sistema). A lógica de retentativa em erro 429 é
reaproveitada de `xano_client._request` em vez de duplicada aqui.
"""

from __future__ import annotations

from . import xano_client

BASE_URL = xano_client.AUTH_URL


class XanoAuthError(Exception):
    """Erro retornado pelo Xano (mensagem já pronta pra decidir o que mostrar)."""


async def _post(caminho: str, dados: dict) -> dict:
    resposta = await xano_client._request("POST", f"{BASE_URL}/{caminho}", json=dados)
    if resposta.status_code >= 400:
        try:
            mensagem = resposta.json().get("message", "")
        except ValueError:
            mensagem = ""
        raise XanoAuthError(mensagem or f"Erro {resposta.status_code} ao chamar {caminho}")
    return resposta.json()


async def login(email: str, senha: str) -> dict:
    """Retorna {"authToken", "user_id", "name"}. Levanta XanoAuthError em credenciais inválidas."""
    return await _post("auth/login", {"email": email, "password": senha})


async def signup(nome: str, email: str, senha: str) -> dict:
    """Retorna {"authToken", "user_id"}. Levanta XanoAuthError se o email já existe."""
    return await _post("auth/signup", {"name": nome, "email": email, "password": senha})


async def redefinir_senha(email: str, nova_senha: str) -> None:
    """"Esqueci minha senha" direto na tela de login, sem email de confirmação.

    Reaproveita os dois endpoints de reset que já existem no Xano, em
    sequência e só aqui no servidor (o código nunca vai para o navegador):
    `reset/request-code` gera um código de uso único para o email e o
    devolve, e `reset/confirm-code` usa esse código para gravar a nova senha.
    Levanta XanoAuthError("No user found...") se o email não estiver cadastrado.
    """
    codigo = (await _post("reset/request-code", {"email": email}))["token"]
    await _post(
        "reset/confirm-code",
        {"email": email, "code": codigo, "password": nova_senha, "confirm_password": nova_senha},
    )

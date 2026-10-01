"""
Cliente HTTP para o grupo "Authentication" do Xano (login e identidade de
quem está logado, na tabela `user`).

É um módulo separado de `xano_client.py` porque o grupo Authentication tem
uma base URL própria (canonical diferente do grupo de CRUD genérico usado
pelas outras tabelas do sistema). A lógica de retentativa em erro 429 é
reaproveitada de `xano_client._request` em vez de duplicada aqui.

Cadastro (`auth/signup`) e "esqueci minha senha" (`reset/*`) passaram a
exigir login no Xano: contas novas e senhas são definidas pelo administrador
na tela "Usuários do sistema" (ver `xano_admin_client.py`).
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


class SessaoInvalida(XanoAuthError):
    """O Xano não reconhece o token (vencido, inventado ou conta excluída)."""


async def quem_sou(token: str) -> dict:
    """{"id", "name", "email", "role", ...} da conta dona do token, conferido
    no Xano (`auth/me`). É a única fonte confiável de quem está logado e do
    perfil dela: cookies podem ser inventados no navegador.
    Levanta SessaoInvalida se o Xano recusar o token."""
    resposta = await xano_client._request(
        "GET", f"{BASE_URL}/auth/me", headers={"Authorization": f"Bearer {token}"}
    )
    if resposta.status_code in (401, 403, 404):
        raise SessaoInvalida("Sessão inválida ou vencida.")
    resposta.raise_for_status()
    return resposta.json()

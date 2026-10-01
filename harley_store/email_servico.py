"""
Envio de e-mails pelo SendGrid e histórico de envios (tabela `emails`).

Segurança da chave:
- a chave fica SÓ no servidor, no arquivo .env da raiz do projeto (fora do
  git; o .env da produção, em C:\\HARLEY_PROD, é outro arquivo) ou em
  variável de ambiente:
      SENDGRID_API_KEY=SG....
      SENDGRID_REMETENTE=contato@sualoja.com.br   (remetente verificado no SendGrid)
      SENDGRID_NOME_REMETENTE=Harley Store        (opcional)
- nada daqui vai para o navegador; mensagens de erro nunca incluem a chave.

Regra de envio: o sistema NÃO envia e-mails sozinho. Todo envio parte de um
clique de um usuário (botão "Enviar e-mail" na ficha do cliente ou do lead).
Uma regra automática só deve ser criada com uma configuração explícita.

Cada tentativa é registrada na tabela `emails` (quando ela existir no Xano),
inclusive as que falharam ou que não puderam ser enviadas por falta de
configuração, com o motivo.
"""

from __future__ import annotations

from dataclasses import dataclass

from . import formatacao
from . import xano_client as xano

TABELA = "emails"
URL_SENDGRID = "https://api.sendgrid.com/v3/mail/send"

ENVIADO = "Enviado"
FALHOU = "Falhou"
NAO_CONFIGURADO = "Não configurado"


@dataclass
class ResultadoEnvio:
    status: str
    erro: str = ""
    registrado: bool = False

    @property
    def enviado(self) -> bool:
        return self.status == ENVIADO


def configuracao() -> tuple[str, str]:
    """(chave, remetente). Vazios se não configurados."""
    from .recursos import variavel
    return variavel("SENDGRID_API_KEY").strip(), variavel("SENDGRID_REMETENTE").strip()


def _nome_remetente() -> str:
    from .recursos import variavel
    return variavel("SENDGRID_NOME_REMETENTE").strip() or "Harley Store"


def _mensagem_de_erro(resposta) -> str:
    try:
        erros = resposta.json().get("errors") or []
        texto = "; ".join(e.get("message", "") for e in erros if e.get("message"))
    except ValueError:
        texto = ""
    explicacoes = {
        401: "chave do SendGrid inválida",
        403: "a chave não tem permissão de envio ou o remetente não foi verificado no SendGrid",
        413: "mensagem grande demais",
        429: "limite de envios do SendGrid atingido; tente mais tarde",
    }
    base = explicacoes.get(resposta.status_code, f"o SendGrid respondeu {resposta.status_code}")
    return f"{base}{': ' + texto if texto else ''}"[:500]


async def _enviar_sendgrid(chave: str, remetente: str, destinatario: str, assunto: str, mensagem: str) -> str:
    """"" se aceito; senão a mensagem de erro."""
    corpo = {
        "personalizations": [{"to": [{"email": destinatario}]}],
        "from": {"email": remetente, "name": _nome_remetente()},
        "subject": assunto,
        "content": [{"type": "text/plain", "value": mensagem}],
    }
    try:
        # _request não repete POST em falha de rede (não duplica e-mail) e
        # espera/repete só quando o SendGrid responde 429.
        resposta = await xano._request(
            "POST", URL_SENDGRID, json=corpo, headers={"Authorization": f"Bearer {chave}"}
        )
    except Exception:
        return "falha de conexão com o SendGrid"
    if resposta.status_code in (200, 202):
        return ""
    return _mensagem_de_erro(resposta)


async def registrar(destinatario: str, assunto: str, mensagem: str, resultado: ResultadoEnvio,
                    cliente_id: int = 0, lead_id: int = 0, usuario_id: int = 0) -> bool:
    if await xano.listar_se_existir(TABELA) is None:
        return False
    try:
        await xano.criar(TABELA, {
            "destinatario": destinatario,
            "assunto": assunto,
            "mensagem": mensagem,
            "status": resultado.status,
            "erro": resultado.erro or None,
            "cliente_id": int(cliente_id or 0),
            "lead_id": int(lead_id or 0),
            "usuario_id": int(usuario_id or 0),
        })
        return True
    except Exception:
        return False


async def enviar(destinatario: str, assunto: str, mensagem: str,
                 cliente_id: int = 0, lead_id: int = 0, usuario_id: int = 0) -> ResultadoEnvio:
    """Envia um e-mail de texto e registra a tentativa. Nunca levanta exceção:
    o resultado diz o que aconteceu."""
    destinatario = (destinatario or "").strip()
    assunto = (assunto or "").strip()
    mensagem = (mensagem or "").strip()
    if not formatacao.email_valido(destinatario):
        return ResultadoEnvio(FALHOU, "e-mail do destinatário inválido")
    if not assunto or not mensagem:
        return ResultadoEnvio(FALHOU, "preencha o assunto e a mensagem")

    chave, remetente = configuracao()
    if not chave or not remetente:
        resultado = ResultadoEnvio(
            NAO_CONFIGURADO, "SendGrid não configurado: defina SENDGRID_API_KEY e SENDGRID_REMETENTE no .env do servidor"
        )
    else:
        erro = await _enviar_sendgrid(chave, remetente, destinatario, assunto, mensagem)
        resultado = ResultadoEnvio(FALHOU, erro) if erro else ResultadoEnvio(ENVIADO)

    resultado.registrado = await registrar(destinatario, assunto, mensagem, resultado,
                                           cliente_id, lead_id, usuario_id)
    return resultado

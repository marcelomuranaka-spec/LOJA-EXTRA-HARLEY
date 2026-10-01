"""
Regras de negócio de leads (pessoas interessadas que ainda não são clientes).

Funil: Novo → Em atendimento → Proposta enviada → Negociação → Convertido
(virou cliente) ou Perdido.

Conversão LEAD → CLIENTE sem duplicar dados:
- se já existe cliente com o mesmo CPF/CNPJ, o lead só é LIGADO a ele;
- senão, o cliente é criado com os dados do lead (nome, telefone, Telegram,
  e-mail, observação), mais o CPF/CNPJ pedido na conversão (obrigatório no
  cadastro de clientes);
- o lead não é apagado: fica "Convertido", com `cliente_id` apontando para o
  cliente, e as interações dele aparecem na ficha do cliente.

Depende da tabela `leads` no Xano (ver recursos.py).
"""

from __future__ import annotations

from . import clientes_servico
from . import formatacao as fmt
from . import xano_client as xano

TABELA = "leads"
STATUS_LEAD = ["Novo", "Em atendimento", "Proposta enviada", "Negociação", "Convertido", "Perdido"]
ABERTOS = {"Novo", "Em atendimento", "Proposta enviada", "Negociação"}
CORES = {"Novo": "blue", "Em atendimento": "amber", "Proposta enviada": "purple", "Negociação": "orange",
         "Convertido": "green", "Perdido": "gray"}
ORIGENS = ["Loja (balcão)", "Telefone", "Telegram", "Instagram", "Facebook", "Site", "Indicação",
           "Telegram (bot)", "Evento", "Outro"]
INTERESSES = ["Comprar moto", "Peças e acessórios", "Serviço / oficina", "Vender ou consignar moto",
              "Financiamento", "Outro"]
CAMPOS = ["nome", "telefone", "telegram", "email", "origem", "interesse", "moto_interesse", "moto_id",
          "observacao", "status", "cliente_id", "usuario_id"]


class ErroValidacao(Exception):
    """Mensagem pronta para mostrar ao usuário."""


def status_de(registro: dict) -> str:
    status = (registro.get("status") or "").strip()
    return status if status in STATUS_LEAD else "Novo"


def validar_lead(form: dict) -> dict:
    nome = (form.get("nome") or "").strip()
    if not nome:
        raise ErroValidacao("Informe o nome do lead.")
    telefone = fmt.formatar_telefone(form.get("telefone"))
    telegram = (form.get("telegram") or "").strip()
    if telegram and not fmt.telegram_valido(telegram):
        raise ErroValidacao("Telegram: informe o @usuário (5 a 32 letras, números ou _) ou o número com DDD.")
    telegram = fmt.formatar_telegram(telegram)
    email = (form.get("email") or "").strip().lower()
    if not (telefone or telegram or email):
        raise ErroValidacao("Informe ao menos um contato: telefone, Telegram ou e-mail.")
    if email and not fmt.email_valido(email):
        raise ErroValidacao("E-mail inválido.")
    status = (form.get("status") or "Novo").strip()
    if status not in STATUS_LEAD:
        raise ErroValidacao("Status inválido.")
    try:
        moto_id = int(str(form.get("moto_id") or "0").split(" - ")[0])
    except ValueError:
        moto_id = 0
    return {
        "nome": nome,
        "telefone": telefone or None,
        "telegram": telegram or None,
        "email": email or None,
        "origem": (form.get("origem") or "").strip() or None,
        "interesse": (form.get("interesse") or "").strip() or None,
        "moto_interesse": (form.get("moto_interesse") or "").strip() or None,
        "moto_id": moto_id,
        "observacao": (form.get("observacao") or "").strip() or None,
        "status": status,
    }


def linha_lead(r: dict, motos_por_id: dict[int, str] | None = None, clientes_por_id: dict[int, str] | None = None) -> dict:
    motos_por_id = motos_por_id or {}
    clientes_por_id = clientes_por_id or {}
    status = status_de(r)
    moto = motos_por_id.get(int(r.get("moto_id") or 0), "")
    return {
        "id": str(r["id"]),
        "nome": r.get("nome") or "",
        "telefone": r.get("telefone") or "",
        "telegram": r.get("telegram") or "",
        "telegram_link": fmt.link_telegram(r.get("telegram")),
        "email": r.get("email") or "",
        "origem": r.get("origem") or "",
        "interesse": r.get("interesse") or "",
        "moto": moto or (r.get("moto_interesse") or ""),
        "moto_interesse": r.get("moto_interesse") or "",
        "moto_id": str(r.get("moto_id") or 0),
        "observacao": r.get("observacao") or "",
        "status": status,
        "status_cor": CORES[status],
        "aberto": status in ABERTOS,
        "cliente_id": str(r.get("cliente_id") or 0),
        "cliente_nome": clientes_por_id.get(int(r.get("cliente_id") or 0), ""),
        "data": fmt.data(r.get("created_at")),
        "criado_em": fmt.epoch(r.get("created_at")),
    }


LEAD_VAZIO = {**{k: "" for k in linha_lead({"id": 0})}, "aberto": False, "criado_em": 0, "status_cor": "gray"}


def filtrar(linhas: list[dict], busca: str, status: str, origem: str) -> list[dict]:
    termo = (busca or "").strip().lower()
    digitos = fmt.so_digitos(termo)
    resultado = []
    for l in linhas:
        if status == "Em aberto" and not l["aberto"]:
            continue
        if status not in ("Todos", "Em aberto") and l["status"] != status:
            continue
        if origem not in ("", "Todas") and l["origem"] != origem:
            continue
        if termo:
            texto = " ".join((l["nome"], l["email"], l["interesse"], l["moto"], l["origem"])).lower()
            texto += " " + l["telegram"].lower()
            numeros = fmt.so_digitos(l["telefone"] + l["telegram"])
            if termo not in texto and not (len(digitos) >= 3 and digitos in numeros):
                continue
        resultado.append(l)
    return sorted(resultado, key=lambda l: (l["criado_em"], int(l["id"])), reverse=True)


def contagem_funil(linhas: list[dict]) -> list[dict]:
    return [{"status": s, "qtd": sum(1 for l in linhas if l["status"] == s), "cor": CORES[s]} for s in STATUS_LEAD]


async def converter(lead_id: int, documento: str, usuario_id: int = 0) -> tuple[int, bool]:
    """Converte o lead em cliente. Devolve (id do cliente, criado agora?).
    Levanta ErroValidacao ou clientes_servico.ErroValidacao."""
    lead = await xano.ler_direto(TABELA, lead_id)
    if lead is None:
        raise ErroValidacao("Esse lead não existe mais.")
    if int(lead.get("cliente_id") or 0):
        raise ErroValidacao("Esse lead já foi convertido em cliente.")
    clientes = await xano.listar(clientes_servico.TABELA)
    digitos = fmt.so_digitos(documento)
    existente = next((c for c in clientes if fmt.so_digitos(c.get("cpf_cnpj")) == digitos and digitos), None)
    if existente:
        cliente_id, criado = int(existente["id"]), False
    else:
        form = {
            "nome_cliente": lead.get("nome"),
            "cpf_cnpj": documento,
            "telefone": lead.get("telefone"),
            "telegram": lead.get("telegram"),
            "email": lead.get("email"),
            "status": "Cliente",
            "observacoes": "\n".join(p for p in (
                f"Convertido de lead (origem: {lead.get('origem')})" if lead.get("origem") else "Convertido de lead",
                lead.get("observacao") or "") if p),
        }
        dados = clientes_servico.validar_cliente(form, clientes, None)
        from .recursos import campos_disponiveis
        novos = await campos_disponiveis("clientes")
        registro, _ = await clientes_servico.gravar(clientes_servico.TABELA, None, dados,
                                                    clientes_servico.CAMPOS_BASE_CLIENTE, novos)
        cliente_id, criado = int(registro["id"]), True
    await xano.atualizar_mesclando(TABELA, lead_id, {"status": "Convertido", "cliente_id": cliente_id})
    try:
        await xano.criar("interacoes", {
            "cliente_id": cliente_id, "lead_id": lead_id, "tipo": "Lead convertido em cliente",
            "descricao": f"{lead.get('nome')} virou cliente" + ("" if criado else " (ligado ao cadastro existente)"),
            "usuario_id": int(usuario_id or 0),
        })
    except Exception:
        pass  # sem a tabela de interações, a conversão continua valendo
    return cliente_id, criado

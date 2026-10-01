"""
Regras de negócio de clientes e motos dos clientes: validação, gravação e a
visão 360º do cliente (motos, compras, ordens de serviço, interações,
e-mails e a linha do tempo).

Separado dos states (telas) para poder ser testado sem o Reflex. As funções
`montar_*` são puras: recebem as listagens das tabelas e devolvem dicts
prontos para a tela.

Campos novos (Telegram, cidade, status... ver `recursos.py`) só são enviados
ao Xano quando já existem lá; enquanto não existem, o resto do cadastro
continua funcionando como antes.
"""

from __future__ import annotations

from . import formatacao as fmt
from . import imagens
from . import xano_client as xano
from .vendas_servico import CAMPO_VENDA, esta_cancelada

TABELA = "clientes"
TABELA_MOTOS = "motos_clientes"

STATUS_CLIENTE = ["Lead", "Cliente", "Cliente recorrente", "Inativo"]
STATUS_PADRAO = "Cliente"  # clientes cadastrados antes do campo status
CORES_STATUS = {"Lead": "blue", "Cliente": "green", "Cliente recorrente": "orange", "Inativo": "gray"}


class ErroValidacao(Exception):
    """Mensagem pronta para mostrar ao usuário."""


def status_de(registro: dict) -> str:
    status = (registro.get("status") or "").strip()
    return status if status in STATUS_CLIENTE else STATUS_PADRAO


# ------------------------------------------------------------------ clientes

def validar_cliente(form: dict, outros: list[dict], cliente_id: int | None, cpf_original: str = "") -> dict:
    """form: nome_cliente, cpf_cnpj, telefone, telegram, email, endereco,
    cidade, status, observacoes (strings). Devolve os dados para o Xano
    (todos os campos; quem grava filtra os que existem). Levanta ErroValidacao."""
    nome = (form.get("nome_cliente") or "").strip()
    documento = (form.get("cpf_cnpj") or "").strip()
    if not nome:
        raise ErroValidacao("Informe o nome do cliente.")
    digitos = fmt.so_digitos(documento)
    if len(digitos) not in (11, 14):
        raise ErroValidacao("CPF precisa ter 11 dígitos e CNPJ, 14.")
    # Dígito verificador só em cadastro novo ou documento alterado: não trava
    # a edição de clientes antigos.
    if (cliente_id is None or digitos != fmt.so_digitos(cpf_original)) and not fmt.cpf_cnpj_valido(digitos):
        raise ErroValidacao("CPF/CNPJ inválido (confira os números).")
    if any(fmt.so_digitos(r.get("cpf_cnpj")) == digitos and r.get("id") != cliente_id for r in outros):
        raise ErroValidacao("Já existe um cliente com esse CPF/CNPJ.")
    email = (form.get("email") or "").strip().lower()
    if email and not fmt.email_valido(email):
        raise ErroValidacao("E-mail inválido.")
    telegram = (form.get("telegram") or "").strip()
    if telegram and not fmt.telegram_valido(telegram):
        raise ErroValidacao("Telegram: informe o @usuário (5 a 32 letras, números ou _) ou o número com DDD.")
    status = (form.get("status") or "").strip() or STATUS_PADRAO
    if status not in STATUS_CLIENTE:
        raise ErroValidacao("Status inválido.")
    return {
        "nome_cliente": nome,
        "cpf_cnpj": fmt.formatar_cpf_cnpj(digitos),
        "telefone": fmt.formatar_telefone(form.get("telefone")) or None,
        "email": email or None,
        "endereco": (form.get("endereco") or "").strip() or None,
        "telegram": fmt.formatar_telegram(telegram) or None,
        "cidade": (form.get("cidade") or "").strip() or None,
        "status": status,
        "observacoes": (form.get("observacoes") or "").strip() or None,
    }


CAMPOS_BASE_CLIENTE = {"nome_cliente", "cpf_cnpj", "telefone", "email", "endereco"}


async def gravar(tabela: str, registro_id: int | None, dados: dict, campos_base: set[str],
                 campos_novos: set[str]) -> tuple[dict, list[str]]:
    """Cria ou altera só com os campos que existem no Xano (base + novos já
    criados), preservando o resto do registro. Devolve (registro, campos
    novos que o Xano não gravou)."""
    enviar = {k: v for k, v in dados.items() if k in campos_base or k in campos_novos}
    if registro_id is None:
        registro = await xano.criar(tabela, enviar)
    else:
        registro = await xano.atualizar_mesclando(tabela, registro_id, enviar)
    return registro, xano.campos_nao_gravados(enviar, registro, campos_novos)


def linha_cliente(r: dict, qtd_motos: int = 0, qtd_compras: int = 0) -> dict:
    status = status_de(r)
    return {
        "id": str(r["id"]),
        "nome_cliente": r.get("nome_cliente") or "",
        "cpf_cnpj": r.get("cpf_cnpj") or "",
        "telefone": r.get("telefone") or "",
        "telegram": r.get("telegram") or "",
        "telegram_link": fmt.link_telegram(r.get("telegram")),
        "email": r.get("email") or "",
        "endereco": r.get("endereco") or "",
        "cidade": r.get("cidade") or "",
        "observacoes": r.get("observacoes") or "",
        "status": status,
        "status_cor": CORES_STATUS[status],
        "data_cadastro": fmt.data(r.get("created_at")),
        "criado_em": fmt.epoch(r.get("created_at")),
        "qtd_motos": qtd_motos,
        "qtd_compras": qtd_compras,
    }


def _vazio(exemplo: dict) -> dict:
    return {k: (0 if isinstance(v, (int, float)) and not isinstance(v, bool) else
                False if isinstance(v, bool) else "") for k, v in exemplo.items()}


CLIENTE_VAZIO = _vazio(linha_cliente({"id": 0}))
del CLIENTE_VAZIO["status_cor"]
CLIENTE_VAZIO["status_cor"] = "gray"


def filtrar_clientes(linhas: list[dict], busca: str, status: str, cidade: str, ordem: str) -> list[dict]:
    termo = (busca or "").strip().lower()
    termo_digitos = fmt.so_digitos(termo)
    resultado = []
    for linha in linhas:
        if status and status != "Todos" and linha["status"] != status:
            continue
        if cidade and cidade != "Todas" and linha["cidade"] != cidade:
            continue
        if termo:
            texto = " ".join((linha["nome_cliente"], linha["email"], linha["cidade"])).lower()
            numeros = fmt.so_digitos(" ".join((linha["cpf_cnpj"], linha["telefone"], linha["telegram"])))
            if termo not in texto and not (termo_digitos and len(termo_digitos) >= 3 and termo_digitos in numeros):
                continue
        resultado.append(linha)
    chaves = {
        "Nome (A–Z)": (lambda l: l["nome_cliente"].lower(), False),
        "Nome (Z–A)": (lambda l: l["nome_cliente"].lower(), True),
        "Mais recentes": (lambda l: (l["criado_em"], int(l["id"])), True),
        "Mais antigos": (lambda l: (l["criado_em"], int(l["id"])), False),
        "Mais compras": (lambda l: (l["qtd_compras"], l["nome_cliente"].lower()), True),
    }
    chave, reverso = chaves.get(ordem, chaves["Nome (A–Z)"])
    return sorted(resultado, key=chave, reverse=reverso)


# ------------------------------------------------------------ motos clientes

CAMPOS_BASE_MOTO = {"id_cliente", "modelo", "placa", "chassi", "imagem"}


def validar_moto(form: dict, outras: list[dict], moto_id: int | None, clientes_ids: set[int]) -> dict:
    """form: id_cliente, marca, modelo, ano, cor, placa, chassi, quilometragem,
    observacoes, imagem. A moto SEMPRE pertence a um cliente."""
    try:
        id_cliente = int(form.get("id_cliente") or 0)
    except (TypeError, ValueError):
        id_cliente = 0
    if not id_cliente or id_cliente not in clientes_ids:
        raise ErroValidacao("Escolha o cliente dono da moto.")
    modelo = (form.get("modelo") or "").strip()
    placa = (form.get("placa") or "").strip().upper().replace(" ", "")
    chassi = (form.get("chassi") or "").strip().upper().replace(" ", "")
    if not modelo or not placa or not chassi:
        raise ErroValidacao("Preencha modelo, placa e chassi.")
    try:
        ano = fmt.inteiro(form.get("ano"))
        km = fmt.inteiro(form.get("quilometragem"))
    except ValueError:
        raise ErroValidacao("Ano e quilometragem precisam ser números.")
    if ano and not 1903 <= ano <= 2100:
        raise ErroValidacao("Ano inválido.")
    if km < 0:
        raise ErroValidacao("A quilometragem não pode ser negativa.")
    for r in outras:
        if r.get("id") == moto_id:
            continue
        if (r.get("placa") or "").upper() == placa:
            raise ErroValidacao("Já existe uma moto cadastrada com essa placa.")
        if (r.get("chassi") or "").upper() == chassi:
            raise ErroValidacao("Já existe uma moto cadastrada com esse chassi.")
    return {
        "id_cliente": id_cliente,
        "modelo": modelo,
        "placa": placa,
        "chassi": chassi,
        "imagem": form.get("imagem") or None,
        "marca": (form.get("marca") or "").strip() or None,
        "ano": ano or None,
        "cor": (form.get("cor") or "").strip() or None,
        "quilometragem": km or None,
        "observacoes": (form.get("observacoes") or "").strip() or None,
    }


def linha_moto(r: dict, nome_cliente: str = "") -> dict:
    url, local = imagens.separar(r.get("imagem"))
    titulo = " ".join(p for p in ((r.get("marca") or "").strip(), r.get("modelo") or "") if p)
    return {
        "id": str(r["id"]),
        "id_cliente": str(r.get("id_cliente") or 0),
        "cliente_nome": nome_cliente or "(cliente removido)",
        "titulo": titulo,
        "marca": r.get("marca") or "",
        "modelo": r.get("modelo") or "",
        "ano": str(r.get("ano") or ""),
        "cor": r.get("cor") or "",
        "placa": r.get("placa") or "",
        "chassi": r.get("chassi") or "",
        "quilometragem": fmt.moeda(r.get("quilometragem") or 0).split(",")[0] if r.get("quilometragem") else "",
        "observacoes": r.get("observacoes") or "",
        "imagem": r.get("imagem") or "",
        "foto_url": url,
        "foto_local": local,
        "data_cadastro": fmt.data(r.get("created_at")),
    }


MOTO_VAZIA = _vazio(linha_moto({"id": 0}))


# ----------------------------------------------------------- visão 360º

def montar_compras(cliente_id: int, transacoes: list[dict], itens: list[dict]) -> list[dict]:
    resumo: dict[int, list[str]] = {}
    for item in itens:
        vid = int(item.get(CAMPO_VENDA) or 0)
        resumo.setdefault(vid, []).append(f"{item.get('quantidade') or 0}× {item.get('descricao') or ''}")
    compras = []
    for t in sorted((t for t in transacoes if int(t.get("id_cliente") or 0) == cliente_id),
                    key=lambda t: fmt.epoch(t.get("data_transacao")), reverse=True):
        cancelada = esta_cancelada(t)
        compras.append({
            "id": str(t["id"]),
            "data": fmt.data_hora(t.get("data_transacao")),
            "epoch": fmt.epoch(t.get("data_transacao")),
            "tipo": t.get("tipo_transacao") or "",
            "total": fmt.reais(t.get("valor_total")),
            "valor": float(t.get("valor_total") or 0),
            "forma_pagamento": t.get("forma_pagamento") or "",
            "itens": "; ".join(resumo.get(int(t["id"]), [])) or "itens não registrados (venda antiga)",
            "cancelada": cancelada,
        })
    return compras


def montar_ordens(motos_do_cliente: list[dict], ordens: list[dict]) -> list[dict]:
    nomes = {int(m["id"]): f"{m.get('modelo') or ''} ({m.get('placa') or ''})" for m in motos_do_cliente}
    resultado = []
    for o in sorted((o for o in ordens if int(o.get("id_moto_cliente") or 0) in nomes),
                    key=lambda o: fmt.epoch(o.get("data_abertura")), reverse=True):
        resultado.append({
            "id": str(o["id"]),
            "data": fmt.data(o.get("data_abertura")),
            "epoch": fmt.epoch(o.get("data_abertura")),
            "moto": nomes[int(o["id_moto_cliente"])],
            "status": (o.get("status") or "").replace("_", " ").capitalize(),
        })
    return resultado


def montar_interacoes(registros: list[dict], campo: str, registro_id: int) -> list[dict]:
    return [
        {
            "id": str(r["id"]),
            "data": fmt.data_hora(r.get("created_at")),
            "epoch": fmt.epoch(r.get("created_at")),
            "tipo": r.get("tipo") or "Contato",
            "descricao": r.get("descricao") or "",
        }
        for r in sorted((r for r in registros if int(r.get(campo) or 0) == registro_id),
                        key=lambda r: fmt.epoch(r.get("created_at")), reverse=True)
    ]


def montar_emails(registros: list[dict], campo: str, registro_id: int) -> list[dict]:
    return [
        {
            "id": str(r["id"]),
            "data": fmt.data_hora(r.get("created_at")),
            "epoch": fmt.epoch(r.get("created_at")),
            "destinatario": r.get("destinatario") or "",
            "assunto": r.get("assunto") or "",
            "status": r.get("status") or "",
            "erro": r.get("erro") or "",
        }
        for r in sorted((r for r in registros if int(r.get(campo) or 0) == registro_id),
                        key=lambda r: fmt.epoch(r.get("created_at")), reverse=True)
    ]


def montar_linha_do_tempo(cliente: dict, compras: list[dict], ordens: list[dict],
                          interacoes: list[dict], emails: list[dict]) -> list[dict]:
    eventos = []
    if cliente.get("created_at"):
        eventos.append({"epoch": fmt.epoch(cliente["created_at"]), "icone": "user-plus",
                        "titulo": "Cliente cadastrado", "texto": ""})
    for c in compras:
        eventos.append({"epoch": c["epoch"], "icone": "shopping-cart",
                        "titulo": f"Venda nº {c['id']} — {c['total']}" + (" (cancelada)" if c["cancelada"] else ""),
                        "texto": c["itens"]})
    for o in ordens:
        eventos.append({"epoch": o["epoch"], "icone": "wrench",
                        "titulo": f"Ordem de serviço nº {o['id']} — {o['status']}", "texto": o["moto"]})
    for i in interacoes:
        eventos.append({"epoch": i["epoch"], "icone": "message-circle", "titulo": i["tipo"], "texto": i["descricao"]})
    for e in emails:
        eventos.append({"epoch": e["epoch"], "icone": "mail", "titulo": f"E-mail: {e['assunto']}",
                        "texto": f"{e['status']}{' — ' + e['erro'] if e['erro'] else ''}"})
    eventos.sort(key=lambda e: e["epoch"], reverse=True)
    return [
        {**e, "data": fmt.data_hora(e["epoch"]) if e["epoch"] else "—"}
        for e in eventos
    ]

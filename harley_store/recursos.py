"""
Recursos novos que dependem de tabelas ou campos que ainda precisam ser
criados no painel do Xano (o plano Free não permite criá-los pela API).

Cada recurso já está pronto no app e LIGA SOZINHO quando o Xano tiver o que
ele precisa: as telas perguntam aqui (`campos_disponiveis`, `tabela_existe`)
e, enquanto falta algo, mostram o que já funciona e um aviso. A tela
"Configuração do sistema" (só administradores) lista tudo com o passo a passo.

Regras das mudanças no Xano (para não perder dados):
- só ACRESCENTAR: campos novos opcionais e tabelas novas; nada é renomeado
  ou apagado;
- tabela nova: CRUD gerado pelo assistente "CRUD Database Operations" no MESMO
  grupo de API das outras tabelas (api:LtU_pM2N), exigindo login como elas;
- campo novo em tabela existente: incluir o campo também nos inputs dos
  endpoints POST e PATCH da tabela (senão o Xano ignora o valor em silêncio).

O espelho em `xano/table/*.xs` documenta cada tabela nova.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from . import xano_client as xano


@dataclass(frozen=True)
class Campo:
    nome: str
    tipo: str          # como aparece no Xano: text, integer, decimal, boolean, timestamp
    para_que: str


@dataclass(frozen=True)
class Requisito:
    chave: str
    titulo: str
    libera: str        # o que passa a funcionar no app
    tabela: str = ""   # tabela do Xano ("" = não é tabela)
    nova: bool = False # tabela nova (True) ou campos em tabela existente (False)
    campos: tuple[Campo, ...] = ()
    tipo: str = "tabela"  # "tabela" | "endpoint" | "env"


_CRIADO_EM = Campo("created_at", "timestamp (padrão: now)", "data de cadastro")

REQUISITOS: list[Requisito] = [
    Requisito(
        "clientes", "Clientes: WhatsApp, cidade, observações, status e data de cadastro",
        "ficha completa do cliente, filtro por status e por cidade, botão do WhatsApp",
        tabela="clientes",
        campos=(
            Campo("whatsapp", "text", "número do WhatsApp"),
            Campo("cidade", "text", "cidade"),
            Campo("observacoes", "text", "observações"),
            Campo("status", "text", "Lead, Cliente, Cliente recorrente ou Inativo"),
            _CRIADO_EM,
        ),
    ),
    Requisito(
        "motos_clientes", "Motos dos clientes: marca, ano, cor, quilometragem, observações e data",
        "ficha completa das motos dos clientes",
        tabela="motos_clientes",
        campos=(
            Campo("marca", "text", "marca"),
            Campo("ano", "integer", "ano"),
            Campo("cor", "text", "cor"),
            Campo("quilometragem", "integer", "km"),
            Campo("observacoes", "text", "observações"),
            _CRIADO_EM,
        ),
    ),
    Requisito(
        "upload_imagem", "Envio de fotos para o Xano (endpoint upload/image)",
        "fotos das motos da loja; fotos de produtos e motos dos clientes iguais no "
        "desenvolvimento e na produção (sem ele, ficam só no computador onde foram enviadas)",
        tipo="endpoint",
    ),
    Requisito(
        "categorias", "Tabela nova: categorias",
        "cadastro de categorias (criar, editar, ativar/desativar, excluir sem dependências)",
        tabela="categorias", nova=True,
        campos=(
            Campo("nome", "text", "nome da categoria"),
            Campo("ativo", "boolean", "ativa ou desativada"),
            _CRIADO_EM,
        ),
    ),
    Requisito(
        "produtos", "Produtos: categoria, SKU, preço de custo, estoque mínimo e situação",
        "produto ligado à categoria, código/SKU, margem, alerta pelo estoque mínimo de cada produto",
        tabela="produtos",
        campos=(
            Campo("categoria_id", "integer", "categoria (id da tabela categorias)"),
            Campo("sku", "text", "código/SKU"),
            Campo("preco_custo", "decimal", "preço de custo"),
            Campo("estoque_minimo", "integer", "estoque mínimo"),
            Campo("ativo", "boolean", "ativo ou inativo"),
        ),
    ),
    Requisito(
        "formas_pagamento", "Tabela nova: formas_pagamento",
        "formas de pagamento configuráveis (sem ela, o app usa Dinheiro, PIX, débito e crédito)",
        tabela="formas_pagamento", nova=True,
        campos=(
            Campo("nome", "text", "nome (ex.: PIX)"),
            Campo("ativo", "boolean", "disponível no balcão"),
            _CRIADO_EM,
        ),
    ),
    Requisito(
        "transacoes", "Vendas: desconto, forma de pagamento, usuário responsável e moto vendida",
        "registro da forma de pagamento, do desconto, de quem registrou a venda e da moto "
        "da loja vendida (o cancelamento devolve a moto ao estoque)",
        tabela="transacoes",
        campos=(
            Campo("desconto", "decimal", "valor do desconto"),
            Campo("forma_pagamento", "text", "forma de pagamento"),
            Campo("usuario_id", "integer", "conta que registrou a venda"),
            Campo("moto_id", "integer", "moto da loja vendida (0 = nenhuma)"),
        ),
    ),
    Requisito(
        "leads", "Tabela nova: leads",
        "controle de leads (funil de atendimento) e conversão de lead em cliente",
        tabela="leads", nova=True,
        campos=(
            Campo("nome", "text", "nome"),
            Campo("telefone", "text", "telefone"),
            Campo("whatsapp", "text", "WhatsApp"),
            Campo("email", "text", "e-mail"),
            Campo("origem", "text", "de onde veio (Loja, Instagram, Telegram...)"),
            Campo("interesse", "text", "o que procura"),
            Campo("moto_interesse", "text", "moto de interesse (texto livre)"),
            Campo("moto_id", "integer", "moto da loja de interesse (0 = nenhuma)"),
            Campo("observacao", "text", "observação"),
            Campo("status", "text", "Novo, Em atendimento, Proposta enviada, Negociação, Convertido ou Perdido"),
            Campo("cliente_id", "integer", "cliente criado na conversão"),
            Campo("usuario_id", "integer", "conta que cadastrou"),
            _CRIADO_EM,
        ),
    ),
    Requisito(
        "interacoes", "Tabela nova: interacoes",
        "linha do tempo do cliente e do lead (contatos, orçamentos enviados, visitas...)",
        tabela="interacoes", nova=True,
        campos=(
            Campo("cliente_id", "integer", "cliente (0 = nenhum)"),
            Campo("lead_id", "integer", "lead (0 = nenhum)"),
            Campo("tipo", "text", "Contato, Orçamento enviado, Visita, Pós-venda..."),
            Campo("descricao", "text", "o que aconteceu"),
            Campo("usuario_id", "integer", "conta que registrou"),
            _CRIADO_EM,
        ),
    ),
    Requisito(
        "emails", "Tabela nova: emails",
        "histórico de e-mails enviados (destinatário, assunto, data, situação e erro)",
        tabela="emails", nova=True,
        campos=(
            Campo("destinatario", "text", "e-mail de destino"),
            Campo("assunto", "text", "assunto"),
            Campo("mensagem", "text", "texto enviado"),
            Campo("status", "text", "Enviado, Falhou ou Não configurado"),
            Campo("erro", "text", "mensagem de erro, quando houver"),
            Campo("cliente_id", "integer", "cliente (0 = nenhum)"),
            Campo("lead_id", "integer", "lead (0 = nenhum)"),
            Campo("usuario_id", "integer", "conta que enviou"),
            _CRIADO_EM,
        ),
    ),
    Requisito(
        "sendgrid", "Chave do SendGrid no arquivo .env do servidor",
        "envio de e-mails pelo SendGrid (sempre manual, por um botão; nada é enviado sozinho)",
        tipo="env",
    ),
]

POR_CHAVE = {r.chave: r for r in REQUISITOS}


def nomes(chave: str) -> list[str]:
    return [c.nome for c in POR_CHAVE[chave].campos]


async def tabela_existe(tabela: str) -> bool:
    return await xano.listar_se_existir(tabela) is not None


async def campos_disponiveis(chave: str) -> set[str]:
    """Campos do recurso que já existem no Xano. Tabela vazia: não dá para
    conferir, então considera todos (e a gravação confere depois, com
    `xano.campos_nao_gravados`)."""
    req = POR_CHAVE[chave]
    desejados = set(nomes(chave))
    existentes = await xano.campos(req.tabela)
    if existentes is None:
        return set()
    if not existentes:
        return desejados
    return desejados & existentes


async def endpoint_upload_existe() -> bool:
    """Pergunta ao Xano sem mandar arquivo: 404 = endpoint não existe;
    qualquer outra resposta (erro de entrada) = existe. Não grava nada."""
    resposta = await xano._request_xano("POST", f"{xano.BASE_URL}/upload/image", json={})
    return resposta.status_code != 404


def sendgrid_configurado() -> bool:
    from .email_servico import configuracao
    chave, remetente = configuracao()
    return bool(chave and remetente)


async def situacao(conferir_upload: bool = True) -> list[dict]:
    """Para a tela de Configuração: um item por requisito, com o que falta."""
    itens = []
    for req in REQUISITOS:
        faltando: list[str] = []
        if req.tipo == "endpoint":
            try:
                ok = await endpoint_upload_existe() if conferir_upload else False
            except Exception:
                ok = False
            faltando = [] if ok else ["upload/image"]
        elif req.tipo == "env":
            faltando = [] if sendgrid_configurado() else ["SENDGRID_API_KEY", "SENDGRID_REMETENTE"]
        else:
            existentes = await xano.campos(req.tabela)
            if existentes is None:
                faltando = ["(tabela)"] + nomes(req.chave)
            elif existentes:
                faltando = [n for n in nomes(req.chave) if n not in existentes]
        itens.append({
            "chave": req.chave,
            "titulo": req.titulo,
            "libera": req.libera,
            "ativo": not faltando,
            "falta_tabela": "(tabela)" in faltando,
            "faltando": ", ".join(n for n in faltando if n != "(tabela)"),
            "tabela": req.tabela,
            "nova": req.nova,
            "tipo": req.tipo,
            "campos": [{"nome": c.nome, "tipo": c.tipo, "para_que": c.para_que,
                        "falta": c.nome in faltando} for c in req.campos],
        })
    return itens


def variavel(nome: str) -> str:
    """Valor de configuração: variável de ambiente ou linha do .env."""
    return os.environ.get(nome) or xano.ler_env().get(nome, "")

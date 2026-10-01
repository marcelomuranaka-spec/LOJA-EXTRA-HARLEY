"""
Regras de negócio de produtos, categorias e alerta de estoque.

Categoria do produto:
- enquanto a tabela `categorias` não existe no Xano, a categoria é o texto
  livre do campo `produtos.categoria` (como sempre foi);
- com a tabela e o campo `produtos.categoria_id`, o produto passa a apontar
  para a categoria. O texto `produtos.categoria` continua sendo gravado com o
  nome da categoria (é obrigatório no Xano e outras telas o exibem).

Estoque: o saldo só muda pelo módulo `estoque.py` (vendas, OS, compras,
ajuste de estoque), sempre no servidor e com trava. Editar o cadastro de um
produto não sobrescreve o saldo. Alerta: saldo menor ou igual ao estoque
mínimo do produto (ou `LIMITE_PADRAO`, se o produto não tiver mínimo).
"""

from __future__ import annotations

import unicodedata

from . import formatacao as fmt
from . import imagens
from . import xano_client as xano

TABELA = "produtos"
TABELA_CATEGORIAS = "categorias"
LIMITE_PADRAO = 5
CATEGORIAS_SUGERIDAS = ["Peças", "Acessórios", "Capacetes", "Vestuário", "Lubrificantes", "Outros"]
CAMPOS_BASE = {"nome_produto", "descricao", "categoria", "estoque_qtd", "preco_venda", "imagem"}


class ErroValidacao(Exception):
    """Mensagem pronta para mostrar ao usuário."""


def chave_nome(texto: str) -> str:
    """Compara nomes sem diferenciar maiúsculas e acentos ("Peças" = "pecas")."""
    sem_acento = unicodedata.normalize("NFKD", texto or "").encode("ascii", "ignore").decode()
    return " ".join(sem_acento.lower().split())


def ativo(registro: dict) -> bool:
    """Campo `ativo` vazio (registros antigos) conta como ativo."""
    return registro.get("ativo") is not False


def minimo(registro: dict) -> int:
    valor = registro.get("estoque_minimo")
    return int(valor) if valor not in (None, "") else LIMITE_PADRAO


def estoque_baixo(registro: dict) -> bool:
    return int(registro.get("estoque_qtd") or 0) <= minimo(registro)


def nome_categoria(produto: dict, categorias_por_id: dict[int, dict]) -> str:
    categoria = categorias_por_id.get(int(produto.get("categoria_id") or 0))
    return categoria["nome"] if categoria else (produto.get("categoria") or "").strip() or "Sem categoria"


def linha_produto(r: dict, categorias_por_id: dict[int, dict] | None = None) -> dict:
    categorias_por_id = categorias_por_id or {}
    url, local = imagens.separar(r.get("imagem"))
    custo = float(r.get("preco_custo") or 0)
    venda = float(r.get("preco_venda") or 0)
    margem = f"{(venda - custo) / venda * 100:.0f}%" if custo and venda else ""
    saldo = int(r.get("estoque_qtd") or 0)
    return {
        "id": str(r["id"]),
        "nome_produto": r.get("nome_produto") or "",
        "descricao": r.get("descricao") or "",
        "categoria": nome_categoria(r, categorias_por_id),
        "categoria_id": str(r.get("categoria_id") or 0),
        "sku": r.get("sku") or "",
        "preco_custo": fmt.moeda(custo) if r.get("preco_custo") not in (None, "") else "",
        "preco_venda": fmt.moeda(venda),
        "margem": margem,
        "estoque_qtd": saldo,
        "estoque_minimo": minimo(r),
        "tem_minimo": r.get("estoque_minimo") not in (None, ""),
        "estoque_baixo": estoque_baixo(r),
        "ativo": ativo(r),
        "imagem": r.get("imagem") or "",
        "foto_url": url,
        "foto_local": local,
    }


def filtrar(linhas: list[dict], busca: str, categoria: str, situacao: str, so_baixo: bool) -> list[dict]:
    termo = chave_nome(busca)
    resultado = []
    for l in linhas:
        if categoria not in ("", "Todas") and l["categoria"] != categoria:
            continue
        if situacao == "Ativos" and not l["ativo"]:
            continue
        if situacao == "Inativos" and l["ativo"]:
            continue
        if so_baixo and not (l["estoque_baixo"] and l["ativo"]):
            continue
        if termo and termo not in chave_nome(" ".join((l["nome_produto"], l["sku"], l["descricao"], l["categoria"]))):
            continue
        resultado.append(l)
    return sorted(resultado, key=lambda l: chave_nome(l["nome_produto"]))


def validar_produto(form: dict, outros: list[dict], produto_id: int | None,
                    categorias: list[dict] | None) -> dict:
    """form: nome_produto, descricao, categoria (nome ou id, ver abaixo), sku,
    preco_custo, preco_venda, estoque_minimo, estoque_inicial, ativo, imagem.
    `categorias` = lista da tabela categorias, ou None se ela não existe
    (aí `categoria` é o texto livre)."""
    nome = (form.get("nome_produto") or "").strip()
    if not nome:
        raise ErroValidacao("Informe o nome do produto.")
    categoria_id = 0
    if categorias is not None and categorias:
        try:
            categoria_id = int(str(form.get("categoria") or "0").split(" - ")[0])
        except ValueError:
            categoria_id = 0
        categoria = next((c for c in categorias if c["id"] == categoria_id), None)
        if categoria is None:
            raise ErroValidacao("Escolha a categoria do produto.")
        nome_cat = categoria["nome"]
    else:
        nome_cat = (form.get("categoria") or "").strip()
        if not nome_cat:
            raise ErroValidacao("Informe a categoria do produto.")
    try:
        preco_venda = fmt.numero(form.get("preco_venda"))
        preco_custo = fmt.numero(form.get("preco_custo"))
        estoque_minimo = fmt.inteiro(form.get("estoque_minimo")) if str(form.get("estoque_minimo") or "").strip() else None
        estoque_inicial = fmt.inteiro(form.get("estoque_inicial"))
    except ValueError:
        raise ErroValidacao("Preços, estoque e estoque mínimo precisam ser números.")
    if preco_venda < 0 or preco_custo < 0 or estoque_inicial < 0 or (estoque_minimo or 0) < 0:
        raise ErroValidacao("Preços e quantidades não podem ser negativos.")
    sku = (form.get("sku") or "").strip().upper()
    if sku and any((r.get("sku") or "").strip().upper() == sku and r.get("id") != produto_id for r in outros):
        raise ErroValidacao("Já existe um produto com esse código/SKU.")
    dados = {
        "nome_produto": nome,
        "descricao": (form.get("descricao") or "").strip() or None,
        "categoria": nome_cat,
        "preco_venda": round(preco_venda, 2),
        "imagem": form.get("imagem") or None,
        "categoria_id": categoria_id or None,
        "sku": sku or None,
        "preco_custo": round(preco_custo, 2) if str(form.get("preco_custo") or "").strip() else None,
        "estoque_minimo": estoque_minimo,
        "ativo": bool(form.get("ativo", True)),
    }
    if produto_id is None:
        dados["estoque_qtd"] = estoque_inicial
    return dados


# ---------------------------------------------------------------- categorias

def validar_categoria(nome: str, categorias: list[dict], categoria_id: int | None) -> str:
    nome = " ".join((nome or "").split())
    if not nome:
        raise ErroValidacao("Informe o nome da categoria.")
    if any(chave_nome(c.get("nome")) == chave_nome(nome) and c.get("id") != categoria_id for c in categorias):
        raise ErroValidacao("Já existe uma categoria com esse nome.")
    return nome


def produtos_da_categoria(categoria: dict, produtos: list[dict]) -> list[dict]:
    """Ligados pelo id ou, nos produtos ainda sem categoria_id, pelo nome."""
    return [
        p for p in produtos
        if int(p.get("categoria_id") or 0) == categoria["id"]
        or (not p.get("categoria_id") and chave_nome(p.get("categoria")) == chave_nome(categoria.get("nome")))
    ]


def plano_importacao(produtos: list[dict], categorias: list[dict]) -> tuple[list[str], list[tuple[int, str]]]:
    """O que importar: (nomes de categorias a criar, [(id do produto, nome da
    categoria)] a ligar). Puro e idempotente: rodar de novo não duplica nada."""
    existentes = {chave_nome(c["nome"]) for c in categorias}
    a_criar: list[str] = []
    for nome in [*(p.get("categoria") or "" for p in produtos), *CATEGORIAS_SUGERIDAS]:
        nome = " ".join(nome.split())
        if nome and chave_nome(nome) not in existentes:
            existentes.add(chave_nome(nome))
            a_criar.append(nome)
    a_ligar = [
        (p["id"], " ".join((p.get("categoria") or "").split()))
        for p in produtos
        if not p.get("categoria_id") and (p.get("categoria") or "").strip()
    ]
    return a_criar, a_ligar


async def importar_categorias(pode_ligar: bool) -> tuple[int, int]:
    """Cria as categorias que já existem como texto nos produtos (mais as
    sugeridas) e liga cada produto à sua (`categoria_id`), se o campo existir.
    Devolve (categorias criadas, produtos ligados)."""
    from . import estoque
    produtos = await xano.listar(TABELA)
    categorias = await xano.listar(TABELA_CATEGORIAS)
    a_criar, a_ligar = plano_importacao(produtos, categorias)
    for nome in a_criar:
        categorias.append(await xano.criar(TABELA_CATEGORIAS, {"nome": nome, "ativo": True}))
    ligados = 0
    if pode_ligar:
        por_nome = {chave_nome(c["nome"]): c for c in categorias}
        for produto_id, nome in a_ligar:
            categoria = por_nome.get(chave_nome(nome))
            if categoria:
                await estoque.editar_produto(produto_id, {"categoria_id": categoria["id"], "categoria": categoria["nome"]})
                ligados += 1
    return len(a_criar), ligados

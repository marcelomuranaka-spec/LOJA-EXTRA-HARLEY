"""
State de Produtos (catálogo + estoque). Dados vêm do backend Xano.

Regras em `produtos_servico.py`. O saldo do estoque nunca é gravado direto
pelo formulário: no cadastro novo entra o estoque inicial; depois, o saldo
só muda por venda, OS, compra ou pelo "Ajustar estoque" (que usa a trava de
`estoque.py`). Editar o produto preserva o saldo atual.
"""

import asyncio
import math
from typing import Optional

import reflex as rx

from .. import estoque, imagens, recursos
from .. import formatacao as fmt
from .. import produtos_servico as servico
from .. import xano_client as xano
from ..seguranca import sessao_ok
from .. import integridade

POR_PAGINA = 20
SITUACOES = ["Ativos", "Inativos", "Todos"]
TIPOS_AJUSTE = ["Entrada (somar)", "Saída (subtrair)", "Contagem (saldo exato)"]


class ProdutosState(rx.State):
    produtos: list[dict] = []
    total: int = 0
    pagina: int = 1
    busca: str = ""
    filtro_categoria: str = "Todas"
    filtro_situacao: str = "Ativos"
    somente_estoque_baixo: bool = False
    categorias_filtro: list[str] = ["Todas"]
    qtd_estoque_baixo: int = 0

    # recursos do Xano
    usa_tabela_categorias: bool = False   # categorias vêm da tabela (select)
    tem_extras: bool = False              # sku, custo, mínimo, ativo
    categorias_opcoes: list[str] = []     # "3 - Peças" (tabela) ou nomes (texto)

    # formulário
    dialogo_aberto: bool = False
    form_id: Optional[int] = None
    nome_produto: str = ""
    descricao: str = ""
    categoria: str = ""
    sku: str = ""
    preco_custo: str = ""
    preco_venda: str = ""
    estoque_minimo: str = ""
    estoque_inicial: str = "0"
    estoque_atual: int = 0
    ativo: bool = True
    imagem: str = ""
    erro_form: str = ""
    erro_imagem: str = ""

    # ajuste de estoque
    dialogo_ajuste: bool = False
    ajuste_id: int = 0
    ajuste_nome: str = ""
    ajuste_saldo: int = 0
    ajuste_tipo: str = TIPOS_AJUSTE[0]
    ajuste_qtd: str = ""
    erro_ajuste: str = ""

    _linhas: list[dict] = []

    @rx.var
    def total_paginas(self) -> int:
        return max(1, math.ceil(self.total / POR_PAGINA))

    @rx.var
    def situacoes(self) -> list[str]:
        return SITUACOES

    @rx.var
    def tipos_ajuste(self) -> list[str]:
        return TIPOS_AJUSTE

    @rx.var
    def imagem_url(self) -> str:
        return imagens.separar(self.imagem)[0]

    @rx.var
    def imagem_local(self) -> str:
        return imagens.separar(self.imagem)[1]

    # ------------------------------------------------------------ listagem

    async def _carregar_base(self):
        registros, categorias, disponiveis = await asyncio.gather(
            xano.listar(servico.TABELA), xano.listar_se_existir(servico.TABELA_CATEGORIAS),
            recursos.campos_disponiveis("produtos"),
        )
        self.tem_extras = {"sku", "preco_custo", "estoque_minimo", "ativo"} <= disponiveis
        self.usa_tabela_categorias = bool(categorias)
        categorias_por_id = {c["id"]: c for c in (categorias or [])}
        self._linhas = [servico.linha_produto(r, categorias_por_id) for r in registros]
        if categorias:
            ativas = sorted((c for c in categorias if servico.ativo(c)), key=lambda c: servico.chave_nome(c["nome"]))
            self.categorias_opcoes = [f"{c['id']} - {c['nome']}" for c in ativas]
        else:
            self.categorias_opcoes = sorted({l["categoria"] for l in self._linhas if l["categoria"] != "Sem categoria"},
                                            key=servico.chave_nome)
        self.categorias_filtro = ["Todas", *sorted({l["categoria"] for l in self._linhas}, key=servico.chave_nome)]
        self.qtd_estoque_baixo = sum(1 for l in self._linhas if l["estoque_baixo"] and l["ativo"])

    @rx.event
    async def carregar(self):
        await self._carregar_base()
        self._aplicar()

    def _aplicar(self):
        filtradas = servico.filtrar(self._linhas, self.busca, self.filtro_categoria,
                                    self.filtro_situacao, self.somente_estoque_baixo)
        self.total = len(filtradas)
        self.pagina = min(max(1, self.pagina), max(1, math.ceil(self.total / POR_PAGINA)))
        inicio = (self.pagina - 1) * POR_PAGINA
        self.produtos = filtradas[inicio:inicio + POR_PAGINA]

    @rx.event
    def definir_busca(self, valor: str):
        self.busca, self.pagina = valor, 1
        self._aplicar()

    @rx.event
    def definir_filtro_categoria(self, valor: str):
        self.filtro_categoria, self.pagina = valor, 1
        self._aplicar()

    @rx.event
    def definir_filtro_situacao(self, valor: str):
        self.filtro_situacao, self.pagina = valor, 1
        self._aplicar()

    @rx.event
    def alternar_filtro_estoque_baixo(self, valor: bool):
        self.somente_estoque_baixo, self.pagina = valor, 1
        self._aplicar()

    @rx.event
    def ver_estoque_baixo(self):
        self.busca, self.filtro_categoria, self.filtro_situacao = "", "Todas", "Ativos"
        self.somente_estoque_baixo, self.pagina = True, 1
        self._aplicar()

    @rx.event
    def pagina_anterior(self):
        self.pagina -= 1
        self._aplicar()

    @rx.event
    def proxima_pagina(self):
        self.pagina += 1
        self._aplicar()

    # ---------------------------------------------------------- formulário

    def _preencher(self, linha: dict | None):
        linha = linha or {}
        self.form_id = int(linha["id"]) if linha.get("id") else None
        self.nome_produto = linha.get("nome_produto", "")
        self.descricao = linha.get("descricao", "")
        if self.usa_tabela_categorias:
            cid = linha.get("categoria_id", "0")
            self.categoria = next((o for o in self.categorias_opcoes if o.startswith(f"{cid} - ")),
                                  next((o for o in self.categorias_opcoes
                                        if o.split(" - ", 1)[1] == linha.get("categoria")), ""))
        else:
            self.categoria = linha.get("categoria", "") if linha.get("categoria") != "Sem categoria" else ""
        self.sku = linha.get("sku", "")
        self.preco_custo = linha.get("preco_custo", "")
        self.preco_venda = linha.get("preco_venda", "")
        self.estoque_minimo = str(linha.get("estoque_minimo", "")) if linha.get("tem_minimo") else ""
        self.estoque_inicial = "0"
        self.estoque_atual = int(linha.get("estoque_qtd", 0))
        self.ativo = bool(linha.get("ativo", True))
        self.imagem = linha.get("imagem", "")
        self.erro_form = ""
        self.erro_imagem = ""

    @rx.event
    async def novo(self):
        await self._carregar_base()
        self._preencher(None)
        self.dialogo_aberto = True

    @rx.event
    async def editar(self, produto_id: str):
        await self._carregar_base()
        linha = next((l for l in self._linhas if l["id"] == str(produto_id)), None)
        if linha is None:
            return rx.toast.error("Esse produto não existe mais.")
        self._preencher(linha)
        self.dialogo_aberto = True

    @rx.event
    def fechar_dialogo(self):
        self.dialogo_aberto = False

    @rx.event
    async def handle_upload_imagem(self, files: list[rx.UploadFile]):
        if not await sessao_ok(self):
            return
        self.erro_imagem = ""
        if not files:
            return
        arquivo = files[0]
        try:
            self.imagem = await imagens.guardar("produto", arquivo.name or "", await arquivo.read())
        except imagens.ImagemInvalida as erro:
            self.erro_imagem = str(erro)

    @rx.event
    def remover_imagem(self):
        self.imagem = ""
        self.erro_imagem = ""

    @rx.event
    async def salvar(self):
        produtos, categorias = await asyncio.gather(
            xano.listar(servico.TABELA), xano.listar_se_existir(servico.TABELA_CATEGORIAS))
        form = {
            "nome_produto": self.nome_produto, "descricao": self.descricao, "categoria": self.categoria,
            "sku": self.sku, "preco_custo": self.preco_custo, "preco_venda": self.preco_venda,
            "estoque_minimo": self.estoque_minimo, "estoque_inicial": self.estoque_inicial,
            "ativo": self.ativo, "imagem": self.imagem,
        }
        try:
            dados = servico.validar_produto(form, produtos, self.form_id, categorias)
        except servico.ErroValidacao as erro:
            self.erro_form = str(erro)
            return
        novos = await recursos.campos_disponiveis("produtos")
        enviar = {k: v for k, v in dados.items() if k in servico.CAMPOS_BASE or k in novos}
        try:
            if self.form_id is None:
                registro = await xano.criar(servico.TABELA, enviar)
            else:
                registro = await estoque.editar_produto(self.form_id, enviar)
        except Exception:
            self.erro_form = "Não foi possível salvar (falha de conexão com o Xano). Tente de novo."
            return
        nao_gravados = xano.campos_nao_gravados(enviar, registro, novos)
        novo = self.form_id is None
        self.dialogo_aberto = False
        await self.carregar()
        eventos = [rx.toast.success(f"Produto {'cadastrado' if novo else 'atualizado'}.")]
        if nao_gravados:
            eventos.append(rx.toast.warning("O Xano não gravou: " + ", ".join(nao_gravados)
                                            + ". Inclua esses campos nos inputs dos endpoints POST/PATCH de produtos."))
        return eventos

    @rx.event
    async def excluir(self, produto_id: str):
        encontrados = await integridade.dependentes(servico.TABELA, int(produto_id))
        if encontrados:
            return rx.toast.error(integridade.mensagem_bloqueio("este produto", encontrados)
                                  + " Para tirá-lo das vendas, marque-o como inativo.")
        await xano.excluir(servico.TABELA, int(produto_id))
        await self.carregar()
        return rx.toast.success("Produto excluído.")

    # ------------------------------------------------------ ajuste de estoque

    @rx.event
    async def abrir_ajuste(self, produto_id: str):
        produto = await estoque._ler_produto(int(produto_id))
        if produto is None:
            return rx.toast.error("Esse produto não existe mais.")
        self.ajuste_id = int(produto_id)
        self.ajuste_nome = produto.get("nome_produto") or ""
        self.ajuste_saldo = int(produto.get("estoque_qtd") or 0)
        self.ajuste_tipo = TIPOS_AJUSTE[0]
        self.ajuste_qtd = ""
        self.erro_ajuste = ""
        self.dialogo_ajuste = True

    @rx.event
    def fechar_ajuste(self):
        self.dialogo_ajuste = False

    @rx.event
    async def salvar_ajuste(self):
        try:
            qtd = fmt.inteiro(self.ajuste_qtd)
        except ValueError:
            self.erro_ajuste = "Informe um número inteiro."
            return
        if qtd < 0 or (qtd == 0 and self.ajuste_tipo != TIPOS_AJUSTE[2]):
            self.erro_ajuste = "Informe uma quantidade maior que zero."
            return
        try:
            if self.ajuste_tipo == TIPOS_AJUSTE[2]:
                await estoque.definir_saldo(self.ajuste_id, qtd)
            else:
                await estoque.movimentar({self.ajuste_id: qtd if self.ajuste_tipo == TIPOS_AJUSTE[0] else -qtd})
        except estoque.EstoqueInsuficiente as erro:
            self.erro_ajuste = "Saída maior que o saldo: " + ", ".join(erro.produtos) + "."
            return
        except Exception:
            self.erro_ajuste = "Não foi possível ajustar (falha de conexão). Nada foi alterado."
            return
        self.dialogo_ajuste = False
        await self.carregar()
        return rx.toast.success(f"Estoque de {self.ajuste_nome} ajustado.")

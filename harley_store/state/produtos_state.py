"""State de Produtos (catálogo + estoque). Dados vêm do backend Xano."""

from pathlib import Path
from typing import Optional
from uuid import uuid4

import reflex as rx

from .. import xano_client as xano

TABELA = "produtos"

LIMITE_ESTOQUE_BAIXO = 5

EXTENSOES_IMAGEM_PERMITIDAS = {".png", ".jpg", ".jpeg", ".webp", ".gif"}
TAMANHO_MAXIMO_IMAGEM = 5 * 1024 * 1024  # 5 MB


class ProdutosState(rx.State):
    produtos: list[dict] = []
    busca: str = ""
    somente_estoque_baixo: bool = False

    form_id: Optional[int] = None
    nome_produto: str = ""
    descricao: str = ""
    categoria: str = ""
    estoque_qtd: str = "0"
    preco_venda: str = "0"
    imagem: str = ""
    erro_imagem: str = ""

    @rx.event
    async def carregar(self):
        registros = await xano.listar(TABELA)
        if self.busca.strip():
            termo = self.busca.strip().lower()
            registros = [r for r in registros if termo in r["nome_produto"].lower()]

        if self.somente_estoque_baixo:
            registros = [r for r in registros if r["estoque_qtd"] <= LIMITE_ESTOQUE_BAIXO]

        registros = sorted(registros, key=lambda r: r["nome_produto"])

        self.produtos = [
            {
                "id": str(r["id"]),
                "nome_produto": r["nome_produto"],
                "descricao": r.get("descricao") or "—",
                "categoria": r["categoria"],
                "estoque_qtd": str(r["estoque_qtd"]),
                "preco_venda": f"{r['preco_venda']:.2f}",
                "estoque_baixo": r["estoque_qtd"] <= LIMITE_ESTOQUE_BAIXO,
                "imagem": r.get("imagem") or "",
            }
            for r in registros
        ]

    @rx.event
    async def definir_busca(self, valor: str):
        self.busca = valor
        await self.carregar()

    @rx.event
    async def alternar_filtro_estoque_baixo(self, valor: bool):
        self.somente_estoque_baixo = valor
        await self.carregar()

    @rx.event
    def novo(self):
        self.form_id = None
        self.nome_produto = ""
        self.descricao = ""
        self.categoria = ""
        self.estoque_qtd = "0"
        self.preco_venda = "0"
        self.imagem = ""
        self.erro_imagem = ""

    @rx.event
    def editar(self, row: dict):
        self.form_id = int(row["id"])
        self.nome_produto = row["nome_produto"]
        self.descricao = "" if row["descricao"] == "—" else row["descricao"]
        self.categoria = row["categoria"]
        self.estoque_qtd = row["estoque_qtd"]
        self.preco_venda = row["preco_venda"]
        self.imagem = row.get("imagem") or ""
        self.erro_imagem = ""

    @rx.event
    async def handle_upload_imagem(self, files: list[rx.UploadFile]):
        """Salva a foto do produto localmente (pasta uploaded_files/) e
        guarda só o nome do arquivo gerado — esse nome é o que vai pro
        Xano no campo `imagem` quando o formulário for salvo."""
        self.erro_imagem = ""
        if not files:
            return
        arquivo = files[0]
        extensao = Path(arquivo.name or "").suffix.lower()
        if extensao not in EXTENSOES_IMAGEM_PERMITIDAS:
            self.erro_imagem = "Formato inválido. Use PNG, JPG, WEBP ou GIF."
            return
        conteudo = await arquivo.read()
        if len(conteudo) > TAMANHO_MAXIMO_IMAGEM:
            self.erro_imagem = "Imagem muito grande (máximo 5 MB)."
            return
        nome_arquivo = f"produto_{uuid4().hex}{extensao}"
        (rx.get_upload_dir() / nome_arquivo).write_bytes(conteudo)
        self.imagem = nome_arquivo

    @rx.event
    def remover_imagem(self):
        self.imagem = ""
        self.erro_imagem = ""

    @rx.event
    async def salvar(self):
        nome = self.nome_produto.strip()
        categoria = self.categoria.strip()
        if not nome or not categoria:
            return rx.window_alert("Preencha nome e categoria do produto.")
        try:
            estoque = int(self.estoque_qtd or 0)
            preco = float(str(self.preco_venda).replace(",", ".") or 0)
        except ValueError:
            return rx.window_alert("Estoque precisa ser um número inteiro e preço um número válido.")
        if estoque < 0 or preco < 0:
            return rx.window_alert("Estoque e preço não podem ser negativos.")

        dados = {
            "nome_produto": nome,
            "descricao": self.descricao.strip() or None,
            "categoria": categoria,
            "estoque_qtd": estoque,
            "preco_venda": preco,
            "imagem": self.imagem or None,
        }
        if self.form_id is None:
            await xano.criar(TABELA, dados)
        else:
            await xano.atualizar(TABELA, self.form_id, dados)

        self.novo()
        await self.carregar()

    @rx.event
    async def excluir(self, produto_id: str):
        await xano.excluir(TABELA, int(produto_id))
        await self.carregar()

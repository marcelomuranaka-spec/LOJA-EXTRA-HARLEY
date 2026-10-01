"""
State de Categorias de produtos (tabela `categorias` do Xano).

Enquanto a tabela não existe no Xano, a tela mostra as categorias que já
estão escritas nos produtos (texto livre) e o passo a passo para ativar.
Com a tabela criada, o botão "Importar categorias dos produtos" cria uma
categoria para cada texto já usado (mais as sugeridas) e liga os produtos.

Excluir: só quando nenhum produto usa a categoria; senão, desative.
"""

import asyncio
from typing import Optional

import reflex as rx

from .. import produtos_servico as servico
from .. import recursos
from .. import xano_client as xano

TABELA = servico.TABELA_CATEGORIAS


class CategoriasState(rx.State):
    tabela_existe: bool = False
    pode_ligar: bool = False           # produtos.categoria_id existe
    categorias: list[dict] = []
    categorias_texto: list[dict] = []  # sem a tabela: [{nome, qtd}]
    pendentes_importacao: int = 0      # produtos ainda sem categoria_id ou categorias a criar

    dialogo_aberto: bool = False
    form_id: Optional[int] = None
    nome: str = ""
    erro_form: str = ""

    @rx.event
    async def carregar(self):
        produtos, categorias, disponiveis = await asyncio.gather(
            xano.listar(servico.TABELA), xano.listar_se_existir(TABELA),
            recursos.campos_disponiveis("produtos"),
        )
        self.tabela_existe = categorias is not None
        self.pode_ligar = "categoria_id" in disponiveis
        if categorias is None:
            contagem: dict[str, int] = {}
            for p in produtos:
                nome = (p.get("categoria") or "").strip() or "Sem categoria"
                contagem[nome] = contagem.get(nome, 0) + 1
            self.categorias_texto = [{"nome": n, "qtd": q} for n, q in sorted(contagem.items(),
                                                                              key=lambda i: servico.chave_nome(i[0]))]
            self.categorias = []
            return
        self.categorias = [
            {
                "id": str(c["id"]),
                "nome": c.get("nome") or "",
                "ativo": servico.ativo(c),
                "qtd": len(servico.produtos_da_categoria(c, produtos)),
            }
            for c in sorted(categorias, key=lambda c: servico.chave_nome(c.get("nome")))
        ]
        a_criar, a_ligar = servico.plano_importacao(produtos, categorias)
        self.pendentes_importacao = len(a_criar) + (len(a_ligar) if self.pode_ligar else 0)

    @rx.event
    def abrir_novo(self):
        self.form_id, self.nome, self.erro_form = None, "", ""
        self.dialogo_aberto = True

    @rx.event
    def abrir_editar(self, categoria_id: str):
        categoria = next((c for c in self.categorias if c["id"] == categoria_id), None)
        if categoria is None:
            return
        self.form_id, self.nome, self.erro_form = int(categoria_id), categoria["nome"], ""
        self.dialogo_aberto = True

    @rx.event
    def fechar_dialogo(self):
        self.dialogo_aberto = False

    @rx.event
    async def salvar(self):
        categorias = await xano.listar(TABELA)
        try:
            nome = servico.validar_categoria(self.nome, categorias, self.form_id)
        except servico.ErroValidacao as erro:
            self.erro_form = str(erro)
            return
        try:
            if self.form_id is None:
                await xano.criar(TABELA, {"nome": nome, "ativo": True})
                renomeados = 0
            else:
                antiga = next((c for c in categorias if c["id"] == self.form_id), None)
                await xano.atualizar_mesclando(TABELA, self.form_id, {"nome": nome})
                renomeados = await self._renomear_nos_produtos(antiga, nome) if antiga else 0
        except Exception:
            self.erro_form = "Não foi possível salvar (falha de conexão com o Xano). Tente de novo."
            return
        self.dialogo_aberto = False
        await self.carregar()
        extra = f" {renomeados} produto(s) atualizados." if renomeados else ""
        return rx.toast.success(f"Categoria {nome} salva.{extra}")

    async def _renomear_nos_produtos(self, antiga: dict, nome_novo: str) -> int:
        """O texto `produtos.categoria` acompanha o nome da categoria."""
        from .. import estoque
        if antiga.get("nome") == nome_novo:
            return 0
        total = 0
        for produto in servico.produtos_da_categoria(antiga, await xano.listar(servico.TABELA)):
            await estoque.editar_produto(produto["id"], {"categoria": nome_novo})
            total += 1
        return total

    @rx.event
    async def alternar_ativo(self, categoria_id: str):
        categoria = next((c for c in self.categorias if c["id"] == categoria_id), None)
        if categoria is None:
            return
        try:
            await xano.atualizar_mesclando(TABELA, int(categoria_id), {"ativo": not categoria["ativo"]})
        except Exception:
            return rx.toast.error("Não foi possível alterar (falha de conexão).")
        await self.carregar()
        return rx.toast.success(f"Categoria {categoria['nome']} {'desativada' if categoria['ativo'] else 'ativada'}.")

    @rx.event
    async def excluir(self, categoria_id: str):
        categorias = await xano.listar(TABELA)
        categoria = next((c for c in categorias if c["id"] == int(categoria_id)), None)
        if categoria is None:
            return
        em_uso = servico.produtos_da_categoria(categoria, await xano.listar(servico.TABELA))
        if em_uso:
            return rx.toast.error(f"Não é possível excluir: {len(em_uso)} produto(s) usam esta categoria. "
                                  "Troque a categoria deles ou desative a categoria.")
        await xano.excluir(TABELA, int(categoria_id))
        await self.carregar()
        return rx.toast.success("Categoria excluída.")

    @rx.event
    async def importar(self):
        try:
            criadas, ligados = await servico.importar_categorias(self.pode_ligar)
        except Exception:
            await self.carregar()
            return rx.toast.error("A importação parou por falha de conexão. Rode de novo: o que já foi feito não se repete.")
        await self.carregar()
        return rx.toast.success(f"{criadas} categoria(s) criada(s) e {ligados} produto(s) ligado(s).")

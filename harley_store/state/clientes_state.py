"""
State da lista de Clientes (/clientes): pesquisa, filtros, ordenação,
paginação e o formulário (janela) de novo/editar cliente. A ficha completa
do cliente fica em `cliente_detalhe_state.py` (/clientes/<id>).

Regras de validação e gravação: `clientes_servico.py`. Dados vêm do Xano.
"""

import asyncio
import math
from typing import Optional

import reflex as rx

from .. import clientes_servico as servico
from .. import integridade, recursos
from .. import xano_client as xano
from .cliente_detalhe_state import ClienteDetalheState

POR_PAGINA = 15
ORDENS = ["Nome (A–Z)", "Nome (Z–A)", "Mais recentes", "Mais antigos", "Mais compras"]


class ClientesState(rx.State):
    clientes: list[dict] = []          # página atual
    total: int = 0
    pagina: int = 1
    busca: str = ""
    filtro_status: str = "Todos"
    filtro_cidade: str = "Todas"
    ordem: str = ORDENS[0]
    cidades: list[str] = ["Todas"]

    # campos novos já criados no Xano (ver recursos.py)
    tem_telegram: bool = False
    tem_cidade: bool = False
    tem_status: bool = False
    tem_observacoes: bool = False
    tem_data: bool = False

    # formulário
    dialogo_aberto: bool = False
    form_id: Optional[int] = None
    nome_cliente: str = ""
    cpf_cnpj: str = ""
    telefone: str = ""
    telegram: str = ""
    email: str = ""
    endereco: str = ""
    cidade: str = ""
    status: str = servico.STATUS_PADRAO
    observacoes: str = ""
    erro_form: str = ""

    _linhas: list[dict] = []
    _cpf_original: str = ""

    @rx.var
    def total_paginas(self) -> int:
        return max(1, math.ceil(self.total / POR_PAGINA))

    @rx.var
    def opcoes_status(self) -> list[str]:
        return servico.STATUS_CLIENTE

    @rx.var
    def filtros_status(self) -> list[str]:
        return ["Todos", *servico.STATUS_CLIENTE]

    @rx.var
    def ordens(self) -> list[str]:
        return ORDENS

    @rx.var
    def campos_extras_pendentes(self) -> bool:
        return not (self.tem_telegram and self.tem_cidade and self.tem_status
                    and self.tem_observacoes and self.tem_data)

    # ---------------------------------------------------------- listagem

    @rx.event
    async def carregar(self):
        registros, motos, vendas, disponiveis = await asyncio.gather(
            xano.listar(servico.TABELA), xano.listar(servico.TABELA_MOTOS),
            xano.listar("transacoes"), recursos.campos_disponiveis("clientes"),
        )
        self.tem_telegram = "telegram" in disponiveis
        self.tem_cidade = "cidade" in disponiveis
        self.tem_status = "status" in disponiveis
        self.tem_observacoes = "observacoes" in disponiveis
        self.tem_data = "created_at" in disponiveis
        motos_por_cliente: dict[int, int] = {}
        for m in motos:
            motos_por_cliente[int(m.get("id_cliente") or 0)] = motos_por_cliente.get(int(m.get("id_cliente") or 0), 0) + 1
        compras_por_cliente: dict[int, int] = {}
        for t in vendas:
            if not servico.esta_cancelada(t):
                cid = int(t.get("id_cliente") or 0)
                compras_por_cliente[cid] = compras_por_cliente.get(cid, 0) + 1
        self._linhas = [
            servico.linha_cliente(r, motos_por_cliente.get(r["id"], 0), compras_por_cliente.get(r["id"], 0))
            for r in registros
        ]
        self.cidades = ["Todas", *sorted({l["cidade"] for l in self._linhas if l["cidade"]})]
        self._aplicar()

    def _aplicar(self):
        filtradas = servico.filtrar_clientes(self._linhas, self.busca, self.filtro_status,
                                             self.filtro_cidade, self.ordem)
        self.total = len(filtradas)
        self.pagina = min(max(1, self.pagina), max(1, math.ceil(self.total / POR_PAGINA)))
        inicio = (self.pagina - 1) * POR_PAGINA
        self.clientes = filtradas[inicio:inicio + POR_PAGINA]

    @rx.event
    def definir_busca(self, valor: str):
        self.busca = valor
        self.pagina = 1
        self._aplicar()

    @rx.event
    def definir_filtro_status(self, valor: str):
        self.filtro_status = valor
        self.pagina = 1
        self._aplicar()

    @rx.event
    def definir_filtro_cidade(self, valor: str):
        self.filtro_cidade = valor
        self.pagina = 1
        self._aplicar()

    @rx.event
    def definir_ordem(self, valor: str):
        self.ordem = valor
        self._aplicar()

    @rx.event
    def limpar_filtros(self):
        self.busca, self.filtro_status, self.filtro_cidade, self.ordem = "", "Todos", "Todas", ORDENS[0]
        self.pagina = 1
        self._aplicar()

    @rx.event
    def pagina_anterior(self):
        self.pagina -= 1
        self._aplicar()

    @rx.event
    def proxima_pagina(self):
        self.pagina += 1
        self._aplicar()

    # ------------------------------------------------------- formulário

    def _preencher(self, linha: dict | None):
        linha = linha or {}
        self.form_id = int(linha["id"]) if linha.get("id") else None
        self.nome_cliente = linha.get("nome_cliente", "")
        self.cpf_cnpj = linha.get("cpf_cnpj", "")
        self.telefone = linha.get("telefone", "")
        self.telegram = linha.get("telegram", "")
        self.email = linha.get("email", "")
        self.endereco = linha.get("endereco", "")
        self.cidade = linha.get("cidade", "")
        self.status = linha.get("status", servico.STATUS_PADRAO)
        self.observacoes = linha.get("observacoes", "")
        self._cpf_original = linha.get("cpf_cnpj", "")
        self.erro_form = ""

    @rx.event
    def abrir_novo(self):
        self._preencher(None)
        self.dialogo_aberto = True

    @rx.event
    async def abrir_editar(self, cliente_id: str):
        registro = await xano.buscar(servico.TABELA, int(cliente_id))
        if registro is None:
            return rx.toast.error("Esse cliente não existe mais.")
        self._preencher(servico.linha_cliente(registro))
        self.dialogo_aberto = True

    @rx.event
    def fechar_dialogo(self):
        self.dialogo_aberto = False

    @rx.event
    async def salvar(self):
        form = {
            "nome_cliente": self.nome_cliente, "cpf_cnpj": self.cpf_cnpj, "telefone": self.telefone,
            "telegram": self.telegram, "email": self.email, "endereco": self.endereco,
            "cidade": self.cidade, "status": self.status, "observacoes": self.observacoes,
        }
        try:
            dados = servico.validar_cliente(form, await xano.listar(servico.TABELA), self.form_id,
                                            self._cpf_original)
        except servico.ErroValidacao as erro:
            self.erro_form = str(erro)
            return
        novos = await recursos.campos_disponiveis("clientes")
        try:
            registro, nao_gravados = await servico.gravar(servico.TABELA, self.form_id, dados,
                                                          servico.CAMPOS_BASE_CLIENTE, novos)
        except Exception:
            self.erro_form = "Não foi possível salvar (falha de conexão com o Xano). Tente de novo."
            return
        novo = self.form_id is None
        self.dialogo_aberto = False
        await self.carregar()
        eventos = [rx.toast.success(f"Cliente {registro.get('nome_cliente', '')} {'cadastrado' if novo else 'atualizado'}.")]
        if nao_gravados:
            eventos.append(rx.toast.warning(
                "O Xano não gravou: " + ", ".join(nao_gravados)
                + ". Inclua esses campos nos inputs dos endpoints POST/PATCH de clientes (ver Configuração)."
            ))
        if novo:
            eventos.append(rx.redirect(f"/clientes/{registro['id']}"))
        elif self.router.page.path.startswith("/clientes/"):
            eventos.append(ClienteDetalheState.carregar)
        return eventos

    @rx.event
    async def excluir(self, cliente_id: str):
        encontrados = await integridade.dependentes(servico.TABELA, int(cliente_id))
        if encontrados:
            return rx.toast.error(integridade.mensagem_bloqueio("este cliente", encontrados)
                                  + " Se ele não compra mais, mude o status para Inativo.")
        await xano.excluir(servico.TABELA, int(cliente_id))
        await self.carregar()
        return rx.toast.success("Cliente excluído.")

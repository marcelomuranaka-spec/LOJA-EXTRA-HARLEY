"""
State de Motos dos Clientes (tabela `motos_clientes`).

Usado em dois lugares, com o mesmo formulário (janela):
- a página /motos, com todas as motos de todos os clientes;
- a ficha do cliente (/clientes/<id>), onde o cliente já vem escolhido e não
  pode ser trocado (`_cliente_fixo`). Depois de salvar, a ficha é recarregada.

A moto SEMPRE pertence a um cliente escolhido de propósito (antes, sem
escolha, o app gravava no primeiro cliente da lista). Regras de validação:
`clientes_servico.validar_moto`. Fotos: `imagens.py`.
"""

import asyncio
from typing import Optional

import reflex as rx

from .. import clientes_servico as servico
from .. import imagens, integridade, recursos
from .. import xano_client as xano
from ..seguranca import sessao_ok
from .cliente_detalhe_state import ClienteDetalheState


class MotosState(rx.State):
    motos: list[dict] = []
    busca: str = ""
    clientes_opcoes: list[str] = []  # ex.: ["3 - João Pereira", ...]

    # campos novos já criados no Xano
    tem_extras: bool = False
    extras_disponiveis: list[str] = []

    # formulário
    dialogo_aberto: bool = False
    form_id: Optional[int] = None
    cliente_selecionado: str = ""
    cliente_travado: bool = False
    marca: str = ""
    modelo: str = ""
    ano: str = ""
    cor: str = ""
    placa: str = ""
    chassi: str = ""
    quilometragem: str = ""
    observacoes: str = ""
    imagem: str = ""
    erro_form: str = ""
    erro_imagem: str = ""

    # visualizar
    dialogo_ver: bool = False
    moto_vista: dict = servico.MOTO_VAZIA

    _registros: list[dict] = []

    @rx.var
    def imagem_url(self) -> str:
        return imagens.separar(self.imagem)[0]

    @rx.var
    def imagem_local(self) -> str:
        return imagens.separar(self.imagem)[1]

    async def _carregar_base(self):
        clientes, registros, disponiveis = await asyncio.gather(
            xano.listar(servico.TABELA), xano.listar(servico.TABELA_MOTOS),
            recursos.campos_disponiveis("motos_clientes"),
        )
        clientes.sort(key=lambda c: c["nome_cliente"].lower())
        self.clientes_opcoes = [f"{c['id']} - {c['nome_cliente']}" for c in clientes]
        self.extras_disponiveis = sorted(disponiveis)
        self.tem_extras = {"marca", "ano", "cor", "quilometragem", "observacoes"} <= disponiveis
        nomes = {c["id"]: c["nome_cliente"] for c in clientes}
        self._registros = [servico.linha_moto(r, nomes.get(r.get("id_cliente"), "")) for r in registros]

    @rx.event
    async def carregar(self):
        await self._carregar_base()
        self._aplicar()

    def _aplicar(self):
        termo = self.busca.strip().lower()
        linhas = [
            l for l in self._registros
            if not termo or termo in " ".join((l["titulo"], l["placa"], l["chassi"], l["cliente_nome"])).lower()
        ]
        self.motos = sorted(linhas, key=lambda l: (l["cliente_nome"].lower(), l["titulo"].lower()))

    @rx.event
    def definir_busca(self, valor: str):
        self.busca = valor
        self._aplicar()

    # ---------------------------------------------------------- formulário

    def _preencher(self, linha: dict | None, cliente_id: int = 0):
        linha = linha or {}
        self.form_id = int(linha["id"]) if linha.get("id") else None
        cid = int(linha.get("id_cliente") or cliente_id or 0)
        self.cliente_selecionado = next((o for o in self.clientes_opcoes if o.startswith(f"{cid} - ")), "")
        self.marca = linha.get("marca", "")
        self.modelo = linha.get("modelo", "")
        self.ano = linha.get("ano", "")
        self.cor = linha.get("cor", "")
        self.placa = linha.get("placa", "")
        self.chassi = linha.get("chassi", "")
        self.quilometragem = linha.get("quilometragem", "")
        self.observacoes = linha.get("observacoes", "")
        self.imagem = linha.get("imagem", "")
        self.erro_form = ""
        self.erro_imagem = ""

    @rx.event
    async def abrir_novo(self):
        await self._carregar_base()
        self.cliente_travado = False
        self._preencher(None)
        self.dialogo_aberto = True

    @rx.event
    async def abrir_novo_para_cliente(self, cliente_id: int):
        await self._carregar_base()
        self.cliente_travado = True
        self._preencher(None, int(cliente_id))
        self.dialogo_aberto = True

    @rx.event
    async def abrir_editar(self, moto_id: str, travar_cliente: bool = False):
        await self._carregar_base()
        linha = next((l for l in self._registros if l["id"] == str(moto_id)), None)
        if linha is None:
            return rx.toast.error("Essa moto não existe mais.")
        self.cliente_travado = bool(travar_cliente)
        self._preencher(linha)
        self.dialogo_aberto = True

    @rx.event
    def fechar_dialogo(self):
        self.dialogo_aberto = False

    @rx.event
    async def visualizar(self, moto_id: str):
        if not self._registros:
            await self._carregar_base()
        linha = next((l for l in self._registros if l["id"] == str(moto_id)), None)
        if linha is None:
            return rx.toast.error("Essa moto não existe mais.")
        self.moto_vista = linha
        self.dialogo_ver = True

    @rx.event
    def fechar_ver(self):
        self.dialogo_ver = False

    @rx.event
    async def handle_upload_imagem(self, files: list[rx.UploadFile]):
        """Valida e guarda a foto (Xano, ou pasta local enquanto o endpoint de
        upload não existir). Só o endereço/nome vai para o campo `imagem`."""
        if not await sessao_ok(self):
            return
        self.erro_imagem = ""
        if not files:
            return
        arquivo = files[0]
        try:
            self.imagem = await imagens.guardar("moto", arquivo.name or "", await arquivo.read())
        except imagens.ImagemInvalida as erro:
            self.erro_imagem = str(erro)

    def _na_ficha_do_cliente(self) -> bool:
        return self.router.page.path.startswith("/clientes/")

    @rx.event
    def remover_imagem(self):
        self.imagem = ""
        self.erro_imagem = ""

    @rx.event
    async def salvar(self):
        form = {
            "id_cliente": self.cliente_selecionado.split(" - ")[0] if self.cliente_selecionado else "",
            "marca": self.marca, "modelo": self.modelo, "ano": self.ano, "cor": self.cor,
            "placa": self.placa, "chassi": self.chassi, "quilometragem": self.quilometragem,
            "observacoes": self.observacoes, "imagem": self.imagem,
        }
        clientes, motos = await asyncio.gather(xano.listar(servico.TABELA), xano.listar(servico.TABELA_MOTOS))
        try:
            dados = servico.validar_moto(form, motos, self.form_id, {c["id"] for c in clientes})
        except servico.ErroValidacao as erro:
            self.erro_form = str(erro)
            return
        novos = await recursos.campos_disponiveis("motos_clientes")
        try:
            _, nao_gravados = await servico.gravar(servico.TABELA_MOTOS, self.form_id, dados,
                                                   servico.CAMPOS_BASE_MOTO, novos)
        except Exception:
            self.erro_form = "Não foi possível salvar (falha de conexão com o Xano). Tente de novo."
            return
        novo = self.form_id is None
        self.dialogo_aberto = False
        await self.carregar()
        eventos = [rx.toast.success("Moto cadastrada." if novo else "Moto atualizada.")]
        if self._na_ficha_do_cliente():
            eventos.append(ClienteDetalheState.carregar)
        if nao_gravados:
            eventos.append(rx.toast.warning(
                "O Xano não gravou: " + ", ".join(nao_gravados)
                + ". Inclua esses campos nos inputs dos endpoints POST/PATCH de motos_clientes."
            ))
        return eventos

    @rx.event
    async def excluir(self, moto_id: str):
        encontrados = await integridade.dependentes(servico.TABELA_MOTOS, int(moto_id))
        if encontrados:
            return rx.toast.error(integridade.mensagem_bloqueio("esta moto", encontrados))
        await xano.excluir(servico.TABELA_MOTOS, int(moto_id))
        await self.carregar()
        eventos = [rx.toast.success("Moto excluída.")]
        if self._na_ficha_do_cliente():
            eventos.append(ClienteDetalheState.carregar)
        return eventos

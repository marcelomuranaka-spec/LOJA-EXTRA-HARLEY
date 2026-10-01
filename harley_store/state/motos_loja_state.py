"""
State de Motos da Loja (estoque de motos à venda) — tabela `motos` do Xano.

Não confundir com `motos_state.py` (motos dos CLIENTES, que passam pela
oficina). Aqui ficam as motos que a loja compra e revende.

Cuidados específicos desta tabela no Xano:

- O PATCH gerado pelo Xano SUBSTITUI o registro inteiro: campo que não for
  enviado volta zerado/vazio. Por isso a edição usa
  `xano.atualizar_mesclando`, que relê a moto e só troca os campos do
  formulário — campos que a tela não mostra (renavam, cilindrada,
  localização, fotos adicionais) são preservados.
- `foto` é um campo de imagem do Xano (objeto com path/url), não um nome de
  arquivo local. Foto nova passa por `imagens.enviar_ao_xano`, que precisa do
  endpoint `upload/image` (ver README e Configuração do sistema).
- Datas (`data_entrada`/`data_saida`) são epoch em ms; 0 = sem data.
- Situações e rótulos ("Disponível" = "Em estoque"): `motos_loja_servico.py`.
"""

import asyncio
import datetime
from typing import Optional

import reflex as rx

from .. import formatacao as fmt
from .. import imagens, integridade
from .. import motos_loja_servico as servico
from .. import xano_client as xano
from ..seguranca import sessao_ok

TABELA = servico.TABELA
SEM_CLIENTE = "— nenhum —"
ORDENS = ["Mais recentes", "Menor preço", "Maior preço", "Ano (mais novas)", "Marca e modelo"]


def _urls_fotos(valor) -> list[str]:
    """Campo `fotos` (fotos adicionais): lista de objetos de imagem do Xano
    (com `url`) ou de URLs em texto."""
    if not isinstance(valor, list):
        return []
    urls = []
    for item in valor:
        if isinstance(item, dict) and item.get("url"):
            urls.append(item["url"])
        elif isinstance(item, str) and item.startswith(("http://", "https://")):
            urls.append(item)
    return urls


class MotosLojaState(rx.State):
    motos: list[dict] = []
    busca: str = ""
    filtro_status: str = "Todas"
    filtro_marca: str = "Todas"
    ano_min: str = ""
    ano_max: str = ""
    preco_min: str = ""
    preco_max: str = ""
    ordem: str = ORDENS[0]
    marcas: list[str] = ["Todas"]
    resumo: dict = {"disponiveis": "0", "valor": "0,00", "vendidas": "0"}

    clientes_opcoes: list[str] = []

    # formulário
    dialogo_aberto: bool = False
    form_id: Optional[int] = None
    marca: str = "Harley-Davidson"
    modelo: str = ""
    ano: str = ""
    cor: str = ""
    placa: str = ""
    chassi: str = ""
    quilometragem: str = ""
    status: str = "Disponível"
    preco_compra: str = ""
    preco_venda: str = ""
    data_entrada: str = ""
    data_saida: str = ""
    observacoes: str = ""
    cliente_selecionado: str = SEM_CLIENTE
    erro_form: str = ""

    foto_url: str = ""
    erro_foto: str = ""
    enviando_foto: bool = False
    _foto: dict = {}

    # visualizar / fotos adicionais
    dialogo_ver: bool = False
    moto_vista: dict = {k: "" for k in ("id", "marca", "modelo", "ano", "cor", "placa", "chassi",
                                        "quilometragem", "status", "status_rotulo", "preco_venda",
                                        "data_entrada", "data_saida", "observacoes", "cliente_nome", "foto_url")}
    fotos_vista: list[str] = []
    erro_fotos: str = ""

    _linhas: list[dict] = []

    @rx.var
    def status_opcoes(self) -> list[str]:
        return [rotulo for _, rotulo in servico.SITUACOES]

    @rx.var
    def filtros_status(self) -> list[str]:
        return ["Todas", *[rotulo for _, rotulo in servico.SITUACOES]]

    @rx.var
    def ordens(self) -> list[str]:
        return ORDENS

    # ------------------------------------------------------------ listagem

    @rx.event
    async def carregar(self):
        clientes, registros = await asyncio.gather(xano.listar("clientes"), xano.listar(TABELA))
        clientes.sort(key=lambda c: c["nome_cliente"].lower())
        self.clientes_opcoes = [SEM_CLIENTE, *[f"{c['id']} - {c['nome_cliente']}" for c in clientes]]
        nomes_por_id = {c["id"]: c["nome_cliente"] for c in clientes}
        self._linhas = []
        for r in registros:
            situacao = servico.situacao(r)
            fotos = _urls_fotos(r.get("fotos"))
            self._linhas.append({
                "id": str(r["id"]),
                "marca": r.get("marca") or "",
                "modelo": r.get("modelo") or "",
                "ano": str(r.get("ano") or ""),
                "ano_num": int(r.get("ano") or 0),
                "cor": r.get("cor") or "",
                "placa": r.get("placa") or "",
                "chassi": r.get("chassi") or "",
                "quilometragem": fmt.moeda(r.get("quilometragem") or 0).split(",")[0],
                "status": situacao,
                "status_rotulo": servico.ROTULOS[situacao],
                "status_cor": servico.CORES[situacao],
                "preco_compra": fmt.moeda(r.get("preco_compra") or 0),
                "preco_venda": fmt.moeda(r.get("preco_venda") or 0),
                "preco_num": float(r.get("preco_venda") or 0),
                "data_entrada": fmt.data(r.get("data_entrada")),
                "entrada_num": fmt.epoch(r.get("data_entrada") or r.get("created_at")),
                "data_saida": fmt.data(r.get("data_saida")),
                "observacoes": r.get("observacoes") or "",
                "id_cliente": str(r.get("cliente_id") or 0),
                "cliente_nome": nomes_por_id.get(r.get("cliente_id"), ""),
                "foto_url": ((r.get("foto") or {}).get("url")) or "",
                "fotos": fotos,
                "qtd_fotos": len(fotos) + (1 if (r.get("foto") or {}).get("url") else 0),
            })
        self.marcas = ["Todas", *sorted({l["marca"] for l in self._linhas if l["marca"]})]
        disponiveis = [l for l in self._linhas if l["status"] in servico.VENDAVEIS]
        self.resumo = {
            "disponiveis": str(len(disponiveis)),
            "valor": fmt.moeda(sum(l["preco_num"] for l in disponiveis)),
            "vendidas": str(sum(1 for l in self._linhas if l["status"] == servico.VENDIDA)),
        }
        self._aplicar()

    def _aplicar(self):
        termo = self.busca.strip().lower()
        try:
            ano_min = fmt.inteiro(self.ano_min) if self.ano_min.strip() else 0
            ano_max = fmt.inteiro(self.ano_max) if self.ano_max.strip() else 0
            preco_min = fmt.numero(self.preco_min) if self.preco_min.strip() else 0
            preco_max = fmt.numero(self.preco_max) if self.preco_max.strip() else 0
        except ValueError:
            ano_min = ano_max = preco_min = preco_max = 0
        filtradas = [
            l for l in self._linhas
            if (not termo or termo in f"{l['marca']} {l['modelo']} {l['placa']} {l['chassi']} {l['cor']}".lower())
            and (self.filtro_status == "Todas" or l["status_rotulo"] == self.filtro_status)
            and (self.filtro_marca == "Todas" or l["marca"] == self.filtro_marca)
            and (not ano_min or l["ano_num"] >= ano_min)
            and (not ano_max or l["ano_num"] <= ano_max)
            and (not preco_min or l["preco_num"] >= preco_min)
            and (not preco_max or l["preco_num"] <= preco_max)
        ]
        chaves = {
            "Mais recentes": (lambda l: (l["entrada_num"], int(l["id"])), True),
            "Menor preço": (lambda l: l["preco_num"], False),
            "Maior preço": (lambda l: l["preco_num"], True),
            "Ano (mais novas)": (lambda l: l["ano_num"], True),
            "Marca e modelo": (lambda l: (l["marca"].lower(), l["modelo"].lower()), False),
        }
        chave, reverso = chaves.get(self.ordem, chaves[ORDENS[0]])
        self.motos = sorted(filtradas, key=chave, reverse=reverso)

    @rx.event
    def definir_busca(self, valor: str):
        self.busca = valor
        self._aplicar()

    @rx.event
    def definir_filtro_status(self, valor: str):
        self.filtro_status = valor
        self._aplicar()

    @rx.event
    def definir_filtro_marca(self, valor: str):
        self.filtro_marca = valor
        self._aplicar()

    @rx.event
    def definir_ordem(self, valor: str):
        self.ordem = valor
        self._aplicar()

    @rx.event
    def definir_ano_min(self, valor: str):
        self.ano_min = valor
        self._aplicar()

    @rx.event
    def definir_ano_max(self, valor: str):
        self.ano_max = valor
        self._aplicar()

    @rx.event
    def definir_preco_min(self, valor: str):
        self.preco_min = valor
        self._aplicar()

    @rx.event
    def definir_preco_max(self, valor: str):
        self.preco_max = valor
        self._aplicar()

    @rx.event
    def limpar_filtros(self):
        self.busca, self.filtro_status, self.filtro_marca = "", "Todas", "Todas"
        self.ano_min = self.ano_max = self.preco_min = self.preco_max = ""
        self.ordem = ORDENS[0]
        self._aplicar()

    # ---------------------------------------------------------- formulário

    @rx.event
    def novo(self):
        self.form_id = None
        self.marca = "Harley-Davidson"
        self.modelo = ""
        self.ano = ""
        self.cor = ""
        self.placa = ""
        self.chassi = ""
        self.quilometragem = ""
        self.status = "Disponível"
        self.preco_compra = ""
        self.preco_venda = ""
        self.data_entrada = datetime.date.today().strftime("%Y-%m-%d")
        self.data_saida = ""
        self.observacoes = ""
        self.cliente_selecionado = SEM_CLIENTE
        self.foto_url = ""
        self.erro_foto = ""
        self.erro_form = ""
        self._foto = {}

    @rx.event
    def abrir_novo(self):
        self.novo()
        self.dialogo_aberto = True

    @rx.event
    def fechar_dialogo(self):
        self.dialogo_aberto = False

    @rx.event
    async def editar(self, moto_id: str):
        registro = await xano.ler_direto(TABELA, int(moto_id))
        if registro is None:
            return rx.toast.error("Essa moto não existe mais no Xano.")
        self.form_id = registro["id"]
        self.marca = registro.get("marca") or ""
        self.modelo = registro.get("modelo") or ""
        self.ano = str(registro.get("ano") or "")
        self.cor = registro.get("cor") or ""
        self.placa = registro.get("placa") or ""
        self.chassi = registro.get("chassi") or ""
        self.quilometragem = str(registro.get("quilometragem") or "")
        self.status = servico.rotulo(registro)
        self.preco_compra = fmt.moeda(registro.get("preco_compra") or 0)
        self.preco_venda = fmt.moeda(registro.get("preco_venda") or 0)
        self.data_entrada = fmt.data_para_input(registro.get("data_entrada"))
        self.data_saida = fmt.data_para_input(registro.get("data_saida"))
        self.observacoes = registro.get("observacoes") or ""
        cliente_id = registro.get("cliente_id") or 0
        self.cliente_selecionado = next(
            (op for op in self.clientes_opcoes if op.startswith(f"{cliente_id} - ")), SEM_CLIENTE
        )
        foto = registro.get("foto") or {}
        self._foto = foto if foto.get("path") else {}
        self.foto_url = foto.get("url") or ""
        self.erro_foto = ""
        self.erro_form = ""
        self.dialogo_ver = False
        self.dialogo_aberto = True

    @rx.event
    async def handle_upload_foto(self, files: list[rx.UploadFile]):
        if not await sessao_ok(self):
            return
        self.erro_foto = ""
        if not files:
            return
        arquivo = files[0]
        conteudo = await arquivo.read()
        self.enviando_foto = True
        yield
        try:
            imagem = await imagens.enviar_ao_xano("moto_loja", arquivo.name or "", conteudo)
        except imagens.ImagemInvalida as erro:
            self.erro_foto = str(erro)
        except xano.UploadIndisponivel:
            self.erro_foto = (
                "O Xano ainda não tem o endpoint upload/image (ver Configuração do sistema). "
                "A moto pode ser salva sem foto."
            )
        except Exception:
            self.erro_foto = "Não foi possível enviar a foto ao Xano. Tente novamente."
        else:
            self._foto = imagem
            self.foto_url = imagem.get("url") or ""
        finally:
            self.enviando_foto = False

    @rx.event
    def remover_foto(self):
        self._foto = {}
        self.foto_url = ""
        self.erro_foto = ""

    @rx.event
    async def salvar(self):
        modelo = self.modelo.strip()
        placa = self.placa.strip().upper().replace(" ", "")
        chassi = self.chassi.strip().upper().replace(" ", "")
        if not self.marca.strip() or not modelo or not chassi:
            self.erro_form = "Preencha marca, modelo e chassi."
            return
        try:
            ano = fmt.inteiro(self.ano) if self.ano.strip() else 0
            quilometragem = fmt.inteiro(self.quilometragem)
            preco_compra = fmt.numero(self.preco_compra)
            preco_venda = fmt.numero(self.preco_venda)
        except ValueError:
            self.erro_form = "Ano, quilometragem e preços precisam ser números."
            return
        if ano and not 1903 <= ano <= datetime.date.today().year + 1:
            self.erro_form = "Ano inválido."
            return
        if quilometragem < 0 or preco_compra < 0 or preco_venda < 0:
            self.erro_form = "Quilometragem e preços não podem ser negativos."
            return
        situacao = servico.VALORES.get(self.status, servico.DISPONIVEL)

        duplicado = any(
            ((placa and (r.get("placa") or "").upper() == placa) or (r.get("chassi") or "").upper() == chassi)
            and r["id"] != self.form_id
            for r in await xano.listar(TABELA)
        )
        if duplicado:
            self.erro_form = "Já existe uma moto cadastrada com essa placa ou chassi."
            return

        cliente_id = 0 if self.cliente_selecionado == SEM_CLIENTE else int(self.cliente_selecionado.split(" - ")[0])
        data_saida = self.data_saida
        if situacao == servico.VENDIDA and not data_saida:
            data_saida = datetime.date.today().strftime("%Y-%m-%d")

        dados = {
            "marca": self.marca.strip(),
            "modelo": modelo,
            "ano": ano,
            "cor": self.cor.strip(),
            "placa": placa,
            "chassi": chassi,
            "quilometragem": quilometragem,
            "status": situacao,
            "em_estoque": servico.em_estoque(situacao),
            "preco_compra": round(preco_compra, 2),
            "preco_venda": round(preco_venda, 2),
            "data_entrada": fmt.input_para_epoch(self.data_entrada),
            "data_saida": fmt.input_para_epoch(data_saida),
            "observacoes": self.observacoes.strip(),
            "cliente_id": cliente_id,
            "foto": self._foto or None,
        }
        try:
            if self.form_id is None:
                await xano.criar(TABELA, dados)
            else:
                await xano.atualizar_mesclando(TABELA, self.form_id, dados)
        except Exception:
            self.erro_form = "Não foi possível salvar (falha de conexão com o Xano). Tente de novo."
            return
        novo = self.form_id is None
        self.dialogo_aberto = False
        self.novo()
        await self.carregar()
        return rx.toast.success("Moto cadastrada no estoque." if novo else "Moto atualizada.")

    @rx.event
    async def excluir(self, moto_id: str):
        registro = next((l for l in self._linhas if l["id"] == str(moto_id)), None)
        if registro and registro["status"] == servico.VENDIDA:
            return rx.toast.error("Moto vendida não pode ser excluída: o recibo e o histórico dependem dela. "
                                  "Para tirá-la da lista, filtre por situação.")
        encontrados = await integridade.dependentes(TABELA, int(moto_id))
        if encontrados:
            return rx.toast.error(integridade.mensagem_bloqueio("esta moto", encontrados))
        await xano.excluir(TABELA, int(moto_id))
        if self.form_id == int(moto_id):
            self.novo()
        await self.carregar()
        return rx.toast.success("Moto excluída.")

    # ---------------------------------------------------- visualizar / fotos

    @rx.event
    def visualizar(self, moto_id: str):
        linha = next((l for l in self._linhas if l["id"] == str(moto_id)), None)
        if linha is None:
            return
        self.moto_vista = linha
        self.fotos_vista = ([linha["foto_url"]] if linha["foto_url"] else []) + linha["fotos"]
        self.erro_fotos = ""
        self.dialogo_ver = True

    @rx.event
    def fechar_ver(self):
        self.dialogo_ver = False

    @rx.event
    async def adicionar_fotos(self, files: list[rx.UploadFile]):
        """Fotos adicionais (campo `fotos` da tabela motos)."""
        if not await sessao_ok(self):
            return
        self.erro_fotos = ""
        moto_id = int(self.moto_vista.get("id") or 0)
        if not files or not moto_id:
            return
        self.enviando_foto = True
        yield
        try:
            novas = []
            for arquivo in files[:6]:
                novas.append(await imagens.enviar_ao_xano("moto_loja", arquivo.name or "", await arquivo.read()))
            atual = await xano.ler_direto(TABELA, moto_id)
            existentes = atual.get("fotos") if isinstance(atual.get("fotos"), list) else []
            await xano.atualizar_mesclando(TABELA, moto_id, {"fotos": existentes + novas})
        except imagens.ImagemInvalida as erro:
            self.erro_fotos = str(erro)
        except xano.UploadIndisponivel:
            self.erro_fotos = ("O Xano ainda não tem o endpoint upload/image (ver Configuração do sistema): "
                               "fotos adicionais ficam disponíveis depois dele.")
        except Exception:
            self.erro_fotos = "Não foi possível guardar as fotos no Xano (confira o tipo do campo fotos: lista de imagens)."
        finally:
            self.enviando_foto = False
        await self.carregar()
        self.visualizar(str(moto_id))

    @rx.event
    async def remover_foto_adicional(self, url: str):
        moto_id = int(self.moto_vista.get("id") or 0)
        atual = await xano.ler_direto(TABELA, moto_id) if moto_id else None
        if atual is None:
            return
        restantes = [f for f in (atual.get("fotos") or [])
                     if not ((isinstance(f, dict) and f.get("url") == url) or f == url)]
        try:
            await xano.atualizar_mesclando(TABELA, moto_id, {"fotos": restantes})
        except Exception:
            return rx.toast.error("Não foi possível remover a foto.")
        await self.carregar()
        self.visualizar(str(moto_id))

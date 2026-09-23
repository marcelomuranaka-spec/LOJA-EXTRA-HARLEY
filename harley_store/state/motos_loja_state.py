"""
State de Motos da Loja (estoque de motos à venda) — tabela `motos` do Xano.

Não confundir com `motos_state.py` (motos dos CLIENTES, que passam pela
oficina). Aqui ficam as motos que a loja compra e revende.

Dois cuidados específicos desta tabela no Xano:

- O PATCH gerado pelo Xano SUBSTITUI o registro inteiro: campo que não
  for enviado volta zerado/vazio (inclusive a foto). Por isso `salvar()`
  sempre manda todos os campos, e guarda o objeto da foto já existente em
  `_foto` para reenviá-lo sem mudanças quando o usuário não troca a foto.
- `foto` é um campo de imagem do Xano (objeto com path/url), não um nome
  de arquivo local. Foto nova passa por `xano.enviar_imagem`.
- Datas (`data_entrada`/`data_saida`) são epoch em ms; 0 = sem data.
"""

import asyncio
import datetime
from pathlib import Path
from typing import Optional

import reflex as rx

from .. import xano_client as xano

TABELA = "motos"
TABELA_CLIENTES = "clientes"

STATUS_OPCOES = ["Em estoque", "Reservada", "Consignada", "Vendida"]
SEM_CLIENTE = "— nenhum —"

EXTENSOES_IMAGEM_PERMITIDAS = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp"}
TAMANHO_MAXIMO_IMAGEM = 5 * 1024 * 1024  # 5 MB


def _numero(valor: str) -> float:
    """Aceita "150000", "150.000,00" ou "150000.50"."""
    texto = (valor or "").strip().replace("R$", "").replace(" ", "")
    if "," in texto:
        texto = texto.replace(".", "").replace(",", ".")
    return float(texto) if texto else 0.0


def _moeda(valor: float) -> str:
    return f"{valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _data_para_input(epoch_ms: int | None) -> str:
    return xano.epoch_ms_para_datetime(epoch_ms).strftime("%Y-%m-%d") if epoch_ms else ""


def _input_para_epoch(texto: str) -> int:
    if not texto:
        return 0
    return xano.datetime_para_epoch_ms(datetime.datetime.strptime(texto, "%Y-%m-%d"))


class MotosLojaState(rx.State):
    motos: list[dict] = []
    busca: str = ""
    filtro_status: str = "Todos"

    clientes_opcoes: list[str] = []

    form_id: Optional[int] = None
    marca: str = "Harley-Davidson"
    modelo: str = ""
    ano: str = ""
    cor: str = ""
    placa: str = ""
    chassi: str = ""
    quilometragem: str = ""
    status: str = "Em estoque"
    preco_compra: str = ""
    preco_venda: str = ""
    data_entrada: str = ""
    data_saida: str = ""
    observacoes: str = ""
    cliente_selecionado: str = SEM_CLIENTE

    foto_url: str = ""
    erro_foto: str = ""
    enviando_foto: bool = False
    _foto: dict = {}

    @rx.var
    def status_opcoes(self) -> list[str]:
        return STATUS_OPCOES

    @rx.var
    def filtros_status(self) -> list[str]:
        return ["Todos", *STATUS_OPCOES]

    @rx.event
    async def carregar(self):
        clientes, registros = await asyncio.gather(xano.listar(TABELA_CLIENTES), xano.listar(TABELA))
        clientes.sort(key=lambda c: c["nome_cliente"])
        self.clientes_opcoes = [SEM_CLIENTE, *[f"{c['id']} - {c['nome_cliente']}" for c in clientes]]
        nomes_por_id = {c["id"]: c["nome_cliente"] for c in clientes}

        if self.busca.strip():
            termo = self.busca.strip().lower()
            registros = [
                r for r in registros
                if termo in f"{r.get('marca', '')} {r.get('modelo', '')} {r.get('placa', '')} {r.get('chassi', '')}".lower()
            ]
        if self.filtro_status != "Todos":
            registros = [r for r in registros if r.get("status") == self.filtro_status]
        registros.sort(key=lambda r: (r.get("marca") or "", r.get("modelo") or "", r.get("ano") or 0))

        self.motos = [
            {
                "id": str(r["id"]),
                "marca": r.get("marca") or "",
                "modelo": r.get("modelo") or "",
                "ano": str(r.get("ano") or ""),
                "cor": r.get("cor") or "",
                "placa": r.get("placa") or "",
                "chassi": r.get("chassi") or "",
                "quilometragem": str(r.get("quilometragem") or 0),
                "status": r.get("status") or "Em estoque",
                "preco_compra": _moeda(r.get("preco_compra") or 0),
                "preco_venda": _moeda(r.get("preco_venda") or 0),
                "data_entrada": _data_para_input(r.get("data_entrada")),
                "data_saida": _data_para_input(r.get("data_saida")),
                "observacoes": r.get("observacoes") or "",
                "id_cliente": str(r.get("cliente_id") or 0),
                "cliente_nome": nomes_por_id.get(r.get("cliente_id"), ""),
                "foto_url": ((r.get("foto") or {}).get("url")) or "",
            }
            for r in registros
        ]

    @rx.event
    async def definir_busca(self, valor: str):
        self.busca = valor
        await self.carregar()

    @rx.event
    async def definir_filtro_status(self, valor: str | list[str]):
        # o segmented_control declara str | list[str]; aqui é sempre um só valor
        self.filtro_status = valor[0] if isinstance(valor, list) else valor
        await self.carregar()

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
        self.status = "Em estoque"
        self.preco_compra = ""
        self.preco_venda = ""
        self.data_entrada = datetime.date.today().strftime("%Y-%m-%d")
        self.data_saida = ""
        self.observacoes = ""
        self.cliente_selecionado = SEM_CLIENTE
        self.foto_url = ""
        self.erro_foto = ""
        self._foto = {}

    @rx.event
    async def editar(self, moto_id: str):
        registro = await xano.buscar(TABELA, int(moto_id))
        if registro is None:
            return rx.window_alert("Essa moto não existe mais no Xano.")
        self.form_id = registro["id"]
        self.marca = registro.get("marca") or ""
        self.modelo = registro.get("modelo") or ""
        self.ano = str(registro.get("ano") or "")
        self.cor = registro.get("cor") or ""
        self.placa = registro.get("placa") or ""
        self.chassi = registro.get("chassi") or ""
        self.quilometragem = str(registro.get("quilometragem") or "")
        self.status = registro.get("status") or "Em estoque"
        self.preco_compra = _moeda(registro.get("preco_compra") or 0)
        self.preco_venda = _moeda(registro.get("preco_venda") or 0)
        self.data_entrada = _data_para_input(registro.get("data_entrada"))
        self.data_saida = _data_para_input(registro.get("data_saida"))
        self.observacoes = registro.get("observacoes") or ""
        cliente_id = registro.get("cliente_id") or 0
        self.cliente_selecionado = next(
            (op for op in self.clientes_opcoes if op.startswith(f"{cliente_id} - ")), SEM_CLIENTE
        )
        foto = registro.get("foto") or {}
        self._foto = foto if foto.get("path") else {}
        self.foto_url = foto.get("url") or ""
        self.erro_foto = ""
        return rx.scroll_to("form-moto-loja")

    @rx.event
    async def handle_upload_foto(self, files: list[rx.UploadFile]):
        self.erro_foto = ""
        if not files:
            return
        arquivo = files[0]
        extensao = Path(arquivo.name or "").suffix.lower()
        if extensao not in EXTENSOES_IMAGEM_PERMITIDAS:
            self.erro_foto = "Formato inválido. Use PNG, JPG ou WEBP."
            return
        conteudo = await arquivo.read()
        if len(conteudo) > TAMANHO_MAXIMO_IMAGEM:
            self.erro_foto = "Imagem muito grande (máximo 5 MB)."
            return
        self.enviando_foto = True
        yield
        try:
            imagem = await xano.enviar_imagem(arquivo.name, conteudo, EXTENSOES_IMAGEM_PERMITIDAS[extensao])
        except xano.UploadIndisponivel:
            self.erro_foto = (
                "O Xano ainda não tem o endpoint upload/image — veja a seção "
                "\"Fotos das motos da loja\" no README. A moto pode ser salva sem foto."
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
        placa = self.placa.strip().upper()
        chassi = self.chassi.strip().upper()
        if not self.marca.strip() or not modelo or not chassi:
            return rx.window_alert("Preencha marca, modelo e chassi.")
        try:
            ano = int(self.ano) if self.ano.strip() else 0
            quilometragem = int(_numero(self.quilometragem))
            preco_compra = _numero(self.preco_compra)
            preco_venda = _numero(self.preco_venda)
        except ValueError:
            return rx.window_alert("Ano, quilometragem e preços precisam ser números.")
        if ano and not 1903 <= ano <= datetime.date.today().year + 1:
            return rx.window_alert("Ano inválido.")

        duplicado = any(
            ((placa and (r.get("placa") or "").upper() == placa) or (r.get("chassi") or "").upper() == chassi)
            and r["id"] != self.form_id
            for r in await xano.listar(TABELA)
        )
        if duplicado:
            return rx.window_alert("Já existe uma moto cadastrada com essa placa ou chassi.")

        cliente_id = 0 if self.cliente_selecionado == SEM_CLIENTE else int(self.cliente_selecionado.split(" - ")[0])
        data_saida = self.data_saida
        if self.status == "Vendida" and not data_saida:
            data_saida = datetime.date.today().strftime("%Y-%m-%d")

        # Registro COMPLETO — o PATCH do Xano zera o que não for enviado.
        dados = {
            "marca": self.marca.strip(),
            "modelo": modelo,
            "ano": ano,
            "cor": self.cor.strip(),
            "placa": placa,
            "chassi": chassi,
            "quilometragem": quilometragem,
            "status": self.status,
            "em_estoque": self.status != "Vendida",
            "preco_compra": preco_compra,
            "preco_venda": preco_venda,
            "data_entrada": _input_para_epoch(self.data_entrada),
            "data_saida": _input_para_epoch(data_saida),
            "observacoes": self.observacoes.strip(),
            "cliente_id": cliente_id,
            "foto": self._foto or None,
        }
        if self.form_id is None:
            await xano.criar(TABELA, dados)
        else:
            await xano.atualizar(TABELA, self.form_id, dados)

        self.novo()
        await self.carregar()

    @rx.event
    async def excluir(self, moto_id: str):
        await xano.excluir(TABELA, int(moto_id))
        if self.form_id == int(moto_id):
            self.novo()
        await self.carregar()

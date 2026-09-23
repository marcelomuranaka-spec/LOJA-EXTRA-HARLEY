"""State de Funcionários. Dados vêm do backend Xano."""

from typing import Optional

import reflex as rx

from ..models import TIPOS_FUNCIONARIO
from .. import xano_client as xano

TABELA = "funcionarios"


class FuncionariosState(rx.State):
    funcionarios: list[dict] = []
    busca: str = ""

    form_id: Optional[int] = None
    nome_funcionario: str = ""
    cargo: str = ""
    tipo: str = TIPOS_FUNCIONARIO[0]
    contato: str = ""

    @rx.event
    async def carregar(self):
        registros = await xano.listar(TABELA)
        if self.busca.strip():
            termo = self.busca.strip().lower()
            registros = [r for r in registros if termo in r["nome_funcionario"].lower()]
        registros = sorted(registros, key=lambda r: r["nome_funcionario"])
        self.funcionarios = [
            {
                "id": str(r["id"]),
                "nome_funcionario": r["nome_funcionario"],
                "cargo": r["cargo"],
                "tipo": r["tipo"],
                "contato": r.get("contato") or "—",
            }
            for r in registros
        ]

    @rx.event
    async def definir_busca(self, valor: str):
        self.busca = valor
        await self.carregar()

    @rx.event
    def novo(self):
        self.form_id = None
        self.nome_funcionario = ""
        self.cargo = ""
        self.tipo = TIPOS_FUNCIONARIO[0]
        self.contato = ""

    @rx.event
    def editar(self, row: dict):
        self.form_id = int(row["id"])
        self.nome_funcionario = row["nome_funcionario"]
        self.cargo = row["cargo"]
        self.tipo = row["tipo"]
        self.contato = "" if row["contato"] == "—" else row["contato"]

    @rx.event
    async def salvar(self):
        nome = self.nome_funcionario.strip()
        cargo = self.cargo.strip()
        if not nome or not cargo:
            return rx.window_alert("Preencha nome e cargo do funcionário.")

        dados = {
            "nome_funcionario": nome,
            "cargo": cargo,
            "tipo": self.tipo,
            "contato": self.contato.strip() or None,
        }
        if self.form_id is None:
            await xano.criar(TABELA, dados)
        else:
            await xano.atualizar(TABELA, self.form_id, dados)

        self.novo()
        await self.carregar()

    @rx.event
    async def excluir(self, funcionario_id: str):
        await xano.excluir(TABELA, int(funcionario_id))
        await self.carregar()

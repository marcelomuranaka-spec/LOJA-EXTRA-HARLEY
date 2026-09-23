"""State de Clientes. Dados vêm do backend Xano."""

from typing import Optional

import reflex as rx

from .. import xano_client as xano

TABELA = "clientes"


class ClientesState(rx.State):
    clientes: list[dict] = []
    busca: str = ""

    form_id: Optional[int] = None
    nome_cliente: str = ""
    cpf_cnpj: str = ""
    telefone: str = ""
    email: str = ""
    endereco: str = ""

    @rx.event
    async def carregar(self):
        registros = await xano.listar(TABELA)
        if self.busca.strip():
            termo = self.busca.strip().lower()
            registros = [r for r in registros if termo in r["nome_cliente"].lower()]
        registros = sorted(registros, key=lambda r: r["nome_cliente"])
        self.clientes = [
            {
                "id": str(r["id"]),
                "nome_cliente": r["nome_cliente"],
                "cpf_cnpj": r["cpf_cnpj"],
                "telefone": r.get("telefone") or "—",
                "email": r.get("email") or "—",
                "endereco": r.get("endereco") or "—",
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
        self.nome_cliente = ""
        self.cpf_cnpj = ""
        self.telefone = ""
        self.email = ""
        self.endereco = ""

    @rx.event
    def editar(self, row: dict):
        self.form_id = int(row["id"])
        self.nome_cliente = row["nome_cliente"]
        self.cpf_cnpj = row["cpf_cnpj"]
        self.telefone = "" if row["telefone"] == "—" else row["telefone"]
        self.email = "" if row["email"] == "—" else row["email"]
        self.endereco = "" if row["endereco"] == "—" else row["endereco"]

    @rx.event
    async def salvar(self):
        nome = self.nome_cliente.strip()
        doc = self.cpf_cnpj.strip()
        if not nome or not doc:
            return rx.window_alert("Preencha nome e CPF/CNPJ do cliente.")

        duplicado = any(
            r["cpf_cnpj"] == doc and str(r["id"]) != str(self.form_id)
            for r in await xano.listar(TABELA)
        )
        if duplicado:
            return rx.window_alert("Já existe um cliente com esse CPF/CNPJ.")

        dados = {
            "nome_cliente": nome,
            "cpf_cnpj": doc,
            "telefone": self.telefone.strip() or None,
            "email": self.email.strip() or None,
            "endereco": self.endereco.strip() or None,
        }
        if self.form_id is None:
            await xano.criar(TABELA, dados)
        else:
            await xano.atualizar(TABELA, self.form_id, dados)

        self.novo()
        await self.carregar()

    @rx.event
    async def excluir(self, cliente_id: str):
        await xano.excluir(TABELA, int(cliente_id))
        await self.carregar()

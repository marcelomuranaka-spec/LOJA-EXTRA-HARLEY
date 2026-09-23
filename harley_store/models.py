"""
Modelos de dados (tabelas do banco) do Harley Store App.

Cada classe abaixo é uma tabela, e espelha 1:1 o script original
HARLEY_DAVIDSON_STORE.sql (SQL Server), adaptado para SQLModel/Reflex:

    SQL Server (original)              Python (aqui)
    ----------------------------------  ----------------------
    dbo.Fornecedores                    Fornecedor
    dbo.Produtos                        Produto
    dbo.Funcionarios                    Funcionario
    dbo.Clientes                        Cliente
    dbo.Motos_Clientes                  MotoCliente
    dbo.Entrada_Mercadoria              EntradaMercadoria
    dbo.Itens_Compra_Estoque            ItemCompraEstoque
    dbo.Transacoes                      Transacao
    dbo.Ordens_Servico                  OrdemServico
    dbo.Itens_Ordem_Servico             ItemOrdemServico

Toda tabela criada com `rx.Model, table=True` já ganha automaticamente
uma coluna `id` (chave primária, autoincremento) — por isso ela não
aparece declarada em nenhuma classe abaixo.

COMO ADICIONAR UMA TABELA NOVA
-------------------------------
1. Crie uma classe nova aqui, com `class MinhaTabela(rx.Model, table=True):`
   e defina `__tablename__` e os campos (veja os exemplos abaixo).
2. Rode no terminal, dentro da pasta do projeto:
       reflex db makemigrations --message "adiciona minha_tabela"
       reflex db migrate
   Isso atualiza o arquivo harley_store.db sem apagar os dados existentes.
3. Crie um `state/minha_tabela_state.py` e um `pages/minha_tabela.py`
   copiando o padrão de `fornecedores_state.py` / `fornecedores.py`,
   que é o CRUD mais simples do projeto.
4. Registre a página em `harley_store.py` (função `app.add_page(...)`)
   e o link em `components/layout.py` (lista MENU_ITEMS).

As validações de negócio (ex.: "estoque não pode ficar negativo", que no
SQL Server original era um CHECK CONSTRAINT) são feitas aqui na camada
Python, dentro dos States — o SQLite local não impõe CHECK constraints
como o SQL Server fazia. Se um dia migrar para Postgres/SQL Server de
verdade, vale recriar essas regras direto no banco também.
"""

from __future__ import annotations

import datetime
from typing import Optional

import reflex as rx
from sqlmodel import Field


class Fornecedor(rx.Model, table=True):
    __tablename__ = "fornecedores"

    nome_fornecedor: str
    cnpj: str = Field(unique=True)
    contato: Optional[str] = None


class Produto(rx.Model, table=True):
    __tablename__ = "produtos"

    nome_produto: str
    descricao: Optional[str] = None
    categoria: str
    estoque_qtd: int = 0
    preco_venda: float = 0.0
    imagem: Optional[str] = None


class Funcionario(rx.Model, table=True):
    __tablename__ = "funcionarios"

    nome_funcionario: str
    cargo: str
    tipo: str  # VENDEDOR | MECANICO | GERENTE
    contato: Optional[str] = None


TIPOS_FUNCIONARIO = ["VENDEDOR", "MECANICO", "GERENTE"]


class Cliente(rx.Model, table=True):
    __tablename__ = "clientes"

    nome_cliente: str
    cpf_cnpj: str = Field(unique=True)
    telefone: Optional[str] = None
    email: Optional[str] = None
    endereco: Optional[str] = None


class MotoCliente(rx.Model, table=True):
    __tablename__ = "motos_clientes"

    id_cliente: int = Field(foreign_key="clientes.id")
    modelo: str
    placa: str = Field(unique=True)
    chassi: str = Field(unique=True)
    imagem: Optional[str] = None


class EntradaMercadoria(rx.Model, table=True):
    __tablename__ = "entrada_mercadoria"

    id_fornecedor: int = Field(foreign_key="fornecedores.id")
    data_entrada: datetime.datetime = Field(default_factory=datetime.datetime.now)
    valor_total: float = 0.0


class ItemCompraEstoque(rx.Model, table=True):
    __tablename__ = "itens_compra_estoque"

    id_entrada: int = Field(foreign_key="entrada_mercadoria.id")
    id_produto: int = Field(foreign_key="produtos.id")
    quantidade: int
    valor_unitario: float


class Transacao(rx.Model, table=True):
    __tablename__ = "transacoes"

    tipo_transacao: str  # MOTO | PECAS | BALCAO | COMPRA | ORDEM_SERVICO
    id_funcionario: int = Field(foreign_key="funcionarios.id")
    id_cliente: Optional[int] = Field(default=None, foreign_key="clientes.id")
    id_moto_cliente: Optional[int] = Field(default=None, foreign_key="motos_clientes.id")
    data_transacao: datetime.datetime = Field(default_factory=datetime.datetime.now)
    valor_total: float = 0.0


TIPOS_TRANSACAO = ["BALCAO", "PECAS", "MOTO", "ORDEM_SERVICO", "COMPRA"]


class OrdemServico(rx.Model, table=True):
    __tablename__ = "ordens_servico"

    id_moto_cliente: int = Field(foreign_key="motos_clientes.id")
    id_funcionario: int = Field(foreign_key="funcionarios.id")
    data_abertura: datetime.datetime = Field(default_factory=datetime.datetime.now)
    status: str = "ABERTA"  # ABERTA | EM_ANDAMENTO | CONCLUIDA | CANCELADA


STATUS_OS = ["ABERTA", "EM_ANDAMENTO", "CONCLUIDA", "CANCELADA"]


class ItemOrdemServico(rx.Model, table=True):
    __tablename__ = "itens_ordem_servico"

    id_os: int = Field(foreign_key="ordens_servico.id")
    id_produto: int = Field(foreign_key="produtos.id")
    quantidade: int
    valor_total_item: float

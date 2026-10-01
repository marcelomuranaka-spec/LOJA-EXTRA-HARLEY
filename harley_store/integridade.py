"""
Integridade referencial que o banco original (SQL Server) garantia com
FOREIGN KEY e o Xano não garante.

Sem isso, excluir um cliente, funcionário, fornecedor, produto ou moto de
cliente deixava vendas, ordens de serviço e compras apontando para um id que
não existe mais (o registro some dos comprovantes e relatórios).

`DEPENDENCIAS` reproduz as chaves estrangeiras do modelo original
(models.py, espelho do HARLEY_DAVIDSON_STORE.sql), com o comportamento
padrão do SQL Server (NO ACTION): a exclusão é recusada enquanto houver
registros ligados, inclusive vendas canceladas, que ficam no histórico.

Os itens de venda (itens_transacao) de propósito não bloqueiam a exclusão
de produtos: o item guarda a descrição justamente para o comprovante
continuar correto se o produto for excluído (ver xano/table/itens_transacao.xs).

A consulta usa as listagens em cache (xano_client.listar): um registro
criado por outro processo nos últimos minutos pode não ser visto.
"""

from __future__ import annotations

from . import xano_client as xano

# tabela -> [(tabela que aponta para ela, campo da chave, nome na mensagem)]
DEPENDENCIAS: dict[str, list[tuple[str, str, str]]] = {
    "clientes": [
        ("motos_clientes", "id_cliente", "moto(s) do cliente"),
        ("transacoes", "id_cliente", "venda(s)"),
    ],
    "fornecedores": [
        ("entrada_mercadoria", "id_fornecedor", "compra(s)"),
    ],
    "funcionarios": [
        ("transacoes", "id_funcionario", "venda(s)"),
        ("ordens_servico", "id_funcionario", "ordem(ns) de serviço"),
    ],
    "produtos": [
        ("itens_compra_estoque", "id_produto", "item(ns) de compra"),
        ("itens_ordem_servico", "id_produto", "item(ns) de ordem de serviço"),
    ],
    "motos_clientes": [
        ("ordens_servico", "id_moto_cliente", "ordem(ns) de serviço"),
        ("transacoes", "id_moto_cliente", "venda(s)"),
    ],
}


def contar_dependentes(tabela: str, registro_id: int, listagens: dict[str, list[dict]]) -> list[str]:
    """Ex.: ["2 venda(s)", "1 ordem(ns) de serviço"]. Lista vazia = pode excluir."""
    encontrados = []
    for tabela_filha, campo, nome in DEPENDENCIAS.get(tabela, []):
        total = sum(1 for r in listagens.get(tabela_filha, []) if int(r.get(campo) or 0) == registro_id)
        if total:
            encontrados.append(f"{total} {nome}")
    return encontrados


async def dependentes(tabela: str, registro_id: int) -> list[str]:
    filhas = {filha for filha, _, _ in DEPENDENCIAS.get(tabela, [])}
    listagens = {filha: await xano.listar(filha) for filha in filhas}
    return contar_dependentes(tabela, int(registro_id), listagens)


def mensagem_bloqueio(o_que: str, encontrados: list[str]) -> str:
    return (
        f"Não é possível excluir {o_que}: há {', '.join(encontrados)} ligada(s) a ele. "
        "Excluir apagaria a referência no histórico."
    )

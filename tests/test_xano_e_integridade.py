"""
Testes sem acesso ao Xano de verdade: as respostas são simuladas com
httpx.MockTransport. Nada é gravado no banco da loja.

Rodar na raiz do projeto:  .venv\\Scripts\\python -m unittest discover -s tests -v
"""

from __future__ import annotations

import asyncio
import json
import unittest
from unittest import mock

import httpx

from harley_store import estoque, integridade, vendas_servico, xano_admin_client
from harley_store import xano_client as xano

# Guardada antes dos remendos dos testes, que trocam _credenciais por uma conta falsa.
_CREDENCIAIS_REAIS = xano._credenciais

TOKEN_1 = "token-1"
TOKEN_2 = "token-2"


class XanoFalso:
    """Xano simulado: login devolve tokens em sequência; tabelas exigem token."""

    def __init__(self, tokens=(TOKEN_1, TOKEN_2), token_aceito=TOKEN_1, produtos=None):
        self.tokens = list(tokens)
        self.token_aceito = token_aceito
        self.produtos = {p["id"]: dict(p) for p in (produtos or [])}
        self.logins = 0
        self.pedidos: list[httpx.Request] = []

    def __call__(self, pedido: httpx.Request) -> httpx.Response:
        self.pedidos.append(pedido)
        caminho = pedido.url.path
        if caminho.endswith("/auth/login"):
            self.logins += 1
            return httpx.Response(200, json={"authToken": self.tokens[self.logins - 1]})
        if pedido.headers.get("Authorization") != f"Bearer {self.token_aceito}":
            return httpx.Response(401, json={"code": "ERROR_CODE_UNAUTHORIZED"})
        partes = caminho.rstrip("/").split("/")
        if partes[-2] == "produtos":
            pid = int(partes[-1])
            if pid not in self.produtos:
                return httpx.Response(404)
            if pedido.method == "PATCH":
                self.produtos[pid].update(json.loads(pedido.content))
            return httpx.Response(200, json={"id": pid, **self.produtos[pid]})
        return httpx.Response(200, json=[])


class BaseComRemendos(unittest.IsolatedAsyncioTestCase):
    def preparar(self, falso: XanoFalso) -> XanoFalso:
        cliente = httpx.AsyncClient(transport=httpx.MockTransport(falso))
        self.addAsyncCleanup(cliente.aclose)
        remendos = {
            (xano, "_obter_cliente"): lambda: cliente,
            (xano, "_credenciais"): lambda: ("conta@teste", "senha-de-teste"),
            (xano, "_token"): None,
            (xano, "_trava_token"): asyncio.Lock(),
            (xano, "_cache"): {},
            (xano, "_travas"): {},
            (estoque, "_travas"): {},
        }
        for (modulo, nome), valor in remendos.items():
            remendo = mock.patch.object(modulo, nome, valor)
            remendo.start()
            self.addCleanup(remendo.stop)
        return falso


class TestTokenDoXano(BaseComRemendos):
    async def test_envia_token_da_conta_de_servico(self):
        falso = self.preparar(XanoFalso())
        self.assertEqual(await xano.listar("clientes"), [])
        self.assertEqual(falso.logins, 1)
        self.assertEqual(falso.pedidos[-1].headers["Authorization"], f"Bearer {TOKEN_1}")

    async def test_token_vencido_refaz_login_uma_vez(self):
        falso = self.preparar(XanoFalso(token_aceito=TOKEN_2))
        self.assertEqual(await xano.listar("clientes"), [])
        self.assertEqual(falso.logins, 2)
        self.assertEqual(falso.pedidos[-1].headers["Authorization"], f"Bearer {TOKEN_2}")

    async def test_sem_conta_configurada_explica_o_que_falta(self):
        with mock.patch.dict("os.environ", {"XANO_EMAIL": "", "XANO_SENHA": ""}),              mock.patch.object(xano, "_ARQUIVO_ENV", xano.Path("arquivo-que-nao-existe.env")):
            with self.assertRaises(xano.XanoSemLogin):
                _CREDENCIAIS_REAIS()


class TestLeiturasDiretasComToken(BaseComRemendos):
    """Regressão: estas leituras usavam _request sem token e recebiam 401
    depois que o Xano passou a exigir login (vendas e cancelamentos falhavam)."""

    async def test_estoque_le_produto_com_token(self):
        self.preparar(XanoFalso(produtos=[{"id": 7, "nome_produto": "Filtro", "estoque_qtd": 3}]))
        produto = await estoque._ler_produto(7)
        self.assertEqual(produto["estoque_qtd"], 3)

    async def test_venda_le_direto_com_token(self):
        self.preparar(XanoFalso())
        self.assertEqual(await vendas_servico._ler_direto("itens_transacao"), [])

    async def test_tela_de_usuarios_usa_o_token_de_quem_esta_logado(self):
        """O grupo Admin do Xano exige perfil admin: a chamada vai com o token
        do administrador logado, não com o da conta de serviço."""
        falso = self.preparar(XanoFalso(token_aceito="token-do-admin"))
        self.assertEqual(await xano_admin_client.listar_usuarios("token-do-admin"), [])
        self.assertEqual(falso.pedidos[-1].headers["Authorization"], "Bearer token-do-admin")
        self.assertEqual(falso.logins, 0)


class TestMovimentarEstoque(BaseComRemendos):
    async def test_entrada_de_compra_soma_no_saldo_real(self):
        falso = self.preparar(XanoFalso(produtos=[{"id": 1, "nome_produto": "Pneu", "estoque_qtd": 2}]))
        await estoque.movimentar({1: 5})
        self.assertEqual(falso.produtos[1]["estoque_qtd"], 7)

    async def test_saldo_vazio_conta_como_zero(self):
        falso = self.preparar(XanoFalso(produtos=[{"id": 1, "nome_produto": "Pneu", "estoque_qtd": None}]))
        await estoque.movimentar({1: 4})
        self.assertEqual(falso.produtos[1]["estoque_qtd"], 4)

    async def test_baixa_maior_que_o_saldo_nao_altera_nada(self):
        falso = self.preparar(XanoFalso(produtos=[
            {"id": 1, "nome_produto": "Pneu", "estoque_qtd": 5},
            {"id": 2, "nome_produto": "Vela", "estoque_qtd": 1},
        ]))
        with self.assertRaises(estoque.EstoqueInsuficiente):
            await estoque.movimentar({1: -2, 2: -3})
        self.assertEqual((falso.produtos[1]["estoque_qtd"], falso.produtos[2]["estoque_qtd"]), (5, 1))


class TestIntegridadeReferencial(unittest.TestCase):
    LISTAGENS = {
        "motos_clientes": [{"id": 1, "id_cliente": 10}],
        "transacoes": [
            {"id": 1, "id_cliente": 10, "id_funcionario": 3, "id_moto_cliente": 1, "status": "CANCELADA"},
            {"id": 2, "id_cliente": 0, "id_funcionario": 3, "id_moto_cliente": 0},
        ],
        "ordens_servico": [{"id": 1, "id_moto_cliente": 1, "id_funcionario": 4}],
        "entrada_mercadoria": [{"id": 1, "id_fornecedor": 5}],
        "itens_compra_estoque": [{"id": 1, "id_entrada": 1, "id_produto": 8}],
        "itens_ordem_servico": [],
        "itens_transacao": [{"id": 1, "transacao_id": 2, "produto_id": 9}],
    }

    def contar(self, tabela, registro_id):
        return integridade.contar_dependentes(tabela, registro_id, self.LISTAGENS)

    def test_cliente_com_moto_e_venda_cancelada_nao_pode_ser_excluido(self):
        self.assertEqual(self.contar("clientes", 10), ["1 moto(s) do cliente", "1 venda(s)"])

    def test_registro_sem_dependentes_pode_ser_excluido(self):
        self.assertEqual(self.contar("clientes", 11), [])
        self.assertEqual(self.contar("fornecedores", 6), [])

    def test_funcionario_com_vendas_e_os(self):
        self.assertEqual(self.contar("funcionarios", 3), ["2 venda(s)"])
        self.assertEqual(self.contar("funcionarios", 4), ["1 ordem(ns) de serviço"])

    def test_moto_de_cliente_com_os_e_venda(self):
        self.assertEqual(self.contar("motos_clientes", 1), ["1 ordem(ns) de serviço", "1 venda(s)"])

    def test_produto_em_compra_bloqueia_mas_item_de_venda_nao(self):
        self.assertEqual(self.contar("produtos", 8), ["1 item(ns) de compra"])
        self.assertEqual(self.contar("produtos", 9), [])

    def test_fornecedor_com_compra(self):
        self.assertEqual(self.contar("fornecedores", 5), ["1 compra(s)"])


if __name__ == "__main__":
    unittest.main()

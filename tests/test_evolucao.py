"""
Testes das regras da evolução do sistema (perfis, clientes, produtos,
vendas, leads e e-mail), sem acesso ao Xano de verdade: as respostas são
simuladas com httpx.MockTransport. Nada é gravado no banco da loja.

Rodar na raiz do projeto:  .venv\\Scripts\\python -m unittest discover -s tests -v
"""

from __future__ import annotations

import asyncio
import json
import unittest
from unittest import mock

import httpx
from reflex.event import Event

from harley_store import (clientes_servico, email_servico, estoque, formatacao, imagens, leads_servico,
                          motos_loja_servico, produtos_servico, seguranca, vendas_servico, xano_admin_client)
from harley_store import xano_client as xano
from harley_store.state.auth_state import AuthState
from harley_store.state.clientes_state import ClientesState
from harley_store.state import usuarios_state
from harley_store.state.usuarios_state import UsuariosState

CPF_VALIDO = "529.982.247-25"


# ------------------------------------------------------------------ Xano falso

class BancoFalso:
    """CRUD simulado por tabela, com ids sequenciais. `falhar_post` = tabela
    em que o próximo POST responde 500 (para testar o desfazer)."""

    def __init__(self, **tabelas):
        self.tabelas = {nome: {r["id"]: dict(r) for r in regs} for nome, regs in tabelas.items()}
        self.proximo = 1000
        self.falhar_post: set[str] = set()
        self.pedidos: list[tuple[str, str]] = []

    def __call__(self, pedido: httpx.Request) -> httpx.Response:
        partes = pedido.url.path.rstrip("/").split("/")
        self.pedidos.append((pedido.method, pedido.url.path))
        if partes[-1] == "login":
            return httpx.Response(200, json={"authToken": "token-servico"})
        if partes[-1].isdigit():
            tabela, rid = partes[-2], int(partes[-1])
        else:
            tabela, rid = partes[-1], None
        if tabela not in self.tabelas:
            return httpx.Response(404, json={"message": "Unable to locate request."})
        dados = self.tabelas[tabela]
        if pedido.method == "GET":
            if rid is None:
                return httpx.Response(200, json=list(dados.values()))
            return httpx.Response(200, json=dados[rid]) if rid in dados else httpx.Response(404)
        if pedido.method == "POST":
            if tabela in self.falhar_post:
                return httpx.Response(500)
            self.proximo += 1
            registro = {"id": self.proximo, **json.loads(pedido.content)}
            dados[self.proximo] = registro
            return httpx.Response(200, json=registro)
        if pedido.method == "PATCH":
            registro = {"id": rid, **json.loads(pedido.content)}  # PATCH do Xano substitui tudo
            dados[rid] = registro
            return httpx.Response(200, json=registro)
        if pedido.method == "DELETE":
            dados.pop(rid, None)
            return httpx.Response(200, json=None)
        return httpx.Response(405)


class ComBancoFalso(unittest.IsolatedAsyncioTestCase):
    def preparar(self, banco: BancoFalso) -> BancoFalso:
        cliente = httpx.AsyncClient(transport=httpx.MockTransport(banco))
        self.addAsyncCleanup(cliente.aclose)
        remendos = {
            (xano, "_obter_cliente"): lambda: cliente,
            (xano, "_credenciais"): lambda: ("conta@teste", "senha-de-teste"),
            (xano, "_token"): None,
            (xano, "_trava_token"): asyncio.Lock(),
            (xano, "_cache"): {},
            (xano, "_travas"): {},
            (xano, "_ausentes"): {},
            (estoque, "_travas"): {},
            (motos_loja_servico, "_travas"): {},
        }
        for (modulo, nome), valor in remendos.items():
            remendo = mock.patch.object(modulo, nome, valor)
            remendo.start()
            self.addCleanup(remendo.stop)
        return banco


# --------------------------------------------------------------- segurança

class AuthFalso:
    def __init__(self, valida: bool, admin: bool = False):
        self._valida, self._admin = valida, admin

    def sessao_valida(self):
        return self._valida

    def admin_confirmado(self):
        return self._valida and self._admin


class EstadoRaizFalso:
    def __init__(self, auth):
        self.auth = auth

    async def get_state(self, classe):
        assert classe is AuthState
        return self.auth


class TestMiddlewareDeSessao(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        seguranca.SOMENTE_ADMIN.add(UsuariosState)
        seguranca.SessaoMiddleware._protegidos = None
        self.mw = seguranca.SessaoMiddleware()

    async def processar(self, classe, handler, auth):
        evento = Event(token="t", name=f"{classe.get_full_name()}.{handler}", payload={})
        return await self.mw.preprocess(None, EstadoRaizFalso(auth), evento)

    async def test_acao_de_tela_sem_sessao_e_recusada(self):
        self.assertIsNotNone(await self.processar(ClientesState, "excluir", AuthFalso(valida=False)))

    async def test_acao_de_tela_com_sessao_passa(self):
        self.assertIsNone(await self.processar(ClientesState, "excluir", AuthFalso(valida=True)))

    async def test_login_passa_sem_sessao(self):
        self.assertIsNone(await self.processar(AuthState, "fazer_login", AuthFalso(valida=False)))

    async def test_tela_de_usuarios_exige_administrador(self):
        self.assertIsNotNone(await self.processar(UsuariosState, "alternar_perfil", AuthFalso(True, admin=False)))
        self.assertIsNone(await self.processar(UsuariosState, "alternar_perfil", AuthFalso(True, admin=True)))

    async def test_setter_automatico_tambem_e_protegido(self):
        self.assertIsNotNone(await self.processar(ClientesState, "set_busca", AuthFalso(valida=False)))


class TestRegrasDeUsuarios(unittest.TestCase):
    """Regras da tela Usuários do sistema (só administradores)."""

    def conta(self, id_, admin=False, voce=False, servico=False):
        return {"id": str(id_), "eh_admin": admin, "eh_voce": voce, "eh_servico": servico}

    def test_ultimo_administrador_nao_perde_o_perfil_nem_e_excluido(self):
        marcelo = self.conta(4, admin=True, voce=True)
        servico = self.conta(13, servico=True)
        contas = [marcelo, servico]
        self.assertIn("pelo menos um administrador", usuarios_state.bloqueio_mudar_perfil(contas, marcelo))
        joao = self.conta(20)
        self.assertIn("pelo menos um administrador", usuarios_state.bloqueio_excluir(contas + [joao],
                                                                                    {**marcelo, "eh_voce": False}))

    def test_com_dois_administradores_um_pode_virar_funcionario(self):
        marcelo, joao = self.conta(4, admin=True, voce=True), self.conta(20, admin=True)
        self.assertEqual(usuarios_state.bloqueio_mudar_perfil([marcelo, joao], joao), "")
        self.assertEqual(usuarios_state.bloqueio_excluir([marcelo, joao], joao), "")

    def test_funcionario_pode_virar_administrador(self):
        self.assertEqual(usuarios_state.bloqueio_mudar_perfil([], self.conta(20)), "")

    def test_conta_de_servico_e_a_propria_conta_protegidas(self):
        servico = self.conta(13, servico=True)
        self.assertIn("conta de serviço", usuarios_state.bloqueio_mudar_perfil([servico], servico))
        self.assertIn("conta de serviço", usuarios_state.bloqueio_excluir([servico], servico))
        self.assertIn("própria conta", usuarios_state.bloqueio_excluir([], self.conta(4, admin=True, voce=True)))


class TestClienteAdmin(ComBancoFalso):
    async def test_perfil_e_conta_nova_vao_com_o_token_do_administrador(self):
        enviados = []

        def falso(pedido):
            enviados.append((pedido.url.path, pedido.headers.get("Authorization"), json.loads(pedido.content or b"{}")))
            if pedido.url.path.endswith("/auth/signup"):
                return httpx.Response(200, json={"authToken": "novo", "user_id": "31"})
            return httpx.Response(200, json={"id": "31", "role": "admin"})

        cliente = httpx.AsyncClient(transport=httpx.MockTransport(falso))
        self.addAsyncCleanup(cliente.aclose)
        with mock.patch.object(xano, "_obter_cliente", lambda: cliente):
            novo_id = await xano_admin_client.criar_usuario("tok-admin", "João", "joao@x.com", "senha1234")
            await xano_admin_client.definir_perfil("tok-admin", novo_id, "admin")
        self.assertEqual(novo_id, 31)
        self.assertTrue(all(auth == "Bearer tok-admin" for _, auth, _ in enviados))
        self.assertEqual(enviados[-1][0].rsplit("/", 2)[-2:], ["user", "set-role"])
        self.assertEqual(enviados[-1][2], {"id": 31, "role": "admin"})
        with self.assertRaises(ValueError):
            await xano_admin_client.definir_perfil("tok-admin", 31, "dono")


# ----------------------------------------------------- formatação e imagens

class TestFormatacao(unittest.TestCase):
    def test_cpf_e_cnpj(self):
        self.assertTrue(formatacao.cpf_cnpj_valido(CPF_VALIDO))
        self.assertFalse(formatacao.cpf_cnpj_valido("529.982.247-24"))
        self.assertFalse(formatacao.cpf_cnpj_valido("111.111.111-11"))
        self.assertTrue(formatacao.cpf_cnpj_valido("11.222.333/0001-81"))
        self.assertEqual(formatacao.formatar_cpf_cnpj("52998224725"), CPF_VALIDO)

    def test_numeros_brasileiros(self):
        self.assertEqual(formatacao.numero("150.000,50"), 150000.5)
        self.assertEqual(formatacao.numero("R$ 10"), 10.0)
        self.assertEqual(formatacao.moeda(1234.5), "1.234,50")
        self.assertEqual(formatacao.inteiro("12.500"), 12500)

    def test_whatsapp(self):
        self.assertEqual(formatacao.link_whatsapp("(11) 98888-7777"), "https://wa.me/5511988887777")


class TestImagens(unittest.TestCase):
    PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 20

    def test_aceita_png_de_verdade(self):
        self.assertEqual(imagens.validar("foto.PNG", self.PNG), (".png", "image/png"))

    def test_recusa_extensao_conteudo_falso_e_tamanho(self):
        with self.assertRaises(imagens.ImagemInvalida):
            imagens.validar("foto.svg", b"<svg/>")
        with self.assertRaises(imagens.ImagemInvalida):
            imagens.validar("foto.png", b"isto nao e imagem")
        with self.assertRaises(imagens.ImagemInvalida):
            imagens.validar("foto.jpg", self.PNG)  # PNG com nome de JPG
        with self.assertRaises(imagens.ImagemInvalida):
            imagens.validar("foto.png", self.PNG + b"\x00" * imagens.TAMANHO_MAXIMO)

    def test_separa_url_e_arquivo_local(self):
        self.assertEqual(imagens.separar("https://x/y.png"), ("https://x/y.png", ""))
        self.assertEqual(imagens.separar("moto_abc.png"), ("", "moto_abc.png"))
        self.assertEqual(imagens.separar("../../segredo.png"), ("", ""))


# ------------------------------------------------------------- cliente Xano

class TestClienteXano(ComBancoFalso):
    async def test_tabela_inexistente_vira_recurso_desativado(self):
        self.preparar(BancoFalso(clientes=[]))
        self.assertIsNone(await xano.listar_se_existir("leads"))
        with self.assertRaises(xano.TabelaInexistente):
            await xano.criar("leads", {"nome": "x"})

    async def test_campos_do_xano(self):
        self.preparar(BancoFalso(clientes=[{"id": 1, "nome_cliente": "A", "cidade": None}]))
        self.assertEqual(await xano.campos("clientes"), {"id", "nome_cliente", "cidade"})

    async def test_atualizar_mesclando_preserva_campos_desconhecidos(self):
        banco = self.preparar(BancoFalso(motos=[{"id": 2, "modelo": "Fat Boy", "renavam": "123", "fotos": ["a"]}]))
        await xano.atualizar_mesclando("motos", 2, {"modelo": "Fat Boy 114"})
        self.assertEqual(banco.tabelas["motos"][2], {"id": 2, "modelo": "Fat Boy 114", "renavam": "123", "fotos": ["a"]})

    def test_campos_nao_gravados(self):
        self.assertEqual(xano.campos_nao_gravados({"cidade": "SP", "status": "Cliente"}, {"status": "Cliente"},
                                                  {"cidade", "status"}), ["cidade"])


# ------------------------------------------------------------------- clientes

class TestClientes(unittest.TestCase):
    def test_validacao_e_duplicidade(self):
        outros = [{"id": 1, "cpf_cnpj": CPF_VALIDO}]
        with self.assertRaises(clientes_servico.ErroValidacao):
            clientes_servico.validar_cliente({"nome_cliente": "X", "cpf_cnpj": "52998224725"}, outros, None)
        dados = clientes_servico.validar_cliente({"nome_cliente": "X", "cpf_cnpj": "52998224725"}, outros, 1,
                                                 CPF_VALIDO)
        self.assertEqual(dados["status"], "Cliente")

    def test_cliente_antigo_com_cpf_sem_digito_valido_pode_ser_editado(self):
        antigo = "111.222.333-44"
        dados = clientes_servico.validar_cliente({"nome_cliente": "Anselmo", "cpf_cnpj": antigo}, [], 7, antigo)
        self.assertEqual(dados["cpf_cnpj"], antigo)

    def test_moto_precisa_de_cliente(self):
        with self.assertRaises(clientes_servico.ErroValidacao):
            clientes_servico.validar_moto({"modelo": "M", "placa": "A", "chassi": "B"}, [], None, {1})

    def test_busca_por_numero_e_filtro(self):
        linhas = [clientes_servico.linha_cliente({"id": 1, "nome_cliente": "Ana", "cpf_cnpj": CPF_VALIDO,
                                                  "telefone": "(11) 97000-0001"}),
                  clientes_servico.linha_cliente({"id": 2, "nome_cliente": "Bia", "cpf_cnpj": "x",
                                                  "status": "Inativo"})]
        self.assertEqual([l["id"] for l in clientes_servico.filtrar_clientes(linhas, "97000", "Todos", "Todas",
                                                                             "Nome (A–Z)")], ["1"])
        self.assertEqual([l["id"] for l in clientes_servico.filtrar_clientes(linhas, "", "Inativo", "Todas",
                                                                             "Nome (A–Z)")], ["2"])

    def test_linha_do_tempo_ordenada(self):
        compras = clientes_servico.montar_compras(1, [{"id": 5, "id_cliente": 1, "data_transacao": 2000,
                                                       "valor_total": 10}], [])
        eventos = clientes_servico.montar_linha_do_tempo({"created_at": 1000}, compras, [], [
            {"epoch": 3000, "tipo": "Contato", "descricao": "ligou"}], [])
        self.assertEqual([e["titulo"] for e in eventos], ["Contato", "Venda nº 5 — R$ 10,00", "Cliente cadastrado"])


# ------------------------------------------------------- produtos/categorias

class TestProdutos(unittest.TestCase):
    def test_estoque_baixo_pelo_minimo_do_produto(self):
        self.assertTrue(produtos_servico.estoque_baixo({"estoque_qtd": 5}))  # padrão 5
        self.assertFalse(produtos_servico.estoque_baixo({"estoque_qtd": 5, "estoque_minimo": 2}))
        self.assertTrue(produtos_servico.estoque_baixo({"estoque_qtd": 9, "estoque_minimo": 10}))

    def test_importacao_de_categorias_nao_duplica(self):
        produtos = [{"id": 1, "categoria": "Peças"}, {"id": 2, "categoria": "pecas"}, {"id": 3, "categoria": "Pneus"}]
        criar, ligar = produtos_servico.plano_importacao(produtos, [{"id": 9, "nome": "Pneus"}])
        self.assertEqual(criar, ["Peças", "Acessórios", "Capacetes", "Vestuário", "Lubrificantes", "Outros"])
        self.assertEqual(len(ligar), 3)
        criar2, _ = produtos_servico.plano_importacao(produtos, [{"id": i, "nome": n} for i, n in enumerate(criar + ["Pneus"])])
        self.assertEqual(criar2, [])

    def test_estoque_inicial_so_no_cadastro(self):
        form = {"nome_produto": "Óleo", "categoria": "Lubrificantes", "preco_venda": "50", "estoque_inicial": "3"}
        self.assertEqual(produtos_servico.validar_produto(form, [], None, None)["estoque_qtd"], 3)
        self.assertNotIn("estoque_qtd", produtos_servico.validar_produto(form, [], 7, None))


class TestEstoqueProtegido(ComBancoFalso):
    async def test_editar_produto_nao_sobrescreve_saldo(self):
        banco = self.preparar(BancoFalso(produtos=[{"id": 1, "nome_produto": "Pneu", "estoque_qtd": 4}]))
        await estoque.editar_produto(1, {"nome_produto": "Pneu dianteiro", "estoque_qtd": 99})
        self.assertEqual(banco.tabelas["produtos"][1]["estoque_qtd"], 4)

    async def test_contagem_define_saldo_exato(self):
        banco = self.preparar(BancoFalso(produtos=[{"id": 1, "nome_produto": "Pneu", "estoque_qtd": 4}]))
        self.assertEqual(await estoque.definir_saldo(1, 10), (4, 10))
        self.assertEqual(banco.tabelas["produtos"][1]["estoque_qtd"], 10)


# -------------------------------------------------------------------- vendas

class TestVendaCompleta(ComBancoFalso):
    def banco(self, **extra):
        return BancoFalso(
            produtos=[{"id": 1, "nome_produto": "Capacete", "estoque_qtd": 5, "preco_venda": 100}],
            motos=[{"id": 2, "marca": "Harley-Davidson", "modelo": "Fat Boy", "ano": 2020, "placa": "ABC1D23",
                    "status": "Em estoque", "em_estoque": True, "cliente_id": 0, "data_saida": 0}],
            transacoes=[], itens_transacao=[], **extra)

    async def registrar(self, **kw):
        return await vendas_servico.registrar_venda(
            "MOTO", 1, 7, 0, [{"id_produto": 1, "descricao": "Capacete", "quantidade": 2, "valor_unitario": 100}],
            **kw)

    async def test_desconto_vira_item_e_total_bate(self):
        banco = self.preparar(self.banco())
        venda_id = await self.registrar(desconto=20, campos_venda={"desconto"})
        venda = banco.tabelas["transacoes"][venda_id]
        itens = [i for i in banco.tabelas["itens_transacao"].values() if i["transacao_id"] == venda_id]
        self.assertEqual(venda["valor_total"], 180)
        self.assertEqual(venda["desconto"], 20)
        self.assertEqual(round(sum(i["quantidade"] * i["valor_unitario"] for i in itens), 2), 180)
        self.assertEqual(banco.tabelas["produtos"][1]["estoque_qtd"], 3)

    async def test_campo_que_nao_existe_no_xano_nao_e_enviado(self):
        banco = self.preparar(self.banco())
        venda_id = await self.registrar(forma_pagamento="PIX", usuario_id=4)
        self.assertNotIn("forma_pagamento", banco.tabelas["transacoes"][venda_id])

    async def test_venda_de_moto_marca_vendida_e_cancelamento_devolve(self):
        banco = self.preparar(self.banco())
        venda_id = await self.registrar(moto_loja={"id": 2, "valor": 90000}, campos_venda={"moto_id"})
        moto = banco.tabelas["motos"][2]
        self.assertEqual((moto["status"], moto["cliente_id"], moto["em_estoque"]), ("Vendida", 7, False))
        self.assertEqual(banco.tabelas["transacoes"][venda_id]["valor_total"], 90200)
        resultado = await vendas_servico.cancelar_venda(venda_id)
        self.assertEqual(resultado["situacao"], "cancelada")
        moto = banco.tabelas["motos"][2]
        self.assertEqual((moto["status"], moto["cliente_id"]), ("Em estoque", 0))
        self.assertEqual(banco.tabelas["produtos"][1]["estoque_qtd"], 5)

    async def test_moto_ja_vendida_e_recusada_sem_mexer_no_estoque(self):
        banco = self.preparar(self.banco())
        banco.tabelas["motos"][2]["status"] = "Vendida"
        with self.assertRaises(vendas_servico.FalhaVenda):
            await self.registrar(moto_loja={"id": 2, "valor": 90000})
        self.assertEqual(banco.tabelas["produtos"][1]["estoque_qtd"], 5)

    async def test_falha_ao_gravar_desfaz_estoque_e_moto(self):
        banco = self.preparar(self.banco())
        banco.falhar_post.add("transacoes")
        with self.assertRaises(vendas_servico.FalhaVenda):
            await self.registrar(moto_loja={"id": 2, "valor": 90000})
        self.assertEqual(banco.tabelas["produtos"][1]["estoque_qtd"], 5)
        self.assertEqual(banco.tabelas["motos"][2]["status"], "Em estoque")

    async def test_desconto_maior_que_subtotal_e_recusado(self):
        self.preparar(self.banco())
        with self.assertRaises(vendas_servico.FalhaVenda):
            await self.registrar(desconto=500)


# --------------------------------------------------------------------- leads

class TestLeads(ComBancoFalso):
    def test_lead_precisa_de_um_contato(self):
        with self.assertRaises(leads_servico.ErroValidacao):
            leads_servico.validar_lead({"nome": "Rui"})

    async def test_conversao_cria_cliente_com_dados_do_lead(self):
        banco = self.preparar(BancoFalso(
            clientes=[{"id": 1, "nome_cliente": "Outro", "cpf_cnpj": "111.222.333-44"}],
            leads=[{"id": 5, "nome": "Rui Lima", "whatsapp": "(11) 98888-0000", "email": "rui@x.com",
                    "origem": "Instagram", "status": "Negociação", "cliente_id": 0}],
        ))
        cliente_id, criado = await leads_servico.converter(5, "52998224725")
        self.assertTrue(criado)
        cliente = banco.tabelas["clientes"][cliente_id]
        self.assertEqual((cliente["nome_cliente"], cliente["email"], cliente["cpf_cnpj"]),
                         ("Rui Lima", "rui@x.com", CPF_VALIDO))
        lead = banco.tabelas["leads"][5]
        self.assertEqual((lead["status"], lead["cliente_id"]), ("Convertido", cliente_id))

    async def test_conversao_com_cpf_existente_so_liga(self):
        banco = self.preparar(BancoFalso(
            clientes=[{"id": 1, "nome_cliente": "Rui", "cpf_cnpj": CPF_VALIDO}],
            leads=[{"id": 5, "nome": "Rui", "telefone": "1199", "status": "Novo", "cliente_id": 0}],
        ))
        self.assertEqual(await leads_servico.converter(5, CPF_VALIDO), (1, False))
        self.assertEqual(len(banco.tabelas["clientes"]), 1)


# -------------------------------------------------------------------- e-mail

class TestEmail(ComBancoFalso):
    async def test_sem_configuracao_registra_e_nao_envia(self):
        banco = self.preparar(BancoFalso(emails=[]))
        with mock.patch.object(email_servico, "configuracao", lambda: ("", "")):
            resultado = await email_servico.enviar("a@b.com", "Oi", "Texto", cliente_id=3)
        self.assertEqual(resultado.status, email_servico.NAO_CONFIGURADO)
        self.assertTrue(resultado.registrado)
        self.assertNotIn(("POST", "/v3/mail/send"), banco.pedidos)

    async def test_envio_aceito_pelo_sendgrid(self):
        banco = self.preparar(BancoFalso(emails=[]))
        original = banco.__call__

        def com_sendgrid(pedido):
            if pedido.url.host == "api.sendgrid.com":
                assert pedido.headers["Authorization"] == "Bearer SG.chave"
                return httpx.Response(202)
            return original(pedido)

        banco.__call__ = com_sendgrid  # type: ignore[method-assign]
        cliente = httpx.AsyncClient(transport=httpx.MockTransport(com_sendgrid))
        self.addAsyncCleanup(cliente.aclose)
        with mock.patch.object(xano, "_obter_cliente", lambda: cliente), \
             mock.patch.object(email_servico, "configuracao", lambda: ("SG.chave", "loja@x.com")):
            resultado = await email_servico.enviar("a@b.com", "Oi", "Texto")
        self.assertTrue(resultado.enviado)
        gravado = next(iter(banco.tabelas["emails"].values()))
        self.assertEqual(gravado["status"], "Enviado")

    async def test_destinatario_invalido(self):
        self.preparar(BancoFalso(emails=[]))
        self.assertEqual((await email_servico.enviar("sem-arroba", "a", "b")).status, email_servico.FALHOU)


if __name__ == "__main__":
    unittest.main()

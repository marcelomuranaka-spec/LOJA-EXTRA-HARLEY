"""
Cliente HTTP para o backend Xano (workspace HARLEY, instância Free).

Os states em `state/` usavam `rx.session()` (SQLModel/SQLite local). Este
módulo troca a fonte de dados pelas APIs REST publicadas no Xano, mantendo
a mesma forma de uso: funções simples que recebem/retornam `dict`.

Detalhes importantes do Xano que este cliente já resolve para quem chama:

- O endpoint PATCH gerado pelo assistente "CRUD Database Operations" do
  Xano exige TODOS os campos obrigatórios da tabela (não é um PATCH
  parcial de verdade) — por isso `update()` espera o registro completo,
  não só os campos alterados.
- Campos de data/hora voltam do Xano como epoch em milissegundos (int),
  não como string ISO. `epoch_ms_para_datetime` / `datetime_para_epoch_ms`
  fazem a conversão nos dois sentidos.
- O plano Free do Xano tem limite de requisições por minuto. Como
  algumas telas (ex.: Painel, Compras, Vendas, Ordens de Serviço) fazem
  várias chamadas em sequência para montar os menus/relatórios, é fácil
  esbarrar nesse limite (erro 429) mesmo em uso normal. `_request` faz
  retentativas automáticas com espera crescente antes de desistir.

Todas as funções aqui são `async` e usam `httpx.AsyncClient` (não
`httpx.request` síncrono). Isso importa especialmente no Reflex: um
event handler síncrono que faz uma chamada de rede bloqueante trava a
única thread do loop de eventos do app inteiro enquanto espera — nesse
tempo o servidor não consegue nem responder ao ping/pong do websocket,
e o navegador chega a mostrar "Cannot connect to server" mesmo com o
back-end vivo, só ocupado. Usando `await` em vez de chamada bloqueante,
o loop de eventos fica livre para atender outras coisas (incluindo o
próprio heartbeat da conexão) enquanto a resposta do Xano não chega.
"""

from __future__ import annotations

import asyncio
import copy
import datetime
import os
import time
from pathlib import Path

import httpx

BASE_URL = "https://x8ki-letl-twmt.n7.xano.io/api:LtU_pM2N"
_TIMEOUT = 15.0
_MAX_TENTATIVAS = 5
_ESPERA_BASE_SEGUNDOS = 1.5

# Uma conexão reaproveitada (keep-alive) em vez de uma nova a cada chamada:
# evita repetir o aperto de mão TLS com o Xano em toda consulta. Fica presa
# ao loop de eventos em que foi criada; se o loop mudar, cria outra.
_cliente: httpx.AsyncClient | None = None
_cliente_loop: asyncio.AbstractEventLoop | None = None


def _obter_cliente() -> httpx.AsyncClient:
    global _cliente, _cliente_loop
    loop = asyncio.get_running_loop()
    if _cliente is None or _cliente.is_closed or _cliente_loop is not loop:
        _cliente = httpx.AsyncClient(timeout=_TIMEOUT)
        _cliente_loop = loop
    return _cliente


# Métodos que podem ser repetidos sem efeito colateral: o PATCH do Xano grava
# o registro completo (mesmo resultado se repetido). POST NÃO entra: repetir
# um POST que chegou ao Xano mas cuja resposta se perdeu criaria um registro
# em dobro (por exemplo, uma venda duplicada).
_REPETIVEIS = {"GET", "PATCH", "PUT", "DELETE"}


async def _request(metodo: str, url: str, **kwargs) -> httpx.Response:
    client = _obter_cliente()
    for tentativa in range(_MAX_TENTATIVAS):
        try:
            resposta = await client.request(metodo, url, **kwargs)
        except httpx.TransportError:
            # rede instável / Xano demorando: tenta de novo só o que é seguro repetir
            if metodo.upper() not in _REPETIVEIS or tentativa == _MAX_TENTATIVAS - 1:
                raise
            await asyncio.sleep(_ESPERA_BASE_SEGUNDOS * (tentativa + 1))
            continue
        if resposta.status_code != 429:
            return resposta
        espera = float(resposta.headers.get("Retry-After", 0)) or _ESPERA_BASE_SEGUNDOS * (2**tentativa)
        await asyncio.sleep(min(espera, 20))
    return resposta


# Os endpoints das tabelas exigem login (sem token o Xano responde 401).
# O servidor entra com uma conta de serviço própria, e não com o token de
# quem está usando a tela: o cache é um só para todos e a tarefa de fundo
# manter_cache_aquecido roda sem ninguém logado. A conta é um usuário comum
# da tabela `user` do Xano; email e senha ficam no arquivo .env da raiz do
# projeto (fora do git, um em cada pasta: desenvolvimento e produção):
#     XANO_EMAIL=...
#     XANO_SENHA=...
# O token vale 24 h; quando vence, o Xano responde 401 e o login é refeito.
AUTH_URL = "https://x8ki-letl-twmt.n7.xano.io/api:lH_WsSPl"
_ARQUIVO_ENV = Path(__file__).resolve().parent.parent / ".env"
_token: str | None = None
_trava_token = asyncio.Lock()


class XanoSemLogin(Exception):
    """Conta de serviço do Xano não configurada ou recusada no login."""


def ler_env() -> dict[str, str]:
    """Linhas CHAVE=valor do .env da raiz (segredos do servidor, fora do git)."""
    valores = {}
    if _ARQUIVO_ENV.exists():
        for linha in _ARQUIVO_ENV.read_text(encoding="utf-8-sig").splitlines():
            chave, igual, valor = linha.partition("=")
            if igual and not chave.strip().startswith("#"):
                valores[chave.strip()] = valor.strip().strip("'\"")
    return valores


def _credenciais() -> tuple[str, str]:
    valores = ler_env()
    email = os.environ.get("XANO_EMAIL") or valores.get("XANO_EMAIL", "")
    senha = os.environ.get("XANO_SENHA") or valores.get("XANO_SENHA", "")
    if not email or not senha:
        raise XanoSemLogin(f"Defina XANO_EMAIL e XANO_SENHA em {_ARQUIVO_ENV}")
    return email, senha


def email_conta_servico() -> str:
    """E-mail da conta de serviço (para a tela de usuários protegê-la); "" se
    não configurada."""
    try:
        return _credenciais()[0].strip().lower()
    except XanoSemLogin:
        return ""


async def _obter_token(vencido: str | None = None) -> str:
    """Token atual; `vencido` é o token que acabou de levar 401. Se outra
    chamada já renovou enquanto esta esperava a trava, reaproveita o novo."""
    global _token
    async with _trava_token:
        if _token is None or _token == vencido:
            email, senha = _credenciais()
            resposta = await _request("POST", f"{AUTH_URL}/auth/login", json={"email": email, "password": senha})
            if resposta.status_code >= 400:
                raise XanoSemLogin(f"Login da conta de serviço {email} recusado pelo Xano ({resposta.status_code})")
            _token = resposta.json()["authToken"]
        return _token


async def _request_xano(metodo: str, url: str, **kwargs) -> httpx.Response:
    """_request com o token da conta de serviço. Um 401 significa que o Xano
    recusou antes de executar, então repetir (até um POST) não duplica nada."""
    token = await _obter_token()
    resposta = await _request(metodo, url, headers={"Authorization": f"Bearer {token}"}, **kwargs)
    if resposta.status_code == 401:
        token = await _obter_token(vencido=token)
        resposta = await _request(metodo, url, headers={"Authorization": f"Bearer {token}"}, **kwargs)
    return resposta


# Cache curto das listagens. As telas relistam as mesmas tabelas o tempo todo
# (a cada letra digitada numa busca, a cada troca de página, várias telas
# pedindo "clientes"): com o cache essas leituras são instantâneas e o limite
# de requisições do Xano Free deixa de ser atingido. Qualquer gravação feita
# pelo app (criar/atualizar/excluir) é aplicada no cache na hora (ver
# _aplicar_no_cache), então quem acabou de salvar sempre vê o dado novo. Alterações feitas por fora do
# app (painel do Xano) aparecem em no máximo _CACHE_SEGUNDOS (5 min).
_CACHE_SEGUNDOS = 300.0
_cache: dict[str, tuple[float, list[dict]]] = {}
_travas: dict[str, asyncio.Lock] = {}


def limpar_cache(tabela: str | None = None) -> None:
    if tabela is None:
        _cache.clear()
    else:
        _cache.pop(tabela, None)


class TabelaInexistente(Exception):
    """A tabela (ou os endpoints de CRUD dela) ainda não existe no Xano."""


# Tabelas que responderam 404: não pergunta de novo por _AUSENTE_SEGUNDOS
# (cada tela que usa um recurso ainda não ativado não gasta requisição).
_AUSENTE_SEGUNDOS = 300.0
_ausentes: dict[str, float] = {}


def _conferir_ausente(tabela: str) -> None:
    quando = _ausentes.get(tabela)
    if quando is not None and time.monotonic() - quando < _AUSENTE_SEGUNDOS:
        raise TabelaInexistente(tabela)


def esquecer_ausencias() -> None:
    """Depois de criar tabelas no Xano: confere de novo na próxima leitura."""
    _ausentes.clear()


async def _buscar_tabela(tabela: str) -> list[dict]:
    resposta = await _request_xano("GET", f"{BASE_URL}/{tabela}")
    if resposta.status_code == 404:
        _ausentes[tabela] = time.monotonic()
        raise TabelaInexistente(tabela)
    resposta.raise_for_status()
    _ausentes.pop(tabela, None)
    return resposta.json() or []


async def listar(tabela: str) -> list[dict]:
    # Devolve sempre uma CÓPIA: quem chama pode alterar os dicts à vontade.
    guardado = _cache.get(tabela)
    if guardado and time.monotonic() - guardado[0] < _CACHE_SEGUNDOS:
        return copy.deepcopy(guardado[1])
    _conferir_ausente(tabela)
    # A trava evita que várias telas pedindo a mesma tabela ao mesmo tempo
    # façam várias chamadas iguais ao Xano.
    trava = _travas.setdefault(tabela, asyncio.Lock())
    async with trava:
        guardado = _cache.get(tabela)
        if guardado and time.monotonic() - guardado[0] < _CACHE_SEGUNDOS:
            return copy.deepcopy(guardado[1])
        dados = await _buscar_tabela(tabela)
        _cache[tabela] = (time.monotonic(), dados)
        return copy.deepcopy(dados)


async def listar_se_existir(tabela: str) -> list[dict] | None:
    """None se a tabela ainda não existe no Xano (recurso não ativado)."""
    try:
        return await listar(tabela)
    except TabelaInexistente:
        return None


async def campos(tabela: str) -> set[str] | None:
    """Campos que a tabela tem hoje no Xano (o Xano devolve todos os campos
    em cada registro, mesmo vazios). None se a tabela não existe; conjunto
    vazio se ela existe mas não tem registros (não dá para saber)."""
    registros = await listar_se_existir(tabela)
    if registros is None:
        return None
    return {chave for registro in registros for chave in registro}


async def _renovar(tabela: str) -> None:
    _conferir_ausente(tabela)
    async with _travas.setdefault(tabela, asyncio.Lock()):
        _cache[tabela] = (time.monotonic(), await _buscar_tabela(tabela))


# Tabelas usadas pelas telas. Mantidas sempre em cache por manter_cache_aquecido.
TABELAS_AQUECIDAS = [
    "clientes", "produtos", "motos", "motos_clientes", "funcionarios", "fornecedores",
    "transacoes", "itens_transacao", "ordens_servico", "itens_ordem_servico",
    "entrada_mercadoria", "itens_compra_estoque",
    # tabelas novas (enquanto não existirem no Xano, são puladas sem requisição)
    "categorias", "formas_pagamento", "leads", "interacoes", "emails",
]


async def manter_cache_aquecido() -> None:
    """Tarefa de fundo do servidor (registrada em harley_store.py): mantém as
    tabelas sempre no cache, para que nenhuma tela precise esperar o Xano.

    Primeira passada rápida ao subir (1 tabela a cada 3 s); depois renova uma
    tabela a cada 15 s, ou seja, cada uma das 17 tabelas a cada ~4,3 min, antes
    de vencer o cache de 5 min. É no máximo 1 requisição a cada 15 s, bem abaixo
    do limite do plano Free (~10 a cada 20 s), então sobra folga para as
    gravações. Tabela que ainda não existe no Xano não gasta requisição."""
    espera = 3.0
    while True:
        for tabela in TABELAS_AQUECIDAS:
            try:
                await _renovar(tabela)
            except asyncio.CancelledError:
                raise
            except TabelaInexistente:
                continue  # recurso ainda não ativado: sem espera, sem requisição
            except Exception:
                pass  # sem internet/Xano fora: tenta de novo na próxima volta
            await asyncio.sleep(espera)
        espera = 15.0


async def buscar(tabela: str, registro_id: int) -> dict | None:
    """Um registro pelo id. Procura na listagem em cache em vez de chamar o
    Xano uma vez por registro: as tabelas da loja são pequenas, e um
    documento de OS, por exemplo, precisava de 4 buscas avulsas, o que
    estourava o limite de requisições do plano Free (erro 429 e espera)."""
    registro_id = int(registro_id)
    return next((r for r in await listar(tabela) if r.get("id") == registro_id), None)


# Cache atualizado pela própria gravação ("write-through"). O Xano devolve o
# registro completo após criar/alterar; aplicá-lo no cache mantém a listagem
# correta SEM reler a tabela inteira. Antes, cada gravação descartava o cache
# e a tela relia produtos/vendas/itens, o que somava requisições e fazia o
# Xano Free responder 429 ("espere 20 s") durante vendas e cancelamentos.
# Se algo der errado (resposta inesperada, tabela fora do cache), descarta
# o cache da tabela, e a próxima leitura busca do Xano: nunca fica dado errado.

def _aplicar_no_cache(tabela: str, registro_id: int, registro: dict | None) -> None:
    guardado = _cache.get(tabela)
    if not guardado:
        return
    lista = [r for r in guardado[1] if r.get("id") != registro_id]
    if registro is not None:
        lista.append(copy.deepcopy(registro))
    _cache[tabela] = (guardado[0], lista)


async def criar(tabela: str, dados: dict) -> dict:
    _conferir_ausente(tabela)
    try:
        resposta = await _request_xano("POST", f"{BASE_URL}/{tabela}", json=dados)
        if resposta.status_code == 404:
            _ausentes[tabela] = time.monotonic()
            raise TabelaInexistente(tabela)
        resposta.raise_for_status()
        registro = resposta.json()
        _aplicar_no_cache(tabela, int(registro["id"]), registro)
        return registro
    except Exception:
        limpar_cache(tabela)
        raise


async def atualizar(tabela: str, registro_id: int, dados: dict) -> dict:
    try:
        resposta = await _request_xano("PATCH", f"{BASE_URL}/{tabela}/{registro_id}", json=dados)
        resposta.raise_for_status()
        registro = resposta.json()
        _aplicar_no_cache(tabela, int(registro_id), registro)
        return registro
    except Exception:
        limpar_cache(tabela)
        raise


async def excluir(tabela: str, registro_id: int) -> None:
    try:
        resposta = await _request_xano("DELETE", f"{BASE_URL}/{tabela}/{registro_id}")
        if resposta.status_code != 404:
            resposta.raise_for_status()
        _aplicar_no_cache(tabela, int(registro_id), None)
    except Exception:
        limpar_cache(tabela)
        raise


async def ler_direto(tabela: str, registro_id: int) -> dict | None:
    """Um registro lido direto do Xano, sem cache (dado atual)."""
    resposta = await _request_xano("GET", f"{BASE_URL}/{tabela}/{int(registro_id)}")
    if resposta.status_code == 404:
        return None
    resposta.raise_for_status()
    return resposta.json()


async def atualizar_mesclando(tabela: str, registro_id: int, alteracoes: dict) -> dict:
    """PATCH seguro: o PATCH do Xano substitui o registro inteiro (campo não
    enviado volta vazio). Aqui o registro atual é relido do Xano e só os
    campos de `alteracoes` mudam: campos que o app não conhece (ex.: criados
    depois no painel) são preservados."""
    atual = await ler_direto(tabela, registro_id)
    if atual is None:
        raise LookupError(f"Registro {registro_id} de {tabela} não existe mais.")
    dados = {k: v for k, v in atual.items() if k != "id"}
    dados.update(alteracoes)
    return await atualizar(tabela, registro_id, dados)


def campos_nao_gravados(enviado: dict, devolvido: dict, nomes: list[str] | set[str]) -> list[str]:
    """Campos novos que foram enviados com valor e voltaram diferentes: sinal
    de que o endpoint do Xano ainda não tem esse campo nos inputs."""
    faltando = []
    for nome in nomes:
        valor = enviado.get(nome)
        if valor in (None, "", 0, False):
            continue
        voltou = devolvido.get(nome)
        if isinstance(valor, (int, float)) and not isinstance(valor, bool):
            try:
                igual = abs(float(voltou or 0) - float(valor)) < 0.005
            except (TypeError, ValueError):
                igual = False
        else:
            igual = str(voltou or "").strip().lower() == str(valor).strip().lower()
        if not igual:
            faltando.append(nome)
    return faltando


class UploadIndisponivel(Exception):
    """O endpoint `upload/image` ainda não foi criado no Xano."""


async def enviar_imagem(nome_arquivo: str, conteudo: bytes, mime: str) -> dict:
    """Sobe uma imagem para o storage do Xano e devolve o objeto de imagem
    (com `path`, `url`, etc.) — é esse objeto que vai no campo `foto` da
    tabela `motos`. Mandar a foto direto no POST/PATCH da tabela não
    funciona: o Xano grava só o nome, sem o arquivo. Precisa do endpoint
    `POST /upload/image` (ver README, seção "Fotos das motos da loja")."""
    resposta = await _request_xano(
        "POST", f"{BASE_URL}/upload/image", files={"content": (nome_arquivo, conteudo, mime)}
    )
    if resposta.status_code == 404:
        raise UploadIndisponivel()
    resposta.raise_for_status()
    return resposta.json()


def epoch_ms_para_datetime(valor: int | float | None) -> datetime.datetime:
    if not valor:
        return datetime.datetime.now()
    return datetime.datetime.fromtimestamp(valor / 1000)


def datetime_para_epoch_ms(valor: datetime.datetime | None = None) -> int:
    valor = valor or datetime.datetime.now()
    return int(valor.timestamp() * 1000)

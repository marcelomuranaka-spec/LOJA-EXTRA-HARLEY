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
import time

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


async def _request(metodo: str, url: str, **kwargs) -> httpx.Response:
    client = _obter_cliente()
    for tentativa in range(_MAX_TENTATIVAS):
        resposta = await client.request(metodo, url, **kwargs)
        if resposta.status_code != 429:
            return resposta
        espera = float(resposta.headers.get("Retry-After", 0)) or _ESPERA_BASE_SEGUNDOS * (2**tentativa)
        await asyncio.sleep(min(espera, 20))
    return resposta


# Cache curto das listagens. As telas relistam as mesmas tabelas o tempo todo
# (a cada letra digitada numa busca, a cada troca de página, várias telas
# pedindo "clientes"): com o cache essas leituras são instantâneas e o limite
# de requisições do Xano Free deixa de ser atingido. Qualquer gravação feita
# pelo app (criar/atualizar/excluir) apaga o cache da tabela na hora, então
# quem acabou de salvar sempre vê o dado novo. Alterações feitas por fora do
# app (painel do Xano) aparecem em no máximo _CACHE_SEGUNDOS (5 min).
_CACHE_SEGUNDOS = 300.0
_cache: dict[str, tuple[float, list[dict]]] = {}
_travas: dict[str, asyncio.Lock] = {}


def limpar_cache(tabela: str | None = None) -> None:
    if tabela is None:
        _cache.clear()
    else:
        _cache.pop(tabela, None)


async def listar(tabela: str) -> list[dict]:
    # Devolve sempre uma CÓPIA: quem chama pode alterar os dicts à vontade.
    guardado = _cache.get(tabela)
    if guardado and time.monotonic() - guardado[0] < _CACHE_SEGUNDOS:
        return copy.deepcopy(guardado[1])
    # A trava evita que várias telas pedindo a mesma tabela ao mesmo tempo
    # façam várias chamadas iguais ao Xano.
    trava = _travas.setdefault(tabela, asyncio.Lock())
    async with trava:
        guardado = _cache.get(tabela)
        if guardado and time.monotonic() - guardado[0] < _CACHE_SEGUNDOS:
            return copy.deepcopy(guardado[1])
        resposta = await _request("GET", f"{BASE_URL}/{tabela}")
        resposta.raise_for_status()
        dados = resposta.json() or []
        _cache[tabela] = (time.monotonic(), dados)
        return copy.deepcopy(dados)


async def _renovar(tabela: str) -> None:
    async with _travas.setdefault(tabela, asyncio.Lock()):
        resposta = await _request("GET", f"{BASE_URL}/{tabela}")
        resposta.raise_for_status()
        _cache[tabela] = (time.monotonic(), resposta.json() or [])


# Tabelas usadas pelas telas. Mantidas sempre em cache por manter_cache_aquecido.
TABELAS_AQUECIDAS = [
    "clientes", "produtos", "motos", "motos_clientes", "funcionarios", "fornecedores",
    "transacoes", "ordens_servico", "itens_ordem_servico", "entrada_mercadoria", "itens_compra_estoque",
]


async def manter_cache_aquecido() -> None:
    """Tarefa de fundo do servidor (registrada em harley_store.py): mantém as
    tabelas sempre no cache, para que nenhuma tela precise esperar o Xano.

    Primeira passada rápida ao subir (1 tabela a cada 3 s); depois renova uma
    tabela a cada 20 s, ou seja, cada tabela a cada ~3,7 min, antes de vencer o
    cache de 5 min. É 1 requisição a cada 20 s, bem abaixo do limite do plano
    Free (~10 a cada 20 s), então sobra folga para as gravações."""
    espera = 3.0
    while True:
        for tabela in TABELAS_AQUECIDAS:
            try:
                await _renovar(tabela)
            except asyncio.CancelledError:
                raise
            except Exception:
                pass  # sem internet/Xano fora: tenta de novo na próxima volta
            await asyncio.sleep(espera)
        espera = 20.0


async def buscar(tabela: str, registro_id: int) -> dict | None:
    """Um registro pelo id. Procura na listagem em cache em vez de chamar o
    Xano uma vez por registro: as tabelas da loja são pequenas, e um
    documento de OS, por exemplo, precisava de 4 buscas avulsas, o que
    estourava o limite de requisições do plano Free (erro 429 e espera)."""
    registro_id = int(registro_id)
    return next((r for r in await listar(tabela) if r.get("id") == registro_id), None)


async def criar(tabela: str, dados: dict) -> dict:
    limpar_cache(tabela)
    resposta = await _request("POST", f"{BASE_URL}/{tabela}", json=dados)
    limpar_cache(tabela)
    resposta.raise_for_status()
    return resposta.json()


async def atualizar(tabela: str, registro_id: int, dados: dict) -> dict:
    limpar_cache(tabela)
    resposta = await _request("PATCH", f"{BASE_URL}/{tabela}/{registro_id}", json=dados)
    limpar_cache(tabela)
    resposta.raise_for_status()
    return resposta.json()


async def excluir(tabela: str, registro_id: int) -> None:
    limpar_cache(tabela)
    resposta = await _request("DELETE", f"{BASE_URL}/{tabela}/{registro_id}")
    limpar_cache(tabela)
    if resposta.status_code == 404:
        return
    resposta.raise_for_status()


class UploadIndisponivel(Exception):
    """O endpoint `upload/image` ainda não foi criado no Xano."""


async def enviar_imagem(nome_arquivo: str, conteudo: bytes, mime: str) -> dict:
    """Sobe uma imagem para o storage do Xano e devolve o objeto de imagem
    (com `path`, `url`, etc.) — é esse objeto que vai no campo `foto` da
    tabela `motos`. Mandar a foto direto no POST/PATCH da tabela não
    funciona: o Xano grava só o nome, sem o arquivo. Precisa do endpoint
    `POST /upload/image` (ver README, seção "Fotos das motos da loja")."""
    resposta = await _request(
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

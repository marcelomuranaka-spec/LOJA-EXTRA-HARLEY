"""
Fotos de produtos, motos dos clientes e motos da loja: validação e onde guardar.

Validação (antes de guardar qualquer coisa):
- extensão: só PNG, JPG/JPEG e WEBP (SVG e GIF ficam de fora: SVG pode
  carregar código, e GIF não é necessário);
- conteúdo: os primeiros bytes do arquivo têm de ser mesmo de uma imagem
  desse tipo (o "MIME" real, e não o que o navegador declarou);
- tamanho: até 5 MB;
- nome: o nome enviado é descartado; o arquivo ganha um nome aleatório.

Onde guarda:
1. no storage do Xano, pelo endpoint `upload/image` (ver README, "Fotos das
   motos da loja"), quando ele existir: a foto aparece igual no
   desenvolvimento e na produção;
2. enquanto o endpoint não existir, na pasta `uploaded_files/` do servidor
   (como o app já fazia para produtos e motos dos clientes). Nesse caso a
   foto só existe no ambiente em que foi enviada.

Os campos `imagem` (texto) de produtos e motos dos clientes guardam a URL
completa (Xano) ou só o nome do arquivo local. `separar()` diz qual é qual
para a tela montar o endereço certo.
"""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import reflex as rx

from . import xano_client as xano

EXTENSOES = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp"}
TAMANHO_MAXIMO = 5 * 1024 * 1024  # 5 MB
FORMATOS_TEXTO = "PNG, JPG ou WEBP"


class ImagemInvalida(Exception):
    """Mensagem pronta para mostrar ao usuário."""


def _tipo_real(conteudo: bytes) -> str | None:
    if conteudo.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if conteudo.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if len(conteudo) >= 12 and conteudo[:4] == b"RIFF" and conteudo[8:12] == b"WEBP":
        return "image/webp"
    return None


def validar(nome_arquivo: str, conteudo: bytes) -> tuple[str, str]:
    """Devolve (extensão, mime). Levanta ImagemInvalida."""
    extensao = Path(nome_arquivo or "").suffix.lower()
    if extensao not in EXTENSOES:
        raise ImagemInvalida(f"Formato inválido. Use {FORMATOS_TEXTO}.")
    if not conteudo:
        raise ImagemInvalida("O arquivo está vazio.")
    if len(conteudo) > TAMANHO_MAXIMO:
        raise ImagemInvalida("Imagem muito grande (máximo 5 MB).")
    mime = _tipo_real(conteudo)
    if mime is None or mime != EXTENSOES[extensao]:
        raise ImagemInvalida(f"O arquivo não é uma imagem {FORMATOS_TEXTO} válida.")
    return extensao, mime


async def enviar_ao_xano(prefixo: str, nome_arquivo: str, conteudo: bytes) -> dict:
    """Objeto de imagem do Xano (campo `foto` das motos da loja). Levanta
    ImagemInvalida ou xano.UploadIndisponivel."""
    extensao, mime = validar(nome_arquivo, conteudo)
    return await xano.enviar_imagem(f"{prefixo}_{uuid4().hex}{extensao}", conteudo, mime)


async def guardar(prefixo: str, nome_arquivo: str, conteudo: bytes) -> str:
    """Valor para os campos `imagem` (texto): URL no Xano ou nome do arquivo
    local. Levanta ImagemInvalida."""
    extensao, mime = validar(nome_arquivo, conteudo)
    nome = f"{prefixo}_{uuid4().hex}{extensao}"
    try:
        imagem = await xano.enviar_imagem(nome, conteudo, mime)
        if imagem.get("url"):
            return imagem["url"]
    except xano.UploadIndisponivel:
        pass
    except Exception:
        pass  # Xano fora do ar: guarda local para não perder a foto
    (rx.get_upload_dir() / nome).write_bytes(conteudo)
    return nome


def separar(valor: str | None) -> tuple[str, str]:
    """(url_externa, arquivo_local) — um dos dois vazio."""
    valor = (valor or "").strip()
    if valor.startswith(("http://", "https://")):
        return valor, ""
    if valor and Path(valor).name == valor and Path(valor).suffix.lower() in EXTENSOES:
        return "", valor
    return "", ""

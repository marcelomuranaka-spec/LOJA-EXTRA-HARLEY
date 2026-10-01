"""
Formatação e conversão de valores no padrão brasileiro, usadas pelas telas:
moeda ("1.234,50"), números digitados ("1.234,50", "1234.5", "R$ 10"),
datas do Xano (epoch em milissegundos), CPF/CNPJ e e-mail.
"""

from __future__ import annotations

import datetime
import re

from . import xano_client as xano

_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def moeda(valor) -> str:
    """1234.5 -> "1.234,50"."""
    return f"{float(valor or 0):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def reais(valor) -> str:
    return "R$ " + moeda(valor)


def numero(texto) -> float:
    """Aceita "150000", "150.000,00", "150000.50" e "R$ 10". Vazio = 0.
    Levanta ValueError se não for número."""
    if isinstance(texto, (int, float)):
        return float(texto)
    texto = (texto or "").strip().replace("R$", "").replace(" ", "")
    if "," in texto:
        texto = texto.replace(".", "").replace(",", ".")
    return float(texto) if texto else 0.0


def inteiro(texto) -> int:
    """"12.500" -> 12500. Vazio = 0. Levanta ValueError se não for número."""
    if isinstance(texto, int):
        return texto
    texto = (str(texto or "")).strip().replace(".", "").replace(" ", "")
    return int(texto) if texto else 0


def data(epoch_ms) -> str:
    return xano.epoch_ms_para_datetime(epoch_ms).strftime("%d/%m/%Y") if epoch_ms else "—"


def data_hora(epoch_ms) -> str:
    return xano.epoch_ms_para_datetime(epoch_ms).strftime("%d/%m/%Y %H:%M") if epoch_ms else "—"


def epoch(epoch_ms) -> float:
    """Para ordenar: registros sem data ficam por último/primeiro de forma estável."""
    return float(epoch_ms or 0)


def data_para_input(epoch_ms) -> str:
    """epoch ms -> "AAAA-MM-DD" (campo de data do navegador)."""
    return xano.epoch_ms_para_datetime(epoch_ms).strftime("%Y-%m-%d") if epoch_ms else ""


def input_para_epoch(texto: str) -> int:
    if not texto:
        return 0
    return xano.datetime_para_epoch_ms(datetime.datetime.strptime(texto, "%Y-%m-%d"))


def so_digitos(texto) -> str:
    return re.sub(r"\D", "", str(texto or ""))


def formatar_cpf_cnpj(texto) -> str:
    d = so_digitos(texto)
    if len(d) == 11:
        return f"{d[:3]}.{d[3:6]}.{d[6:9]}-{d[9:]}"
    if len(d) == 14:
        return f"{d[:2]}.{d[2:5]}.{d[5:8]}/{d[8:12]}-{d[12:]}"
    return (texto or "").strip()


def _digito(numeros: str, pesos: list[int]) -> int:
    resto = sum(int(n) * p for n, p in zip(numeros, pesos)) % 11
    return 0 if resto < 2 else 11 - resto


def cpf_cnpj_valido(texto) -> bool:
    """Confere os dígitos verificadores de CPF (11) ou CNPJ (14)."""
    d = so_digitos(texto)
    if len(d) == 11:
        if d == d[0] * 11:
            return False
        return (_digito(d[:9], list(range(10, 1, -1))) == int(d[9])
                and _digito(d[:10], list(range(11, 1, -1))) == int(d[10]))
    if len(d) == 14:
        if d == d[0] * 14:
            return False
        pesos1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
        return _digito(d[:12], pesos1) == int(d[12]) and _digito(d[:13], [6] + pesos1) == int(d[13])
    return False


def email_valido(texto) -> bool:
    return bool(_EMAIL.match((texto or "").strip()))


def formatar_telefone(texto) -> str:
    d = so_digitos(texto)
    if len(d) == 11:
        return f"({d[:2]}) {d[2:7]}-{d[7:]}"
    if len(d) == 10:
        return f"({d[:2]}) {d[2:6]}-{d[6:]}"
    return (texto or "").strip()


_USUARIO_TELEGRAM = re.compile(r"^[A-Za-z][A-Za-z0-9_]{4,31}$")


def formatar_telegram(texto) -> str:
    """Contato do Telegram: "@usuario" (aceita também "usuario" ou o link
    t.me/usuario) ou um número de telefone, formatado. Vazio = ""."""
    t = (texto or "").strip()
    if not t:
        return ""
    if "t.me/" in t:
        t = t.rstrip("/").rsplit("/", 1)[-1]
    usuario = t.lstrip("@").strip()
    if _USUARIO_TELEGRAM.match(usuario):
        return "@" + usuario
    return formatar_telefone(t)


def telegram_valido(texto) -> bool:
    t = formatar_telegram(texto)
    if t.startswith("@"):
        return bool(_USUARIO_TELEGRAM.match(t[1:]))
    return len(so_digitos(t)) in (10, 11, 12, 13) and not re.search(r"[A-Za-z@]", t)


def link_telegram(texto) -> str:
    """Link para abrir a conversa no Telegram: t.me/usuario ou t.me/+55DDNUMERO
    (pelo número só abre se a pessoa permitir ser encontrada pelo telefone)."""
    if not telegram_valido(texto):
        return ""
    t = formatar_telegram(texto)
    if t.startswith("@"):
        return f"https://t.me/{t[1:]}"
    d = so_digitos(t)
    if not d:
        return ""
    if len(d) in (10, 11):
        d = "55" + d
    return f"https://t.me/+{d}"

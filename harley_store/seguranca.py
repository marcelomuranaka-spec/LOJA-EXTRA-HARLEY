"""
Proteção das ações de tela no servidor.

Esconder um botão ou redirecionar no `on_load` não basta: o navegador pode
mandar ao servidor qualquer evento pelo websocket (salvar, excluir...), com
ou sem a página aberta. Este middleware do Reflex confere CADA evento antes
de executá-lo:

- eventos dos states do app (`harley_store.state.*`) só rodam com a sessão
  conferida no Xano (`AuthState.sessao_valida`), exceto os do próprio
  AuthState (login, sair, conferir sessão);
- eventos dos states listados em `SOMENTE_ADMIN` exigem perfil Administrador.

Eventos internos do Reflex (hidratação, on_load) passam direto: eles mesmos
chamam `AuthState.exigir_login`. Um state novo criado em `state/` fica
protegido automaticamente.

O envio de arquivos (rx.upload) não passa por middleware no Reflex 0.7: os
handlers de upload chamam `sessao_ok(self)` no início.
"""

from __future__ import annotations

import reflex as rx
from reflex.event import Event, fix_events
from reflex.middleware import Middleware
from reflex.state import BaseState, StateUpdate

from .state.auth_state import AuthState

_PACOTE_STATES = "harley_store.state."
_LIVRES = {AuthState}

# Preenchido em `registrar` (harley_store.py), com os states das telas de
# administração.
SOMENTE_ADMIN: set[type[BaseState]] = set()


def _todos_os_states(raiz: type[BaseState] = rx.State) -> list[type[BaseState]]:
    encontrados = []
    for sub in raiz.class_subclasses:
        encontrados.append(sub)
        encontrados.extend(_todos_os_states(sub))
    return encontrados


def _nomes_protegidos() -> tuple[set[str], set[str]]:
    protegidos = {
        s.get_full_name()
        for s in _todos_os_states()
        if s.__module__.startswith(_PACOTE_STATES) and s not in _LIVRES
    }
    so_admin = {s.get_full_name() for s in SOMENTE_ADMIN}
    return protegidos, so_admin


def _recusar(event: Event, destino: str, aviso: str) -> StateUpdate:
    eventos = fix_events([rx.redirect(destino), rx.toast.warning(aviso)], event.token)
    return StateUpdate(delta={}, events=eventos, final=True)


class SessaoMiddleware(Middleware):
    _protegidos: set[str] | None = None
    _so_admin: set[str] = set()

    async def preprocess(self, app, state: BaseState, event: Event) -> StateUpdate | None:
        if self._protegidos is None:
            # Calculado na primeira ação: aí todos os states já foram importados.
            SessaoMiddleware._protegidos, SessaoMiddleware._so_admin = _nomes_protegidos()
        nome_state = event.name.rpartition(".")[0]
        if nome_state not in self._protegidos:
            return None
        auth = await state.get_state(AuthState)
        if not auth.sessao_valida():
            return _recusar(event, "/login", "Entre no sistema para continuar.")
        if nome_state in self._so_admin and not auth.admin_confirmado():
            return _recusar(event, "/painel", "Essa ação é só para administradores.")
        return None


async def sessao_ok(state: BaseState) -> bool:
    """Para handlers que não passam pelo middleware (upload de arquivos)."""
    return (await state.get_state(AuthState)).sessao_valida()


async def admin_ok(state: BaseState) -> bool:
    return (await state.get_state(AuthState)).admin_confirmado()


def registrar(app: rx.App, *states_admin: type[BaseState]) -> None:
    SOMENTE_ADMIN.update(states_admin)
    app.add_middleware(SessaoMiddleware())

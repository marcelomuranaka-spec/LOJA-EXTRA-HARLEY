# AGENTS.md — Instruções para agentes de IA

Regras de trabalho para qualquer agente de IA que atue neste projeto.

## Documentação

- Antes de alterações significativas, ler `docs/project-overview.md`,
  `docs/domain-model.md` e as specs relacionadas em `openspec/specs/`.
- Escrever documentação, artefatos OpenSpec e mensagens da interface em
  português do Brasil.

## Desenvolvimento com OpenSpec

- Toda mudança de comportamento passa pelo ciclo do OpenSpec:
  explore → propose → revisão do grupo → apply → archive.
- Não implementar durante o propose; esperar a aprovação do grupo.
- Se a implementação exigir algo fora do que a change descreve, parar e
  perguntar, em vez de improvisar.

## Arquitetura

- Respeitar a stack definida: Python + Reflex (interface e servidor) e
  Xano (dados e autenticação). Não introduzir outro banco ou framework sem
  justificativa aprovada.
- Cada tela é um par `harley_store/state/<nome>_state.py` +
  `harley_store/pages/<nome>.py`; rotas em `harley_store/harley_store.py`.
- Acesso a dados só por `harley_store/xano_client.py`. O PATCH do Xano
  substitui o registro inteiro: sempre enviar todos os campos.
- Mudanças no banco vão pelo espelho em `xano/` e são aplicadas com
  `scripts/aplicar_xano.ps1`.

## Código

- Reutilizar o código existente e evitar duplicação.
- Não alterar funcionalidades não relacionadas à change atual.
- Escopo enxuto: não criar campos ou tabelas no Xano sem pedido explícito.

## Segurança

- Regras de negócio e de autorização ficam no servidor e no Xano; a
  interface não é mecanismo de segurança.
- Todo state novo deve entrar no `ExigeSessaoMiddleware`.
- Nunca expor ou versionar credenciais (`.env` fica fora do git).
- O Xano é compartilhado entre desenvolvimento e produção: testes com dados
  reais só com registros marcados como TESTE, removidos ao final.

## Testes

- Mudanças funcionais devem ter estratégia de verificação; regras de
  cálculo em funções puras com testes em `tests/`.
- Antes de concluir: `.venv\Scripts\python.exe -m unittest discover -s tests -t .`

## Git

- Commit e envio ao GitHub somente quando o grupo pedir.

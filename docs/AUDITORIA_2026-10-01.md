# Auditoria do banco de dados e da aplicação (01/10/2026)

- Branch da auditoria: `audit/database-refactor`
- Ponto de restauração (estado antes da auditoria, com o n8n): commit `3bf70f1`
- Estado original antes do n8n: `main` = `b26972a` (intocado)
- Bot do Telegram (n8n) preservado no branch `n8n/assistente-telegram`

## 1. Situação original

**Banco real: Xano** (PostgreSQL gerenciado, plano Free), um só para produção e
desenvolvimento. O app não fala SQL: usa a API REST do Xano.

| Grupo de API | Canonical | Uso | Autenticação hoje |
|---|---|---|---|
| CRUD das tabelas | `LtU_pM2N` | todas as telas | exige login (ligado no painel do Xano, fora do git) |
| Authentication | `lH_WsSPl` | login, cadastro, "esqueci minha senha" | público, exceto `auth/me` e `reset/update_password` |
| Admin | `KegVKtiw` | tela "Usuários do sistema" | exige login (no painel); o espelho no git ainda mostra sem login |
| event_logs | `hcb8d6dA` | não usado pelo app | `auth = "user"` |
| relatorios | `relatorios` | endpoint vazio (`response = null`) | — |

**Tabelas** (espelho em `xano/table`; `motos` existe só no Xano, não foi exportada):

| Tabela | Únicos | Referências (int simples, sem FK) | Observações |
|---|---|---|---|
| clientes | cpf_cnpj | — | |
| fornecedores | cnpj | — | |
| funcionarios | — | — | tipo em texto livre (VENDEDOR/MECANICO/GERENTE no código) |
| produtos | — | — | estoque_qtd opcional; sem SKU |
| motos | ? (não exportada) | cliente_id → clientes | unicidade de placa/chassi só no código |
| motos_clientes | placa, chassi | id_cliente → clientes | |
| transacoes | — | id_funcionario, id_cliente, id_moto_cliente | status ATIVA/CANCELADA; data_cancelamento é `date` |
| itens_transacao | — | transacao_id, produto_id (0 = avulso) | guarda descrição do produto |
| ordens_servico | — | id_moto_cliente, id_funcionario | |
| itens_ordem_servico | — | id_os, id_produto | |
| entrada_mercadoria | — | id_fornecedor | |
| itens_compra_estoque | — | id_entrada, id_produto | |
| user, event_log | email | event_log.user_id → user | modelo "quick start" do Xano |

Sem triggers, views, procedures ou sequences (o Xano não os expõe). Funções
Xano: `log_event`, `generate_magic_link`, `enforce_role` (não usada), `resumo_operacoes`.

**Banco local** `harley_store.db` (SQLite) + Alembic (6 migrations em linha, sem
conflito) + `models.py`: legado da migração SQL Server → SQLite → Xano. Todas as
tabelas têm 0 registros; `models.py` ainda fornece constantes às telas.

**Dados reais na data da auditoria:** clientes 10, fornecedores 10, funcionários
10, produtos 10, motos 1, motos de clientes 10, vendas 9 (formato antigo, sem
itens), itens de venda 0, OS 10, itens de OS 10, compras 10, itens de compra 10.

## 2. Alterações relacionadas ao n8n

Nenhum commit anterior a `3bf70f1` menciona n8n, Telegram ou webhook, e o
código do app não referencia nada disso.

| Item | Onde | Classe | Situação |
|---|---|---|---|
| `n8n/` (compose, `iniciar_n8n.ps1`, `configurar_bot.ps1`, 3 workflows) | git | **B** n8n | mantido, aguardando decisão (ver §5) |
| Seção "Assistente de vendas no Telegram (n8n)" do README | git | **B** n8n | idem |
| Container n8n (`happy_pike`), túnel, Data Table `leads_telegram` | Docker | **B** n8n | fora do projeto; o reset do Docker apagou a versão anterior |
| Login de serviço no Xano (`xano_client._request_xano`, `.env`) | git | **D** necessária | mantida: sem ela o app recebe 401 |
| `scripts/configurar_xano.ps1`, passo do `.env` no README | git | **D** necessária | mantida |
| Login exigido nos grupos CRUD e Admin | painel Xano | **C** duvidosa | mantida: o dono confirmou que foi intencional, e o roadmap já previa (`proteger-api-de-dados`). Reverter reabriria os dados ao público |
| Tabelas, colunas ou endpoints novos no Xano para o n8n | — | — | nenhum encontrado (os leads ficavam no n8n) |

## 3. Problemas encontrados

| ID | Gravidade | Problema | Local | Situação |
|---|---|---|---|---|
| P01 | CRÍTICO | Vendas e cancelamentos falhavam com 401: as leituras diretas do estoque e dos itens iam sem token. Causa: o login de serviço de `3bf70f1` cobriu só listar/criar/atualizar/excluir | `estoque.py`, `vendas_servico.py` | **corrigido** |
| P02 | CRÍTICO | `reset/request-code` devolve o código de redefinição na resposta: quem souber um email troca a senha daquela conta (inclusive a conta de serviço do app). A tela "Esqueci minha senha" usa esse fluxo | Xano Authentication; `xano_auth_client.redefinir_senha` | pendente (decisão) |
| P03 | CRÍTICO | Cadastro aberto (`auth/signup` público e aba "Cadastrar") e endpoints de dados que aceitam qualquer conta: qualquer pessoa cria uma conta e lê ou altera todos os dados (CPF, telefones). Não testado de propósito, para não criar conta na produção; conferir no Xano se o CRUD verifica `role` | Xano; `pages/login.py` | pendente (decisão) |
| P04 | ALTO | Grupo Admin sem verificação de perfil: qualquer conta logada lista e exclui usuários ou troca o email de outra conta (com P02, toma a conta) | Xano Admin | pendente (`enforce_role` já existe no Xano) |
| P05 | ALTO | Tela "Usuários do sistema" quebrada (401): chamadas sem token | `xano_admin_client.py` | **corrigido** |
| P06 | ALTO | Exclusão sem verificar dependências: cliente, funcionário, fornecedor, produto e moto de cliente podiam ser apagados com vendas, OS e compras ligadas (órfãos). O SQL Server original tinha essas FKs | telas de cadastro | **corrigido** no app |
| P07 | ALTO | A sessão do app vale só pela existência do cookie: um cookie inventado abre as telas e, com a conta de serviço, dá acesso a todos os dados pela interface | `auth_state.exigir_login` | pendente (change `validar-sessao-no-servidor` já especificada) |
| P08 | MÉDIO | A compra somava o estoque sobre o saldo do cache, sem a trava das vendas (podia apagar uma baixa simultânea), e quebrava com estoque vazio | `compras_state.finalizar_compra` | **corrigido** |
| P09 | MÉDIO | A OS baixa o estoque com `max(0, …)`: se faltar peça, o saldo vira 0 em silêncio e não usa a trava | `os_state.abrir_os` | pendente (decisão: recusar como nas vendas?) |
| P10 | MÉDIO | Excluir uma compra ou uma OS não estorna o estoque (na compra é proposital, comentado no código) | `compras_state`, `os_state` | pendente (decisão) |
| P11 | MÉDIO | `event_log` grava o registro inteiro do usuário em `metadata` (inclui o hash da senha e do código de reset) no cadastro e na troca de senha | Xano `log_event` | pendente (Xano) |
| P12 | MÉDIO | O espelho `xano/` está desatualizado: faltam a tabela `motos` e o grupo CRUD, e o Admin aparece sem login | `xano/` | pendente: baixar pela extensão do Xano |
| P13 | MÉDIO | Sem chaves estrangeiras no Xano e sem índice único conhecido em `motos.placa`/`chassi` (só no código) | Xano | mitigado no app (P06 e checagem de duplicidade) |
| P14 | BAIXO | Nomenclatura mista: `id_cliente` (tabelas antigas) e `cliente_id`/`transacao_id` (novas, convenção de `xano/knowledge/agents.md`) | Xano | aceito: renomear quebraria app e dados |
| P15 | BAIXO | Tipos: `data_cancelamento` é `date` (as outras datas são `timestamp`); `estoque_qtd` aceita vazio; tipos e status em texto livre | Xano | aceito |
| P16 | BAIXO | SQLite, Alembic e `models.py` legados (0 registros), e o README ainda manda rodar `reflex db init/migrate` | raiz | mantido (original; ainda fornece constantes) |
| P17 | BAIXO | Excluir um cliente referenciado por `motos.cliente_id` (moto da loja) não é bloqueado: relação criada depois do modelo original | `clientes_state` | pendente (decisão) |
| P18 | INFO | As telas leem tabelas inteiras e filtram em memória (cache de 5 min). Com cerca de 10 registros não há gargalo, e índices no Xano não mudam esse padrão | `xano_client` | revisar acima de alguns milhares |

Não existem no sistema (nada foi inventado): financeiro (contas a pagar e a
receber, parcelas), controle de ponto e presença, SKU ou código de produto,
departamentos, perfis e permissões (previstos na change `perfis-de-acesso`).

## 4. Alterações realizadas

| Arquivo | Alteração | Problema |
|---|---|---|
| `harley_store/estoque.py` | leitura do produto com token (`_request_xano`) | P01 |
| `harley_store/vendas_servico.py` | leitura direta com token | P01 |
| `harley_store/xano_admin_client.py` | as três chamadas com token | P05 |
| `harley_store/integridade.py` (novo) | dependências do modelo original e checagem antes de excluir | P06 |
| `state/clientes, fornecedores, funcionarios, produtos, motos_state.py` | `excluir` recusa com mensagem quando há registros ligados | P06 |
| `state/compras_state.py` | entrada no estoque por `estoque.movimentar` (trava e saldo real) | P08 |
| `scripts/auditoria_integridade.py` (novo) | verificação somente leitura: órfãos, duplicidades, estoque, vendas | §19 |
| `tests/test_xano_e_integridade.py` (novo) | 15 testes sem acesso ao Xano real | §18 |

**Tabelas, colunas, relacionamentos, índices e migrations alterados no banco:**
nenhum. Nada foi alterado no Xano nem no SQLite, e nenhuma migration foi
criada. As FKs do modelo original voltaram a valer na camada do app
(`integridade.DEPENDENCIAS`).

## 5. Alterações do n8n removidas e mantidas

**Removidas: nenhuma.** A remoção de `n8n/` e da seção do README foi bloqueada
pela permissão de ações destrutivas e aguarda a sua decisão. Os arquivos estão
preservados em `3bf70f1` e no branch `n8n/assistente-telegram`. Para remover:

```
git rm -r n8n
# e apagar a seção "Assistente de vendas no Telegram (n8n)" do README
```

**Mantidas:** as alterações da classe D (§2), porque o app depende delas desde
que o Xano passou a exigir login.

## 6. Testes

- **Automatizados** (`.venv\Scripts\python -m unittest discover -s tests -v`): 15 de 15 passaram.
  Cobrem token, renovação após 401, conta não configurada, leituras diretas,
  tela de usuários, movimentação de estoque (entrada, saldo vazio, baixa
  recusada sem alterar nada) e as regras de exclusão. Os 3 testes de
  regressão de P01 e P05 falham com o mesmo 401 quando rodados contra o código
  anterior: conferido.
- **Integridade dos dados reais** (`scripts\auditoria_integridade.py`, somente
  leitura): 0 problemas. Nenhum órfão em 14 referências, nenhuma duplicidade de
  CPF/CNPJ, placa ou chassi, nenhum estoque negativo, nenhuma venda ou compra
  inconsistente.
- **Não executado:** teste pelas telas do app (cadastros, venda, compra) e a
  produção. Esta ainda roda o código antigo e continua com o erro 401 até a
  publicação.

## 7. Riscos e pendências

1. **P02, P03 e P04 (segurança no Xano)** são o maior risco: juntos, permitem
   a qualquer pessoa ler os dados da loja ou tomar contas, inclusive a conta de
   serviço. Exigem mudar o Xano e o fluxo "Esqueci minha senha".
2. **Produção fora do ar** (401) até publicar uma versão com o login de serviço.
   O `.env` de `C:\HARLEY_PROD` precisa existir.
3. **P07** (sessão por cookie): implementar a change `validar-sessao-no-servidor`.
4. **Decisões de negócio** pendentes: P09, P10 e P17.
5. **P12**: baixar o espelho atualizado do Xano para o git.
6. **n8n**: decidir entre manter ou remover (§5).

## Como desfazer

- Desfazer as correções da auditoria: `git revert` do commit da auditoria.
- Voltar ao estado antes da auditoria: `git switch --detach 3bf70f1`.
- Código original antes do n8n: `main` (`b26972a`). Atenção: sem o login de
  serviço, ele recebe 401 do Xano atual.

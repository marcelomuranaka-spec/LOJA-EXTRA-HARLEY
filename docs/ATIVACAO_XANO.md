# Ativar os recursos novos no Xano

O sistema já tem todos os recursos novos prontos. Os que dependem de uma tabela
ou campo que ainda não existe no Xano **ligam sozinhos** quando você criar o que
falta no painel (o plano Free do Xano não deixa o sistema criar tabelas pela API).

Enquanto isso, tudo o que já existia continua funcionando igual.

A tela **Configuração do sistema** (menu Administração, só para administradores)
mostra a situação de cada item ao vivo. Depois de criar algo no Xano, clique em
**Verificar agora**.

## Regras para não perder dados

- Só **acrescentar**: campos novos (todos opcionais) e tabelas novas. Não renomeie
  nem apague campos existentes.
- Campo novo em tabela que já existe: inclua o campo também nos **inputs dos
  endpoints POST e PATCH** dessa tabela (e no "Add Record" / "Edit Record" do
  function stack). Sem isso o Xano ignora o valor sem avisar, e o sistema mostra
  "O Xano não gravou: ...".
- Tabela nova: gere o CRUD com **Add API Endpoint → CRUD Database Operations**, no
  mesmo grupo de API das tabelas da loja (a URL termina em `api:LtU_pM2N`), e
  deixe a autenticação ligada, igual às outras.
- Teste com um registro marcado "TESTE" e apague-o em seguida (desenvolvimento e
  produção usam o mesmo Xano).

## Ordem sugerida (do mais útil para o menos)

### 1. `clientes`: 5 campos novos

| Campo | Tipo | Para quê |
|---|---|---|
| `telegram` | text | @usuário ou número do Telegram |
| `cidade` | text | cidade |
| `observacoes` | text | observações |
| `status` | text | Lead, Cliente, Cliente recorrente ou Inativo (vazio = Cliente) |
| `created_at` | timestamp, padrão `now` | data de cadastro |

Libera a ficha completa, o filtro por status e por cidade e o botão do Telegram.

### 2. `motos_clientes`: 6 campos novos

| Campo | Tipo |
|---|---|
| `marca` | text |
| `ano` | integer |
| `cor` | text |
| `quilometragem` | integer |
| `observacoes` | text |
| `created_at` | timestamp, padrão `now` |

### 3. Endpoint `upload/image` (fotos)

API → grupo das tabelas da loja → Add API Endpoint → **POST** `upload/image` →
Inputs: **File Resource** chamado `content` → Function Stack: **Create Image from
File** (value = `content`, acesso public) → Response: a imagem criada → Publish.

Libera as fotos das motos da loja (inclusive fotos adicionais). Também faz as
fotos de produtos e de motos dos clientes ficarem no Xano. Hoje elas ficam na
pasta `uploaded_files` do computador onde foram enviadas, e uma foto enviada no
desenvolvimento não aparece na produção.

### 4. Tabela nova `categorias` + campos em `produtos`

`categorias`: `nome` (text), `ativo` (boolean), `created_at` (timestamp, padrão now).

`produtos`, campos novos:

| Campo | Tipo |
|---|---|
| `categoria_id` | integer |
| `sku` | text |
| `preco_custo` | decimal |
| `estoque_minimo` | integer |
| `ativo` | boolean |

Depois, em **Categorias**, clique em **Importar categorias dos produtos**. Isso
cria as categorias já usadas nos produtos, mais Peças, Acessórios, Capacetes,
Vestuário, Lubrificantes e Outros, e liga cada produto à sua. Rodar de novo não
duplica nada.

### 5. Tabela nova `formas_pagamento` + campos em `transacoes`

`formas_pagamento`: `nome` (text), `ativo` (boolean), `created_at`.

`transacoes`, campos novos:

| Campo | Tipo | Para quê |
|---|---|---|
| `desconto` | decimal | valor do desconto |
| `forma_pagamento` | text | forma de pagamento (guarda o nome) |
| `usuario_id` | integer | conta que registrou a venda |
| `moto_id` | integer | moto da loja vendida (0 = nenhuma) |

Com `moto_id`, cancelar a venda de uma moto devolve a moto ao estoque sozinho.
Na Configuração, o botão **Criar as formas mais comuns** preenche a tabela.

### 6. Tabelas novas `leads` e `interacoes`

`leads`: `nome`, `telefone`, `telegram`, `email`, `origem`, `interesse`,
`moto_interesse`, `observacao` e `status` (text); `moto_id`, `cliente_id` e
`usuario_id` (integer); `created_at` (timestamp, padrão now).

`interacoes`: `cliente_id`, `lead_id` e `usuario_id` (integer); `tipo` e
`descricao` (text); `created_at`.

### 7. Tabela nova `emails` + chave do SendGrid

`emails`: `destinatario`, `assunto`, `mensagem`, `status` e `erro` (text);
`cliente_id`, `lead_id` e `usuario_id` (integer); `created_at`.

SendGrid:
1. crie a conta e verifique o remetente (Sender Authentication);
2. gere uma API Key com permissão **Mail Send**;
3. acrescente ao `.env` do servidor (no desenvolvimento, `C:\TESTE_LOJA_HARLEY\.env`;
   na produção, `C:\HARLEY_PROD\.env`) e reinicie o sistema:

```
SENDGRID_API_KEY=SG.xxxxxxxx
SENDGRID_REMETENTE=contato@sualoja.com.br
SENDGRID_NOME_REMETENTE=Harley Store
```

A chave fica só no servidor: não vai para o navegador nem para o git. O sistema
nunca envia e-mail sozinho; todo envio parte de um clique ("Enviar e-mail" na
ficha do cliente ou do lead) e fica registrado na tela **E-mails**.

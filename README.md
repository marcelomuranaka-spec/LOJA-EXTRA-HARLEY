# Harley Store App

Aplicativo web para o dia a dia da loja/oficina, construído em [Reflex](https://reflex.dev)
(Python puro — sem precisar escrever HTML/JS) a partir da estrutura do banco
`HARLEY_DAVIDSON_STORE.sql` que você enviou.

Ele cobre as 10 tabelas do banco original: Fornecedores, Produtos, Funcionários,
Clientes, Motos dos Clientes, Entrada de Mercadoria (Compras), Itens de Compra,
Transações (Vendas), Ordens de Serviço e Itens de Ordem de Serviço.

## O que o app faz

- **Tela inicial** (`/`) — logo Harley-Davidson sobre fundo preto, com o
  botão **ENTRAR** que leva ao login (`/login`). Depois do login o usuário
  vai para o Painel (`/painel`). O logo fica em `assets/harley_logo.png`
  e as cores da marca em `harley_store/components/tema.py`.
- **Painel** (`/painel`) — visual Harley (preto + laranja): motos em
  estoque, valor do estoque de motos, motos vendidas no mês, faturamento
  de hoje/do mês, gráfico de faturamento dos últimos 12 meses, produtos,
  estoque baixo, clientes, OS em aberto e um extrato recente (igual à
  view `vw_resumo_operacoes` do script original, só que calculada em Python).
- **Motos da loja** (`/motos-loja`) — estoque de motos à venda, ligado à
  tabela `motos` do Xano: marca, modelo, ano, cor, placa, chassi, km,
  status (Em estoque / Reservada / Consignada / Vendida), preços de
  compra e venda, datas de entrada/saída, cliente, observações e foto.
- **Produtos** — catálogo e estoque, com aviso de estoque baixo (≤ 5 unidades).
- **Clientes** e **Motos dos clientes** — cadastro e vínculo cliente → moto.
- **Vendas / Balcão** — venda com **vários itens** (carrinho): produtos do
  estoque (preço já preenchido e editável, para descontos) e itens avulsos
  sem estoque (ex.: mão de obra). O estoque é baixado na hora, protegido
  contra vendas simultâneas do mesmo produto. Vendas **não são apagadas**:
  são **canceladas** (uma ou várias de uma vez, com motivo opcional),
  continuam no histórico como "Cancelada", saem do faturamento e devolvem
  os produtos ao estoque.
- **Ordens de serviço** — abre OS vinculada a uma moto e um mecânico, permite
  lançar peças usadas (que também baixam o estoque) e trocar o status
  (Aberta → Em andamento → Concluída/Cancelada).
- **Compras** — dá entrada de mercadoria de um fornecedor com vários itens
  de uma vez; cada item já soma no estoque do produto correspondente.
- **Fornecedores** e **Funcionários** — cadastros de apoio.
- **Impressão de documentos** — botão **Imprimir** em Vendas, Ordens de
  serviço, Compras e Motos da loja. Abre em nova aba uma folha A4
  (comprovante de venda, ordem de serviço, entrada de mercadoria, recibo de
  compra e venda ou ficha da moto) com cliente/fornecedor, itens, total e
  assinaturas; imprime ou salva em PDF pelo navegador.

### Desempenho

O servidor guarda as tabelas do Xano em cache (5 min) e as mantém
atualizadas em segundo plano (1 consulta a cada 20 s), então as telas abrem
em cerca de 0,1–0,9 s e o limite de requisições do plano Free do Xano não é
atingido. Toda gravação feita pelo app limpa o cache da tabela na hora; uma
alteração feita direto no painel do Xano aparece no app em até 5 minutos.

## Como rodar (no VSCode)

Pré-requisitos: **Python 3.11, 3.12 ou 3.13** instalado (⚠️ **não use Python
3.14** — o Reflex ainda não é compatível com ele; a instalação quebra com
`ImportError: cannot import name 'Discriminator' from 'pydantic.v1'` ou
`RuntimeError: generator didn't stop after throw()`, ver
[reflex-dev/reflex#5964](https://github.com/reflex-dev/reflex/issues/5964)),
e a extensão **Python** do VSCode (o Reflex também baixa sozinho, na primeira
execução, um runtime Node.js/Bun próprio para compilar a interface — você
não precisa instalar Node manualmente).

Para conferir quais versões de Python você tem instaladas no Windows, rode
`py -0` no terminal. Se só aparecer a 3.14, baixe o instalador do Python 3.12
em python.org, marque "Add python.exe to PATH" na instalação, e use `py
-3.12` no lugar de `python` nos comandos abaixo.

1. Abra esta pasta (`harley_store`) no VSCode: `Arquivo → Abrir Pasta...`.
2. Abra um terminal no VSCode (`Terminal → Novo Terminal`) e crie um ambiente
   virtual **com uma versão suportada do Python**:

   ```bash
   # Windows (troque -3.12 por -3.11 ou -3.13 se for a versão que você tem):
   py -3.12 -m venv .venv
   .venv\Scripts\activate
   # macOS/Linux:
   python3.12 -m venv .venv
   source .venv/bin/activate
   ```

3. Instale as dependências:

   ```bash
   pip install -r requirements.txt
   ```

4. Inicialize o Reflex (só na primeira vez — baixa os pacotes do frontend):

   ```bash
   reflex init
   ```

5. Crie o banco local (arquivo `harley_store.db`, criado automaticamente
   pelo Reflex a partir dos modelos em `harley_store/models.py`):

   ```bash
   reflex db init
   reflex db migrate
   ```

6. Configure a conta que o servidor usa para acessar o Xano. Os endpoints
   das tabelas exigem login (sem ele toda tela falha com `401
   Unauthorized`). Crie o arquivo `.env` na raiz do projeto, fora do git,
   com o email e a senha de um usuário do app (tabela `user` do Xano):

   ```
   XANO_EMAIL=conta.do.sistema@exemplo.com
   XANO_SENHA=...
   ```

   A pasta da produção (`C:\HARLEY_PROD`) precisa do **seu próprio** `.env`,
   porque ele não vai junto na publicação.

7. Rode o app de **desenvolvimento** e acesse **http://localhost:3001**:

   ```powershell
   .\scripts\iniciar_dev.ps1
   ```

   O sistema que os funcionários usam é a **produção**, que roda sozinha;
   veja a seção abaixo.

## Produção e desenvolvimento (rede da loja)

O mesmo notebook roda dois ambientes, em pastas separadas:

| | Produção (funcionários) | Desenvolvimento |
|---|---|---|
| Endereço | **http://192.168.0.54:3000**, em qualquer aparelho da rede da loja | http://localhost:3001, só neste notebook |
| Pasta | `C:\HARLEY_PROD` (clone git, **não edite arquivos lá**) | `C:\TESTE_LOJA_HARLEY` |
| Portas | 3000 (tela) / 8000 (backend), liberadas no firewall só na rede Privada | 3001 / 8001, fechadas para a rede |
| Como sobe | sozinha quando o notebook liga (tarefa agendada `HarleyStore-Producao`) | `.\scripts\iniciar_dev.ps1` |
| Modo | `prod`: estável, não recarrega ao editar código | `dev`: recarrega a cada arquivo salvo |

O IP da produção fica em `C:\HARLEY_PROD\producao.local.ps1`, fora do git.
Ele deve ser o IP **reservado no roteador** para o Wi-Fi deste notebook
(adaptador `ec:0e:c4:f6:76:0d`). Se mudar, edite esse arquivo e rode
`.\scripts\atualizar_producao.ps1`.

### Levar uma alteração para a produção

1. Teste no desenvolvimento e faça o commit (`git add -A` e `git commit -m "..."`).
2. Rode `.\scripts\publicar.ps1`. Ele recusa se houver algo sem commit,
   cria a tag `prod-AAAAMMDD-HHMM`, envia ao GitHub e reinicia a produção
   nessa versão. Os funcionários ficam cerca de 1 minuto sem o sistema,
   enquanto ele recompila.

### Voltar para a versão anterior

```powershell
git tag --list "prod-*"                                # versões publicadas
.\scripts\atualizar_producao.ps1 -Tag prod-AAAAMMDD-HHMM
```

### Parar a produção

`.\scripts\parar_producao.ps1`. **Não** use "Encerrar" no Agendador de
Tarefas: isso deixa processos órfãos segurando as portas 3000/8000, que só
somem reiniciando o notebook.

Os registros ficam em `C:\HARLEY_PROD\logs\` (`producao-*.log` = saída do
sistema; `supervisor-*.log` = início e parada).

### Configuração do Windows (já aplicada)

`scripts\configurar_windows.ps1` (como administrador) deixa o notebook
pronto para servir durante o expediente: rede como Privada, nunca
suspender na tomada, tampa fechada não suspende, horário ativo do Windows
Update das 7h às 19h (reinícios automáticos só à noite), firewall e a
tarefa de início automático. Pode ser executado de novo sem duplicar nada.

### ⚠️ Os dois ambientes usam o MESMO banco Xano

Não existe um banco "de teste": o que se faz no desenvolvimento altera os
dados reais da loja. Teste só com registros claramente marcados como teste
(por exemplo, com "TESTE" no nome) e apague-os em seguida. Não faça testes
de estoque em produtos reais.

Na primeira vez que abrir, todas as listas estarão vazias. Cadastre nesta
ordem, porque uma tela depende da outra (é a mesma ordem de dependência das
chaves estrangeiras do banco original):

`Funcionários` e `Fornecedores` → `Produtos` → `Clientes` → `Motos dos clientes`
→ aí sim `Vendas`, `Ordens de serviço` e `Compras`.

## Assistente de vendas no Telegram (n8n)

O bot roda no n8n do Docker Desktop (pasta `n8n/`). Ele usa o Claude para
responder, consulta as motos à venda no Xano e grava os leads na Data Table
`leads_telegram` do n8n (ela é criada sozinha no primeiro lead).

- **Configurar (uma vez):** `.\n8n\configurar_bot.ps1`. O script pede o token
  do bot (@BotFather), a chave da API da Anthropic e a conta do Xano, e testa
  cada um. Depois importa os workflows, grava as credenciais no n8n, publica o
  bot, grava a conta do Xano no `.env` do app (desenvolvimento e produção) e
  cria a tarefa `HarleyStore-n8n`. Rode de novo para trocar alguma chave ou
  depois de reinstalar o Docker.
- **Iniciar:** `.\n8n\iniciar_n8n.ps1` (editor em http://localhost:5678).
  A tarefa `HarleyStore-n8n` roda esse script sozinha ao entrar no Windows,
  e ele abre o Docker Desktop se precisar. O Telegram só entrega mensagens
  num endereço HTTPS público. Por isso o script abre um túnel gratuito da
  Cloudflare, cujo endereço muda a cada início, e passa esse endereço ao n8n.
  Log da tarefa: `logs\n8n-inicio.log`.
- **Dados:** ficam no volume Docker `n8n_data`, então recriar ou atualizar
  o container não apaga nada. Mas o volume some se o Docker Desktop for
  reinstalado ou voltar ao padrão de fábrica. A imagem é a
  `n8nio/n8n:v3-rc-20260928` (prévia "nightly"): o n8n não volta a uma versão
  anterior depois de atualizar o banco.
- **Workflows:** `n8n/workflows/` tem as cópias versionadas do bot
  (`assistente_telegram`) e das ferramentas dele (`consultar_motos` e
  `salvar_lead`).
- A consulta de motos mostra só as motos com situação *Em estoque* ou
  *Consignada*, sem preço de compra, placa, chassi nem observações internas.

## Estrutura do projeto (para você mexer)

```
harley_store/
├── rxconfig.py              ← configuração do app e do banco de dados
└── harley_store/
    ├── harley_store.py      ← ponto de entrada: registra as páginas/rotas
    ├── models.py            ← as 10 tabelas (comece por aqui para alterar a estrutura)
    ├── components/
    │   └── layout.py        ← menu lateral + moldura comum das páginas
    ├── state/                ← um arquivo por tela: dados + regras de negócio
    │   ├── fornecedores_state.py   ← CRUD mais simples (comece por aqui pra copiar)
    │   ├── produtos_state.py
    │   ├── ...
    └── pages/                ← um arquivo por tela: só a parte visual
        ├── fornecedores.py
        ├── produtos.py
        ├── ...
```

Cada tela é **sempre** o par `state/algo_state.py` + `pages/algo.py`. O
`state` guarda os dados carregados do banco e os métodos que salvam,
editam e excluem; a `page` só desenha a tela e chama os métodos do state
quando o usuário clica em algo. Separar assim é o que deixa fácil mexer
numa tela sem quebrar as outras.

### Como alterar a estrutura do banco (adicionar/mudar uma tabela)

1. Edite (ou adicione) a classe correspondente em `harley_store/models.py`
   — tem um passo a passo comentado bem no topo desse arquivo.
2. Gere e aplique a migração (isso preserva os dados que já existem):

   ```bash
   reflex db makemigrations --message "descreva o que mudou"
   reflex db migrate
   ```

3. Se for uma tabela nova, copie um `state/*.py` e um `pages/*.py`
   parecidos (o de `Fornecedores` é o mais simples; o de `Compras` mostra
   o padrão de "cabeçalho + itens", usado também em Ordens de Serviço).
4. Registre a rota nova em `harley_store/harley_store.py`
   (`app.add_page(...)`) e o link no menu em
   `harley_store/components/layout.py` (lista `MENU_ITEMS`).

### Como conectar no SQL Server (banco original) em vez do SQLite local

Por padrão o app usa um arquivo local `harley_store.db` (SQLite), pensado
para rodar direto no computador da loja sem precisar instalar nada além do
Python. Se preferir usar o SQL Server do script original:

1. `pip install pyodbc` (já vem comentado no `requirements.txt`).
2. Em `rxconfig.py`, troque o `db_url` por algo como:

   ```python
   db_url="mssql+pyodbc://usuario:senha@servidor/HarleyDavidsonStore?driver=ODBC+Driver+17+for+SQL+Server"
   ```

3. Rode `reflex db migrate` de novo para o Reflex criar/ajustar as tabelas
   nesse banco.

### Vendas antigas (antes do registro de itens)

Vendas registradas antes de existirem os itens (tabela `itens_transacao`)
guardam só o valor total. Elas continuam aparecendo e podem ser canceladas,
mas nesse caso nada volta ao estoque automaticamente, porque não se sabe o
que foi vendido; o sistema avisa para conferir o estoque manualmente.

## Esqueci minha senha

Na tela de login, **Esqueci minha senha** pede só o email cadastrado, a
nova senha e a repetição dela. Não há email de confirmação: o servidor do
app chama em sequência os endpoints `reset/request-code` e
`reset/confirm-code` que já existem no Xano (ver
`xano_auth_client.redefinir_senha`). O código de uso único nunca chega ao
navegador.

> ⚠️ Sem confirmação por email, **quem souber o email de uma conta pode
> trocar a senha dela**. Serve para uso interno na loja; se o app ficar
> acessível pela internet, vale voltar a exigir um código enviado por email.

## Spinner de carregamento nos botões

Qualquer botão que dispare uma ação no servidor mostra um círculo girando
até a ação terminar. Se o botão some da tela (diálogo que fecha, troca de
página), aparece um spinner laranja no centro. Funciona em todas as telas,
inclusive nas futuras, sem mexer em nenhuma delas: `assets/carregando.js`
observa as mensagens do websocket do Reflex, e o visual fica em
`assets/carregando.css`.

## Fotos das motos da loja (endpoint `upload/image` no Xano)

O campo `foto` da tabela `motos` é um campo de **imagem do Xano**. Mandar
o arquivo direto no POST/PATCH da tabela não funciona (o Xano grava só o
nome, sem a imagem), então o app envia a foto antes para um endpoint de
upload. Enquanto ele não existir, a tela avisa e a moto pode ser salva
sem foto. As fotos já cadastradas no Xano continuam aparecendo e são
mantidas ao editar. Para liberar o envio:

1. No Xano, abra o grupo de API onde estão os CRUDs das tabelas (a URL
   base termina em `api:LtU_pM2N`).
2. **Add API Endpoint** → método **POST**, caminho `upload/image`.
3. Em **Inputs**, adicione um campo do tipo **File Resource** chamado
   `content`.
4. Em **Function Stack**, adicione **Create Image from File** (grupo
   Storage) com *value* = `content` e acesso **public**; guarde a saída
   numa variável (ex.: `image`).
5. Em **Response**, devolva a variável `image` e publique.

> Cuidado ao mexer na tabela `motos` por fora do app: o PATCH do Xano
> **substitui o registro inteiro** (campo não enviado volta vazio).

## OpenSpec

O projeto está inicializado com o [OpenSpec](https://github.com/Fission-AI/OpenSpec)
(pasta `openspec/`, contexto do projeto em `openspec/config.yaml`) e os
comandos do Claude Code em `.claude/`. Para propor uma mudança nova:
`/opsx:propose "sua ideia"`. Conferir a instalação: `openspec --version`.

## Backup

O banco inteiro da loja fica no arquivo `harley_store.db`, na pasta do
projeto. Copie esse arquivo para outro lugar (um pen drive, um serviço de
nuvem) periodicamente — ele **não** sobe para o Git (está no
`.gitignore`) de propósito, exatamente para não misturar dados reais da
loja com o código-fonte.
# LOJA-EXTRA-HARLEY

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
  RENAVAM, cilindrada, localização, situação (Em estoque, Em preparação,
  Em manutenção, Reservada, Consignada, Indisponível, Vendida), preços de
  compra e venda, datas de entrada/saída, cliente, observações e fotos
  (principal + até 8 adicionais, com galeria ampliada). Só
  "Vendida" tira a moto do estoque, e ela exige o cliente comprador.
- **Produtos** — catálogo e estoque, com aviso de estoque baixo (≤ 5
  unidades), busca, filtro por categoria e categorias sugeridas
  (Motocicletas, Peças, Vestuário, Consumíveis, Acessórios, Motores,
  Pneus, Lubrificantes, Outros). Uma categoria nova é só digitada: não
  precisa mudar código.
- **Clientes** e **Motos dos clientes** — cadastro e vínculo cliente → moto.
- **Vendas / Balcão** — venda com **vários itens** (carrinho): produtos do
  estoque (preço já preenchido e editável, para descontos) e itens avulsos
  sem estoque (ex.: mão de obra). O estoque é baixado na hora, protegido
  contra vendas simultâneas do mesmo produto. Vendas **não são apagadas**:
  são **canceladas** (uma ou várias de uma vez, com motivo opcional),
  continuam no histórico como "Cancelada", saem do faturamento e devolvem
  os produtos ao estoque.
- **Ordens de serviço** — abre OS vinculada a uma moto e um mecânico, permite
  lançar peças usadas (que também baixam o estoque) e serviços / mão de
  obra (descrição e valor, sem estoque), e trocar o status
  (Aberta → Em andamento → Concluída/Cancelada). Excluir uma OS devolve
  as peças ao estoque.
- **Compras** — dá entrada de mercadoria de um fornecedor com vários itens
  de uma vez; cada item já soma no estoque do produto correspondente.
  Excluir uma compra retira do estoque o que ela somou (e é recusado se
  esses produtos já foram vendidos).
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

6. Rode o app de **desenvolvimento** e acesse **http://localhost:3001**:

   ```powershell
   .\scripts\iniciar_dev.ps1
   ```

   O sistema que os funcionários usam é a **produção**, que roda sozinha;
   veja a seção abaixo.

## Produção e desenvolvimento (rede da loja)

O mesmo notebook roda dois ambientes, em pastas separadas:

| | Produção (funcionários) | Desenvolvimento |
|---|---|---|
| Endereço | **http://192.168.0.12:3000**, em qualquer aparelho da rede da loja | http://localhost:3001, só neste notebook |
| Pasta | `C:\HARLEY_PROD` (clone git, **não edite arquivos lá**) | `C:\LOJA-EXTRA-HARLEY` |
| Portas | 3000 (tela) / 8000 (backend), liberadas no firewall só na rede Privada | 3001 / 8001, fechadas para a rede |
| Como sobe | sozinha quando o notebook liga (tarefa agendada `HarleyStore-Producao`) | `.\scripts\iniciar_dev.ps1` |
| Modo | `prod`: estável, não recarrega ao editar código | `dev`: recarrega a cada arquivo salvo |

O IP da produção fica em `C:\HARLEY_PROD\producao.local.ps1`, fora do git.
O Wi-Fi deste notebook (adaptador `4C-5F-70-A2-40-1D`, rede `SIDLAR_2G`)
está com **IP fixo 192.168.0.12**, configurado no Windows por
`scripts\ip_do_servidor.ps1` (como administrador). Com IP fixo o notebook
não conecta direito em outras redes: para usá-lo fora da loja, rode
`.\scripts\ip_do_servidor.ps1 -Automatico`, e `-Fixo` ao voltar. Se o IP
mudar, edite `producao.local.ps1` e rode `.\scriptstualizar_producao.ps1`.
(O ideal, quando houver a senha do modem Claro, é trocar o IP fixo por uma
reserva de DHCP no modem.)

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

## Regras de integridade (estoque, cadastros e sessão)

- **Estoque:** toda alteração de saldo (venda, cancelamento, peças de OS,
  compras, exclusão de OS/compra e edição do cadastro de produto) passa por
  `harley_store/estoque.py`, com trava por produto e releitura do Xano. O
  saldo nunca fica negativo, nenhuma movimentação simultânea se perde e,
  se uma gravação falhar no meio, o que já foi feito é desfeito. Na edição
  de um produto, vale a **variação** digitada: se houve uma venda enquanto
  o formulário estava aberto, ela é preservada.
- **Exclusões:** um cadastro usado em outro lugar não pode ser excluído
  (cliente com motos ou vendas, produto usado em vendas/OS/compras,
  funcionário com vendas/OS, fornecedor com compras, moto com OS). As
  ligações ficam em `harley_store/dependencias.py`.
- **Validações no servidor** (`harley_store/validacao.py`): CPF/CNPJ com
  dígitos verificadores (gravados sempre formatados, e a duplicidade é
  conferida pelos números), e-mail, telefone com DDD, placa (antiga ou
  Mercosul), chassi, valores e quantidades. Fotos são conferidas pelo
  conteúdo, não só pela extensão (máximo 5 MB).
- **Sessão:** o login é conferido no Xano (`auth/me`), não basta existir
  o cookie; ele vence em 24 h, junto com o token. Toda ação das telas é
  barrada no servidor para quem não tem sessão válida
  (`harley_store/sessao.py`), inclusive eventos mandados direto pelo
  websocket. Um state novo precisa entrar na lista do
  `ExigeSessaoMiddleware` em `harley_store/harley_store.py`.
- **Erros:** falhas inesperadas aparecem ao funcionário como uma mensagem
  clara em português; os detalhes vão para o log (na produção,
  `logs\producao-*.log`), sem senhas nem tokens.

## Testes automáticos

Rodam sem internet e sem tocar no Xano (o estoque é testado com um Xano
simulado, incluindo vendas simultâneas):

```powershell
.venv\Scripts\python.exe -m unittest discover -s tests -t . -v
```

## Contas, perfis e senhas

- Não existe cadastro público: só um **administrador** cria contas, na tela
  **Usuários do sistema** (que só aparece para administradores). Lá ele
  também troca o e-mail, define uma nova senha, muda o perfil
  (Administrador / Funcionário) e exclui contas.
- **Esqueci minha senha:** a pessoa pede a um administrador, que define
  uma nova senha para ela. (Antes, qualquer um trocava a senha de qualquer
  conta sabendo só o e-mail.)
- O Xano confere o perfil em toda operação de administração; um
  funcionário comum recebe "sem permissão" mesmo chamando a API direto.
- Ninguém altera o próprio perfil nem exclui a própria conta, então sempre
  sobra ao menos um administrador.

## Segurança da API do Xano e conta de serviço

Todos os endpoints de dados do Xano exigem login. O **servidor** do app
acessa os dados com uma **conta de serviço** própria ("Sistema Harley
Store"), cujas credenciais ficam no arquivo `.env` da pasta de cada
ambiente (desenvolvimento e `C:\HARLEY_PROD`), **fora do git**:

```
HARLEY_XANO_EMAIL=...
HARLEY_XANO_SENHA=...
```

Sem esse arquivo o app não consegue ler nem gravar nada (o log mostra
`HARLEY_XANO_EMAIL/HARLEY_XANO_SENHA ausentes`). Numa instalação nova,
copie o `.env` de uma pasta existente. **Não exclua** a conta "Sistema
Harley Store" na tela de usuários.

As definições do Xano (tabelas e endpoints) ficam espelhadas na pasta
`xano\`. Para aplicar mudanças feitas nela:

```powershell
.\scripts\aplicar_xano.ps1 -SoPrevia   # mostra o que mudaria
.\scripts\aplicar_xano.ps1             # mostra e pede confirmação
```

`-Reverter` volta os endpoints ao estado de antes da auditoria de
24/09/2026 (API aberta), só para emergência.

## Spinner de carregamento nos botões

Qualquer botão que dispare uma ação no servidor mostra um círculo girando
até a ação terminar. Se o botão some da tela (diálogo que fecha, troca de
página), aparece um spinner laranja no centro. Funciona em todas as telas,
inclusive nas futuras, sem mexer em nenhuma delas: `assets/carregando.js`
observa as mensagens do websocket do Reflex, e o visual fica em
`assets/carregando.css`.

## Fotos

- Todas as fotos (motos da loja, produtos e motos de clientes) vão para o
  armazenamento do Xano pelo endpoint `POST motos/foto` (campo `arquivo`),
  então aparecem igual na produção e no desenvolvimento. Fotos antigas de
  produtos/motos de clientes, guardadas em `uploaded_files/`, continuam
  aparecendo.
- Motos da loja: uma foto principal e até 8 adicionais; qualquer adicional
  pode virar a principal. O botão de ampliar no cartão abre a galeria.
- Aceitos: PNG, JPG e WEBP (produtos e motos de clientes também GIF), até
  5 MB; o conteúdo do arquivo é conferido, não só a extensão.
- Ao excluir uma moto, a foto continua guardada no Xano (o plano não
  oferece exclusão de arquivo pela API); isso não aparece para ninguém.

## Histórico de estoque

Cada entrada e saída (venda, cancelamento, peça em OS, compra, exclusões,
cadastro e ajuste manual) é registrada na tabela `movimentacoes_estoque`
com data, quantidade, saldo depois da operação, documento de origem e
usuário. Em **Produtos**, o botão **Histórico** mostra as movimentações de
cada produto.

## OpenSpec

O projeto está inicializado com o [OpenSpec](https://github.com/Fission-AI/OpenSpec)
(pasta `openspec/`, contexto do projeto em `openspec/config.yaml`) e os
comandos do Claude Code em `.claude/`. Para propor uma mudança nova:
`/opsx:propose "sua ideia"`. Conferir a instalação: `openspec --version`.

## Backup

Os dados da loja (clientes, produtos, vendas, OS, motos, usuários) ficam
no **Xano**, não neste computador. Para ter uma cópia, exporte as tabelas
pelo painel do Xano (Database → cada tabela → Export CSV) periodicamente e
guarde os arquivos fora do notebook (pen drive ou nuvem).

O arquivo `harley_store.db` (SQLite) e os `models.py`/`alembic/` são do
início do projeto, antes da mudança para o Xano: o app não grava mais
neles. As fotos de **produtos** e de **motos de clientes** ficam em
`uploaded_files/` na pasta de cada ambiente (na produção,
`C:\HARLEY_PROD\uploaded_files`); copie essa pasta junto com o backup.
# LOJA-EXTRA-HARLEY

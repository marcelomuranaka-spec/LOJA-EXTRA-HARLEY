# Tasks

Legenda: **[você]** = feito pelo usuário, ou com autorização explícita dele, porque exige o roteador ou privilégio de administrador do Windows.

## 1. Pré-requisitos do ambiente

- [x] 1.1 [você] Instalar o Git for Windows e configurar `user.name` e `user.email`; verificar com `git --version` e `git config --list` (Git 2.55.0 e GitHub CLI 2.101.0 instalados; autor configurado no repositório como `marcelomuranaka-spec`)
- [ ] 1.2 [você] Mudar a rede "Sidlar" para o perfil Privado; verificar que `Get-NetConnectionProfile` mostra `NetworkCategory: Private`
- [ ] 1.3 [você] Configurar "nunca suspender" na tomada, mantendo 10 min na bateria; verificar com `powercfg /query SCHEME_CURRENT SUB_SLEEP STANDBYIDLE` (índice AC `0x00000000`)
- [ ] 1.4 [você] Configurar "fechar a tampa: não fazer nada" na tomada; verificar com `powercfg /query SCHEME_CURRENT SUB_BUTTONS LIDACTION` (índice AC `0x00000000`)
- [ ] 1.5 [você] Definir o horário ativo do Windows Update das 7h às 19h; verificar em Configurações > Windows Update > Opções avançadas
- [ ] 1.6 [você] Criar no roteador a reserva de IP para o adaptador `ec:0e:c4:f6:76:0d` e confirmar que "endereços de hardware aleatórios" está desligado para a rede "Sidlar"; verificar que o IP permanece o mesmo após desconectar e reconectar o Wi-Fi, e anotar o IP reservado

## 2. Versionamento

- [x] 2.1 Revisar o `.gitignore` (acrescentar `.states/`, `logs/` e `producao.local.ps1`); verificar que `git status`, após o init, não lista `.venv`, `.web`, `*.db`, `uploaded_files` nem `.states`
- [x] 2.2 Executar `git init` em `C:\TESTE_LOJA_HARLEY` e fazer o commit inicial do estado atual; verificar com `git log --oneline` (1 commit) e `git status` limpo
- [x] 2.3 Enviar o repositório ao GitHub privado `marcelomuranaka-spec/LOJA-EXTRA-HARLEY` (remoto `origin`); verificar que o commit local e o remoto são iguais (`git ls-remote origin`) e que o repositório responde 404 sem login (privado)

## 3. Scripts de operação

- [x] 3.1 Criar `scripts/iniciar_dev.ps1` (portas 3001/8001, backend em 127.0.0.1, `REFLEX_API_URL=http://localhost:8001`, `--env dev`); verificar que o app abre em `http://localhost:3001` e que o login funciona
- [x] 3.2 Criar `scripts/iniciar_producao.ps1`, que lê `producao.local.ps1`, define `REFLEX_API_URL`/`REFLEX_FRONTEND_PORT`/`REFLEX_BACKEND_PORT`, roda `reflex run --env prod` e grava a saída em `logs/`; verificar que ele falha com mensagem clara se `producao.local.ps1` não existir
- [ ] 3.3 Criar `scripts/parar_producao.ps1`, que encerra todos os processos (incluindo os filhos) cuja linha de comando pertence à pasta de produção; verificar que depois dele as portas 3000 e 8000 ficam livres (`Get-NetTCPConnection`)
- [ ] 3.4 Criar `scripts/atualizar_producao.ps1 [-Tag]` (parar → fetch → checkout da tag → `pip install -r requirements.txt` → iniciar pela tarefa agendada), recusando-se a rodar se houver alterações locais na produção; verificar a recusa com um arquivo alterado de propósito
- [ ] 3.5 Criar `scripts/publicar.ps1`, que recusa rodar com alterações não commitadas, cria a tag `prod-AAAAMMDD-HHMM` e chama a atualização; verificar a recusa com uma alteração pendente
- [x] 3.6 Adicionar ao `rxconfig.py` um comentário indicando que endereço e portas vêm dos scripts (`REFLEX_*`); verificar que `scripts/iniciar_dev.ps1` continua funcionando; commit dos scripts

## 4. Ambiente de produção

- [x] 4.1 Clonar o repositório para `C:\HARLEY_PROD`, criar o `.venv` com Python 3.12 e instalar `requirements.txt`; verificar com `.venv\Scripts\reflex.exe --version` (0.7.14)
- [x] 4.2 Criar `C:\HARLEY_PROD\producao.local.ps1` com o IP reservado da tarefa 1.6; verificar que `git status` na produção não o lista
- [ ] 4.3 Executar `scripts/publicar.ps1` para a primeira versão; verificar que a produção está na tag criada (`git describe --tags`) e que `http://<IP reservado>:3000` abre no próprio notebook
- [ ] 4.4 [você] Criar a regra de firewall de entrada para TCP 3000 e 8000, somente no perfil Privado; verificar com `Get-NetFirewallRule` e `Get-NetFirewallPortFilter`
- [ ] 4.5 [você] Criar a tarefa `HarleyStore-Producao` no Agendador (gatilho na inicialização, sem exigir logon, S4U, reiniciar se falhar 3x a cada 1 min, sem limite de tempo); verificar com `Start-ScheduledTask` que a produção sobe, e com `Get-ScheduledTaskInfo` que o último resultado é bem-sucedido. Se o S4U falhar, trocar para "armazenar senha" (design D6)

## 5. Verificação integrada

- [ ] 5.1 De outro computador ou celular na rede da loja, abrir `http://<IP reservado>:3000`, entrar e navegar por Vendas, Clientes e Produtos sem erro de conexão (spec: Acesso pelos aparelhos da rede interna)
- [ ] 5.2 Com a produção em execução, rodar `scripts/iniciar_dev.ps1`, editar um arquivo e confirmar que a sessão aberta no outro aparelho continua funcionando sem desconectar (spec: Produção isolada do desenvolvimento)
- [ ] 5.3 Do outro aparelho, tentar abrir `http://<IP reservado>:3001` e confirmar que a conexão é recusada (spec: Exposição restrita à rede privada)
- [ ] 5.4 Reiniciar o notebook sem entrar na conta, esperar a inicialização e confirmar, pelo outro aparelho, que o sistema volta sozinho; anotar o tempo de subida (spec: Retorno automático após reinício)
- [ ] 5.5 Deixar o notebook na tomada, com a tampa fechada, sem uso por 20 minutos, e confirmar pelo outro aparelho que o sistema continua respondendo (spec: Disponibilidade durante o expediente)
- [ ] 5.6 Publicar uma alteração trivial e depois voltar à tag anterior com `atualizar_producao.ps1 -Tag <anterior>`; confirmar que a produção reflete cada versão (spec: Atualização controlada da produção)

## 6. Documentação

- [ ] 6.1 Atualizar o README: remover "deixe o terminal aberto" e documentar os dois ambientes (endereços e portas), os scripts, o roteiro de publicação e rollback, a regra de testes com o Xano compartilhado e o tempo de subida medido em 5.4; verificar que os comandos citados no README existem em `scripts/`

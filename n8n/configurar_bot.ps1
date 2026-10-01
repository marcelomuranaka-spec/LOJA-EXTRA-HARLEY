<#
  Configura o assistente de vendas do Telegram no n8n. Rode uma vez (ou de
  novo para trocar alguma chave, ou depois de reinstalar o Docker/n8n).

  1. Pede o token do bot do Telegram, a chave da API da Anthropic e a conta
     do Xano (as senhas nao aparecem na tela) e testa cada uma.
  2. Sobe o n8n com o tunel (iniciar_n8n.ps1), importa os workflows de
     n8n\workflows e grava as credenciais no n8n.
  3. Publica o bot e confere se o Telegram ja aponta para o n8n.
  4. Grava a conta do Xano no .env do app (desenvolvimento e producao).
  5. Cria a tarefa "HarleyStore-n8n", que roda iniciar_n8n.ps1 ao entrar no
     Windows (o endereco do tunel muda a cada inicio).

  Nenhuma chave vai para o git: ficam so nas credenciais do n8n e no .env.

  Uso:  .\n8n\configurar_bot.ps1
#>
$ErrorActionPreference = 'Continue'
function Falhar($texto) { Write-Host "ERRO: $texto" -ForegroundColor Red; exit 1 }
function Ok($texto) { Write-Host "  ok: $texto" -ForegroundColor Green }
function Ler-Segredo($pergunta) {
    $seguro = Read-Host $pergunta -AsSecureString
    $ptr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($seguro)
    try { return [Runtime.InteropServices.Marshal]::PtrToStringBSTR($ptr).Trim() }
    finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ptr) }
}
function Mensagem-Erro($erro) {
    if ($erro.ErrorDetails -and $erro.ErrorDetails.Message) { return $erro.ErrorDetails.Message }
    return $erro.Exception.Message
}
function Corpo-Json($objeto) { [Text.Encoding]::UTF8.GetBytes(($objeto | ConvertTo-Json -Compress -Depth 5)) }

[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
$raiz = Split-Path $PSScriptRoot -Parent
$xanoAuth = 'https://x8ki-letl-twmt.n7.xano.io/api:lH_WsSPl'
$xanoApi = 'https://x8ki-letl-twmt.n7.xano.io/api:LtU_pM2N'
$modelo = 'claude-sonnet-5'

# ---------------------------------------------------------------- 1. chaves
Write-Host "`n1/5 Telegram" -ForegroundColor Cyan
$tokenTelegram = Ler-Segredo 'Token do bot (o @BotFather mostra ao criar o bot)'
try { $bot = Invoke-RestMethod "https://api.telegram.org/bot$tokenTelegram/getMe" }
catch { Falhar 'o Telegram recusou esse token.' }
Ok "bot @$($bot.result.username)"

Write-Host "`n2/5 Anthropic (Claude)" -ForegroundColor Cyan
$chaveClaude = Ler-Segredo 'Chave da API (sk-ant-..., em console.anthropic.com > API Keys)'
try {
    Invoke-RestMethod -Method Post 'https://api.anthropic.com/v1/messages' -ContentType 'application/json' `
        -Headers @{ 'x-api-key' = $chaveClaude; 'anthropic-version' = '2023-06-01' } `
        -Body (Corpo-Json @{ model = $modelo; max_tokens = 5; messages = @(@{ role = 'user'; content = 'Responda ok' }) }) | Out-Null
} catch { Falhar ("a Anthropic recusou: " + (Mensagem-Erro $_)) }
Ok "chave aceita, modelo $modelo respondeu"

Write-Host "`n3/5 Xano (usuario do app que o bot e o app vao usar)" -ForegroundColor Cyan
$emailXano = (Read-Host 'Email da conta').Trim()
$senhaXano = Ler-Segredo 'Senha da conta'
try {
    $login = Invoke-RestMethod -Method Post "$xanoAuth/auth/login" -ContentType 'application/json' `
        -Body (Corpo-Json @{ email = $emailXano; password = $senhaXano })
} catch { Falhar 'o Xano recusou esse email ou senha.' }
try { $motos = @(Invoke-RestMethod "$xanoApi/motos" -Headers @{ Authorization = "Bearer $($login.authToken)" }) }
catch { Falhar ("login aceito, mas o Xano recusou a consulta de motos: " + (Mensagem-Erro $_)) }
Ok "login aceito, $($motos.Count) motos cadastradas"

# ---------------------------------------------------------------- 2. n8n
Write-Host "`n4/5 n8n" -ForegroundColor Cyan
& (Join-Path $PSScriptRoot 'iniciar_n8n.ps1')
if ($LASTEXITCODE -ne 0) { exit 1 }
Write-Host 'Aguardando o n8n responder...'
foreach ($i in 1..40) {
    Start-Sleep -Seconds 3
    try { Invoke-WebRequest 'http://localhost:5678/healthz' -UseBasicParsing -TimeoutSec 5 | Out-Null; break } catch {}
}

$workflows = 'consultar_motos', 'salvar_lead', 'assistente_telegram'
foreach ($nome in $workflows) {
    docker cp (Join-Path $PSScriptRoot "workflows\$nome.json") "n8n_celo:/tmp/$nome.json" *> $null
    docker exec n8n_celo n8n import:workflow "--input=/tmp/$nome.json" *> $null
    if ($LASTEXITCODE -ne 0) { Falhar "nao foi possivel importar o workflow $nome." }
}
Ok 'workflows importados'

$credenciais = @(
    @{ id = 'hsCredTelegram01'; name = 'Telegram - bot da loja'; type = 'telegramApi'
       data = @{ accessToken = $tokenTelegram; baseUrl = 'https://api.telegram.org' } },
    @{ id = 'hsCredClaude0001'; name = 'Anthropic - Claude'; type = 'anthropicApi'
       data = @{ apiKey = $chaveClaude; url = 'https://api.anthropic.com' } },
    @{ id = 'hsCredXanoBot001'; name = 'Xano - conta do bot'; type = 'httpCustomAuth'
       data = @{ json = (@{ body = @{ email = $emailXano; password = $senhaXano } } | ConvertTo-Json -Compress) } }
)
# Vai pela entrada padrao direto para dentro do container: as chaves nao
# ficam gravadas em nenhum arquivo do Windows.
$OutputEncoding = New-Object Text.UTF8Encoding $false
ConvertTo-Json -InputObject $credenciais -Depth 5 -Compress |
    docker exec -i n8n_celo sh -c 'cat > /tmp/cred.json && n8n import:credentials --input=/tmp/cred.json >/dev/null 2>&1; r=$?; rm -f /tmp/cred.json; exit $r'
if ($LASTEXITCODE -ne 0) { Falhar 'nao foi possivel gravar as credenciais no n8n.' }
Ok 'credenciais gravadas'

foreach ($id in 'hsMotosXano00001', 'hsSalvarLead0001', 'hsTelegramBot001') {
    docker exec n8n_celo n8n publish:workflow "--id=$id" *> $null
    if ($LASTEXITCODE -ne 0) { Falhar "nao foi possivel publicar o workflow $id." }
}
# A publicacao pela linha de comando so vale depois de reiniciar; ao subir, o
# n8n registra o endereco do tunel no Telegram.
docker restart n8n_celo *> $null
$endereco = (docker exec n8n_celo printenv WEBHOOK_URL).Trim()
$registrado = $false
foreach ($i in 1..40) {
    Start-Sleep -Seconds 3
    try {
        $info = Invoke-RestMethod "https://api.telegram.org/bot$tokenTelegram/getWebhookInfo"
        if ($info.result.url -and $info.result.url.StartsWith($endereco)) { $registrado = $true; break }
    } catch {}
}
if (-not $registrado) {
    Falhar ('o Telegram ainda nao aponta para o n8n. Abra http://localhost:5678, o workflow ' +
            '"Harley - assistente de vendas (Telegram)", e veja o erro ao publicar.')
}
Ok "bot no ar, recebendo em $endereco"

# ---------------------------------------------------------------- 3. app e inicio automatico
Write-Host "`n5/5 App e inicio automatico" -ForegroundColor Cyan
$conteudoEnv = "# Conta de servico do Xano usada pelo app (usuario da tabela user). Fora do git.`r`n" +
        "XANO_EMAIL=$emailXano`r`nXANO_SENHA=$senhaXano`r`n"
foreach ($pasta in @($raiz, 'C:\HARLEY_PROD')) {
    if (Test-Path $pasta) {
        [IO.File]::WriteAllText((Join-Path $pasta '.env'), $conteudoEnv, (New-Object Text.UTF8Encoding $false))
        Ok "conta do Xano gravada em $pasta\.env"
    }
}

$iniciar = Join-Path $PSScriptRoot 'iniciar_n8n.ps1'
$log = Join-Path $raiz 'logs\n8n-inicio.log'
New-Item -ItemType Directory -Force (Split-Path $log) | Out-Null
$acao = New-ScheduledTaskAction -Execute 'powershell.exe' -WorkingDirectory $raiz `
    -Argument "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -Command `"& '$iniciar' *> '$log'`""
$gatilho = New-ScheduledTaskTrigger -AtLogOn -User "$env:USERDOMAIN\$env:USERNAME"
$config = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 15) -MultipleInstances IgnoreNew
try {
    Register-ScheduledTask -TaskName 'HarleyStore-n8n' -Action $acao -Trigger $gatilho -Settings $config -Force `
        -Description 'Abre o Docker e inicia o n8n com o tunel (bot do Telegram) ao entrar no Windows' -ErrorAction Stop | Out-Null
    Ok 'tarefa HarleyStore-n8n criada (inicia o bot ao entrar no Windows)'
} catch {
    Write-Host '  aviso: sem permissao para criar a tarefa de inicio automatico. Rode este script' -ForegroundColor Yellow
    Write-Host '  como administrador, ou rode .\n8n\iniciar_n8n.ps1 sempre que ligar o computador.' -ForegroundColor Yellow
}

Write-Host "`nPronto. Mande uma mensagem para @$($bot.result.username) no Telegram." -ForegroundColor Green

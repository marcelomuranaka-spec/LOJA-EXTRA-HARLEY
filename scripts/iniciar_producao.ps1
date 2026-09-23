<#
  Inicia o ambiente de PRODUÇÃO do Harley Store (o que os funcionários usam).

  Executado automaticamente pela tarefa agendada "HarleyStore-Producao"
  quando o notebook liga. Fica em execução enquanto o sistema estiver no ar.

  Lê o endereço de rede do arquivo producao.local.ps1, que fica na raiz da
  pasta de produção e NÃO vai para o git. Conteúdo esperado:

      $EnderecoProducao = '192.168.0.54'

  A saída do Reflex vai para logs\producao-AAAAMMDD.log.
#>
$ErrorActionPreference = 'Stop'
$raiz = Split-Path $PSScriptRoot -Parent
Set-Location $raiz

$arquivoLocal = Join-Path $raiz 'producao.local.ps1'
if (-not (Test-Path $arquivoLocal)) {
    Write-Error ("Arquivo producao.local.ps1 nao encontrado em $raiz. " +
                 "Crie-o com a linha:  `$EnderecoProducao = '<IP reservado do notebook>'")
    exit 1
}
$EnderecoProducao = $null
. $arquivoLocal
if (-not $EnderecoProducao) {
    Write-Error "producao.local.ps1 nao define `$EnderecoProducao."
    exit 1
}

# Em produção o Reflex inicia o backend chamando o executável "granian" pelo
# nome; na tarefa agendada o .venv não está no PATH, então é incluído aqui.
$env:PATH = (Join-Path $raiz '.venv\Scripts') + ';' + $env:PATH

$env:REFLEX_API_URL       = "http://${EnderecoProducao}:8000"
$env:REFLEX_DEPLOY_URL    = "http://${EnderecoProducao}:3000"
$env:REFLEX_FRONTEND_PORT = '3000'
$env:REFLEX_BACKEND_PORT  = '8000'
Remove-Item Env:\REFLEX_BACKEND_HOST -ErrorAction SilentlyContinue  # padrao 0.0.0.0

$pastaLogs = Join-Path $raiz 'logs'
New-Item -ItemType Directory -Force $pastaLogs | Out-Null
$log = Join-Path $pastaLogs ("producao-{0:yyyyMMdd}.log" -f (Get-Date))
Add-Content -Path $log -Encoding utf8 -Value ("`r`n==== {0:yyyy-MM-dd HH:mm:ss} iniciando producao em http://{1}:3000" -f (Get-Date), $EnderecoProducao)

# cmd /c faz o redirecionamento sem o PowerShell 5.1 transformar a saida de
# erro do Reflex em excecao. Bloqueia ate o Reflex terminar.
$reflex = Join-Path $raiz '.venv\Scripts\reflex.exe'
cmd /c "`"$reflex`" run --env prod --loglevel info >> `"$log`" 2>&1"
$codigo = $LASTEXITCODE
Add-Content -Path $log -Encoding utf8 -Value ("==== {0:yyyy-MM-dd HH:mm:ss} producao encerrada (codigo {1})" -f (Get-Date), $codigo)
exit $codigo

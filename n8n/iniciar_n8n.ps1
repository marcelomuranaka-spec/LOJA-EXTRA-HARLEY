<#
  Inicia o n8n (assistente de vendas no Telegram) com o túnel da Cloudflare.

  O túnel rápido da Cloudflare (trycloudflare.com) é gratuito e não pede
  conta, mas ganha um endereço novo sempre que o container do túnel reinicia.
  Este script sobe o túnel, lê o endereço dele e recria o n8n com esse
  endereço em WEBHOOK_URL; ao iniciar, o n8n registra o novo endereço no
  Telegram sozinho. Rode-o de novo sempre que o computador ou o Docker
  reiniciar, senão o bot para de receber mensagens.

  Uso:  .\n8n\iniciar_n8n.ps1      (editor em http://localhost:5678)
#>
# 'Continue' (e nao 'Stop'): no PowerShell 5.1, com 'Stop', qualquer aviso que o
# docker escreva na saida de erro vira excecao. Cada passo confere $LASTEXITCODE.
$ErrorActionPreference = 'Continue'
function Falhar($texto) { Write-Host "ERRO: $texto" -ForegroundColor Red; exit 1 }
$compose = Join-Path $PSScriptRoot 'docker-compose.yml'

# O Docker Desktop instalado por usuario fica fora do PATH de janelas abertas
# antes da instalacao; e, se nao abrir junto com o Windows, e aberto aqui.
$pastasDocker = @((Join-Path $env:LOCALAPPDATA 'Programs\DockerDesktop'), (Join-Path $env:ProgramFiles 'Docker\Docker'))
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    $env:PATH = (($pastasDocker | ForEach-Object { Join-Path $_ 'resources\bin' }) -join ';') + ';' + $env:PATH
}
docker info *> $null
if ($LASTEXITCODE -ne 0) {
    $app = $pastasDocker | ForEach-Object { Join-Path $_ 'Docker Desktop.exe' } | Where-Object { Test-Path $_ } | Select-Object -First 1
    if (-not $app) { Falhar 'Docker Desktop nao encontrado.' }
    Write-Host 'Abrindo o Docker Desktop...'
    Start-Process $app
    foreach ($i in 1..60) {
        Start-Sleep -Seconds 5
        docker info *> $null
        if ($LASTEXITCODE -eq 0) { break }
    }
    if ($LASTEXITCODE -ne 0) { Falhar 'o Docker nao respondeu em 5 minutos.' }
}

docker volume inspect n8n_data *> $null
if ($LASTEXITCODE -ne 0) { docker volume create n8n_data | Out-Null }

# Túnel novo a cada execução: um endereço antigo que continue nos logs não
# serve mais, então o container do túnel é sempre recriado.
docker compose -f $compose up -d --force-recreate tunel
if ($LASTEXITCODE -ne 0) { Falhar 'nao foi possivel iniciar o tunel.' }

$endereco = $null
foreach ($i in 1..30) {
    Start-Sleep -Seconds 2
    $logs = (docker logs n8n_tunel 2>&1) -join "`n"
    if ($logs -match 'https://[a-z0-9-]+\.trycloudflare\.com') { $endereco = $Matches[0]; break }
}
if (-not $endereco) { Falhar 'o tunel nao informou o endereco em 60 s. Veja: docker logs n8n_tunel' }

$env:WEBHOOK_URL = "$endereco/"
docker compose -f $compose up -d n8n
if ($LASTEXITCODE -ne 0) {
    Falhar 'nao foi possivel iniciar o n8n. Se outro container ja usa a porta 5678, veja com: docker ps'
}

Write-Host "n8n no ar: editor em http://localhost:5678" -ForegroundColor Green
Write-Host "Endereco publico (Telegram): $endereco" -ForegroundColor Green

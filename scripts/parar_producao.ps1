<#
  Para o ambiente de PRODUÇÃO do Harley Store por completo.

  Encerra a tarefa agendada e TODOS os processos da produção, inclusive os
  processos-filhos (workers do backend, frontend Next.js). Sem isso, um
  worker órfão pode continuar segurando a porta 8000 com o código antigo.

  Uso:  .\scripts\parar_producao.ps1 [-Producao C:\HARLEY_PROD]
#>
param([string]$Producao = 'C:\HARLEY_PROD')
$ErrorActionPreference = 'Continue'
$nomeTarefa = 'HarleyStore-Producao'
$portas = 3000, 8000

# 1) Encerra a tarefa agendada (assim o Agendador não tenta reiniciá-la).
if (Get-ScheduledTask -TaskName $nomeTarefa -ErrorAction SilentlyContinue) {
    try { Stop-ScheduledTask -TaskName $nomeTarefa -ErrorAction Stop } catch {}
}

# 2) Processos da pasta de produção + todos os descendentes.
$todos = @(Get-CimInstance Win32_Process)
$alvo = @{}
$pastaNorm = $Producao.TrimEnd('\')
foreach ($p in $todos) {
    if ($p.CommandLine -and $p.CommandLine.IndexOf($pastaNorm, [StringComparison]::OrdinalIgnoreCase) -ge 0) {
        $alvo[[int]$p.ProcessId] = $p.Name
    }
}
do {
    $novos = 0
    foreach ($p in $todos) {
        if (-not $alvo.ContainsKey([int]$p.ProcessId) -and $alvo.ContainsKey([int]$p.ParentProcessId)) {
            $alvo[[int]$p.ProcessId] = $p.Name; $novos++
        }
    }
} while ($novos -gt 0)
$alvo.Remove($PID)  # nunca encerrar este próprio script

foreach ($id in $alvo.Keys) { Stop-Process -Id $id -Force -ErrorAction SilentlyContinue }

# 3) Órfãos que ainda seguram as portas da produção (python/node/bun).
Start-Sleep -Seconds 2
foreach ($c in @(Get-NetTCPConnection -LocalPort $portas -State Listen -ErrorAction SilentlyContinue)) {
    $proc = Get-Process -Id $c.OwningProcess -ErrorAction SilentlyContinue
    if ($proc -and $proc.ProcessName -match '^(python|pythonw|node|bun)$') {
        Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
        $alvo[[int]$proc.Id] = $proc.ProcessName
    }
}

# 4) Confirma que as portas ficaram livres.
$ocupadas = @()
for ($i = 0; $i -lt 15; $i++) {
    $ocupadas = @(Get-NetTCPConnection -LocalPort $portas -State Listen -ErrorAction SilentlyContinue)
    if ($ocupadas.Count -eq 0) { break }
    Start-Sleep -Seconds 1
}
if ($ocupadas.Count -gt 0) {
    Write-Warning ("Portas ainda ocupadas: " + (($ocupadas | ForEach-Object { "$($_.LocalPort) (PID $($_.OwningProcess))" }) -join ', '))
    exit 1
}
Write-Host ("Producao parada ({0} processo(s) encerrado(s)); portas 3000 e 8000 livres." -f $alvo.Count) -ForegroundColor Green
exit 0

<#
  Grava no .env a conta que o app usa para acessar o Xano (os endpoints das
  tabelas exigem login; sem ela as telas mostram "XanoSemLogin").

  Pede o email e a senha de um usuário do app (o mesmo da tela de login),
  testa no Xano e grava o .env do desenvolvimento e o da produção
  (C:\HARLEY_PROD). A senha não aparece na tela e não vai para o git.

  Uso:  .\scripts\configurar_xano.ps1      (depois, recarregue a página)
#>
$ErrorActionPreference = 'Continue'
function Falhar($texto) { Write-Host "ERRO: $texto" -ForegroundColor Red; exit 1 }
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
$raiz = Split-Path $PSScriptRoot -Parent
$xanoAuth = 'https://x8ki-letl-twmt.n7.xano.io/api:lH_WsSPl'
$xanoApi = 'https://x8ki-letl-twmt.n7.xano.io/api:LtU_pM2N'

$email = (Read-Host 'Email de um usuario do app (o mesmo da tela de login)').Trim()
$seguro = Read-Host 'Senha (nao aparece enquanto digita)' -AsSecureString
$ptr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($seguro)
try { $senha = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($ptr) }
finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ptr) }
if (-not $email -or -not $senha) { Falhar 'preencha email e senha.' }

$corpo = [Text.Encoding]::UTF8.GetBytes((@{ email = $email; password = $senha } | ConvertTo-Json -Compress))
try { $login = Invoke-RestMethod -Method Post "$xanoAuth/auth/login" -ContentType 'application/json' -Body $corpo }
catch { Falhar 'o Xano recusou esse email ou senha. Confira na tela de login do app.' }
try { $motos = @(Invoke-RestMethod "$xanoApi/motos" -Headers @{ Authorization = "Bearer $($login.authToken)" }) }
catch { Falhar 'o login foi aceito, mas o Xano recusou a leitura das tabelas com essa conta.' }
Write-Host "ok: login aceito ($($motos.Count) motos cadastradas)" -ForegroundColor Green

$conteudo = "# Conta de servico do Xano usada pelo app (usuario da tabela user). Fora do git.`r`n" +
            "XANO_EMAIL=$email`r`nXANO_SENHA=$senha`r`n"
foreach ($pasta in @($raiz, 'C:\HARLEY_PROD')) {
    if (Test-Path $pasta) {
        [IO.File]::WriteAllText((Join-Path $pasta '.env'), $conteudo, (New-Object Text.UTF8Encoding $false))
        Write-Host "ok: gravado em $pasta\.env" -ForegroundColor Green
    }
}
Write-Host 'Pronto. Recarregue a pagina do app (F5).' -ForegroundColor Green

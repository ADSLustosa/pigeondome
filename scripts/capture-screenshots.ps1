# Captura as imagens do painel para o README, com o Edge (ou Chrome) sem interface.
# Antes: simulador, atuador, controlador, API e `npm run dev` rodando, com bastante tempo de dados
# (o grafico usa a ultima hora). Precisa do Node 24 ou superior.
# Uso: .\scripts\capture-screenshots.ps1 [-WaitMs 8000]
param(
  [string]$Url = 'http://127.0.0.1:5173',
  [int]$WaitMs = 8000
)
$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
$out = Join-Path $root 'assets\screenshots'

$browser = @(
  "${env:ProgramFiles(x86)}\Microsoft\Edge\Application\msedge.exe",
  "$env:ProgramFiles\Microsoft\Edge\Application\msedge.exe",
  "$env:ProgramFiles\Google\Chrome\Application\chrome.exe"
) | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $browser) { throw 'Edge ou Chrome nao encontrado' }

try { Invoke-WebRequest $Url -UseBasicParsing -TimeoutSec 5 | Out-Null }
catch { throw "o painel nao responde em $Url (o npm run dev esta rodando?)" }

node (Join-Path $PSScriptRoot 'capture-screenshots.mjs') $browser $Url $out $WaitMs
if ($LASTEXITCODE -ne 0) { throw 'a captura falhou' }

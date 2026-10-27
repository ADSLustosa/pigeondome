# Captura as imagens do painel para o README, com o Edge (ou Chrome) sem interface.
# Antes: simulador, atuador, controlador, API e `npm run dev` rodando, com alguns minutos de dados.
# Uso: .\scripts\capture-screenshots.ps1 [-Height 2600]
param(
  [string]$Url = 'http://127.0.0.1:5173',
  [int]$Width = 1280,
  [int]$Height = 2600,
  [int]$WaitMs = 20000
)
$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
$out = Join-Path $root 'assets\screenshots'
New-Item -ItemType Directory -Force $out | Out-Null

$browser = @(
  "${env:ProgramFiles(x86)}\Microsoft\Edge\Application\msedge.exe",
  "$env:ProgramFiles\Microsoft\Edge\Application\msedge.exe",
  "$env:ProgramFiles\Google\Chrome\Application\chrome.exe"
) | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $browser) { throw 'Edge ou Chrome nao encontrado' }

try { Invoke-WebRequest $Url -UseBasicParsing -TimeoutSec 5 | Out-Null }
catch { throw "o painel nao responde em $Url (o npm run dev esta rodando?)" }

function Save-Shot([string]$Name, [int]$W, [int]$H, [int]$Scale, [bool]$Dark) {
  $profileDir = Join-Path $env:TEMP ('pigeondome-shot-' + [guid]::NewGuid())
  $file = Join-Path $out $Name
  $flags = @(
    '--headless=new', '--disable-gpu', '--hide-scrollbars',
    "--user-data-dir=$profileDir", "--window-size=$W,$H",
    "--force-device-scale-factor=$Scale", "--virtual-time-budget=$WaitMs",
    "--screenshot=$file"
  )
  if ($Dark) { $flags += '--blink-settings=preferredColorScheme=1' }
  & $browser @flags $Url | Out-Null
  Remove-Item $profileDir -Recurse -Force -ErrorAction SilentlyContinue
  if (-not (Test-Path $file) -or (Get-Item $file).Length -lt 20000) { throw "falha ao capturar $Name" }
  '{0}  {1:N0} KB' -f $Name, ((Get-Item $file).Length / 1KB)
}

Save-Shot 'painel-claro.png' $Width $Height 1 $false
Save-Shot 'painel-escuro.png' $Width $Height 1 $true
Save-Shot 'painel-movel-claro.png' 390 1900 2 $false
Save-Shot 'painel-movel-escuro.png' 390 1900 2 $true

# Mostra o registro de eventos gravado pelo próprio atuador (independe do broker e do controlador).
# Uso: .\scripts\show-actuator-journal.ps1 [-DeviceId act-sim-01] [-Last 20]
param(
  [string]$DeviceId = 'act-sim-01',
  [int]$Last = 20
)
$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
. "$PSScriptRoot\mqtt-env.ps1"
$py = Get-ProjectPython $root

$file = Join-Path $root ".pigeondome-state\actuator-$DeviceId-events.jsonl"
if (-not (Test-Path $file)) {
  Write-Host "Ainda nao ha registro em $file (suba o atuador com .\scripts\run-actuator.ps1)."
  return
}
# Acentos corretos no console: o Python escreve em UTF-8 e o PowerShell lê em UTF-8.
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$env:PYTHONUTF8 = '1'
$env:PYTHONPATH = Join-Path $root 'simulator\src'
$lines = & $py -m pigeondome_sim.actuator_journal $file
# A primeira linha é o cabeçalho; mostra os últimos eventos e mantém os avisos (linhas com "!").
$header = $lines | Select-Object -First 1
$events = $lines | Select-Object -Skip 1 | Where-Object { $_ -notmatch '^!' }
$warnings = $lines | Where-Object { $_ -match '^!' }
$header
$events | Select-Object -Last $Last
$warnings

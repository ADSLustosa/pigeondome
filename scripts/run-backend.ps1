# Executa o backend como o papel MQTT 'backend'. Uso: .\scripts\run-backend.ps1
$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
. "$PSScriptRoot\mqtt-env.ps1"
$py = Get-ProjectPython $root
Invoke-WithMqttRole -Role backend -Root $root -Command { & $py -m pigeondome }.GetNewClosure()

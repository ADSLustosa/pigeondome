# Console do atuador (comandos e monitoramento) como o papel MQTT 'backend'.
# Uso: .\scripts\actuator-console.ps1 pulse [-Seconds 5]
#      .\scripts\actuator-console.ps1 stop
#      .\scripts\actuator-console.ps1 watch
param(
  [Parameter(Mandatory, Position = 0)][ValidateSet('pulse', 'stop', 'watch')][string]$Action,
  [int]$Seconds = 5,
  [string]$DeviceId = 'act-sim-01'
)
$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
. "$PSScriptRoot\mqtt-env.ps1"
$py = Get-ProjectPython $root

$consoleArgs = @('-m', 'pigeondome_sim.actuator_console', $Action)
if ($Action -eq 'pulse') { $consoleArgs += @('--seconds', "$Seconds") }

$extra = @{ ACTUATOR_DEVICE_ID = $DeviceId }
Invoke-WithMqttRole -Role backend -Root $root -ExtraEnv $extra -Command { & $py @consoleArgs }.GetNewClosure()

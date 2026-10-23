# Executa o atuador simulado como o papel MQTT 'actuator'.
# Uso: .\scripts\run-actuator.ps1 [-DeviceId act-sim-01]
param(
  [string]$DeviceId = 'act-sim-01'
)
$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
. "$PSScriptRoot\mqtt-env.ps1"
$py = Get-ProjectPython $root

$extra = @{ ACTUATOR_DEVICE_ID = $DeviceId }
Invoke-WithMqttRole -Role actuator -Root $root -ExtraEnv $extra -Command { & $py -m pigeondome_sim.actuator_runner }.GetNewClosure()

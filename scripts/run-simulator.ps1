# Executa o simulador de camera como o papel MQTT 'camera'.
# Uso: .\scripts\run-simulator.ps1 [-Hour 8] [-IntervalSeconds 2]
#   -Hour: forca a hora usada pelo MODELO de presenca (o timestamp continua real)
param(
  [int]$Hour = -1,
  [double]$IntervalSeconds = 5
)
$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
. "$PSScriptRoot\mqtt-env.ps1"
$py = Get-ProjectPython $root

$extra = @{ SIM_INTERVAL_S = "$IntervalSeconds" }
if ($Hour -ge 0) { $extra['SIM_FORCE_HOUR'] = "$Hour" }
Invoke-WithMqttRole -Role camera -Root $root -ExtraEnv $extra -Command { & $py -m pigeondome_sim }.GetNewClosure()

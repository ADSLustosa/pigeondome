# Executa o controlador como o papel MQTT 'backend', com o banco do ambiente local (infra\.env).
# O PADRAO E O MODO SECO: decide e registra, mas nao envia nenhum comando ao atuador.
# Uso: .\scripts\run-controller.ps1 [-Mode dry_run|live|experiment|off] [-ActuatorId act-sim-01]
#                                   [-CameraId cam-sim-01]
param(
  [ValidateSet('off', 'dry_run', 'live', 'experiment')][string]$Mode = 'dry_run',
  [string]$ActuatorId = 'act-sim-01',
  [string]$CameraId = 'cam-sim-01'
)
$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
. "$PSScriptRoot\mqtt-env.ps1"
$py = Get-ProjectPython $root

$extra = @{
  CONTROLLER_MODE        = $Mode
  CONTROLLER_ACTUATOR_ID = $ActuatorId
  CONTROLLER_CAMERA_ID   = $CameraId
}
$envFile = Join-Path $root 'infra\.env'
foreach ($key in 'POSTGRES_PASSWORD', 'POSTGRES_PORT') {
  $hit = Select-String -Path $envFile -Pattern "^$key=" | Select-Object -First 1
  if ($hit) { $extra[$key] = $hit.Line.Split('=', 2)[1] }
}
Invoke-WithMqttRole -Role backend -Root $root -ExtraEnv $extra -Command { & $py -m pigeondome.controller_server }.GetNewClosure()

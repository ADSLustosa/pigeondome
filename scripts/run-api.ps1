# Executa a API HTTP de leitura (nao usa MQTT). Uso: .\scripts\run-api.ps1 [-Port 8000]
param([int]$Port = 8000)
$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
. "$PSScriptRoot\mqtt-env.ps1"
$py = Get-ProjectPython $root

# a camera simulada serve o quadro em http://127.0.0.1:8081/snapshot (so neste computador)
$vars = @{
  API_PORT = "$Port"
  CAMERA_SNAPSHOT_URLS = 'cam-sim-01=http://127.0.0.1:8081/snapshot'
}
$envFile = Join-Path $root 'infra\.env'
foreach ($key in 'POSTGRES_PASSWORD', 'POSTGRES_PORT') {
  $hit = Select-String -Path $envFile -Pattern "^$key=" | Select-Object -First 1
  if ($hit) { $vars[$key] = $hit.Line.Split('=', 2)[1] }
}

$saved = @{}
foreach ($k in $vars.Keys) { $saved[$k] = [Environment]::GetEnvironmentVariable($k) }
try {
  foreach ($k in $vars.Keys) { [Environment]::SetEnvironmentVariable($k, $vars[$k]) }
  & $py -m pigeondome.api_server
}
finally {
  foreach ($k in $vars.Keys) { [Environment]::SetEnvironmentVariable($k, $saved[$k]) }
}

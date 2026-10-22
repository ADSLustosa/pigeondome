# Executa o backend como o papel MQTT 'backend', com o banco do ambiente local (infra\.env).
# Uso: .\scripts\run-backend.ps1
$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
. "$PSScriptRoot\mqtt-env.ps1"
$py = Get-ProjectPython $root

$extra = @{}
$envFile = Join-Path $root 'infra\.env'
foreach ($key in 'POSTGRES_PASSWORD', 'POSTGRES_PORT') {
  $hit = Select-String -Path $envFile -Pattern "^$key=" | Select-Object -First 1
  if ($hit) { $extra[$key] = $hit.Line.Split('=', 2)[1] }
}
Invoke-WithMqttRole -Role backend -Root $root -ExtraEnv $extra -Command { & $py -m pigeondome }.GetNewClosure()

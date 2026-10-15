# Ajudante: executa um comando com as credenciais MQTT de um papel (backend, camera, actuator).
# As variaveis de ambiente sao restauradas ao final, sem contaminar a sessao.
function Invoke-WithMqttRole {
  param(
    [Parameter(Mandatory)][ValidateSet('backend', 'camera', 'actuator')][string]$Role,
    [Parameter(Mandatory)][string]$Root,
    [Parameter(Mandatory)][scriptblock]$Command,
    [hashtable]$ExtraEnv = @{}
  )
  $envFile = Join-Path $Root 'infra\.env'
  if (-not (Test-Path $envFile)) { throw "infra\.env nao encontrado: rode infra\setup.ps1" }
  $line = Select-String -Path $envFile -Pattern "^MQTT_PASS_$($Role.ToUpper())=" | Select-Object -First 1
  if (-not $line) { throw "senha do papel '$Role' ausente em infra\.env" }

  $names = @('MQTT_USER', 'MQTT_PASSWORD') + @($ExtraEnv.Keys)
  $saved = @{}
  foreach ($n in $names) { $saved[$n] = [Environment]::GetEnvironmentVariable($n) }
  try {
    [Environment]::SetEnvironmentVariable('MQTT_USER', $Role)
    [Environment]::SetEnvironmentVariable('MQTT_PASSWORD', $line.Line.Split('=', 2)[1])
    foreach ($k in $ExtraEnv.Keys) { [Environment]::SetEnvironmentVariable($k, [string]$ExtraEnv[$k]) }
    & $Command
  }
  finally {
    foreach ($n in $names) { [Environment]::SetEnvironmentVariable($n, $saved[$n]) }
  }
}

function Get-ProjectPython([string]$Root) {
  $py = Join-Path $Root '.venv\Scripts\python.exe'
  if (Test-Path $py) { return $py }
  return 'python'
}

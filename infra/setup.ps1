$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot

function New-Secret {
  $bytes = New-Object byte[] 24
  [Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($bytes)
  ([Convert]::ToBase64String($bytes) -replace '[+/=]', 'x')
}

if (-not (Test-Path .env)) {
  $content = "POSTGRES_PASSWORD=$(New-Secret)`nMQTT_PASS_BACKEND=$(New-Secret)`nMQTT_PASS_CAMERA=$(New-Secret)`nMQTT_PASS_ACTUATOR=$(New-Secret)`n"
  [IO.File]::WriteAllText("$PSScriptRoot\.env", $content, (New-Object Text.UTF8Encoding $false))
  Write-Host "[ok] .env criado com segredos aleatorios"
}

function Find-FreePort([int[]]$Candidates) {
  foreach ($port in $Candidates) {
    try {
      $l = [Net.Sockets.TcpListener]::new([Net.IPAddress]::Loopback, $port)
      $l.Start(); $l.Stop()
      return $port
    } catch { continue }
  }
  throw "nenhuma porta livre entre: $($Candidates -join ', ')"
}

if ((Get-Content .env -Raw) -notmatch '(?m)^POSTGRES_PORT=') {
  $port = Find-FreePort 5433, 5434, 5435, 15432
  [IO.File]::AppendAllText("$PSScriptRoot\.env", "POSTGRES_PORT=$port`n")
  Write-Host "[ok] POSTGRES_PORT=$port"
}

$cfg = @{}
Get-Content .env | Where-Object { $_ -match '^\s*[^#=]+=' } | ForEach-Object {
  $k, $v = $_ -split '=', 2
  $cfg[$k.Trim()] = $v.Trim()
}

$cmd = "mosquitto_passwd -b -c /mosquitto/config/passwd backend '$($cfg.MQTT_PASS_BACKEND)' && " +
       "mosquitto_passwd -b /mosquitto/config/passwd camera '$($cfg.MQTT_PASS_CAMERA)' && " +
       "mosquitto_passwd -b /mosquitto/config/passwd actuator '$($cfg.MQTT_PASS_ACTUATOR)'"

docker run --rm -v "${PSScriptRoot}\mosquitto:/mosquitto/config" eclipse-mosquitto:2.0.20 sh -c $cmd
if ($LASTEXITCODE -ne 0) { throw "falha ao gerar o arquivo de senhas do Mosquitto" }
Write-Host "[ok] mosquitto/passwd gerado para backend, camera e actuator"

# Prepara o ambiente local de desenvolvimento: segredos (.env) e arquivo de senhas do Mosquitto.
# Uso: .\infra\setup.ps1   (idempotente: nao sobrescreve o .env existente)
$ErrorActionPreference = 'Stop'

function New-Secret {
  $bytes = New-Object byte[] 24
  [Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($bytes)
  ([Convert]::ToBase64String($bytes) -replace '[+/=]', 'x')
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

# O script muda de pasta para trabalhar, mas SEMPRE devolve o terminal ao lugar de origem.
Push-Location $PSScriptRoot
try {
  if (-not (Test-Path .env)) {
    $content = "POSTGRES_PASSWORD=$(New-Secret)`nMQTT_PASS_BACKEND=$(New-Secret)`nMQTT_PASS_CAMERA=$(New-Secret)`nMQTT_PASS_ACTUATOR=$(New-Secret)`n"
    [IO.File]::WriteAllText("$PSScriptRoot\.env", $content, (New-Object Text.UTF8Encoding $false))
    Write-Host "[ok] .env criado com segredos aleatorios"
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

  $image = 'eclipse-mosquitto:2.0.20'
  $mount = "${PSScriptRoot}\mosquitto:/mosquitto/config"

  # O mosquitto_passwd roda como root e cria o arquivo so legivel por root. O broker, porem,
  # abre o arquivo depois de passar a rodar como o usuario 1883: ele precisa ser o dono (0600).
  $cmd = "mosquitto_passwd -b -c /mosquitto/config/passwd backend '$($cfg.MQTT_PASS_BACKEND)' && " +
         "mosquitto_passwd -b /mosquitto/config/passwd camera '$($cfg.MQTT_PASS_CAMERA)' && " +
         "mosquitto_passwd -b /mosquitto/config/passwd actuator '$($cfg.MQTT_PASS_ACTUATOR)' && " +
         "chown 1883:1883 /mosquitto/config/passwd /mosquitto/config/acl && " +
         "chmod 0600 /mosquitto/config/passwd /mosquitto/config/acl"
  docker run --rm -v $mount $image sh -c $cmd
  if ($LASTEXITCODE -ne 0) { throw "falha ao gerar o arquivo de senhas do Mosquitto" }

  # Verificacao: um container NOVO, rodando como o usuario do broker, precisa conseguir ler o arquivo.
  # Se nao conseguir, o broker entraria em reinicio repetido: melhor falhar aqui, com clareza.
  docker run --rm --user 1883:1883 -v "${mount}:ro" --entrypoint sh $image -c "test -s /mosquitto/config/passwd && test -r /mosquitto/config/passwd && test -r /mosquitto/config/acl"
  if ($LASTEXITCODE -ne 0) { throw "o usuario do broker (uid 1883) nao consegue ler mosquitto/passwd ou mosquitto/acl" }

  Write-Host "[ok] mosquitto/passwd gerado e legivel pelo usuario do broker (backend, camera, actuator)"
}
finally {
  Pop-Location
}

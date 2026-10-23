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

function Get-ExistingDbPort {
  # Se o banco ja existe (criado antes de o .env ter POSTGRES_PORT), a porta dele vale:
  # escolher outra faria os scripts procurarem o banco no lugar errado.
  try {
    $raw = docker inspect --format '{{with index .HostConfig.PortBindings `5432/tcp`}}{{(index . 0).HostPort}}{{end}}' pigeondome-db 2>$null
    $text = "$raw".Trim()
    if ($LASTEXITCODE -eq 0 -and $text -match '^\d+$') { return [int]$text }
  } catch { return $null }
  return $null
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
    $port = Get-ExistingDbPort
    $origin = 'porta do banco ja existente'
    if (-not $port) {
      $port = Find-FreePort 5433, 5434, 5435, 15432
      $origin = 'porta livre'
    }
    [IO.File]::AppendAllText("$PSScriptRoot\.env", "POSTGRES_PORT=$port`n")
    Write-Host "[ok] POSTGRES_PORT=$port ($origin)"
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
  # Os avisos "owner is not root" impressos aqui sao do mosquitto_passwd (uma vez por usuario)
  # e sao esperados: o chown final, dentro do mesmo comando, acerta o dono.
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

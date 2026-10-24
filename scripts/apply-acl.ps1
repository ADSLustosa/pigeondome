# Aplica dono e modo ao passwd/acl do Mosquitto, reinicia o broker e confere os logs.
# Use depois de EDITAR infra\mosquitto\acl (ou de um git pull que o tenha alterado): gravar o
# arquivo no Windows apaga o dono e o modo (1883:1883, 0600) que o broker exige.
# Uso: .\scripts\apply-acl.ps1
$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
$image = 'eclipse-mosquitto:2.0.20'
$mount = "$root\infra\mosquitto:/mosquitto/config"
$compose = "$root\infra\docker-compose.yml"

foreach ($file in 'acl', 'passwd') {
  if (-not (Test-Path "$root\infra\mosquitto\$file")) {
    throw "infra\mosquitto\$file nao encontrado: rode .\infra\setup.ps1"
  }
}

docker run --rm -v $mount $image sh -c 'chown 1883:1883 /mosquitto/config/passwd /mosquitto/config/acl && chmod 0600 /mosquitto/config/passwd /mosquitto/config/acl'
if ($LASTEXITCODE -ne 0) { throw 'falha ao aplicar dono e modo no passwd e no acl' }

# Um container NOVO, rodando como o usuario do broker, precisa conseguir ler os dois arquivos.
docker run --rm --user 1883:1883 -v "${mount}:ro" --entrypoint sh $image -c 'test -r /mosquitto/config/passwd && test -r /mosquitto/config/acl'
if ($LASTEXITCODE -ne 0) { throw 'o usuario do broker (uid 1883) nao consegue ler passwd ou acl' }

# cmd /c devolve texto puro, sem os "erros nativos" que o Windows PowerShell 5.1 cria no 2>&1.
$before = @(cmd /c 'docker logs pigeondome-mqtt 2>&1').Count
docker compose -f $compose restart mosquitto
if ($LASTEXITCODE -ne 0) { throw 'falha ao reiniciar o broker' }

$logs = ''
for ($i = 0; $i -lt 15; $i++) {
  Start-Sleep -Seconds 1
  $logs = (@(cmd /c 'docker logs pigeondome-mqtt 2>&1') | Select-Object -Skip $before) -join "`n"
  if ($logs -match 'mosquitto version .* running') { break }
}
if ($logs -notmatch 'mosquitto version .* running') { throw "o broker nao subiu em 15 s:`n$logs" }
if ($logs -match 'Warning: File|Error:') { throw "o broker carregou com avisos ou erros:`n$logs" }
Write-Host '[ok] ACL aplicado: broker rodando, sem avisos de permissao nem erros'

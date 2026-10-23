# Teste de fumaca da API: sobe o servidor em segundo plano, confere os codigos HTTP e encerra.
# Uso: .\scripts\smoke-api.ps1 [-Port 8765] [-Start ...] [-End ...]
param(
  [int]$Port = 8765,
  [string]$Start = '2026-10-22T22:30:00Z',
  [string]$End = '2026-10-22T22:33:00Z'
)
$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
. "$PSScriptRoot\mqtt-env.ps1"
$py = Get-ProjectPython $root
$base = "http://127.0.0.1:$Port"

$vars = @{ API_PORT = "$Port" }
$envFile = Join-Path $root 'infra\.env'
foreach ($key in 'POSTGRES_PASSWORD', 'POSTGRES_PORT') {
  $hit = Select-String -Path $envFile -Pattern "^$key=" | Select-Object -First 1
  if ($hit) { $vars[$key] = $hit.Line.Split('=', 2)[1] }
}

$checks = @(
  @{ Expect = 200; Path = '/health' },
  @{ Expect = 200; Path = '/api/v1/devices' },
  @{ Expect = 404; Path = '/api/v1/devices/nao-existe/presence' },
  @{ Expect = 422; Path = '/api/v1/devices/BAD_ID/presence' },
  @{ Expect = 422; Path = '/api/v1/devices/cam-sim-01/presence?start=2026-10-22T22:30:00' },
  @{ Expect = 422; Path = '/api/v1/devices/cam-sim-01/presence?start=2026-01-01T00:00:00Z&end=2026-10-22T00:00:00Z' }
)

$saved = @{}
foreach ($k in $vars.Keys) { $saved[$k] = [Environment]::GetEnvironmentVariable($k) }
$log = Join-Path ([IO.Path]::GetTempPath()) 'pigeondome-smoke.log'
$proc = $null
$failed = 0
try {
  foreach ($k in $vars.Keys) { [Environment]::SetEnvironmentVariable($k, $vars[$k]) }
  $proc = Start-Process -FilePath $py -ArgumentList '-m', 'pigeondome.api_server' -PassThru -WindowStyle Hidden -RedirectStandardError $log -RedirectStandardOutput "$log.out"

  $ready = $false
  for ($i = 0; $i -lt 30; $i++) {
    Start-Sleep -Milliseconds 500
    if ($proc.HasExited) { break }
    if ((curl.exe -s -o NUL -w "%{http_code}" "$base/health") -eq '200') { $ready = $true; break }
  }
  if (-not $ready) { throw "a API nao respondeu em /health (veja $log)" }

  foreach ($c in $checks) {
    $out = (curl.exe -s -o NUL -w "%{http_code} %{content_type}" "$base$($c.Path)").Split(' ', 2)
    $code = [int]$out[0]
    $ctype = $out[1]
    $ok = ($code -eq $c.Expect) -and ($code -lt 400 -or $ctype -like 'application/problem+json*')
    if (-not $ok) { $failed++ }
    '{0}  esperado {1}  obtido {2}  [{3}]  {4}' -f $(if ($ok) { 'OK   ' } else { 'FALHA' }), $c.Expect, $code, $ctype, $c.Path
  }

  "--- amostra: presenca de cam-sim-01 entre $Start e $End ---"
  curl.exe -s "$base/api/v1/devices/cam-sim-01/presence?start=$Start&end=$End"
  ""
}
finally {
  # o python do venv, no Windows, abre um processo filho: /T encerra a arvore inteira
  if ($proc -and -not $proc.HasExited) { taskkill.exe /PID $proc.Id /T /F | Out-Null }
  foreach ($k in $vars.Keys) { [Environment]::SetEnvironmentVariable($k, $saved[$k]) }
}
if ($failed -gt 0) { Write-Host "$failed verificacao(oes) falharam"; exit 1 }
Write-Host "[ok] todas as verificacoes passaram"

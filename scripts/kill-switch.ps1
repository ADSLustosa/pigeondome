# Chave geral do controlador: mostra, liga ou desliga.
# Uso: .\scripts\kill-switch.ps1 status|on|off
#
# DESLIGAR a chave (voltar a permitir pulsos) so e possivel por aqui, na maquina do banco.
# A API so consegue LIGAR a chave: parar o sistema e sempre seguro, rearma-lo exige presenca.
param(
  [Parameter(Mandatory, Position = 0)][ValidateSet('status', 'on', 'off')][string]$Action
)

function Invoke-Psql([string]$Sql) {
  docker exec pigeondome-db psql -U pigeon -d pigeondome -c $Sql
  if ($LASTEXITCODE -ne 0) {
    Write-Error 'falha ao falar com o banco (o conteiner pigeondome-db esta de pe?)'
    exit 1
  }
}

switch ($Action) {
  'on' {
    Invoke-Psql 'UPDATE controller_flags SET kill_switch = true, updated_at = now() WHERE id = 1'
    Write-Host 'chave geral LIGADA: o controlador para de comandar o atuador no proximo passo'
  }
  'off' {
    Invoke-Psql 'UPDATE controller_flags SET kill_switch = false, updated_at = now() WHERE id = 1'
    Write-Host 'chave geral DESLIGADA: o controlador volta a poder acionar o atuador (pelo modo)'
  }
}
Invoke-Psql 'SELECT kill_switch AS chave_ligada, updated_at FROM controller_flags WHERE id = 1'

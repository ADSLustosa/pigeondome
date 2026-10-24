# Mostra a trilha do controlador direto do banco (via o container do PostgreSQL).
# Uso: .\scripts\show-decisions.ps1 [-View decisions|events|summary] [-Last 15]
param(
  [ValidateSet('decisions', 'events', 'summary')][string]$View = 'decisions',
  [int]$Last = 15
)
$ErrorActionPreference = 'Stop'
$queries = @{
  decisions = "SELECT to_char(decided_at AT TIME ZONE 'America/Fortaleza', 'HH24:MI:SS') AS hora, mode, verdict, reason, detail, coalesce(arm, '') AS arm, detections AS det, triggered AS disparo FROM actuation_decisions ORDER BY decided_at DESC LIMIT $Last"
  events    = "SELECT to_char(occurred_at AT TIME ZONE 'America/Fortaleza', 'HH24:MI:SS') AS hora, event, coalesce(reason_code, '') AS motivo, left(coalesce(command_id::text, ''), 8) AS comando FROM actuator_events ORDER BY occurred_at DESC LIMIT $Last"
  summary   = "SELECT mode, verdict, reason, count(*) AS n FROM actuation_decisions GROUP BY 1, 2, 3 ORDER BY n DESC"
}
docker exec pigeondome-db psql -U pigeon -d pigeondome -c $queries[$View]

import { useState } from 'react'
import { getDecisions } from '../api/client'
import type { Decision } from '../api/types'
import { ACTUATOR_ID, LOG_LIMIT, LOG_POLL_MS } from '../config'
import { usePolling } from '../hooks/usePolling'
import { armLabel, modeInfo, reasonText, verdictInfo } from '../lib/actuation'
import { formatLogTime, formatPercent } from '../lib/format'
import { defaultPageSize, shownText } from '../lib/paging'
import { Chip } from './Chip'
import { ErrorNotice } from './ErrorNotice'
import { PageSizeControl } from './PageSizeControl'

const fetchDecisions = (signal: AbortSignal) => getDecisions(ACTUATOR_ID, LOG_LIMIT, signal)

// O mesmo texto serve ao cabeçalho da tabela e ao rótulo (data-label) que cada célula mostra
// quando a tabela vira lista de cartões em telas estreitas.
const COLUMN = {
  when: 'Quando',
  mode: 'Modo',
  verdict: 'Decisão',
  reason: 'Motivo',
  evidence: 'Evidência',
  command: 'Comando',
} as const

function evidenceText(decision: Decision): string {
  if (decision.readings === 0) return 'sem leituras'
  const base = `${decision.detections} de ${decision.readings} leituras com pombo`
  return decision.detections === 0
    ? base
    : `${base} · confiança ${formatPercent(decision.mean_confidence)}`
}

function reasonCell(decision: Decision): string {
  const reason = reasonText(decision.reason, decision.detail)
  return decision.arm === null ? reason : `${reason} · ${armLabel(decision.arm)}`
}

export function DecisionLog() {
  const { data, error } = usePolling(fetchDecisions, LOG_POLL_MS)
  const [onlyTriggered, setOnlyTriggered] = useState(false)
  const [pageSize, setPageSize] = useState(defaultPageSize)
  const all = data?.decisions ?? []
  const matching = onlyTriggered ? all.filter((decision) => decision.triggered) : all
  const rows = matching.slice(0, pageSize)
  const loading = data === null && error === null

  return (
    <article className="act-card" aria-labelledby="decisions-title">
      <header className="act-card__head">
        <div>
          <h3 id="decisions-title" className="act-card__title">
            Decisões
          </h3>
          <p className="act-card__subtitle">
            Só acionamentos e mudanças de motivo são registrados.
          </p>
        </div>
      </header>

      {all.length > 0 ? (
        <div className="act-toolbar">
          <label className="act-check">
            <input
              type="checkbox"
              checked={onlyTriggered}
              onChange={(event) => setOnlyTriggered(event.target.checked)}
            />
            Só acionamentos
          </label>
          <PageSizeControl name="decisions" value={pageSize} onChange={setPageSize} />
        </div>
      ) : null}

      {error ? (
        <ErrorNotice
          title="Não foi possível atualizar as decisões"
          message={data ? `${error.message}. Mostrando o último dado recebido.` : error.message}
        />
      ) : null}

      {loading ? (
        <div className="act-skeleton act-skeleton--tall" aria-busy="true">
          <span className="visually-hidden">Carregando as decisões</span>
        </div>
      ) : null}

      {data !== null && rows.length === 0 ? (
        <p className="act-empty">
          {onlyTriggered
            ? 'Nenhum acionamento nas últimas 24 horas.'
            : 'Nenhuma decisão nas últimas 24 horas.'}
        </p>
      ) : null}

      {rows.length > 0 ? (
        <div className="act-log">
          <div
            className="act-table-wrap"
            role="region"
            aria-labelledby="decisions-title"
            tabIndex={0}
          >
            <table className="act-table" role="table">
              <caption className="visually-hidden">
                Decisões do controlador, da mais recente para a mais antiga
              </caption>
              <thead role="rowgroup">
                <tr role="row">
                  <th scope="col" role="columnheader">
                    {COLUMN.when}
                  </th>
                  <th scope="col" role="columnheader">
                    {COLUMN.mode}
                  </th>
                  <th scope="col" role="columnheader">
                    {COLUMN.verdict}
                  </th>
                  <th scope="col" role="columnheader">
                    {COLUMN.reason}
                  </th>
                  <th scope="col" role="columnheader">
                    {COLUMN.evidence}
                  </th>
                  <th scope="col" role="columnheader">
                    {COLUMN.command}
                  </th>
                </tr>
              </thead>
              <tbody role="rowgroup">
                {rows.map((decision) => {
                  const verdict = verdictInfo(decision.verdict)
                  return (
                    <tr
                      key={`${decision.decided_at}|${decision.camera_id}`}
                      role="row"
                      className={decision.triggered ? 'act-row act-row--triggered' : 'act-row'}
                    >
                      <td role="cell" data-label={COLUMN.when}>
                        <time dateTime={decision.decided_at}>
                          {formatLogTime(decision.decided_at)}
                        </time>
                      </td>
                      <td role="cell" data-label={COLUMN.mode}>
                        {modeInfo(decision.mode).label}
                      </td>
                      <td role="cell" data-label={COLUMN.verdict}>
                        <Chip tone={verdict.tone}>{verdict.label}</Chip>
                      </td>
                      <td role="cell" data-label={COLUMN.reason} className="act-wrap">
                        {reasonCell(decision)}
                      </td>
                      <td role="cell" data-label={COLUMN.evidence} className="act-wrap">
                        {evidenceText(decision)}
                      </td>
                      <td role="cell" data-label={COLUMN.command}>
                        {decision.command_id === null ? (
                          '—'
                        ) : (
                          <code title={decision.command_id}>{decision.command_id.slice(0, 8)}</code>
                        )}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        </div>
      ) : null}

      {matching.length > rows.length ? (
        <p className="act-hint">{shownText(rows.length, matching.length, 'decisões')}</p>
      ) : null}

      {data?.truncated ? (
        <p className="act-hint">
          {`Mostrando as ${data.limit} decisões mais recentes; há decisões mais antigas nesta janela.`}
        </p>
      ) : null}
    </article>
  )
}

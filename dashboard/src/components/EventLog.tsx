import { useState } from 'react'
import { getActuatorEvents } from '../api/client'
import { ACTUATOR_ID, LOG_LIMIT, LOG_POLL_MS } from '../config'
import { usePolling } from '../hooks/usePolling'
import { eventInfo, reasonCodeText } from '../lib/actuation'
import { formatLogTime } from '../lib/format'
import { defaultPageSize, shownText } from '../lib/paging'
import { Chip } from './Chip'
import { ErrorNotice } from './ErrorNotice'
import { PageSizeControl } from './PageSizeControl'

const fetchEvents = (signal: AbortSignal) => getActuatorEvents(ACTUATOR_ID, LOG_LIMIT, signal)

// O mesmo texto serve ao cabeçalho da tabela e ao rótulo (data-label) que cada célula mostra
// quando a tabela vira lista de cartões em telas estreitas.
const COLUMN = {
  when: 'Quando',
  event: 'Evento',
  reason: 'Motivo',
  command: 'Comando',
} as const

export function EventLog() {
  const { data, error } = usePolling(fetchEvents, LOG_POLL_MS)
  const [pageSize, setPageSize] = useState(defaultPageSize)
  const all = data?.events ?? []
  const rows = all.slice(0, pageSize)
  const loading = data === null && error === null

  return (
    <article className="act-card" aria-labelledby="events-title">
      <header className="act-card__head">
        <div>
          <h3 id="events-title" className="act-card__title">
            Eventos do atuador
          </h3>
          <p className="act-card__subtitle">
            Gravados pelo controlador: com ele parado, a lista pode estar incompleta.
          </p>
        </div>
      </header>

      {all.length > 0 ? (
        <div className="act-toolbar">
          <PageSizeControl name="events" value={pageSize} onChange={setPageSize} />
        </div>
      ) : null}

      {error ? (
        <ErrorNotice
          title="Não foi possível atualizar os eventos"
          message={data ? `${error.message}. Mostrando o último dado recebido.` : error.message}
        />
      ) : null}

      {loading ? (
        <div className="act-skeleton act-skeleton--tall" aria-busy="true">
          <span className="visually-hidden">Carregando os eventos</span>
        </div>
      ) : null}

      {data !== null && rows.length === 0 ? (
        <p className="act-empty">Nenhum evento do atuador nas últimas 24 horas.</p>
      ) : null}

      {rows.length > 0 ? (
        <div className="act-log">
          <div className="act-table-wrap" role="region" aria-labelledby="events-title" tabIndex={0}>
            <table className="act-table" role="table">
              <caption className="visually-hidden">
                Eventos do atuador, do mais recente para o mais antigo
              </caption>
              <thead role="rowgroup">
                <tr role="row">
                  <th scope="col" role="columnheader">
                    {COLUMN.when}
                  </th>
                  <th scope="col" role="columnheader">
                    {COLUMN.event}
                  </th>
                  <th scope="col" role="columnheader">
                    {COLUMN.reason}
                  </th>
                  <th scope="col" role="columnheader">
                    {COLUMN.command}
                  </th>
                </tr>
              </thead>
              <tbody role="rowgroup">
                {rows.map((event) => {
                  const info = eventInfo(event.event)
                  return (
                    <tr key={`${event.occurred_at}|${event.event}`} role="row" className="act-row">
                      <td role="cell" data-label={COLUMN.when}>
                        <time dateTime={event.occurred_at}>{formatLogTime(event.occurred_at)}</time>
                      </td>
                      <td role="cell" data-label={COLUMN.event}>
                        <Chip tone={info.tone}>{info.label}</Chip>
                      </td>
                      <td role="cell" data-label={COLUMN.reason} className="act-wrap">
                        {event.reason_code === null ? '—' : reasonCodeText(event.reason_code)}
                      </td>
                      <td role="cell" data-label={COLUMN.command}>
                        {event.command_id === null ? (
                          '—'
                        ) : (
                          <code title={event.command_id}>{event.command_id.slice(0, 8)}</code>
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

      {all.length > rows.length ? (
        <p className="act-hint">{shownText(rows.length, all.length, 'eventos')}</p>
      ) : null}

      {data?.truncated ? (
        <p className="act-hint">
          {`Mostrando os ${data.limit} eventos mais recentes; há eventos mais antigos nesta janela.`}
        </p>
      ) : null}
    </article>
  )
}

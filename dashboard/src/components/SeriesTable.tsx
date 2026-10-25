import type { Series } from '../api/types'
import {
  formatClock,
  formatDateTime,
  formatDayMonth,
  formatDecimal,
  formatInteger,
  formatPercent,
} from '../lib/format'
import { BUCKET_MINUTES } from '../lib/windows'

interface ColumnHeaderProps {
  full: string
  short: string
}

/** O nome completo fica para leitores de tela; em telas estreitas a versão curta o substitui. */
function ColumnHeader({ full, short }: ColumnHeaderProps) {
  return (
    <th scope="col">
      <span className="col-full">{full}</span>
      <span className="col-short" aria-hidden="true">
        {short}
      </span>
    </th>
  )
}

export function SeriesTable({ series }: { series: Series }) {
  // intervalos de 1 h ou mais começam em minutos quebrados: os segundos só atrapalham
  const withSeconds = BUCKET_MINUTES[series.bucket] < 60
  return (
    <details className="data-table">
      <summary>Ver os dados em tabela</summary>
      <div className="data-table__scroll">
        <table>
          <caption className="visually-hidden">Presença de pombos por intervalo de tempo</caption>
          <thead>
            <tr>
              <ColumnHeader full="Início do intervalo" short="Início" />
              <ColumnHeader full="Leituras" short="Leit." />
              <ColumnHeader full="Presença" short="Pres." />
              <ColumnHeader full="Média" short="Méd." />
              <ColumnHeader full="Pico" short="Pico" />
            </tr>
          </thead>
          <tbody>
            {series.points.map((point, index) => {
              const day = formatDayMonth(point.bucket_start)
              const previous = series.points[index - 1]
              // o dia só aparece na primeira linha e quando muda; nas demais fica para leitores de tela
              const showDay = !previous || formatDayMonth(previous.bucket_start) !== day
              return (
                <tr key={point.bucket_start}>
                  <th scope="row">
                    <time dateTime={point.bucket_start} title={formatDateTime(point.bucket_start)}>
                      {showDay ? (
                        <span className="data-table__day">{day}</span>
                      ) : (
                        <span className="visually-hidden">{day}</span>
                      )}{' '}
                      <span className="data-table__clock">
                        {formatClock(point.bucket_start, withSeconds)}
                      </span>
                    </time>
                  </th>
                  <td>{formatInteger(point.readings)}</td>
                  <td>{formatPercent(point.presence_rate)}</td>
                  <td>{formatDecimal(point.mean_pigeons)}</td>
                  <td>{formatInteger(point.max_pigeons)}</td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </details>
  )
}

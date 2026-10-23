import type { Series } from '../api/types'
import { formatDateTime, formatDecimal, formatInteger, formatPercent } from '../lib/format'

export function SeriesTable({ series }: { series: Series }) {
  return (
    <details className="data-table">
      <summary>Ver os dados em tabela</summary>
      <div className="data-table__scroll">
        <table>
          <caption className="visually-hidden">Presença de pombos por intervalo de tempo</caption>
          <thead>
            <tr>
              <th scope="col">Início do intervalo</th>
              <th scope="col">Leituras</th>
              <th scope="col">Presença</th>
              <th scope="col">Média</th>
              <th scope="col">Pico</th>
            </tr>
          </thead>
          <tbody>
            {series.points.map((point) => (
              <tr key={point.bucket_start}>
                <th scope="row">{formatDateTime(point.bucket_start)}</th>
                <td>{formatInteger(point.readings)}</td>
                <td>{formatPercent(point.presence_rate)}</td>
                <td>{formatDecimal(point.mean_pigeons)}</td>
                <td>{formatInteger(point.max_pigeons)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </details>
  )
}

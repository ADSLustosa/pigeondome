import { useCallback } from 'react'
import { getSeries } from '../api/client'
import { SERIES_POLL_MS } from '../config'
import { usePolling } from '../hooks/usePolling'
import { BUCKET_LABELS } from '../lib/chart'
import { rangeFor } from '../lib/windows'
import type { WindowPreset } from '../lib/windows'
import { ChartLegend } from './ChartLegend'
import { ErrorNotice } from './ErrorNotice'
import { PresenceChart } from './PresenceChart'
import { SeriesTable } from './SeriesTable'

interface SeriesSectionProps {
  deviceId: string
  preset: WindowPreset
}

export function SeriesSection({ deviceId, preset }: SeriesSectionProps) {
  const fetchSeries = useCallback(
    (signal: AbortSignal) =>
      getSeries(deviceId, rangeFor(preset, new Date()), preset.bucket, signal),
    [deviceId, preset],
  )
  const { data, error } = usePolling(fetchSeries, SERIES_POLL_MS)
  const loading = data === null && error === null

  return (
    <section aria-labelledby="series-title">
      <div className="section-head">
        <h2 id="series-title" className="section-title">
          Presença ao longo do tempo
        </h2>
        <p className="section-subtitle">
          média de pombos a cada {BUCKET_LABELS[preset.bucket]}
        </p>
      </div>

      {error ? (
        <ErrorNotice title="Não foi possível atualizar o gráfico" message={error.message} />
      ) : null}

      <div className="chart-card">
        {data && data.points.length > 0 ? (
          <>
            <PresenceChart series={data} />
            <ChartLegend />
            <SeriesTable series={data} />
          </>
        ) : null}
        {data && data.points.length === 0 ? (
          <div className="chart-empty">
            <p>Nenhuma medição neste período. Tente um período maior.</p>
          </div>
        ) : null}
        {loading ? (
          <div className="chart-skeleton" aria-busy="true">
            <span className="visually-hidden">Carregando o gráfico</span>
          </div>
        ) : null}
      </div>
    </section>
  )
}

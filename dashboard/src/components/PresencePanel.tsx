import { useCallback } from 'react'
import { getPresence } from '../api/client'
import { PRESENCE_POLL_MS } from '../config'
import { usePolling } from '../hooks/usePolling'
import { formatDecimal, formatInteger, formatPercent, formatTime } from '../lib/format'
import { rangeFor } from '../lib/windows'
import type { WindowPreset } from '../lib/windows'
import { ErrorNotice } from './ErrorNotice'
import { KpiCard } from './KpiCard'

interface PresencePanelProps {
  deviceId: string
  preset: WindowPreset
}

export function PresencePanel({ deviceId, preset }: PresencePanelProps) {
  // a janela é recalculada a cada atualização, então ela "desliza" junto com o relógio
  const fetchPresence = useCallback(
    (signal: AbortSignal) => getPresence(deviceId, rangeFor(preset, new Date()), signal),
    [deviceId, preset],
  )
  const { data, error, updatedAt } = usePolling(fetchPresence, PRESENCE_POLL_MS)
  const loading = data === null && error === null

  return (
    <section aria-labelledby="summary-title">
      <div className="section-head">
        <h2 id="summary-title" className="section-title">
          Resumo
        </h2>
        <p className="section-subtitle">{preset.title}</p>
      </div>

      {error ? <ErrorNotice title="Não foi possível atualizar os dados" message={error.message} /> : null}

      <div className="kpi-grid">
        <KpiCard
          label="Leituras"
          value={data ? formatInteger(data.readings) : null}
          hint="medições da câmera no período"
          loading={loading}
        />
        <KpiCard
          label="Presença"
          value={data ? formatPercent(data.presence_rate) : null}
          hint="das leituras tinham ao menos um pombo"
          loading={loading}
        />
        <KpiCard
          label="Média de pombos"
          value={data ? formatDecimal(data.mean_pigeons) : null}
          hint="por leitura"
          loading={loading}
        />
        <KpiCard
          label="Pico"
          value={data ? formatInteger(data.max_pigeons) : null}
          hint="maior contagem em uma leitura"
          loading={loading}
        />
      </div>

      <p className="updated">{updatedAt ? `Atualizado às ${formatTime(updatedAt)}` : ''}</p>
    </section>
  )
}

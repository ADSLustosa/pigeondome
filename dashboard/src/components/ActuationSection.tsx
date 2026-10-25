import { getController } from '../api/client'
import { ACTUATION_POLL_MS } from '../config'
import { usePolling } from '../hooks/usePolling'
import { formatTime } from '../lib/format'
import { ActuatorCard } from './ActuatorCard'
import { ControllerCard } from './ControllerCard'
import { ErrorNotice } from './ErrorNotice'
import { KillSwitchCard } from './KillSwitchCard'

export function ActuationSection() {
  const { data, error, updatedAt, refresh } = usePolling(getController, ACTUATION_POLL_MS)
  const killSwitch = data === null ? null : data.kill_switch

  return (
    <section aria-labelledby="actuation-title">
      <div className="section-head">
        <h2 id="actuation-title" className="section-title">
          Atuação
        </h2>
        <p className="section-subtitle">controlador, atuador e chave geral</p>
      </div>

      {error ? (
        <ErrorNotice
          title="Não foi possível atualizar o estado do controlador"
          message={data ? `${error.message}. Mostrando o último estado recebido.` : error.message}
        />
      ) : null}

      <div className="act-grid">
        <ControllerCard data={data} failed={error !== null} outdated={data !== null && error !== null} />
        <ActuatorCard />
        <KillSwitchCard key={String(killSwitch)} engaged={killSwitch} onEngaged={refresh} />
      </div>

      <p className="updated">{updatedAt ? `Atualizado às ${formatTime(updatedAt)}` : ''}</p>
    </section>
  )
}

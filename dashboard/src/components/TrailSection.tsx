import { DecisionLog } from './DecisionLog'
import { EventLog } from './EventLog'

export function TrailSection() {
  return (
    <section aria-labelledby="trail-title">
      <div className="section-head">
        <h2 id="trail-title" className="section-title">
          Trilha do controlador
        </h2>
        <p className="section-subtitle">últimas 24 horas</p>
      </div>
      <div className="act-stack">
        <DecisionLog />
        <EventLog />
      </div>
    </section>
  )
}

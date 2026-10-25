import { ApiError, getActuatorStatus } from '../api/client'
import type { ActuatorStatus } from '../api/types'
import { ACTUATION_POLL_MS, ACTUATOR_HOURLY_BUDGET_S, ACTUATOR_ID } from '../config'
import { usePolling } from '../hooks/usePolling'
import { actuatorSummary } from '../lib/actuation'
import { formatAge, formatDateTime } from '../lib/format'
import { CardShell, Facts } from './CardShell'
import { Chip } from './Chip'
import { ErrorNotice } from './ErrorNotice'

const TITLE_ID = 'actuator-title'

const fetchStatus = (signal: AbortSignal) => getActuatorStatus(ACTUATOR_ID, signal)

function outputLabel(output: boolean | null): string {
  if (output === null) return 'Não informada'
  return output ? 'Ligada' : 'Desligada'
}

function Details({ status, outdated }: { status: ActuatorStatus; outdated: boolean }) {
  const summary = actuatorSummary(status)
  const used = status.budget_used_s_1h
  const age = formatAge(status.age_s)
  return (
    <CardShell
      id={TITLE_ID}
      title="Atuador"
      outdated={outdated}
      chip={<Chip tone={summary.tone}>{summary.label}</Chip>}
    >
      {!status.online ? (
        <p className="act-note act-note--danger">
          {`O broker informou que o atuador está fora do ar há ${age}. O controlador não envia comandos enquanto ele não voltar.`}
        </p>
      ) : null}
      {status.stale ? (
        <p className="act-note act-note--warning">
          {`Sem mensagem do atuador há ${age}: o estado abaixo pode estar desatualizado.`}
        </p>
      ) : null}
      <Facts
        items={[
          ['Saída', outputLabel(status.output_on)],
          [
            'Uso na última hora',
            used === null ? 'Não informado' : `${used} s de ${ACTUATOR_HOURLY_BUDGET_S} s`,
          ],
          ['Última mensagem', `${formatDateTime(status.received_at)} (há ${age})`],
          ['Identificador', status.actuator_id],
        ]}
      />
      {used === null ? null : (
        <progress
          className="act-meter"
          max={ACTUATOR_HOURLY_BUDGET_S}
          value={Math.min(used, ACTUATOR_HOURLY_BUDGET_S)}
          aria-label="Uso do orçamento de saída ligada na última hora"
        />
      )}
    </CardShell>
  )
}

export function ActuatorCard() {
  const { data, error } = usePolling(fetchStatus, ACTUATION_POLL_MS)

  if (data !== null) return <Details status={data} outdated={error !== null} />

  if (error === null) {
    return (
      <CardShell id={TITLE_ID} title="Atuador" busy>
        <div className="act-skeleton" aria-hidden="true" />
        <span className="visually-hidden">Carregando</span>
      </CardShell>
    )
  }

  if (error instanceof ApiError && error.status === 404) {
    return (
      <CardShell id={TITLE_ID} title="Atuador">
        <p className="act-note">
          O controlador ainda não recebeu nenhum estado de <code>{ACTUATOR_ID}</code>. Inicie o
          atuador (<code>scripts/run-actuator.ps1</code>) e o controlador.
        </p>
      </CardShell>
    )
  }

  return (
    <CardShell id={TITLE_ID} title="Atuador">
      <ErrorNotice title="Não foi possível ler o estado do atuador" message={error.message} />
    </CardShell>
  )
}

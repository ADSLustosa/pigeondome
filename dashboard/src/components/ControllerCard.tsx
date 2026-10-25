import type { Controller } from '../api/types'
import { controllerSummary, modeInfo } from '../lib/actuation'
import { formatAge, formatDateTime } from '../lib/format'
import { CardShell, Facts } from './CardShell'
import { Chip } from './Chip'

const TITLE_ID = 'controller-title'

interface ControllerCardProps {
  data: Controller | null
  /** A leitura do controlador falhou e não há dado anterior. */
  failed: boolean
  /** Há dado anterior, mas a última atualização falhou. */
  outdated: boolean
}

export function ControllerCard({ data, failed, outdated }: ControllerCardProps) {
  if (data === null) {
    return (
      <CardShell id={TITLE_ID} title="Controlador" busy={!failed}>
        {failed ? (
          <p className="act-note act-note--warning">Sem dados do controlador no momento.</p>
        ) : (
          <>
            <div className="act-skeleton" aria-hidden="true" />
            <span className="visually-hidden">Carregando</span>
          </>
        )}
      </CardShell>
    )
  }

  const summary = controllerSummary(data)
  const mode = data.mode === null ? null : modeInfo(data.mode)
  const age = data.age_s === null ? null : formatAge(data.age_s)
  const silence = age === null ? '' : ` há ${age}`

  return (
    <CardShell
      id={TITLE_ID}
      title="Controlador"
      outdated={outdated}
      chip={<Chip tone={summary.tone}>{summary.label}</Chip>}
    >
      {mode === null ? (
        <p className="act-note">
          O controlador ainda não rodou. Inicie com <code>scripts/run-controller.ps1</code>.
        </p>
      ) : (
        <>
          <p className="act-mode">
            <Chip tone={mode.tone}>{mode.label}</Chip>
            {mode.hint ? <span>{mode.hint}</span> : null}
          </p>
          {!data.running ? (
            <p className="act-note act-note--warning">
              {`Sem batimento${silence}. Nenhuma decisão está sendo tomada.`}
            </p>
          ) : null}
          <Facts
            items={[
              ['Último batimento', age === null ? '—' : `há ${age}`],
              ['Iniciado em', data.started_at === null ? '—' : formatDateTime(data.started_at)],
              ['Câmera', data.camera_id ?? '—'],
              ['Atuador', data.actuator_id ?? '—'],
            ]}
          />
        </>
      )}
    </CardShell>
  )
}

import { CAMERA_POLL_MS, CAMERA_STALE_AFTER_S } from '../config'
import { useLiveFrame } from '../hooks/useLiveFrame'
import { describeFrame, frameChip } from '../lib/camera'
import { formatAge } from '../lib/format'
import { Chip } from './Chip'

interface LiveCameraProps {
  deviceId: string
  pollMs?: number
  staleAfterS?: number
}

export function LiveCamera({
  deviceId,
  pollMs = CAMERA_POLL_MS,
  staleAfterS = CAMERA_STALE_AFTER_S,
}: LiveCameraProps) {
  const frame = useLiveFrame(deviceId, pollMs)
  const { status, ageS } = describeFrame(frame, staleAfterS)
  const chip = frameChip(status)

  return (
    <div className="cam">
      {/* só o rótulo do estado é anunciado; a idade (que muda todo segundo) fica fora */}
      <p className="cam__status" role="status">
        <Chip tone={chip.tone}>{chip.label}</Chip>
      </p>

      <div className={`cam__frame cam__frame--${status}`}>
        {frame.url !== null && status !== 'unconfigured' ? (
          <img
            className="cam__image"
            src={frame.url}
            width={320}
            height={240}
            alt={`Imagem da câmera ${deviceId}`}
          />
        ) : (
          <div className="cam__placeholder" aria-hidden="true" />
        )}
      </div>

      {status === 'stale' && ageS !== null ? (
        <p className="act-note act-note--warning">
          {`Último quadro há ${formatAge(ageS)}: a imagem acima está desatualizada.`}
        </p>
      ) : null}
      {status === 'unavailable' ? (
        <p className="act-note act-note--danger">
          A API não conseguiu obter a imagem. Confira se a câmera (ou o simulador) está no ar.
        </p>
      ) : null}
      {status === 'unconfigured' ? (
        <p className="act-note">
          A API não tem câmera configurada para <code>{deviceId}</code>. Defina{' '}
          <code>CAMERA_SNAPSHOT_URLS</code> e reinicie a API.
        </p>
      ) : null}

      <p className="act-hint">A imagem só passa pela API: não é gravada nem guardada em cache.</p>
    </div>
  )
}

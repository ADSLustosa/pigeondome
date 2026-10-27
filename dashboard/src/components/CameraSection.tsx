import { useState } from 'react'
import { CAMERA_POLL_MS } from '../config'
import { isNarrowScreen } from '../lib/paging'
import { LiveCamera } from './LiveCamera'

interface CameraSectionProps {
  deviceId: string
  pollMs?: number
}

export function CameraSection({ deviceId, pollMs = CAMERA_POLL_MS }: CameraSectionProps) {
  // no celular começa fechado: a página fica curta e nenhum quadro é pedido sem necessidade
  const [open, setOpen] = useState(() => !isNarrowScreen())

  return (
    <section aria-labelledby="camera-title">
      <div className="section-head">
        <h2 id="camera-title" className="section-title">
          Câmera ao vivo
        </h2>
        <p className="section-subtitle">{deviceId}</p>
      </div>

      <button
        type="button"
        className="cam__toggle"
        aria-expanded={open}
        aria-controls="camera-panel"
        onClick={() => setOpen((value) => !value)}
      >
        {open ? 'Ocultar a imagem' : 'Mostrar a imagem ao vivo'}
      </button>

      <div id="camera-panel" hidden={!open}>
        {open ? <LiveCamera key={deviceId} deviceId={deviceId} pollMs={pollMs} /> : null}
      </div>
    </section>
  )
}

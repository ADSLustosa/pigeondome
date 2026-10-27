import { useCallback, useState } from 'react'
import { listDevices } from './api/client'
import { ActuationSection } from './components/ActuationSection'
import { CameraSection } from './components/CameraSection'
import { Controls } from './components/Controls'
import { ErrorNotice } from './components/ErrorNotice'
import { Header } from './components/Header'
import { PresencePanel } from './components/PresencePanel'
import { SeriesSection } from './components/SeriesSection'
import type { ConnectionStatus } from './components/StatusChip'
import { TrailSection } from './components/TrailSection'
import { DEVICES_POLL_MS } from './config'
import { usePolling } from './hooks/usePolling'
import { useTheme } from './hooks/useTheme'
import { DEFAULT_WINDOW_ID, presetById } from './lib/windows'
import type { WindowId } from './lib/windows'
import './styles/actuation.css'
import './styles/camera.css'

export default function App() {
  const { theme, toggle } = useTheme()
  const [selectedDevice, setSelectedDevice] = useState<string | null>(null)
  const [windowId, setWindowId] = useState<WindowId>(DEFAULT_WINDOW_ID)

  const fetchDevices = useCallback((signal: AbortSignal) => listDevices(signal), [])
  const devices = usePolling(fetchDevices, DEVICES_POLL_MS)

  const deviceList = devices.data ?? []
  const deviceId = selectedDevice ?? deviceList[0]?.device_id ?? null
  const preset = presetById(windowId)

  let status: ConnectionStatus = 'connecting'
  if (devices.error) status = 'offline'
  else if (devices.data) status = 'online'

  return (
    <>
      <a className="skip-link" href="#conteudo">
        Ir para o conteúdo
      </a>
      <Header status={status} theme={theme} onToggleTheme={toggle} />
      <main id="conteudo" className="container page">
        {devices.error && !devices.data ? (
          <ErrorNotice
            title="Sem conexão com a API"
            message={`${devices.error.message}. Confira se a API está no ar (scripts/run-api.ps1).`}
          />
        ) : null}

        {devices.data ? <ActuationSection /> : null}

        {devices.data && deviceList.length === 0 ? (
          <div className="empty-state">
            <strong>Nenhum dispositivo enviou dados ainda</strong>
            <span>
              Inicie o simulador com <code>scripts/run-simulator.ps1</code> e o backend com{' '}
              <code>scripts/run-backend.ps1</code>.
            </span>
          </div>
        ) : null}

        {deviceList.length > 0 && deviceId ? (
          <>
            <Controls
              devices={deviceList}
              deviceId={deviceId}
              onDeviceChange={setSelectedDevice}
              windowId={windowId}
              onWindowChange={setWindowId}
            />
            <CameraSection deviceId={deviceId} />
            <PresencePanel key={`presence:${deviceId}:${windowId}`} deviceId={deviceId} preset={preset} />
            <SeriesSection key={`series:${deviceId}:${windowId}`} deviceId={deviceId} preset={preset} />
          </>
        ) : null}

        {devices.data ? <TrailSection /> : null}
      </main>
    </>
  )
}

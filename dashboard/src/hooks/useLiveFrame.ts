import { useEffect, useState } from 'react'
import { ApiError, getSnapshot } from '../api/client'
import { CAMERA_REQUEST_TIMEOUT_MS } from '../config'
import { INITIAL_FRAME } from '../lib/camera'
import type { FrameState } from '../lib/camera'

/**
 * Pede o quadro da câmera, espera a resposta e só então agenda o próximo: nunca há dois pedidos
 * juntos. Não pede nada com a aba escondida (e pede na hora ao voltar) e para de vez se a API
 * disser que não há câmera configurada. Para recomeçar do zero ao trocar de dispositivo, quem usa
 * o hook deve remontá-lo com `key`.
 */
export function useLiveFrame(deviceId: string, intervalMs: number): FrameState {
  const [frame, setFrame] = useState<FrameState>(INITIAL_FRAME)

  useEffect(() => {
    let cancelled = false
    let stopped = false
    let inFlight = false
    let current: string | null = null
    let timer: ReturnType<typeof setTimeout> | undefined
    let controller: AbortController | null = null

    const run = async (): Promise<void> => {
      if (cancelled || stopped || inFlight) return
      if (!document.hidden) {
        inFlight = true
        const attempt = new AbortController()
        controller = attempt
        const timeout = setTimeout(() => attempt.abort(), CAMERA_REQUEST_TIMEOUT_MS)
        try {
          const blob = await getSnapshot(deviceId, attempt.signal)
          if (cancelled) return
          const url = URL.createObjectURL(blob)
          const previous = current
          current = url
          const at = performance.now()
          setFrame({ url, okAt: at, now: at, failure: null })
          if (previous !== null) URL.revokeObjectURL(previous)
        } catch (error) {
          if (cancelled) return
          const at = performance.now()
          if (error instanceof ApiError && error.status === 404) {
            stopped = true
            setFrame((previous) => ({ ...previous, now: at, failure: 'unconfigured' }))
            return
          }
          setFrame((previous) => ({ ...previous, now: at, failure: 'unavailable' }))
        } finally {
          clearTimeout(timeout)
          inFlight = false
        }
      }
      timer = setTimeout(run, intervalMs)
    }

    const onVisibilityChange = () => {
      if (document.hidden) return
      clearTimeout(timer)
      void run()
    }

    document.addEventListener('visibilitychange', onVisibilityChange)
    void run()
    return () => {
      cancelled = true
      clearTimeout(timer)
      controller?.abort()
      document.removeEventListener('visibilitychange', onVisibilityChange)
      if (current !== null) URL.revokeObjectURL(current)
    }
  }, [deviceId, intervalMs])

  // a idade do quadro cresce sozinha: sem isto o "Ao vivo" ficaria parado se os pedidos
  // deixassem de terminar
  useEffect(() => {
    const id = setInterval(() => {
      const at = performance.now()
      setFrame((previous) => ({ ...previous, now: at }))
    }, Math.min(intervalMs, 1000))
    return () => clearInterval(id)
  }, [intervalMs])

  return frame
}

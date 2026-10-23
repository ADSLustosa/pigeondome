import { useEffect, useState } from 'react'

export interface PollingState<T> {
  data: T | null
  error: Error | null
  updatedAt: Date | null
}

function toError(value: unknown): Error {
  return value instanceof Error ? value : new Error(String(value))
}

/**
 * Executa `fetcher` agora e depois a cada `intervalMs`.
 * `fetcher` precisa ser estável (useCallback). Para recomeçar do zero ao mudar de
 * dispositivo ou período, o componente que usa o hook deve ser remontado com `key`.
 */
export function usePolling<T>(
  fetcher: (signal: AbortSignal) => Promise<T>,
  intervalMs: number,
): PollingState<T> {
  const [state, setState] = useState<PollingState<T>>({ data: null, error: null, updatedAt: null })

  useEffect(() => {
    const controller = new AbortController()
    let timer: ReturnType<typeof setTimeout> | undefined

    const run = async () => {
      try {
        const data = await fetcher(controller.signal)
        if (controller.signal.aborted) return
        setState({ data, error: null, updatedAt: new Date() })
      } catch (error) {
        if (controller.signal.aborted) return
        setState((previous) => ({ ...previous, error: toError(error) }))
      }
      if (!controller.signal.aborted) timer = setTimeout(run, intervalMs)
    }

    void run()
    return () => {
      controller.abort()
      clearTimeout(timer)
    }
  }, [fetcher, intervalMs])

  return state
}

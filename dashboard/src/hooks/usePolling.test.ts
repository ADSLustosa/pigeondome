import { act, renderHook, waitFor } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { usePolling } from './usePolling'

describe('usePolling', () => {
  it('busca na hora e entrega o dado', async () => {
    const fetcher = vi.fn<(signal: AbortSignal) => Promise<string>>().mockResolvedValue('ok')
    const { result } = renderHook(() => usePolling(fetcher, 60_000))
    await waitFor(() => expect(result.current.data).toBe('ok'))
    expect(result.current.error).toBeNull()
    expect(fetcher).toHaveBeenCalledTimes(1)
  })

  it('refresh busca de novo na hora, sem esperar o intervalo', async () => {
    const fetcher = vi.fn<(signal: AbortSignal) => Promise<string>>().mockResolvedValue('ok')
    const { result } = renderHook(() => usePolling(fetcher, 60_000))
    await waitFor(() => expect(result.current.data).toBe('ok'))
    act(() => {
      result.current.refresh()
    })
    await waitFor(() => expect(fetcher).toHaveBeenCalledTimes(2))
  })

  it('mantém o dado anterior quando uma atualização falha', async () => {
    const fetcher = vi
      .fn<(signal: AbortSignal) => Promise<string>>()
      .mockResolvedValueOnce('primeiro')
      .mockRejectedValue(new Error('falhou'))
    const { result } = renderHook(() => usePolling(fetcher, 60_000))
    await waitFor(() => expect(result.current.data).toBe('primeiro'))
    act(() => {
      result.current.refresh()
    })
    await waitFor(() => expect(result.current.error?.message).toBe('falhou'))
    expect(result.current.data).toBe('primeiro')
  })
})

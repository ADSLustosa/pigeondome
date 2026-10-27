import { act, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { get, jpeg, mockApi } from '../test/api'
import { CameraSection } from './CameraSection'

const SNAPSHOT_01 = '/devices/cam-sim-01/snapshot'
const SNAPSHOT_02 = '/devices/cam-sim-02/snapshot'

const settle = (ms: number) =>
  act(async () => {
    await new Promise<void>((resolve) => setTimeout(resolve, ms))
  })

const originalMatchMedia = window.matchMedia.bind(window)

function narrowScreen() {
  window.matchMedia = vi
    .fn()
    .mockReturnValue({ matches: true }) as unknown as typeof window.matchMedia
}

beforeEach(() => {
  let counter = 0
  URL.createObjectURL = vi.fn(() => {
    counter += 1
    return `blob:mock-${counter}`
  })
  URL.revokeObjectURL = vi.fn()
})

afterEach(() => {
  window.matchMedia = originalMatchMedia
})

describe('CameraSection', () => {
  it('em tela larga começa aberta e já mostra a imagem', async () => {
    mockApi([get(SNAPSHOT_01, jpeg)])
    render(<CameraSection deviceId="cam-sim-01" pollMs={20} />)
    expect(screen.getByRole('heading', { name: 'Câmera ao vivo' })).toBeInTheDocument()
    const toggle = screen.getByRole('button', { name: 'Ocultar a imagem' })
    expect(toggle).toHaveAttribute('aria-expanded', 'true')
    expect(await screen.findByText('Ao vivo')).toBeInTheDocument()
  })

  it('em tela estreita começa fechada, sem pedir nada, e abre ao clicar', async () => {
    narrowScreen()
    const api = mockApi([get(SNAPSHOT_01, jpeg)])
    render(<CameraSection deviceId="cam-sim-01" pollMs={20} />)
    const toggle = screen.getByRole('button', { name: 'Mostrar a imagem ao vivo' })
    expect(toggle).toHaveAttribute('aria-expanded', 'false')
    expect(document.getElementById('camera-panel')).toHaveAttribute('hidden')
    await settle(100)
    expect(api.calls).toHaveLength(0)

    fireEvent.click(toggle)
    expect(await screen.findByText('Ao vivo')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Ocultar a imagem' })).toHaveAttribute(
      'aria-expanded',
      'true',
    )
  })

  it('ao ocultar a imagem, para de pedir quadros', async () => {
    const api = mockApi([get(SNAPSHOT_01, jpeg)])
    render(<CameraSection deviceId="cam-sim-01" pollMs={20} />)
    await screen.findByText('Ao vivo')
    fireEvent.click(screen.getByRole('button', { name: 'Ocultar a imagem' }))
    const before = api.calls.length
    await settle(120)
    expect(api.calls.length).toBe(before)
    expect(screen.queryByRole('img')).not.toBeInTheDocument()
  })

  it('ao trocar de dispositivo, descarta o quadro antigo e pede o do novo', async () => {
    const api = mockApi([get(SNAPSHOT_01, jpeg), get(SNAPSHOT_02, jpeg)])
    const { rerender } = render(<CameraSection deviceId="cam-sim-01" pollMs={20} />)
    await screen.findByText('Ao vivo')
    rerender(<CameraSection deviceId="cam-sim-02" pollMs={20} />)
    await waitFor(() =>
      expect(api.calls.some((call) => call.url.includes('cam-sim-02'))).toBe(true),
    )
    expect(screen.getByText('cam-sim-02')).toBeInTheDocument()
  })
})

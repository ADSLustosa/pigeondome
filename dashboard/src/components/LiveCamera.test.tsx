import { act, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { get, jpeg, mockApi, problem } from '../test/api'
import { LiveCamera } from './LiveCamera'

const SNAPSHOT = '/devices/cam-sim-01/snapshot'
const created: string[] = []
const revoked: string[] = []

/** Espera de verdade (os temporizadores são reais, de poucos milissegundos). */
const settle = (ms: number) =>
  act(async () => {
    await new Promise<void>((resolve) => setTimeout(resolve, ms))
  })

function setHidden(hidden: boolean) {
  Object.defineProperty(document, 'hidden', { configurable: true, get: () => hidden })
}

beforeEach(() => {
  created.length = 0
  revoked.length = 0
  let counter = 0
  // o jsdom não implementa os endereços blob:
  URL.createObjectURL = vi.fn(() => {
    counter += 1
    const url = `blob:mock-${counter}`
    created.push(url)
    return url
  })
  URL.revokeObjectURL = vi.fn((url: string) => {
    revoked.push(url)
  })
  setHidden(false)
})

afterEach(() => {
  Reflect.deleteProperty(document, 'hidden')
})

describe('LiveCamera', () => {
  it('mostra "Ao vivo" e a imagem assim que o primeiro quadro chega', async () => {
    const api = mockApi([get(SNAPSHOT, jpeg)])
    render(<LiveCamera deviceId="cam-sim-01" pollMs={20} />)
    expect(await screen.findByText('Ao vivo')).toBeInTheDocument()
    const image = screen.getByRole('img', { name: 'Imagem da câmera cam-sim-01' })
    expect(image.getAttribute('src')).toMatch(/^blob:mock-\d+$/)
    expect(api.calls[0]?.headers.get('Accept')).toBe('image/jpeg')
    expect(screen.getByText(/não é gravada/)).toBeInTheDocument()
  })

  it('mostra "Carregando" antes do primeiro quadro', async () => {
    mockApi([get(SNAPSHOT, jpeg)])
    render(<LiveCamera deviceId="cam-sim-01" pollMs={20} />)
    expect(screen.getByText('Carregando')).toBeInTheDocument()
    expect(screen.queryByRole('img')).not.toBeInTheDocument()
    await screen.findByText('Ao vivo')
  })

  it('vira "Sem sinal" quando os quadros deixam de chegar e apaga a imagem velha', async () => {
    let requests = 0
    mockApi([
      get(SNAPSHOT, () => {
        requests += 1
        return requests === 1 ? jpeg() : problem(503, 'camera fora')
      }),
    ])
    const { container } = render(
      <LiveCamera deviceId="cam-sim-01" pollMs={20} staleAfterS={0.2} />,
    )
    expect(await screen.findByText('Ao vivo')).toBeInTheDocument()
    expect(await screen.findByText('Sem sinal')).toBeInTheDocument()
    expect(screen.getByText(/Último quadro há/)).toBeInTheDocument()
    expect(container.querySelector('.cam__frame')).toHaveClass('cam__frame--stale')
    expect(screen.getByRole('img')).toBeInTheDocument()
  })

  it('mostra "Sem imagem" e orienta quando a câmera nunca respondeu', async () => {
    mockApi([get(SNAPSHOT, () => problem(502, 'não foi possível obter o quadro da câmera'))])
    render(<LiveCamera deviceId="cam-sim-01" pollMs={20} />)
    expect(await screen.findByText('Sem imagem')).toBeInTheDocument()
    expect(screen.getByText(/câmera \(ou o simulador\)/)).toBeInTheDocument()
    expect(screen.queryByRole('img')).not.toBeInTheDocument()
  })

  it('avisa que não há câmera configurada e para de pedir quadros', async () => {
    const api = mockApi([get(SNAPSHOT, () => problem(404, 'nenhuma câmera configurada'))])
    render(<LiveCamera deviceId="cam-sim-01" pollMs={20} />)
    expect(await screen.findByText('Não configurada')).toBeInTheDocument()
    expect(screen.getByText('CAMERA_SNAPSHOT_URLS')).toBeInTheDocument()
    await settle(150)
    expect(api.calls).toHaveLength(1)
  })

  it('libera cada endereço de imagem ao trocar de quadro e ao sair da tela', async () => {
    mockApi([get(SNAPSHOT, jpeg)])
    const { unmount } = render(<LiveCamera deviceId="cam-sim-01" pollMs={20} />)
    await waitFor(() => expect(revoked).toContain('blob:mock-1'))
    unmount()
    expect([...revoked].sort()).toEqual([...created].sort())
  })

  it('não pede quadros com a aba escondida e pede na hora ao voltar', async () => {
    setHidden(true)
    const api = mockApi([get(SNAPSHOT, jpeg)])
    render(<LiveCamera deviceId="cam-sim-01" pollMs={20} />)
    await settle(120)
    expect(api.calls).toHaveLength(0)
    setHidden(false)
    document.dispatchEvent(new Event('visibilitychange'))
    expect(await screen.findByText('Ao vivo')).toBeInTheDocument()
    expect(api.calls.length).toBeGreaterThan(0)
  })
})

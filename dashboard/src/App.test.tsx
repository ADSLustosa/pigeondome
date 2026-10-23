import { render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import App from './App'

const DEVICES = [{ device_id: 'cam-sim-01', readings: 57, last_detected_at: '2026-10-22T22:32:37Z' }]
const PRESENCE = {
  device_id: 'cam-sim-01',
  start: '2026-10-22T21:33:00Z',
  end: '2026-10-22T22:33:00Z',
  readings: 57,
  readings_with_pigeons: 54,
  presence_rate: 0.9473684,
  mean_pigeons: 3.9824561,
  max_pigeons: 8,
}

function json(body: unknown): Response {
  return new Response(JSON.stringify(body), { headers: { 'content-type': 'application/json' } })
}

/** Simula a API: a primeira rota cujo fragmento aparece na URL responde. */
function mockApi(routes: [fragment: string, body: unknown][]) {
  vi.stubGlobal(
    'fetch',
    vi.fn((input: RequestInfo | URL) => {
      const url = String(input)
      const route = routes.find(([fragment]) => url.includes(fragment))
      return Promise.resolve(route ? json(route[1]) : new Response('{}', { status: 404 }))
    }),
  )
}

describe('App', () => {
  it('mostra os indicadores do dispositivo selecionado', async () => {
    mockApi([
      ['/devices/cam-sim-01/presence', PRESENCE],
      ['/devices', DEVICES],
    ])
    render(<App />)
    expect(await screen.findByRole('combobox', { name: /dispositivo/i })).toHaveValue('cam-sim-01')
    expect(await screen.findByText('57')).toBeInTheDocument()
    expect(screen.getByText('94,7%')).toBeInTheDocument()
    expect(screen.getByText('4,0')).toBeInTheDocument()
    expect(screen.getByText('API online')).toBeInTheDocument()
  })

  it('avisa quando a API está fora do ar', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('Failed to fetch')))
    render(<App />)
    expect(await screen.findByRole('alert')).toHaveTextContent('Não foi possível conectar à API')
    expect(screen.getByText('Sem conexão')).toBeInTheDocument()
  })

  it('explica o que fazer quando ainda não há dispositivos', async () => {
    mockApi([['/devices', []]])
    render(<App />)
    expect(await screen.findByText('Nenhum dispositivo enviou dados ainda')).toBeInTheDocument()
  })
})

import { render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import App from './App'
import { get, mockApi, ok } from './test/api'
import { ACTUATOR, CONTROLLER, DECISIONS, EVENTS } from './test/fixtures'

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
const SERIES = {
  device_id: 'cam-sim-01',
  start: '2026-10-22T21:33:00Z',
  end: '2026-10-22T22:33:00Z',
  bucket: '1m',
  points: [],
}

describe('App com a atuação', () => {
  it('mostra o painel de atuação e a trilha quando a API responde', async () => {
    mockApi([
      get('/devices/cam-sim-01/presence/series', ok(SERIES)),
      get('/devices/cam-sim-01/presence', ok(PRESENCE)),
      get('/devices', ok(DEVICES)),
      get('/controller', ok(CONTROLLER)),
      get('/actuators/act-sim-01/status', ok(ACTUATOR)),
      get('/actuators/act-sim-01/decisions', ok(DECISIONS)),
      get('/actuators/act-sim-01/events', ok(EVENTS)),
    ])
    render(<App />)
    expect(await screen.findByRole('heading', { name: 'Atuação' })).toBeInTheDocument()
    expect(await screen.findByRole('heading', { name: 'Trilha do controlador' })).toBeInTheDocument()
    expect(
      await screen.findByRole('table', { name: /decisões do controlador/i }),
    ).toBeInTheDocument()
    expect(await screen.findByRole('table', { name: /eventos do atuador/i })).toBeInTheDocument()
  })

  it('não mostra a atuação enquanto a API não responde', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('Failed to fetch')))
    render(<App />)
    expect(await screen.findByRole('alert')).toHaveTextContent('Não foi possível conectar à API')
    expect(screen.queryByRole('heading', { name: 'Atuação' })).not.toBeInTheDocument()
  })
})

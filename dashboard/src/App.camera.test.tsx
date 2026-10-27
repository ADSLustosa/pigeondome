import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import App from './App'
import { get, jpeg, mockApi, ok } from './test/api'
import {
  ACTUATOR,
  CONTROLLER,
  DECISIONS,
  DEVICES,
  EVENTS,
  PRESENCE,
  SERIES,
} from './test/fixtures'

describe('App com a câmera', () => {
  it('mostra a câmera ao vivo do dispositivo selecionado', async () => {
    mockApi([
      get('/devices/cam-sim-01/snapshot', jpeg),
      get('/devices/cam-sim-01/presence/series', ok(SERIES)),
      get('/devices/cam-sim-01/presence', ok(PRESENCE)),
      get('/devices', ok(DEVICES)),
      get('/controller', ok(CONTROLLER)),
      get('/actuators/act-sim-01/status', ok(ACTUATOR)),
      get('/actuators/act-sim-01/decisions', ok(DECISIONS)),
      get('/actuators/act-sim-01/events', ok(EVENTS)),
    ])
    render(<App />)
    expect(await screen.findByRole('heading', { name: 'Câmera ao vivo' })).toBeInTheDocument()
    expect(await screen.findByText('Ao vivo')).toBeInTheDocument()
  })
})

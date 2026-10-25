import { describe, expect, it } from 'vitest'
import { get, mockApi, ok, post, problem } from '../test/api'
import { ACTUATOR, CONTROLLER, DECISIONS, EVENTS } from '../test/fixtures'
import {
  engageKillSwitch,
  getActuatorEvents,
  getActuatorStatus,
  getController,
  getDecisions,
} from './client'

describe('cliente da API de atuação', () => {
  it('lê o estado do controlador', async () => {
    const api = mockApi([get('/api/v1/controller', ok(CONTROLLER))])
    expect(await getController()).toEqual(CONTROLLER)
    expect(api.calls[0]).toMatchObject({ method: 'GET' })
  })

  it('lê o estado do atuador com o identificador codificado', async () => {
    const api = mockApi([get('/status', ok(ACTUATOR))])
    await getActuatorStatus('act sim/01')
    expect(api.calls[0]?.url).toContain('/api/v1/actuators/act%20sim%2F01/status')
  })

  it('pede as decisões com o limite', async () => {
    const api = mockApi([get('/decisions', ok(DECISIONS))])
    expect(await getDecisions('act-sim-01', 50)).toEqual(DECISIONS)
    expect(api.calls[0]?.url).toContain('/api/v1/actuators/act-sim-01/decisions?limit=50')
  })

  it('pede os eventos com o limite', async () => {
    const api = mockApi([get('/events', ok(EVENTS))])
    expect(await getActuatorEvents('act-sim-01', 25)).toEqual(EVENTS)
    expect(api.calls[0]?.url).toContain('/api/v1/actuators/act-sim-01/events?limit=25')
  })

  it('liga a chave geral com POST e o cabeçalho de confirmação', async () => {
    const api = mockApi([post('/controller/kill-switch', ok({ kill_switch: true }))])
    expect(await engageKillSwitch()).toEqual({ kill_switch: true })
    expect(api.calls[0]?.method).toBe('POST')
    expect(api.calls[0]?.headers.get('X-Pigeondome-Action')).toBe('kill-switch-on')
  })

  it('transforma a recusa da chave geral em ApiError com o detalhe da API', async () => {
    mockApi([
      post('/controller/kill-switch', () => problem(403, 'envie o cabeçalho de confirmação')),
    ])
    await expect(engageKillSwitch()).rejects.toMatchObject({
      name: 'ApiError',
      status: 403,
      message: 'envie o cabeçalho de confirmação',
    })
  })
})

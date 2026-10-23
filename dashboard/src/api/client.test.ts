import { describe, expect, it, vi } from 'vitest'
import { getPresence, getSeries, listDevices } from './client'

const RANGE = { start: '2026-10-22T22:00:00.000Z', end: '2026-10-22T23:00:00.000Z' }

function respond(body: unknown, status = 200, type = 'application/json'): Response {
  return new Response(JSON.stringify(body), { status, headers: { 'content-type': type } })
}

describe('cliente da API', () => {
  it('devolve o JSON de uma resposta de sucesso', async () => {
    const devices = [{ device_id: 'cam-sim-01', readings: 3, last_detected_at: '2026-10-22T22:00:00Z' }]
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(respond(devices)))
    const result = await listDevices()
    expect(result[0]?.device_id).toBe('cam-sim-01')
  })

  it('transforma problem+json em ApiError com o detalhe da API', async () => {
    const problem = {
      type: 'urn:pigeondome:erro:dispositivo-desconhecido',
      title: 'Dispositivo desconhecido',
      status: 404,
      detail: 'nenhum dado recebido do dispositivo',
    }
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(respond(problem, 404, 'application/problem+json')))
    await expect(getPresence('cam-x', RANGE)).rejects.toMatchObject({
      name: 'ApiError',
      status: 404,
      message: 'nenhum dado recebido do dispositivo',
    })
  })

  it('usa uma mensagem genérica quando o erro não é problem+json', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(respond({}, 500)))
    await expect(listDevices()).rejects.toMatchObject({ status: 500, message: 'A API respondeu com erro 500' })
  })

  it('converte falha de rede em ApiError com status 0', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('Failed to fetch')))
    await expect(listDevices()).rejects.toMatchObject({
      status: 0,
      message: 'Não foi possível conectar à API',
    })
  })

  it('pede a série com o tamanho do intervalo', async () => {
    const fetchMock = vi.fn().mockResolvedValue(respond({ points: [] }))
    vi.stubGlobal('fetch', fetchMock)
    await getSeries('cam-sim-01', RANGE, '5m')
    const url = String(fetchMock.mock.calls[0]?.[0])
    expect(url).toContain('/presence/series?')
    expect(url).toContain('bucket=5m')
  })

  it('codifica o identificador e envia a janela na URL', async () => {
    const fetchMock = vi.fn().mockResolvedValue(respond({}))
    vi.stubGlobal('fetch', fetchMock)
    await getPresence('cam-sim-01', RANGE)
    const url = String(fetchMock.mock.calls[0]?.[0])
    expect(url).toContain('/api/v1/devices/cam-sim-01/presence?')
    expect(url).toContain('start=2026-10-22T22%3A00%3A00.000Z')
  })
})

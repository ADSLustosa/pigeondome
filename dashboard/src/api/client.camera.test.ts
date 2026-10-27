import { describe, expect, it } from 'vitest'
import { get, mockApi, ok, problem, jpeg } from '../test/api'
import { getSnapshot } from './client'

describe('cliente da câmera', () => {
  it('devolve o quadro JPEG e pede image/jpeg', async () => {
    const api = mockApi([get('/devices/cam-sim-01/snapshot', jpeg)])
    const frame = await getSnapshot('cam-sim-01')
    expect(frame.size).toBe(4)
    expect(api.calls[0]?.method).toBe('GET')
    expect(api.calls[0]?.headers.get('Accept')).toBe('image/jpeg')
  })

  it('codifica o identificador do dispositivo na URL', async () => {
    const api = mockApi([get('/snapshot', jpeg)])
    await getSnapshot('cam sim/01')
    expect(api.calls[0]?.url).toContain('/api/v1/devices/cam%20sim%2F01/snapshot')
  })

  it('transforma a câmera não configurada em ApiError 404 com o detalhe da API', async () => {
    mockApi([get('/snapshot', () => problem(404, 'nenhuma câmera configurada'))])
    await expect(getSnapshot('cam-sim-01')).rejects.toMatchObject({
      name: 'ApiError',
      status: 404,
      message: 'nenhuma câmera configurada',
    })
  })

  it('recusa uma resposta que não é uma imagem', async () => {
    mockApi([get('/snapshot', ok({}))])
    await expect(getSnapshot('cam-sim-01')).rejects.toMatchObject({
      name: 'ApiError',
      message: 'A API não devolveu uma imagem',
    })
  })
})

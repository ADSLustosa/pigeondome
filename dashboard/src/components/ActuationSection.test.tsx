import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { get, json, mockApi, ok, post, problem } from '../test/api'
import { ACTUATOR, CONTROLLER } from '../test/fixtures'
import { ActuationSection } from './ActuationSection'

const STATUS = '/actuators/act-sim-01/status'

describe('ActuationSection', () => {
  it('mostra o controlador, o atuador e a chave geral', async () => {
    mockApi([get('/controller', ok(CONTROLLER)), get(STATUS, ok(ACTUATOR))])
    render(<ActuationSection />)
    expect(screen.getByRole('heading', { name: 'Atuação' })).toBeInTheDocument()
    expect(await screen.findByText('Em execução')).toBeInTheDocument()
    expect(await screen.findByText('Pronto')).toBeInTheDocument()
    expect(await screen.findByRole('button', { name: 'Ligar a chave geral' })).toBeEnabled()
  })

  it('liga a chave geral de ponta a ponta e troca o botão pelo aviso', async () => {
    let engaged = false
    const api = mockApi([
      get('/controller', () => json({ ...CONTROLLER, kill_switch: engaged })),
      get(STATUS, ok(ACTUATOR)),
      post('/controller/kill-switch', () => {
        engaged = true
        return json({ kill_switch: true })
      }),
    ])
    render(<ActuationSection />)
    fireEvent.click(await screen.findByRole('button', { name: 'Ligar a chave geral' }))
    expect(await screen.findByText('Ligada')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /ligar a chave geral/i })).not.toBeInTheDocument()
    expect(api.calls.filter((call) => call.method === 'POST')).toHaveLength(1)
  })

  it('avisa quando o controlador não responde, sem esconder o atuador nem oferecer a chave', async () => {
    mockApi([
      get('/controller', () => problem(503, 'o armazenamento de dados está temporariamente indisponível')),
      get(STATUS, ok(ACTUATOR)),
    ])
    render(<ActuationSection />)
    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Não foi possível atualizar o estado do controlador',
    )
    expect(await screen.findByText('Pronto')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Ligar a chave geral' })).not.toBeInTheDocument()
  })
})

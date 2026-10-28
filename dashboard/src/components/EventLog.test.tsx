import { render, screen, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { get, mockApi, ok, problem } from '../test/api'
import { COMMAND_ID, EVENTS, STOP_COMMAND_ID } from '../test/fixtures'
import { EventLog } from './EventLog'

const EVENTS_PATH = '/actuators/act-sim-01/events'

describe('EventLog', () => {
  it('lista os eventos com rótulos em português e o motivo do aborto', async () => {
    const api = mockApi([get(EVENTS_PATH, ok(EVENTS))])
    render(<EventLog />)
    const table = await screen.findByRole('table', { name: /eventos do atuador/i })
    expect(within(table).getAllByRole('row')).toHaveLength(5)
    expect(within(table).getByText('Pulso concluído')).toBeInTheDocument()
    expect(within(table).getByText('Pulso iniciado')).toBeInTheDocument()
    expect(within(table).getByText('Comando aceito')).toBeInTheDocument()
    expect(within(table).getByText('Pulso interrompido')).toBeInTheDocument()
    expect(within(table).getByText('comando de parada')).toBeInTheDocument()
    expect(within(table).getByText('0972ed43')).toBeInTheDocument()
    expect(within(table).getAllByText('3f2b8c1e')).toHaveLength(3)
    expect(api.calls[0]?.url).toContain('limit=50')
  })

  it('diz o que o motivo "desconectado" significa em cada tipo de evento', async () => {
    const events = [
      {
        occurred_at: '2026-10-24T22:30:00Z',
        event: 'command_rejected',
        command_id: STOP_COMMAND_ID,
        reason_code: 'disconnected',
      },
      {
        occurred_at: '2026-10-24T22:20:00Z',
        event: 'pulse_aborted',
        command_id: COMMAND_ID,
        reason_code: 'disconnected',
      },
    ]
    mockApi([get(EVENTS_PATH, ok({ ...EVENTS, events }))])
    render(<EventLog />)
    const table = await screen.findByRole('table', { name: /eventos do atuador/i })
    expect(within(table).getByText('atuador desconectado')).toBeInTheDocument()
    expect(within(table).getByText('conexão encerrada')).toBeInTheDocument()
  })

  it('explica quando não há eventos', async () => {
    mockApi([get(EVENTS_PATH, ok({ ...EVENTS, events: [] }))])
    render(<EventLog />)
    expect(
      await screen.findByText(/Nenhum evento do atuador nas últimas 24 horas/),
    ).toBeInTheDocument()
    expect(screen.queryByRole('table')).not.toBeInTheDocument()
  })

  it('avisa quando há eventos mais antigos do que o limite', async () => {
    mockApi([get(EVENTS_PATH, ok({ ...EVENTS, truncated: true }))])
    render(<EventLog />)
    expect(await screen.findByText(/Mostrando os 50 eventos mais recentes/)).toBeInTheDocument()
  })

  it('mostra o erro quando a API falha', async () => {
    mockApi([
      get(EVENTS_PATH, () => problem(503, 'o armazenamento de dados está temporariamente indisponível')),
    ])
    render(<EventLog />)
    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent('Não foi possível atualizar os eventos')
  })
})

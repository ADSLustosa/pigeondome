import { fireEvent, render, screen, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { get, mockApi, ok, problem } from '../test/api'
import { DECISIONS } from '../test/fixtures'
import { DecisionLog } from './DecisionLog'

const DECISIONS_PATH = '/actuators/act-sim-01/decisions'

describe('DecisionLog', () => {
  it('lista as decisões, da mais recente para a mais antiga', async () => {
    const api = mockApi([get(DECISIONS_PATH, ok(DECISIONS))])
    render(<DecisionLog />)
    const table = await screen.findByRole('table', { name: /decisões do controlador/i })
    expect(within(table).getAllByRole('row')).toHaveLength(4)
    expect(within(table).getByText('Aguardando o intervalo mínimo entre pulsos')).toBeInTheDocument()
    expect(within(table).getByText('Atuador indisponível (pulsando)')).toBeInTheDocument()
    expect(within(table).getByText('Pulso enviado')).toBeInTheDocument()
    expect(within(table).getByText('3f2b8c1e')).toBeInTheDocument()
    expect(within(table).getByText('14 de 15 leituras com pombo · confiança 86%')).toBeInTheDocument()
    expect(api.calls[0]?.url).toContain('limit=50')
  })

  it('filtra só os acionamentos', async () => {
    mockApi([get(DECISIONS_PATH, ok(DECISIONS))])
    render(<DecisionLog />)
    const table = await screen.findByRole('table', { name: /decisões do controlador/i })
    fireEvent.click(screen.getByRole('checkbox', { name: /só acionamentos/i }))
    expect(within(table).getAllByRole('row')).toHaveLength(2)
    expect(within(table).getByText('Pulso enviado')).toBeInTheDocument()
    expect(
      within(table).queryByText('Aguardando o intervalo mínimo entre pulsos'),
    ).not.toBeInTheDocument()
  })

  it('explica quando não há o que mostrar', async () => {
    mockApi([get(DECISIONS_PATH, ok({ ...DECISIONS, decisions: [] }))])
    const first = render(<DecisionLog />)
    expect(await screen.findByText('Nenhuma decisão nas últimas 24 horas.')).toBeInTheDocument()
    expect(screen.queryByRole('table')).not.toBeInTheDocument()
    first.unmount()

    const onlySkips = DECISIONS.decisions.slice(0, 2)
    mockApi([get(DECISIONS_PATH, ok({ ...DECISIONS, decisions: onlySkips }))])
    render(<DecisionLog />)
    await screen.findByRole('table', { name: /decisões do controlador/i })
    fireEvent.click(screen.getByRole('checkbox', { name: /só acionamentos/i }))
    expect(screen.getByText('Nenhum acionamento nas últimas 24 horas.')).toBeInTheDocument()
  })

  it('avisa quando há decisões mais antigas do que o limite', async () => {
    mockApi([get(DECISIONS_PATH, ok({ ...DECISIONS, truncated: true }))])
    render(<DecisionLog />)
    expect(await screen.findByText(/Mostrando as 50 decisões mais recentes/)).toBeInTheDocument()
  })

  it('mostra o erro quando a API falha', async () => {
    mockApi([
      get(DECISIONS_PATH, () => problem(503, 'o armazenamento de dados está temporariamente indisponível')),
    ])
    render(<DecisionLog />)
    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent('Não foi possível atualizar as decisões')
    expect(alert).toHaveTextContent('temporariamente indisponível')
  })
})

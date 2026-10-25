import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { get, mockApi, ok, problem } from '../test/api'
import { ACTUATOR } from '../test/fixtures'
import { ActuatorCard } from './ActuatorCard'

const STATUS = '/actuators/act-sim-01/status'

describe('ActuatorCard', () => {
  it('mostra o estado, a saída e o uso da última hora', async () => {
    mockApi([get(STATUS, ok(ACTUATOR))])
    render(<ActuatorCard />)
    expect(await screen.findByText('Pronto')).toBeInTheDocument()
    expect(screen.getByText('Desligada')).toBeInTheDocument()
    expect(screen.getByText('5 s de 120 s')).toBeInTheDocument()
    expect(screen.getByText(/há 6 s/)).toBeInTheDocument()
    expect(screen.getByRole('progressbar', { name: /orçamento/i })).toHaveAttribute('value', '5')
    expect(screen.getByRole('article', { name: 'Atuador' })).toHaveAttribute('aria-busy', 'false')
  })

  it('mostra o atuador pulsando com a saída ligada', async () => {
    const status = { ...ACTUATOR, state: 'pulsing', output_on: true, budget_used_s_1h: 12 }
    mockApi([get(STATUS, ok(status))])
    render(<ActuatorCard />)
    expect(await screen.findByText('Pulsando')).toBeInTheDocument()
    expect(screen.getByText('Ligada')).toBeInTheDocument()
    expect(screen.getByText('12 s de 120 s')).toBeInTheDocument()
  })

  it('trata o atuador offline como um fato, não como dado velho', async () => {
    const status = { ...ACTUATOR, online: false, state: 'safe_off', age_s: 600 }
    mockApi([get(STATUS, ok(status))])
    render(<ActuatorCard />)
    expect(await screen.findByText('Offline')).toBeInTheDocument()
    expect(screen.getByText(/fora do ar há 10 min/)).toBeInTheDocument()
    expect(screen.queryByText('Sem sinal')).not.toBeInTheDocument()
  })

  it('avisa que o dado pode estar desatualizado quando o atuador some', async () => {
    mockApi([get(STATUS, ok({ ...ACTUATOR, stale: true, age_s: 45 }))])
    render(<ActuatorCard />)
    expect(await screen.findByText('Sem sinal')).toBeInTheDocument()
    expect(screen.getByText(/Sem mensagem do atuador há 45 s/)).toBeInTheDocument()
  })

  it('diz "não informado" para campos que o atuador não relatou', async () => {
    mockApi([get(STATUS, ok({ ...ACTUATOR, output_on: null, budget_used_s_1h: null }))])
    render(<ActuatorCard />)
    expect(await screen.findByText('Pronto')).toBeInTheDocument()
    expect(screen.getByText('Não informada')).toBeInTheDocument()
    expect(screen.getByText('Não informado')).toBeInTheDocument()
    expect(screen.queryByRole('progressbar')).not.toBeInTheDocument()
  })

  it('orienta quando o controlador nunca recebeu o estado do atuador', async () => {
    mockApi([get(STATUS, () => problem(404, 'nenhum estado recebido do atuador'))])
    render(<ActuatorCard />)
    expect(await screen.findByText(/ainda não recebeu nenhum estado de/)).toBeInTheDocument()
    expect(screen.getByText('scripts/run-actuator.ps1')).toBeInTheDocument()
  })

  it('mostra o erro quando a leitura falha por outro motivo', async () => {
    mockApi([
      get(STATUS, () => problem(503, 'o armazenamento de dados está temporariamente indisponível')),
    ])
    render(<ActuatorCard />)
    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent('Não foi possível ler o estado do atuador')
    expect(alert).toHaveTextContent('temporariamente indisponível')
  })
})

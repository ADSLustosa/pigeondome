import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { CONTROLLER } from '../test/fixtures'
import { ControllerCard } from './ControllerCard'

describe('ControllerCard', () => {
  it('mostra modo, batimento e identificadores de um controlador em execução', () => {
    render(<ControllerCard data={CONTROLLER} failed={false} outdated={false} />)
    expect(screen.getByText('Em execução')).toBeInTheDocument()
    expect(screen.getByText('Modo real')).toBeInTheDocument()
    expect(screen.getByText(/envia pulsos reais ao atuador/)).toBeInTheDocument()
    expect(screen.getByText('há 3 s')).toBeInTheDocument()
    expect(screen.getByText('cam-sim-01')).toBeInTheDocument()
    expect(screen.getByText('act-sim-01')).toBeInTheDocument()
  })

  it('avisa quando o controlador parou de bater o coração', () => {
    const data = { ...CONTROLLER, running: false, age_s: 120 }
    render(<ControllerCard data={data} failed={false} outdated={false} />)
    expect(screen.getByText('Parado')).toBeInTheDocument()
    expect(screen.getByText(/Sem batimento há 2 min/)).toBeInTheDocument()
  })

  it('orienta quando o controlador nunca rodou', () => {
    const data = {
      ...CONTROLLER,
      mode: null,
      running: false,
      camera_id: null,
      actuator_id: null,
      started_at: null,
      heartbeat_at: null,
      age_s: null,
    }
    render(<ControllerCard data={data} failed={false} outdated={false} />)
    expect(screen.getByText('Nunca executou')).toBeInTheDocument()
    expect(screen.getByText('scripts/run-controller.ps1')).toBeInTheDocument()
    expect(screen.queryByText('Modo real')).not.toBeInTheDocument()
  })

  it('fica ocupado enquanto carrega', () => {
    render(<ControllerCard data={null} failed={false} outdated={false} />)
    expect(screen.getByRole('article', { name: 'Controlador' })).toHaveAttribute(
      'aria-busy',
      'true',
    )
    expect(screen.getByText('Carregando')).toBeInTheDocument()
  })

  it('diz que não há dados quando a leitura falhou e não há dado anterior', () => {
    render(<ControllerCard data={null} failed outdated={false} />)
    expect(screen.getByText(/Sem dados do controlador/)).toBeInTheDocument()
    expect(screen.getByRole('article', { name: 'Controlador' })).toHaveAttribute(
      'aria-busy',
      'false',
    )
  })

  it('marca o cartão como desatualizado quando a última leitura falhou', () => {
    render(<ControllerCard data={CONTROLLER} failed={false} outdated />)
    expect(screen.getByRole('article', { name: 'Controlador' })).toHaveClass('act-card--outdated')
  })
})

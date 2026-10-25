import { fireEvent, render, screen, within } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import type { ActuatorEvent, Decision } from '../api/types'
import { defaultPageSize } from '../lib/paging'
import { get, mockApi, ok } from '../test/api'
import { COMMAND_ID, DECISIONS, EVENTS } from '../test/fixtures'
import { DecisionLog } from './DecisionLog'
import { EventLog } from './EventLog'

const DECISIONS_PATH = '/actuators/act-sim-01/decisions'
const EVENTS_PATH = '/actuators/act-sim-01/events'

const SKIP: Decision = {
  decided_at: '',
  camera_id: 'cam-sim-01',
  mode: 'live',
  verdict: 'skip',
  reason: 'retry_gap',
  detail: '',
  arm: null,
  duration_s: null,
  command_id: null,
  readings: 15,
  detections: 14,
  mean_confidence: 0.86,
  triggered: false,
}
const PULSE: Decision = {
  ...SKIP,
  verdict: 'pulse',
  reason: 'evidence_confirmed',
  duration_s: 5,
  command_id: COMMAND_ID,
  triggered: true,
}
const STARTED: ActuatorEvent = {
  occurred_at: '',
  event: 'pulse_started',
  command_id: COMMAND_ID,
  reason_code: null,
}

const BASE = Date.parse('2026-10-24T22:00:00Z')
const at = (index: number): string => new Date(BASE - index * 1000).toISOString()

/** `total` decisões, da mais recente para a mais antiga; 1 em cada 4 é um acionamento. */
const manyDecisions = (total: number) => ({
  ...DECISIONS,
  decisions: Array.from({ length: total }, (_, index): Decision => ({
    ...(index % 4 === 0 ? PULSE : SKIP),
    decided_at: at(index),
  })),
})

const manyEvents = (total: number) => ({
  ...EVENTS,
  events: Array.from({ length: total }, (_, index): ActuatorEvent => ({
    ...STARTED,
    occurred_at: at(index),
  })),
})

const dataRows = (table: HTMLElement): number => within(table).getAllByRole('row').length - 1
const decisionTable = () => screen.findByRole('table', { name: /decisões do controlador/i })
const eventTable = () => screen.findByRole('table', { name: /eventos do atuador/i })
const pickSize = (size: string) => fireEvent.click(screen.getByRole('radio', { name: size }))

const originalMatchMedia = window.matchMedia.bind(window)
afterEach(() => {
  window.matchMedia = originalMatchMedia
})

function narrowScreen() {
  window.matchMedia = vi.fn().mockReturnValue({ matches: true }) as unknown as typeof window.matchMedia
}

describe('quantidade de linhas das trilhas', () => {
  it('começa com 10 em tela larga e com 5 em tela estreita', () => {
    expect(defaultPageSize()).toBe(10)
    narrowScreen()
    expect(defaultPageSize()).toBe(5)
  })

  it('mostra 10 decisões por padrão e resume o que ficou de fora', async () => {
    mockApi([get(DECISIONS_PATH, ok(manyDecisions(30)))])
    render(<DecisionLog />)
    const table = await decisionTable()
    expect(dataRows(table)).toBe(10)
    expect(screen.getByRole('radio', { name: '10' })).toBeChecked()
    expect(screen.getByText(/Mostrando 10 de 30 decisões/)).toBeInTheDocument()
  })

  it('aumenta a quantidade e o resumo some quando tudo cabe', async () => {
    mockApi([get(DECISIONS_PATH, ok(manyDecisions(30)))])
    render(<DecisionLog />)
    const table = await decisionTable()
    pickSize('25')
    expect(dataRows(table)).toBe(25)
    expect(screen.getByText(/Mostrando 25 de 30 decisões/)).toBeInTheDocument()
    pickSize('50')
    expect(dataRows(table)).toBe(30)
    expect(screen.queryByText(/Mostrando \d+ de/)).not.toBeInTheDocument()
  })

  it('aplica o filtro de acionamentos antes de limitar as linhas', async () => {
    mockApi([get(DECISIONS_PATH, ok(manyDecisions(30)))])
    render(<DecisionLog />)
    const table = await decisionTable()
    fireEvent.click(screen.getByRole('checkbox', { name: /só acionamentos/i }))
    expect(dataRows(table)).toBe(8)
    expect(screen.queryByText(/Mostrando \d+ de/)).not.toBeInTheDocument()
    pickSize('5')
    expect(dataRows(table)).toBe(5)
    expect(screen.getByText(/Mostrando 5 de 8 decisões/)).toBeInTheDocument()
  })

  it('começa com 5 decisões em tela estreita', async () => {
    narrowScreen()
    mockApi([get(DECISIONS_PATH, ok(manyDecisions(30)))])
    render(<DecisionLog />)
    const table = await decisionTable()
    expect(dataRows(table)).toBe(5)
    expect(screen.getByRole('radio', { name: '5' })).toBeChecked()
    expect(screen.getByText(/Mostrando 5 de 30 decisões/)).toBeInTheDocument()
  })

  it('não mostra resumo com poucas decisões nem controles sem nenhuma', async () => {
    mockApi([get(DECISIONS_PATH, ok(manyDecisions(3)))])
    const first = render(<DecisionLog />)
    await decisionTable()
    expect(screen.queryByText(/Mostrando \d+ de/)).not.toBeInTheDocument()
    first.unmount()

    mockApi([get(DECISIONS_PATH, ok({ ...DECISIONS, decisions: [] }))])
    render(<DecisionLog />)
    expect(await screen.findByText('Nenhuma decisão nas últimas 24 horas.')).toBeInTheDocument()
    expect(screen.queryByRole('radio')).not.toBeInTheDocument()
  })

  it('limita os eventos do atuador do mesmo jeito', async () => {
    mockApi([get(EVENTS_PATH, ok(manyEvents(30)))])
    render(<EventLog />)
    const table = await eventTable()
    expect(dataRows(table)).toBe(10)
    expect(screen.getByText(/Mostrando 10 de 30 eventos/)).toBeInTheDocument()
    pickSize('50')
    expect(dataRows(table)).toBe(30)
    expect(screen.queryByText(/Mostrando \d+ de/)).not.toBeInTheDocument()
  })

  it('começa com 5 eventos em tela estreita', async () => {
    narrowScreen()
    mockApi([get(EVENTS_PATH, ok(manyEvents(30)))])
    render(<EventLog />)
    const table = await eventTable()
    expect(dataRows(table)).toBe(5)
    expect(screen.getByRole('radio', { name: '5' })).toBeChecked()
  })
})

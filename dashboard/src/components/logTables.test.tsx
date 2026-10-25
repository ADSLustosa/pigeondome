import { render, screen, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { get, mockApi, ok } from '../test/api'
import { DECISIONS, EVENTS } from '../test/fixtures'
import { DecisionLog } from './DecisionLog'
import { EventLog } from './EventLog'

/** Em telas estreitas cada célula mostra o seu data-label: ele precisa ser o cabeçalho da coluna. */
function expectLabelsToMatchHeaders(table: HTMLElement) {
  const headers = within(table)
    .getAllByRole('columnheader')
    .map((header) => header.textContent)
  const bodyRows = within(table).getAllByRole('row').slice(1)
  expect(bodyRows.length).toBeGreaterThan(0)
  for (const row of bodyRows) {
    const labels = within(row)
      .getAllByRole('cell')
      .map((cell) => cell.getAttribute('data-label'))
    expect(labels).toEqual(headers)
  }
}

describe('tabelas da trilha em telas estreitas', () => {
  it('cada célula de decisão traz o rótulo da sua coluna', async () => {
    mockApi([get('/actuators/act-sim-01/decisions', ok(DECISIONS))])
    render(<DecisionLog />)
    expectLabelsToMatchHeaders(
      await screen.findByRole('table', { name: /decisões do controlador/i }),
    )
  })

  it('cada célula de evento traz o rótulo da sua coluna', async () => {
    mockApi([get('/actuators/act-sim-01/events', ok(EVENTS))])
    render(<EventLog />)
    expectLabelsToMatchHeaders(await screen.findByRole('table', { name: /eventos do atuador/i }))
  })
})

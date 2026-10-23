import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import type { Series, SeriesPoint } from '../api/types'
import { PresenceChart } from './PresenceChart'
import { SeriesTable } from './SeriesTable'

const START = Date.parse('2026-10-22T22:00:00Z')

function point(minute: number, mean: number, max: number): SeriesPoint {
  return {
    bucket_start: new Date(START + minute * 60_000).toISOString(),
    readings: 30,
    readings_with_pigeons: 29,
    presence_rate: 0.9667,
    mean_pigeons: mean,
    max_pigeons: max,
  }
}

const SERIES: Series = {
  device_id: 'cam-sim-01',
  start: '2026-10-22T22:00:00Z',
  end: '2026-10-22T22:10:00Z',
  bucket: '1m',
  points: [point(0, 2, 3), point(1, 4, 8), point(2, 3, 5), point(6, 1, 2)],
}

describe('PresenceChart', () => {
  it('é uma imagem acessível com título e descrição', () => {
    render(<PresenceChart series={SERIES} />)
    const chart = screen.getByRole('img', { name: /presença de pombos ao longo do tempo/i })
    expect(chart).toHaveAccessibleName(/6 sem medição/)
  })

  it('desenha uma barra por intervalo com medição e marca as lacunas', () => {
    const { container } = render(<PresenceChart series={SERIES} />)
    expect(container.querySelectorAll('.chart__bar')).toHaveLength(4)
    expect(container.querySelectorAll('.chart__gap')).toHaveLength(2)
  })
})

describe('SeriesTable', () => {
  it('lista os mesmos intervalos que o gráfico, com cabeçalhos de coluna', () => {
    render(<SeriesTable series={SERIES} />)
    expect(screen.getAllByRole('row', { hidden: true })).toHaveLength(5) // cabeçalho + 4 pontos
    expect(screen.getAllByRole('columnheader', { hidden: true })).toHaveLength(5)
  })
})

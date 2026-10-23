import { describe, expect, it } from 'vitest'
import type { Series, SeriesPoint } from '../api/types'
import { describeSeries, layoutSeries, niceScale, slotAtX } from './chart'

const START = Date.parse('2026-10-22T22:00:00Z')

function point(minute: number, mean: number, max: number): SeriesPoint {
  return {
    bucket_start: new Date(START + minute * 60_000).toISOString(),
    readings: 30,
    readings_with_pigeons: 30,
    presence_rate: 1,
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
const SIZE = { width: 700, height: 300 }

describe('niceScale', () => {
  it('arredonda o máximo para um passo inteiro', () => {
    expect(niceScale(8)).toEqual({ max: 8, ticks: [0, 2, 4, 6, 8] })
    expect(niceScale(37).max).toBe(40)
  })

  it('nunca produz uma escala vazia', () => {
    expect(niceScale(0)).toEqual({ max: 1, ticks: [0, 1] })
  })
})

describe('layoutSeries', () => {
  const layout = layoutSeries(SERIES, SIZE)

  it('separa intervalos com medição dos sem medição', () => {
    expect(layout.slots).toBe(10)
    expect(layout.bars.map((bar) => bar.index)).toEqual([0, 1, 2, 6])
    expect(layout.gaps.map((gap) => [gap.startIndex, gap.endIndex])).toEqual([
      [3, 5],
      [7, 9],
    ])
  })

  it('une intervalos vazios vizinhos em uma só lacuna com a largura certa', () => {
    const slot = layout.plot.width / 10
    expect(layout.gaps[0]?.width).toBeCloseTo(slot * 3, 5)
  })

  it('posiciona a média e o pico na escala do eixo Y', () => {
    const bar = layout.bars[1]
    const { top, height } = layout.plot
    expect(bar?.yPeak).toBeCloseTo(top, 5) // pico 8 = topo da escala (0 a 8)
    expect(bar?.yMean).toBeCloseTo(top + height / 2, 5) // média 4 = metade
  })

  it('gera 5 marcas de tempo, da primeira à última', () => {
    expect(layout.xTicks).toHaveLength(5)
    expect(layout.xTicks[0]?.anchor).toBe('start')
    expect(layout.xTicks[4]?.anchor).toBe('end')
  })
})

describe('descrição e ponteiro', () => {
  const layout = layoutSeries(SERIES, SIZE)

  it('descreve o gráfico em texto', () => {
    const text = describeSeries(SERIES, layout)
    expect(text).toContain('4 intervalos com medição')
    expect(text).toContain('6 sem medição')
    expect(text).toContain('Pico de 8')
  })

  it('traduz a posição do ponteiro em intervalo', () => {
    const { left, width } = layout.plot
    expect(slotAtX(layout, left)).toBe(0)
    expect(slotAtX(layout, left + width)).toBe(9)
    expect(slotAtX(layout, left - 1)).toBeNull()
  })
})

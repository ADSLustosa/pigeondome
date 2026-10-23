import { describe, expect, it } from 'vitest'
import type { Series, SeriesPoint } from '../api/types'
import { describeSeries, layoutSeries, niceScale, niceTimeTicks, slotAtX } from './chart'

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

  it('gera marcas de tempo dentro da área do gráfico', () => {
    expect(layout.xTicks.length).toBeGreaterThanOrEqual(2)
    for (const tick of layout.xTicks) {
      expect(tick.x).toBeGreaterThanOrEqual(layout.plot.left)
      expect(tick.x).toBeLessThanOrEqual(layout.plot.left + layout.plot.width)
    }
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

describe('niceTimeTicks', () => {
  const HOUR = 3_600_000
  const start = Date.parse('2026-10-22T21:53:31Z')
  const offsetOf = (ms: number) => -new Date(ms).getTimezoneOffset() * 60_000
  const gap = (ticks: number[]) => (ticks[1] ?? 0) - (ticks[0] ?? 0)

  it('alinha as marcas a horários redondos do relógio local', () => {
    const ticks = niceTimeTicks(start, start + HOUR, 7)
    expect(ticks.length).toBeGreaterThan(0)
    for (const tick of ticks) {
      expect((tick + offsetOf(start)) % (10 * 60_000)).toBe(0)
    }
  })

  it('mantém todas as marcas dentro da janela e sem exagero', () => {
    for (const hours of [1, 6, 24, 168]) {
      const end = start + hours * HOUR
      const ticks = niceTimeTicks(start, end, 7)
      expect(ticks.length).toBeLessThanOrEqual(8)
      expect(ticks.every((tick) => tick >= start && tick <= end)).toBe(true)
    }
  })

  it('usa passos maiores em janelas maiores', () => {
    const hour = niceTimeTicks(start, start + HOUR, 7)
    const week = niceTimeTicks(start, start + 168 * HOUR, 7)
    expect(gap(hour)).toBe(10 * 60_000)
    expect(gap(week)).toBe(24 * HOUR)
  })
})
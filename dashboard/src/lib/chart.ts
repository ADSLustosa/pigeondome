import type { BucketName, Series, SeriesPoint } from '../api/types'
import { formatDateTime, formatInteger } from './format'
import { BUCKET_MINUTES } from './windows'

export const BUCKET_LABELS: Record<BucketName, string> = {
  '1m': '1 minuto',
  '5m': '5 minutos',
  '15m': '15 minutos',
  '1h': '1 hora',
  '1d': '1 dia',
}

export const MARGIN = { top: 12, right: 12, bottom: 30, left: 44 }

export interface ChartSize {
  width: number
  height: number
}

export interface Bar {
  index: number
  x: number
  width: number
  yMean: number
  yPeak: number
  point: SeriesPoint
}

/** Uma sequência contínua de intervalos sem nenhuma leitura. */
export interface GapRun {
  startIndex: number
  endIndex: number
  x: number
  width: number
}

export interface YTick {
  value: number
  y: number
  label: string
}

export interface XTick {
  x: number
  label: string
  anchor: 'start' | 'middle' | 'end'
}

export interface ChartLayout {
  plot: { left: number; top: number; width: number; height: number }
  bars: Bar[]
  gaps: GapRun[]
  yTicks: YTick[]
  xTicks: XTick[]
  slots: number
  startMs: number
  bucketMs: number
  spanMs: number
}

/** Escala "redonda" para o eixo Y: passos inteiros (contagem de pombos). */
export function niceScale(maxValue: number, targetTicks = 4): { max: number; ticks: number[] } {
  const safe = Math.max(maxValue, 1)
  const rough = safe / targetTicks
  const magnitude = 10 ** Math.floor(Math.log10(rough))
  const residual = rough / magnitude
  let factor = 10
  if (residual <= 1) factor = 1
  else if (residual <= 2) factor = 2
  else if (residual <= 5) factor = 5
  const step = Math.max(1, factor * magnitude)
  const max = Math.ceil(safe / step) * step
  const ticks: number[] = []
  for (let value = 0; value <= max; value += step) ticks.push(value)
  return { max, ticks }
}

const timeOnly = new Intl.DateTimeFormat('pt-BR', { hour: '2-digit', minute: '2-digit' })
const dayAndTime = new Intl.DateTimeFormat('pt-BR', {
  day: '2-digit',
  month: '2-digit',
  hour: '2-digit',
  minute: '2-digit',
})

const dateOnly = new Intl.DateTimeFormat('pt-BR', { day: '2-digit', month: '2-digit' })

const MINUTE_MS = 60_000
const HOUR_MS = 3_600_000
const DAY_MS = 86_400_000
const TIME_STEPS = [
  5 * MINUTE_MS,
  10 * MINUTE_MS,
  15 * MINUTE_MS,
  30 * MINUTE_MS,
  HOUR_MS,
  2 * HOUR_MS,
  3 * HOUR_MS,
  6 * HOUR_MS,
  12 * HOUR_MS,
  DAY_MS,
]

export function formatAxisTime(ms: number, spanMs: number): string {
  if (spanMs <= 36 * HOUR_MS) return timeOnly.format(new Date(ms))
  const date = new Date(ms)
  const atMidnight = date.getHours() === 0 && date.getMinutes() === 0
  return (atMidnight ? dateOnly : dayAndTime).format(date)
}

/** Marcas em horários redondos do relógio local (22:00, 22:10...), todas dentro da janela. */
export function niceTimeTicks(startMs: number, endMs: number, maxTicks: number): number[] {
  const span = endMs - startMs
  const step = TIME_STEPS.find((candidate) => span / candidate < maxTicks) ?? DAY_MS
  // alinha ao relógio local (há fusos com diferença de meia hora, por exemplo)
  const offset = -new Date(startMs).getTimezoneOffset() * MINUTE_MS
  const ticks: number[] = []
  for (
    let tick = Math.ceil((startMs + offset) / step) * step - offset;
    tick <= endMs;
    tick += step
  ) {
    ticks.push(tick)
  }
  return ticks
}

export function layoutSeries(series: Series, size: ChartSize): ChartLayout {
  const startMs = Date.parse(series.start)
  const spanMs = Math.max(Date.parse(series.end) - startMs, 1)
  const bucketMs = BUCKET_MINUTES[series.bucket] * 60_000
  const slots = Math.max(1, Math.ceil(spanMs / bucketMs))

  const plot = {
    left: MARGIN.left,
    top: MARGIN.top,
    width: Math.max(1, size.width - MARGIN.left - MARGIN.right),
    height: Math.max(1, size.height - MARGIN.top - MARGIN.bottom),
  }
  const right = plot.left + plot.width
  const slotWidth = (bucketMs / spanMs) * plot.width
  const xOf = (ms: number) => plot.left + ((ms - startMs) / spanMs) * plot.width

  const peak = Math.max(0, ...series.points.map((point) => point.max_pigeons))
  const scale = niceScale(peak)
  const yOf = (value: number) => plot.top + plot.height * (1 - value / scale.max)

  const byIndex = new Map<number, SeriesPoint>()
  for (const point of series.points) {
    byIndex.set(Math.round((Date.parse(point.bucket_start) - startMs) / bucketMs), point)
  }

  const gapRect = (startIndex: number, endIndex: number): GapRun => {
    const x = xOf(startMs + startIndex * bucketMs)
    const end = Math.min(xOf(startMs + (endIndex + 1) * bucketMs), right)
    return { startIndex, endIndex, x, width: Math.max(1, end - x) }
  }

  const bars: Bar[] = []
  const gaps: GapRun[] = []
  let gapStart: number | null = null
  for (let index = 0; index < slots; index += 1) {
    const point = byIndex.get(index)
    if (point) {
      if (gapStart !== null) {
        gaps.push(gapRect(gapStart, index - 1))
        gapStart = null
      }
      const x = xOf(startMs + index * bucketMs)
      bars.push({
        index,
        x,
        width: Math.max(1, Math.min(slotWidth, right - x) - 1),
        yMean: yOf(point.mean_pigeons),
        yPeak: yOf(point.max_pigeons),
        point,
      })
    } else if (gapStart === null) {
      gapStart = index
    }
  }
  if (gapStart !== null) gaps.push(gapRect(gapStart, slots - 1))

  const yTicks = scale.ticks.map((value) => ({
    value,
    y: yOf(value),
    label: formatInteger(value),
  }))

  const maxTicks = Math.max(3, Math.floor(plot.width / 90))
  const xTicks: XTick[] = niceTimeTicks(startMs, startMs + spanMs, maxTicks).map((ms) => {
    const x = xOf(ms)
    let anchor: XTick['anchor'] = 'middle'
    if (x < plot.left + 20) anchor = 'start'
    else if (x > right - 20) anchor = 'end'
    return { x, label: formatAxisTime(ms, spanMs), anchor }
  })

  return { plot, bars, gaps, yTicks, xTicks, slots, startMs, bucketMs, spanMs }
}

/** Texto para leitores de tela: o que o gráfico mostra, em uma frase. */
export function describeSeries(series: Series, layout: ChartLayout): string {
  const peak = Math.max(0, ...series.points.map((point) => point.max_pigeons))
  const withoutData = layout.slots - layout.bars.length
  return (
    `Média de pombos a cada ${BUCKET_LABELS[series.bucket]}, ` +
    `de ${formatDateTime(series.start)} a ${formatDateTime(series.end)}. ` +
    `${formatInteger(layout.bars.length)} intervalos com medição e ` +
    `${formatInteger(withoutData)} sem medição. ` +
    `Pico de ${formatInteger(peak)} pombos em uma leitura.`
  )
}

/** Intervalo sob o ponteiro (posição x em pixels do SVG), ou null fora da área do gráfico. */
export function slotAtX(layout: ChartLayout, x: number): number | null {
  const { left, width } = layout.plot
  if (x < left || x > left + width) return null
  const ms = ((x - left) / width) * layout.spanMs
  return Math.min(layout.slots - 1, Math.floor(ms / layout.bucketMs))
}

export function slotStartIso(layout: ChartLayout, index: number): string {
  return new Date(layout.startMs + index * layout.bucketMs).toISOString()
}

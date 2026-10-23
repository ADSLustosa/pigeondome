import type { BucketName, TimeRange } from '../api/types'

export type WindowId = '1h' | '6h' | '24h' | '7d'

export interface WindowPreset {
  id: WindowId
  label: string
  title: string
  hours: number
  bucket: BucketName
}

const LAST_HOUR: WindowPreset = { id: '1h', label: '1 h', title: 'última hora', hours: 1, bucket: '1m' }

export const WINDOW_PRESETS: readonly WindowPreset[] = [
  LAST_HOUR,
  { id: '6h', label: '6 h', title: 'últimas 6 horas', hours: 6, bucket: '5m' },
  { id: '24h', label: '24 h', title: 'últimas 24 horas', hours: 24, bucket: '15m' },
  { id: '7d', label: '7 d', title: 'últimos 7 dias', hours: 168, bucket: '1h' },
]

export const DEFAULT_WINDOW_ID: WindowId = '1h'
export const MAX_SERIES_POINTS = 500

export const BUCKET_MINUTES: Record<BucketName, number> = {
  '1m': 1,
  '5m': 5,
  '15m': 15,
  '1h': 60,
  '1d': 1440,
}

export function presetById(id: WindowId): WindowPreset {
  return WINDOW_PRESETS.find((preset) => preset.id === id) ?? LAST_HOUR
}

export function rangeFor(preset: WindowPreset, now: Date): TimeRange {
  const start = new Date(now.getTime() - preset.hours * 3_600_000)
  return { start: start.toISOString(), end: now.toISOString() }
}

import { describe, expect, it } from 'vitest'
import { formatDecimal, formatInteger, formatPercent } from './format'
import {
  BUCKET_MINUTES,
  MAX_SERIES_POINTS,
  WINDOW_PRESETS,
  presetById,
  rangeFor,
} from './windows'

describe('períodos', () => {
  it('nenhum período pede mais pontos do que o backend aceita', () => {
    for (const preset of WINDOW_PRESETS) {
      const points = Math.ceil((preset.hours * 60) / BUCKET_MINUTES[preset.bucket])
      expect(points, preset.id).toBeLessThanOrEqual(MAX_SERIES_POINTS)
    }
  })

  it('calcula o início e o fim da janela em UTC', () => {
    const now = new Date('2026-10-22T22:00:00.000Z')
    const range = rangeFor(presetById('6h'), now)
    expect(range.end).toBe('2026-10-22T22:00:00.000Z')
    expect(range.start).toBe('2026-10-22T16:00:00.000Z')
  })

  it('volta ao período padrão quando o id é desconhecido', () => {
    expect(presetById('999' as never).id).toBe('1h')
  })
})

describe('formatação pt-BR', () => {
  it('formata números e porcentagens', () => {
    expect(formatInteger(1234)).toContain('1')
    expect(formatPercent(0.9473)).toContain('94,7')
    expect(formatDecimal(3.98245)).toBe('4,0')
  })
})

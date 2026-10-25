import { describe, expect, it } from 'vitest'
import { formatAge, formatClock, formatDayMonth, formatLogTime } from './format'

describe('formatAge', () => {
  it.each<[number, string]>([
    [0, '0 s'],
    [6.8, '6 s'],
    [59.9, '59 s'],
    [60, '1 min'],
    [125, '2 min 5 s'],
    [3600, '1 h'],
    [3780, '1 h 3 min'],
    [86_400, '1 d'],
    [90_000, '1 d 1 h'],
    [-5, '0 s'],
  ])('%s s vira "%s"', (seconds, expected) => {
    expect(formatAge(seconds)).toBe(expected)
  })
})

describe('formatLogTime', () => {
  it('mostra dia, mês e hora com segundos', () => {
    // meio-dia em UTC cai no dia 24 ou 25 conforme o fuso da máquina, mas sempre em outubro
    const text = formatLogTime('2026-10-24T12:00:05Z')
    expect(text).toMatch(/\/10/)
    expect(text).toMatch(/:05$/)
  })
})

describe('formatClock', () => {
  it('mostra a hora com ou sem segundos', () => {
    expect(formatClock('2026-10-24T12:00:05Z', true)).toMatch(/^\d{2}:\d{2}:\d{2}$/)
    expect(formatClock('2026-10-24T12:00:05Z', false)).toMatch(/^\d{2}:\d{2}$/)
  })
})

describe('formatDayMonth', () => {
  it('mostra só o dia e o mês', () => {
    expect(formatDayMonth('2026-10-24T12:00:05Z')).toMatch(/^\d{2}\/10$/)
  })
})

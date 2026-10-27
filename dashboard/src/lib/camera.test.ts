import { describe, expect, it } from 'vitest'
import { describeFrame, frameChip } from './camera'
import type { FrameState, FrameStatus } from './camera'

const frame = (changes: Partial<FrameState> = {}): FrameState => ({
  url: null,
  okAt: null,
  now: 0,
  failure: null,
  ...changes,
})

/** Um quadro que chegou há `ageMs` milissegundos. */
const received = (ageMs: number, changes: Partial<FrameState> = {}): FrameState =>
  frame({ url: 'blob:x', okAt: 10_000, now: 10_000 + ageMs, ...changes })

describe('describeFrame', () => {
  it.each<[string, FrameState, FrameStatus, number | null]>([
    ['sem câmera configurada', frame({ failure: 'unconfigured' }), 'unconfigured', null],
    ['antes do primeiro quadro', frame(), 'loading', null],
    ['o primeiro pedido falhou', frame({ failure: 'unavailable' }), 'unavailable', null],
    ['o quadro acabou de chegar', received(0), 'live', 0],
    ['no limite de 5 s ainda é ao vivo', received(5000), 'live', 5],
    ['passado o limite fica sem sinal', received(5100), 'stale', 5.1],
    [
      'uma falha logo depois de um bom quadro não derruba o ao vivo',
      received(1000, { failure: 'unavailable' }),
      'live',
      1,
    ],
    [
      'relógio andando para trás nunca dá idade negativa',
      frame({ url: 'blob:x', okAt: 10_000, now: 9000 }),
      'live',
      0,
    ],
    [
      'a câmera deixou de estar configurada depois de ter funcionado',
      received(0, { failure: 'unconfigured' }),
      'unconfigured',
      null,
    ],
  ])('%s', (_name, state, status, ageS) => {
    expect(describeFrame(state, 5)).toEqual({ status, ageS })
  })
})

describe('frameChip', () => {
  it('traduz cada estado do quadro', () => {
    expect(frameChip('loading')).toEqual({ label: 'Carregando', tone: 'neutral' })
    expect(frameChip('live')).toEqual({ label: 'Ao vivo', tone: 'success' })
    expect(frameChip('stale')).toEqual({ label: 'Sem sinal', tone: 'warning' })
    expect(frameChip('unavailable')).toEqual({ label: 'Sem imagem', tone: 'danger' })
    expect(frameChip('unconfigured')).toEqual({ label: 'Não configurada', tone: 'neutral' })
  })
})

import type { Labeled } from './actuation'

/** O que aconteceu da última vez que o painel pediu o quadro. */
export type Failure = 'unavailable' | 'unconfigured'

export type FrameStatus = 'loading' | 'live' | 'stale' | 'unavailable' | 'unconfigured'

export interface FrameState {
  /** Endereço (blob:) do quadro mais recente, ou null enquanto não chegou nenhum. */
  url: string | null
  /** Quando o quadro mais recente chegou (relógio monotônico do navegador, em ms). */
  okAt: number | null
  /** Última atualização do estado (mesmo relógio): a idade do quadro é a diferença. */
  now: number
  failure: Failure | null
}

export const INITIAL_FRAME: FrameState = { url: null, okAt: null, now: 0, failure: null }

export interface FrameView {
  status: FrameStatus
  /** Segundos desde o último quadro; null se nunca chegou nenhum. */
  ageS: number | null
}

export function describeFrame(frame: FrameState, staleAfterS: number): FrameView {
  if (frame.failure === 'unconfigured') return { status: 'unconfigured', ageS: null }
  if (frame.okAt === null) {
    return { status: frame.failure === null ? 'loading' : 'unavailable', ageS: null }
  }
  // a diferença de relógios nunca vira uma idade negativa
  const ageS = Math.max(0, (frame.now - frame.okAt) / 1000)
  return { status: ageS <= staleAfterS ? 'live' : 'stale', ageS }
}

const CHIPS: Record<FrameStatus, Labeled> = {
  loading: { label: 'Carregando', tone: 'neutral' },
  live: { label: 'Ao vivo', tone: 'success' },
  stale: { label: 'Sem sinal', tone: 'warning' },
  unavailable: { label: 'Sem imagem', tone: 'danger' },
  unconfigured: { label: 'Não configurada', tone: 'neutral' },
}

export const frameChip = (status: FrameStatus): Labeled => CHIPS[status]

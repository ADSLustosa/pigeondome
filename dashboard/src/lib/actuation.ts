import type { ActuatorStatus, Controller } from '../api/types'

/** Cor semântica de um estado. Nunca é a única pista: todo chip também traz texto. */
export type Tone = 'success' | 'accent' | 'warning' | 'danger' | 'neutral'

export interface Labeled {
  label: string
  tone: Tone
}

// Os valores vêm da API, então os mapas são Map (e não objetos): uma chave como "constructor"
// não pode devolver propriedades herdadas. Valor desconhecido aparece como veio, nunca quebra.

const STATES = new Map<string, Labeled>([
  ['idle', { label: 'Pronto', tone: 'success' }],
  ['pulsing', { label: 'Pulsando', tone: 'accent' }],
  ['cooldown', { label: 'Em pausa', tone: 'neutral' }],
  ['safe_off', { label: 'Desligado com segurança', tone: 'neutral' }],
  ['maintenance', { label: 'Em manutenção', tone: 'warning' }],
  ['fault', { label: 'Em falha', tone: 'danger' }],
])

const MODES = new Map<string, Labeled & { hint: string }>([
  ['off', { label: 'Desligado', tone: 'neutral', hint: 'só observa, nunca decide acionar' }],
  [
    'dry_run',
    { label: 'Modo seco', tone: 'neutral', hint: 'decide e registra, mas não envia comandos' },
  ],
  ['live', { label: 'Modo real', tone: 'accent', hint: 'envia pulsos reais ao atuador' }],
  [
    'experiment',
    {
      label: 'Experimento',
      tone: 'accent',
      hint: 'pulsos reais só nos blocos de tratamento sorteados',
    },
  ],
])

const VERDICTS = new Map<string, Labeled>([
  ['pulse', { label: 'Pulso enviado', tone: 'accent' }],
  ['would_pulse', { label: 'Teria pulsado', tone: 'neutral' }],
  ['skip', { label: 'Sem ação', tone: 'neutral' }],
])

const EVENTS = new Map<string, Labeled>([
  ['command_accepted', { label: 'Comando aceito', tone: 'neutral' }],
  ['command_rejected', { label: 'Comando rejeitado', tone: 'danger' }],
  ['pulse_started', { label: 'Pulso iniciado', tone: 'accent' }],
  ['pulse_finished', { label: 'Pulso concluído', tone: 'success' }],
  ['pulse_aborted', { label: 'Pulso interrompido', tone: 'warning' }],
])

const REASONS = new Map<string, string>([
  ['mode_off', 'Controlador em modo desligado'],
  ['kill_switch', 'Chave geral ligada'],
  ['stale_data', 'Sem leituras recentes da câmera'],
  ['insufficient_evidence', 'Evidência insuficiente'],
  ['quiet_hours', 'Horário de silêncio'],
  ['actuator_unavailable', 'Atuador indisponível'],
  ['retry_gap', 'Aguardando o intervalo mínimo entre pulsos'],
  ['daily_budget', 'Limite diário de pulsos atingido'],
  ['experiment_control', 'Bloco de controle do experimento'],
  ['dry_run', 'Modo seco: teria enviado o pulso'],
  ['evidence_confirmed', 'Evidência confirmada'],
])

const DETAILS = new Map<string, string>([
  ['offline', 'offline'],
  ['unknown', 'sem estado conhecido'],
  ['send_failed', 'falha ao enviar o comando'],
  ['idle', 'pronto'],
  ['pulsing', 'pulsando'],
  ['cooldown', 'em pausa'],
  ['safe_off', 'desligado com segurança'],
  ['maintenance', 'em manutenção'],
  ['fault', 'em falha'],
])

const ARMS = new Map<string, string>([
  ['treatment', 'tratamento'],
  ['control', 'controle'],
])

const REASON_CODES = new Map<string, string>([
  ['stop_command', 'comando de parada'],
  ['disconnected', 'conexão encerrada'],
  ['budget_exhausted', 'orçamento horário esgotado'],
])

export const stateInfo = (state: string): Labeled =>
  STATES.get(state) ?? { label: state, tone: 'neutral' }

/** Offline é um fato e vence tudo; dado velho vence o estado relatado. */
export function actuatorSummary(status: ActuatorStatus): Labeled {
  if (!status.online) return { label: 'Offline', tone: 'danger' }
  if (status.stale) return { label: 'Sem sinal', tone: 'warning' }
  return stateInfo(status.state)
}

export function controllerSummary(controller: Controller): Labeled {
  if (controller.mode === null) return { label: 'Nunca executou', tone: 'neutral' }
  return controller.running
    ? { label: 'Em execução', tone: 'success' }
    : { label: 'Parado', tone: 'danger' }
}

export const modeInfo = (mode: string): Labeled & { hint: string } =>
  MODES.get(mode) ?? { label: mode, tone: 'neutral', hint: '' }

export const verdictInfo = (verdict: string): Labeled =>
  VERDICTS.get(verdict) ?? { label: verdict, tone: 'neutral' }

export const eventInfo = (event: string): Labeled =>
  EVENTS.get(event) ?? { label: event, tone: 'neutral' }

export const armLabel = (arm: string): string => ARMS.get(arm) ?? arm

/**
 * O motivo `disconnected` vale para dois eventos: no aborto, a conexão caiu durante o pulso; na
 * recusa, o comando chegou com o atuador desconectado. O par evento + motivo é inequívoco, então
 * o texto depende do evento, e o contrato não muda.
 */
export function reasonCodeText(code: string, event?: string): string {
  if (code === 'disconnected' && event === 'command_rejected') return 'atuador desconectado'
  return REASON_CODES.get(code) ?? code
}

/** O motivo da decisão, com o detalhe entre parênteses (ex.: o estado do atuador). */
export function reasonText(reason: string, detail: string): string {
  const base = REASONS.get(reason) ?? reason
  if (detail === '') return base
  return `${base} (${DETAILS.get(detail) ?? detail})`
}

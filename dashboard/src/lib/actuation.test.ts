import { describe, expect, it } from 'vitest'
import type { ActuatorStatus, Controller } from '../api/types'
import { ACTUATOR, CONTROLLER } from '../test/fixtures'
import {
  actuatorSummary,
  armLabel,
  controllerSummary,
  eventInfo,
  modeInfo,
  reasonCodeText,
  reasonText,
  stateInfo,
  verdictInfo,
} from './actuation'

describe('estado do atuador', () => {
  it('traduz todos os estados do contrato', () => {
    expect(stateInfo('idle')).toEqual({ label: 'Pronto', tone: 'success' })
    expect(stateInfo('pulsing')).toEqual({ label: 'Pulsando', tone: 'accent' })
    expect(stateInfo('cooldown')).toEqual({ label: 'Em pausa', tone: 'neutral' })
    expect(stateInfo('safe_off')).toEqual({ label: 'Desligado com segurança', tone: 'neutral' })
    expect(stateInfo('maintenance')).toEqual({ label: 'Em manutenção', tone: 'warning' })
    expect(stateInfo('fault')).toEqual({ label: 'Em falha', tone: 'danger' })
  })

  it('mostra um estado desconhecido como veio, sem herdar propriedades de objetos', () => {
    expect(stateInfo('novo_estado')).toEqual({ label: 'novo_estado', tone: 'neutral' })
    expect(stateInfo('constructor')).toEqual({ label: 'constructor', tone: 'neutral' })
  })

  it('o atuador offline vence o dado velho, que vence o estado', () => {
    const offline: ActuatorStatus = { ...ACTUATOR, online: false, stale: true, state: 'safe_off' }
    expect(actuatorSummary(offline)).toEqual({ label: 'Offline', tone: 'danger' })
    expect(actuatorSummary({ ...ACTUATOR, stale: true })).toEqual({
      label: 'Sem sinal',
      tone: 'warning',
    })
    expect(actuatorSummary(ACTUATOR)).toEqual({ label: 'Pronto', tone: 'success' })
  })
})

describe('controlador', () => {
  it('resume o controlador', () => {
    const neverRan: Controller = { ...CONTROLLER, mode: null, running: false }
    expect(controllerSummary(neverRan)).toEqual({ label: 'Nunca executou', tone: 'neutral' })
    expect(controllerSummary({ ...CONTROLLER, running: false })).toEqual({
      label: 'Parado',
      tone: 'danger',
    })
    expect(controllerSummary(CONTROLLER)).toEqual({ label: 'Em execução', tone: 'success' })
  })

  it('explica cada modo e destaca só os que enviam pulsos reais', () => {
    expect(modeInfo('off')).toMatchObject({ label: 'Desligado', tone: 'neutral' })
    expect(modeInfo('dry_run')).toMatchObject({ label: 'Modo seco', tone: 'neutral' })
    expect(modeInfo('live')).toMatchObject({ label: 'Modo real', tone: 'accent' })
    expect(modeInfo('experiment')).toMatchObject({ label: 'Experimento', tone: 'accent' })
    expect(modeInfo('live').hint).toMatch(/pulsos reais/)
    expect(modeInfo('novo')).toEqual({ label: 'novo', tone: 'neutral', hint: '' })
  })
})

describe('trilha', () => {
  it('traduz os motivos e o detalhe', () => {
    expect(reasonText('evidence_confirmed', '')).toBe('Evidência confirmada')
    expect(reasonText('retry_gap', '')).toBe('Aguardando o intervalo mínimo entre pulsos')
    expect(reasonText('kill_switch', '')).toBe('Chave geral ligada')
    expect(reasonText('actuator_unavailable', 'pulsing')).toBe('Atuador indisponível (pulsando)')
    expect(reasonText('actuator_unavailable', 'offline')).toBe('Atuador indisponível (offline)')
    expect(reasonText('actuator_unavailable', 'send_failed')).toBe(
      'Atuador indisponível (falha ao enviar o comando)',
    )
  })

  it('mostra motivo ou detalhe desconhecido como veio', () => {
    expect(reasonText('motivo_novo', '')).toBe('motivo_novo')
    expect(reasonText('actuator_unavailable', 'estranho')).toBe('Atuador indisponível (estranho)')
    expect(reasonText('toString', '')).toBe('toString')
  })

  it('traduz veredito, evento, braço do experimento e código de motivo', () => {
    expect(verdictInfo('pulse')).toEqual({ label: 'Pulso enviado', tone: 'accent' })
    expect(verdictInfo('would_pulse')).toEqual({ label: 'Teria pulsado', tone: 'neutral' })
    expect(verdictInfo('skip')).toEqual({ label: 'Sem ação', tone: 'neutral' })
    expect(verdictInfo('novo')).toEqual({ label: 'novo', tone: 'neutral' })
    expect(eventInfo('pulse_started')).toEqual({ label: 'Pulso iniciado', tone: 'accent' })
    expect(eventInfo('pulse_finished')).toEqual({ label: 'Pulso concluído', tone: 'success' })
    expect(eventInfo('pulse_aborted')).toEqual({ label: 'Pulso interrompido', tone: 'warning' })
    expect(eventInfo('command_rejected')).toEqual({ label: 'Comando rejeitado', tone: 'danger' })
    expect(eventInfo('command_accepted')).toEqual({ label: 'Comando aceito', tone: 'neutral' })
    expect(armLabel('treatment')).toBe('tratamento')
    expect(armLabel('control')).toBe('controle')
    expect(armLabel('novo')).toBe('novo')
    expect(reasonCodeText('stop_command')).toBe('comando de parada')
    expect(reasonCodeText('disconnected')).toBe('conexão encerrada')
    expect(reasonCodeText('disconnected', 'pulse_aborted')).toBe('conexão encerrada')
    expect(reasonCodeText('disconnected', 'command_rejected')).toBe('atuador desconectado')
    expect(reasonCodeText('stop_command', 'command_rejected')).toBe('comando de parada')
    expect(reasonCodeText('budget_exhausted')).toBe('orçamento horário esgotado')
    expect(reasonCodeText('outro')).toBe('outro')
  })
})

import type { ActuatorEvents, ActuatorStatus, Controller, Decisions } from '../api/types'

export const COMMAND_ID = '3f2b8c1e-7a4d-4e5b-9c6a-1d2e3f4a5b6c'
export const STOP_COMMAND_ID = '0972ed43-afdb-407d-83cb-17c6ce5b67ba'

export const CONTROLLER: Controller = {
  kill_switch: false,
  running: true,
  mode: 'live',
  camera_id: 'cam-sim-01',
  actuator_id: 'act-sim-01',
  started_at: '2026-10-24T22:20:33Z',
  heartbeat_at: '2026-10-24T22:20:39Z',
  age_s: 3.2,
}

export const ACTUATOR: ActuatorStatus = {
  actuator_id: 'act-sim-01',
  online: true,
  state: 'idle',
  output_on: false,
  budget_used_s_1h: 5,
  received_at: '2026-10-24T22:20:36Z',
  age_s: 6.8,
  stale: false,
}

export const DECISIONS: Decisions = {
  actuator_id: 'act-sim-01',
  start: '2026-10-23T22:20:00Z',
  end: '2026-10-24T22:20:00Z',
  limit: 50,
  truncated: false,
  decisions: [
    {
      decided_at: '2026-10-24T22:20:40Z',
      camera_id: 'cam-sim-01',
      mode: 'live',
      verdict: 'skip',
      reason: 'retry_gap',
      detail: '',
      arm: null,
      duration_s: null,
      command_id: null,
      readings: 15,
      detections: 14,
      mean_confidence: 0.86,
      triggered: false,
    },
    {
      decided_at: '2026-10-24T22:20:35Z',
      camera_id: 'cam-sim-01',
      mode: 'live',
      verdict: 'skip',
      reason: 'actuator_unavailable',
      detail: 'pulsing',
      arm: null,
      duration_s: null,
      command_id: null,
      readings: 4,
      detections: 4,
      mean_confidence: 0.86,
      triggered: false,
    },
    {
      decided_at: '2026-10-24T22:20:34Z',
      camera_id: 'cam-sim-01',
      mode: 'live',
      verdict: 'pulse',
      reason: 'evidence_confirmed',
      detail: '',
      arm: null,
      duration_s: 5,
      command_id: COMMAND_ID,
      readings: 4,
      detections: 4,
      mean_confidence: 0.86,
      triggered: true,
    },
  ],
}

export const EVENTS: ActuatorEvents = {
  actuator_id: 'act-sim-01',
  start: '2026-10-23T22:20:00Z',
  end: '2026-10-24T22:20:00Z',
  limit: 50,
  truncated: false,
  events: [
    {
      occurred_at: '2026-10-24T22:20:39Z',
      event: 'pulse_finished',
      command_id: COMMAND_ID,
      reason_code: null,
    },
    {
      occurred_at: '2026-10-24T22:20:34Z',
      event: 'pulse_started',
      command_id: COMMAND_ID,
      reason_code: null,
    },
    {
      occurred_at: '2026-10-24T22:20:34Z',
      event: 'command_accepted',
      command_id: COMMAND_ID,
      reason_code: null,
    },
    {
      occurred_at: '2026-10-24T22:10:00Z',
      event: 'pulse_aborted',
      command_id: STOP_COMMAND_ID,
      reason_code: 'stop_command',
    },
  ],
}

export const DEVICES = [
  { device_id: 'cam-sim-01', readings: 57, last_detected_at: '2026-10-22T22:32:37Z' },
]

export const PRESENCE = {
  device_id: 'cam-sim-01',
  start: '2026-10-22T21:33:00Z',
  end: '2026-10-22T22:33:00Z',
  readings: 57,
  readings_with_pigeons: 54,
  presence_rate: 0.9473684,
  mean_pigeons: 3.9824561,
  max_pigeons: 8,
}

export const SERIES = {
  device_id: 'cam-sim-01',
  start: '2026-10-22T21:33:00Z',
  end: '2026-10-22T22:33:00Z',
  bucket: '1m',
  points: [],
}

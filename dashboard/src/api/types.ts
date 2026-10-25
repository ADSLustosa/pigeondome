/** Tipos que espelham o contrato OpenAPI da API (backend). */

export type BucketName = '1m' | '5m' | '15m' | '1h' | '1d'

export interface TimeRange {
  start: string
  end: string
}

export interface Device {
  device_id: string
  readings: number
  last_detected_at: string
}

export interface Presence {
  device_id: string
  start: string
  end: string
  readings: number
  readings_with_pigeons: number
  presence_rate: number
  mean_pigeons: number
  max_pigeons: number
}

export interface SeriesPoint {
  bucket_start: string
  readings: number
  readings_with_pigeons: number
  presence_rate: number
  mean_pigeons: number
  max_pigeons: number
}

/** Só traz intervalos COM leituras: ausência de ponto = ausência de medição. */
export interface Series {
  device_id: string
  start: string
  end: string
  bucket: BucketName
  points: SeriesPoint[]
}

export interface FieldError {
  field: string
  message: string
  code: string
}

/** Formato de erro da API: RFC 9457 (application/problem+json). */
export interface Problem {
  type: string
  title: string
  status: number
  detail: string
  instance?: string
  errors?: FieldError[]
}

/** Último estado do atuador, com a idade e o frescor já calculados pela API. */
export interface ActuatorStatus {
  actuator_id: string
  online: boolean
  state: string
  output_on: boolean | null
  budget_used_s_1h: number | null
  received_at: string
  age_s: number
  /** Consta como online, mas não manda mensagem há mais de 30 s: dado não confiável. */
  stale: boolean
}

export interface Controller {
  kill_switch: boolean
  /** O último batimento tem no máximo 15 s. */
  running: boolean
  mode: string | null
  camera_id: string | null
  actuator_id: string | null
  started_at: string | null
  heartbeat_at: string | null
  age_s: number | null
}

export interface Decision {
  decided_at: string
  camera_id: string
  mode: string
  verdict: string
  reason: string
  detail: string
  arm: string | null
  duration_s: number | null
  command_id: string | null
  readings: number
  detections: number
  mean_confidence: number
  triggered: boolean
}

/** Da decisão mais recente para a mais antiga. */
export interface Decisions {
  actuator_id: string
  start: string
  end: string
  limit: number
  truncated: boolean
  decisions: Decision[]
}

export interface ActuatorEvent {
  occurred_at: string
  event: string
  command_id: string | null
  reason_code: string | null
}

/** Do evento mais recente para o mais antigo. */
export interface ActuatorEvents {
  actuator_id: string
  start: string
  end: string
  limit: number
  truncated: boolean
  events: ActuatorEvent[]
}

export interface KillSwitch {
  kill_switch: boolean
}

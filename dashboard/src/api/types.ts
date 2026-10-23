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

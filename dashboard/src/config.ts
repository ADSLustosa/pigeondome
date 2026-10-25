export const API_BASE_URL: string =
  (import.meta.env.VITE_API_URL as string | undefined) ?? 'http://127.0.0.1:8000'

export const DEVICES_POLL_MS = 30_000
export const PRESENCE_POLL_MS = 10_000
export const SERIES_POLL_MS = 15_000
export const ACTUATION_POLL_MS = 5_000
export const LOG_POLL_MS = 10_000
export const LOG_LIMIT = 50

/** Atuador acompanhado pelo painel (hoje o sistema tem um só). */
export const ACTUATOR_ID: string =
  (import.meta.env.VITE_ACTUATOR_ID as string | undefined) ?? 'act-sim-01'

/**
 * Orçamento de saída ligada por hora: constante do firmware do atuador (limites de segurança).
 * Está duplicada aqui só para desenhar a barra de uso; precisa acompanhar o firmware.
 */
export const ACTUATOR_HOURLY_BUDGET_S = 120

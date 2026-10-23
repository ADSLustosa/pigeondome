export const API_BASE_URL: string =
  (import.meta.env.VITE_API_URL as string | undefined) ?? 'http://127.0.0.1:8000'

export const DEVICES_POLL_MS = 30_000
export const PRESENCE_POLL_MS = 10_000

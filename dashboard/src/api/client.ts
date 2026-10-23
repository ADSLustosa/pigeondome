import { API_BASE_URL } from '../config'
import type { BucketName, Device, Presence, Problem, Series, TimeRange } from './types'

export class ApiError extends Error {
  readonly status: number
  readonly problem: Problem | null

  constructor(message: string, status: number, problem: Problem | null = null) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.problem = problem
  }
}

async function toApiError(response: Response): Promise<ApiError> {
  const contentType = response.headers.get('content-type') ?? ''
  if (contentType.includes('application/problem+json')) {
    try {
      const problem = (await response.json()) as Problem
      return new ApiError(problem.detail, response.status, problem)
    } catch {
      // corpo ilegível: cai na mensagem genérica abaixo
    }
  }
  return new ApiError(`A API respondeu com erro ${response.status}`, response.status)
}

async function getJson<T>(path: string, signal?: AbortSignal): Promise<T> {
  let response: Response
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      signal,
      headers: { Accept: 'application/json' },
    })
  } catch (cause) {
    if (signal?.aborted) throw cause
    throw new ApiError('Não foi possível conectar à API', 0)
  }
  if (!response.ok) throw await toApiError(response)
  return (await response.json()) as T
}

export function listDevices(signal?: AbortSignal): Promise<Device[]> {
  return getJson<Device[]>('/api/v1/devices', signal)
}

export function getPresence(
  deviceId: string,
  range: TimeRange,
  signal?: AbortSignal,
): Promise<Presence> {
  const query = new URLSearchParams({ start: range.start, end: range.end })
  const path = `/api/v1/devices/${encodeURIComponent(deviceId)}/presence?${query.toString()}`
  return getJson<Presence>(path, signal)
}

export function getSeries(
  deviceId: string,
  range: TimeRange,
  bucket: BucketName,
  signal?: AbortSignal,
): Promise<Series> {
  const query = new URLSearchParams({ start: range.start, end: range.end, bucket })
  const path = `/api/v1/devices/${encodeURIComponent(deviceId)}/presence/series?${query.toString()}`
  return getJson<Series>(path, signal)
}

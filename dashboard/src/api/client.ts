import { API_BASE_URL } from '../config'
import type {
  ActuatorEvents,
  ActuatorStatus,
  BucketName,
  Controller,
  Decisions,
  Device,
  KillSwitch,
  Presence,
  Problem,
  Series,
  TimeRange,
} from './types'

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

interface RequestOptions {
  method?: 'GET' | 'POST'
  headers?: Record<string, string>
  accept?: string
  signal?: AbortSignal
}

async function request<T>(
  path: string,
  options: RequestOptions,
  read: (response: Response) => Promise<T>,
): Promise<T> {
  let response: Response
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      method: options.method,
      signal: options.signal,
      headers: { Accept: options.accept ?? 'application/json', ...options.headers },
    })
  } catch (cause) {
    if (options.signal?.aborted) throw cause
    throw new ApiError('Não foi possível conectar à API', 0)
  }
  if (!response.ok) throw await toApiError(response)
  return read(response)
}

function requestJson<T>(path: string, options: RequestOptions): Promise<T> {
  return request(path, options, async (response) => (await response.json()) as T)
}

function getJson<T>(path: string, signal?: AbortSignal): Promise<T> {
  return requestJson<T>(path, { signal })
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

const actuatorPath = (actuatorId: string): string =>
  `/api/v1/actuators/${encodeURIComponent(actuatorId)}`

export function getController(signal?: AbortSignal): Promise<Controller> {
  return getJson<Controller>('/api/v1/controller', signal)
}

export function getActuatorStatus(
  actuatorId: string,
  signal?: AbortSignal,
): Promise<ActuatorStatus> {
  return getJson<ActuatorStatus>(`${actuatorPath(actuatorId)}/status`, signal)
}

export function getDecisions(
  actuatorId: string,
  limit: number,
  signal?: AbortSignal,
): Promise<Decisions> {
  const query = new URLSearchParams({ limit: String(limit) })
  return getJson<Decisions>(`${actuatorPath(actuatorId)}/decisions?${query.toString()}`, signal)
}

export function getActuatorEvents(
  actuatorId: string,
  limit: number,
  signal?: AbortSignal,
): Promise<ActuatorEvents> {
  const query = new URLSearchParams({ limit: String(limit) })
  return getJson<ActuatorEvents>(`${actuatorPath(actuatorId)}/events?${query.toString()}`, signal)
}

/**
 * Liga a chave geral. A API não oferece o caminho inverso: desligá-la (voltar a permitir
 * pulsos) é só pelo script local, na máquina do banco. O cabeçalho força o preflight de CORS.
 */
export function engageKillSwitch(signal?: AbortSignal): Promise<KillSwitch> {
  return requestJson<KillSwitch>('/api/v1/controller/kill-switch', {
    method: 'POST',
    headers: { 'X-Pigeondome-Action': 'kill-switch-on' },
    signal,
  })
}

/**
 * O quadro mais recente da câmera (JPEG). A API repassa a imagem sem gravá-la, e o painel só a
 * guarda na memória, como um endereço blob: liberado ao trocar de quadro.
 */
export function getSnapshot(deviceId: string, signal?: AbortSignal): Promise<Blob> {
  const path = `/api/v1/devices/${encodeURIComponent(deviceId)}/snapshot`
  return request(path, { signal, accept: 'image/jpeg' }, async (response) => {
    const type = response.headers.get('content-type') ?? ''
    if (!type.includes('image/jpeg')) {
      throw new ApiError('A API não devolveu uma imagem', response.status)
    }
    return response.blob()
  })
}

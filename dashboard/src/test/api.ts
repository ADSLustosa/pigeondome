import { vi } from 'vitest'

export interface Call {
  url: string
  method: string
  headers: Headers
}

export interface Route {
  method: string
  fragment: string
  reply: () => Response
}

export const json = (body: unknown, status = 200): Response =>
  new Response(JSON.stringify(body), {
    status,
    headers: { 'content-type': 'application/json' },
  })

/** Erro no formato da API (RFC 9457, application/problem+json). */
export const problem = (status: number, detail: string): Response =>
  new Response(JSON.stringify({ type: 'about:blank', title: 'Erro', status, detail }), {
    status,
    headers: { 'content-type': 'application/problem+json' },
  })

/** Resposta de sucesso fixa. */
export const ok = (body: unknown) => (): Response => json(body)

export const get = (fragment: string, reply: () => Response): Route => ({
  method: 'GET',
  fragment,
  reply,
})

export const post = (fragment: string, reply: () => Response): Route => ({
  method: 'POST',
  fragment,
  reply,
})

/**
 * Simula a API: a primeira rota cujo método e fragmento de URL batem responde (cada chamada
 * recebe uma Response nova, porque o corpo só se lê uma vez). O resto é 404.
 */
export function mockApi(routes: readonly Route[]): { calls: Call[] } {
  const calls: Call[] = []
  vi.stubGlobal(
    'fetch',
    vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const call: Call = {
        url: String(input),
        method: (init?.method ?? 'GET').toUpperCase(),
        headers: new Headers(init?.headers),
      }
      calls.push(call)
      const route = routes.find((r) => r.method === call.method && call.url.includes(r.fragment))
      return Promise.resolve(route ? route.reply() : new Response('{}', { status: 404 }))
    }),
  )
  return { calls }
}

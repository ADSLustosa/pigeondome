import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { mockApi, ok, post, problem } from '../test/api'
import { KillSwitchCard } from './KillSwitchCard'

const KILL_SWITCH = '/controller/kill-switch'

describe('KillSwitchCard', () => {
  it('fica ocupado, sem botão, enquanto o estado do controlador não chega', () => {
    render(<KillSwitchCard engaged={null} onEngaged={vi.fn()} />)
    expect(screen.getByRole('article', { name: 'Chave geral' })).toHaveAttribute(
      'aria-busy',
      'true',
    )
    expect(screen.queryByRole('button')).not.toBeInTheDocument()
  })

  it('liga a chave com o cabeçalho de confirmação e avisa o painel', async () => {
    const api = mockApi([post(KILL_SWITCH, ok({ kill_switch: true }))])
    const onEngaged = vi.fn()
    render(<KillSwitchCard engaged={false} onEngaged={onEngaged} />)
    fireEvent.click(screen.getByRole('button', { name: 'Ligar a chave geral' }))
    expect(await screen.findByRole('status')).toHaveTextContent(/aguardando a confirmação/i)
    expect(onEngaged).toHaveBeenCalledTimes(1)
    expect(api.calls[0]?.method).toBe('POST')
    expect(api.calls[0]?.headers.get('X-Pigeondome-Action')).toBe('kill-switch-on')
    expect(screen.queryByRole('button')).not.toBeInTheDocument()
  })

  it('mostra o erro e deixa tentar de novo quando a API recusa', async () => {
    mockApi([
      post(KILL_SWITCH, () => problem(503, 'o armazenamento de dados está temporariamente indisponível')),
    ])
    const onEngaged = vi.fn()
    render(<KillSwitchCard engaged={false} onEngaged={onEngaged} />)
    fireEvent.click(screen.getByRole('button', { name: 'Ligar a chave geral' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('temporariamente indisponível')
    expect(onEngaged).not.toHaveBeenCalled()
    expect(screen.getByRole('button', { name: 'Ligar a chave geral' })).toBeEnabled()
  })

  it('com a chave ligada, não oferece botão e explica como desligar', () => {
    render(<KillSwitchCard engaged onEngaged={vi.fn()} />)
    expect(screen.getByText('Ligada')).toBeInTheDocument()
    expect(screen.getByText(/kill-switch\.ps1 off/)).toBeInTheDocument()
    expect(screen.queryByRole('button')).not.toBeInTheDocument()
  })
})

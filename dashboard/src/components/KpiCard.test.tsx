import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { KpiCard } from './KpiCard'

describe('KpiCard', () => {
  it('mostra o rótulo, o valor e a dica', () => {
    render(<KpiCard label="Leituras" value="57" hint="no período" loading={false} />)
    expect(screen.getByRole('heading', { name: 'Leituras' })).toBeInTheDocument()
    expect(screen.getByText('57')).toBeInTheDocument()
    expect(screen.getByText('no período')).toBeInTheDocument()
  })

  it('indica carregamento para leitores de tela', () => {
    render(<KpiCard label="Leituras" value={null} hint="no período" loading />)
    expect(screen.getByText('Carregando')).toBeInTheDocument()
    expect(screen.getByRole('article')).toHaveAttribute('aria-busy', 'true')
  })
})

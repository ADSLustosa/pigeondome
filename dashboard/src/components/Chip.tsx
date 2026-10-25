import type { ReactNode } from 'react'
import type { Tone } from '../lib/actuation'

export function Chip({ tone, children }: { tone: Tone; children: ReactNode }) {
  return (
    <span className={`act-chip act-chip--${tone}`}>
      <span className="act-chip__dot" aria-hidden="true" />
      {children}
    </span>
  )
}

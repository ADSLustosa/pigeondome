import type { ReactNode } from 'react'

interface CardShellProps {
  id: string
  title: string
  chip?: ReactNode
  busy?: boolean
  outdated?: boolean
  children: ReactNode
}

export function CardShell({
  id,
  title,
  chip,
  busy = false,
  outdated = false,
  children,
}: CardShellProps) {
  return (
    <article
      className={outdated ? 'act-card act-card--outdated' : 'act-card'}
      aria-labelledby={id}
      aria-busy={busy}
    >
      <header className="act-card__head">
        <h3 id={id} className="act-card__title">
          {title}
        </h3>
        {chip}
      </header>
      <div className="act-card__body">{children}</div>
    </article>
  )
}

export function Facts({ items }: { items: readonly (readonly [label: string, value: string])[] }) {
  return (
    <dl className="act-facts">
      {items.map(([label, value]) => (
        <div key={label} className="act-facts__row">
          <dt>{label}</dt>
          <dd>{value}</dd>
        </div>
      ))}
    </dl>
  )
}

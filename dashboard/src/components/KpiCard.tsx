interface KpiCardProps {
  label: string
  value: string | null
  hint: string
  loading: boolean
}

export function KpiCard({ label, value, hint, loading }: KpiCardProps) {
  const showSkeleton = loading || value === null
  return (
    <article className="kpi" aria-busy={showSkeleton}>
      <h3 className="kpi__label">{label}</h3>
      <p className="kpi__value">
        {showSkeleton ? (
          <>
            <span className="skeleton" aria-hidden="true" />
            <span className="visually-hidden">Carregando</span>
          </>
        ) : (
          value
        )}
      </p>
      <p className="kpi__hint">{hint}</p>
    </article>
  )
}

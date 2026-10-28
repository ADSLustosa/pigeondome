/** Simbolo oficial da marca (cúpula e voo). As cores vêm dos tokens, então vale nos dois temas. */
export function Logo() {
  return (
    <svg viewBox="0 0 120 84" width="46" height="32" aria-hidden="true" focusable="false">
      <g fill="none" strokeLinecap="round" strokeLinejoin="round">
        <path d="M12 76 A48 48 0 0 1 108 76" strokeWidth="8" style={{ stroke: 'var(--text)' }} />
        <path d="M28 76 A32 32 0 0 1 92 76" strokeWidth="4" style={{ stroke: 'var(--accent)' }} />
        <path
          d="M84 18 Q91 9 98 16 Q105 8 113 11"
          strokeWidth="4.5"
          style={{ stroke: 'var(--text)' }}
        />
      </g>
    </svg>
  )
}

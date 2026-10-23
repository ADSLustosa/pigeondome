export function Logo() {
  return (
    <svg viewBox="0 0 48 48" width="40" height="40" aria-hidden="true" focusable="false">
      <defs>
        <linearGradient id="pigeondome-logo" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#38BDF8" />
          <stop offset="1" stopColor="#34D399" />
        </linearGradient>
      </defs>
      <circle cx="24" cy="24" r="4" fill="url(#pigeondome-logo)" />
      <circle cx="24" cy="24" r="10" fill="none" stroke="url(#pigeondome-logo)" strokeWidth="2.5" opacity="0.8" />
      <circle cx="24" cy="24" r="16" fill="none" stroke="url(#pigeondome-logo)" strokeWidth="2.5" opacity="0.5" />
      <circle cx="24" cy="24" r="22" fill="none" stroke="url(#pigeondome-logo)" strokeWidth="2.5" opacity="0.28" />
    </svg>
  )
}

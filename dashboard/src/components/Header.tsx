import type { Theme } from '../hooks/useTheme'
import { Logo } from './Logo'
import type { ConnectionStatus } from './StatusChip'
import { StatusChip } from './StatusChip'
import { ThemeToggle } from './ThemeToggle'

interface HeaderProps {
  status: ConnectionStatus
  theme: Theme
  onToggleTheme: () => void
}

export function Header({ status, theme, onToggleTheme }: HeaderProps) {
  return (
    <header className="app-header">
      <div className="container app-header__inner">
        <div className="brand">
          <Logo />
          <div>
            <h1 className="brand__name">Pigeondome</h1>
            <p className="brand__tagline">Monitoramento de pombos com IoT</p>
          </div>
        </div>
        <div className="app-header__actions">
          <StatusChip status={status} />
          <ThemeToggle theme={theme} onToggle={onToggleTheme} />
        </div>
      </div>
    </header>
  )
}

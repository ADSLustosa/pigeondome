export type ConnectionStatus = 'connecting' | 'online' | 'offline'

const LABELS: Record<ConnectionStatus, string> = {
  connecting: 'Conectando…',
  online: 'API online',
  offline: 'Sem conexão',
}

export function StatusChip({ status }: { status: ConnectionStatus }) {
  return (
    <p className={`status-chip status-chip--${status}`} role="status">
      <span className="status-chip__dot" aria-hidden="true" />
      {LABELS[status]}
    </p>
  )
}

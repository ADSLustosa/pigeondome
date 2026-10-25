import { useState } from 'react'
import { engageKillSwitch } from '../api/client'
import { CardShell } from './CardShell'
import { Chip } from './Chip'
import { ErrorNotice } from './ErrorNotice'

type Phase = 'idle' | 'sending' | 'sent' | 'error'

const TITLE_ID = 'kill-switch-title'

interface KillSwitchCardProps {
  /** null enquanto o estado do controlador ainda não chegou. */
  engaged: boolean | null
  /** Chamado depois que a API aceitou: o painel confirma o estado na hora. */
  onEngaged: () => void
}

/**
 * A chave geral só pode ser LIGADA daqui: parar o sistema é sempre seguro. Desligá-la (voltar a
 * permitir pulsos) exige estar na máquina do banco. Quem usa este cartão deve remontá-lo
 * (key) quando `engaged` mudar, para o estado local não sobreviver à mudança.
 */
export function KillSwitchCard({ engaged, onEngaged }: KillSwitchCardProps) {
  const [phase, setPhase] = useState<Phase>('idle')
  const [message, setMessage] = useState('')

  if (engaged === null) {
    return (
      <CardShell id={TITLE_ID} title="Chave geral" busy>
        <div className="act-skeleton" aria-hidden="true" />
        <span className="visually-hidden">Carregando</span>
      </CardShell>
    )
  }

  if (engaged) {
    return (
      <CardShell id={TITLE_ID} title="Chave geral" chip={<Chip tone="warning">Ligada</Chip>}>
        <p className="act-text">O controlador não envia nenhum comando ao atuador.</p>
        <p className="act-note">
          Por segurança, o painel só liga a chave. Para desligá-la, rode{' '}
          <code>scripts\kill-switch.ps1 off</code> na máquina do banco.
        </p>
      </CardShell>
    )
  }

  const engage = async () => {
    setPhase('sending')
    try {
      await engageKillSwitch()
    } catch (error) {
      setMessage(error instanceof Error ? error.message : String(error))
      setPhase('error')
      return
    }
    setPhase('sent')
    onEngaged()
  }

  const pending = phase === 'sending'
  return (
    <CardShell id={TITLE_ID} title="Chave geral" chip={<Chip tone="success">Desligada</Chip>}>
      <p className="act-text">
        Para o controlador na hora: nenhum novo comando é enviado ao atuador.
      </p>
      {phase === 'sent' ? (
        <p className="act-note act-note--warning" role="status">
          Comando enviado. Aguardando a confirmação do controlador…
        </p>
      ) : (
        <button
          type="button"
          className="act-button act-button--danger"
          disabled={pending}
          onClick={() => void engage()}
        >
          {pending ? 'Ligando…' : 'Ligar a chave geral'}
        </button>
      )}
      <p className="act-hint">
        Só pode ser desligada na máquina do banco, com <code>scripts\kill-switch.ps1 off</code>.
      </p>
      {phase === 'error' ? (
        <ErrorNotice title="Não foi possível ligar a chave geral" message={message} />
      ) : null}
    </CardShell>
  )
}

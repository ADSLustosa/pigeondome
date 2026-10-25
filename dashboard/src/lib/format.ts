const integer = new Intl.NumberFormat('pt-BR')
const percent = new Intl.NumberFormat('pt-BR', { style: 'percent', maximumFractionDigits: 1 })
const time = new Intl.DateTimeFormat('pt-BR', { timeStyle: 'medium' })
const dateTime = new Intl.DateTimeFormat('pt-BR', { dateStyle: 'short', timeStyle: 'medium' })

export const formatInteger = (value: number): string => integer.format(value)
export const formatPercent = (ratio: number): string => percent.format(ratio)
export const formatTime = (date: Date): string => time.format(date)
export const formatDateTime = (iso: string): string => dateTime.format(new Date(iso))

export function formatDecimal(value: number, digits = 1): string {
  return new Intl.NumberFormat('pt-BR', {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  }).format(value)
}

const logTime = new Intl.DateTimeFormat('pt-BR', {
  day: '2-digit',
  month: '2-digit',
  hour: '2-digit',
  minute: '2-digit',
  second: '2-digit',
})

/** Dia, mês e hora com segundos: para as linhas das trilhas, que cobrem até 24 h. */
export const formatLogTime = (iso: string): string => logTime.format(new Date(iso))

/** Duração curta em português ("6 s", "2 min 5 s", "1 h 3 min", "2 d 4 h"). Nunca negativa. */
export function formatAge(seconds: number): string {
  const total = Math.max(0, Math.floor(seconds))
  if (total < 60) return `${total} s`
  const minutes = Math.floor(total / 60)
  if (total < 3600) {
    const rest = total % 60
    return rest === 0 ? `${minutes} min` : `${minutes} min ${rest} s`
  }
  const hours = Math.floor(total / 3600)
  if (total < 86_400) {
    const rest = minutes % 60
    return rest === 0 ? `${hours} h` : `${hours} h ${rest} min`
  }
  const days = Math.floor(total / 86_400)
  const rest = hours % 24
  return rest === 0 ? `${days} d` : `${days} d ${rest} h`
}

const clockWithSeconds = new Intl.DateTimeFormat('pt-BR', {
  hour: '2-digit',
  minute: '2-digit',
  second: '2-digit',
})
const clockMinutes = new Intl.DateTimeFormat('pt-BR', { hour: '2-digit', minute: '2-digit' })
const dayMonth = new Intl.DateTimeFormat('pt-BR', { day: '2-digit', month: '2-digit' })

/** Hora de um instante ISO, no fuso do navegador: "20:01:42" ou, sem segundos, "20:01". */
export const formatClock = (iso: string, withSeconds: boolean): string =>
  (withSeconds ? clockWithSeconds : clockMinutes).format(new Date(iso))

/** Só dia e mês ("24/10"): a data completa fica no atributo title da linha da tabela. */
export const formatDayMonth = (iso: string): string => dayMonth.format(new Date(iso))

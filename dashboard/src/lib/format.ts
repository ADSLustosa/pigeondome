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

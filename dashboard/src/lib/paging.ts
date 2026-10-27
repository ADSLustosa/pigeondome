/** Quantidades de linhas que as trilhas oferecem. 50 é tudo o que a API devolve por vez. */
export const PAGE_SIZES = [5, 10, 25, 50] as const
export type PageSize = (typeof PAGE_SIZES)[number]

// Em tela estreita cada linha vira um cartão alto: começar com menos mantém a página curta.
const NARROW_SCREEN = '(max-width: 40rem)'

export function defaultPageSize(): PageSize {
  return isNarrowScreen() ? 5 : 10
}

export function shownText(shown: number, total: number, noun: string): string {
  return `Mostrando ${shown} de ${total} ${noun}. Aumente em “Linhas” para ver mais.`
}

/** Tela estreita (celular): a interface começa com menos conteúdo aberto. */
export function isNarrowScreen(): boolean {
  return window.matchMedia(NARROW_SCREEN).matches
}

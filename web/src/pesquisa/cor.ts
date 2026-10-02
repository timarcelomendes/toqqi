/** Normaliza para #rrggbb; se não for uma cor válida, devolve o padrão. */
export function corValida(cor: string | null | undefined, padrao = '#ff5a36'): string {
  const c = (cor ?? '').trim().toLowerCase()
  if (/^#[0-9a-f]{6}$/.test(c)) return c
  if (/^#[0-9a-f]{3}$/.test(c)) return `#${c[1]}${c[1]}${c[2]}${c[2]}${c[3]}${c[3]}`
  return padrao
}

function luminancia(hex: string): number {
  const canal = (i: number) => {
    const v = parseInt(hex.slice(i, i + 2), 16) / 255
    return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4
  }
  return 0.2126 * canal(1) + 0.7152 * canal(3) + 0.0722 * canal(5)
}

/** Texto legível sobre a cor: branco ou quase preto, o que der mais contraste. */
export function corDoTexto(fundo: string): string {
  const l = luminancia(corValida(fundo))
  const contrasteBranco = 1.05 / (l + 0.05)
  const contrastePreto = (l + 0.05) / 0.05
  return contrasteBranco >= contrastePreto || contrasteBranco >= 4.5 ? '#ffffff' : '#111827'
}

/** Variáveis CSS da cor da pesquisa (botões, foco, fundos suaves), as mesmas da página pública. */
export function variaveisDaCor(cor: string | null | undefined): Record<string, string> {
  const c = corValida(cor)
  return { '--cor': c, '--cor-texto': corDoTexto(c), '--cor-suave': `color-mix(in srgb, ${c} 10%, white)` }
}

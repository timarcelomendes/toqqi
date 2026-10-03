// Regras puras do visual dos e-mails de pesquisa (docs/api-etapa-5e.md §2): cor de destaque, contraste do texto do
// botão, limites da assinatura e do rodapé e a conferência antes de salvar. Sem Vue, para testar com facilidade.
// A montagem da prévia fica em `mensagens.ts` (`montarPreviaEmail`), com as mesmas regras da API (`mensagens.py`).

/** Sem cor da conta e sem cor válida no formulário: o coral dos botões do Toqqi. */
export const COR_PADRAO_EMAIL = '#D63A18'
/** Texto do botão quando o branco não tem contraste de 4,5:1 com a cor de destaque. */
export const TEXTO_ESCURO_BOTAO = '#111827'
export const TEXTO_CLARO_BOTAO = '#ffffff'
/** Contraste mínimo (WCAG AA, texto normal) para o texto branco sobre a cor de destaque. */
export const CONTRASTE_MINIMO = 4.5

export const LIMITE_ASSINATURA = 300
export const LIMITE_RODAPE = 500

/**
 * Sugestões de cor de destaque: todas com texto branco legível (contraste ≥ 4,5:1), para o botão "Responder pesquisa"
 * não ficar com texto escuro sem a pessoa querer.
 */
export const SUGESTOES_COR_EMAIL: readonly { cor: string; nome: string }[] = [
  { cor: '#D63A18', nome: 'Coral' },
  { cor: '#2563EB', nome: 'Azul' },
  { cor: '#0E7490', nome: 'Turquesa' },
  { cor: '#047857', nome: 'Verde' },
  { cor: '#7C3AED', nome: 'Roxo' },
  { cor: '#0F172A', nome: 'Grafite' },
]

const HEX = /^#[0-9a-fA-F]{6}$/

/** `#RRGGBB` (maiúsculas ou minúsculas), o único formato que a API aceita em `email_cor`. */
export function corHexValida(v: unknown): v is string {
  return typeof v === 'string' && HEX.test(v)
}

/** Lê o que foi digitado ("d63a18", " #D63A18 ") e devolve `#RRGGBB` em maiúsculas, ou null se não for uma cor. */
export function normalizarCorHex(v: string | null | undefined): string | null {
  const t = (v ?? '').trim()
  if (!t) return null
  const c = t.startsWith('#') ? t : `#${t}`
  return HEX.test(c) ? c.toUpperCase() : null
}

function canal(hex: string, inicio: number): number {
  const v = Number.parseInt(hex.slice(inicio, inicio + 2), 16) / 255
  return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4
}

/** Luminância relativa (WCAG 2) de uma cor `#RRGGBB`. */
export function luminancia(hex: string): number {
  return 0.2126 * canal(hex, 1) + 0.7152 * canal(hex, 3) + 0.0722 * canal(hex, 5)
}

/** Razão de contraste (WCAG 2) entre duas cores `#RRGGBB`, de 1 a 21. */
export function contraste(a: string, b: string): number {
  const la = luminancia(a)
  const lb = luminancia(b)
  return (Math.max(la, lb) + 0.05) / (Math.min(la, lb) + 0.05)
}

/** Texto do botão sobre a cor de destaque: branco se o contraste com o branco for ≥ 4,5:1, senão `#111827`. */
export function corTextoBotao(cor: string): string {
  const c = corHexValida(cor) ? cor : COR_PADRAO_EMAIL
  return contraste(c, TEXTO_CLARO_BOTAO) >= CONTRASTE_MINIMO ? TEXTO_CLARO_BOTAO : TEXTO_ESCURO_BOTAO
}

/** A cor é clara demais para texto branco: o botão sai com o texto escuro (a tela avisa). */
export function textoDoBotaoEscuro(cor: string | null | undefined): boolean {
  return corHexValida(cor) && corTextoBotao(cor) === TEXTO_ESCURO_BOTAO
}

/**
 * Cor de destaque do e-mail (faixa do topo, botão "Responder pesquisa" e links do corpo): a da conta (`email_cor`);
 * sem ela, a do tema do formulário do envio; se nenhuma for válida, o coral padrão.
 */
export function corDestaque(emailCor: string | null | undefined, temaCor: string | null | undefined): string {
  if (corHexValida(emailCor)) return emailCor
  if (corHexValida(temaCor)) return temaCor
  return COR_PADRAO_EMAIL
}

// Caracteres de controle: a API só aceita a quebra de linha (e o \r de uma quebra de linha do Windows).
const CONTROLE = /[\u0000-\u0009\u000B\u000C\u000E-\u001F\u007F]/

/** O que a tela manda no PUT para o visual (com a imagem de topo pelo id). */
export interface CamposVisualEmail {
  email_cor?: string | null
  email_mostrar_logo?: boolean
  email_assinatura?: string | null
  email_rodape?: string | null
}

function conferirTexto(v: string | null | undefined, limite: number): string | null {
  const t = (v ?? '').trim()
  if (!t) return null
  if (t.length > limite) return `Use até ${limite} caracteres.`
  if (CONTROLE.test(t)) return 'Tire os caracteres invisíveis, como a tabulação. Só as quebras de linha valem.'
  return null
}

/**
 * Confere o visual antes de salvar (as mesmas regras da API). Só olha os campos que vieram: uma configuração da API
 * antiga, sem o visual, passa. Chaves iguais às de `campos` da API.
 */
export function validarVisual(c: CamposVisualEmail): Record<string, string> {
  const e: Record<string, string> = {}
  if (c.email_cor !== undefined && c.email_cor !== null && !corHexValida(c.email_cor)) {
    e.email_cor = 'Use o formato #RRGGBB, por exemplo #D63A18.'
  }
  const assinatura = conferirTexto(c.email_assinatura, LIMITE_ASSINATURA)
  if (assinatura) e.email_assinatura = assinatura
  const rodape = conferirTexto(c.email_rodape, LIMITE_RODAPE)
  if (rodape) e.email_rodape = rodape
  return e
}

/** Texto opcional para o PUT: sem espaços nas pontas; vazio vira null (a API faz o mesmo). */
export function textoOuNulo(v: string | null | undefined): string | null {
  const t = (v ?? '').trim()
  return t ? t : null
}

/** "1200 × 400 px" (ou null quando a API não conseguiu ler as dimensões). */
export function textoDimensoes(largura: number | null | undefined, altura: number | null | undefined): string | null {
  return largura && altura ? `${largura} × ${altura} px` : null
}

/** Largura da imagem de topo no e-mail (o cartão de 600 px menos as margens), como a API (`width="544"`). */
export const LARGURA_IMAGEM_TOPO = 544

/** Teto da altura (o dobro da largura), como a API: uma imagem de proporção absurda não vira um `height` gigante. */
export const ALTURA_MAXIMA_IMAGEM_TOPO = 2 * LARGURA_IMAGEM_TOPO

/** Altura proporcional da imagem de topo na largura do e-mail, até o teto (null sem as dimensões). */
export function alturaImagemTopo(largura: number | null | undefined, altura: number | null | undefined): number | null {
  if (!largura || !altura) return null
  return Math.min(ALTURA_MAXIMA_IMAGEM_TOPO, Math.max(1, Math.round((LARGURA_IMAGEM_TOPO * altura) / largura)))
}

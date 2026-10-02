// Aceite dos Termos de uso e da Política de privacidade (docs/api-aceite-lgpd.md §3): quem decide para onde a pessoa
// vai (guarda de rotas) e os textos da tela "Antes de continuar". Sem Vue nem router aqui: fácil de testar.
import type { Aceite } from '@/api/tipos'
import { formatarData } from '@/utils/datas'
import { destinoSeguro } from '@/utils/validacao'
import { VIGENTE_DESDE } from './versao'

/**
 * Páginas que quem tem aceite pendente ainda pode abrir. `/assinatura` fica livre para o administrador poder cancelar
 * sem aceitar a versão nova (o CDC não permite condicionar o cancelamento ao aceite); a rota já exige a permissão
 * `assinatura.gerenciar`. O menu do AppLayout leva a outras telas, mas a guarda manda de volta ao aceite.
 */
export const ROTAS_LIVRES = ['/aceite', '/termos', '/privacidade', '/confirmar-email', '/redefinir-senha', '/assinatura'] as const

const PADRAO = '/inicio'

/**
 * Endereço para onde ir depois de aceitar: só caminho interno (`destinoSeguro`, a mesma regra do "voltar" de Entrar)
 * e que não seja a própria tela de aceite. Qualquer outra coisa vira /inicio.
 */
export function destinoDepoisDoAceite(de: unknown): string {
  const destino = destinoSeguro(de, PADRAO)
  if (destino === '/aceite' || destino.startsWith('/aceite?') || destino.startsWith('/aceite#')) return PADRAO
  return destino
}

/** O aceite está pendente? Sem a informação (API antiga, sessão sem o campo), não bloqueia. */
export function aceitePendente(aceite: Aceite | null | undefined): boolean {
  return !!aceite?.pendente
}

function livre(caminho: string): boolean {
  return (ROTAS_LIVRES as readonly string[]).includes(caminho)
}

interface Destino {
  path: string
  fullPath: string
  meta: { logado?: boolean }
}

/**
 * Guarda de rotas do aceite. Devolve para onde redirecionar, ou null para seguir.
 * - Logado com aceite pendente abrindo uma página do app (meta `logado`) → /aceite?de=<caminho>.
 * - As páginas de ROTAS_LIVRES ficam livres (inclusive a própria /aceite).
 * - Logado sem pendência abrindo /aceite → /inicio.
 */
export function redirecionarAceite(
  to: Destino,
  sessao: { logado: boolean; aceite: Aceite | null | undefined },
): { path: string; query?: Record<string, string> } | null {
  if (!sessao.logado) return null
  const pendente = aceitePendente(sessao.aceite)
  if (to.path === '/aceite') return pendente ? null : { path: PADRAO }
  if (!pendente || livre(to.path) || !to.meta.logado) return null
  const de = destinoDepoisDoAceite(to.fullPath)
  return { path: '/aceite', query: de !== PADRAO ? { de } : {} }
}

/** Primeira frase da tela: muda quando a pessoa já aceitou uma versão anterior (é uma versão nova). */
export function textoAbertura(aceite: Aceite | null | undefined, vigenteDesde = VIGENTE_DESDE): string {
  if (aceite && aceite.versao_aceita !== null && aceite.versao_aceita !== undefined) {
    return `Atualizamos os Termos de uso e a Política de privacidade em ${formatarData(vigenteDesde)}.`
  }
  return 'Para usar o Toqqi, leia e aceite os Termos de uso e a Política de privacidade.'
}

/** "Versão 1 · vigente desde 02/10/2026" */
export function textoVersao(versao: number, vigenteDesde = VIGENTE_DESDE): string {
  return `Versão ${versao} · vigente desde ${formatarData(vigenteDesde)}`
}

/** Frase do cartão "Privacidade" em Minha conta. */
export function textoAceiteRegistrado(aceite: Aceite | null | undefined, formatarDataHora: (v: string) => string): string {
  if (!aceite || aceite.versao_aceita === null || !aceite.aceito_em) {
    return 'Ainda não há registro do seu aceite dos Termos de uso e da Política de privacidade.'
  }
  return `Você aceitou os Termos de uso e a Política de privacidade (versão ${aceite.versao_aceita}) em ${formatarDataHora(aceite.aceito_em)}.`
}

// Regras puras da tela Configurações › Planos de ação (prazos de 1 a 90 dias).
import type { ConfigAcoes } from '@/api/tipos'

export type ChavePrazo = 'prazo_detrator' | 'prazo_neutro' | 'prazo_promotor'

export const PRAZO_MINIMO = 1
export const PRAZO_MAXIMO = 90

export const PRAZOS_ACOES: { chave: ChavePrazo; rotulo: string; descricao: string }[] = [
  { chave: 'prazo_detrator', rotulo: 'Detrator (nota 0 a 6)', descricao: 'A ação nasce com prioridade alta. Se o responsável da empresa tiver e-mail, ele recebe um alerta na hora.' },
  { chave: 'prazo_neutro', rotulo: 'Neutro (nota 7 ou 8)', descricao: 'A ação nasce com prioridade média.' },
  { chave: 'prazo_promotor', rotulo: 'Promotor (nota 9 ou 10)', descricao: 'Só vale se "Criar ação também para promotores" estiver ligado. Prioridade baixa.' },
]

function inteiro(v: string): number {
  return /^\s*\d+\s*$/.test(v) ? Number.parseInt(v, 10) : Number.NaN
}

/** Erros por campo (mesmas chaves da API). */
export function validarConfigAcoes(texto: Record<ChavePrazo, string>): Partial<Record<ChavePrazo, string>> {
  const erros: Partial<Record<ChavePrazo, string>> = {}
  for (const { chave } of PRAZOS_ACOES) {
    const n = inteiro(texto[chave])
    if (!Number.isInteger(n) || n < PRAZO_MINIMO || n > PRAZO_MAXIMO) erros[chave] = 'Use um número de dias de 1 a 90.'
  }
  return erros
}

/** A configuração pronta para salvar (os números digitados viram números). */
export function montarConfigAcoes(texto: Record<ChavePrazo, string>, acaoPromotor: boolean): ConfigAcoes {
  return {
    prazo_detrator: inteiro(texto.prazo_detrator),
    prazo_neutro: inteiro(texto.prazo_neutro),
    prazo_promotor: inteiro(texto.prazo_promotor),
    acao_promotor: acaoPromotor,
  }
}

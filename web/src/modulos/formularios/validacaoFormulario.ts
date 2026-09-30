import { faixa, gruposDoTipo, indicePrincipal } from '@/pesquisa/logica'
import type { Pergunta } from '@/api/tipos'

export const LIMITE_PERGUNTAS = 60

/**
 * Confere o formulário antes de salvar, com as mesmas regras da API.
 * As chaves seguem o formato da API: `perguntas.<indice>.<campo>`.
 */
export function validarFormulario(perguntas: Pergunta[], nome?: string): Record<string, string> {
  const erros: Record<string, string> = {}
  if (nome !== undefined && !nome.trim()) erros.nome = 'Dê um nome para o formulário.'
  if (perguntas.filter((p) => p.tipo !== 'quebra_pagina').length > LIMITE_PERGUNTAS) {
    erros.perguntas = `Use no máximo ${LIMITE_PERGUNTAS} perguntas.`
  }
  const ip = indicePrincipal(perguntas)
  const principal = ip >= 0 ? perguntas[ip]! : null

  perguntas.forEach((p, i) => {
    const k = (campo: string) => `perguntas.${i}.${campo}`
    if (p.tipo !== 'quebra_pagina' && !p.titulo?.trim()) erros[k('titulo')] = 'Escreva a pergunta.'

    if (p.tipo === 'escolha_unica' || p.tipo === 'escolha_multipla') {
      const opcoes = (p.opcoes ?? []).map((o) => o.trim())
      const normal = opcoes.map((o) => o.toLocaleLowerCase('pt-BR'))
      if (opcoes.some((o) => !o)) erros[k('opcoes')] = 'Tem opção em branco. Escreva ou apague.'
      else if (opcoes.length < 2) erros[k('opcoes')] = 'Coloque pelo menos 2 opções.'
      else if (opcoes.length > 30) erros[k('opcoes')] = 'Use no máximo 30 opções.'
      else if (new Set(normal).size !== normal.length) erros[k('opcoes')] = 'Tem opção repetida.'
    }

    if (p.tipo === 'escala') {
      const min = p.min ?? 1
      const max = p.max ?? 5
      if (min !== 0 && min !== 1) erros[k('min')] = 'A escala começa em 0 ou 1.'
      else if (max > 10 || max <= min + 1) erros[k('max')] = `O fim da escala vai de ${min + 2} a 10.`
    }

    if (p.condicao) {
      if (!principal || i <= ip) {
        erros[k('condicao')] = 'A condição só vale para perguntas depois da nota principal.'
      } else if (p.condicao.tipo === 'grupo') {
        const validos = new Set(gruposDoTipo(principal.tipo).map((g) => g.valor))
        if (!p.condicao.grupos?.length) erros[k('condicao')] = 'Escolha pelo menos um grupo.'
        else if (p.condicao.grupos.some((g) => !validos.has(g))) erros[k('condicao')] = 'Tem grupo que não combina com a nota principal.'
      } else if (p.condicao.tipo === 'nota') {
        const { min, max } = faixa(principal)
        const v = p.condicao.valor
        if (typeof v !== 'number' || v < min || v > max) erros[k('condicao')] = `Escolha uma nota de ${min} a ${max}.`
      }
    }
  })
  return erros
}

/** Separa os erros por índice de pergunta: {0: {titulo: '...'}}. */
export function errosPorPergunta(erros: Record<string, string>): Record<number, Record<string, string>> {
  const saida: Record<number, Record<string, string>> = {}
  for (const [chave, msg] of Object.entries(erros)) {
    const m = chave.match(/^perguntas\.(\d+)(?:\.(.+))?$/)
    if (!m) continue
    const i = Number(m[1])
    ;(saida[i] ??= {})[m[2] ?? '_'] = msg
  }
  return saida
}

// O topo de Planos de ação (docs/api-acoes-panorama.md): a frase dos prazos, a barra das abertas por prazo, a carga
// por responsável (com o filtro), as concluídas e o componente com a API simulada.
import { afterEach, beforeEach, describe, expect, it } from 'vitest'
import { enableAutoUnmount, flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import type { PanoramaAcoes } from '@/api/tipos'
import PanoramaView from '@/modulos/acoes/PanoramaAcoes.vue'
import { carga, comparacaoConcluidas, manchete, retorno, segmentosPrazo, tempoConclusao } from '@/modulos/acoes/panorama'
import { apiFalsa, type Chamada } from './apiFalsa'

const t = (s: string) => s.replace(/ /g, ' ').replace(/\s+/g, ' ').trim()
function textos(alvo: { element: Element }): string {
  const partes: string[] = []
  const passeio = document.createTreeWalker(alvo.element, NodeFilter.SHOW_TEXT)
  for (let n = passeio.nextNode(); n; n = passeio.nextNode()) {
    const s = t(n.textContent ?? '')
    if (s) partes.push(s)
  }
  return partes.join(' ')
}

function panorama(extra: Partial<PanoramaAcoes> = {}): PanoramaAcoes {
  return {
    prazos: { abertas: 7, vencidas: 4, hoje: 1, proximos_7_dias: 1, depois: 1, sem_prazo: 0 },
    responsaveis: [
      { responsavel: { id: 3, nome: 'Paula Souza' }, abertas: 2, vencidas: 2 },
      { responsavel: { id: 2, nome: 'Diego Martins' }, abertas: 4, vencidas: 1 },
      { responsavel: null, abertas: 1, vencidas: 0 },
    ],
    concluidas: {
      de: '2026-09-09',
      ate: '2026-10-08',
      total: 3,
      mediana_dias: 5.6,
      com_retorno: 1,
      anterior: { de: '2026-08-10', ate: '2026-09-08', total: 1, mediana_dias: 2, com_retorno: 0 },
    },
    ...extra,
  }
}
const prazos = (extra: Partial<PanoramaAcoes['prazos']>) => ({ ...panorama().prazos, ...extra })

describe('Planos de ação › panorama: regras', () => {
  it('a frase dos prazos', () => {
    expect(manchete(prazos({}))).toEqual({ titulo: '4 de 7 ações abertas estão vencidas', texto: 'E 1 vence hoje.', tom: 'erro' })
    expect(manchete(prazos({ abertas: 1, vencidas: 1, hoje: 0 }))).toEqual({ titulo: '1 de 1 ação aberta está vencida', texto: null, tom: 'erro' })
    expect(manchete(prazos({ vencidas: 0, hoje: 2 }))).toEqual({ titulo: 'Nenhuma vencida, mas 2 vencem hoje', texto: '7 ações abertas ao todo.', tom: 'atencao' })
    expect(manchete(prazos({ vencidas: 0, hoje: 0, sem_prazo: 2 }))).toEqual({ titulo: 'As 7 ações abertas estão em dia', texto: '2 estão sem prazo.', tom: 'sucesso' })
    expect(manchete(prazos({ abertas: 1, vencidas: 0, hoje: 0 })).titulo).toBe('A ação aberta está em dia')
    expect(manchete(prazos({ abertas: 0, vencidas: 0, hoje: 0 })).titulo).toBe('Nenhuma ação aberta')
  })

  it('a barra por prazo: só as partes com valor, "em dia" juntando os próximos 7 dias e depois', () => {
    expect(segmentosPrazo(prazos({})).map((s) => [s.chave, s.valor, s.rotulo, s.largura])).toEqual([
      ['vencidas', 4, 'vencidas', 57],
      ['hoje', 1, 'vence hoje', 14],
      ['em_dia', 2, 'em dia', 29],
    ])
    expect(segmentosPrazo(prazos({ abertas: 40, vencidas: 1, hoje: 0, proximos_7_dias: 30, depois: 0, sem_prazo: 9 })).map((s) => [s.rotulo, s.largura])).toEqual([
      ['vencida', 3],
      ['em dia', 75],
      ['sem prazo', 23],
    ])
    expect(segmentosPrazo(prazos({ abertas: 0, vencidas: 0, hoje: 0, proximos_7_dias: 0, depois: 0 }))).toEqual([])
  })

  it('a carga por responsável: o filtro de cada um, o detalhe e as barras', () => {
    expect(carga(panorama()).map((p) => [p.filtro, p.nome, p.detalhe, p.largura, p.parteVencida])).toEqual([
      [3, 'Paula Souza', '2 abertas, 2 vencidas', 50, 100],
      [2, 'Diego Martins', '4 abertas, 1 vencida', 100, 25],
      ['0', 'Sem responsável', '1 aberta', 25, 0],
    ])
  })

  it('as concluídas: o tempo até a metade, o retorno e a comparação', () => {
    const c = panorama().concluidas
    expect(tempoConclusao(c)).toBe('Metade concluída em até 6 dias')
    expect(tempoConclusao({ ...c, mediana_dias: 0.4 })).toBe('Metade concluída no mesmo dia')
    expect(tempoConclusao({ ...c, mediana_dias: null })).toBeNull()
    expect(retorno(c)).toBe('1 de 3 com retorno ao cliente')
    expect(retorno({ ...c, com_retorno: 0 })).toBe('Nenhuma com retorno ao cliente ainda')
    expect(retorno({ ...c, total: 0 })).toBeNull()
    expect(comparacaoConcluidas(c)).toEqual({ texto: '2 a mais que nos 30 dias anteriores', sentido: 'subiu' })
    expect(comparacaoConcluidas({ ...c, total: 1 })).toEqual({ texto: 'O mesmo que nos 30 dias anteriores', sentido: 'igual' })
    expect(comparacaoConcluidas({ ...c, total: 0 })).toEqual({ texto: '1 a menos que nos 30 dias anteriores', sentido: 'caiu' })
    expect(comparacaoConcluidas({ ...c, total: 0, anterior: { ...c.anterior, total: 0 } })).toBeNull()
  })
})

// ── Componente ──────────────────────────────────────────────────────────────

async function montar(resposta: (c: Chamada) => unknown, props: Partial<{ responsavel: string; soVencidas: boolean; versao: number }> = {}) {
  const { chamadas } = apiFalsa({ 'GET /acoes/panorama': resposta })
  const w = mount(PanoramaView, {
    props: { filtros: { grupo_id: '7' }, versao: 1, responsavel: '', soVencidas: false, ...props },
    attachTo: document.body,
  })
  await flushPromises()
  return { w, chamadas }
}

enableAutoUnmount(afterEach)
beforeEach(() => setActivePinia(createPinia()))
afterEach(() => {
  document.body.innerHTML = ''
})

describe('Planos de ação › panorama: componente', () => {
  it('mostra a frase, a barra com a legenda, quem está com quantas e as concluídas, com os filtros do quadro', async () => {
    const { w, chamadas } = await montar(() => panorama())
    expect(Object.fromEntries(chamadas[0]!.url.searchParams)).toEqual({ grupo_id: '7' })
    expect(t(w.get('[data-manchete-acoes]').text())).toBe('4 de 7 ações abertas estão vencidas')
    expect(w.get('[data-manchete-acoes]').classes()).toContain('text-erro')
    expect(w.findAll('[data-segmento]').map((s) => [s.attributes('data-segmento'), s.attributes('style')])).toEqual([
      ['vencidas', 'width: 57%;'],
      ['hoje', 'width: 14%;'],
      ['em_dia', 'width: 29%;'],
    ])
    expect(w.findAll('[data-legenda-prazo]').map((l) => textos(l).replace(/\s*:.*$/, ''))).toEqual(['4 vencidas', '1 vence hoje', '2 em dia'])
    expect(w.findAll('[data-pessoa]').map((p) => textos(p))).toEqual([
      'Paula Souza 2 abertas, 2 vencidas',
      'Diego Martins 4 abertas, 1 vencida',
      'Sem responsável 1 aberta',
    ])
    expect(t(w.get('[data-total-concluidas]').text())).toBe('3')
    expect(t(w.get('[data-comparacao-concluidas]').text())).toBe('2 a mais que nos 30 dias anteriores')
    expect(t(w.get('[data-tempo-conclusao]').text())).toBe('Metade concluída em até 6 dias')
    expect(t(w.get('[data-retorno]').text())).toBe('1 de 3 com retorno ao cliente')
  })

  it('um clique numa pessoa pede o filtro (outro clique tira); "vencidas" liga e desliga o "Só vencidas"', async () => {
    const { w } = await montar(() => panorama())
    await w.get('[data-pessoa="2"]').trigger('click')
    await w.get('[data-pessoa="0"]').trigger('click')
    expect(w.emitted('responsavel')).toEqual([[2], ['0']])
    expect(w.find('[data-filtro-pessoa]').exists()).toBe(false)
    await w.setProps({ responsavel: '2' })
    expect(w.get('[data-pessoa="2"]').attributes('aria-pressed')).toBe('true')
    expect(t(w.get('[data-filtro-pessoa]').text())).toBe('Só as de Diego Martins. Ver de todos')
    await w.get('[data-pessoa="2"]').trigger('click')
    expect(w.emitted('responsavel')!.at(-1)).toEqual([''])
    await w.get('[data-filtro-pessoa] button').trigger('click')
    expect(w.emitted('responsavel')!.at(-1)).toEqual([''])
    await w.setProps({ responsavel: '0' })
    expect(t(w.get('[data-filtro-pessoa]').text())).toBe('Só as sem responsável. Ver de todos')
    await w.setProps({ responsavel: '' })
    await w.get('[data-legenda-prazo="vencidas"] button').trigger('click')
    expect(w.emitted('soVencidas')).toEqual([[true]])
    await w.setProps({ soVencidas: true })
    expect(w.get('[data-legenda-prazo="vencidas"] button').attributes('aria-pressed')).toBe('true')
  })

  it('com mais de 5 pessoas, mostra 5 e "Ver mais"; uma versão nova do quadro busca de novo', async () => {
    const muitas = Array.from({ length: 7 }, (_, i) => ({ responsavel: { id: i + 1, nome: `Pessoa ${i + 1}` }, abertas: 7 - i, vencidas: 0 }))
    let vez = 0
    const { w, chamadas } = await montar(() => {
      vez += 1
      return panorama({ responsaveis: muitas, prazos: prazos({ vencidas: vez === 1 ? 4 : 0, hoje: 0 }) })
    })
    expect(w.findAll('[data-pessoa]')).toHaveLength(5)
    await w.findAll('button').find((b) => t(b.text()) === 'Ver mais 2')!.trigger('click')
    expect(w.findAll('[data-pessoa]')).toHaveLength(7)
    await w.setProps({ versao: 2 })
    await flushPromises()
    expect(chamadas).toHaveLength(2)
    expect(t(w.get('[data-manchete-acoes]').text())).toBe('As 7 ações abertas estão em dia')
  })

  it('erro na primeira carga: o aviso com "Tentar de novo"', async () => {
    let vez = 0
    const { w } = await montar(() => {
      vez += 1
      return vez === 1 ? new Response(JSON.stringify({ erro: { codigo: 'x', mensagem: 'Fora do ar.' } }), { status: 503 }) : panorama()
    })
    expect(t(w.text())).toContain('Não deu para carregar o resumo das ações')
    await w.findAll('button').find((b) => t(b.text()) === 'Tentar de novo')!.trigger('click')
    await flushPromises()
    expect(w.find('[data-manchete-acoes]').exists()).toBe(true)
  })
})

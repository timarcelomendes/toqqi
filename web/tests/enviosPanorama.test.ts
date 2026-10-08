// O topo de Envios (docs/api-envios-panorama.md): a frase do envio automático em cada estado, as regras em uma linha,
// a agenda dos 14 dias, a taxa de resposta com a comparação e o componente com a API simulada.
import { afterEach, beforeEach, describe, expect, it } from 'vitest'
import { enableAutoUnmount, flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createMemoryHistory, createRouter } from 'vue-router'
import type { PanoramaEnvios } from '@/api/tipos'
import { hojeIso } from '@/utils/datas'
import PanoramaView from '@/modulos/envios/PanoramaEnvios.vue'
import { agenda, detalheDia, hora, manchete, quandoDia, quandoRodada, regras, respondidas, tempoAteMetade, totalAgenda, variacaoTaxa } from '@/modulos/envios/panorama'
import { apiFalsa } from './apiFalsa'

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

/** 14 dias a partir de `hoje` ("2026-10-08", uma quinta): o sábado e o domingo sem envio. */
function dias(hoje: string, valores: [number, number][] = []): PanoramaEnvios['agenda'] {
  const [a, m, d] = hoje.split('-').map(Number) as [number, number, number]
  return Array.from({ length: 14 }, (_, i) => {
    const data = new Date(a, m - 1, d + i, 12)
    const dia = `${data.getFullYear()}-${String(data.getMonth() + 1).padStart(2, '0')}-${String(data.getDate()).padStart(2, '0')}`
    const [pesquisas, lembretes] = valores[i] ?? [0, 0]
    return { dia, pesquisas, lembretes, sai: data.getDay() !== 0 && data.getDay() !== 6 }
  })
}

function panorama(extra: Partial<PanoramaEnvios> = {}, hoje = '2026-10-08'): PanoramaEnvios {
  return {
    automatico: {
      estado: 'ligado',
      proxima_rodada: `${hoje}T14:00:00-03:00`,
      na_fila: 12,
      fora_da_rodada: 0,
      por_rodada: 100,
      proximo_contato: null,
      janela_inicio: '08:00',
      janela_fim: '18:00',
      so_dias_uteis: true,
      intervalo_dias: 90,
      canal: 'email',
      lembretes: 3,
    },
    agenda: dias(hoje, [[12, 3], [0, 1], [0, 0], [0, 0], [3, 2], [1, 0]]),
    respostas: {
      de: '2026-09-09',
      ate: hoje,
      enviadas: 36,
      respondidas: 17,
      taxa: 47,
      horas_ate_metade: 30,
      canais: [{ canal: 'email', enviadas: 36, respondidas: 17, taxa: 47 }],
      anterior: { de: '2026-08-10', ate: '2026-09-08', enviadas: 30, respondidas: 12, taxa: 40, horas_ate_metade: 50, canais: [] },
    },
    ...extra,
  }
}
const auto = (extra: Partial<PanoramaEnvios['automatico']> = {}) => ({ ...panorama().automatico, ...extra })
const HOJE = '2026-10-08'
const AGORA = new Date('2026-10-08T01:30:00-03:00').getTime()

describe('Envios › panorama: regras', () => {
  it('horas e dias em palavras', () => {
    expect([hora('08:00'), hora('14:30'), hora('18:00')]).toEqual(['8h', '14h30', '18h'])
    expect([quandoDia('2026-10-08', HOJE), quandoDia('2026-10-09', HOJE), quandoDia('2026-10-10', HOJE), quandoDia('2026-10-12', HOJE), quandoDia('2026-10-20', HOJE)]).toEqual([
      'hoje',
      'amanhã',
      'no sábado',
      'na segunda-feira',
      'em 20/10',
    ])
    expect(quandoRodada('2026-10-09T08:00:00-03:00', HOJE)).toBe('amanhã às 8h')
  })

  it('a frase de cada estado do envio', () => {
    expect(manchete(auto(), HOJE, AGORA)).toEqual({ estado: 'Envio automático ligado', tom: 'sucesso', titulo: 'Próxima rodada hoje às 14h, para 12 contatos', texto: null })
    // a hora prevista já passou: sai na próxima passada das tarefas
    expect(manchete(auto(), HOJE, new Date('2026-10-08T14:10:00-03:00').getTime()).titulo).toBe('Próxima rodada nos próximos 30 minutos, para 12 contatos')
    // fila maior que uma rodada e gente de fora
    expect(manchete(auto({ na_fila: 130, fora_da_rodada: 3 }), HOJE, AGORA)).toMatchObject({
      titulo: 'Próxima rodada hoje às 14h, para 100 contatos',
      texto: 'Cada rodada leva até 100; os outros 30 vão nas seguintes. 3 contatos da fila ficam de fora: sem e-mail, em descanso ou com envios que falharam.',
    })
    expect(manchete(auto({ na_fila: 1, fora_da_rodada: 1, canal: 'whatsapp_e_email' }), HOJE, AGORA).texto).toBe(
      '1 contato da fila fica de fora: sem e-mail nem telefone, em descanso ou com envios que falharam.',
    )
    expect(manchete(auto({ na_fila: 0, proximo_contato: '2026-11-23' }), HOJE, AGORA)).toMatchObject({ titulo: 'Ninguém na fila agora', texto: 'O próximo contato entra na fila em 23/11.' })
    expect(manchete(auto({ na_fila: 0 }), HOJE, AGORA).texto).toBe('Todos já receberam a pesquisa dentro do intervalo.')
    expect(manchete(auto({ na_fila: 0, fora_da_rodada: 2 }), HOJE, AGORA)).toMatchObject({
      titulo: 'Ninguém na fila pode receber agora',
      texto: '2 contatos estão na fila, mas sem e-mail, em descanso ou com envios que falharam.',
    })
    expect(manchete(auto({ estado: 'manual', proxima_rodada: null }), HOJE, AGORA)).toEqual({
      estado: 'Envio automático desligado',
      tom: 'neutro',
      titulo: 'As pesquisas só saem quando alguém envia por aqui',
      texto: 'Os lembretes de quem não respondeu continuam saindo sozinhos.',
    })
    expect(manchete(auto({ estado: 'manual', lembretes: 0 }), HOJE, AGORA).texto).toBeNull()
    expect(manchete(auto({ estado: 'parado' }), HOJE, AGORA)).toMatchObject({ estado: 'Envios parados', tom: 'atencao' })
    expect(manchete(auto({ estado: 'desligado' }), HOJE, AGORA)).toMatchObject({ estado: 'Envios desligados', titulo: 'Nenhuma pesquisa ou lembrete sai agora' })
  })

  it('as regras em uma linha', () => {
    expect(regras(auto())).toBe('Em dias úteis, das 8h às 18h, por e-mail, a cada 90 dias por contato.')
    expect(regras(auto({ so_dias_uteis: false, janela_inicio: '09:30', canal: 'whatsapp_e_email', intervalo_dias: 60 }))).toBe(
      'Todos os dias, das 9h30 às 18h, pelo WhatsApp e por e-mail, a cada 60 dias por contato.',
    )
  })

  it('agenda: rótulos, alturas pelo dia com mais envios, total e a dica de cada dia', () => {
    const d = agenda(panorama(), HOJE)
    expect(d).toHaveLength(14)
    expect(d.slice(0, 5).map((x) => [x.rotulo, x.numero, x.alturaPesquisas, x.alturaLembretes, x.sai, x.hoje])).toEqual([
      ['Hoje', '8', 80, 20, true, true],
      ['sex', '9', 0, 7, true, false],
      ['sáb', '10', 0, 0, false, false],
      ['dom', '11', 0, 0, false, false],
      ['seg', '12', 20, 13, true, false],
    ])
    expect(totalAgenda(panorama())).toBe('16 pesquisas e 6 lembretes nos próximos 14 dias')
    expect(totalAgenda(panorama({ agenda: dias(HOJE) }))).toBe('Nada previsto nos próximos 14 dias')
    expect(totalAgenda(panorama({ agenda: dias(HOJE, [[0, 1]]) }))).toBe('1 lembrete nos próximos 14 dias')
    expect(detalheDia(d[0]!, true)).toBe('hoje, quinta-feira, 8 de outubro: 12 pesquisas e 3 lembretes')
    expect(detalheDia(d[2]!, true)).toBe('sábado, 10 de outubro: sem envio (só dias úteis)')
    expect(detalheDia(d[5]!, true)).toBe('terça-feira, 13 de outubro: 1 pesquisa')
    expect(detalheDia(d[6]!, true)).toBe('quarta-feira, 14 de outubro: nada previsto')
    expect(detalheDia({ ...d[0]!, sai: false }, true)).toBe('hoje, quinta-feira, 8 de outubro: sem envio (a janela de hoje já fechou)')
  })

  it('respostas: a frase, a comparação em pontos e o tempo até a metade', () => {
    const r = panorama().respostas
    expect(respondidas(r)).toBe('17 de 36 pesquisas enviadas nos últimos 30 dias foram respondidas')
    expect(respondidas({ ...r, enviadas: 1, respondidas: 1 })).toBe('1 de 1 pesquisa enviada nos últimos 30 dias foi respondida')
    expect(respondidas({ ...r, enviadas: 0, respondidas: 0 })).toBeNull()
    expect(variacaoTaxa(r)).toEqual({ texto: '7 pontos acima dos 30 dias anteriores', sentido: 'subiu' })
    expect(variacaoTaxa({ ...r, taxa: 39 })).toEqual({ texto: '1 ponto abaixo dos 30 dias anteriores', sentido: 'caiu' })
    expect(variacaoTaxa({ ...r, taxa: 40 })).toEqual({ texto: 'Igual aos 30 dias anteriores', sentido: 'igual' })
    expect(variacaoTaxa({ ...r, anterior: { ...r.anterior, taxa: null } })).toBeNull()
    expect([tempoAteMetade(0.4), tempoAteMetade(6), tempoAteMetade(30), tempoAteMetade(50), tempoAteMetade(null)]).toEqual([
      'Metade respondeu em menos de 1 hora',
      'Metade respondeu em até 6 horas',
      'Metade respondeu em até 30 horas',
      'Metade respondeu em até 2 dias',
      null,
    ])
  })
})

// ── Componente ──────────────────────────────────────────────────────────────

async function montar(resposta: () => unknown) {
  const { chamadas } = apiFalsa({ 'GET /envios/panorama': resposta })
  const router = createRouter({ history: createMemoryHistory(), routes: [{ path: '/:qualquer(.*)*', component: { render: () => null } }] })
  await router.push('/envios')
  await router.isReady()
  const w = mount(PanoramaView, { global: { plugins: [router] }, attachTo: document.body })
  await flushPromises()
  return { w, chamadas }
}

enableAutoUnmount(afterEach)
beforeEach(() => setActivePinia(createPinia()))
afterEach(() => {
  document.body.innerHTML = ''
})

describe('Envios › panorama: componente', () => {
  it('mostra o estado, a próxima rodada, as regras, a agenda (com a tabela para leitores de tela) e a taxa de resposta', async () => {
    const hoje = hojeIso()
    const { w } = await montar(() => panorama({ automatico: auto({ proxima_rodada: '2099-01-01T08:00:00-03:00' }), agenda: dias(hoje, [[12, 3], [0, 1]]) }, hoje))
    expect(t(w.get('[data-estado-envio]').text())).toBe('Envio automático ligado')
    expect(w.get('[data-estado-envio]').classes()).toContain('text-sucesso')
    expect(t(w.get('[data-manchete]').text())).toBe('Próxima rodada em 01/01 às 8h, para 12 contatos')
    expect(textos(w.get('[data-regras]'))).toBe('Em dias úteis, das 8h às 18h, por e-mail, a cada 90 dias por contato. Mudar as regras')
    expect(w.get('[data-regras] a').attributes('href')).toBe('/configuracoes/envios')
    expect(t(w.get('[data-total-agenda]').text())).toBe('12 pesquisas e 4 lembretes nos próximos 14 dias')
    expect(w.findAll('[data-dia]')).toHaveLength(14)
    const primeiro = w.get(`[data-dia="${hoje}"]`)
    expect(primeiro.get('[data-barra-pesquisas]').attributes('style')).toContain('height: 80%')
    expect(primeiro.get('[data-barra-lembretes]').attributes('style')).toContain('height: 20%')
    expect(primeiro.attributes('title')).toMatch(/^hoje, .*: 12 pesquisas e 3 lembretes$/)
    expect(w.findAll('[data-agenda] table tbody tr')).toHaveLength(14)
    expect(textos(w.get('[data-legenda-agenda]'))).toBe('Pesquisas Lembretes')
    expect(t(w.get('[data-taxa]').text())).toBe('47%')
    expect(t(w.get('[data-respondidas]').text())).toBe('17 de 36 pesquisas enviadas nos últimos 30 dias foram respondidas')
    expect(t(w.get('[data-variacao-taxa]').text())).toBe('7 pontos acima dos 30 dias anteriores')
    expect(t(w.get('[data-tempo-resposta]').text())).toBe('Metade respondeu em até 30 horas')
    // um canal só: sem a divisão por canal
    expect(w.find('[data-canais]').exists()).toBe(false)
  })

  it('dois canais: a taxa de cada um; sem pesquisas enviadas, o traço e a frase', async () => {
    const base = panorama()
    const { w } = await montar(() => ({
      ...base,
      respostas: {
        ...base.respostas,
        canais: [
          { canal: 'email', enviadas: 30, respondidas: 12, taxa: 40 },
          { canal: 'whatsapp', enviadas: 6, respondidas: 5, taxa: 83 },
        ],
      },
    }))
    expect(w.findAll('[data-canais] li').map((li) => textos(li))).toEqual(['E-mail 40% de 30 enviadas', 'WhatsApp 83% de 6 enviadas'])
    w.unmount()
    const vazio = await montar(() => ({ ...base, respostas: { ...base.respostas, enviadas: 0, respondidas: 0, taxa: null, horas_ate_metade: null, canais: [] } }))
    expect(t(vazio.w.get('[data-taxa]').text())).toBe('—')
    expect(t(vazio.w.get('[data-respondidas]').text())).toBe('Nenhuma pesquisa saiu nos últimos 30 dias.')
    expect(vazio.w.find('[data-variacao-taxa]').exists()).toBe(false)
  })

  it('erro: o aviso com "Tentar de novo"; recarregar() atualiza sem piscar', async () => {
    let vez = 0
    const { w, chamadas } = await montar(() => {
      vez += 1
      if (vez === 1) return new Response(JSON.stringify({ erro: { codigo: 'erro', mensagem: 'Fora do ar.' } }), { status: 503 })
      return vez === 2 ? panorama() : panorama({ automatico: auto({ estado: 'manual' }) })
    })
    expect(t(w.text())).toContain('Não deu para carregar o resumo dos envios')
    await w.findAll('button').find((b) => t(b.text()) === 'Tentar de novo')!.trigger('click')
    await flushPromises()
    expect(w.find('[data-manchete]').exists()).toBe(true)
    await (w.vm as unknown as { recarregar: () => Promise<void> }).recarregar()
    await flushPromises()
    expect(chamadas.filter((c) => c.caminho === '/envios/panorama')).toHaveLength(3)
    expect(t(w.get('[data-estado-envio]').text())).toBe('Envio automático desligado')
  })
})

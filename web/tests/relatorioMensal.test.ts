// Relatório mensal em PDF: a lista de meses (atual "até hoje" e os 12 anteriores, virando o ano), a janela em
// Relatórios (padrão = mês anterior, baixa com ?mes=AAAA-MM) e a preferência em Minha conta.
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { enableAutoUnmount, flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createMemoryHistory, createRouter } from 'vue-router'
import { defineComponent, h } from 'vue'
import { avisos } from '@/composables/avisos'
import { useSessaoStore } from '@/stores/sessao'
import RelatorioMensal from '@/modulos/relatorios/RelatorioMensal.vue'
import SecaoEmails from '@/modulos/conta/SecaoEmails.vue'
import { mesesDoRelatorio } from '@/modulos/relatorios/logica'
import { apiFalsa } from './apiFalsa'

enableAutoUnmount(afterEach)
beforeEach(() => {
  setActivePinia(createPinia())
  avisos.splice(0)
  URL.createObjectURL = vi.fn(() => 'blob:x')
  URL.revokeObjectURL = vi.fn()
})
afterEach(() => {
  vi.unstubAllGlobals()
  document.body.innerHTML = ''
})

const Vazio = defineComponent({ render: () => h('div') })
function roteador() {
  return createRouter({ history: createMemoryHistory(), routes: [{ path: '/:p(.*)*', component: Vazio }] })
}

describe('mesesDoRelatorio', () => {
  it('o mês atual (até hoje) e os 12 anteriores, virando o ano', () => {
    const m = mesesDoRelatorio('2026-02-10')
    expect(m).toHaveLength(13)
    expect(m[0]).toEqual({ valor: '2026-02', rotulo: 'Fevereiro de 2026 (até hoje)' })
    expect(m[1]).toEqual({ valor: '2026-01', rotulo: 'Janeiro de 2026' })
    expect(m[2]).toEqual({ valor: '2025-12', rotulo: 'Dezembro de 2025' })
    expect(m[12]).toEqual({ valor: '2025-02', rotulo: 'Fevereiro de 2025' })
  })
})

describe('Relatórios › Relatório mensal (PDF)', () => {
  it('abre com o mês anterior e baixa o PDF do mês escolhido', async () => {
    const { chamadas } = apiFalsa({
      'GET /relatorios/mensal.pdf': () => new Response('%PDF-1.4', {
        status: 200, headers: { 'Content-Type': 'application/pdf', 'Content-Disposition': 'attachment; filename="toqqi-relatorio-2026-09.pdf"' },
      }),
    })
    const w = mount(RelatorioMensal, { props: { hoje: '2026-11-10' }, attachTo: document.body, global: { plugins: [roteador()] } })
    await w.get('[data-relatorio-mensal]').trigger('click')
    const select = document.querySelector<HTMLSelectElement>('[data-mes-relatorio] select, select[data-mes-relatorio]')!
    expect(select.value).toBe('2026-10')
    select.value = '2026-09'
    select.dispatchEvent(new Event('change'))
    await flushPromises()
    document.querySelector<HTMLButtonElement>('[data-baixar-mensal]')!.click()
    await vi.waitFor(() => expect(URL.createObjectURL).toHaveBeenCalledTimes(1))
    await flushPromises()
    expect(chamadas.map((c) => [c.caminho, c.url.searchParams.get('mes')])).toEqual([['/relatorios/mensal.pdf', '2026-09']])
    expect(document.querySelector('[data-baixar-mensal]')).toBeNull() // a janela fecha
  })

  it('erro ao baixar: avisa e a janela continua aberta', async () => {
    apiFalsa({
      'GET /relatorios/mensal.pdf': () => new Response(JSON.stringify({ erro: { codigo: 'x', mensagem: 'Falhou.' } }), { status: 500 }),
    })
    const w = mount(RelatorioMensal, { props: { hoje: '2026-11-10' }, attachTo: document.body, global: { plugins: [roteador()] } })
    await w.get('[data-relatorio-mensal]').trigger('click')
    document.querySelector<HTMLButtonElement>('[data-baixar-mensal]')!.click()
    await flushPromises()
    expect(avisos.at(-1)?.tipo).toBe('erro')
    expect(document.querySelector('[data-baixar-mensal]')).not.toBeNull()
  })
})

describe('Minha conta › E-mails do Toqqi', () => {
  it('liga e desliga o relatório mensal', async () => {
    const { chamadas } = apiFalsa({ 'PATCH /eu': (c) => ({ ...(c.corpo as object) }) })
    const sessao = useSessaoStore()
    sessao.atualizarUsuario({ id: 1, nome: 'Ana', email: 'ana@x.com', recebe_relatorio_mensal: true } as never)
    const w = mount(SecaoEmails, { attachTo: document.body })
    const chave = w.find('[data-pref-relatorio-mensal] [role="switch"]').exists()
      ? w.get('[data-pref-relatorio-mensal] [role="switch"]') : w.get('[data-pref-relatorio-mensal]')
    expect(chave.attributes('aria-checked')).toBe('true')
    await chave.trigger('click')
    await flushPromises()
    expect(chamadas.map((c) => c.corpo)).toEqual([{ recebe_relatorio_mensal: false }])
    expect(avisos.at(-1)?.mensagem).toBe('Você não vai mais receber o relatório mensal.')
  })
})

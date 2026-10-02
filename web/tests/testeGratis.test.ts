import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createMemoryHistory, createRouter } from 'vue-router'
import { h } from 'vue'
import type { Conta } from '@/api/tipos'
import { useSessaoStore } from '@/stores/sessao'
import { cartaoDoTeste, diasDeTeste, seloDoTeste } from '@/modulos/assinatura/logica'
import CartaoTeste from '@/modulos/inicio/CartaoTeste.vue'

// 02/10/2026 às 10h em São Paulo; o teste vai até o fim de 16/10 (teste_ate = 17/10 00:00 em São Paulo).
const AGORA = new Date('2026-10-02T13:00:00Z')
const ATE = '2026-10-17T03:00:00Z'

function conta(extra: Partial<Conta> = {}): Conta {
  return { id: 1, nome: 'Conta', plano: 'profissional', situacao: 'teste', teste_ate: ATE, cobranca: { liberada: true, assinada: false, pago_ate: null, atrasada_desde: null, pausa_em: null, aviso: null }, ...extra }
}

describe('selo do teste no topo', () => {
  it('conta os dias pelo último dia do teste em São Paulo', () => {
    expect(diasDeTeste('2026-10-16', AGORA)).toBe(14)
    expect(diasDeTeste('2026-10-02', AGORA)).toBe(0)
  })

  it('administrador antes de assinar: link para a Assinatura com "Escolher plano"', () => {
    expect(seloDoTeste(conta(), true, AGORA)).toEqual({
      texto: 'Teste grátis: faltam 14 dias',
      curto: 'Teste: 14 dias',
      titulo: 'Teste grátis até 16/10/2026',
      link: true,
      convite: 'Escolher plano',
    })
  })

  it('depois de assinar no teste: continua link, sem o convite', () => {
    const s = seloDoTeste(conta({ cobranca: { liberada: true, assinada: true, pago_ate: null, atrasada_desde: null, pausa_em: null, aviso: null } }), true, AGORA)
    expect(s).toMatchObject({ link: true, convite: null, texto: 'Teste grátis: faltam 14 dias' })
  })

  it('quem não cuida da assinatura só lê', () => {
    expect(seloDoTeste(conta(), false, AGORA)).toMatchObject({ link: false, convite: null })
  })

  it('último dia, um dia, encerrado e conta fora do teste', () => {
    expect(seloDoTeste(conta(), true, new Date('2026-10-16T13:00:00Z'))).toMatchObject({ texto: 'Teste grátis: termina hoje', curto: 'Teste: hoje' })
    expect(seloDoTeste(conta(), true, new Date('2026-10-15T13:00:00Z'))).toMatchObject({ texto: 'Teste grátis: falta 1 dia', curto: 'Teste: 1 dia' })
    expect(seloDoTeste(conta(), true, new Date('2026-10-17T13:00:00Z'))).toMatchObject({ texto: 'Teste grátis encerrado em 16/10/2026', link: true, convite: 'Escolher plano' })
    expect(seloDoTeste(conta({ situacao: 'ativa' }), true, AGORA)).toBeNull()
  })
})

describe('cartão do teste no Início', () => {
  it('aparece para quem cuida da assinatura, antes de assinar, com mais de 5 dias', () => {
    expect(cartaoDoTeste(conta(), true, AGORA)).toEqual({ data: '16/10/2026', dias: 14, plano: 'Profissional' })
    expect(cartaoDoTeste(conta(), true, new Date('2026-10-10T13:00:00Z'))).toMatchObject({ dias: 6 })
  })

  it('sai nos últimos 5 dias (a faixa do topo avisa), depois de assinar, para os outros perfis e fora do teste', () => {
    expect(cartaoDoTeste(conta(), true, new Date('2026-10-11T13:00:00Z'))).toBeNull()
    expect(cartaoDoTeste(conta({ cobranca: { liberada: true, assinada: true, pago_ate: null, atrasada_desde: null, pausa_em: null, aviso: null } }), true, AGORA)).toBeNull()
    expect(cartaoDoTeste(conta(), false, AGORA)).toBeNull()
    expect(cartaoDoTeste(conta({ situacao: 'ativa' }), true, AGORA)).toBeNull()
  })
})

describe('CartaoTeste', () => {
  beforeEach(() => {
    vi.useFakeTimers({ toFake: ['Date'] })
    vi.setSystemTime(AGORA)
    setActivePinia(createPinia())
  })
  afterEach(() => vi.useRealTimers())

  async function montar(permissoes: string[], c: Conta) {
    useSessaoStore().definirSessao(
      {
        token: 't',
        expira_em: '2099-01-01T00:00:00Z',
        usuario: { id: 1, nome: 'Ana', email: 'a@x.com', cargo: null, perfil: 'admin', situacao: 'ativo', email_confirmado: true, ultimo_acesso: null, superadmin: false },
        conta: c,
        permissoes: permissoes as never,
      },
      false,
    )
    const router = createRouter({ history: createMemoryHistory(), routes: [{ path: '/:qualquer(.*)*', component: { render: () => h('div') } }] })
    await router.push('/inicio')
    await router.isReady()
    const w = mount(CartaoTeste, { global: { plugins: [router] } })
    await flushPromises()
    return w
  }

  it('mostra os dias, o plano e leva aos planos', async () => {
    const w = await montar(['assinatura.gerenciar'], conta())
    expect(w.text()).toContain('Seu teste grátis vai até 16/10/2026 (faltam 14 dias)')
    expect(w.text()).toContain('plano Profissional')
    expect(w.get('a').attributes('href')).toBe('/assinatura')
  })

  it('não aparece para quem não cuida da assinatura', async () => {
    const w = await montar(['painel.ver'], conta())
    expect(w.find('[data-cartao-teste]').exists()).toBe(false)
  })
})

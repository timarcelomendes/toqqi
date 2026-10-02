// Etapa 5a: na lista de pré-condições de Envios, o atalho para a Assinatura só aparece para quem pode gerenciá-la
// (os outros leem que precisam do administrador) e, com a conta pausada, o texto não oferece o WhatsApp.
import { beforeEach, describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createMemoryHistory, createRouter } from 'vue-router'
import type { PreCondicoes } from '@/api'
import AvisoPreCondicoes from '@/modulos/envios/AvisoPreCondicoes.vue'
import { useSessaoStore } from '@/stores/sessao'

const DADOS: PreCondicoes = {
  pronto: false,
  itens: [
    { chave: 'assinatura', ok: false, mensagem: 'O período de teste acabou. Assine um plano para voltar a enviar.', acao: { rotulo: 'Assinatura', rota: '/assinatura' } },
    { chave: 'provedor', ok: true, mensagem: null, acao: null },
  ],
} as never

function montar(permissoes: string[], liberada: boolean) {
  setActivePinia(createPinia())
  const sessao = useSessaoStore()
  sessao.permissoes = permissoes
  sessao.conta = { id: 1, nome: 'Sol', plano: 'profissional', situacao: liberada ? 'teste' : 'teste_expirado', teste_ate: null,
    cobranca: { liberada, pago_ate: null, atrasada_desde: null, pausa_em: null, aviso: null } } as never
  const router = createRouter({ history: createMemoryHistory(), routes: [{ path: '/:p(.*)*', component: { template: '<div />' } }] })
  return mount(AvisoPreCondicoes, { props: { dados: DADOS }, global: { plugins: [router] } })
}

describe('pré-condições de Envios e a assinatura', () => {
  beforeEach(() => setActivePinia(createPinia()))

  it('quem gerencia a assinatura vê o atalho; com a conta pausada, o texto não oferece o WhatsApp', () => {
    const w = montar(['envios.ver', 'assinatura.gerenciar'], false)
    expect(w.find('a[href="/assinatura"]').exists()).toBe(true)
    expect(w.find('[data-fale-com-admin]').exists()).toBe(false)
    expect(w.text()).toContain('Os envios estão pausados')
    expect(w.text()).not.toContain('você já pode mandar pelo WhatsApp')
  })

  it('quem não gerencia lê "Fale com o administrador da conta." no lugar do atalho', () => {
    const w = montar(['envios.ver'], false)
    expect(w.find('a[href="/assinatura"]').exists()).toBe(false)
    expect(w.get('[data-fale-com-admin]').text()).toBe('Fale com o administrador da conta.')
  })

  it('com a assinatura em dia (falta só o e-mail), segue oferecendo o WhatsApp', () => {
    const w = montar(['envios.ver'], true)
    expect(w.text()).toContain('você já pode mandar pelo WhatsApp')
    expect(w.text()).toContain('Falta pouco para as pesquisas por e-mail começarem a sair')
  })
})

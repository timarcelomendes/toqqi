// Melhoria 5, prova social: a leitura do bloco `depoimento` da tela final, o cartão na pesquisa (autorizar e o link de
// avaliação), o texto para copiar e a configuração (link só https).
import { describe, expect, it } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import CartaoDepoimento from '@/pesquisa/CartaoDepoimento.vue'
import { lerDepoimento } from '@/pesquisa/indicacao'
import { textoDepoimento } from '@/modulos/crescimento/logica'
import { normalizarConfigCrescimento, PADRAO_CRESCIMENTO, validarConfigCrescimento } from '@/modulos/configuracoes/configCrescimento'

const GOOGLE = 'https://g.page/r/alfa/review'

describe('depoimentos', () => {
  it('lê o bloco da API com segurança', () => {
    expect(lerDepoimento(null)).toBeNull()
    expect(lerDepoimento({ pedir: false, avaliar_url: null })).toBeNull()
    expect(lerDepoimento({ pedir: false, avaliar_url: 'javascript:alert(1)' })).toBeNull()
    expect(lerDepoimento({ pedir: true, avaliar_url: GOOGLE, avaliar_rotulo: 'Avaliar a Alfa' })).toEqual({ pedir: true, avaliar_url: GOOGLE, avaliar_rotulo: 'Avaliar a Alfa' })
  })

  it('cartão: autoriza uma vez e mostra o link de avaliação', async () => {
    let chamadas = 0
    const w = mount(CartaoDepoimento, {
      props: { dados: { pedir: true, avaliar_url: GOOGLE, avaliar_rotulo: 'Avaliar a Alfa' }, autorizar: async () => { chamadas++; return 'Obrigado!' } },
    })
    expect(w.get('[data-avaliar]').attributes('href')).toBe(GOOGLE)
    await w.get('[data-autorizar-depoimento]').trigger('click')
    await flushPromises()
    expect(chamadas).toBe(1)
    expect(w.get('[data-depoimento-final]').text()).toBe('Obrigado!')
    expect(w.find('[data-autorizar-depoimento]').exists()).toBe(false)
  })

  it('texto para copiar e configuração', () => {
    expect(textoDepoimento({ comentario: ' Ótimo atendimento ', assinatura: 'Ana, Mercado Azul' })).toBe('“Ótimo atendimento” — Ana, Mercado Azul')
    expect(normalizarConfigCrescimento({ ...PADRAO_CRESCIMENTO, link_avaliacao: '  ' }).link_avaliacao).toBeNull()
    expect(validarConfigCrescimento({ ...PADRAO_CRESCIMENTO, link_avaliacao: 'http://x.com' }).link_avaliacao).toBeTruthy()
    expect(validarConfigCrescimento({ ...PADRAO_CRESCIMENTO, link_avaliacao: GOOGLE }).link_avaliacao).toBeUndefined()
  })
})

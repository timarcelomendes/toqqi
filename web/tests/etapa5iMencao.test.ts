// Etapa 5i, §4: "Pesquisa feita com Toqqi" na página da pesquisa (fora do cartão, sem Referer) e a origem do cadastro
// (utm do primeiro link da visita, com a mesma limpeza da API).
import { afterEach, beforeEach, describe, expect, it } from 'vitest'
import { enableAutoUnmount, mount } from '@vue/test-utils'
import Pesquisa from '@/pesquisa/Pesquisa.vue'
import { TEMA_PADRAO, type FormularioPublico } from '@/pesquisa/tipos'
import { apagarOrigem, guardarOrigem, limparOrigem, origemParaCadastro } from '@/site/origem'

enableAutoUnmount(afterEach)

const URL = 'https://app.toqqi.com/?utm_source=pesquisa&utm_medium=rodape&utm_campaign=pagina'
const formulario = (mencao?: FormularioPublico['mencao_toqqi']): FormularioPublico => ({
  nome: 'NPS',
  perguntas: [{ id: 'nota', tipo: 'nps', titulo: 'Recomendaria?', obrigatoria: true }],
  tema: { ...TEMA_PADRAO },
  ...(mencao !== undefined ? { mencao_toqqi: mencao } : {}),
})

describe('Pesquisa feita com Toqqi', () => {
  it('aparece fora do cartão, abre em outra aba e não manda o endereço da pesquisa', () => {
    const w = mount(Pesquisa, { props: { formulario: formulario({ texto: 'Pesquisa feita com Toqqi', url: URL }) } })
    const a = w.get('[data-mencao-toqqi] a')
    expect(a.text()).toBe('Pesquisa feita com Toqqi')
    expect(a.attributes('href')).toBe(URL)
    expect(a.attributes('target')).toBe('_blank')
    expect(a.attributes('rel')).toBe('noopener noreferrer')
    expect(a.attributes('referrerpolicy')).toBe('no-referrer')
    expect(w.get('form').element.contains(a.element)).toBe(false)
  })

  it('some quando a conta tirou (null) e na prévia do editor (sem o campo)', () => {
    expect(mount(Pesquisa, { props: { formulario: formulario(null) } }).find('[data-mencao-toqqi]').exists()).toBe(false)
    expect(mount(Pesquisa, { props: { formulario: formulario() } }).find('[data-mencao-toqqi]').exists()).toBe(false)
  })
})

describe('origem do cadastro', () => {
  beforeEach(() => sessionStorage.clear())

  it('limpa como a API', () => {
    expect(limparOrigem({ utm_source: ' Pesquisa ', utm_medium: 'rodape', outra: 'x' })).toEqual({ utm_source: 'pesquisa', utm_medium: 'rodape' })
    expect(limparOrigem({ utm_campaign: 'black friday+2026' })).toEqual({ utm_campaign: 'black-friday-2026' })
    expect(limparOrigem({ utm_source: 'ana@x.com.br' })).toBeNull()
    expect(limparOrigem({ utm_source: 'tel11987654321' })).toBeNull()
    expect(limparOrigem({ utm_source: 'x'.repeat(61) })).toBeNull()
    expect(limparOrigem('pesquisa')).toBeNull()
  })

  it('vale o primeiro link da visita; o cadastro usa a guardada ou a do próprio endereço', () => {
    guardarOrigem('?utm_source=pesquisa&utm_medium=rodape&utm_campaign=email')
    guardarOrigem('?utm_source=google')
    expect(origemParaCadastro('')).toEqual({ utm_source: 'pesquisa', utm_medium: 'rodape', utm_campaign: 'email' })
    apagarOrigem()
    expect(origemParaCadastro('?utm_source=linkedin')).toEqual({ utm_source: 'linkedin' })
    expect(origemParaCadastro('')).toBeNull()
  })
})

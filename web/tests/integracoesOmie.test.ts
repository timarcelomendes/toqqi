// Integrações › Omie: o passo a passo das chaves e do webhook segue o caminho de hoje no Omie (conferido na Central de
// Ajuda do Omie em 13/10/2026). Pedido do Marcelo: "não encontrei essa opção" (o texto antigo mandava a
// Configurações › Integrações, que o Omie não tem).
import { afterEach, beforeEach, describe, expect, it } from 'vitest'
import { enableAutoUnmount, flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import SecaoOmie from '@/modulos/integracoes/SecaoOmie.vue'
import { apiFalsa } from './apiFalsa'

const desconectado = { conectado: false }
const conectado = {
  conectado: true,
  pesquisar_ao_faturar: true,
  url_aviso: 'https://api.toqqi.com/api/v1/publico/omie/segredo',
  eventos: ['VendaProduto.Faturada', 'NFe.NotaAutorizada'],
  sincronizado_em: null,
  resumo: null,
  erro: null,
}
const texto = (el: Element | null | undefined) => (el?.textContent ?? '').replace(/\s+/g, ' ').trim()

enableAutoUnmount(afterEach)
beforeEach(() => setActivePinia(createPinia()))

async function abrir(omie: object) {
  apiFalsa({ 'GET /integracoes/conectores': () => ({ omie, rdstation_crm: { conectado: false }, bling: { conectado: false } }) })
  const w = mount(SecaoOmie, { attachTo: document.body })
  await flushPromises()
  return w
}

describe('Integrações › Omie', () => {
  it('as chaves: Área do Desenvolvedor › Aplicativos, com usuário administrador, sem criar aplicativo', async () => {
    const w = await abrir(desconectado)
    const passos = w.findAll('[data-passos-omie] > li').map((li) => texto(li.element))
    expect(passos).toEqual([
      'No Omie, entre com um usuário administrador e abra a Área do Desenvolvedor: o botão “Developer”, ou developer.omie.com.br com o mesmo e-mail e senha.',
      'Clique em Aplicativos e no aplicativo da sua empresa (no Omie, cada empresa já é um aplicativo: não precisa criar outro). Copie o App Key e o App Secret. Não use “Gerar nova chave de acesso”: as integrações que já usam a chave de agora param.',
      'Cole aqui e conecte. As chaves ficam guardadas cifradas.',
    ])
    const link = w.get<HTMLAnchorElement>('[data-passos-omie] a')
    expect([link.attributes('href'), link.attributes('target'), link.attributes('rel')]).toEqual([
      'https://developer.omie.com.br',
      '_blank',
      'noopener noreferrer',
    ])
    expect(w.text()).not.toContain('Configurações › Integrações')
  })

  it('o webhook: Aplicativos › o aplicativo › “Adicionar novo webhook”, os eventos e “Salvar”', async () => {
    const w = await abrir(conectado)
    expect(texto(w.get('[data-url-aviso-omie]').findAll('p')[1]!.element)).toBe(
      'Na Área do Desenvolvedor do Omie (developer.omie.com.br), em Aplicativos, clique no aplicativo da sua empresa e em “Adicionar novo webhook”. Cole o endereço, ligue os eventos VendaProduto.Faturada, NFe.NotaAutorizada e clique em “Salvar”.',
    )
  })
})

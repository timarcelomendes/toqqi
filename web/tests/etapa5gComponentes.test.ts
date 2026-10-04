// Etapa 5g com a API simulada (docs/api-etapa-5g.md §8, site): Plataforma › Parâmetros (quatro seções com valores,
// padrões e "Alterado em", salvar só com mudança, "Usar o padrão", validação, prévia e diálogo com os números, cancelar
// não salva, 409 com "Recarregar", 422, 503 e "Testando o modelo…", histórico com filtro e páginas, abas, só
// superadmin), os dias do teste em Contas, Nova conta e Cadastro, o valor contratado ao trocar de plano e o 409
// `preco_mudou` ao assinar e ao trocar.
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { enableAutoUnmount, flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createMemoryHistory, createRouter, RouterView, type Router } from 'vue-router'
import { defineComponent, h, type Component } from 'vue'
import type { ContaPlataforma, EstadoAssinatura, GrupoParametrosPlataforma, ItemHistoricoParametros, PlanoAssinatura, ValorParametro } from '@/api/tipos'
import { avisos } from '@/composables/avisos'
import { estadoConfirmacao, responderConfirmacao } from '@/composables/confirmacao'
import { useSessaoStore } from '@/stores/sessao'
import { router as rotasDoApp } from '@/router'
import CadastroView from '@/modulos/acesso/CadastroView.vue'
import AssinaturaView from '@/modulos/assinatura/AssinaturaView.vue'
import PlataformaView from '@/modulos/plataforma/PlataformaView.vue'
import { apiFalsa, type Chamada } from './apiFalsa'

const t = (s: string | null | undefined) => (s ?? '').replace(/ /g, ' ').replace(/\s+/g, ' ').trim()

const USUARIO = { id: 1, nome: 'Marcelo', email: 'marcelo@toqqi.com', cargo: null, situacao: 'ativo' as const, email_confirmado: true, ultimo_acesso: null }

function entrar(opcoes: { superadmin?: boolean; permissoes?: string[] } = {}) {
  const s = useSessaoStore()
  s.definirSessao(
    {
      token: 't',
      expira_em: '2099-01-01T00:00:00Z',
      usuario: { ...USUARIO, perfil: 'admin', superadmin: opcoes.superadmin ?? true },
      conta: { id: 1, nome: 'Toqqi', plano: 'profissional', situacao: 'cortesia', teste_ate: null, cobranca: { liberada: true, pago_ate: null, atrasada_desde: null, pausa_em: null, aviso: null } },
      permissoes: (opcoes.permissoes ?? []) as never,
    },
    false,
  )
  s.inicializada = true
  return s
}

// ── Dados ───────────────────────────────────────────────────────────────────

const PADROES: Record<string, Record<string, ValorParametro>> = {
  planos: {
    'planos.essencial.preco': '149.00',
    'planos.essencial.contatos': 300,
    'planos.profissional.preco': '349.00',
    'planos.profissional.contatos': 1500,
    'planos.empresa.preco': '799.00',
    'planos.empresa.contatos': null,
  },
  ia: {
    'ia.cota.essencial': 100,
    'ia.cota.profissional': 500,
    'ia.cota.empresa': 2000,
    'ia.cota.cortesia': 500,
    'ia.modelo.rapido': 'gpt-5-nano',
    'ia.esforco.rapido': 'minimal',
    'ia.analises.rapido': 1,
    'ia.modelo.equilibrado': 'gpt-5-mini',
    'ia.esforco.equilibrado': 'low',
    'ia.analises.equilibrado': 1,
    'ia.modelo.detalhado': 'gpt-5',
    'ia.esforco.detalhado': 'low',
    'ia.analises.detalhado': 2,
    'ia.teto.essencial': 1000,
    'ia.teto.profissional': 5000,
    'ia.teto.empresa': 20000,
    'ia.teto.cortesia': 5000,
    'ia.teto.teste': 1000,
  },
  whatsapp: {
    'whatsapp.franquia.essencial': 40,
    'whatsapp.franquia.profissional': 90,
    'whatsapp.franquia.empresa': 200,
    'whatsapp.franquia.cortesia': 200,
    'whatsapp.franquia.teste': 20,
  },
  teste: { 'teste.dias': 14, 'teste.plano': 'profissional', 'teste.exclusao_automatica': 'simular' },
}
const ROTULOS: Record<string, string> = { planos: 'Planos', ia: 'IA', whatsapp: 'WhatsApp automático', teste: 'Teste e cortesia' }

function grupo(nome: string, valores: Record<string, ValorParametro> = {}, extra: Partial<GrupoParametrosPlataforma> = {}): GrupoParametrosPlataforma {
  const padroes = PADROES[nome]!
  const v = { ...padroes, ...valores }
  return {
    grupo: nome,
    rotulo: ROTULOS[nome]!,
    versao: 0,
    alterado_em: null,
    alterado_por: null,
    valores: v,
    padroes: { ...padroes },
    origens: Object.fromEntries(Object.keys(padroes).map((k) => [k, k in valores ? 'banco' : k === 'ia.modelo.equilibrado' ? 'ambiente' : 'codigo'])),
    ...extra,
  }
}

/** GET /plataforma/parametros: o preço do Essencial já foi mudado (R$ 159,00) por marcelo@toqqi.com. */
const PARAMETROS = () => ({
  grupos: [
    grupo('planos', { 'planos.essencial.preco': '159.00' }, { versao: 7, alterado_em: '2026-10-03T17:32:00Z', alterado_por: 'marcelo@toqqi.com' }),
    grupo('ia'),
    grupo('whatsapp'),
    grupo('teste'),
  ],
})

const HISTORICO: ItemHistoricoParametros[] = [
  { id: 7, criado_em: '2026-10-03T17:32:00Z', grupo: 'planos', por: 'marcelo@toqqi.com', mudancas: [{ chave: 'planos.essencial.preco', de: '149.00', para: '159.00' }] },
  {
    id: 3,
    criado_em: '2026-10-02T12:00:00Z',
    grupo: 'teste',
    por: 'ana@toqqi.com',
    mudancas: [
      { chave: 'teste.dias', de: 14, para: 7 },
      { chave: 'teste.exclusao_automatica', de: 'simular', para: 'ligada' },
    ],
  },
]
const paginaHistorico = (itens = HISTORICO, total = itens.length) => ({ itens, total, pagina: 1, por_pagina: 20 })

function adiada<T>() {
  let resolver!: (v: T) => void
  const promessa = new Promise<T>((r) => (resolver = r))
  return { promessa, resolver }
}

const erroApi = (status: number, codigo: string, mensagem: string, campos: Record<string, string> = {}) =>
  new Response(JSON.stringify({ erro: { codigo, mensagem, campos } }), { status })

// ── Montagem ────────────────────────────────────────────────────────────────

let router: Router
async function abrir(caminho: string, componente: Component = PlataformaView): Promise<VueWrapper> {
  router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/plataforma/:aba(contas|parametros)?', name: 'plataforma', component: PlataformaView },
      { path: '/assinatura', component: AssinaturaView },
      { path: '/cadastro', component: CadastroView },
      { path: '/:qualquer(.*)*', component: { render: () => h('div', 'outra página') } },
    ],
  })
  void componente
  await router.push(caminho)
  await router.isReady()
  const w = mount(defineComponent({ render: () => h(RouterView) }), { global: { plugins: [router] }, attachTo: document.body })
  await flushPromises()
  return w
}

const $ = <T extends HTMLElement = HTMLElement>(sel: string) => document.body.querySelector<T>(sel)
const $$ = (sel: string) => Array.from(document.body.querySelectorAll<HTMLElement>(sel))
async function clicar(el: HTMLElement | null) {
  if (!el) throw new Error('Elemento não encontrado')
  el.click()
  await flushPromises()
}
async function digitar(el: HTMLElement | null, valor: string) {
  if (!(el instanceof HTMLInputElement)) throw new Error('Campo não encontrado')
  el.value = valor
  el.dispatchEvent(new Event('input'))
  await flushPromises()
}
async function escolher(el: HTMLElement | null, valor: string) {
  if (!(el instanceof HTMLSelectElement)) throw new Error('Lista não encontrada')
  el.value = valor
  el.dispatchEvent(new Event('change'))
  await flushPromises()
}
const cartao = (g: string) => $(`section[data-grupo="${g}"]`)!
const campo = (chave: string) => $<HTMLInputElement>(`#p-${chave.replace(/[^a-z0-9]+/gi, '-')}`)
const botaoSalvar = (g: string) => cartao(g).querySelector<HTMLButtonElement>('[data-salvar]')!
/** Salvar como a pessoa faz: o foco no botão e o envio do formulário. */
async function salvar(g: string) {
  const b = botaoSalvar(g)
  b.focus()
  b.closest('form')!.dispatchEvent(new Event('submit', { cancelable: true }))
  await flushPromises()
}
const dialogo = () => $('[role="alertdialog"]')
/** Visível como no navegador: nem o elemento nem quem o contém está com `display: none` (o v-show das abas). */
function visivel(el: HTMLElement | null): boolean {
  if (!el) throw new Error('Elemento não encontrado')
  for (let e: HTMLElement | null = el; e; e = e.parentElement) if (e.style.display === 'none') return false
  return true
}
const chamadasDe =(api: { chamadas: Chamada[] }, metodo: string, caminho: string) => api.chamadas.filter((c) => c.metodo === metodo && c.caminho === caminho)

function apiParametros(rotas: Parameters<typeof apiFalsa>[0] = {}) {
  return apiFalsa({
    'GET /plataforma/parametros': () => PARAMETROS(),
    'GET /plataforma/parametros/historico': () => paginaHistorico(),
    ...rotas,
  })
}

beforeEach(() => {
  setActivePinia(createPinia())
  avisos.splice(0)
  responderConfirmacao(false)
})
enableAutoUnmount(afterEach)

// ── Parâmetros ──────────────────────────────────────────────────────────────

describe('Plataforma › Parâmetros', () => {
  it('quatro seções com o valor em uso, o padrão e a origem, "Alterado em" e as notas', async () => {
    entrar()
    apiParametros()
    await abrir('/plataforma/parametros')
    expect($$('section[data-grupo]').map((s) => s.dataset.grupo)).toEqual(['planos', 'ia', 'whatsapp', 'teste'])
    expect($$('section[data-grupo] h2').map((e) => t(e.textContent))).toEqual(['Planos', 'IA', 'WhatsApp automático', 'Teste e cortesia'])
    expect(t(cartao('planos').querySelector('[data-alterado]')!.textContent)).toBe('Alterado em 03/10/2026 às 14:32 por marcelo@toqqi.com')
    expect(t(cartao('ia').querySelector('[data-alterado]')!.textContent)).toBe('Nunca alterado: valem os padrões.')
    // Um fieldset por plano (legenda = nome), com preço e contatos.
    expect(Array.from(cartao('planos').querySelectorAll('fieldset[data-bloco] > legend')).map((l) => t(l.textContent))).toEqual(['Essencial', 'Profissional', 'Empresa'])
    const preco = campo('planos.essencial.preco')!
    expect(preco.value).toBe('159,00')
    const dica = document.getElementById(preco.getAttribute('aria-describedby')!.split(' ').pop()!)!
    expect(t(dica.textContent)).toBe('Padrão: R$ 149,00. O valor em uso foi salvo aqui.')
    expect(t(document.getElementById(campo('planos.profissional.preco')!.getAttribute('aria-describedby')!)!.textContent)).toBe('Padrão: R$ 349,00, do código.')
    // "Usar o padrão" só onde o valor difere do padrão.
    expect($$('[data-usar-padrao]').map((b) => b.closest<HTMLElement>('[data-parametro]')!.dataset.parametro)).toEqual(['planos.essencial.preco'])
    // Empresa sem limite: a caixa marcada e o número desligado.
    const empresa = $('[data-parametro="planos.empresa.contatos"]')!
    expect(empresa.querySelector<HTMLInputElement>('input[type="checkbox"]')!.checked).toBe(true)
    expect(campo('planos.empresa.contatos')!.disabled).toBe(true)
    expect([campo('planos.empresa.contatos')!.value, campo('planos.empresa.contatos')!.placeholder]).toEqual(['', 'Sem limite'])
    expect(t(cartao('planos').querySelector('[data-nota]')!.textContent)).toBe(
      'O preço novo vale para assinaturas novas e trocas de plano. Quem já assina continua com o valor contratado.',
    )
    // IA: níveis com modelo, esforço (lista, vazio = "Sem raciocínio") e análises; a origem da variável de ambiente.
    expect(Array.from(cartao('ia').querySelectorAll('fieldset[data-bloco] fieldset > legend')).map((l) => t(l.textContent))).toEqual(['Rápido', 'Equilibrado', 'Mais detalhado'])
    const esforco = $<HTMLSelectElement>('[data-parametro="ia.esforco.rapido"] select')!
    expect(esforco.value).toBe('minimal')
    expect(Array.from(esforco.options).map((o) => o.text)).toEqual(['Sem raciocínio', 'none', 'minimal', 'low', 'medium', 'high', 'xhigh'])
    expect(t($('[data-parametro="ia.modelo.equilibrado"]')!.textContent)).toContain('Padrão: gpt-5-mini, da variável de ambiente.')
    expect(t(cartao('ia').querySelector('[data-nota]')!.textContent)).toBe('Ao salvar um modelo ou esforço novo, o Toqqi faz uma chamada curta à OpenAI para conferir.')
    // Teste e cortesia: dias, plano e os rádios da exclusão.
    expect(campo('teste.dias')!.value).toBe('14')
    expect($<HTMLInputElement>('[data-parametro="teste.exclusao_automatica"] input[value="simular"]')!.checked).toBe(true)
    expect(t($('[data-parametro="teste.exclusao_automatica"]')!.textContent)).toContain('Ligada: avisa e exclui')
    expect(t(cartao('teste').querySelector('[data-nota]')!.textContent)).toBe('Cota, teto e franquia da cortesia e do teste ficam em IA e WhatsApp automático.')
  })

  it('salvar e descartar só com mudança; descartar volta ao valor em uso', async () => {
    entrar()
    apiParametros()
    await abrir('/plataforma/parametros')
    const descartar = () => cartao('whatsapp').querySelector<HTMLButtonElement>('[data-descartar]')!
    expect(botaoSalvar('whatsapp').getAttribute('aria-disabled')).toBe('true')
    expect(descartar().disabled).toBe(true)
    await digitar(campo('whatsapp.franquia.teste'), '40')
    expect(botaoSalvar('whatsapp').getAttribute('aria-disabled')).toBeNull()
    expect(descartar().disabled).toBe(false)
    // Mesmo valor escrito de outro jeito não conta.
    await digitar(campo('whatsapp.franquia.teste'), '20')
    expect(botaoSalvar('whatsapp').getAttribute('aria-disabled')).toBe('true')
    await digitar(campo('whatsapp.franquia.teste'), '40')
    await clicar(descartar())
    expect(campo('whatsapp.franquia.teste')!.value).toBe('20')
    expect(botaoSalvar('whatsapp').getAttribute('aria-disabled')).toBe('true')
  })

  it('"Sem limite" liga e desliga o número dos contatos (e conta como mudança)', async () => {
    entrar()
    const api = apiParametros({
      'POST /plataforma/parametros/planos/previa': () => ({ mudancas: [], precisa_confirmar: false, impactos: [] }),
      'PUT /plataforma/parametros/planos': () => grupo('planos'),
    })
    await abrir('/plataforma/parametros')
    const caixa = () => $<HTMLInputElement>('[data-parametro="planos.empresa.contatos"] input[type="checkbox"]')!
    caixa().click()
    await flushPromises()
    expect(campo('planos.empresa.contatos')!.disabled).toBe(false)
    expect(botaoSalvar('planos').getAttribute('aria-disabled')).toBeNull()
    // Sem número: a validação pede um (a mensagem da API).
    await salvar('planos')
    expect(t($('[data-parametro="planos.empresa.contatos"]')!.textContent)).toContain('Use um número inteiro de 1 a 1.000.000, ou marque “Sem limite”.')
    expect(document.activeElement).toBe(campo('planos.empresa.contatos'))
    await digitar(campo('planos.empresa.contatos'), '20.000')
    await salvar('planos')
    expect((chamadasDe(api, 'POST', '/plataforma/parametros/planos/previa')[0]!.corpo as { valores: Record<string, unknown> }).valores['planos.empresa.contatos']).toBe(20000)
  })

  it('"Usar o padrão" põe o padrão no campo e leva o foco a ele', async () => {
    entrar()
    apiParametros()
    await abrir('/plataforma/parametros')
    await clicar($('[data-parametro="planos.essencial.preco"] [data-usar-padrao]'))
    expect(campo('planos.essencial.preco')!.value).toBe('149,00')
    expect($('[data-parametro="planos.essencial.preco"] [data-usar-padrao]')).toBeNull()
    expect(document.activeElement).toBe(campo('planos.essencial.preco'))
    // Mudou (o em uso é R$ 159,00): dá para salvar.
    expect(botaoSalvar('planos').getAttribute('aria-disabled')).toBeNull()
  })

  it('validação da tela: faixa e ordem dos preços, foco no primeiro erro e nada vai à API', async () => {
    entrar()
    const api = apiParametros()
    await abrir('/plataforma/parametros')
    await digitar(campo('planos.essencial.preco'), '4,99')
    await digitar(campo('planos.profissional.preco'), '100')
    await salvar('planos')
    expect(t($('[data-parametro="planos.essencial.preco"]')!.textContent)).toContain('Use um valor entre R$ 5,00 e R$ 99.999,99.')
    expect(campo('planos.essencial.preco')!.getAttribute('aria-invalid')).toBe('true')
    expect(document.activeElement).toBe(campo('planos.essencial.preco'))
    await digitar(campo('planos.essencial.preco'), '149,00')
    await salvar('planos')
    expect(t($('[data-parametro="planos.profissional.preco"]')!.textContent)).toContain('O preço do Profissional precisa ser maior que o do Essencial.')
    expect(document.activeElement).toBe(campo('planos.profissional.preco'))
    expect(api.chamadas.filter((c) => c.metodo !== 'GET')).toEqual([])
  })

  it('sem confirmação: prévia, PUT com versão e todas as chaves, "Parâmetros salvos." e cartão e histórico relidos', async () => {
    entrar()
    const salvo = grupo('whatsapp', { 'whatsapp.franquia.teste': 40 }, { versao: 8, alterado_em: '2026-10-03T18:00:00Z', alterado_por: 'marcelo@toqqi.com' })
    const api = apiParametros({
      'POST /plataforma/parametros/whatsapp/previa': () => ({ mudancas: [{ chave: 'whatsapp.franquia.teste', de: 20, para: 40 }], precisa_confirmar: false, impactos: [] }),
      'PUT /plataforma/parametros/whatsapp': () => salvo,
    })
    await abrir('/plataforma/parametros')
    await digitar(campo('whatsapp.franquia.teste'), '40')
    await salvar('whatsapp')
    const valores = { ...PADROES.whatsapp, 'whatsapp.franquia.teste': 40 }
    expect(chamadasDe(api, 'POST', '/plataforma/parametros/whatsapp/previa')[0]!.corpo).toEqual({ valores })
    expect(chamadasDe(api, 'PUT', '/plataforma/parametros/whatsapp')[0]!.corpo).toEqual({ versao: 0, valores, confirmar: false })
    expect(dialogo()).toBeNull()
    expect(t(cartao('whatsapp').querySelector('[data-status]')!.textContent)).toBe('Parâmetros salvos.')
    expect(cartao('whatsapp').querySelector('[data-status]')!.getAttribute('aria-live')).toBe('polite')
    expect(t(cartao('whatsapp').querySelector('[data-alterado]')!.textContent)).toBe('Alterado em 03/10/2026 às 15:00 por marcelo@toqqi.com')
    expect(campo('whatsapp.franquia.teste')!.value).toBe('40')
    expect(botaoSalvar('whatsapp').getAttribute('aria-disabled')).toBe('true')
    expect(document.activeElement).toBe(botaoSalvar('whatsapp'))
    expect(chamadasDe(api, 'GET', '/plataforma/parametros/historico')).toHaveLength(2)
    // Mexeu de novo: o "Parâmetros salvos." sai.
    await digitar(campo('whatsapp.franquia.teste'), '41')
    expect(t(cartao('whatsapp').querySelector('[data-status]')!.textContent)).toBe('')
  })

  it('com confirmação: diálogo com os números; cancelar não salva; "Confirmar e salvar" manda confirmar', async () => {
    entrar()
    const previa = {
      mudancas: [
        { chave: 'planos.essencial.preco', de: '159.00', para: '169.00' },
        { chave: 'planos.essencial.contatos', de: 300, para: 250 },
      ],
      precisa_confirmar: true,
      impactos: [{ chave: 'planos.essencial.contatos', contas: 12, exemplos: [{ id: 4, nome: 'Alfa', uso: 320 }, { id: 5, nome: 'Beta', uso: 300 }] }],
    }
    const api = apiParametros({
      'POST /plataforma/parametros/planos/previa': () => previa,
      'PUT /plataforma/parametros/planos': (c) => grupo('planos', (c.corpo as { valores: Record<string, ValorParametro> }).valores, { versao: 9 }),
    })
    await abrir('/plataforma/parametros')
    await digitar(campo('planos.essencial.preco'), '169')
    await digitar(campo('planos.essencial.contatos'), '250')
    await salvar('planos')
    const d = dialogo()!
    expect(d).not.toBeNull()
    expect(t(d.querySelector('h2')!.textContent)).toBe('Confirmar as mudanças em Planos?')
    expect(Array.from(d.querySelectorAll('[data-dialogo-parametros] li')).map((l) => t(l.textContent))).toEqual([
      'Preço do Essencial: R$ 159,00 → R$ 169,00. Vale para assinaturas novas e trocas de plano.',
      'Contatos do Essencial: 300 → 250. 12 contas têm mais de 250 contatos ativos (Alfa, Beta…): ficam com eles, mas não cadastram, importam nem reativam contatos.',
    ])
    expect(t(d.querySelector('[data-aviso-diminui]')!.textContent)).toBe(
      'Vale na hora para todas as contas, inclusive quem já assina. Os Termos prometem aviso com antecedência razoável.',
    )
    // Cancelar: nada salvo, o foco volta ao botão de salvar.
    await clicar(Array.from(d.querySelectorAll<HTMLButtonElement>('button')).find((b) => t(b.textContent) === 'Cancelar')!)
    expect(dialogo()).toBeNull()
    expect(chamadasDe(api, 'PUT', '/plataforma/parametros/planos')).toHaveLength(0)
    expect(document.activeElement).toBe(botaoSalvar('planos'))
    expect(campo('planos.essencial.preco')!.value).toBe('169')
    // De novo, agora confirmando.
    await salvar('planos')
    await clicar($('[data-confirmar-salvar]'))
    const put = chamadasDe(api, 'PUT', '/plataforma/parametros/planos')
    expect(put).toHaveLength(1)
    expect(put[0]!.corpo).toEqual({
      versao: 7,
      valores: { ...PADROES.planos, 'planos.essencial.preco': '169.00', 'planos.essencial.contatos': 250 },
      confirmar: true,
    })
    expect(dialogo()).toBeNull()
    expect(t(cartao('planos').querySelector('[data-status]')!.textContent)).toBe('Parâmetros salvos.')
    expect(document.activeElement).toBe(botaoSalvar('planos'))
  })

  it('Enter num campo: fechar o diálogo sem salvar (Esc, Cancelar, X ou fora) devolve o foco ao "Salvar alterações"', async () => {
    entrar()
    const previa = { mudancas: [{ chave: 'planos.essencial.preco', de: '159.00', para: '169.00' }], precisa_confirmar: true, impactos: [] }
    let pendente: { promessa: Promise<typeof previa>; resolver: (v: typeof previa) => void } | null = null
    const api = apiParametros({
      'POST /plataforma/parametros/planos/previa': () => {
        pendente = adiada<typeof previa>()
        return pendente.promessa
      },
      'PUT /plataforma/parametros/planos': () =>
        erroApi(422, 'dados_invalidos', 'Confira os campos.', { 'planos.essencial.preco': 'Use um valor entre R$ 5,00 e R$ 99.999,99.' }),
    })
    await abrir('/plataforma/parametros')
    await digitar(campo('planos.essencial.preco'), '169')
    /** Enter no campo: o navegador envia o formulário com o foco ainda no campo e a prévia abre o diálogo. */
    async function enterNoCampo() {
      const preco = campo('planos.essencial.preco')!
      preco.focus()
      preco.closest('form')!.dispatchEvent(new Event('submit', { cancelable: true }))
      await flushPromises()
      // Como o navegador: o campo com foco dentro do fieldset desligado (durante a prévia) perde o foco para o body. O jsdom
      // não faz isso (nem o blur() de um campo desligado): o foco passa por um botão temporário, que sai da página.
      if (document.activeElement?.closest('fieldset[disabled]')) {
        const temporario = document.body.appendChild(document.createElement('button'))
        temporario.focus()
        temporario.remove()
        expect(document.activeElement).toBe(document.body)
      }
      pendente!.resolver(previa)
      await flushPromises()
      expect(dialogo()).not.toBeNull()
    }
    const fechamentos: Record<string, () => void> = {
      Esc: () => document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true })),
      Cancelar: () => Array.from(dialogo()!.querySelectorAll<HTMLButtonElement>('button')).find((b) => t(b.textContent) === 'Cancelar')!.click(),
      X: () => dialogo()!.querySelector<HTMLButtonElement>('button[aria-label="Fechar"]')!.click(),
      fora: () => (dialogo()!.previousElementSibling as HTMLElement).click(),
    }
    for (const [como, fechar] of Object.entries(fechamentos)) {
      await enterNoCampo()
      fechar()
      await flushPromises()
      expect(dialogo(), como).toBeNull()
      expect(document.activeElement, como).toBe(botaoSalvar('planos'))
    }
    expect(chamadasDe(api, 'PUT', '/plataforma/parametros/planos')).toHaveLength(0)
    // "Confirmar e salvar" com 422 no campo: o foco vai ao campo com o erro (não ao botão).
    await enterNoCampo()
    await clicar($('[data-confirmar-salvar]'))
    expect(dialogo()).toBeNull()
    expect(document.activeElement).toBe(campo('planos.essencial.preco'))
  })

  it('409 de outra pessoa: alerta com "Recarregar", que relê o grupo; o foco volta ao botão', async () => {
    entrar()
    let leituras = 0
    const api = apiParametros({
      'GET /plataforma/parametros': () => {
        leituras++
        const r = PARAMETROS()
        if (leituras > 1) r.grupos[3] = grupo('teste', { 'teste.dias': 30 }, { versao: 12, alterado_em: '2026-10-03T19:00:00Z', alterado_por: 'ana@toqqi.com' })
        return r
      },
      'POST /plataforma/parametros/teste/previa': () => ({ mudancas: [{ chave: 'teste.dias', de: 14, para: 7 }], precisa_confirmar: false, impactos: [] }),
      'PUT /plataforma/parametros/teste': () =>
        erroApi(409, 'parametros_alterados', 'Outra pessoa mudou estes parâmetros enquanto você editava. Recarregue para ver os valores atuais.'),
    })
    await abrir('/plataforma/parametros')
    await digitar(campo('teste.dias'), '7')
    await salvar('teste')
    const alerta = cartao('teste').querySelector<HTMLElement>('[data-alerta-cartao]')!
    expect(t(alerta.textContent)).toContain('Outra pessoa mudou estes parâmetros enquanto você editava. Recarregue para ver os valores atuais.')
    expect(document.activeElement).toBe(botaoSalvar('teste'))
    expect(campo('teste.dias')!.value).toBe('7')
    await clicar(alerta.querySelector('[data-recarregar]'))
    expect(chamadasDe(api, 'GET', '/plataforma/parametros')).toHaveLength(2)
    expect(campo('teste.dias')!.value).toBe('30')
    expect(cartao('teste').querySelector('[data-alerta-cartao]')).toBeNull()
    expect(t(cartao('teste').querySelector('[data-alterado]')!.textContent)).toBe('Alterado em 03/10/2026 às 16:00 por ana@toqqi.com')
  })

  it('422 da API: nos campos (foco no primeiro); `valores` vai para o alerta', async () => {
    entrar()
    let vez = 0
    apiParametros({
      'POST /plataforma/parametros/planos/previa': () =>
        ++vez === 1
          ? erroApi(422, 'dados_invalidos', 'Confira os campos.', { 'planos.profissional.preco': 'O preço do Profissional precisa ser maior que o do Essencial.' })
          : erroApi(422, 'dados_invalidos', 'Confira os campos.', { valores: 'Faltam chaves: planos.empresa.preco.' }),
    })
    await abrir('/plataforma/parametros')
    await digitar(campo('planos.essencial.preco'), '300')
    await salvar('planos')
    expect(t($('[data-parametro="planos.profissional.preco"]')!.textContent)).toContain('O preço do Profissional precisa ser maior que o do Essencial.')
    expect(document.activeElement).toBe(campo('planos.profissional.preco'))
    // Digitar no campo tira o erro dele.
    await digitar(campo('planos.profissional.preco'), '350,00')
    expect(campo('planos.profissional.preco')!.getAttribute('aria-invalid')).toBeNull()
    await salvar('planos')
    expect(t(cartao('planos').querySelector('[data-alerta-cartao]')!.textContent)).toBe('Faltam chaves: planos.empresa.preco.')
    expect(document.activeElement).toBe(botaoSalvar('planos'))
  })

  it('IA: "Testando o modelo…" enquanto salva; 503 avisa e nada é salvo; recusa da OpenAI (422) vai ao campo do modelo', async () => {
    entrar()
    const respostas: (() => Response | Promise<Response>)[] = []
    const espera = adiada<Response>()
    respostas.push(() => espera.promessa)
    respostas.push(() =>
      erroApi(422, 'dados_invalidos', 'Confira os campos.', {
        'ia.modelo.rapido': 'A OpenAI recusou o modelo “gpt-x” com o esforço “minimal” (HTTP 400). Confira o nome e o esforço.',
      }),
    )
    const api = apiParametros({
      'POST /plataforma/parametros/ia/previa': () => ({ mudancas: [{ chave: 'ia.modelo.rapido', de: 'gpt-5-nano', para: 'gpt-x' }], precisa_confirmar: false, impactos: [] }),
      'PUT /plataforma/parametros/ia': () => respostas.shift()!(),
    })
    await abrir('/plataforma/parametros')
    await digitar(campo('ia.modelo.rapido'), ' gpt-x ')
    await salvar('ia')
    const status = cartao('ia').querySelector('[data-status]')!
    expect(t(status.textContent)).toBe('Testando o modelo…')
    expect(botaoSalvar('ia').getAttribute('aria-busy')).toBe('true')
    // Os campos do grupo ficam travados enquanto salva.
    expect(cartao('ia').querySelector('fieldset')!.disabled).toBe(true)
    espera.resolver(
      erroApi(503, 'teste_ia_indisponivel', 'Não deu para testar o modelo agora: a OpenAI não respondeu. Nada foi salvo; tente de novo em alguns minutos.'),
    )
    await flushPromises()
    expect(t(cartao('ia').querySelector('[data-alerta-cartao]')!.textContent)).toBe(
      'Não deu para testar o modelo agora: a OpenAI não respondeu. Nada foi salvo; tente de novo em alguns minutos.',
    )
    expect(t(status.textContent)).toBe('')
    expect(campo('ia.modelo.rapido')!.value).toBe(' gpt-x ')
    expect(document.activeElement).toBe(botaoSalvar('ia'))
    expect(chamadasDe(api, 'PUT', '/plataforma/parametros/ia')[0]!.corpo).toMatchObject({ valores: { 'ia.modelo.rapido': 'gpt-x' }, confirmar: false })
    await salvar('ia')
    expect(t($('[data-parametro="ia.modelo.rapido"]')!.textContent)).toContain('A OpenAI recusou o modelo “gpt-x” com o esforço “minimal” (HTTP 400).')
    expect(document.activeElement).toBe(campo('ia.modelo.rapido'))
  })

  it('"Salvando…" no diálogo (anunciado ali) e 409 de confirmação mostra a prévia de novo', async () => {
    entrar()
    const espera = adiada<Response>()
    let puts = 0
    let previas = 0
    const api = apiParametros({
      'POST /plataforma/parametros/whatsapp/previa': () => {
        previas++
        return {
          mudancas: [{ chave: 'whatsapp.franquia.essencial', de: 40, para: 30 }],
          precisa_confirmar: previas > 1,
          impactos: [{ chave: 'whatsapp.franquia.essencial', contas: 3, exemplos: [] }],
        }
      },
      'PUT /plataforma/parametros/whatsapp': () => (++puts === 1 ? erroApi(409, 'confirmacao_necessaria', 'Confirme a mudança antes de salvar.') : espera.promessa),
    })
    await abrir('/plataforma/parametros')
    await digitar(campo('whatsapp.franquia.essencial'), '30')
    await salvar('whatsapp')
    // A API pediu confirmação (algo mudou desde a prévia): a tela confere de novo e abre o diálogo.
    expect(previas).toBe(2)
    expect(t(dialogo()!.querySelector('li')!.textContent)).toBe('Franquia de WhatsApp do Essencial: 40 → 30. 3 contas já usaram 30 ou mais neste mês.')
    await clicar($('[data-confirmar-salvar]'))
    expect(t($('[data-confirmar-salvar]')!.textContent)).toBe('Salvando…')
    expect(t(dialogo()!.querySelector('[aria-live]')!.textContent)).toBe('Salvando…')
    espera.resolver(new Response(JSON.stringify(grupo('whatsapp', { 'whatsapp.franquia.essencial': 30 }, { versao: 3 })), { status: 200 }))
    await flushPromises()
    expect(dialogo()).toBeNull()
    expect(chamadasDe(api, 'PUT', '/plataforma/parametros/whatsapp').map((c) => (c.corpo as { confirmar: boolean }).confirmar)).toEqual([false, true])
    expect(t(cartao('whatsapp').querySelector('[data-status]')!.textContent)).toBe('Parâmetros salvos.')
  })

  it('histórico: data, grupo, quem e uma linha por mudança; filtro "Grupo", páginas e estado vazio', async () => {
    entrar()
    const api = apiParametros({
      'GET /plataforma/parametros/historico': (c) => {
        const g = c.url.searchParams.get('grupo')
        const pagina = Number(c.url.searchParams.get('pagina') ?? '1')
        if (g === 'whatsapp') return paginaHistorico([], 0)
        if (g === 'teste') return paginaHistorico([HISTORICO[1]!])
        return { itens: pagina === 1 ? HISTORICO : [], total: 45, pagina, por_pagina: 20 }
      },
    })
    await abrir('/plataforma/parametros')
    const itens = () => $$('[data-item-historico]')
    expect(itens()).toHaveLength(2)
    expect(t(itens()[0]!.querySelector('[data-cabecalho-item]')!.textContent)).toBe('03/10/2026 às 14:32 Planos por marcelo@toqqi.com')
    expect(t(itens()[0]!.querySelector('ul')!.textContent)).toBe('Preço do Essencial: R$ 149,00 → R$ 159,00')
    expect(Array.from(itens()[1]!.querySelectorAll('ul li')).map((l) => t(l.textContent))).toEqual(['Dias de teste: 14 → 7', 'Exclusão automática: Simular → Ligada'])
    const historico = $('[data-historico-parametros]')!
    expect(t(historico.querySelector('nav[aria-label="Paginação"]')!.textContent)).toContain('45 alterações')
    await clicar(Array.from(historico.querySelectorAll<HTMLButtonElement>('button')).find((b) => t(b.textContent) === 'Próxima')!)
    expect(chamadasDe(api, 'GET', '/plataforma/parametros/historico').at(-1)!.url.searchParams.get('pagina')).toBe('2')
    const filtro = historico.querySelector<HTMLSelectElement>('select')!
    expect(Array.from(filtro.options).map((o) => o.text)).toEqual(['Todos', 'Planos', 'IA', 'WhatsApp automático', 'Teste e cortesia'])
    await escolher(filtro, 'teste')
    const ultima = chamadasDe(api, 'GET', '/plataforma/parametros/historico').at(-1)!
    expect([ultima.url.searchParams.get('grupo'), ultima.url.searchParams.get('pagina')]).toEqual(['teste', '1'])
    expect(itens()).toHaveLength(1)
    await escolher(filtro, 'whatsapp')
    expect(itens()).toHaveLength(0)
    expect(t(historico.textContent)).toContain('Nenhuma alteração neste grupo')
  })
})

// ── Abas e acesso ───────────────────────────────────────────────────────────

describe('Plataforma: abas e acesso', () => {
  const CONTA: ContaPlataforma = { id: 2, nome: 'Alfa', plano: 'profissional', situacao: 'teste', teste_ate: '2026-09-20T10:00:00-03:00', usuarios: 2, criada_em: '2026-09-01T12:00:00Z' }

  it('"Contas" em /plataforma; "Parâmetros" muda o endereço e carrega os grupos; o menu continua com um item', async () => {
    entrar()
    const api = apiParametros({ 'GET /plataforma/contas': () => [CONTA] })
    await abrir('/plataforma')
    const abas = $$('[role="tab"]')
    expect(abas.map((a) => t(a.textContent))).toEqual(['Contas', 'Parâmetros'])
    expect(abas[0]!.getAttribute('aria-selected')).toBe('true')
    expect(chamadasDe(api, 'GET', '/plataforma/parametros')).toHaveLength(0)
    await clicar(abas[1]!)
    await flushPromises()
    expect(router.currentRoute.value.path).toBe('/plataforma/parametros')
    expect($$('section[data-grupo]')).toHaveLength(4)
    // Voltar para Contas mantém a tabela (sem buscar de novo).
    await clicar($$('[role="tab"]')[0]!)
    expect(router.currentRoute.value.path).toBe('/plataforma')
    expect(chamadasDe(api, 'GET', '/plataforma/contas')).toHaveLength(1)
    expect(rotasDoApp.resolve('/plataforma/parametros').meta).toMatchObject({ titulo: 'Plataforma', superadmin: true })
    expect(rotasDoApp.resolve('/plataforma/parametros').name).toBe('plataforma')
  })

  it('cada aba mostra só o que é dela (a lista de contas some em Parâmetros e volta), sem aviso do Vue', async () => {
    const avisosVue = vi.spyOn(console, 'warn').mockImplementation(() => {})
    try {
      entrar()
      apiParametros({ 'GET /plataforma/contas': () => [CONTA] })
      await abrir('/plataforma')
      const busca = () => $<HTMLInputElement>('input[type="search"]')
      const novaConta = () => $$('button').find((b) => t(b.textContent) === 'Nova conta') ?? null
      expect([visivel(busca()), visivel(novaConta()), visivel($('table'))]).toEqual([true, true, true])
      await clicar($$('[role="tab"]')[1]!)
      expect([visivel(busca()), visivel(novaConta()), visivel($('table'))]).toEqual([false, false, false])
      expect(visivel($('[data-aba-parametros]'))).toBe(true)
      await clicar($$('[role="tab"]')[0]!)
      expect([visivel(busca()), visivel(novaConta()), visivel($('table'))]).toEqual([true, true, true])
      expect(visivel($('[data-aba-parametros]'))).toBe(false)
      // A busca digitada continua lá (a aba guarda o que tem enquanto a pessoa alterna).
      await digitar(busca(), 'alf')
      await clicar($$('[role="tab"]')[1]!)
      await clicar($$('[role="tab"]')[0]!)
      expect(busca()!.value).toBe('alf')
      expect(avisosVue.mock.calls.map((c) => String(c[0])).filter((m) => m.includes('[Vue warn]'))).toEqual([])
    } finally {
      avisosVue.mockRestore()
    }
  })

  it('"+N dias" segue o teste.dias de Parâmetros na mesma página (lido do banco e salvo): botão, diálogo, pedido e "Nova conta"', async () => {
    entrar()
    let diasNoBanco = 10
    const api = apiParametros({
      'GET /plataforma/contas': () => [CONTA],
      // A leitura pública tem cache (60 s no navegador, 30 s na API): continua dizendo 14 depois das mudanças.
      'GET /publico/planos': () => ({ planos: [], teste: { dias: 14, plano: 'profissional', whatsapp: 20, ia_teto: 1000 }, ia_analises: {} }),
      'GET /plataforma/parametros': () => {
        const r = PARAMETROS()
        r.grupos[3] = grupo('teste', { 'teste.dias': diasNoBanco }, { versao: 4 })
        return r
      },
      'POST /plataforma/parametros/teste/previa': () => ({ mudancas: [{ chave: 'teste.dias', de: 10, para: 7 }], precisa_confirmar: false, impactos: [] }),
      'PUT /plataforma/parametros/teste': (c) => {
        const valores = (c.corpo as { valores: Record<string, ValorParametro> }).valores
        diasNoBanco = valores['teste.dias'] as number
        return grupo('teste', valores, { versao: 5 })
      },
      'POST /plataforma/contas/:id/estender-teste': () => ({ ...CONTA, teste_ate: '2026-10-10T23:59:59-03:00' }),
    })
    await abrir('/plataforma')
    const estender = () => $$('tbody button').find((b) => t(b.textContent).startsWith('+'))!
    expect(t(estender().textContent)).toBe('+14 dias para Alfa')
    // Abrir Parâmetros lê o banco (10): Contas passa a mostrar esse número.
    await clicar($$('[role="tab"]')[1]!)
    expect(campo('teste.dias')!.value).toBe('10')
    await clicar($$('[role="tab"]')[0]!)
    expect(t(estender().textContent)).toBe('+10 dias para Alfa')
    // Salvar 7 e voltar para Contas sem recarregar a página.
    await clicar($$('[role="tab"]')[1]!)
    await digitar(campo('teste.dias'), '7')
    await salvar('teste')
    expect(t(cartao('teste').querySelector('[data-status]')!.textContent)).toBe('Parâmetros salvos.')
    await clicar($$('[role="tab"]')[0]!)
    expect(t(estender().textContent)).toBe('+7 dias para Alfa')
    estender().click()
    await flushPromises()
    expect(estadoConfirmacao.titulo).toBe('Dar mais 7 dias para Alfa?')
    expect(estadoConfirmacao.mensagem).toBe('O teste acabou em 20/09/2026. Os 7 dias contam a partir de hoje.')
    expect(estadoConfirmacao.confirmar).toBe('+7 dias')
    responderConfirmacao(true)
    await flushPromises()
    expect(chamadasDe(api, 'POST', '/plataforma/contas/2/estender-teste').map((c) => c.corpo)).toEqual([{ dias: 7 }])
    await clicar($$('button').find((b) => t(b.textContent) === 'Nova conta')!)
    expect(t(dialogoOuJanela()!.textContent)).toContain('7 dias para conhecer o Toqqi.')
  })

  it('só superadmin: os outros voltam ao início com o aviso', async () => {
    entrar({ superadmin: false })
    apiFalsa({ 'GET /ajuda': () => ({ versao: 1, topicos: [] }) })
    await rotasDoApp.push('/plataforma/parametros')
    expect(rotasDoApp.currentRoute.value.path).toBe('/inicio')
    expect(avisos.map((a) => a.mensagem)).toContain('Esta área é só para a equipe da plataforma Toqqi.')
  })

  it('"+N dias", o diálogo, o pedido e a "Nova conta" usam teste.dias; sem a resposta, 14', async () => {
    entrar()
    const api = apiFalsa({
      'GET /plataforma/contas': () => [CONTA],
      'GET /publico/planos': () => ({ planos: [], teste: { dias: 7, plano: 'essencial', whatsapp: 20, ia_teto: 1000 }, ia_analises: { rapido: 1, equilibrado: 1, detalhado: 2 } }),
      'POST /plataforma/contas/:id/estender-teste': () => ({ ...CONTA, teste_ate: '2026-10-10T23:59:59-03:00' }),
    })
    await abrir('/plataforma')
    const estender = $$('tbody button').find((b) => t(b.textContent).startsWith('+'))!
    expect(t(estender.textContent)).toBe('+7 dias para Alfa')
    estender.click()
    await flushPromises()
    expect(estadoConfirmacao.titulo).toBe('Dar mais 7 dias para Alfa?')
    expect(estadoConfirmacao.mensagem).toBe('O teste acabou em 20/09/2026. Os 7 dias contam a partir de hoje.')
    expect(estadoConfirmacao.confirmar).toBe('+7 dias')
    responderConfirmacao(true)
    await flushPromises()
    expect(chamadasDe(api, 'POST', '/plataforma/contas/2/estender-teste')[0]!.corpo).toEqual({ dias: 7 })
    // Nova conta
    await clicar($$('button').find((b) => t(b.textContent) === 'Nova conta')!)
    expect(t(dialogoOuJanela()!.textContent)).toContain('7 dias para conhecer o Toqqi.')
  })

  it('sem /publico/planos, "+14 dias" (o padrão)', async () => {
    entrar()
    apiFalsa({ 'GET /plataforma/contas': () => [CONTA], 'GET /publico/planos': () => erroApi(503, 'erro_servidor', 'Fora do ar.') })
    await abrir('/plataforma')
    expect(t($$('tbody button').find((b) => t(b.textContent).startsWith('+'))!.textContent)).toBe('+14 dias para Alfa')
  })
})

const dialogoOuJanela = () => $('[role="dialog"]') ?? $('[role="alertdialog"]')

// ── Cadastro ────────────────────────────────────────────────────────────────

describe('Cadastro: os dias do teste', () => {
  it('os três "N dias" vêm de teste.dias (sem login); sem resposta, 14', async () => {
    const api = apiFalsa({ 'GET /publico/planos': () => ({ planos: [], teste: { dias: 7, plano: 'essencial', whatsapp: 20, ia_teto: 1000 }, ia_analises: {} }) })
    await abrir('/cadastro')
    expect(t(document.body.textContent)).toContain('Em poucos minutos você começa a ouvir seus clientes. 7 dias grátis, sem cartão.')
    expect(t($$('button[type="submit"]').at(-1)!.textContent)).toBe('Começar 7 dias grátis')
    const pedido = chamadasDe(api, 'GET', '/publico/planos')[0]!
    expect(pedido).toBeDefined()
    document.body.innerHTML = ''
  })
  it('falhou: 14 dias', async () => {
    apiFalsa({})
    await abrir('/cadastro')
    expect(t($$('button[type="submit"]').at(-1)!.textContent)).toBe('Começar 14 dias grátis')
  })
})

// ── Assinatura: o preço que a tela mostrou ──────────────────────────────────

describe('Assinatura: preço mostrado e 409 `preco_mudou`', () => {
  const PLANOS: PlanoAssinatura[] = [
    { chave: 'essencial', nome: 'Essencial', preco: '149.00', contatos: 300 },
    { chave: 'profissional', nome: 'Profissional', preco: '349.00', contatos: 1500 },
    { chave: 'empresa', nome: 'Empresa', preco: '799.00', contatos: null },
  ]
  const comPreco = (chave: string, preco: string) => PLANOS.map((p) => (p.chave === chave ? { ...p, preco } : p))
  const SUGERIDOS = { razao_social: 'Distribuidora Sol Nascente Ltda', documento: '11222333000181', email_cobranca: 'ana@sol.com.br', telefone: '5511987654321' }
  const ASSINATURA = {
    plano: 'profissional',
    valor: '349.00',
    situacao: 'ativa',
    criada_em: '2026-09-01T15:00:00Z',
    cancelada_em: null,
    primeiro_vencimento: '2026-09-15',
    dados: { razao_social: 'Sol', documento: '11222333000181', email_cobranca: 'financeiro@sol.com.br', telefone: '5511987654321' },
  }
  function estado(p: Partial<EstadoAssinatura> = {}): EstadoAssinatura {
    return {
      contatos_ativos: 120,
      disponivel: true,
      planos: PLANOS,
      dados_sugeridos: SUGERIDOS,
      assinatura: null,
      fatura_aberta: null,
      cobrancas: [],
      ...p,
      conta: { situacao: 'teste', plano: 'profissional', teste_ate: '2099-10-15T14:30:00-03:00', pago_ate: null, atrasada_desde: null, liberada: true, pausa_em: null },
    }
  }
  const PRECO_MUDOU = 'O preço do plano Profissional mudou para R$ 399,00. Confira e confirme de novo.'
  /** 422 da API quando o `preco` não veio (ou veio inválido): ex.: a página foi aberta antes de uma atualização do site. */
  const PRECO_422 = 'Recarregue a página para ver o preço atual do plano.'
  const erroPreco = () => erroApi(422, 'dados_invalidos', 'Confira os campos destacados.', { preco: PRECO_422 })
  /** Roda `fn` com um `location.reload` falso (o jsdom não recarrega a página). */
  async function comRecarregarFalso(fn: (recarregar: ReturnType<typeof vi.fn>) => Promise<void>) {
    const recarregar = vi.fn()
    const original = window.location
    Object.defineProperty(window, 'location', { configurable: true, value: { ...original, reload: recarregar } })
    try {
      await fn(recarregar)
    } finally {
      Object.defineProperty(window, 'location', { configurable: true, value: original })
    }
  }

  it('assinar manda o preço; 409 relê os planos, explica e o próximo envio leva o preço novo', async () => {
    entrar({ superadmin: false, permissoes: ['assinatura.gerenciar'] })
    let leituras = 0
    const api = apiFalsa({
      'GET /assinatura': () => (++leituras === 1 ? estado() : estado({ planos: comPreco('profissional', '399.00') })),
      'POST /assinatura': (c) =>
        (c.corpo as { preco: string }).preco === '399.00' ? estado({ assinatura: { ...ASSINATURA, valor: '399.00' } }) : erroApi(409, 'preco_mudou', PRECO_MUDOU),
      'GET /eu': () => ({ usuario: { ...USUARIO, perfil: 'admin', superadmin: false }, conta: { id: 1, nome: 'Sol', plano: 'profissional', situacao: 'teste', teste_ate: null }, permissoes: ['assinatura.gerenciar'] }),
    })
    await abrir('/assinatura')
    const radio = $<HTMLInputElement>('input[type="radio"][value="profissional"]')!
    radio.checked = true
    radio.dispatchEvent(new Event('change'))
    await flushPromises()
    $('[data-form-assinar] form')!.dispatchEvent(new Event('submit', { cancelable: true }))
    await flushPromises()
    expect((chamadasDe(api, 'POST', '/assinatura')[0]!.corpo as { preco: string; plano: string })).toMatchObject({ plano: 'profissional', preco: '349.00' })
    expect(leituras).toBe(2)
    expect(t($('[data-erro-assinar]')!.textContent)).toBe(PRECO_MUDOU)
    expect($('[data-erro-assinar]')!.getAttribute('role')).toBe('status')
    expect(t($('[data-resumo]')!.textContent)).toContain('Primeira fatura de R$ 399,00')
    expect(t($('[data-plano="profissional"]')!.textContent)).toContain('R$ 399,00')
    $('[data-form-assinar] form')!.dispatchEvent(new Event('submit', { cancelable: true }))
    await flushPromises()
    expect(chamadasDe(api, 'POST', '/assinatura').map((c) => (c.corpo as { preco: string }).preco)).toEqual(['349.00', '399.00'])
  })

  it('trocar de plano: o atual mostra o contratado quando o preço mudou; 409 relê e explica', async () => {
    entrar({ superadmin: false, permissoes: ['assinatura.gerenciar'] })
    const assinada = (planos: PlanoAssinatura[]) => estado({ assinatura: ASSINATURA, planos })
    let leituras = 0
    const api = apiFalsa({
      'GET /assinatura': () => (++leituras === 1 ? assinada(comPreco('profissional', '399.00')) : assinada(comPreco('empresa', '899.00').map((p) => (p.chave === 'profissional' ? { ...p, preco: '399.00' } : p)))),
      'PUT /assinatura/plano': () => erroApi(409, 'preco_mudou', 'O preço do plano Empresa mudou para R$ 899,00. Confira e confirme de novo.'),
    })
    await abrir('/assinatura')
    await clicar($$('button').find((b) => t(b.textContent) === 'Trocar de plano')!)
    const janela = () => $('[role="dialog"]')!
    expect(t(janela().querySelector('[data-plano="profissional"] [data-contratado]')!.textContent)).toBe('Você paga R$ 349,00; hoje o plano custa R$ 399,00.')
    expect(janela().querySelector('[data-plano="empresa"] [data-contratado]')).toBeNull()
    const empresa = janela().querySelector<HTMLInputElement>('input[value="empresa"]')!
    empresa.checked = true
    empresa.dispatchEvent(new Event('change'))
    await flushPromises()
    expect(t(janela().querySelector('[data-efeito]')!.textContent)).toContain('O valor passa de R$ 349,00 para R$ 799,00 por mês.')
    janela().querySelector('form')!.dispatchEvent(new Event('submit', { cancelable: true }))
    await flushPromises()
    expect(chamadasDe(api, 'PUT', '/assinatura/plano')[0]!.corpo).toEqual({ plano: 'empresa', preco: '799.00' })
    expect(leituras).toBe(2)
    expect(t(janela().querySelector('[data-erro-troca]')!.textContent)).toBe('O preço do plano Empresa mudou para R$ 899,00. Confira e confirme de novo.')
    expect(t(janela().querySelector('[data-efeito]')!.textContent)).toContain('O valor passa de R$ 349,00 para R$ 899,00 por mês.')
  })

  it('assinar: 422 no campo `preco` mostra a mensagem da API com "Recarregar" (foco nele), que recarrega a página', async () => {
    entrar({ superadmin: false, permissoes: ['assinatura.gerenciar'] })
    const api = apiFalsa({ 'GET /assinatura': () => estado(), 'POST /assinatura': () => erroPreco() })
    await comRecarregarFalso(async (recarregar) => {
      await abrir('/assinatura')
      const radio = $<HTMLInputElement>('input[type="radio"][value="essencial"]')!
      radio.checked = true
      radio.dispatchEvent(new Event('change'))
      await flushPromises()
      $('[data-form-assinar] form')!.dispatchEvent(new Event('submit', { cancelable: true }))
      await flushPromises()
      expect(chamadasDe(api, 'POST', '/assinatura')[0]!.corpo).toMatchObject({ plano: 'essencial', preco: '149.00' })
      const alerta = $('[data-erro-assinar]')!
      expect(t(alerta.textContent)).toBe(`${PRECO_422} Recarregar`)
      expect(alerta.getAttribute('role')).toBe('status')
      const botao = alerta.querySelector<HTMLButtonElement>('[data-recarregar]')!
      expect(document.activeElement).toBe(botao)
      expect(recarregar).not.toHaveBeenCalled()
      await clicar(botao)
      expect(recarregar).toHaveBeenCalledOnce()
      // "Recarregar" só recarrega: não manda nada à API.
      expect(chamadasDe(api, 'POST', '/assinatura')).toHaveLength(1)
    })
  })

  it('trocar de plano: o pedido leva sempre o preço; 422 no campo `preco` mostra a mensagem com "Recarregar" na janela', async () => {
    entrar({ superadmin: false, permissoes: ['assinatura.gerenciar'] })
    let vez = 0
    const api = apiFalsa({
      'GET /assinatura': () => estado({ assinatura: ASSINATURA }),
      'PUT /assinatura/plano': () => (++vez === 1 ? erroPreco() : erroApi(422, 'limite_do_plano', 'Este plano não comporta os contatos ativos.')),
    })
    await comRecarregarFalso(async (recarregar) => {
      await abrir('/assinatura')
      await clicar($$('button').find((b) => t(b.textContent) === 'Trocar de plano')!)
      const janela = () => $('[role="dialog"]')!
      const essencial = janela().querySelector<HTMLInputElement>('input[value="essencial"]')!
      essencial.checked = true
      essencial.dispatchEvent(new Event('change'))
      await flushPromises()
      janela().querySelector('form')!.dispatchEvent(new Event('submit', { cancelable: true }))
      await flushPromises()
      expect(chamadasDe(api, 'PUT', '/assinatura/plano')[0]!.corpo).toEqual({ plano: 'essencial', preco: '149.00' })
      const alerta = janela().querySelector<HTMLElement>('[data-erro-troca]')!
      expect(t(alerta.textContent)).toBe(`${PRECO_422} Recarregar`)
      expect(alerta.getAttribute('role')).toBe('status')
      expect(document.activeElement).toBe(alerta.querySelector('[data-recarregar]'))
      await clicar(alerta.querySelector('[data-recarregar]'))
      expect(recarregar).toHaveBeenCalledOnce()
      // Outro erro (sem o campo `preco`) não traz o "Recarregar".
      janela().querySelector('form')!.dispatchEvent(new Event('submit', { cancelable: true }))
      await flushPromises()
      expect(t(janela().querySelector('[data-erro-troca]')!.textContent)).toBe('Este plano não comporta os contatos ativos.')
      expect(janela().querySelector('[data-recarregar]')).toBeNull()
    })
  })
})

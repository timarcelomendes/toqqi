// Plano Grátis (docs/api-plano-gratis.md) no site: as regras puras (gratis.ts, denúncias, parâmetros, cadastro,
// validação do descanso) e as telas com a API simulada: o aviso do topo, as travas (Equipe, Formulários, Integrações,
// Configurações de envio, envio manual), as pré-condições, "Denunciar esta pesquisa" e Plataforma › Feedback ›
// Denúncias.
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { enableAutoUnmount, flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createMemoryHistory, createRouter, RouterView, type Router } from 'vue-router'
import { defineComponent, h, type Component } from 'vue'
import type { DenunciaPlataforma, FormularioResumo, PreCondicoes, ResumoGratis } from '@/api/tipos'
import { avisos } from '@/composables/avisos'
import { gratisDoPublico, textoDepoisDoTeste } from '@/composables/planosPublicos'
import { useSessaoStore } from '@/stores/sessao'
import AvisoCobranca from '@/components/app/AvisoCobranca.vue'
import AvisoPlanoGratis from '@/components/app/AvisoPlanoGratis.vue'
import {
  avisoDoGratis,
  diaPorExtenso,
  itensDoGratis,
  textoDaPassagem,
  textoUsuarios,
  usoDoGratis,
} from '@/modulos/assinatura/gratis'
import { validarConfig } from '@/modulos/configuracoes/mensagens'
import AvisoPreCondicoes from '@/modulos/envios/AvisoPreCondicoes.vue'
import FormulariosView from '@/modulos/formularios/FormulariosView.vue'
import IntegracoesView from '@/modulos/integracoes/IntegracoesView.vue'
import AbaFeedback from '@/modulos/plataforma/AbaFeedback.vue'
import { infoSituacaoDenuncia, linkDaConta, mensagemSituacao, rotuloMotivo, rotuloOrigem, textoAbertas } from '@/modulos/plataforma/denuncias'
import { formDe, lerFormulario, textoConfirmacao } from '@/modulos/plataforma/parametros'
import { textoSinal } from '@/modulos/plataforma/risco'
import Pesquisa from '@/pesquisa/Pesquisa.vue'
import type { FormularioPublico } from '@/pesquisa/tipos'
import { apiFalsa } from './apiFalsa'

const t = (s: string | null | undefined) => (s ?? '').replace(/ /g, ' ').replace(/\s+/g, ' ').trim()

function resumo(extra: Partial<ResumoGratis> = {}): ResumoGratis {
  return {
    desde: '2026-10-01T03:00:00Z',
    motivo: 'teste',
    contatos: { ativos: 40, limite: 100 },
    envios: { mes: 12, limite_mes: 200, dia: 3, limite_dia: 100, volta_mes: '2026-11-01', volta_dia: '2026-10-14' },
    ia: { usadas: 2, limite: 10 },
    usuarios: 1,
    formularios: 2,
    descanso_minimo: 30,
    dias_sem_uso: 180,
    pausada_por_risco: false,
    ...extra,
  }
}

// ───────────────────────── Regras puras ─────────────────────────

describe('gratis.ts: textos e prioridade do aviso', () => {
  it('a passagem, pelo motivo, com os limites da conta (ou os padrões)', () => {
    expect(textoDaPassagem('teste', resumo())).toBe('Seu teste acabou e a conta passou para o Grátis: até 100 contatos e 200 envios por e-mail por mês.')
    expect(textoDaPassagem('cancelamento', null)).toBe('O período pago terminou e a conta passou para o Grátis: até 100 contatos e 200 envios por e-mail por mês.')
    expect(textoDaPassagem('atraso', resumo({ contatos: { ativos: 1, limite: 1500 } }))).toBe(
      'A assinatura foi cancelada por falta de pagamento e a conta passou para o Grátis: até 1.500 contatos e 200 envios por e-mail por mês.',
    )
  })

  it('aviso do limite: pausa pelo risco, contatos, mês, dia, nada; os que pedem ação não fecham', () => {
    expect(avisoDoGratis(null)).toBeNull()
    expect(avisoDoGratis(resumo())).toBeNull()
    const risco = avisoDoGratis(resumo({ pausada_por_risco: true, contatos: { ativos: 300, limite: 100 } }))!
    expect([risco.chave, risco.tom, risco.acoes, risco.dispensavel]).toEqual(['gratis:revisao', 'atencao', ['feedback'], false])
    const contatos = avisoDoGratis(resumo({ contatos: { ativos: 140, limite: 100 }, envios: { ...resumo().envios, mes: 200 } }))!
    expect(contatos.texto).toBe('Sua conta tem 140 contatos ativos. O Grátis envia para até 100: escolha quais manter ativos ou assine um plano.')
    expect([contatos.acoes, contatos.dispensavel]).toEqual([['contatos', 'planos'], false])
    const mes = avisoDoGratis(resumo({ envios: { ...resumo().envios, mes: 200, dia: 100 } }))!
    expect([mes.chave, mes.texto, mes.dispensavel]).toEqual([
      'gratis:mes:2026-11-01',
      'Os envios por e-mail deste mês acabaram (200 de 200). Voltam em 1º de novembro, ou assine para continuar agora.',
      true,
    ])
    const dia = avisoDoGratis(resumo({ envios: { ...resumo().envios, dia: 100 } }))!
    expect([dia.chave, dia.texto]).toEqual(['gratis:dia:2026-10-14', 'Os envios por e-mail de hoje acabaram (100 de 100). Voltam amanhã.'])
  })

  it('o uso, os itens do cartão e os textos curtos', () => {
    expect(usoDoGratis(resumo()).map((u) => [u.chave, u.texto, u.dica])).toEqual([
      ['contatos', '40 de 100', 'Contatos inativos não contam.'],
      ['envios', '12 de 200', 'Até 100 por dia. Zeram em 01/11.'],
      ['ia', '2 de 10', 'Perguntas e análises pedidas ao ToqqiAI.'],
    ])
    expect(itensDoGratis({ usuarios: 3, formularios: 2 })[0]).toBe('até 3 usuários e até 2 formulários recebendo respostas')
    expect([textoUsuarios(1), textoUsuarios(5)]).toEqual(['1 usuário', 'até 5 usuários'])
    expect([diaPorExtenso('2026-11-01'), diaPorExtenso('2026-03-15'), diaPorExtenso('x')]).toEqual(['1º de novembro', '15 de março', 'x'])
  })
})

describe('denúncias, parâmetros, cadastro e descanso', () => {
  it('rótulos e textos das denúncias', () => {
    expect(rotuloMotivo('dados_pessoais')).toBe('Pede senha, cartão ou dados bancários')
    expect(rotuloMotivo('novo')).toBe('novo')
    expect([rotuloOrigem('convite'), rotuloOrigem('link_publico')]).toEqual(['Pelo convite', 'Pelo link público'])
    expect(infoSituacaoDenuncia('procedente')).toEqual({ rotulo: 'Procedente', tom: 'erro' })
    expect([textoAbertas(0), textoAbertas(1), textoAbertas(3)]).toEqual(['Nenhuma denúncia aberta', '1 denúncia aberta', '3 denúncias abertas'])
    expect(mensagemSituacao('descartada')).toBe('Denúncia descartada: ela não pesa mais na nota de risco da conta.')
    expect(linkDaConta({ conta: { id: 4, nome: 'Alfa & Cia', situacao: 'gratis' } })).toBe('/plataforma/contas?busca=Alfa%20%26%20Cia')
    expect(linkDaConta({ conta: { id: 4, nome: null, situacao: null } })).toBeNull()
    expect(textoSinal({ tipo: 'denuncias', pontos: 60, pessoas: 2, denuncias: 3 })).toBe('Pesquisa denunciada por 2 pessoas em 30 dias (3 denúncias)')
    expect(textoSinal({ tipo: 'denuncias', pontos: 30, pessoas: 1, denuncias: 1 })).toBe('Pesquisa denunciada por 1 pessoa em 30 dias')
  })

  it('Parâmetros › Plano Grátis: a ordem dos números (dia ≤ mês, aviso < exclusão) e o impacto de cada limite menor', () => {
    const dados = {
      grupo: 'gratis',
      valores: {
        'gratis.contatos': 100,
        'gratis.envios_mes': 200,
        'gratis.envios_dia': 100,
        'gratis.usuarios': 1,
        'gratis.dias_sem_uso': 180,
        'gratis.dias_aviso': 30,
        'gratis.dias_atraso': 30,
      },
    }
    const form = formDe(dados)
    expect(lerFormulario(dados, form).erros).toEqual({})
    form.textos['gratis.envios_dia'] = '201'
    form.textos['gratis.dias_aviso'] = '60'
    form.textos['gratis.dias_sem_uso'] = '60'
    expect(lerFormulario(dados, form).erros).toEqual({
      'gratis.envios_dia': 'Os envios do dia não podem passar dos envios do mês.',
      'gratis.dias_aviso': 'O aviso precisa sair antes da exclusão.',
    })
    const m = (chave: string, de: number, para: number) => ({ chave, de, para })
    const c = textoConfirmacao('Plano Grátis', {
      mudancas: [m('gratis.envios_mes', 200, 150), m('gratis.envios_dia', 100, 50), m('gratis.usuarios', 3, 1), m('gratis.dias_sem_uso', 180, 120), m('gratis.contatos', 100, 120)],
      impactos: [
        { chave: 'gratis.envios_mes', contas: 1, exemplos: [{ id: 1, nome: 'Alfa', uso: 170 }] },
        { chave: 'gratis.envios_dia', contas: 0, exemplos: [] },
        { chave: 'gratis.usuarios', contas: 2, exemplos: [{ id: 1, nome: 'Alfa', uso: 3 }, { id: 2, nome: 'Beta', uso: 2 }] },
      ],
    })
    expect(c.linhas.map((l) => l.texto)).toEqual([
      'Envios por mês do Grátis: 200 → 150. 1 conta Grátis (Alfa) já mandou 150 e-mails ou mais neste mês: os próximos esperam o mês virar.',
      'Envios por dia do Grátis: 100 → 50. Nenhuma conta Grátis mandou 50 e-mails ou mais hoje.',
      'Usuários do Grátis: 3 → 1. 2 contas Grátis (Alfa e Beta) têm mais usuários ativos: no próximo login, os mais novos ficam de fora.',
      'Dias sem uso até excluir a conta Grátis: 180 → 120.',
      'Contatos do Grátis: 100 → 120.',
    ])
    expect(c.aviso).not.toBeNull()
  })

  it('cadastro: o que acontece depois do teste, com os números de /publico/planos (ou os padrões)', () => {
    expect(gratisDoPublico({ gratis: { contatos: 80, envios_mes: 150, usuarios: 1, ia_cota: 10 } })).toEqual({ contatos: 80, envios_mes: 150 })
    expect(gratisDoPublico({ gratis: { contatos: 0, envios_mes: 150, usuarios: 1, ia_cota: 10 } })).toBeNull()
    expect(gratisDoPublico({})).toBeNull()
    expect(textoDepoisDoTeste(null)).toBe('Depois do teste, se não assinar, a conta continua no plano Grátis: até 100 contatos e 200 envios por e-mail por mês.')
    expect(textoDepoisDoTeste({ contatos: 1500, envios_mes: 300 })).toContain('até 1.500 contatos e 300 envios por e-mail por mês')
  })

  it('Configurações de envio: no Grátis, o descanso tem piso (a mesma frase da API)', () => {
    const base = {
      envios_ativos: true,
      envio_automatico: false,
      formulario_id: 1,
      intervalo_dias: 90,
      descanso_dias: 10,
      lembretes: 0,
      dias_lembretes: [],
      janela_inicio: '08:00',
      janela_fim: '18:00',
      so_dias_uteis: true,
      responder_para: null,
      remetente_nome: null,
      assunto_convite: 'a',
      texto_convite: 'b',
      assunto_lembrete: 'c',
      texto_lembrete: 'd',
      texto_whatsapp: 'Oi {link}',
      agradecimento_ativo: false,
      agradecimento: { promotor: '', neutro: '', detrator: '' },
      canal: 'email',
    } as unknown as Parameters<typeof validarConfig>[0]
    expect(validarConfig(base).descanso_dias).toBeUndefined()
    expect(validarConfig(base, { descansoMinimo: 30 }).descanso_dias).toBe('No plano Grátis, o descanso entre pesquisas é de pelo menos 30 dias.')
    expect(validarConfig({ ...base, descanso_dias: 30 }, { descansoMinimo: 30 }).descanso_dias).toBeUndefined()
  })
})

// ───────────────────────── Telas ─────────────────────────

const USUARIO = { id: 1, nome: 'Ana Paula', email: 'ana@sol.com.br', cargo: null, situacao: 'ativo' as const, email_confirmado: true, ultimo_acesso: null }

function entrar(permissoes: string[], gratis: ResumoGratis | null = resumo(), opcoes: { superadmin?: boolean } = {}) {
  const s = useSessaoStore()
  s.definirSessao(
    {
      token: 't',
      expira_em: '2099-01-01T00:00:00Z',
      usuario: { ...USUARIO, perfil: 'admin', superadmin: !!opcoes.superadmin },
      conta: {
        id: 1,
        nome: 'Distribuidora Sol',
        plano: 'profissional',
        situacao: gratis ? 'gratis' : 'ativa',
        teste_ate: '2026-09-30T00:00:00-03:00',
        cobranca: { liberada: true, pago_ate: null, atrasada_desde: null, pausa_em: null, aviso: null, exclusao_em: null },
        gratis,
      },
      permissoes: permissoes as never,
    },
    false,
  )
  s.inicializada = true
  return s
}

let router: Router
async function abrir(caminho: string, componente: Component, rota = caminho.split('?')[0]!): Promise<VueWrapper> {
  router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: rota, component: componente },
      { path: '/:qualquer(.*)*', component: { render: () => h('div', 'outra página') } },
    ],
  })
  await router.push(caminho)
  await router.isReady()
  const w = mount(defineComponent({ render: () => h(RouterView) }), { global: { plugins: [router] }, attachTo: document.body })
  await flushPromises()
  return w
}
async function montar(componente: Component, caminho = '/inicio', props: Record<string, unknown> = {}): Promise<VueWrapper> {
  router = createRouter({ history: createMemoryHistory(), routes: [{ path: '/:qualquer(.*)*', component: { render: () => h('div') } }] })
  await router.push(caminho)
  await router.isReady()
  const w = mount(componente, { props, global: { plugins: [router] }, attachTo: document.body })
  await flushPromises()
  return w
}
const $ = (sel: string) => document.body.querySelector<HTMLElement>(sel)
const $$ = (sel: string) => Array.from(document.body.querySelectorAll<HTMLElement>(sel))
async function clicar(el: HTMLElement | null) {
  if (!el) throw new Error('Elemento não encontrado')
  el.click()
  await flushPromises()
}
const chamadasDe = (api: ReturnType<typeof apiFalsa>, metodo: string, caminho: string) => api.chamadas.filter((c) => c.metodo === metodo && c.caminho === caminho)

enableAutoUnmount(afterEach)
beforeEach(() => {
  setActivePinia(createPinia())
  sessionStorage.clear()
  avisos.splice(0)
  Element.prototype.scrollIntoView = vi.fn() as unknown as Element['scrollIntoView']
})
afterEach(() => {
  vi.unstubAllGlobals()
  document.body.innerHTML = ''
})

describe('o aviso do topo e o aviso "Plano Grátis"', () => {
  it('passou de um limite: o aviso do Grátis no lugar do de cobrança; "Ver planos" só para quem cuida da assinatura; some na Assinatura', async () => {
    entrar(['assinatura.gerenciar'], resumo({ contatos: { ativos: 140, limite: 100 } }))
    const w = await montar(AvisoCobranca, '/inicio')
    const aviso = w.get('[data-aviso-gratis]')
    expect(aviso.attributes('data-chave')).toBe('gratis:contatos:100')
    expect(t(aviso.text())).toContain('Sua conta tem 140 contatos ativos.')
    expect(aviso.findAll('[data-acao-gratis]').map((b) => t(b.text()))).toEqual(['Ver contatos', 'Ver planos'])
    expect(aviso.find('button[aria-label="Fechar aviso"]').exists()).toBe(false)
    w.unmount()
    const naAssinatura = await montar(AvisoCobranca, '/assinatura')
    expect(naAssinatura.find('[data-aviso-gratis]').exists()).toBe(false)
  })

  it('sem a permissão: "Fale com o administrador da conta." e sem "Ver planos"; os e-mails do mês acabaram fecha e não volta na sessão', async () => {
    setActivePinia(createPinia())
    entrar([], resumo({ envios: { ...resumo().envios, mes: 200 } }))
    const w = await montar(AvisoCobranca, '/envios')
    expect(t(w.get('[data-aviso-gratis]').text())).toContain('Fale com o administrador da conta.')
    expect(w.findAll('[data-acao-gratis]')).toHaveLength(0)
    await w.get('[data-aviso-gratis] button[aria-label="Fechar aviso"]').trigger('click')
    expect(w.find('[data-aviso-gratis]').exists()).toBe(false)
    expect(JSON.parse(sessionStorage.getItem('toqqi.avisos-fechados')!)).toEqual(['gratis:mes:2026-11-01'])
  })

  it('AvisoPlanoGratis: o texto, "Disponível a partir do plano Essencial." e "Ver planos" (ou o administrador)', async () => {
    entrar(['assinatura.gerenciar'])
    const w = await montar(AvisoPlanoGratis, '/integracoes', { texto: 'As integrações ficam desligadas.' })
    expect(w.findAll('p').map((p) => t(p.text()))).toEqual(['Plano Grátis', 'As integrações ficam desligadas. Disponível a partir do plano Essencial.'])
    expect(t(w.get('[data-ver-planos]').text())).toBe('Ver planos')
    expect(w.get('[data-ver-planos]').attributes('href')).toBe('/assinatura')
    w.unmount()
    setActivePinia(createPinia())
    entrar([])
    const semPermissao = await montar(AvisoPlanoGratis, '/integracoes', { texto: 'Uma regra.', recurso: false })
    expect(semPermissao.findAll('p').map((p) => t(p.text()))).toEqual(['Plano Grátis', 'Uma regra. Fale com o administrador da conta.'])
    expect(semPermissao.find('[data-ver-planos]').exists()).toBe(false)
  })
})

function formulario(id: number, extra: Partial<FormularioResumo> = {}): FormularioResumo {
  return {
    id,
    nome: `Formulário ${id}`,
    descricao: null,
    tipo_principal: 'nps',
    ativo: true,
    publico: false,
    codigo_publico: `f${id}`,
    padrao_nps: id === 1,
    padrao_csat: false,
    respostas: 0,
    atualizado_em: '2026-10-01T12:00:00Z',
    ...extra,
  }
}

describe('as travas do Grátis nas telas', () => {
  it('Formulários: com 2 ativos, o aviso e "Novo formulário" desligado; "Duplicar" explica sem chamar a API', async () => {
    entrar(['formularios.editar', 'formularios.ver', 'assinatura.gerenciar'])
    const api = apiFalsa({ 'GET /formularios': () => [formulario(1), formulario(2), formulario(3, { ativo: false })] })
    const w = await abrir('/formularios', FormulariosView)
    expect(t(w.get('[data-gratis-formularios]').text())).toContain(
      'No plano Grátis, até 2 formulários recebem respostas ao mesmo tempo. Para criar ou duplicar, desative um deles, ou assine um plano a partir do Essencial.',
    )
    const novo = w.get('[data-novo-formulario]')
    expect(novo.attributes('disabled') !== undefined || novo.attributes('aria-disabled') === 'true').toBe(true)
    // Duplicar pelo menu do primeiro cartão.
    await clicar($('[aria-label="Ações para Formulário 1"]'))
    await clicar($$('[role="menuitem"]').find((b) => t(b.textContent) === 'Duplicar')!)
    expect(chamadasDe(api, 'POST', '/formularios/1/duplicar')).toHaveLength(0)
    expect(avisos.at(-1)?.mensagem).toContain('Para criar ou duplicar, desative um deles')
  })

  it('Formulários: com 3 ativos (do teste), o aviso explica que os envios novos usam só os padrão; com 1, sem aviso', async () => {
    entrar(['formularios.editar', 'formularios.ver'])
    apiFalsa({ 'GET /formularios': () => [formulario(1), formulario(2), formulario(3)] })
    const w = await abrir('/formularios', FormulariosView)
    expect(t(w.get('[data-gratis-formularios]').text())).toContain('Esta conta tem 3 ativos, vindos do teste: os links já enviados seguem valendo, mas os envios novos usam só os padrão (NPS e CSAT).')
    w.unmount()
    apiFalsa({ 'GET /formularios': () => [formulario(1), formulario(2, { ativo: false })] })
    const um = await abrir('/formularios', FormulariosView)
    expect(um.find('[data-gratis-formularios]').exists()).toBe(false)
  })

  it('Integrações: o aviso em Sistemas e em API e avisos; o WhatsApp automático faz parte do Grátis', async () => {
    entrar(['integracoes.gerenciar'])
    apiFalsa({})
    const w = await abrir('/integracoes', IntegracoesView)
    expect(t(w.get('[data-gratis-integracoes="crm"]').text())).toContain('RD Station, Omie, Bling, a chave de API e os avisos (webhooks) ficam desligados no plano Grátis.')
    await router.push('/integracoes?aba=whatsapp')
    await flushPromises()
    const whatsapp = $$('[data-gratis-integracoes]').filter((el) => el.closest<HTMLElement>('[style*="display: none"]') === null)
    expect(whatsapp).toHaveLength(0)
    await router.push('/integracoes?aba=api')
    await flushPromises()
    expect(w.find('[data-gratis-integracoes="api"]').exists()).toBe(true)
  })

  it('fora do Grátis, nenhuma trava', async () => {
    entrar(['formularios.editar', 'formularios.ver'], null)
    apiFalsa({ 'GET /formularios': () => [formulario(1), formulario(2), formulario(3)] })
    const w = await abrir('/formularios', FormulariosView)
    expect(w.find('[data-gratis-formularios]').exists()).toBe(false)
    expect(w.get('[data-novo-formulario]').attributes('disabled')).toBeUndefined()
  })
})

describe('pré-condições do Grátis', () => {
  const pre = (itens: PreCondicoes['itens']): PreCondicoes => ({ pronto: itens.every((i) => i.ok), itens })
  it('em revisão: "Os envios estão pausados" e nem WhatsApp; os itens do Grátis com os textos de resolvido', async () => {
    entrar(['assinatura.gerenciar'])
    const w = await montar(AvisoPreCondicoes, '/envios', {
      dados: pre([
        { chave: 'assinatura', ok: true, mensagem: null, acao: null },
        { chave: 'revisao', ok: false, mensagem: 'Os envios estão pausados enquanto a equipe Toqqi confere a conta.', acao: { rotulo: 'Feedback', rota: '/feedback' } },
        { chave: 'contatos_do_plano', ok: true, mensagem: null, acao: null },
        { chave: 'envios_do_mes', ok: true, mensagem: null, acao: null },
      ]),
    })
    expect(t(w.get('h2').text())).toBe('Os envios estão pausados')
    expect(t(w.text())).toContain('Nem e-mail nem WhatsApp saem enquanto a equipe Toqqi confere a conta.')
    expect(t(w.text())).toContain('Contatos ativos dentro do limite do Grátis')
    expect(t(w.text())).toContain('Envios do plano Grátis disponíveis')
  })
  it('os envios do mês acabaram: "Falta pouco…", o WhatsApp segue e o atalho "Ver planos"', async () => {
    entrar(['assinatura.gerenciar'])
    const w = await montar(AvisoPreCondicoes, '/envios', {
      dados: pre([
        { chave: 'revisao', ok: true, mensagem: null, acao: null },
        { chave: 'envios_do_mes', ok: false, mensagem: 'Os envios por e-mail deste mês acabaram (200 de 200).', acao: { rotulo: 'Ver planos', rota: '/assinatura' } },
      ]),
    })
    expect(t(w.get('h2').text())).toBe('Falta pouco para as pesquisas por e-mail começarem a sair')
    expect(t(w.text())).toContain('Enquanto isso, você já pode mandar pelo WhatsApp.')
    expect(t(w.text())).toContain('Sem revisão pendente da equipe Toqqi')
    expect(w.get('a[href="/assinatura"]').text()).toContain('Ver planos')
  })
})

const FORMULARIO_PUBLICO: FormularioPublico = {
  nome: 'Pesquisa da Sol',
  perguntas: [{ id: 'p1', tipo: 'nps', titulo: 'De 0 a 10, quanto você recomenda a Sol?', obrigatoria: true }] as FormularioPublico['perguntas'],
  tema: {} as FormularioPublico['tema'],
  mencao_toqqi: { texto: 'Pesquisa feita com Toqqi', url: 'https://toqqi.com/?utm_source=pesquisa' },
  denuncia: true,
}

describe('"Denunciar esta pesquisa" (página pública)', () => {
  it('só na pesquisa de conta Grátis e fora da prévia; escolhe o motivo, escreve e manda; depois, o obrigado no lugar do link', async () => {
    const denunciar = vi.fn(async () => 'Recebemos a sua denúncia. A equipe Toqqi vai conferir esta pesquisa.')
    const w = mount(Pesquisa, { props: { formulario: FORMULARIO_PUBLICO, denunciar }, attachTo: document.body })
    await flushPromises()
    await w.get('[data-denunciar]').trigger('click')
    const form = w.get('[data-form-denuncia]')
    expect(t(form.get('legend').text())).toBe('Por que você quer denunciar esta pesquisa?')
    expect(form.findAll('input[type="radio"]')).toHaveLength(5)
    expect(document.activeElement).toBe(form.find('input[type="radio"]').element)
    // Sem motivo: o erro, sem chamar.
    await form.trigger('submit')
    expect(t(w.get('#erro-denuncia').text())).toBe('Escolha o motivo da denúncia.')
    expect(denunciar).not.toHaveBeenCalled()
    await form.get('input[value="golpe"]').setValue(true)
    await form.get('textarea').setValue('  Pede o número do cartão.  ')
    await form.trigger('submit')
    await flushPromises()
    expect(denunciar).toHaveBeenCalledWith({ motivo: 'golpe', detalhe: 'Pede o número do cartão.' })
    expect(t(w.get('[data-denuncia-feita]').text())).toBe('Recebemos a sua denúncia. A equipe Toqqi vai conferir esta pesquisa.')
    expect(w.find('[data-denunciar]').exists()).toBe(false)
  })

  it('erro da API: a mensagem e o formulário continua; sem `denuncia` ou na prévia, nada', async () => {
    const denunciar = vi.fn(async () => {
      throw { mensagem: 'Muitas tentativas. Tente de novo em instantes.' }
    })
    const w = mount(Pesquisa, { props: { formulario: FORMULARIO_PUBLICO, denunciar }, attachTo: document.body })
    await flushPromises()
    await w.get('[data-denunciar]').trigger('click')
    await w.get('input[value="spam"]').setValue(true)
    await w.get('[data-form-denuncia]').trigger('submit')
    await flushPromises()
    expect(t(w.get('#erro-denuncia').text())).toBe('Muitas tentativas. Tente de novo em instantes.')
    expect(w.find('[data-form-denuncia]').exists()).toBe(true)
    w.unmount()
    const sem = mount(Pesquisa, { props: { formulario: { ...FORMULARIO_PUBLICO, denuncia: false }, denunciar }, attachTo: document.body })
    expect(sem.find('[data-denuncia]').exists()).toBe(false)
    sem.unmount()
    const previa = mount(Pesquisa, { props: { formulario: FORMULARIO_PUBLICO, denunciar, previa: true }, attachTo: document.body })
    expect(previa.find('[data-denuncia]').exists()).toBe(false)
  })
})

function denuncia(id: number, extra: Partial<DenunciaPlataforma> = {}): DenunciaPlataforma {
  return {
    id,
    conta: { id: 7, nome: 'Alfa Distribuidora', situacao: 'gratis' },
    formulario: { id: 3, nome: 'NPS de outubro' },
    origem: 'convite',
    motivo: 'dados_pessoais',
    detalhe: 'Pediu a senha do banco.',
    situacao: 'aberta',
    criada_em: '2026-10-13T12:00:00Z',
    resolvida_em: null,
    nota_interna: null,
    ...extra,
  }
}

describe('Plataforma › Feedback › Denúncias', () => {
  it('?denuncias=1 abre nelas; marcar procedente tira da lista de abertas e o número desce; a nota interna é salva', async () => {
    entrar([], null, { superadmin: true })
    const api = apiFalsa({
      'GET /plataforma/feedback': () => ({ itens: [], contagem: { atencao: 0, abertos: 0 } }),
      'GET /plataforma/denuncias': () => ({ itens: [denuncia(1), denuncia(2, { motivo: 'spam', detalhe: null, origem: 'link_publico' })], abertas: 2 }),
      'PATCH /plataforma/denuncias/:id': (c) => ({ ...denuncia(Number(c.caminho.split('/').pop())), ...(c.corpo as object), resolvida_em: '2026-10-13T13:00:00Z' }),
    })
    const w = await abrir('/plataforma/feedback?denuncias=1', AbaFeedback, '/plataforma/feedback')
    expect(chamadasDe(api, 'GET', '/plataforma/denuncias')[0]!.url.searchParams.get('situacao')).toBe('abertas')
    expect(w.findAll('[data-parte-feedback] label').map((l) => t(l.text()))).toEqual(['Feedbacks', 'Denúncias (2)'])
    expect(t(w.get('[data-total-denuncias]').text())).toBe('2 denúncias abertas')
    const primeira = w.get('[data-denuncia="1"]')
    expect(t(primeira.text())).toContain('Pede senha, cartão ou dados bancários')
    expect(t(primeira.text())).toContain('“Pediu a senha do banco.”')
    expect(t(primeira.text())).toContain('Formulário “NPS de outubro”')
    expect(primeira.get('a').attributes('href')).toBe('/plataforma/contas?busca=Alfa%20Distribuidora')
    await primeira.get('[data-procedente]').trigger('click')
    await flushPromises()
    expect(chamadasDe(api, 'PATCH', '/plataforma/denuncias/1')[0]!.corpo).toEqual({ situacao: 'procedente' })
    expect(w.find('[data-denuncia="1"]').exists()).toBe(false)
    expect(t(w.get('[data-total-denuncias]').text())).toBe('1 denúncia aberta')
    expect(w.findAll('[data-parte-feedback] label').map((l) => t(l.text()))[1]).toBe('Denúncias (1)')
    // Nota interna na outra.
    const segunda = w.get('[data-denuncia="2"]')
    await segunda.findAll('button').find((b) => t(b.text()) === 'Escrever uma nota')!.trigger('click')
    await segunda.get('textarea').setValue('Conferir o remetente.')
    await segunda.get('[data-salvar-nota-denuncia]').trigger('click')
    await flushPromises()
    expect(chamadasDe(api, 'PATCH', '/plataforma/denuncias/2')[0]!.corpo).toEqual({ nota_interna: 'Conferir o remetente.' })
    expect(avisos.at(-1)?.mensagem).toBe('Nota interna salva.')
  })

  it('sem o parâmetro: abre em Feedbacks e só busca o número de denúncias abertas', async () => {
    entrar([], null, { superadmin: true })
    const api = apiFalsa({
      'GET /plataforma/feedback': () => ({ itens: [], contagem: { atencao: 0, abertos: 0 } }),
      'GET /plataforma/denuncias': () => ({ itens: [], abertas: 0 }),
    })
    const w = await abrir('/plataforma/feedback', AbaFeedback)
    expect(chamadasDe(api, 'GET', '/plataforma/denuncias')).toHaveLength(1)
    expect(w.find('[data-denuncias]').exists()).toBe(false)
    expect(w.findAll('[data-parte-feedback] label').map((l) => t(l.text()))).toEqual(['Feedbacks', 'Denúncias'])
    await w.get('[data-parte-feedback] input[value="denuncias"]').setValue(true)
    await flushPromises()
    expect(t(w.get('[data-vazio-denuncias]').text())).toContain('Nenhuma denúncia aberta')
  })
})

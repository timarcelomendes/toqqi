// Risco das contas em Plataforma › Contas (docs/api-plataforma-risco.md): o texto de cada sinal, a coluna Risco (nível,
// nota e motivos; a conta da equipe sem nota), o risco embaixo do nome no celular e o filtro "Suspeitas".
import { afterEach, beforeEach, describe, expect, it } from 'vitest'
import { enableAutoUnmount, flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import type { ContaPlataforma, RiscoConta, SinalRisco } from '@/api/tipos'
import { useSessaoStore } from '@/stores/sessao'
import AbaContas from '@/modulos/plataforma/AbaContas.vue'
import { detalheSinal, suspeitas, textoSinal } from '@/modulos/plataforma/risco'
import { apiFalsa } from './apiFalsa'

const t = (s: string | null | undefined) => (s ?? '').replace(/ /g, ' ').replace(/\s+/g, ' ').trim()
/** Os textos do elemento separados por espaço (`textContent` cola os de elementos vizinhos). */
function textos(el: Element): string {
  const partes: string[] = []
  const passeio = document.createTreeWalker(el, NodeFilter.SHOW_TEXT)
  for (let n = passeio.nextNode(); n; n = passeio.nextNode()) partes.push(n.textContent ?? '')
  return t(partes.join(' '))
}
/** O texto que se vê (sem o que é só para leitor de tela). */
function visivel(el: Element): string {
  const copia = el.cloneNode(true) as Element
  copia.querySelectorAll('.sr-only').forEach((n) => n.remove())
  return textos(copia)
}

const alfa = { id: 2, nome: 'Alfa' }
const beta = { id: 3, nome: 'Beta' }
const gama = { id: 4, nome: 'Gama' }

describe('Plataforma › risco: textos', () => {
  it('cada sinal em uma linha', () => {
    const casos: [SinalRisco, string][] = [
      [{ tipo: 'email_temporario', pontos: 40, dominio: 'mailinator.com' }, 'E-mail temporário (mailinator.com)'],
      [{ tipo: 'email_pessoal', pontos: 10, dominio: 'gmail.com' }, 'E-mail pessoal (gmail.com)'],
      [{ tipo: 'email_nao_confirmado', pontos: 15, dias: 3 }, 'E-mail não confirmado há 3 dias'],
      [{ tipo: 'nome_de_teste', pontos: 15 }, 'Nome de empresa de teste'],
      [{ tipo: 'documento_repetido', pontos: 30, documento: 'cnpj', contas: [alfa], total: 1 }, 'CNPJ igual ao de Alfa'],
      [{ tipo: 'documento_repetido', pontos: 30, documento: 'cpf', contas: [alfa, beta], total: 2 }, 'CPF igual ao de 2 contas: Alfa e Beta'],
      [{ tipo: 'telefone_repetido', pontos: 20, contas: [alfa, beta, gama], total: 5 }, 'Telefone igual ao de 5 contas: Alfa, Beta, Gama e mais 2'],
      [{ tipo: 'dominio_repetido', pontos: 10, dominio: 'aurora.com.br', contas: [alfa], total: 1 }, 'Domínio aurora.com.br também em Alfa'],
      [{ tipo: 'nome_repetido', pontos: 15, contas: [alfa], total: 1 }, 'Nome igual ao de Alfa'],
      [{ tipo: 'descadastros', pontos: 35, saidas: 9, destinatarios: 150, taxa: 6 }, '6% saíram da lista (9 de 150 em 30 dias)'],
      [
        { tipo: 'invalidos', pontos: 15, invalidos: 200, tentativas: 1700, taxa: 12 },
        '12% dos envios para endereço ou número que não existe (200 de 1.700 em 30 dias)',
      ],
      [{ tipo: 'sem_respostas', pontos: 15, convites: 150, respostas: 1 }, '1 resposta em 150 pesquisas (30 dias)'],
      [{ tipo: 'sem_respostas', pontos: 15, convites: 150, respostas: 0 }, 'Nenhuma resposta em 150 pesquisas (30 dias)'],
      [{ tipo: 'volume_inicio', pontos: 10, dias: 0, envios: 520 }, 'Conta criada hoje já fez 520 envios'],
      [{ tipo: 'volume_inicio', pontos: 10, dias: 1, envios: 1520 }, 'Conta de 1 dia já fez 1.520 envios'],
      [
        { tipo: 'formulario_sensivel', pontos: 60, formulario: { id: 9, nome: 'Atualização' }, termo: 'cartao', trecho: 'Número do cartão' },
        'Formulário “Atualização” pede dados de cartão',
      ],
      [{ tipo: 'formulario_sensivel', pontos: 60, formulario: { id: 9, nome: 'X' }, termo: 'senha', trecho: 'Sua senha' }, 'Formulário “X” pede senha'],
      [{ tipo: 'estorno', pontos: 25, quantas: 1, ultima_em: '2026-09-28T15:00:00-03:00' }, 'Pagamento estornado em 28/09/2026'],
      [{ tipo: 'estorno', pontos: 25, quantas: 2, ultima_em: '2026-09-28T15:00:00-03:00' }, '2 pagamentos estornados (último em 28/09/2026)'],
    ]
    for (const [sinal, texto] of casos) expect(textoSinal(sinal)).toBe(texto)
    expect(detalheSinal({ tipo: 'formulario_sensivel', pontos: 60, formulario: { id: 9, nome: 'X' }, termo: 'senha', trecho: 'Sua senha' })).toBe('“Sua senha”')
    expect(detalheSinal({ tipo: 'nome_de_teste', pontos: 15 })).toBeNull()
  })
})

// ── A aba Contas ────────────────────────────────────────────────────────────

const risco = (pontos: number, nivel: RiscoConta['nivel'], sinais: SinalRisco[] = []): RiscoConta => ({ pontos, nivel, sinais })
function conta(c: Partial<ContaPlataforma> & Pick<ContaPlataforma, 'id' | 'nome'>): ContaPlataforma {
  return {
    plano: 'profissional',
    situacao: 'teste',
    teste_ate: '2026-10-15T14:30:00-03:00',
    usuarios: 1,
    criada_em: '2026-10-01T10:00:00Z',
    pago_ate: null,
    atrasada_desde: null,
    assinatura: null,
    admins: [],
    risco: risco(0, 'baixo'),
    ...c,
  }
}

const CONTAS: ContaPlataforma[] = [
  conta({ id: 1, nome: 'Toqqi', situacao: 'cortesia', teste_ate: null, risco: null }),
  conta({ id: 2, nome: 'Mercado Bom', risco: risco(40, 'medio', [{ tipo: 'email_temporario', pontos: 40, dominio: 'yopmail.com' }]) }),
  conta({
    id: 3,
    nome: 'asdf',
    risco: risco(70, 'alto', [
      { tipo: 'email_temporario', pontos: 40, dominio: 'mailinator.com' },
      { tipo: 'email_nao_confirmado', pontos: 15, dias: 3 },
      { tipo: 'nome_de_teste', pontos: 15 },
    ]),
  }),
  conta({ id: 4, nome: 'Padaria do João', risco: risco(10, 'baixo', [{ tipo: 'email_pessoal', pontos: 10, dominio: 'gmail.com' }]) }),
  conta({ id: 5, nome: 'Distribuidora Aurora' }),
]

function entrar() {
  const s = useSessaoStore()
  s.definirSessao(
    {
      token: 't',
      expira_em: '2099-01-01T00:00:00Z',
      usuario: { id: 1, nome: 'Marcelo', email: 'marcelo@toqqi.com', cargo: null, situacao: 'ativo', email_confirmado: true, ultimo_acesso: null, perfil: 'admin', superadmin: true },
      conta: { id: 1, nome: 'Toqqi', plano: 'profissional', situacao: 'cortesia', teste_ate: null, cobranca: { liberada: true, pago_ate: null, atrasada_desde: null, pausa_em: null, aviso: null } },
      permissoes: [] as never,
    },
    false,
  )
  s.inicializada = true
}

async function montar(contas = CONTAS): Promise<VueWrapper> {
  apiFalsa({ 'GET /plataforma/contas': () => contas })
  const w = mount(AbaContas, { attachTo: document.body, global: { stubs: { teleport: true } } })
  await flushPromises()
  return w
}

const nomes = (w: VueWrapper) => w.findAll('tbody tr').map((tr) => t(tr.find('td p').text()))
const linha = (w: VueWrapper, nome: string) => w.findAll('tbody tr').find((tr) => t(tr.find('td p').text()) === nome)!

enableAutoUnmount(afterEach)
beforeEach(() => {
  setActivePinia(createPinia())
  entrar()
})
afterEach(() => {
  document.body.innerHTML = ''
})

describe('Plataforma › risco: aba Contas', () => {
  it('coluna Risco com o nível, a nota e os motivos; a conta da equipe sem nota', async () => {
    const w = await montar()
    // a coluna Datas saiu: as datas ficam embaixo da situação
    expect(w.findAll('thead th').map((th) => t(th.text()))).toEqual(['Empresa', 'Risco', 'Situação', 'Assinatura', 'Usuários', 'Criada em', 'Ações'])
    expect(w.get('thead th:nth-child(2)').classes()).toContain('xl:table-cell')
    expect(t(linha(w, 'asdf').findAll('td')[2]!.text())).toContain('Teste até 15/10/2026')
    const alto = linha(w, 'asdf').get('[data-risco]')
    expect(visivel(alto.get('[data-nivel]').element)).toBe('Alto 70')
    expect(t(alto.get('[data-nivel]').text())).toBe('Alto 70 de 100 pontos')
    expect(alto.get('[data-nivel]').classes().join(' ')).toContain('text-erro')
    expect(alto.findAll('[data-sinal]').map((s) => visivel(s.element))).toEqual([
      '+40 E-mail temporário (mailinator.com)',
      '+15 E-mail não confirmado há 3 dias',
      '+15 Nome de empresa de teste',
    ])
    expect(t(alto.get('[data-sinal]').text())).toContain('(40 pontos)') // o "+40" é escondido do leitor de tela
    expect(visivel(linha(w, 'Mercado Bom').get('[data-nivel]').element)).toBe('Médio 40')
    // baixo: sem selo colorido; sem sinal nenhum, "Nenhum sinal"
    const baixo = linha(w, 'Padaria do João').get('[data-risco]')
    expect(baixo.get('[data-nivel]').element.tagName).toBe('P')
    expect(visivel(baixo.get('[data-nivel]').element)).toBe('Baixo 10')
    expect(visivel(baixo.get('[data-sinal]').element)).toBe('+10 E-mail pessoal (gmail.com)')
    expect(visivel(linha(w, 'Distribuidora Aurora').get('[data-nivel]').element)).toBe('Nenhum sinal')
    const equipe = linha(w, 'Toqqi')
    expect(equipe.find('[data-risco]').exists()).toBe(false)
    expect(t(equipe.findAll('td')[1]!.text())).toBe('—Conta da equipe, sem nota')
  })

  it('até 1280 px (sem a coluna), o risco médio ou alto aparece embaixo do nome', async () => {
    const w = await montar()
    const celular = linha(w, 'asdf').get('[data-risco-celular]')
    expect(celular.classes()).toContain('xl:hidden')
    expect(textos(celular.element)).toBe('Risco alto 70 E-mail temporário (mailinator.com) E-mail não confirmado há 3 dias Nome de empresa de teste')
    expect(textos(linha(w, 'Mercado Bom').get('[data-risco-celular]').element)).toBe('Risco médio 40 E-mail temporário (yopmail.com)')
    for (const nome of ['Padaria do João', 'Distribuidora Aurora', 'Toqqi']) expect(linha(w, nome).find('[data-risco-celular]').exists()).toBe(false)
  })

  it('"Suspeitas" mostra só as de risco médio ou alto, da maior nota para a menor, e combina com a busca', async () => {
    const w = await montar()
    const filtro = w.get('[data-filtro-suspeitas]')
    expect(t(filtro.text())).toBe('Suspeitas 2')
    expect(filtro.attributes('aria-pressed')).toBe('false')
    expect(nomes(w)).toEqual(['Toqqi', 'Mercado Bom', 'asdf', 'Padaria do João', 'Distribuidora Aurora'])
    await filtro.trigger('click')
    expect(filtro.attributes('aria-pressed')).toBe('true')
    expect(nomes(w)).toEqual(['asdf', 'Mercado Bom'])
    expect(t(w.text())).toContain('2 contas')
    await w.get('input[type="search"]').setValue('merc')
    expect(nomes(w)).toEqual(['Mercado Bom'])
    await w.get('input[type="search"]').setValue('')
    await filtro.trigger('click')
    expect(nomes(w)).toHaveLength(5)
  })

  it('sem nenhuma suspeita: "Suspeitas 0" e, ligado, o aviso de que não há nenhuma', async () => {
    const w = await montar(CONTAS.filter((c) => !c.risco || c.risco.nivel === 'baixo'))
    expect(t(w.get('[data-filtro-suspeitas]').text())).toBe('Suspeitas 0')
    await w.get('[data-filtro-suspeitas]').trigger('click')
    expect(t(w.text())).toContain('Nenhuma conta suspeita')
    expect(t(w.text())).toContain('Nenhuma conta tem risco médio ou alto agora.')
  })

  it('suspeitas(): empate na nota fica na ordem da lista', () => {
    const lista = [conta({ id: 7, nome: 'A', risco: risco(40, 'medio') }), conta({ id: 8, nome: 'B', risco: risco(65, 'alto') }), conta({ id: 9, nome: 'C', risco: risco(40, 'medio') })]
    expect(suspeitas(lista).map((c) => c.nome)).toEqual(['B', 'A', 'C'])
  })
})

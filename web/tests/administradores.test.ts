// Administradores da conta: em Equipe › Pessoas o administrador adiciona e remove administradores (quadro do topo e
// menu de cada pessoa); em Minha conta, qualquer perfil vê quem administra a conta (GET /conta/administradores).
import { afterEach, beforeEach, describe, expect, it } from 'vitest'
import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createMemoryHistory, createRouter, type Router } from 'vue-router'
import { h } from 'vue'
import { useSessaoStore } from '@/stores/sessao'
import { estadoConfirmacao, responderConfirmacao } from '@/composables/confirmacao'
import { limparPedidosAcesso } from '@/composables/pedidosAcesso'
import AbaUsuarios from '@/modulos/equipe/AbaUsuarios.vue'
import SecaoAdministradores from '@/modulos/conta/SecaoAdministradores.vue'
import { apiFalsa, type Chamada } from './apiFalsa'

function entrar(perfil: 'admin' | 'consulta', permissoes: string[]) {
  useSessaoStore().definirSessao(
    {
      token: 't',
      expira_em: '2099-01-01T00:00:00Z',
      usuario: { id: 1, nome: 'Ana', email: 'ana@alfa.com.br', cargo: null, perfil, situacao: 'ativo', email_confirmado: true, ultimo_acesso: null, superadmin: false },
      conta: { id: 1, nome: 'Alfa', plano: null, situacao: 'ativa', teste_ate: null },
      permissoes,
    } as never,
    false,
  )
}

async function roteador(): Promise<Router> {
  const router = createRouter({ history: createMemoryHistory(), routes: [{ path: '/:qualquer(.*)*', component: { render: () => h('div') } }] })
  await router.push('/equipe')
  await router.isReady()
  return router
}

const pessoa = (id: number, nome: string, perfil: string, situacao = 'ativo') => ({
  id, nome, email: `${nome.toLowerCase()}@alfa.com.br`, cargo: null, perfil, situacao, email_confirmado: true, ultimo_acesso: null, superadmin: false,
})

function equipeFalsa(lista = [
  pessoa(1, 'Ana', 'admin'),
  pessoa(2, 'Bruno', 'admin'),
  pessoa(3, 'Dora', 'admin', 'bloqueado'),
  pessoa(4, 'Gil', 'gestor'),
  pessoa(5, 'Cid', 'consulta'),
  pessoa(6, 'Nina', 'consulta', 'pendente'),
]) {
  const usuarios = lista.map((u) => ({ ...u }))
  return apiFalsa({
    'GET /equipe': () => usuarios,
    'PATCH /equipe/:id': (c: Chamada) => {
      const u = usuarios.find((x) => `/equipe/${x.id}` === c.caminho)!
      Object.assign(u, c.corpo)
      return { ...u }
    },
  })
}

async function montarEquipe(): Promise<VueWrapper> {
  const router = await roteador()
  const w = mount(AbaUsuarios, { global: { plugins: [router] }, attachTo: document.body })
  await flushPromises()
  return w
}

const quadro = (w: VueWrapper) => w.get('[data-administradores]')
const nomesNoQuadro = (w: VueWrapper) =>
  quadro(w)
    .findAll('[data-administrador]')
    .map((li) => li.get('.font-semibold').text() + (li.text().includes('(você)') ? ' (você)' : ''))

async function itensDoMenu(w: VueWrapper, nome: string): Promise<string[]> {
  await w.get(`button[aria-label="Ações para ${nome}"]`).trigger('click')
  await flushPromises()
  const menu = w.get(`button[aria-label="Ações para ${nome}"]`).element.closest('.relative')!
  const itens = [...menu.querySelectorAll('[role="menuitem"]')].map((i) => i.textContent!.trim())
  await w.get(`button[aria-label="Ações para ${nome}"]`).trigger('click')
  return itens
}

beforeEach(() => {
  setActivePinia(createPinia())
  limparPedidosAcesso()
})
afterEach(() => {
  if (estadoConfirmacao.aberto) responderConfirmacao(false)
  document.body.innerHTML = ''
})

describe('Equipe › Administradores da conta', () => {
  it('o quadro mostra os administradores ativos; você sem o botão de remover', async () => {
    entrar('admin', ['equipe.gerenciar'])
    equipeFalsa()
    const w = await montarEquipe()
    expect(nomesNoQuadro(w)).toEqual(['Ana (você)', 'Bruno'])
    const [voce, bruno] = quadro(w).findAll('[data-administrador]')
    expect(voce!.find('[data-remover-admin]').exists()).toBe(false)
    expect(bruno!.get('[data-remover-admin]').attributes('aria-label')).toBe('Remover Bruno dos administradores')
  })

  it('remover pede confirmação e deixa a pessoa como Gestor', async () => {
    entrar('admin', ['equipe.gerenciar'])
    const api = equipeFalsa()
    const w = await montarEquipe()
    await quadro(w).get('[data-remover-admin]').trigger('click')
    expect(estadoConfirmacao.aberto).toBe(true)
    expect(estadoConfirmacao.titulo).toBe('Remover Bruno dos administradores?')
    expect(estadoConfirmacao.perigo).toBe(true)
    responderConfirmacao(true)
    await flushPromises()
    const patch = api.chamadas.find((c) => c.metodo === 'PATCH')!
    expect(patch.caminho).toBe('/equipe/2')
    expect(patch.corpo).toEqual({ perfil: 'gestor' })
    expect(nomesNoQuadro(w)).toEqual(['Ana (você)'])
  })

  it('cancelar a remoção não chama a API', async () => {
    entrar('admin', ['equipe.gerenciar'])
    const api = equipeFalsa()
    const w = await montarEquipe()
    await quadro(w).get('[data-remover-admin]').trigger('click')
    responderConfirmacao(false)
    await flushPromises()
    expect(api.chamadas.filter((c) => c.metodo === 'PATCH')).toHaveLength(0)
  })

  it('"Adicionar administrador" lista só quem está ativo e ainda não administra; escolher torna administrador', async () => {
    entrar('admin', ['equipe.gerenciar'])
    const api = equipeFalsa()
    const w = await montarEquipe()
    await quadro(w).get('[data-adicionar-admin]').trigger('click')
    await flushPromises()
    const candidatos = [...document.body.querySelectorAll('[data-candidato-admin]')]
    const texto = (c: Element, seletor: string) => c.querySelector(seletor)!.textContent!.trim()
    expect(candidatos.map((c) => `${texto(c, '.font-semibold')} | ${texto(c, '.text-texto-fraco')}`)).toEqual([
      'Cid | cid@alfa.com.br · hoje Consulta',
      'Gil | gil@alfa.com.br · hoje Gestor',
    ])
    const dialogo = document.body.querySelector('[role="dialog"]')!
    const tornar = [...dialogo.querySelectorAll('button')].find((b) => b.textContent!.trim() === 'Tornar administrador')!
    expect(tornar.disabled).toBe(true) // ninguém escolhido ainda
    ;(candidatos[1]!.querySelector('input') as HTMLInputElement).click()
    await flushPromises()
    expect(tornar.disabled).toBe(false)
    tornar.click()
    await flushPromises()
    const patch = api.chamadas.find((c) => c.metodo === 'PATCH')!
    expect(patch.caminho).toBe('/equipe/4')
    expect(patch.corpo).toEqual({ perfil: 'admin' })
    expect(nomesNoQuadro(w)).toEqual(['Ana (você)', 'Bruno', 'Gil'])
  })

  it('sem ninguém para escolher, o botão abre o Novo usuário já com o perfil Administrador', async () => {
    entrar('admin', ['equipe.gerenciar'])
    equipeFalsa([pessoa(1, 'Ana', 'admin'), pessoa(6, 'Nina', 'consulta', 'pendente')])
    const w = await montarEquipe()
    await quadro(w).get('[data-adicionar-admin]').trigger('click')
    await flushPromises()
    expect(document.body.querySelector('[data-sem-candidatos]')!.textContent).toContain('crie um novo usuário')
    const dialogo = document.body.querySelector('[role="dialog"]')!
    const novo = [...dialogo.querySelectorAll('button')].find((b) => b.textContent!.trim() === 'Novo usuário')!
    novo.click()
    await flushPromises()
    const marcado = document.body.querySelector<HTMLInputElement>('input[name="perfil"]:checked')!
    expect(marcado.value).toBe('admin')
    expect(document.body.textContent).toContain('Criar usuário')
  })

  it('menu de cada pessoa: Tornar administrador para quem está ativo; Remover para administradores; nada para você e pedidos', async () => {
    entrar('admin', ['equipe.gerenciar'])
    const api = equipeFalsa()
    const w = await montarEquipe()
    expect(await itensDoMenu(w, 'Gil')).toContain('Tornar administrador')
    expect(await itensDoMenu(w, 'Bruno')).toContain('Remover dos administradores')
    expect(await itensDoMenu(w, 'Dora')).toContain('Remover dos administradores') // bloqueada, ainda com perfil admin
    for (const nome of ['Ana', 'Nina']) {
      const itens = await itensDoMenu(w, nome)
      expect(itens).not.toContain('Tornar administrador')
      expect(itens).not.toContain('Remover dos administradores')
    }
    // pelo menu, também pede confirmação
    await w.get('button[aria-label="Ações para Gil"]').trigger('click')
    const menu = w.get('button[aria-label="Ações para Gil"]').element.closest('.relative')!
    ;([...menu.querySelectorAll('[role="menuitem"]')].find((i) => i.textContent!.includes('Tornar administrador')) as HTMLElement).click()
    await flushPromises()
    expect(estadoConfirmacao.titulo).toBe('Dar acesso de administrador a Gil?')
    responderConfirmacao(true)
    await flushPromises()
    expect(api.chamadas.find((c) => c.metodo === 'PATCH')!.corpo).toEqual({ perfil: 'admin' })
  })

  it('erro da API (ex.: último administrador) vira aviso e a lista fica como estava', async () => {
    entrar('admin', ['equipe.gerenciar'])
    apiFalsa({
      'GET /equipe': () => [pessoa(1, 'Ana', 'admin'), pessoa(2, 'Bruno', 'admin')],
      'PATCH /equipe/:id': () =>
        new Response(JSON.stringify({ erro: { codigo: 'ultimo_admin', mensagem: 'A conta precisa de pelo menos um administrador ativo.' } }), { status: 409 }),
    })
    const w = await montarEquipe()
    await quadro(w).get('[data-remover-admin]').trigger('click')
    responderConfirmacao(true)
    await flushPromises()
    expect(nomesNoQuadro(w)).toEqual(['Ana (você)', 'Bruno'])
  })

  it('só com os pedidos (?pedidos=1) o quadro some', async () => {
    entrar('admin', ['equipe.gerenciar'])
    equipeFalsa()
    const router = createRouter({ history: createMemoryHistory(), routes: [{ path: '/:qualquer(.*)*', component: { render: () => h('div') } }] })
    await router.push('/equipe?pedidos=1')
    await router.isReady()
    const w = mount(AbaUsuarios, { global: { plugins: [router] }, attachTo: document.body })
    await flushPromises()
    expect(w.find('[data-administradores]').exists()).toBe(false)
  })
})

describe('Minha conta › Administradores da conta', () => {
  const ADMINS = [
    { id: 1, nome: 'Ana Souza', email: 'ana@alfa.com.br', cargo: 'Diretora', voce: false },
    { id: 2, nome: 'Bruno Lima', email: 'bruno@alfa.com.br', cargo: null, voce: false },
  ]

  async function montarSecao(): Promise<VueWrapper> {
    const router = await roteador()
    const w = mount(SecaoAdministradores, { global: { plugins: [router] }, attachTo: document.body })
    await flushPromises()
    return w
  }

  it('quem não é administrador vê nomes, cargos e e-mails (para escrever) e a quem pedir', async () => {
    entrar('consulta', ['painel.ver'])
    const api = apiFalsa({ 'GET /conta/administradores': () => ADMINS })
    const w = await montarSecao()
    expect(api.chamadas.map((c) => `${c.metodo} ${c.caminho}`)).toEqual(['GET /conta/administradores'])
    expect(w.text()).toContain('Fale com um deles para mudar seu perfil, pedir mais permissões')
    const itens = w.findAll('[data-admin-conta]')
    expect(itens.map((i) => i.findAll('p, a').map((e) => e.text()))).toEqual([
      ['Ana Souza', 'Diretora', 'ana@alfa.com.br'],
      ['Bruno Lima', 'bruno@alfa.com.br'],
    ])
    expect(itens[0]!.get('a').attributes('href')).toBe('mailto:ana@alfa.com.br')
    expect(w.find('[data-ir-equipe]').exists()).toBe(false)
  })

  it('o administrador se vê marcado e tem o atalho para Equipe', async () => {
    entrar('admin', ['equipe.gerenciar'])
    apiFalsa({ 'GET /conta/administradores': () => [{ ...ADMINS[0], voce: true }, ADMINS[1]] })
    const w = await montarSecao()
    expect(w.text()).toContain('Você é um deles.')
    const [voce] = w.findAll('[data-admin-conta]')
    expect(voce!.text()).toContain('(você)')
    expect(voce!.find('a').exists()).toBe(false) // o próprio e-mail não vira link
    expect(w.get('[data-ir-equipe]').attributes('href')).toBe('/equipe')
  })

  it('falhou: mostra o erro e tenta de novo', async () => {
    entrar('consulta', ['painel.ver'])
    let falhar = true
    apiFalsa({
      'GET /conta/administradores': () =>
        falhar ? new Response(JSON.stringify({ erro: { codigo: 'x', mensagem: 'Não deu para carregar.' } }), { status: 500 }) : ADMINS,
    })
    const w = await montarSecao()
    expect(w.text()).toContain('Tentar de novo')
    falhar = false
    await w.findAll('button').find((b) => b.text() === 'Tentar de novo')!.trigger('click')
    await flushPromises()
    expect(w.findAll('[data-admin-conta]')).toHaveLength(2)
  })
})

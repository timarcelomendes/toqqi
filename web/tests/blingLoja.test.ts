// Loja do Bling: o código da instalação guardado por 24 h, a página /conectar/bling (entrar ou criar conta, ligar sozinho
// para o administrador, aviso para quem não é administrador, falha vinda do Bling) e o teste de homologação na Plataforma.
import { afterEach, beforeEach, describe, expect, it } from 'vitest'
import { enableAutoUnmount, flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createMemoryHistory, createRouter } from 'vue-router'
import { defineComponent, h } from 'vue'
import { avisos } from '@/composables/avisos'
import { useSessaoStore } from '@/stores/sessao'
import ConectarBlingView from '@/modulos/integracoes/ConectarBlingView.vue'
import HomologacaoBling from '@/modulos/plataforma/HomologacaoBling.vue'
import { esquecerInstalacao, guardarInstalacao, instalacaoGuardada } from '@/modulos/integracoes/instalacaoBling'
import { apiFalsa } from './apiFalsa'

const CODIGO = 'inst_0123456789abcdefghijklmnop'
const Vazio = defineComponent({ render: () => h('div') })

enableAutoUnmount(afterEach)
beforeEach(() => {
  setActivePinia(createPinia())
  avisos.splice(0)
  localStorage.clear()
})
afterEach(() => {
  document.body.innerHTML = ''
})

function logar(perfil: 'admin' | 'gestor') {
  const sessao = useSessaoStore()
  sessao.definirSessao({ token: 't', usuario: { id: 1, nome: 'Ana', email: 'ana@x.com', perfil }, conta: { id: 1, nome: 'Alfa' }, permissoes: [] } as never, false)
}

async function abrir(query: Record<string, string> = {}) {
  const router = createRouter({ history: createMemoryHistory(), routes: [{ path: '/:p(.*)*', component: Vazio }] })
  await router.push({ path: '/conectar/bling', query })
  const w = mount(ConectarBlingView, { attachTo: document.body, global: { plugins: [router] } })
  await flushPromises()
  return { w, router }
}

describe('código da instalação guardado no navegador', () => {
  it('vale 24 horas e some ao esquecer', () => {
    guardarInstalacao(CODIGO, 1_000)
    expect(instalacaoGuardada(1_000 + 23 * 3600_000)).toBe(CODIGO)
    expect(instalacaoGuardada(1_000 + 24 * 3600_000 + 1)).toBeNull()
    expect(localStorage.length).toBe(0) // vencido: apagado
    guardarInstalacao(CODIGO)
    esquecerInstalacao()
    expect(instalacaoGuardada()).toBeNull()
  })
})

describe('/conectar/bling', () => {
  it('sem sessão: guarda o código, tira do endereço e oferece criar conta ou entrar (voltando para cá)', async () => {
    const { w, router } = await abrir({ instalacao: CODIGO })
    expect(router.currentRoute.value.fullPath).toBe('/conectar/bling')
    expect(instalacaoGuardada()).toBe(CODIGO)
    expect(w.find('[data-situacao="entrar"]').exists()).toBe(true)
    expect(w.get('[data-criar-conta]').attributes('href')).toBe('/cadastro?voltar=/conectar/bling')
    expect(w.get('[data-entrar]').attributes('href')).toBe('/entrar?voltar=/conectar/bling')
  })

  it('administrador: liga sozinho com o código guardado, esquece e vai para Integrações', async () => {
    guardarInstalacao(CODIGO)
    logar('admin')
    const { chamadas } = apiFalsa({ 'POST /integracoes/conectores/bling/instalacao': () => ({ conectado: true }) })
    const { router } = await abrir()
    expect(chamadas.map((c) => [c.caminho, c.corpo])).toEqual([['/integracoes/conectores/bling/instalacao', { instalacao: CODIGO }]])
    expect(instalacaoGuardada()).toBeNull()
    expect(router.currentRoute.value.fullPath).toBe('/integracoes?aba=crm&conector=bling')
    expect(avisos.at(-1)?.tipo).toBe('sucesso')
  })

  it('empresa do Bling em outra conta: mostra o motivo e deixa tentar de novo', async () => {
    guardarInstalacao(CODIGO)
    logar('admin')
    apiFalsa({
      'POST /integracoes/conectores/bling/instalacao': () =>
        new Response(JSON.stringify({ erro: { codigo: 'bling_em_outra_conta', mensagem: 'Esta empresa do Bling já está conectada a outra conta do Toqqi.' } }), { status: 409 }),
    })
    const { w } = await abrir()
    expect(w.get('[data-situacao="erro"]').text()).toContain('já está conectada a outra conta')
    expect(instalacaoGuardada()).toBe(CODIGO) // pode entrar com a conta certa e tentar de novo
  })

  it('quem não é administrador vê o aviso, sem chamar a API', async () => {
    guardarInstalacao(CODIGO)
    logar('gestor')
    const { chamadas } = apiFalsa({})
    const { w } = await abrir()
    expect(w.find('[data-situacao="nao_admin"]').exists()).toBe(true)
    expect(chamadas).toHaveLength(0)
  })

  it('falha vinda do Bling e página sem instalação', async () => {
    const { w } = await abrir({ resultado: 'negado' })
    expect(w.get('[data-situacao="falhou"]').text()).toContain('A autorização no Bling foi cancelada.')
    const { w: w2 } = await abrir()
    expect(w2.find('[data-situacao="sem_instalacao"]').exists()).toBe(true)
    expect(w2.get('a[href="/bling"]').text()).toBe('Como funciona')
  })
})

describe('Plataforma › Homologação do Bling', () => {
  it('roda o teste e mostra os passos, com o intervalo acima de 2 s em destaque', async () => {
    apiFalsa({
      'POST /plataforma/bling/homologacao': () => ({
        ok: false, erro: '3. Alterar o nome para Copo: o Bling respondeu 400.', total_ms: 4200,
        passos: [
          { passo: '1. Buscar o produto', metodo: 'GET', status: 200, ms: 300, intervalo_ms: null, renovou: false },
          { passo: '2. Criar o produto', metodo: 'POST', status: 201, ms: 400, intervalo_ms: 10, renovou: false },
          { passo: '3. Alterar o nome para Copo', metodo: 'PUT', status: 400, ms: 300, intervalo_ms: 2500, renovou: true },
        ],
      }),
    })
    const w = mount(HomologacaoBling, { attachTo: document.body })
    await w.get('[data-rodar-homologacao]').trigger('click')
    await flushPromises()
    expect(w.get('[data-resultado-homologacao]').text()).toBe('3. Alterar o nome para Copo: o Bling respondeu 400.')
    const linhas = w.findAll('tbody tr')
    expect(linhas).toHaveLength(3)
    expect(linhas[2]!.text()).toContain('token renovado')
    expect(linhas[2]!.findAll('td')[3]!.classes()).toContain('text-erro')
    expect(linhas[2]!.findAll('td')[3]!.text()).toBe('2,50 s')
  })
})

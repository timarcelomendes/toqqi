// Versão nova do site no ar (utils/atualizacao.ts): /versao.json conferido ao trocar de tela e quando a aba volta, no
// máximo uma vez por minuto; o aviso com "Atualizar a página"; a próxima troca de tela do app logado carrega a página
// inteira (uma vez por versão em cada aba); a tela cujo arquivo sumiu; e nada fora do Render ("local").
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { nextTick } from 'vue'
import { createMemoryHistory, createRouter, type Router } from 'vue-router'
import Avisos from '@/components/ui/Avisos.vue'
import { avisar, avisos, fecharAviso } from '@/composables/avisos'
import {
  CHAVE_RECARGA,
  INTERVALO,
  MENSAGEM_AVISO,
  TITULO_AVISO,
  criarAtualizacao,
  falhaDeArquivo,
  instalarAtualizacao,
  lerVersao,
} from '@/utils/atualizacao'

const Vazio = { template: '<div />' }

function memoria(): Storage {
  const m = new Map<string, string>()
  return {
    getItem: (k) => m.get(k) ?? null,
    setItem: (k, v) => void m.set(k, String(v)),
    removeItem: (k) => void m.delete(k),
    clear: () => m.clear(),
    key: (i) => [...m.keys()][i] ?? null,
    get length() {
      return m.size
    },
  }
}

function montarRouter(falhar?: () => Promise<never>): Router {
  return createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/entrar', component: Vazio, meta: { visitante: true } },
      { path: '/cadastro', component: Vazio, meta: { visitante: true } },
      {
        path: '/',
        component: Vazio,
        meta: { logado: true },
        children: [
          { path: 'inicio', component: Vazio },
          { path: 'respostas', component: Vazio },
          { path: 'plataforma/:aba(contas|erros)?', component: Vazio },
          { path: 'quebrada', component: falhar ?? (() => Promise.resolve(Vazio)) },
        ],
      },
    ],
  })
}

let relogio = 1_000_000
let versaoNoAr: unknown = { versao: 'b222222' }
let buscas: string[] = []
const buscar = async (url: string) => {
  buscas.push(url)
  if (versaoNoAr instanceof Error) throw versaoNoAr
  return versaoNoAr
}

beforeEach(() => {
  relogio = 1_000_000
  versaoNoAr = { versao: 'b222222' }
  buscas = []
  for (const a of [...avisos]) fecharAviso(a.id)
})
afterEach(() => {
  for (const a of [...avisos]) fecharAviso(a.id)
})

const esperar = () => new Promise((r) => setTimeout(r, 0))

describe('atualização: leitura', () => {
  it('lerVersao aceita só {versao} curta e limpa', () => {
    expect(lerVersao({ versao: 'a995ab2' })).toBe('a995ab2')
    expect(lerVersao({ versao: '' })).toBeNull()
    expect(lerVersao({ versao: 'x y' })).toBeNull()
    expect(lerVersao({ versao: 'a'.repeat(41) })).toBeNull()
    expect(lerVersao({ outra: 'a995ab2' })).toBeNull()
    expect(lerVersao('<!doctype html>')).toBeNull()
    expect(lerVersao(null)).toBeNull()
  })

  it('falhaDeArquivo reconhece o arquivo de tela que não carregou (Chrome, Firefox, Safari), não outros erros', () => {
    expect(falhaDeArquivo(new TypeError('Failed to fetch dynamically imported module: https://toqqi.com/assets/X-abc.js'))).toBe(true)
    expect(falhaDeArquivo(new TypeError('error loading dynamically imported module'))).toBe(true)
    expect(falhaDeArquivo(new TypeError('Importing a module script failed.'))).toBe(true)
    expect(falhaDeArquivo(new Error('Unable to preload CSS for /assets/x.css'))).toBe(true)
    expect(falhaDeArquivo(new Error('Cannot read properties of undefined'))).toBe(false)
    expect(falhaDeArquivo({ message: 'Failed to fetch dynamically imported module' })).toBe(false)
  })
})

describe('atualização: conferir', () => {
  it('versão nova: devolve a versão e mostra o aviso uma vez, com "Atualizar a página"', async () => {
    const recarregar = vi.fn()
    const a = criarAtualizacao({ versaoAtual: 'a111111', buscar, agora: () => relogio, recarregar, armazenamento: memoria() })
    expect(await a.conferir()).toBe('b222222')
    expect(a.nova).toBe('b222222')
    expect(buscas).toEqual([`/versao.json?t=${relogio}`])
    expect(avisos).toHaveLength(1)
    expect(avisos[0]).toMatchObject({ tipo: 'info', titulo: TITULO_AVISO, mensagem: MENSAGEM_AVISO, duracao: 0 })
    expect(avisos[0]!.acao!.rotulo).toBe('Atualizar a página')
    avisos[0]!.acao!.executar()
    expect(recarregar).toHaveBeenCalledOnce()
    // a mesma versão de novo (depois do intervalo): não repete o aviso
    fecharAviso(avisos[0]!.id)
    relogio += INTERVALO
    expect(await a.conferir()).toBe('b222222')
    expect(buscas).toHaveLength(2)
    expect(avisos).toHaveLength(0)
    // outra versão nova: aviso de novo
    versaoNoAr = { versao: 'c333333' }
    relogio += INTERVALO
    expect(await a.conferir()).toBe('c333333')
    expect(avisos).toHaveLength(1)
  })

  it('mesma versão, arquivo estranho ou sem internet: nada', async () => {
    const a = criarAtualizacao({ versaoAtual: 'b222222', buscar, agora: () => relogio, armazenamento: memoria() })
    expect(await a.conferir()).toBeNull()
    versaoNoAr = '<!doctype html>'
    expect(await a.conferir(true)).toBeNull()
    versaoNoAr = new TypeError('Failed to fetch')
    expect(await a.conferir(true)).toBeNull()
    expect(avisos).toHaveLength(0)
  })

  it('no máximo uma consulta por minuto (salvo forçada) e uma de cada vez', async () => {
    const a = criarAtualizacao({ versaoAtual: 'b222222', buscar, agora: () => relogio, armazenamento: memoria() })
    await a.conferir()
    relogio += INTERVALO - 1
    await a.conferir()
    expect(buscas).toHaveLength(1)
    await a.conferir(true)
    expect(buscas).toHaveLength(2)
    relogio += INTERVALO
    await Promise.all([a.conferir(), a.conferir(true)])
    expect(buscas).toHaveLength(3)
  })

  it('fora do Render ("local") não consulta nada', async () => {
    const a = criarAtualizacao({ versaoAtual: 'local', buscar, agora: () => relogio })
    expect(await a.conferir(true)).toBeNull()
    expect(buscas).toHaveLength(0)
  })

  it('podeRecarregar: uma vez por versão em cada aba', () => {
    const armazenamento = memoria()
    const a = criarAtualizacao({ versaoAtual: 'a111111', buscar, armazenamento })
    expect(a.podeRecarregar('b222222')).toBe(true)
    expect(armazenamento.getItem(CHAVE_RECARGA)).toBe('b222222')
    expect(a.podeRecarregar('b222222')).toBe(false)
    expect(a.podeRecarregar('c333333')).toBe(true)
    // sem sessionStorage: recarrega (o aviso segura o resto)
    expect(criarAtualizacao({ versaoAtual: 'a111111', buscar, armazenamento: null }).podeRecarregar('b222222')).toBe(true)
  })
})

describe('atualização: no router e na aba', () => {
  function instalar(router: Router, armazenamento = memoria()) {
    const irPara = vi.fn()
    const documento = document.implementation.createHTMLDocument('x')
    let visivel: DocumentVisibilityState = 'visible'
    Object.defineProperty(documento, 'visibilityState', { get: () => visivel })
    const a = instalarAtualizacao(router, { versaoAtual: 'a111111', buscar, agora: () => relogio, irPara, armazenamento, documento })
    return {
      a,
      irPara,
      aba: (estado: DocumentVisibilityState) => {
        visivel = estado
        documento.dispatchEvent(new Event('visibilitychange'))
      },
    }
  }

  it('confere depois de trocar de caminho; a próxima troca de tela carrega a página inteira no destino, uma vez', async () => {
    const router = montarRouter()
    const armazenamento = memoria()
    const { a, irPara } = instalar(router, armazenamento)
    await router.push('/inicio') // primeira navegação: não confere nem recarrega
    expect(buscas).toHaveLength(0)
    await router.push('/respostas')
    await esperar()
    expect(buscas).toHaveLength(1)
    expect(a.nova).toBe('b222222')
    expect(router.currentRoute.value.path).toBe('/respostas')
    // filtros na mesma tela: troca normal
    await router.push('/respostas?nota=detratores')
    expect(irPara).not.toHaveBeenCalled()
    expect(router.currentRoute.value.fullPath).toBe('/respostas?nota=detratores')
    // outra tela: carrega a página inteira no destino e a troca normal não acontece
    await router.push('/plataforma/contas?busca=x')
    expect(irPara).toHaveBeenCalledWith('/plataforma/contas?busca=x')
    expect(router.currentRoute.value.path).toBe('/respostas')
    expect(armazenamento.getItem(CHAVE_RECARGA)).toBe('b222222')
    // se a página voltou na versão velha (index.html em cache), não tenta de novo: fica o aviso
    await router.push('/inicio')
    expect(irPara).toHaveBeenCalledOnce()
    expect(router.currentRoute.value.path).toBe('/inicio')
  })

  it('telas de visitante (entrar, cadastro) ficam de fora: o "Falta pouco" do Google mora na memória', async () => {
    const router = montarRouter()
    const { a, irPara } = instalar(router)
    await router.push('/entrar')
    await a.conferir(true)
    expect(a.nova).toBe('b222222')
    await router.push('/cadastro')
    await router.push('/inicio')
    expect(irPara).not.toHaveBeenCalled()
    expect(router.currentRoute.value.path).toBe('/inicio')
  })

  it('aba que volta a ficar visível confere (respeitando o minuto) e mostra o aviso', async () => {
    const router = montarRouter()
    const { aba } = instalar(router)
    await router.push('/plataforma/contas')
    aba('hidden')
    await esperar()
    expect(buscas).toHaveLength(0)
    aba('visible')
    await esperar()
    expect(buscas).toHaveLength(1)
    expect(avisos.map((x) => x.titulo)).toEqual([TITULO_AVISO])
    aba('hidden')
    aba('visible')
    await esperar()
    expect(buscas).toHaveLength(1)
  })

  it('arquivo de tela que sumiu: confere na hora e abre o destino carregando a página inteira', async () => {
    const router = montarRouter(() => Promise.reject(new TypeError('Failed to fetch dynamically imported module: https://toqqi.com/assets/Q-1.js')))
    const { irPara } = instalar(router)
    await router.push('/inicio')
    await router.push('/quebrada?x=1').catch(() => {})
    await esperar()
    expect(buscas).toHaveLength(1)
    expect(irPara).toHaveBeenCalledWith('/quebrada?x=1')
  })

  it('arquivo de tela que sumiu, mas a versão é a mesma (falha de rede): não recarrega', async () => {
    versaoNoAr = { versao: 'a111111' }
    const router = montarRouter(() => Promise.reject(new TypeError('Failed to fetch dynamically imported module: x')))
    const { irPara } = instalar(router)
    await router.push('/inicio')
    await router.push('/quebrada').catch(() => {})
    await esperar()
    expect(irPara).not.toHaveBeenCalled()
  })
})

describe('aviso com botão', () => {
  it('"Atualizar a página" no aviso: faz a ação e fecha o aviso; aviso sem ação não tem botão', async () => {
    const w = mount(Avisos, { global: { stubs: { TransitionGroup: false } } })
    const executar = vi.fn()
    avisar({ tipo: 'info', titulo: TITULO_AVISO, mensagem: MENSAGEM_AVISO, duracao: 0, acao: { rotulo: 'Atualizar a página', executar } })
    avisar.sucesso('Salvo.')
    await nextTick()
    const botoes = w.findAll('[data-acao-aviso]')
    expect(botoes).toHaveLength(1)
    expect(botoes[0]!.text()).toBe('Atualizar a página')
    expect(botoes[0]!.attributes('type')).toBe('button')
    await botoes[0]!.trigger('click')
    expect(executar).toHaveBeenCalledOnce()
    expect(avisos.map((a) => a.mensagem)).toEqual(['Salvo.'])
    w.unmount()
  })
})

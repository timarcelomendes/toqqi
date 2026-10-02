import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { CONVERSA, formatarReais, proximoPasso, temSessao, valorContador } from '@/site/logica'
import { ehSite } from '@/site/rota'

const html = readFileSync(resolve(__dirname, '../index.html'), 'utf8')
const corpo = html.slice(html.indexOf('<body>') + 6, html.indexOf('</body>'))

describe('rota do site', () => {
  it('só a raiz é o site; o resto é o app', () => {
    expect(ehSite('/')).toBe(true)
    expect(ehSite('/index.html')).toBe(true)
    for (const p of ['/entrar', '/inicio', '/cadastro', '/termos', '/r/abc', '//', '/a']) {
      expect(ehSite(p)).toBe(false)
    }
  })
})

describe('lógica do site', () => {
  it('formata reais com centavos', () => {
    expect(formatarReais(262399.99)).toBe('R$ 262.399,99')
    expect(formatarReais(0)).toBe('R$ 0,00')
  })
  it('passos giram de 1 a 4', () => {
    expect([1, 2, 3, 4].map((n) => proximoPasso(n))).toEqual([2, 3, 4, 1])
  })
  it('contador começa em 0 e termina exatamente no valor', () => {
    expect(valorContador(262399.99, 0)).toBe(0)
    expect(valorContador(262399.99, 1)).toBe(262399.99)
    const meio = valorContador(262399.99, 0.5)
    expect(meio).toBeGreaterThan(131200)
    expect(meio).toBeLessThan(262399.99)
  })
  it('reconhece a sessão guardada pelo app, sem contar a vencida', () => {
    const agora = Date.parse('2026-10-02T12:00:00Z')
    expect(temSessao(null, agora)).toBe(false)
    expect(temSessao('{', agora)).toBe(false)
    expect(temSessao('{"token":""}', agora)).toBe(false)
    expect(temSessao('{"token":"abc","expira_em":null}', agora)).toBe(true)
    expect(temSessao('{"token":"abc","expira_em":"2026-10-03T00:00:00Z"}', agora)).toBe(true)
    expect(temSessao('{"token":"abc","expira_em":"2026-10-01T00:00:00Z"}', agora)).toBe(false)
  })
})

describe('index.html', () => {
  it('leva às telas do app e não sobra marcador de rascunho', () => {
    expect(corpo).toContain('href="/cadastro"')
    expect(corpo).toContain('href="/entrar"')
    expect(corpo).toContain('href="/termos"')
    expect(corpo).toContain('href="/privacidade"')
    expect(corpo).not.toMatch(/\{\{|<sc-|_blob|#comecar"|\[[A-Z ÃÇ]{4,}\]|fonts\.googleapis/)
  })
  it('a conversa parada é a mesma da animação', () => {
    for (const f of CONVERSA) {
      expect(corpo).toContain(f.pergunta)
      expect(corpo).toContain(f.resposta.replace(/&/g, '&amp;'))
    }
  })
  it('preços e limites batem com os planos da API', () => {
    for (const p of ['>149<', '>349<', '>799<', '300', '1.500', '40', '90', '200', '100/mês', '500/mês', '2.000/mês']) {
      expect(corpo).toContain(p)
    }
  })
})

describe('comportamento da página', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    document.body.innerHTML = corpo.replace(/<script[\s\S]*?<\/script>/g, '')
  })
  afterEach(() => {
    vi.useRealTimers()
    vi.resetModules()
    window.localStorage.clear()
  })

  it('passos: clique troca a cena e o tempo avança sozinho', async () => {
    await import('@/site/site')
    const botoes = document.querySelectorAll<HTMLButtonElement>('[data-passo]')
    const cena = (n: number) => document.getElementById(`cena-${n}`)!
    expect(cena(1).hidden).toBe(false)
    expect(cena(2).hidden).toBe(true)
    botoes[2]!.click()
    expect(cena(3).hidden).toBe(false)
    expect(botoes[2]!.getAttribute('aria-pressed')).toBe('true')
    expect(cena(1).hidden).toBe(true)
    vi.advanceTimersByTime(5500)
    expect(cena(4).hidden).toBe(false)
    vi.advanceTimersByTime(5500)
    expect(cena(1).hidden).toBe(false)
  })

  it('comparar planos abre e fecha a tabela', async () => {
    await import('@/site/site')
    const botao = document.querySelector<HTMLButtonElement>('[data-comparar]')!
    const tabela = document.getElementById('tabela-planos')!
    expect(tabela.hidden).toBe(true)
    botao.click()
    expect(tabela.hidden).toBe(false)
    expect(botao.getAttribute('aria-expanded')).toBe('true')
    botao.click()
    expect(tabela.hidden).toBe(true)
  })

  it('quem já entrou vê "Abrir o Toqqi"', async () => {
    window.localStorage.setItem('toqqi.sessao', JSON.stringify({ token: 't', expira_em: null }))
    await import('@/site/site')
    const entrar = document.querySelector<HTMLAnchorElement>('[data-entrar]')!
    expect(entrar.textContent).toBe('Abrir o Toqqi')
    expect(entrar.getAttribute('href')).toBe('/inicio')
  })

  it('a conversa é digitada, respondida e a cota desce', async () => {
    await import('@/site/site')
    const restam = document.querySelector('[data-restam]')!
    const lista = document.querySelector('[data-msgs]')!
    await vi.advanceTimersByTimeAsync(600)
    expect(lista.children.length).toBe(0)
    expect(restam.textContent).toBe('500')
    await vi.advanceTimersByTimeAsync(20000)
    expect(lista.textContent).toContain(CONVERSA[0]!.pergunta)
    expect(lista.textContent).toContain(CONVERSA[0]!.resposta)
    expect(Number(restam.textContent)).toBeLessThan(500)
  })
})

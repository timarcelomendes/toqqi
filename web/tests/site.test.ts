import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import {
  CONVERSA,
  PADROES_SITE,
  TEMPO_PLANOS_MS,
  formatarReais,
  proximoPasso,
  restamNaConversa,
  restamParado,
  temSessao,
  textoNumeroSite,
  valorContador,
  valorPublico,
} from '@/site/logica'
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

/** Um corpo de GET /publico/planos com números diferentes dos padrões. */
const PLANOS_NOVOS = {
  planos: [
    { chave: 'essencial', nome: 'Essencial', preco: '149.90', contatos: 250, whatsapp: 35, ia_cota: 80, ia_teto: 900 },
    { chave: 'profissional', nome: 'Profissional', preco: '399.00', contatos: 2000, whatsapp: 120, ia_cota: 800, ia_teto: 6000 },
    { chave: 'empresa', nome: 'Empresa', preco: '1299.00', contatos: null, whatsapp: 250, ia_cota: 2500, ia_teto: 25000 },
  ],
  teste: { dias: 7, plano: 'essencial', whatsapp: 15, ia_teto: 800, ia_cota: 40 },
  ia_analises: { rapido: 1, equilibrado: 1, detalhado: 4 },
  descontos: { pix: 5, anual: 15 },
  personalizado: {
    base: '109.00',
    faixas: [{ ate: 1500, preco: '20.00' }, { ate: 10000, preco: '12.00' }, { ate: null, preco: '7.00' }],
    ia: [{ cota: 100, preco: '0.00' }, { cota: 500, preco: '40.00' }, { cota: 2000, preco: '150.00' }, { cota: 5000, preco: '300.00' }],
    contatos_min: 100, contatos_max: 100000, passo: 100, whatsapp: null,
  },
}

describe('números dos planos (etapa 5g)', () => {
  it('acha cada chave do §2 no corpo de /publico/planos', () => {
    expect(valorPublico(PLANOS_NOVOS, 'planos.essencial.preco')).toBe('149.90')
    expect(valorPublico(PLANOS_NOVOS, 'planos.empresa.contatos')).toBeNull()
    expect(valorPublico(PLANOS_NOVOS, 'planos.profissional.contatos')).toBe(2000)
    expect(valorPublico(PLANOS_NOVOS, 'ia.cota.profissional')).toBe(800)
    expect(valorPublico(PLANOS_NOVOS, 'ia.teto.empresa')).toBe(25000)
    expect(valorPublico(PLANOS_NOVOS, 'ia.teto.teste')).toBe(800)
    expect(valorPublico(PLANOS_NOVOS, 'whatsapp.franquia.essencial')).toBe(35)
    expect(valorPublico(PLANOS_NOVOS, 'whatsapp.franquia.teste')).toBe(15)
    expect(valorPublico(PLANOS_NOVOS, 'teste.dias')).toBe(7)
    expect(valorPublico(PLANOS_NOVOS, 'teste.plano')).toBe('essencial')
    expect(valorPublico(PLANOS_NOVOS, 'ia.analises.detalhado')).toBe(4)
    // O que não está lá (ou corpo estranho) fica undefined: o HTML não muda.
    expect(valorPublico(PLANOS_NOVOS, 'ia.cota.cortesia')).toBeUndefined()
    expect(valorPublico(PLANOS_NOVOS, 'ia.modelo.rapido')).toBeUndefined()
    expect(valorPublico({ planos: [{ chave: 'essencial' }] }, 'planos.essencial.contatos')).toBeUndefined()
    expect(valorPublico(null, 'teste.dias')).toBeUndefined()
    expect(valorPublico('erro', 'teste.dias')).toBeUndefined()
  })
  it('formata como a página: preço inteiro "149" ou "149,90", milhar com ponto, "sem limite"', () => {
    expect(textoNumeroSite('planos.essencial.preco', '149.00')).toBe('149')
    expect(textoNumeroSite('planos.essencial.preco', '149.9')).toBe('149,90')
    expect(textoNumeroSite('planos.empresa.preco', 1299)).toBe('1.299')
    expect(textoNumeroSite('planos.empresa.preco', '1299.50')).toBe('1.299,50')
    expect(textoNumeroSite('planos.profissional.contatos', 1500)).toBe('1.500')
    expect(textoNumeroSite('planos.empresa.contatos', null)).toBe('sem limite')
    expect(textoNumeroSite('planos.empresa.contatos', null, true)).toBe('Sem limite')
    expect(textoNumeroSite('ia.teto.empresa', 20000)).toBe('20.000')
    expect(textoNumeroSite('teste.dias', 7)).toBe('7')
    // Valor que não serve: null (fica o HTML).
    for (const [chave, v] of [
      ['planos.essencial.preco', 'abc'],
      ['planos.essencial.preco', ''],
      ['planos.essencial.preco', -1],
      ['teste.dias', '7'],
      ['teste.dias', 2.5],
      ['ia.cota.essencial', null],
      ['ia.cota.essencial', undefined],
    ] as const) {
      expect(textoNumeroSite(chave, v), `${chave} ${String(v)}`).toBeNull()
    }
  })
  it('"Restam" da conversa: a cota menos as respondidas (parada, as 3 do HTML), nunca negativo', () => {
    expect(restamParado(500)).toBe(497)
    expect(restamParado(800)).toBe(797)
    expect(restamParado(2)).toBe(0)
    expect(restamNaConversa(800, 1)).toBe(799)
    expect(restamNaConversa(0, 1)).toBe(0)
    expect(TEMPO_PLANOS_MS).toBe(5000)
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
  // Etapa 5g: cada número é um <span data-p="{chave}"> com o padrão do código (o site.ts troca pelo de agora).
  it('cada data-p traz o padrão do código, no formato da página', () => {
    document.body.innerHTML = corpo.replace(/<script[\s\S]*?<\/script>/g, '')
    const marcados = Array.from(document.querySelectorAll<HTMLElement>('[data-p]'))
    expect(marcados).toHaveLength(40)
    for (const el of marcados) {
      const chave = el.dataset.p!
      expect(chave in PADROES_SITE, chave).toBe(true)
      expect(el.textContent, chave).toBe(textoNumeroSite(chave, PADROES_SITE[chave], el.hasAttribute('data-p-maiuscula')))
    }
    // Todas as chaves aparecem; os seis "14 dias" e os preços nos cartões e na tabela.
    expect(new Set(marcados.map((el) => el.dataset.p))).toEqual(new Set(Object.keys(PADROES_SITE)))
    expect(marcados.filter((el) => el.dataset.p === 'teste.dias')).toHaveLength(6)
    expect(marcados.filter((el) => el.dataset.p === 'planos.essencial.preco').map((el) => el.textContent)).toEqual(['149', '149'])
    // Etapa 5k: WhatsApp sem franquia e o Empresa com 5.000 contatos
    expect(document.querySelector('[data-p="whatsapp.franquia.essencial"]')!.textContent).toBe('Sem franquia')
    expect(marcados.filter((el) => el.dataset.p === 'planos.empresa.contatos').map((el) => el.textContent)).toEqual(['5.000', '5.000'])
    document.body.innerHTML = ''
  })
  it('nos botões, o número fica dentro de um texto só (solto, ele vira item do flex e o gap abre espaço em volta)', () => {
    document.body.innerHTML = corpo.replace(/<script[\s\S]*?<\/script>/g, '')
    const botoes = Array.from(document.querySelectorAll<HTMLElement>('.btn')).filter((b) => b.querySelector('[data-p]'))
    expect(botoes.map((b) => b.textContent)).toEqual([
      'Começar 14 dias grátis',
      'Testar 14 dias grátis',
      'Testar 14 dias grátis',
      'Testar 14 dias grátis',
      'Começar 14 dias grátis',
    ])
    for (const b of botoes) {
      // Um filho só, o <span> do texto, sem texto solto ao lado; o número fica dentro dele.
      const filhos = Array.from(b.childNodes).filter((n) => n.nodeType === Node.ELEMENT_NODE || (n.textContent ?? '').trim())
      expect(filhos.map((n) => n.nodeName)).toEqual(['SPAN'])
      expect(b.querySelector(':scope > [data-p]')).toBeNull()
      expect((filhos[0] as HTMLElement).querySelector(':scope > [data-p="teste.dias"]')).not.toBeNull()
    }
    document.body.innerHTML = ''
  })
  it('sem JavaScript, os textos com os números ficam completos', () => {
    const texto = (html: string) => html.replace(/<[^>]+>/g, '')
    const so = texto(corpo)
    for (const frase of [
      'Começar 14 dias grátis',
      'Comece grátis por 14 dias',
      'Testar 14 dias grátis',
      'No teste grátis valem 50 perguntas ao ToqqiAI e até 500 comentários lidos pela IA.',
      'pague por mês (3% de desconto no Pix) ou por ano (10% de desconto)',
      'Base de R$ 99 por mês.',
      'Restam 497 de 500 perguntas no mês',
      'Contatos ativos1.500',
      '100/mês',
      '2.000/mês',
    ]) {
      expect(so).toContain(frase)
    }
  })
  it('a descrição para redes sociais não cita os dias (robô não roda script); 90/7 dias ficam', () => {
    expect(html).toContain('<meta property="og:description" content="Pesquisa de NPS e CSAT por e-mail e WhatsApp, comentários lidos por IA e planos de ação. Teste grátis, sem cartão." />')
    expect(html.slice(0, html.indexOf('<body>'))).not.toContain('14 dias')
    expect(corpo).toContain('ficam guardados por 90 dias; sem assinatura, a conta é excluída depois disso, com aviso por e-mail 7 dias antes.')
  })
  it('a nota abaixo da tabela de planos: no nível Mais detalhado, cada pergunta, resumo ou parecer conta 3 (5k)', () => {
    const tabela = corpo.indexOf('id="tabela-planos"')
    const nota = corpo.indexOf('data-nota-ia')
    expect(tabela).toBeGreaterThan(-1)
    expect(nota).toBeGreaterThan(corpo.indexOf('</table>', tabela))
    expect(corpo).toContain(
      'No nível “Mais detalhado” da IA, cada pergunta ao ToqqiAI, resumo ou parecer conta como <span data-p="ia.analises.detalhado">3</span>.',
    )
  })
})

describe('comportamento da página', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    document.body.innerHTML = corpo.replace(/<script[\s\S]*?<\/script>/g, '')
    // Sem a API (nenhum teste sai para a rede): a busca dos números falha e o HTML fica.
    vi.stubGlobal('fetch', vi.fn(async () => Promise.reject(new TypeError('sem rede'))))
  })
  afterEach(() => {
    vi.useRealTimers()
    vi.resetModules()
    vi.unstubAllGlobals()
    window.localStorage.clear()
  })

  /** Os textos de cada data-p, por chave. */
  const numeros = () => {
    const r: Record<string, string[]> = {}
    for (const el of Array.from(document.querySelectorAll<HTMLElement>('[data-p]'))) (r[el.dataset.p!] ??= []).push(el.textContent ?? '')
    return r
  }
  const antes = () => {
    const div = document.createElement('div')
    div.innerHTML = corpo.replace(/<script[\s\S]*?<\/script>/g, '')
    const r: Record<string, string[]> = {}
    for (const el of Array.from(div.querySelectorAll<HTMLElement>('[data-p]'))) (r[el.dataset.p!] ??= []).push(el.textContent ?? '')
    return r
  }

  it('depois de abrir, busca /publico/planos (só a API do Toqqi, sem login) e troca todos os números', async () => {
    const fetch = vi.fn(async (_url: string | URL, _init?: RequestInit) => new Response(JSON.stringify(PLANOS_NOVOS), { status: 200 }))
    vi.stubGlobal('fetch', fetch)
    await import('@/site/site')
    await vi.advanceTimersByTimeAsync(10)
    expect(fetch).toHaveBeenCalledTimes(1)
    const url = new URL(String(fetch.mock.calls[0]![0]))
    expect(url.pathname).toBe('/api/v1/publico/planos')
    expect(new Headers(fetch.mock.calls[0]![1]?.headers).has('Authorization')).toBe(false)
    const n = numeros()
    expect(n['teste.dias']).toEqual(['7', '7', '7', '7', '7', '7'])
    expect(n['planos.essencial.preco']).toEqual(['149,90', '149,90'])
    expect(n['planos.profissional.preco']).toEqual(['399', '399'])
    expect(n['planos.empresa.preco']).toEqual(['1.299', '1.299'])
    expect(n['planos.essencial.contatos']).toEqual(['250', '250'])
    expect(n['planos.profissional.contatos']).toEqual(['2.000', '2.000'])
    expect(n['planos.empresa.contatos']).toEqual(['sem limite', 'Sem limite'])
    expect(n['planos.desconto.pix']).toEqual(['5'])
    expect(n['planos.desconto.anual']).toEqual(['15'])
    expect(n['planos.personalizado.base']).toEqual(['109'])
    // a calculadora segue a tabela de agora: 5.000 contatos e 2.000 perguntas = 109 + 15×20 + 35×12 + 150 = 979
    expect(document.querySelector('[data-calc-preco]')!.textContent).toBe('979')
    expect(n['whatsapp.franquia.essencial']).toEqual(['35', '35'])
    expect(n['ia.cota.empresa']).toEqual(['2.500', '2.500'])
    expect(n['ia.teto.empresa']).toEqual(['25.000'])
    expect(n['ia.cota.teste']).toEqual(['40'])
    expect(n['ia.teto.teste']).toEqual(['800'])
    expect(n['ia.analises.detalhado']).toEqual(['4'])
    // A conversa: "de 800" (a cota do Profissional) e a contagem a partir dela.
    expect(n['ia.cota.profissional']).toEqual(['800', '800', '800'])
    const texto = (sel: string) => (document.querySelector(sel)!.textContent ?? '').replace(/\s+/g, ' ').trim()
    expect(texto('[data-nota-teste]')).toBe(
      'No teste grátis valem 40 perguntas ao ToqqiAI e até 800 comentários lidos pela IA.',
    )
    expect(texto('[data-nota-ia]')).toBe('No nível “Mais detalhado” da IA, cada pergunta ao ToqqiAI, resumo ou parecer conta como 4.')
    expect(texto('#planos h2')).toBe('Comece grátis por 7 dias')
  })

  it('a conversa animada passa a contar da cota nova (e recomeça nela a cada volta)', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify(PLANOS_NOVOS), { status: 200 })))
    await import('@/site/site')
    const restam = document.querySelector('[data-restam]')!
    await vi.advanceTimersByTimeAsync(600)
    expect(restam.textContent).toBe('800')
    await vi.advanceTimersByTimeAsync(20000)
    expect(Number(restam.textContent)).toBeLessThan(800)
    expect(Number(restam.textContent)).toBeGreaterThanOrEqual(797)
  })

  it('com movimento reduzido, a conversa parada mostra a cota nova menos as 3 perguntas', async () => {
    vi.stubGlobal('matchMedia', (q: string) => ({ matches: q.includes('reduce'), media: q, addEventListener() {}, removeEventListener() {} }))
    vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify(PLANOS_NOVOS), { status: 200 })))
    await import('@/site/site')
    await vi.advanceTimersByTimeAsync(10)
    expect(document.querySelector('[data-restam]')!.textContent).toBe('797')
    expect(document.querySelector('[data-p="ia.cota.profissional"]')!.closest('div')!.textContent!.replace(/\s+/g, ' ')).toContain('Restam 797 de 800 perguntas no mês')
  })

  it('se a API falha, os números do HTML ficam', async () => {
    const fetch = vi.fn(async () => new Response(JSON.stringify({ erro: { codigo: 'muitas_tentativas', mensagem: 'x' } }), { status: 429 }))
    vi.stubGlobal('fetch', fetch)
    await import('@/site/site')
    await vi.advanceTimersByTimeAsync(10)
    expect(fetch).toHaveBeenCalledTimes(1)
    expect(numeros()).toEqual(antes())
    expect(document.querySelector('[data-restam]')!.textContent).toBe('500')
  })

  it('se a API demora mais de 5 s, desiste e os números do HTML ficam (mesmo que a resposta chegue depois)', async () => {
    let abortado = false
    vi.stubGlobal(
      'fetch',
      vi.fn(
        (_url: string, init?: RequestInit) =>
          new Promise<Response>((ok) => {
            init?.signal?.addEventListener('abort', () => (abortado = true))
            // A resposta chega aos 6 s (o site não deveria usar).
            setTimeout(() => ok(new Response(JSON.stringify(PLANOS_NOVOS), { status: 200 })), 6000)
          }),
      ),
    )
    vi.stubGlobal('matchMedia', (q: string) => ({ matches: q.includes('reduce'), media: q, addEventListener() {}, removeEventListener() {} }))
    await import('@/site/site')
    await vi.advanceTimersByTimeAsync(4900)
    expect(abortado).toBe(false)
    await vi.advanceTimersByTimeAsync(200)
    expect(abortado).toBe(true)
    await vi.advanceTimersByTimeAsync(2000)
    expect(numeros()).toEqual(antes())
    expect(document.querySelector('[data-restam]')!.textContent).toBe('497')
  })

  it('resposta com valores estranhos troca só o que serve', async () => {
    const meio = { ...PLANOS_NOVOS, teste: { dias: 'sete' }, planos: [{ chave: 'essencial', preco: '159.00' }] }
    vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify(meio), { status: 200 })))
    await import('@/site/site')
    await vi.advanceTimersByTimeAsync(10)
    const n = numeros()
    expect(n['planos.essencial.preco']).toEqual(['159', '159'])
    expect(n['teste.dias']).toEqual(antes()['teste.dias'])
    expect(n['planos.profissional.preco']).toEqual(['349', '349'])
    expect(n['ia.analises.detalhado']).toEqual(['4'])
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

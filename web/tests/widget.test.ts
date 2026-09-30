import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { afterEach, beforeEach, describe, expect, it } from 'vitest'

const codigo = readFileSync(resolve(process.cwd(), 'public/widget.js'), 'utf8')

function carregarWidget(attrs: Record<string, string>) {
  const s = document.createElement('script')
  // Não executa pelo DOM: o widget acha a própria tag por data-toqqi.
  s.type = 'text/plain'
  s.setAttribute('src', 'https://app.toqqi.com/widget.js')
  for (const [k, v] of Object.entries(attrs)) s.setAttribute(k, v)
  document.body.appendChild(s)
  new Function(codigo)()
}

describe('widget.js', () => {
  beforeEach(() => {
    document.head.innerHTML = ''
    document.body.innerHTML = ''
    delete (window as unknown as { Toqqi?: unknown }).Toqqi
  })
  afterEach(() => {
    document.body.style.overflow = ''
  })

  it('tem menos de 4 KB', () => {
    expect(new TextEncoder().encode(codigo).length).toBeLessThan(4096)
  })

  it('não faz nada sem data-toqqi', () => {
    carregarWidget({})
    expect(document.querySelector('.toqqi-w-b')).toBeNull()
  })

  it('mostra o botão com texto padrão e abre o iframe certo', () => {
    carregarWidget({ 'data-toqqi': 'Ab12Cd34' })
    const botao = document.querySelector<HTMLButtonElement>('.toqqi-w-b')!
    expect(botao.textContent).toBe('Avalie-nos')
    botao.click()
    const iframe = document.querySelector<HTMLIFrameElement>('.toqqi-w-m iframe')!
    expect(iframe.getAttribute('src')).toBe('https://app.toqqi.com/f/Ab12Cd34?canal=widget&embed=1')
    expect(document.querySelector('[role="dialog"]')?.getAttribute('aria-modal')).toBe('true')
    expect(document.body.style.overflow).toBe('hidden')
    expect(botao.getAttribute('aria-expanded')).toBe('true')
  })

  it('usa texto, cor e posição do script', () => {
    carregarWidget({ 'data-toqqi': 'x', 'data-texto': 'Dê sua opinião', 'data-cor': '#123456', 'data-posicao': 'esquerda' })
    expect(document.querySelector('.toqqi-w-b')?.textContent).toBe('Dê sua opinião')
    const css = document.head.querySelector('style')?.textContent ?? ''
    expect(css).toContain('background:#123456')
    expect(css).toContain('left:20px')
  })

  it('fecha com Esc, clique fora e botão fechar, devolvendo o foco', () => {
    carregarWidget({ 'data-toqqi': 'x' })
    const botao = document.querySelector<HTMLButtonElement>('.toqqi-w-b')!
    botao.focus()
    botao.click()
    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }))
    expect(document.querySelector('.toqqi-w-o')).toBeNull()
    expect(document.activeElement).toBe(botao)
    expect(document.body.style.overflow).toBe('')

    botao.click()
    document.querySelector<HTMLElement>('.toqqi-w-o')!.click()
    expect(document.querySelector('.toqqi-w-o')).toBeNull()

    botao.click()
    document.querySelector<HTMLButtonElement>('.toqqi-w-x')!.click()
    expect(document.querySelector('.toqqi-w-o')).toBeNull()
  })

  it('clique dentro da janela não fecha; abrir duas vezes não duplica', () => {
    carregarWidget({ 'data-toqqi': 'x' })
    const w = window as unknown as { Toqqi: { abrir: () => void } }
    w.Toqqi.abrir()
    w.Toqqi.abrir()
    expect(document.querySelectorAll('.toqqi-w-o')).toHaveLength(1)
    document.querySelector<HTMLElement>('.toqqi-w-m')!.click()
    expect(document.querySelector('.toqqi-w-o')).not.toBeNull()
  })

  it('carregar o script duas vezes não cria dois botões', () => {
    carregarWidget({ 'data-toqqi': 'x' })
    new Function(codigo)()
    expect(document.querySelectorAll('.toqqi-w-b')).toHaveLength(1)
  })
})

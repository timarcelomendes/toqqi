/**
 * Comportamento da página do site (index.html na rota "/"): passos do "Como funciona", animação da Retenção,
 * conversa de exemplo do ToqqiAI, tabela de comparação dos planos e o rótulo "Abrir o Toqqi" para quem já entrou.
 * Sem Vue: a página é HTML estático e funciona sem JavaScript (tudo aparece parado e completo).
 * Etapa 5g: depois de desenhar, busca os preços e limites de agora (GET /publico/planos, até 5 s) e troca cada
 * `[data-p]`; se falhar ou demorar, ficam os números do HTML (os padrões do código).
 */
// Fonte servida pelo próprio site, como no app (sem Google Fonts: o navegador não manda o IP a terceiros).
import '@fontsource/plus-jakarta-sans/latin-400.css'
import '@fontsource/plus-jakarta-sans/latin-500.css'
import '@fontsource/plus-jakarta-sans/latin-600.css'
import '@fontsource/plus-jakarta-sans/latin-700.css'
import '@fontsource/plus-jakarta-sans/latin-800.css'
import './site.css'
import { publicoApi } from '@/api/publico'
import {
  CONVERSA,
  COTA_EXEMPLO,
  TEMPO_PLANOS_MS,
  formatarReais,
  proximoPasso,
  restamNaConversa,
  restamParado,
  temSessao,
  textoNumeroSite,
  valorContador,
  valorPublico,
} from './logica'
import { guardarOrigem } from './origem'

const INTERVALO_PASSOS = 5500
const RISCO = 262399.99
/** A cota da conversa de exemplo (a do Profissional): a contagem recomeça nela a cada volta. */
let cotaConversa = COTA_EXEMPLO
let conversaRodando = false
/** Perguntas já respondidas na volta atual da conversa ("Restam" = cota − respondidas). */
let respondidas = 0

function reduzirMovimento(): boolean {
  try {
    return window.matchMedia('(prefers-reduced-motion: reduce)').matches
  } catch {
    return false
  }
}

function lerSessao(): string | null {
  for (const nome of ['localStorage', 'sessionStorage'] as const) {
    try {
      const v = window[nome].getItem('toqqi.sessao')
      if (v) return v
    } catch {
      /* armazenamento bloqueado: segue como visitante */
    }
  }
  return null
}

/** Chama `fn` uma vez, quando `el` aparecer na tela (sem IntersectionObserver, na hora). */
function aoAparecer(el: Element, fn: () => void, limiar = 0.25): void {
  if (!('IntersectionObserver' in window)) {
    fn()
    return
  }
  const io = new IntersectionObserver(
    (entradas) => {
      if (entradas.some((e) => e.isIntersecting)) {
        io.disconnect()
        fn()
      }
    },
    { threshold: limiar },
  )
  io.observe(el)
}

function sessaoAberta(): void {
  if (!temSessao(lerSessao())) return
  const entrar = document.querySelector<HTMLAnchorElement>('[data-entrar]')
  if (entrar) {
    entrar.textContent = 'Abrir o Toqqi'
    entrar.href = '/inicio'
  }
}

function passos(calmo: boolean): void {
  const botoes = Array.from(document.querySelectorAll<HTMLButtonElement>('[data-passo]'))
  const cenas = Array.from(document.querySelectorAll<HTMLElement>('[data-cena]'))
  if (!botoes.length) return
  let atual = 1
  let timer: number | undefined

  const ativar = (n: number) => {
    atual = n
    for (const b of botoes) {
      const ativo = Number(b.dataset.passo) === n
      b.classList.toggle('ativo', ativo)
      b.setAttribute('aria-pressed', String(ativo))
      // Reinicia a barra de progresso do passo ativo.
      const barra = b.querySelector('.barra > span')
      if (ativo && barra) barra.replaceWith(barra.cloneNode())
    }
    // Mostrar a cena de novo (display) recomeça as animações dela.
    for (const c of cenas) c.hidden = Number(c.dataset.cena) !== n
  }
  const agendar = () => {
    if (timer) window.clearInterval(timer)
    if (calmo) return
    timer = window.setInterval(() => {
      if (document.hidden) return
      ativar(proximoPasso(atual, botoes.length))
    }, INTERVALO_PASSOS)
  }
  for (const b of botoes) {
    b.addEventListener('click', () => {
      ativar(Number(b.dataset.passo))
      agendar()
    })
  }
  agendar()
}

function retencao(calmo: boolean): void {
  const bloco = document.getElementById('retencao')
  const valor = document.querySelector<HTMLElement>('[data-risco]')
  if (!bloco || !valor || calmo) return
  if (typeof window.requestAnimationFrame !== 'function') {
    aoAparecer(bloco, () => bloco.classList.add('vis'))
    return
  }
  valor.textContent = formatarReais(0)
  aoAparecer(bloco, () => {
    bloco.classList.add('vis')
    let inicio: number | null = null
    const quadro = (t: number) => {
      if (inicio === null) inicio = t
      const k = Math.min(1, (t - inicio) / 1400)
      valor.textContent = formatarReais(valorContador(RISCO, k))
      if (k < 1) window.requestAnimationFrame(quadro)
    }
    window.requestAnimationFrame(quadro)
  })
}

function balaoPergunta(texto: string): HTMLElement {
  const el = document.createElement('div')
  el.className = 'an'
  el.style.cssText =
    'align-self:flex-end;max-width:82%;background:#D63A18;color:#FFFFFF;border-radius:16px 16px 4px 16px;padding:11px 15px;font-size:15px;line-height:1.5;flex:none'
  el.textContent = texto
  return el
}

function balaoResposta(texto: string, consultou: string): HTMLElement {
  const el = document.createElement('div')
  el.className = 'an'
  el.style.cssText = 'align-self:flex-start;max-width:92%;display:flex;flex-direction:column;gap:6px;flex:none'
  const fonte = document.createElement('span')
  fonte.style.cssText = 'align-self:flex-start;font-size:11px;font-weight:600;color:#94A3B8'
  fonte.textContent = '✓ ' + consultou
  const corpo = document.createElement('div')
  corpo.style.cssText =
    'background:#1E293B;color:#F1F5F9;border-radius:16px 16px 16px 4px;padding:13px 16px;font-size:15px;line-height:1.6'
  corpo.textContent = texto
  el.append(fonte, corpo)
  return el
}

function conversa(calmo: boolean): void {
  const bloco = document.getElementById('conversa')
  const lista = document.querySelector<HTMLElement>('[data-msgs]')
  const pensando = document.querySelector<HTMLElement>('[data-pensando]')
  const status = document.querySelector<HTMLElement>('[data-status]')
  const restam = document.querySelector<HTMLElement>('[data-restam]')
  const digitado = document.querySelector<HTMLElement>('[data-digitado]')
  const cursor = document.querySelector<HTMLElement>('[data-cursor]')
  const dica = document.querySelector<HTMLElement>('[data-dica]')
  const enviar = document.querySelector<HTMLElement>('[data-enviar]')
  if (!bloco || !lista || !pensando || !status || !restam || !digitado || !cursor || !dica || !enviar) return
  // Parado: a conversa completa já está no HTML.
  if (calmo) return

  const espera = (ms: number) => new Promise<void>((ok) => window.setTimeout(ok, ms))
  const mostrarTexto = (t: string) => {
    digitado.textContent = t
    const tem = t.length > 0
    digitado.hidden = !tem
    cursor.hidden = !tem
    dica.hidden = tem
    enviar.classList.toggle('ativo', tem)
  }
  const acrescentar = (el: HTMLElement) => {
    lista.append(el)
    while (lista.children.length > 5) lista.firstElementChild?.remove()
  }

  const rodar = async () => {
    conversaRodando = true
    for (;;) {
      lista.replaceChildren()
      respondidas = 0
      restam.textContent = String(restamNaConversa(cotaConversa, respondidas))
      await espera(500)
      for (const fala of CONVERSA) {
        for (let i = 1; i <= fala.pergunta.length; i++) {
          mostrarTexto(fala.pergunta.slice(0, i))
          await espera(32 + Math.random() * 40)
        }
        await espera(500)
        mostrarTexto('')
        acrescentar(balaoPergunta(fala.pergunta))
        status.textContent = fala.status[0] ?? ''
        pensando.hidden = false
        if (fala.status[1]) {
          await espera(1400)
          status.textContent = fala.status[1]
          await espera(1500)
        } else {
          await espera(2900)
        }
        pensando.hidden = true
        acrescentar(balaoResposta(fala.resposta, fala.consultou))
        respondidas += 1
        restam.textContent = String(restamNaConversa(cotaConversa, respondidas))
        await espera(2400 + fala.resposta.length * 18)
      }
      await espera(8000)
    }
  }
  aoAparecer(bloco, () => void rodar(), 0.3)
}

function comparar(): void {
  const botao = document.querySelector<HTMLButtonElement>('[data-comparar]')
  const tabela = document.getElementById('tabela-planos')
  const fechado = document.querySelector<HTMLElement>('[data-rotulo-fechado]')
  const aberto = document.querySelector<HTMLElement>('[data-rotulo-aberto]')
  const seta = botao?.querySelector<HTMLElement>('.seta')
  if (!botao || !tabela || !fechado || !aberto) return
  botao.addEventListener('click', () => {
    const abrir = tabela.hidden
    tabela.hidden = !abrir
    botao.setAttribute('aria-expanded', String(abrir))
    fechado.hidden = abrir
    aberto.hidden = !abrir
    seta?.classList.toggle('virada', abrir)
  })
}

/** Troca os números do HTML pelos de GET /publico/planos (o que não vier certo fica como está). */
function aplicarNumeros(corpo: unknown): void {
  for (const el of Array.from(document.querySelectorAll<HTMLElement>('[data-p]'))) {
    const chave = el.dataset.p ?? ''
    const texto = textoNumeroSite(chave, valorPublico(corpo, chave), el.hasAttribute('data-p-maiuscula'))
    if (texto !== null && el.textContent !== texto) el.textContent = texto
  }
  const cota = valorPublico(corpo, 'ia.cota.profissional')
  if (typeof cota === 'number' && Number.isInteger(cota) && cota >= 0) {
    cotaConversa = cota
    // Parada (ou ainda sem aparecer), a conversa mostra a cota menos as 3 perguntas do HTML; rodando, a cota menos as
    // respondidas nesta volta (e a próxima volta recomeça nela).
    const restam = document.querySelector<HTMLElement>('[data-restam]')
    if (restam) restam.textContent = String(conversaRodando ? restamNaConversa(cota, respondidas) : restamParado(cota))
  }
}

function numerosDosPlanos(): void {
  const controle = new AbortController()
  let expirou = false
  const prazo = window.setTimeout(() => {
    expirou = true
    controle.abort()
  }, TEMPO_PLANOS_MS)
  publicoApi
    .planos(controle.signal)
    .then((corpo) => {
      if (!expirou) aplicarNumeros(corpo)
    })
    .catch(() => {
      /* sem resposta: ficam os números do HTML */
    })
    .finally(() => window.clearTimeout(prazo))
}

guardarOrigem() // etapa 5i: de onde veio a visita (para o cadastro)
const calmo = reduzirMovimento()
if (!calmo) document.documentElement.classList.add('movimento')
sessaoAberta()
passos(calmo)
retencao(calmo)
conversa(calmo)
comparar()
numerosDosPlanos()

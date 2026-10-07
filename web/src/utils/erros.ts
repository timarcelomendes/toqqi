// Aviso de erros do site (etapa 5h, docs/api-etapa-5h.md §4): os erros do app e da página da pesquisa vão para a API
// (POST /publico/erros, sem login), que limpa os textos e soma as ocorrências em Plataforma › Erros.
// - Liga `app.config.errorHandler` (erros dos componentes; continuam no console), `window` "error" e
//   "unhandledrejection".
// - Manda cada mensagem uma vez por carregamento da página e, no máximo, 5 por carregamento.
// - Ignora: respostas da API e falhas de rede (`ApiError`, com ou sem status; `fetch` que não chegou; módulo que não
//   carregou; pedido cancelado), erros de extensões do navegador (pilha só com arquivos de fora do nosso endereço) e o
//   aviso do navegador "ResizeObserver loop" (e o "Script error." sem detalhes, de scripts de outros sites).
// - Manda tipo, mensagem, local (o caminho da tela, sem query nem hash, com os ids e tokens trocados por :id e :token),
//   pilha e a versão do build. Nada do que a pessoa digitou nem a query string. O corpo cabe nos 4 KB da API.
// Leve de propósito: a página da pesquisa (responder.html) também usa, sem Pinia nem router.
import type { App } from 'vue'
import { API_URL } from '@/api/cliente'
import { ApiError } from '@/api/erros'
import { registrarErroDoSite } from '@/utils/diagnostico'

export const VERSAO_SITE: string = typeof __TOQQI_VERSAO__ === 'string' && __TOQQI_VERSAO__ ? __TOQQI_VERSAO__ : 'local'
export const MAX_POR_CARREGAMENTO = 5
/** O corpo vai até 4 KB na API: fica uma folga para o JSON. */
export const MAX_BYTES = 3900

export interface ErroSite {
  tipo: string
  mensagem: string
  local: string
  pilha: string
  versao: string
}

export interface OpcoesAviso {
  /** O token da sessão, para a API saber a conta (o app manda; a página da pesquisa, não). */
  obterToken?: () => string | null
  /** O endereço do site (padrão: `window.location.origin`): pilha só com outros endereços = extensão. */
  origem?: string
  /** O caminho da tela agora (padrão: `window.location.pathname`). */
  caminho?: () => string
  /** Para onde vai (padrão: POST /publico/erros). */
  enviar?: (erro: ErroSite, token: string | null) => void
}

const REDE = [
  /failed to fetch/i,
  /networkerror/i,
  /network request failed/i,
  /load failed/i,
  /fetch failed/i,
  /dynamically imported module/i,
  /importing a module script failed/i,
  /error loading dynamically imported module/i,
  /unable to preload css/i,
]
const AVISOS_DO_NAVEGADOR = [/resizeobserver loop/i, /^script error\.?$/i]
const EXTENSAO = /\b(?:chrome|moz|safari|safari-web|ms-browser)-extension:\/\//i
const ENDERECO = /\b(?:https?|chrome-extension|moz-extension|safari-extension|safari-web-extension|webkit-masked-url):\/\/[^\s)]+/gi

function texto(v: unknown): string {
  if (typeof v === 'string') return v
  try {
    return String(v)
  } catch {
    return ''
  }
}

/** Páginas públicas: o segundo pedaço do caminho é o token do convite ou do descadastro, ou o código do formulário. */
const PUBLICAS: Record<string, string> = { r: ':token', sair: ':token', f: ':codigo' }

/**
 * O caminho da tela sem query nem hash, com ids (números), tokens (16+ letras, números, - e _, com algum número) e o
 * token ou código das páginas públicas (/r, /f e /sair) trocados pelo nome: o mesmo erro na mesma tela é um erro só.
 */
export function localDaTela(caminho: string): string {
  const partes = (caminho.split(/[?#]/)[0] ?? '').split('/')
  return partes
    .map((parte, i) => {
      if (i === 2 && parte && PUBLICAS[partes[1] ?? '']) return PUBLICAS[partes[1]!]!
      if (/^\d+$/.test(parte)) return ':id'
      if (/^[A-Za-z0-9_-]{16,}$/.test(parte) && /\d/.test(parte)) return ':token'
      return parte
    })
    .join('/')
    .slice(0, 200)
}

/** Tipo, mensagem e pilha de qualquer coisa lançada (Error, texto, objeto). */
export function descrever(erro: unknown): { tipo: string; mensagem: string; pilha: string } {
  if (erro instanceof Error) {
    return { tipo: erro.name || erro.constructor?.name || 'Error', mensagem: erro.message ?? '', pilha: erro.stack ?? '' }
  }
  if (erro && typeof erro === 'object' && 'message' in erro) {
    const e = erro as { name?: unknown; message?: unknown; stack?: unknown }
    return { tipo: texto(e.name ?? 'Error') || 'Error', mensagem: texto(e.message), pilha: texto(e.stack ?? '') }
  }
  return { tipo: 'Error', mensagem: texto(erro), pilha: '' }
}

function ehApiError(erro: unknown): boolean {
  return erro instanceof ApiError || (!!erro && typeof erro === 'object' && (erro as { name?: unknown }).name === 'ApiError')
}

/**
 * Se o erro fica de fora (regras no cabeçalho). `arquivo`: o arquivo do script onde o erro nasceu, quando o navegador
 * informa (evento "error" da janela).
 */
export function deveIgnorar(erro: unknown, origem: string, arquivo = ''): boolean {
  if (ehApiError(erro)) return true
  if (erro instanceof DOMException && erro.name === 'AbortError') return true
  const { tipo, mensagem, pilha } = descrever(erro)
  if (tipo === 'AbortError') return true
  if (AVISOS_DO_NAVEGADOR.some((r) => r.test(mensagem.trim()))) return true
  if (REDE.some((r) => r.test(mensagem))) return true
  if (arquivo && (EXTENSAO.test(arquivo) || (/^[a-z][a-z0-9+.-]*:\/\//i.test(arquivo) && !arquivo.startsWith(origem)))) return true
  const enderecos = pilha.match(ENDERECO) ?? []
  // pilha com endereços e nenhum do nosso: o erro nasceu numa extensão (ou num script de outro site)
  if (enderecos.length && !enderecos.some((u) => u.startsWith(origem))) return true
  return false
}

function bytes(s: string): number {
  return new TextEncoder().encode(s).length
}

/** O corpo do POST, cortado para caber nos 4 KB da API (a pilha cede primeiro, depois a mensagem). */
export function montarCorpo(erro: ErroSite): string {
  const e: ErroSite = {
    tipo: erro.tipo.slice(0, 200) || 'Error',
    mensagem: erro.mensagem.slice(0, 1000),
    local: erro.local.slice(0, 200),
    pilha: erro.pilha.slice(0, 3000),
    versao: erro.versao.replace(/[^0-9A-Za-z._-]/g, '').slice(0, 40),
  }
  let corpo = JSON.stringify(e)
  while (bytes(corpo) > MAX_BYTES && (e.pilha || e.mensagem)) {
    if (e.pilha) e.pilha = e.pilha.slice(0, Math.floor(e.pilha.length / 2))
    else e.mensagem = e.mensagem.slice(0, Math.floor(e.mensagem.length / 2))
    corpo = JSON.stringify(e)
  }
  return corpo
}

function enviarParaApi(erro: ErroSite, token: string | null): void {
  try {
    const cabecalhos: Record<string, string> = { 'Content-Type': 'application/json' }
    if (token) cabecalhos.Authorization = `Bearer ${token}`
    void fetch(`${API_URL}/publico/erros`, { method: 'POST', headers: cabecalhos, body: montarCorpo(erro), keepalive: true }).catch(
      () => {},
    )
  } catch {
    /* o aviso de erros nunca quebra a página */
  }
}

export interface AvisoDeErros {
  /** Manda o erro (se não for para ignorar, se ainda não foi e se não passou do limite). Devolve se mandou. */
  avisar: (erro: unknown, arquivo?: string) => boolean
  /** Liga o `errorHandler` de um app Vue (o erro continua no console). */
  ligarApp: (app: App) => void
  /** Quantos já foram neste carregamento. */
  readonly enviados: number
}

/** O aviso de erros de um carregamento da página (sem ligar nada: `instalarAvisoDeErros` liga). */
export function criarAvisoDeErros(opcoes: OpcoesAviso = {}): AvisoDeErros {
  const vistos = new Set<string>()
  let enviados = 0
  const origem = () => opcoes.origem ?? (typeof window !== 'undefined' ? window.location.origin : '')
  const caminho = () => (opcoes.caminho ? opcoes.caminho() : typeof window !== 'undefined' ? window.location.pathname : '')
  const enviar = opcoes.enviar ?? enviarParaApi

  function avisar(erro: unknown, arquivo = ''): boolean {
    try {
      if (deveIgnorar(erro, origem(), arquivo)) return false
      const { tipo, mensagem, pilha } = descrever(erro)
      // o feedback de erro leva os últimos erros deste carregamento (utils/diagnostico), mesmo os que não foram à API
      registrarErroDoSite({ tipo, mensagem, local: localDaTela(caminho()) })
      if (enviados >= MAX_POR_CARREGAMENTO) return false
      const chave = `${tipo}: ${mensagem}`
      if (vistos.has(chave)) return false
      vistos.add(chave)
      enviados++
      let token: string | null = null
      try {
        token = opcoes.obterToken?.() ?? null
      } catch {
        token = null
      }
      enviar({ tipo, mensagem, local: localDaTela(caminho()), pilha, versao: VERSAO_SITE }, token)
      return true
    } catch {
      return false
    }
  }

  function ligarApp(app: App): void {
    const anterior = app.config.errorHandler
    app.config.errorHandler = (erro, instancia, info) => {
      avisar(erro)
      if (anterior) anterior(erro, instancia, info)
      else console.error(erro) // sem errorHandler o Vue mostra no console; com ele, quem mostra somos nós
    }
  }

  return {
    avisar,
    ligarApp,
    get enviados() {
      return enviados
    },
  }
}

let instalado: AvisoDeErros | null = null

/**
 * Liga o aviso de erros da página: "error" e "unhandledrejection" da janela (uma vez por carregamento; chamar de novo
 * devolve o mesmo) e, com `app`, o `errorHandler` dele.
 */
export function instalarAvisoDeErros(app?: App | null, opcoes: OpcoesAviso = {}): AvisoDeErros {
  if (!instalado) {
    const aviso = criarAvisoDeErros(opcoes)
    window.addEventListener('error', (e: ErrorEvent) => {
      aviso.avisar(e.error ?? new Error(e.message || 'Erro'), e.filename || '')
    })
    window.addEventListener('unhandledrejection', (e: PromiseRejectionEvent) => {
      aviso.avisar(e.reason instanceof Error || ehApiError(e.reason) ? e.reason : { name: 'PromiseRejection', message: texto(e.reason) })
    })
    instalado = aviso
  }
  if (app) instalado.ligarApp(app)
  return instalado
}

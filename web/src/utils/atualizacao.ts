// Versão nova do site no ar (pedido do Marcelo em 08/10/2026, 12h55: "não apareceu a coluna risco"; a aba do Toqqi
// estava aberta desde antes da publicação, com a versão velha na memória, e nada avisava). A cada publicação, o build
// grava `/versao.json` com a versão do site (o commit, a mesma de `VERSAO_SITE`, em vite.config.ts). O app confere esse
// arquivo ao trocar de tela e quando a aba volta a ficar visível (no máximo uma vez por minuto). Com versão nova no ar:
// - o aviso "O Toqqi foi atualizado", com o botão "Atualizar a página" (uma vez por versão);
// - na próxima troca de tela do app logado (outro caminho; filtros e abas da mesma tela, não), o app abre o destino
//   carregando a página inteira, já na versão nova. As perguntas de "sair sem salvar" das telas vêm antes, como sempre.
//   Entrar, cadastro e as outras telas de visitante ficam de fora: o cadastro com o Google guarda o passo "Falta pouco"
//   só na memória da página.
// - Tela que não abre porque o arquivo dela sumiu (a publicação nova troca os arquivos com hash no nome): confere a versão
//   na hora e, se mudou, abre o destino carregando a página inteira.
// Para não entrar em laço (o navegador com o index.html velho em cache, por exemplo), cada aba recarrega no máximo uma
// vez por versão nova (sessionStorage); depois disso, fica só o aviso. Sem `/versao.json` (sem internet, arquivo que não
// é JSON) não faz nada. Fora do Render (`VERSAO_SITE` "local": desenvolvimento e testes) não confere nada.
import type { Router } from 'vue-router'
import { avisar, fecharAviso } from '@/composables/avisos'
import { VERSAO_SITE } from '@/utils/erros'

export const ARQUIVO_VERSAO = '/versao.json'
/** Intervalo mínimo entre duas consultas a `/versao.json`. */
export const INTERVALO = 60_000
/** sessionStorage: a versão nova que esta aba já tentou abrir carregando a página inteira. */
export const CHAVE_RECARGA = 'toqqi.versao-recarregada'
export const TITULO_AVISO = 'O Toqqi foi atualizado'
export const MENSAGEM_AVISO = 'Atualize a página para usar a versão nova.'

/** Falha ao carregar o arquivo de uma tela (import dinâmico): as mensagens do Chrome, do Firefox e do Safari. */
const ARQUIVO_SUMIU = [
  /failed to fetch dynamically imported module/i,
  /error loading dynamically imported module/i,
  /importing a module script failed/i,
  /unable to preload css/i,
]

export function falhaDeArquivo(erro: unknown): boolean {
  const mensagem = erro instanceof Error ? erro.message : typeof erro === 'string' ? erro : ''
  return ARQUIVO_SUMIU.some((r) => r.test(mensagem))
}

/** A versão de `/versao.json` (`{"versao": "abc1234"}`); null se o arquivo não veio ou não tem versão. */
export function lerVersao(dados: unknown): string | null {
  if (!dados || typeof dados !== 'object') return null
  const v = (dados as { versao?: unknown }).versao
  return typeof v === 'string' && /^[0-9A-Za-z._-]{1,40}$/.test(v) ? v : null
}

export interface OpcoesAtualizacao {
  /** A versão que está rodando (padrão: `VERSAO_SITE`). "local" desliga tudo. */
  versaoAtual?: string
  /** Busca `/versao.json` e devolve o JSON (padrão: `fetch` sem cache). */
  buscar?: (url: string) => Promise<unknown>
  agora?: () => number
  /** Carrega a página inteira neste endereço (padrão: `window.location.assign`). */
  irPara?: (endereco: string) => void
  /** Recarrega a página (padrão: `window.location.reload`). */
  recarregar?: () => void
  /** Onde fica a versão que a aba já tentou abrir (padrão: `sessionStorage`; null = sem memória). */
  armazenamento?: Pick<Storage, 'getItem' | 'setItem'> | null
}

export interface Atualizacao {
  /** Confere `/versao.json` (respeitando o intervalo, salvo com `forcar`). Devolve a versão nova no ar, ou null. */
  conferir: (forcar?: boolean) => Promise<string | null>
  /** Se esta aba ainda pode recarregar para a versão `v` (e anota que vai). */
  podeRecarregar: (v: string) => boolean
  /** A versão nova já vista (null: nenhuma). */
  readonly nova: string | null
}

async function buscarSemCache(url: string): Promise<unknown> {
  const r = await fetch(url, { cache: 'no-store', credentials: 'omit' })
  if (!r.ok) return null
  return r.json()
}

function sessao(): Pick<Storage, 'getItem' | 'setItem'> | null {
  try {
    return window.sessionStorage
  } catch {
    return null
  }
}

/** A conferência da versão (sem ligar nada: `instalarAtualizacao` liga no router e na aba). */
export function criarAtualizacao(opcoes: OpcoesAtualizacao = {}): Atualizacao {
  const versaoAtual = opcoes.versaoAtual ?? VERSAO_SITE
  const buscar = opcoes.buscar ?? buscarSemCache
  const agora = opcoes.agora ?? (() => Date.now())
  const recarregar = opcoes.recarregar ?? (() => window.location.reload())
  const armazenamento = opcoes.armazenamento === undefined ? sessao() : opcoes.armazenamento
  let nova: string | null = null
  let ultima = -Infinity
  let emCurso: Promise<string | null> | null = null
  let avisoId: number | null = null

  function mostrarAviso() {
    if (avisoId !== null) fecharAviso(avisoId)
    avisoId = avisar({ tipo: 'info', titulo: TITULO_AVISO, mensagem: MENSAGEM_AVISO, duracao: 0, acao: { rotulo: 'Atualizar a página', executar: recarregar } })
  }

  async function consultar(): Promise<string | null> {
    ultima = agora()
    let v: string | null = null
    try {
      v = lerVersao(await buscar(`${ARQUIVO_VERSAO}?t=${ultima}`))
    } catch {
      return nova
    }
    if (v && v !== versaoAtual && v !== nova) {
      nova = v
      mostrarAviso()
    }
    return nova
  }

  function conferir(forcar = false): Promise<string | null> {
    if (versaoAtual === 'local') return Promise.resolve(null)
    if (emCurso) return emCurso
    if (!forcar && agora() - ultima < INTERVALO) return Promise.resolve(nova)
    emCurso = consultar().finally(() => {
      emCurso = null
    })
    return emCurso
  }

  function podeRecarregar(v: string): boolean {
    try {
      if (armazenamento?.getItem(CHAVE_RECARGA) === v) return false
      armazenamento?.setItem(CHAVE_RECARGA, v)
    } catch {
      /* sem sessionStorage: recarrega mesmo assim (o aviso segura o resto) */
    }
    return true
  }

  return {
    conferir,
    podeRecarregar,
    get nova() {
      return nova
    },
  }
}

/**
 * Liga a conferência no router (antes de cada troca de tela do app logado, depois de cada troca de caminho e na falha
 * ao carregar o arquivo de uma tela) e na aba (quando volta a ficar visível). Devolve a conferência, para os testes.
 */
export function instalarAtualizacao(router: Router, opcoes: OpcoesAtualizacao & { documento?: Document } = {}): Atualizacao {
  const atualizacao = criarAtualizacao(opcoes)
  const irPara = opcoes.irPara ?? ((endereco: string) => window.location.assign(endereco))
  const documento = opcoes.documento ?? document

  router.beforeEach((to, from) => {
    const v = atualizacao.nova
    if (!v || !from.matched.length || to.path === from.path) return true
    if (!to.meta.logado || !from.meta.logado) return true
    if (!atualizacao.podeRecarregar(v)) return true
    irPara(to.fullPath)
    return false
  })

  // a primeira navegação (a página acabou de carregar) não confere: já é a versão do momento
  router.afterEach((to, from, falha) => {
    if (!falha && from.matched.length && to.path !== from.path) void atualizacao.conferir()
  })

  router.onError(async (erro, to) => {
    if (!falhaDeArquivo(erro)) return
    const v = await atualizacao.conferir(true)
    if (v && atualizacao.podeRecarregar(v)) irPara(to.fullPath)
  })

  documento.addEventListener('visibilitychange', () => {
    if (documento.visibilityState === 'visible') void atualizacao.conferir()
  })

  return atualizacao
}

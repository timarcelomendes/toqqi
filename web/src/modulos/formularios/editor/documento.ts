// O documento de trabalho do editor (docs/api-etapa-5l.md §5.3, "Rascunho, salvamento e conflito"):
// - ao abrir, é o rascunho (se houver) ou uma cópia do publicado;
// - cada mudança grava sozinha com espera de ~1,2 s (PUT …/rascunho), em fila (nunca dois PUT ao mesmo tempo);
// - a resposta atualiza o `rev` e aplica o normalizado (ids gerados, HTML limpo) sem mexer no campo em edição;
// - 409 `rascunho_desatualizado` vira a faixa de conflito; sem rede, "Não foi possível salvar";
// - desfazer/refazer: instantâneos do documento (até 100), com a digitação no mesmo campo agrupada (< 800 ms).
// Sem componente: as telas do editor recebem este controle por provide/inject (`usarEditor`).
import { computed, inject, provide, reactive, ref, shallowRef, watch, type InjectionKey } from 'vue'
import { ApiError, formulariosApi, mensagemDoErro } from '@/api'
import type { ConflitoRascunho, DocumentoFormulario, Final, Formulario, Id, Pergunta, Tema } from '@/api/tipos'
import { converterCondicaoLegada, indicePrincipal } from '@/pesquisa/logica'
import { FOCO_FINAL_PADRAO, TEMA_PADRAO } from '@/pesquisa/tipos'
import { juntarProblemas, problemasDoServidor, validarDocumento, type Problema } from '../validacaoFormulario'

export type EstadoSalvamento = 'salvo' | 'pendente' | 'salvando' | 'erro' | 'conflito'

export const ESPERA_SALVAR = 1200
export const AGRUPAR_DIGITACAO = 800
export const MAX_HISTORICO = 100

interface Instantaneo {
  doc: string
  selecionado: string | null
}

/** Uma cópia simples (o documento só tem dados JSON). */
export function clonar<T>(v: T): T {
  return JSON.parse(JSON.stringify(v)) as T
}

/** Documento a partir do que veio da API: tema completo, finais em lista e a `condicao` antiga convertida. */
export function documentoDe(perguntas: Pergunta[] | null | undefined, tema: Partial<Tema> | null | undefined, finais: Final[] | null | undefined): DocumentoFormulario {
  const itens = clonar(perguntas ?? [])
  const ip = indicePrincipal(itens)
  const idPrincipal = ip >= 0 ? itens[ip]!.id : null
  for (const p of itens) {
    if (!p.condicao) continue
    if (!p.logica?.mostrar_se && idPrincipal && p !== itens[ip]) {
      const g = converterCondicaoLegada(p.condicao, idPrincipal)
      if (g) p.logica = { ...(p.logica ?? {}), mostrar_se: g }
    }
    delete p.condicao
  }
  return { perguntas: itens, tema: { ...TEMA_PADRAO, ...clonar(tema ?? {}) } as Tema, finais: clonar(finais ?? []) }
}

/**
 * Forma canônica para comparar documentos ("tem alterações?"): sem chaves vazias (null, "", false, [], {}) e sem os
 * padrões que a API não grava (`exibicao: "botoes"`), com as chaves em ordem.
 */
export function chaveCanonica(doc: DocumentoFormulario): string {
  const limpar = (v: unknown, chave?: string): unknown => {
    if (Array.isArray(v)) {
      const lista = v.map((x) => limpar(x)).filter((x) => x !== undefined)
      return chave === 'opcoes' || lista.length ? lista : undefined
    }
    if (v && typeof v === 'object') {
      const saida: Record<string, unknown> = {}
      for (const k of Object.keys(v as object).sort()) {
        const x = limpar((v as Record<string, unknown>)[k], k)
        if (x === undefined) continue
        if (k === 'exibicao' && x === 'botoes') continue
        if (k === 'modo' && x === 'visual') continue
        saida[k] = x
      }
      return Object.keys(saida).length ? saida : undefined
    }
    if (v === null || v === undefined || v === '' || v === false) return undefined
    return typeof v === 'string' ? v.trim() || undefined : v
  }
  return JSON.stringify(limpar(doc) ?? {})
}

/** O elemento com o foco é um campo de digitar? (só nele a digitação vira um passo só no desfazer) */
function campoDeTexto(el: Element | null): Element | null {
  if (!el) return null
  if (el instanceof HTMLTextAreaElement) return el
  if (el instanceof HTMLInputElement && ['text', 'search', 'url', 'email', 'tel', 'number', ''].includes(el.type)) return el
  if (el instanceof HTMLElement && el.isContentEditable) return el.closest('[contenteditable="true"]') ?? el
  return null
}

export interface OpcoesEditor {
  formularioId: Id
  /** Para testes: sem `document.activeElement` (agrupa por campo quando houver). */
  agora?: () => number
}

export function criarEditor(opcoes: OpcoesEditor) {
  const agora = opcoes.agora ?? (() => Date.now())
  const formulario = ref<Formulario | null>(null)
  const doc = reactive<DocumentoFormulario>({ perguntas: [], tema: { ...TEMA_PADRAO }, finais: [] })
  const publicado = shallowRef<DocumentoFormulario>({ perguntas: [], tema: { ...TEMA_PADRAO }, finais: [] })
  const rev = ref(0)
  const temRascunhoServidor = ref(false)
  const salvoEm = ref<string | null>(null)
  const salvoPorNome = ref<string | null>(null)
  const estado = ref<EstadoSalvamento>('salvo')
  const erroSalvar = ref<string | null>(null)
  const conflito = ref<ConflitoRascunho | null>(null)
  const problemasServidor = ref<Problema[]>([])
  const errosPublicar = ref<Problema[]>([])
  const publicando = ref(false)
  const descartando = ref(false)
  const selecionado = ref<string | null>(null)
  const painelProblemas = ref(false)
  /** Pedido para levar o foco a um campo do item (o painel de problemas, um item novo): a edição abre o que precisar. */
  const pedidoFoco = ref<{ id: string; campo: string | null; logica: Problema['logica'] | null; vez: number } | null>(null)
  function pedirFoco(id: string, campo: string | null, logica: Problema['logica'] | null = null) {
    pedidoFoco.value = { id, campo, logica, vez: (pedidoFoco.value?.vez ?? 0) + 1 }
  }

  // ── desfazer/refazer ──
  const desfazer_: Instantaneo[] = []
  const refazer_: Instantaneo[] = []
  const tamanhoHistorico = ref({ desfazer: 0, refazer: 0 })
  let ultimo = JSON.stringify(doc)
  let selecionadoAntes: string | null = null
  let ultimaMudanca: { quando: number; campo: Element | null } = { quando: 0, campo: null }
  let novoPasso = false

  // ── salvamento ──
  let versaoLocal = 0
  let versaoSalva = 0
  /** O mesmo `versaoLocal`, reativo: os problemas do servidor só valem enquanto o documento não mudou depois deles. */
  const versaoTela = ref(0)
  const versaoDosProblemas = ref(-1)
  /** O documento como o servidor tem (carregado ou gravado por último): voltar a ele não precisa de outro PUT. */
  let docServidor = ''
  let espera: ReturnType<typeof setTimeout> | null = null
  let emVoo: Promise<void> | null = null

  const contarHistorico = () => (tamanhoHistorico.value = { desfazer: desfazer_.length, refazer: refazer_.length })
  const serializar = () => JSON.stringify({ perguntas: doc.perguntas, tema: doc.tema, finais: doc.finais })

  /** Registra o que mudou desde o último instantâneo (um passo no desfazer, ou junto do anterior se for digitação). */
  function registrarMudanca() {
    const atual = serializar()
    if (atual === ultimo) return
    const quando = agora()
    const campo = typeof document !== 'undefined' ? campoDeTexto(document.activeElement) : null
    const agrupar = !novoPasso && !!campo && campo === ultimaMudanca.campo && quando - ultimaMudanca.quando < AGRUPAR_DIGITACAO && desfazer_.length > 0
    if (!agrupar) {
      desfazer_.push({ doc: ultimo, selecionado: selecionadoAntes ?? selecionado.value })
      if (desfazer_.length > MAX_HISTORICO) desfazer_.shift()
    }
    refazer_.length = 0
    contarHistorico()
    novoPasso = false
    ultimo = atual
    ultimaMudanca = { quando, campo }
    selecionadoAntes = selecionado.value
    versaoTela.value = ++versaoLocal
    agendar()
  }

  watch(doc, registrarMudanca, { deep: true })
  watch(selecionado, (s) => {
    selecionadoAntes = s
    // Trocar de item fecha o grupo de digitação.
    ultimaMudanca = { quando: 0, campo: null }
  })

  /** Aplica um instantâneo (desfazer/refazer, servidor) sem virar passo no histórico. */
  function aplicarDocumento(d: DocumentoFormulario) {
    doc.perguntas = d.perguntas
    doc.tema = d.tema
    doc.finais = d.finais
    ultimo = serializar()
  }

  /** Mudança que é um passo próprio no desfazer, mesmo vindo logo depois de digitar (mover, excluir, duplicar…). */
  function mudar(fn: () => void) {
    registrarMudanca()
    novoPasso = true
    fn()
  }

  function desfazer() {
    registrarMudanca()
    const anterior = desfazer_.pop()
    if (!anterior) return
    refazer_.push({ doc: ultimo, selecionado: selecionado.value })
    aplicarDocumento(JSON.parse(anterior.doc) as DocumentoFormulario)
    if (anterior.selecionado !== undefined) selecionado.value = anterior.selecionado
    selecionadoAntes = selecionado.value
    ultimaMudanca = { quando: 0, campo: null }
    contarHistorico()
    versaoTela.value = ++versaoLocal
    agendar()
  }

  function refazer() {
    registrarMudanca()
    const proximo = refazer_.pop()
    if (!proximo) return
    desfazer_.push({ doc: ultimo, selecionado: selecionado.value })
    aplicarDocumento(JSON.parse(proximo.doc) as DocumentoFormulario)
    if (proximo.selecionado !== undefined) selecionado.value = proximo.selecionado
    selecionadoAntes = selecionado.value
    ultimaMudanca = { quando: 0, campo: null }
    contarHistorico()
    versaoTela.value = ++versaoLocal
    agendar()
  }

  // ── carregar ──

  /** Aplica o formulário que veio da API: o publicado e, se houver, o rascunho como documento de trabalho. */
  function aplicarFormulario(f: Formulario, { limparHistorico = false } = {}) {
    registrarMudanca()
    formulario.value = f
    publicado.value = documentoDe(f.perguntas, f.tema, f.finais)
    const base = f.rascunho ? documentoDe(f.rascunho.perguntas, f.rascunho.tema, f.rascunho.finais) : clonar(publicado.value)
    aplicarDocumento(base)
    docServidor = ultimo
    rev.value = f.rascunho_rev ?? 0
    temRascunhoServidor.value = !!f.rascunho
    salvoEm.value = f.rascunho?.salvo_em ?? null
    salvoPorNome.value = f.rascunho?.salvo_por_nome ?? null
    versaoSalva = versaoLocal
    if (espera) clearTimeout(espera)
    espera = null
    estado.value = 'salvo'
    erroSalvar.value = null
    conflito.value = null
    problemasServidor.value = []
    errosPublicar.value = []
    if (limparHistorico) {
      desfazer_.length = 0
      refazer_.length = 0
      contarHistorico()
    }
    if (selecionado.value && !existe(selecionado.value)) selecionado.value = null
  }

  function existe(id: string): boolean {
    return id === FOCO_FINAL_PADRAO || doc.perguntas.some((p) => p.id === id) || doc.finais.some((f) => f.id === id)
  }

  // ── salvar ──

  function agendar(ms = ESPERA_SALVAR) {
    if (estado.value === 'conflito') return
    if (estado.value !== 'salvando') estado.value = estado.value === 'erro' ? 'erro' : 'pendente'
    if (espera) clearTimeout(espera)
    espera = setTimeout(() => {
      espera = null
      void salvar()
    }, ms)
  }

  /**
   * Junta o que o servidor normalizou com o que está na tela, por id: só os ids que faltavam e o HTML limpo, e só onde
   * a pessoa não mexeu depois do envio (nem no campo em edição). Títulos e textos ficam como estão.
   */
  function mesclar(enviado: DocumentoFormulario, recebido: DocumentoFormulario) {
    const focado = typeof document !== 'undefined' ? document.activeElement : null
    const editandoHtml = (id: string) => !!focado?.closest?.(`[data-editor-html="${id}"]`)
    const enviadoPorId = new Map(enviado.perguntas.map((p) => [p.id, p]))
    const recebidoPorId = new Map(recebido.perguntas.map((p) => [p.id, p]))
    for (const p of doc.perguntas) {
      const e = enviadoPorId.get(p.id)
      const r = recebidoPorId.get(p.id)
      if (!e || !r) continue
      if (p.tipo === 'conteudo' && typeof r.html === 'string' && p.html === e.html && r.html !== p.html && !editandoHtml(p.id)) p.html = r.html
      // Regras sem id (não deveria acontecer: o editor gera) ganham o da API, pela posição.
      const regras = p.logica?.pular ?? []
      const regrasR = r.logica?.pular ?? []
      regras.forEach((regra, k) => {
        if (!regra.id && regrasR[k]?.id) regra.id = regrasR[k]!.id
      })
    }
    const finaisE = new Map(enviado.finais.map((f) => [f.id, f]))
    const finaisR = new Map(recebido.finais.map((f) => [f.id, f]))
    doc.finais.forEach((f, k) => {
      if (!f.id && recebido.finais[k]?.id) f.id = recebido.finais[k]!.id
      const e = finaisE.get(f.id)
      const r = finaisR.get(f.id)
      if (e && r && typeof r.html === 'string' && (f.html ?? '') === (e.html ?? '') && r.html !== (f.html ?? '') && !editandoHtml(f.id)) f.html = r.html
    })
    // O que a mescla mudou não é passo no desfazer nem pede outro salvamento.
    ultimo = serializar()
  }

  /** Grava o rascunho agora (fila: espera o PUT em andamento). Devolve true se ficou tudo salvo. */
  async function salvar(): Promise<boolean> {
    registrarMudanca()
    if (espera) clearTimeout(espera)
    espera = null
    if (estado.value === 'conflito') return false
    if (emVoo) {
      await emVoo
      return salvar()
    }
    if (versaoLocal === versaoSalva && estado.value !== 'erro') {
      estado.value = 'salvo'
      return true
    }
    // Voltou ao que o servidor já tem (ex.: moveu e voltou, desfez tudo): nada para gravar.
    if (estado.value !== 'erro' && serializar() === docServidor) {
      versaoSalva = versaoLocal
      estado.value = 'salvo'
      return true
    }
    const versao = versaoLocal
    const enviado = clonar({ perguntas: doc.perguntas, tema: doc.tema, finais: doc.finais }) as DocumentoFormulario
    estado.value = 'salvando'
    emVoo = (async () => {
      try {
        const r = await formulariosApi.salvarRascunho(opcoes.formularioId, { rev: rev.value, ...enviado })
        registrarMudanca()
        if (typeof r?.rev === 'number') rev.value = r.rev
        salvoEm.value = r?.salvo_em ?? new Date().toISOString()
        salvoPorNome.value = null
        // `tem_rascunho: false` quando o normalizado ficou igual ao publicado (o servidor não guarda rascunho).
        temRascunhoServidor.value =
          typeof r?.tem_rascunho === 'boolean' ? r.tem_rascunho : !!r?.rascunho && chaveCanonica(documentoDe(r.rascunho.perguntas, r.rascunho.tema, r.rascunho.finais)) !== chaveCanonica(publicado.value)
        problemasServidor.value = problemasDoServidor(r?.problemas ?? {}, enviado, r?.avisos)
        versaoDosProblemas.value = versao
        docServidor = JSON.stringify(enviado)
        if (r?.rascunho) mesclar(enviado, r.rascunho)
        // Sem mudança durante o envio, a tela (já com o normalizado) é o que o servidor tem.
        if (versaoLocal === versao) docServidor = serializar()
        versaoSalva = versao
        erroSalvar.value = null
        estado.value = versaoLocal === versaoSalva ? 'salvo' : 'pendente'
      } catch (e) {
        if (e instanceof ApiError && e.status === 409 && e.codigo === 'rascunho_desatualizado') {
          estado.value = 'conflito'
          conflito.value = lerConflito(e)
        } else if (e instanceof ApiError && e.status === 422) {
          estado.value = 'erro'
          erroSalvar.value = e.mensagem
          problemasServidor.value = problemasDoServidor(e.campos, enviado)
          versaoDosProblemas.value = versao
        } else {
          estado.value = 'erro'
          erroSalvar.value = mensagemDoErro(e)
        }
      } finally {
        emVoo = null
      }
    })()
    await emVoo
    // (o estado mudou durante o envio: lê de novo)
    const depois = estado.value as EstadoSalvamento
    if (depois === 'pendente') agendar()
    return depois === 'salvo'
  }

  function lerConflito(e: ApiError): ConflitoRascunho {
    const d = e.dados ?? {}
    const extra = (d.detalhes ?? d.dados ?? {}) as Record<string, unknown>
    const pegar = (k: string) => (d[k] ?? extra[k] ?? null) as never
    return { rev: pegar('rev'), salvo_em: pegar('salvo_em'), salvo_por_nome: pegar('salvo_por_nome') }
  }

  // ── problemas ──
  const problemasLocais = computed(() =>
    validarDocumento(
      { perguntas: doc.perguntas, tema: doc.tema, finais: doc.finais },
      { padrao: formulario.value?.padrao_nps ? 'nps' : formulario.value?.padrao_csat ? 'csat' : null },
    ),
  )
  /**
   * Todos: os do site (na hora), os do último rascunho salvo e os da última tentativa de publicar (por id). Os do
   * servidor só enquanto o documento está como foi enviado (mudou: esperam a próxima resposta) e só nos campos em que
   * o site não achou nada (o mesmo problema com outras palavras não aparece duas vezes).
   */
  const problemas = computed(() => {
    const atuais = new Set([...doc.perguntas.map((p) => p.id), ...doc.finais.map((f) => f.id)])
    const ainda = (p: Problema) => !('id' in p.alvo) || atuais.has(p.alvo.id)
    const locais = problemasLocais.value
    const campo = (p: Problema) => `${p.alvo.tipo}:${'id' in p.alvo ? p.alvo.id : ''}:${p.campo ?? ''}:${p.aviso ? 1 : 0}`
    const cobertos = new Set(locais.map(campo))
    const doServidor = versaoTela.value === versaoDosProblemas.value ? problemasServidor.value.filter((p) => ainda(p) && !cobertos.has(campo(p))) : []
    return juntarProblemas(locais, doServidor, errosPublicar.value.filter(ainda))
  })
  const erros = computed(() => problemas.value.filter((p) => !p.aviso))

  // ── alterações ──
  const temAlteracoes = computed(() => chaveCanonica(doc) !== chaveCanonica(publicado.value))
  const temRascunho = computed(() => temAlteracoes.value || temRascunhoServidor.value)

  // ── publicar, descartar, recarregar ──

  type ResultadoPublicar = 'publicado' | 'problemas' | 'erro' | 'conflito' | 'sem_alteracoes'

  async function publicar(): Promise<{ resultado: ResultadoPublicar; mensagem?: string }> {
    if (publicando.value) return { resultado: 'erro' }
    errosPublicar.value = []
    const ok = await salvar()
    if (!ok) return { resultado: estado.value === 'conflito' ? 'conflito' : 'erro', mensagem: erroSalvar.value ?? undefined }
    if (erros.value.length) {
      painelProblemas.value = true
      return { resultado: 'problemas' }
    }
    publicando.value = true
    try {
      const f = await formulariosApi.publicar(opcoes.formularioId, rev.value)
      const atual = formulario.value
      aplicarFormulario({ ...(atual ?? {}), ...f, rascunho: null } as Formulario)
      if (typeof f?.rascunho_rev === 'number') rev.value = f.rascunho_rev
      return { resultado: 'publicado' }
    } catch (e) {
      if (e instanceof ApiError && e.status === 409 && e.codigo === 'rascunho_desatualizado') {
        estado.value = 'conflito'
        conflito.value = lerConflito(e)
        return { resultado: 'conflito' }
      }
      if (e instanceof ApiError && e.status === 409 && e.codigo === 'sem_rascunho') return { resultado: 'sem_alteracoes', mensagem: e.mensagem }
      if (e instanceof ApiError && e.status === 422) {
        errosPublicar.value = problemasDoServidor(Object.keys(e.campos).length ? e.campos : { perguntas: e.mensagem }, {
          perguntas: doc.perguntas,
          tema: doc.tema,
          finais: doc.finais,
        })
        painelProblemas.value = true
        return { resultado: 'problemas', mensagem: e.mensagem }
      }
      return { resultado: 'erro', mensagem: mensagemDoErro(e) }
    } finally {
      publicando.value = false
    }
  }

  /** Descarta o rascunho: o documento volta ao publicado (o desfazer ainda traz as alterações de volta). */
  async function descartar(): Promise<{ ok: boolean; mensagem?: string }> {
    if (espera) clearTimeout(espera)
    espera = null
    if (emVoo) await emVoo
    descartando.value = true
    try {
      await formulariosApi.descartarRascunho(opcoes.formularioId)
    } catch (e) {
      descartando.value = false
      return { ok: false, mensagem: mensagemDoErro(e) }
    }
    // O que estava na tela vira um passo no desfazer: "Desfazer" logo depois traz as alterações de volta.
    registrarMudanca()
    desfazer_.push({ doc: ultimo, selecionado: selecionado.value })
    if (desfazer_.length > MAX_HISTORICO) desfazer_.shift()
    refazer_.length = 0
    contarHistorico()
    try {
      const f = await formulariosApi.obter(opcoes.formularioId)
      aplicarFormulario({ ...f, rascunho: null })
    } catch {
      // Sem conseguir buscar de novo: volta ao publicado que já temos (o rev sobe 1 no descarte).
      aplicarDocumento(clonar(publicado.value))
      docServidor = ultimo
      rev.value += 1
      temRascunhoServidor.value = false
      versaoSalva = versaoLocal
      estado.value = 'salvo'
    } finally {
      descartando.value = false
    }
    return { ok: true }
  }

  /** Conflito: carrega o que está no servidor (as mudanças daqui se perdem). */
  async function recarregar(): Promise<{ ok: boolean; mensagem?: string }> {
    if (espera) clearTimeout(espera)
    espera = null
    try {
      const f = await formulariosApi.obter(opcoes.formularioId)
      aplicarFormulario(f, { limparHistorico: true })
      return { ok: true }
    } catch (e) {
      return { ok: false, mensagem: mensagemDoErro(e) }
    }
  }

  /** Há mudança que ainda não chegou ao servidor? (sair da página pede confirmação) */
  function pendente(): boolean {
    registrarMudanca()
    return versaoLocal !== versaoSalva || estado.value === 'salvando' || estado.value === 'erro' || estado.value === 'conflito'
  }

  function encerrar() {
    if (espera) clearTimeout(espera)
    espera = null
  }

  return {
    formulario,
    doc,
    publicado,
    rev,
    estado,
    erroSalvar,
    conflito,
    salvoEm,
    salvoPorNome,
    temRascunhoServidor,
    temAlteracoes,
    temRascunho,
    problemas,
    erros,
    problemasLocais,
    problemasServidor,
    errosPublicar,
    publicando,
    descartando,
    selecionado,
    painelProblemas,
    pedidoFoco,
    pedirFoco,
    historico: tamanhoHistorico,
    aplicarFormulario,
    mudar,
    desfazer,
    refazer,
    salvar,
    publicar,
    descartar,
    recarregar,
    pendente,
    encerrar,
    registrarMudanca,
  }
}

export type ControleEditor = ReturnType<typeof criarEditor>

const CHAVE: InjectionKey<ControleEditor> = Symbol('editor-formulario')

export function fornecerEditor(controle: ControleEditor) {
  provide(CHAVE, controle)
}

export function usarEditor(): ControleEditor {
  const c = inject(CHAVE, null)
  if (!c) throw new Error('usarEditor() fora do editor de formulário')
  return c
}

/** O editor, se houver (componentes que também aparecem fora dele, como a Aparência nos testes). */
export function usarEditorOpcional(): ControleEditor | null {
  return inject(CHAVE, null)
}

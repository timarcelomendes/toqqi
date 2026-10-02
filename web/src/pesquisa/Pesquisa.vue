<script setup lang="ts">
// Pesquisa que o cliente responde. É o MESMO componente da página pública (/r e /f)
// e da pré-visualização do editor. Não importa Pinia, router nem ícones externos.
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import CampoPergunta from './CampoPergunta.vue'
import CartaoIndicacao from './CartaoIndicacao.vue'
import { corDoTexto, corValida } from './cor'
import { lerConviteIndicacao, notaDaDireitoAIndicacao } from './indicacao'
import { faixa, paginasVisiveis, perguntaPrincipal, perguntasVisiveis, respostasParaEnvio } from './logica'
import { renderizarVariaveis } from './variaveis'
import { validarPerguntas, validarResposta } from './validacao'
import {
  TEMA_PADRAO,
  type ConviteIndicacao,
  type DadosIndicacao,
  type FormularioPublico,
  type Pergunta,
  type Respostas,
  type TelaFinal,
  type ValorResposta,
  type Variaveis,
} from './tipos'

/** Erro que `enviar` pode lançar: mensagem para mostrar e, se houver, erros por pergunta. */
export interface ErroEnvio {
  mensagem?: string
  campos?: Record<string, string>
}

const props = withDefaults(
  defineProps<{
    formulario: FormularioPublico
    variaveis?: Partial<Variaveis>
    /** ?nota=N: já marca a nota principal e começa depois dela. */
    notaInicial?: number | null
    /** Envia as respostas. Devolve a tela final, ou null se quem chamou assumiu (ex.: "já respondido"). Sem ela: pré-visualização. */
    enviar?: (respostas: Respostas) => Promise<TelaFinal | null>
    /** Dentro de iframe (embed=1): sem margens de fora. */
    compacto?: boolean
    /** Pré-visualização do editor: mostra aviso e botão de recomeçar. */
    previa?: boolean
    /** Etapa 5c: envia uma indicação (convite individual) e devolve a mensagem de obrigado. Sem ela, o cartão é exemplo. */
    indicar?: (dados: DadosIndicacao) => Promise<string | void>
    /**
     * Etapa 5c, pré-visualização: o convite de exemplo, pedido quando a pesquisa termina com nota de promotor (NPS 9–10
     * ou CSAT 5); null não mostra o cartão (ex.: indicações desligadas na conta).
     */
    indicacaoExemplo?: () => Promise<ConviteIndicacao | null>
  }>(),
  { variaveis: () => ({}), notaInicial: null, compacto: false, previa: false, indicar: undefined, indicacaoExemplo: undefined },
)

const tema = computed(() => ({ ...TEMA_PADRAO, ...(props.formulario.tema ?? {}) }))
const cor = computed(() => corValida(tema.value.cor))
const estiloCor = computed(() => ({
  '--cor': cor.value,
  '--cor-texto': corDoTexto(cor.value),
  '--cor-suave': `color-mix(in srgb, ${cor.value} 10%, white)`,
}))
const perguntas = computed<Pergunta[]>(() => props.formulario.perguntas ?? [])
const principal = computed(() => perguntaPrincipal(perguntas.value))
const umaPorVez = computed(() => tema.value.modo !== 'paginas')
const v = (t: string | null | undefined) => renderizarVariaveis(t, props.variaveis)

const respostas = reactive<Respostas>({})
const erros = reactive<Record<string, string>>({})
const etapa = ref<'abertura' | 'perguntas' | 'final'>('perguntas')
const indice = ref(0)
const enviando = ref(false)
const erroEnvio = ref<string | null>(null)
const telaFinal = ref<TelaFinal | null>(null)
/** Etapa 5c: o convite de indicação da tela final (da API ou, na pré-visualização, o de exemplo). */
const indicacao = ref<ConviteIndicacao | null>(null)
let pedidoExemplo = 0
const raiz = ref<HTMLElement | null>(null)
const anuncio = ref('')
let temporizador: ReturnType<typeof setTimeout> | null = null

const visiveis = computed(() => perguntasVisiveis(perguntas.value, respostas))
const paginas = computed(() => paginasVisiveis(perguntas.value, respostas))
const total = computed(() => (umaPorVez.value ? visiveis.value.length : paginas.value.length))
const atuais = computed<Pergunta[]>(() => {
  if (umaPorVez.value) {
    const p = visiveis.value[indice.value]
    return p ? [p] : []
  }
  return paginas.value[indice.value] ?? []
})
const ultima = computed(() => indice.value >= total.value - 1)
const progresso = computed(() => (total.value ? Math.round(((indice.value + (etapa.value === 'final' ? 1 : 0)) / total.value) * 100) : 0))
const temAbertura = computed(() => !!(tema.value.titulo_abertura?.trim() || tema.value.texto_abertura?.trim()))

function limparObjeto(o: Record<string, unknown>) {
  for (const k of Object.keys(o)) delete o[k]
}

function iniciar() {
  limparObjeto(respostas)
  limparObjeto(erros)
  erroEnvio.value = null
  telaFinal.value = null
  indicacao.value = null
  pedidoExemplo++
  indice.value = 0
  etapa.value = temAbertura.value && props.notaInicial === null ? 'abertura' : 'perguntas'
  const p = principal.value
  const n = props.notaInicial
  if (p && typeof n === 'number') {
    const { min, max } = faixa(p)
    if (Number.isInteger(n) && n >= min && n <= max) {
      respostas[p.id] = n
      if (umaPorVez.value) {
        const i = visiveis.value.findIndex((q) => q.id === p.id)
        indice.value = Math.min(i + 1, Math.max(0, visiveis.value.length - 1))
      } else {
        const pg = paginas.value.findIndex((pag) => pag.some((q) => q.id === p.id))
        const sozinha = (paginas.value[pg]?.length ?? 0) === 1
        indice.value = Math.min(sozinha ? pg + 1 : pg, Math.max(0, paginas.value.length - 1))
      }
    }
  }
}

// Se as perguntas mudarem (editor), mantém a posição válida.
watch(total, (t) => {
  if (indice.value > t - 1) indice.value = Math.max(0, t - 1)
})
// Fontes separadas: só reinicia quando a nota inicial ou o modo mudam de fato.
watch([() => props.notaInicial, () => tema.value.modo], iniciar)

function atualizar(p: Pergunta, valor: ValorResposta | undefined) {
  if (valor === undefined) delete respostas[p.id]
  else respostas[p.id] = valor
  if (erros[p.id]) delete erros[p.id]
}

async function focarTopo(idPergunta?: string) {
  await nextTick()
  const alvo = idPergunta
    ? raiz.value?.querySelector<HTMLElement>(`[data-pergunta="${idPergunta}"] [data-titulo-pergunta]`)
    : raiz.value?.querySelector<HTMLElement>('[data-titulo-pergunta], [data-titulo-tela]')
  alvo?.focus({ preventScroll: true })
  if (!props.previa) (alvo ?? raiz.value)?.scrollIntoView?.({ block: 'nearest', behavior: 'smooth' })
}

function validarAtuais(): boolean {
  const e = validarPerguntas(atuais.value, respostas)
  limparObjeto(erros)
  Object.assign(erros, e)
  const primeira = atuais.value.find((p) => e[p.id])
  if (primeira) {
    anuncio.value = e[primeira.id]!
    focarTopo(primeira.id)
    return false
  }
  return true
}

function cancelarAvanco() {
  if (temporizador) clearTimeout(temporizador)
  temporizador = null
}

async function avancar() {
  cancelarAvanco()
  if (enviando.value || !validarAtuais()) return
  if (ultima.value) return enviarTudo()
  indice.value++
  anuncio.value = umaPorVez.value ? `Pergunta ${indice.value + 1} de ${total.value}` : `Página ${indice.value + 1} de ${total.value}`
  focarTopo()
}

function voltar() {
  cancelarAvanco()
  if (indice.value > 0) {
    indice.value--
    limparObjeto(erros)
    focarTopo()
  } else if (temAbertura.value) {
    etapa.value = 'abertura'
    focarTopo()
  }
}

function aoEscolher(p: Pergunta) {
  // Avança sozinho ao tocar numa nota (modo uma por vez), menos na última pergunta.
  if (!umaPorVez.value || ultima.value) return
  if (!['nps', 'csat', 'estrelas', 'escala', 'sim_nao'].includes(p.tipo)) return
  cancelarAvanco()
  temporizador = setTimeout(() => {
    temporizador = null
    if (atuais.value[0]?.id === p.id && !validarResposta(p, respostas[p.id])) avancar()
  }, 320)
}

/** Posiciona na pergunta com erro (vindo do servidor). */
function irParaPergunta(id: string) {
  if (umaPorVez.value) {
    const i = visiveis.value.findIndex((p) => p.id === id)
    if (i >= 0) indice.value = i
  } else {
    const i = paginas.value.findIndex((pg) => pg.some((p) => p.id === id))
    if (i >= 0) indice.value = i
  }
  etapa.value = 'perguntas'
  focarTopo(id)
}

/** A API pode mandar `respostas.<id>`, `<id>` ou `respostas.<id>.<algo>`. */
function lerCamposServidor(campos: Record<string, string>): Record<string, string> {
  const ids = new Set(perguntas.value.map((p) => p.id))
  const saida: Record<string, string> = {}
  for (const [chave, msg] of Object.entries(campos)) {
    const partes = chave.split('.')
    const id = partes.find((x) => ids.has(x))
    if (id && !saida[id]) saida[id] = msg
  }
  return saida
}

async function enviarTudo() {
  // Confere tudo o que está visível (no modo páginas o usuário pode ter voltado e mudado algo).
  const todas = visiveis.value
  const e = validarPerguntas(todas, respostas)
  if (Object.keys(e).length) {
    limparObjeto(erros)
    Object.assign(erros, e)
    irParaPergunta(todas.find((p) => e[p.id])!.id)
    return
  }
  erroEnvio.value = null
  if (!props.enviar) {
    telaFinal.value = { titulo_final: tema.value.titulo_final, texto_final: tema.value.texto_final }
    etapa.value = 'final'
    focarTopo()
    void mostrarIndicacaoExemplo()
    return
  }
  enviando.value = true
  try {
    const r = await props.enviar(respostasParaEnvio(perguntas.value, respostas))
    if (r === null) return
    telaFinal.value = {
      titulo_final: r?.titulo_final || tema.value.titulo_final,
      texto_final: r?.texto_final ?? tema.value.texto_final,
    }
    indicacao.value = lerConviteIndicacao(r?.indicacao)
    etapa.value = 'final'
    focarTopo()
  } catch (err) {
    const erro = (err ?? {}) as ErroEnvio
    const porPergunta = erro.campos ? lerCamposServidor(erro.campos) : {}
    const primeira = visiveis.value.find((p) => porPergunta[p.id])
    if (primeira) {
      limparObjeto(erros)
      Object.assign(erros, porPergunta)
      irParaPergunta(primeira.id)
    } else {
      erroEnvio.value = erro.mensagem || 'Não conseguimos enviar agora. Confira sua internet e tente de novo.'
    }
  } finally {
    enviando.value = false
  }
}

/** Pré-visualização: com nota de promotor na pergunta principal, mostra o cartão de indicação de exemplo. */
async function mostrarIndicacaoExemplo() {
  const p = principal.value
  if (!props.indicacaoExemplo || !p || !notaDaDireitoAIndicacao(p.tipo, respostas[p.id])) return
  const meu = ++pedidoExemplo
  try {
    const c = await props.indicacaoExemplo()
    if (meu === pedidoExemplo && etapa.value === 'final') indicacao.value = c
  } catch {
    /* sem o exemplo, a tela final fica como está */
  }
}

function comecar() {
  etapa.value = 'perguntas'
  focarTopo()
}

// Teclado: 0–9 no NPS (1 e depois 0 rápido = 10); Enter avança.
let digitoPendente: { n: number; ate: number } | null = null
function aoTeclar(e: KeyboardEvent) {
  if (etapa.value !== 'perguntas' || !umaPorVez.value || e.ctrlKey || e.metaKey || e.altKey) return
  const alvo = e.target as HTMLElement | null
  if (alvo && (alvo.tagName === 'TEXTAREA' || (alvo.tagName === 'INPUT' && !['radio', 'checkbox'].includes((alvo as HTMLInputElement).type)))) return
  if (props.previa && raiz.value && !raiz.value.contains(alvo)) return
  const p = atuais.value[0]
  if (!p || p.tipo !== 'nps' || !/^\d$/.test(e.key)) return
  e.preventDefault()
  const n = Number(e.key)
  const agora = Date.now()
  if (n === 0 && digitoPendente?.n === 1 && agora < digitoPendente.ate) {
    digitoPendente = null
    atualizar(p, 10)
  } else {
    digitoPendente = n === 1 ? { n, ate: agora + 700 } : null
    atualizar(p, n)
  }
  anuncio.value = `Nota ${respostas[p.id]}`
  // Espera um pouco para permitir o "10".
  cancelarAvanco()
  if (!ultima.value) {
    temporizador = setTimeout(() => {
      temporizador = null
      avancar()
    }, n === 1 ? 750 : 400)
  }
}

onMounted(() => {
  iniciar()
  document.addEventListener('keydown', aoTeclar)
})
onBeforeUnmount(() => {
  cancelarAvanco()
  document.removeEventListener('keydown', aoTeclar)
})

defineExpose({ recomecar: iniciar, irParaPergunta })
</script>

<template>
  <div
    ref="raiz"
    class="pesquisa w-full text-slate-900"
    :class="compacto ? '' : 'mx-auto max-w-xl px-4 py-6 sm:py-10'"
    :style="estiloCor"
  >
    <div class="overflow-hidden bg-white" :class="compacto ? '' : 'rounded-2xl border border-slate-200 shadow-sm'">
      <!-- Barra de progresso -->
      <div
        v-if="umaPorVez && etapa !== 'abertura' && total > 1"
        class="h-1.5 bg-slate-100"
        role="progressbar"
        :aria-valuenow="progresso"
        aria-valuemin="0"
        aria-valuemax="100"
        aria-label="Progresso da pesquisa"
      >
        <div class="h-full bg-[var(--cor)] transition-all duration-300" :style="{ width: `${progresso}%` }" />
      </div>

      <div :class="compacto ? 'p-4 sm:p-6' : 'p-5 sm:p-8'">
        <header v-if="tema.logo_url" class="mb-6 flex">
          <img :src="tema.logo_url" alt="" class="max-h-12 max-w-[60%] object-contain" />
        </header>

        <!-- Abertura -->
        <section v-if="etapa === 'abertura'" class="flex flex-col items-start gap-3">
          <h1 tabindex="-1" data-titulo-tela class="text-2xl font-extrabold leading-tight text-slate-900 focus:outline-none">
            {{ v(tema.titulo_abertura) || v(formulario.nome) }}
          </h1>
          <p v-if="tema.texto_abertura" class="whitespace-pre-line text-base text-slate-600">{{ v(tema.texto_abertura) }}</p>
          <button
            type="button"
            class="mt-3 inline-flex h-12 items-center justify-center rounded-xl bg-[var(--cor)] px-6 text-base font-bold text-[var(--cor-texto)] shadow-sm transition hover:brightness-95 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-slate-900"
            @click="comecar"
          >
            Começar
          </button>
        </section>

        <!-- Final -->
        <section v-else-if="etapa === 'final'" class="flex flex-col items-center gap-3 py-6 text-center">
          <span class="flex size-16 items-center justify-center rounded-full bg-[var(--cor-suave)] text-[var(--cor)]" aria-hidden="true">
            <svg viewBox="0 0 24 24" class="size-9" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12.5l4.5 4.5L19 7.5" /></svg>
          </span>
          <h1 tabindex="-1" data-titulo-tela class="text-2xl font-extrabold text-slate-900 focus:outline-none">{{ v(telaFinal?.titulo_final) }}</h1>
          <p v-if="telaFinal?.texto_final" class="max-w-md whitespace-pre-line text-base text-slate-600">{{ v(telaFinal.texto_final) }}</p>
          <CartaoIndicacao v-if="indicacao" class="mt-3" :convite="indicacao" :empresa="variaveis.empresa ?? ''" :enviar="indicar" />
          <button v-if="previa" type="button" class="mt-4 text-sm font-semibold text-slate-600 underline underline-offset-4 hover:text-slate-900" @click="iniciar">
            Ver de novo
          </button>
        </section>

        <!-- Perguntas -->
        <form v-else novalidate @submit.prevent="avancar">
          <p v-if="!total" class="py-8 text-center text-slate-500">Esta pesquisa ainda não tem perguntas.</p>
          <template v-else>
            <p v-if="umaPorVez && total > 1" class="mb-3 text-xs font-semibold uppercase tracking-wide text-slate-500">
              Pergunta {{ indice + 1 }} de {{ total }}
            </p>
            <p v-else-if="!umaPorVez && total > 1" class="mb-3 text-xs font-semibold uppercase tracking-wide text-slate-500">
              Página {{ indice + 1 }} de {{ total }}
            </p>
            <div class="flex flex-col gap-8">
              <CampoPergunta
                v-for="p in atuais"
                :key="p.id"
                :pergunta="p"
                :model-value="respostas[p.id]"
                :erro="erros[p.id]"
                :variaveis="variaveis"
                @update:model-value="(valor) => atualizar(p, valor)"
                @escolheu="aoEscolher(p)"
              />
            </div>

            <div v-if="erroEnvio" role="alert" class="mt-6 rounded-xl border border-red-200 bg-red-50 p-3.5 text-sm text-red-800">
              {{ erroEnvio }}
            </div>

            <div class="mt-8 flex items-center gap-3">
              <button
                v-if="indice > 0 || temAbertura"
                type="button"
                class="inline-flex h-12 items-center gap-1.5 rounded-xl px-3 text-sm font-semibold text-slate-600 hover:bg-slate-100 focus-visible:outline-2 focus-visible:outline-slate-900"
                :disabled="enviando"
                @click="voltar"
              >
                <svg viewBox="0 0 24 24" class="size-4" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" aria-hidden="true"><path d="M15 18l-6-6 6-6" /></svg>
                Voltar
              </button>
              <button
                type="submit"
                class="ml-auto inline-flex h-12 min-w-32 items-center justify-center gap-2 rounded-xl bg-[var(--cor)] px-6 text-base font-bold text-[var(--cor-texto)] shadow-sm transition hover:brightness-95 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-slate-900 disabled:opacity-60"
                :disabled="enviando"
                :aria-busy="enviando || undefined"
              >
                <svg v-if="enviando" viewBox="0 0 24 24" class="size-5 animate-spin" fill="none" stroke="currentColor" stroke-width="2.5" aria-hidden="true"><path d="M12 3a9 9 0 1 0 9 9" stroke-linecap="round" /></svg>
                <template v-if="erroEnvio && ultima">Tentar de novo</template>
                <template v-else>{{ ultima ? tema.texto_botao || 'Enviar' : 'Continuar' }}</template>
              </button>
            </div>
          </template>
        </form>
      </div>
    </div>
    <p class="sr-only" aria-live="polite">{{ anuncio }}</p>
  </div>
</template>

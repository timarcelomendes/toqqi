<script setup lang="ts">
// Desenha uma pergunta da pesquisa (todos os tipos). Usado pela página pública e
// pela pré-visualização do editor. Sem ícones externos: tudo em SVG inline.
import { computed, ref, useId } from 'vue'
import { faixa } from './logica'
import { renderizarVariaveis } from './variaveis'
import { LIMITE_COMENTARIO, LIMITE_TEXTO_CURTO } from './validacao'
import type { Pergunta, ValorResposta, Variaveis } from './tipos'

const props = defineProps<{
  pergunta: Pergunta
  modelValue: ValorResposta | undefined
  erro?: string | null
  variaveis?: Partial<Variaveis>
  /** Número mostrado antes do título (modo páginas). */
  numero?: number
  /** Etapa 5l: a ordem das opções para quem responde (embaralhada uma vez por visita); sem ela, a ordem salva. */
  ordemOpcoes?: string[]
  /** Etapa 5l: troca as citações `{{id}}` do título e da descrição pelas respostas (depois das variáveis). */
  citar?: (texto: string) => string
}>()
const emit = defineEmits<{
  'update:modelValue': [ValorResposta | undefined]
  /** Tocou numa nota/opção única: quem usa pode avançar sozinho. */
  escolheu: []
}>()

const id = `pq-${useId()}`
const idTitulo = `${id}-titulo`
const idDesc = `${id}-desc`
const idErro = `${id}-erro`
const comCitacoes = (t: string) => (props.citar && t.includes('{{') ? props.citar(t) : t)
const titulo = computed(() => comCitacoes(renderizarVariaveis(props.pergunta.titulo, props.variaveis)))
const descricao = computed(() => comCitacoes(renderizarVariaveis(props.pergunta.descricao, props.variaveis)))
/** As opções na ordem de quem responde (a resposta da múltipla continua na ordem salva). */
const opcoes = computed(() => props.ordemOpcoes ?? props.pergunta.opcoes ?? [])
/** Escolha múltipla: no máximo N (etapa 5l). */
const maxSelecoes = computed(() => {
  const m = props.pergunta.max_selecoes
  return props.pergunta.tipo === 'escolha_multipla' && typeof m === 'number' && m > 0 ? m : null
})
const marcadas = computed(() => (Array.isArray(props.modelValue) ? props.modelValue : []))
const noLimite = computed(() => maxSelecoes.value !== null && marcadas.value.length >= maxSelecoes.value)
/** Anúncio do limite para leitores de tela (no momento em que ele é atingido). */
const anuncioLimite = ref('')
const descritoPor = computed(() => [descricao.value ? idDesc : '', props.erro ? idErro : ''].filter(Boolean).join(' ') || undefined)
const notas = computed(() => {
  const { min, max } = faixa(props.pergunta)
  return Array.from({ length: Math.max(0, max - min + 1) }, (_, i) => min + i)
})
const estrelaHover = ref<number | null>(null)

// Só avança sozinho em toque/clique. Com teclado, as setas trocam a opção dentro do grupo
// e a pessoa confirma com Enter (senão ela seria levada adiante no meio da escolha).
let viaPonteiro = false
function marcarPonteiro() {
  viaPonteiro = true
}
function marcarTeclado() {
  viaPonteiro = false
}

function escolher(v: ValorResposta) {
  emit('update:modelValue', v)
  if (viaPonteiro) emit('escolheu')
}

function alternarMultipla(opcao: string, marcado: boolean) {
  const atual = Array.isArray(props.modelValue) ? props.modelValue : []
  const novo = marcado ? [...atual.filter((o) => o !== opcao), opcao] : atual.filter((o) => o !== opcao)
  // Mantém a ordem das opções (a salva, mesmo com a ordem embaralhada na tela).
  const valor = (props.pergunta.opcoes ?? []).filter((o) => novo.includes(o))
  emit('update:modelValue', valor)
  anuncioLimite.value = maxSelecoes.value !== null && valor.length >= maxSelecoes.value ? `Você pode escolher até ${maxSelecoes.value} opções.` : ''
}

/** Lista suspensa (escolha única com `exibicao: 'lista'`): vazio volta a "sem resposta". */
function escolherNaLista(e: Event) {
  const v = (e.target as HTMLSelectElement).value
  emit('update:modelValue', v === '' ? undefined : v)
}

function texto(e: Event) {
  emit('update:modelValue', (e.target as HTMLInputElement | HTMLTextAreaElement).value)
}

/** NPS: 0–6 vermelho, 7–8 amarelo, 9–10 verde. */
function classeNps(n: number, marcado: boolean) {
  if (n <= 6) return marcado ? 'bg-red-600 border-red-600 text-white' : 'border-red-200 text-red-700 bg-red-50 hover:bg-red-100'
  if (n <= 8) return marcado ? 'bg-amber-500 border-amber-500 text-slate-900' : 'border-amber-200 text-amber-800 bg-amber-50 hover:bg-amber-100'
  return marcado ? 'bg-emerald-600 border-emerald-600 text-white' : 'border-emerald-200 text-emerald-700 bg-emerald-50 hover:bg-emerald-100'
}

/** Escala numérica: a nota marcada na cor da pesquisa. */
function classeEscala(marcado: boolean) {
  return marcado ? 'border-[var(--cor)] bg-[var(--cor)] text-[var(--cor-texto)]' : 'border-slate-200 bg-white text-slate-700 hover:border-slate-300'
}

/**
 * Régua de notas (NPS e escala numérica). Etapa 5h: com o cartão da pesquisa estreito (menos de 420 px, o container
 * `pesquisa` do Pesquisa.vue), o NPS vai em duas linhas — 0–5 e 6–10, a segunda no meio da primeira — com cada nota de
 * pelo menos 44 × 44 px; "Nada provável" fica embaixo do 0 e "Muito provável" embaixo do 10. Cartão largo: uma linha,
 * como antes. A escala com mais de 7 notas (até 0–10) faz o mesmo; a de até 7 fica sempre numa linha. A ordem no DOM
 * não muda (0, 1, … 10): as setas do teclado e o avanço automático seguem iguais.
 * Grade estreita: cada nota ocupa 2 de 2 × (notas da 1ª linha) colunas; a 2ª linha começa na coluna 2 quando tem uma
 * nota a menos (fica no meio). Linhas: 1 e 3 as notas, 2 e 4 os rótulos.
 */
const regua = computed(() => {
  const total = notas.value.length
  const duasLinhas = props.pergunta.tipo === 'nps' || total > 7
  const primeiraLinha = Math.ceil(total / 2)
  const noMeio = total - primeiraLinha < primeiraLinha
  return {
    duasLinhas,
    primeiraLinha,
    noMeio,
    // --fim: a linha da grade onde termina a última nota (o rótulo máximo termina junto dela)
    estilo: { '--colunas': String(2 * primeiraLinha), '--total': String(total), '--fim': String(noMeio ? 2 * primeiraLinha : 2 * primeiraLinha + 1) },
  }
})
const CLASSE_REGUA_DUAS_LINHAS =
  'grid-cols-[repeat(var(--colunas),minmax(0,1fr))] gap-x-1 gap-y-1 @min-[420px]/pesquisa:grid-cols-[repeat(var(--total),minmax(0,1fr))] @min-[420px]/pesquisa:gap-x-1.5'
const CLASSE_REGUA_UMA_LINHA = 'grid-cols-[repeat(var(--total),minmax(0,1fr))] gap-1.5'
function classeLugarNota(i: number) {
  const r = regua.value
  if (!r.duasLinhas) return ''
  const linha = i < r.primeiraLinha ? 'row-start-1' : 'row-start-3'
  const inicio = i === r.primeiraLinha && r.noMeio ? 'col-start-2 @min-[420px]/pesquisa:col-start-auto' : ''
  return `${linha} ${inicio} col-span-2 @min-[420px]/pesquisa:col-span-1 @min-[420px]/pesquisa:row-start-1`
}
/** Nome da nota para o leitor de tela: a primeira e a última levam os rótulos ("0 (Nada provável)"). */
function rotuloNota(n: number) {
  const { min, max } = faixa(props.pergunta)
  return `${n}${n === min && rotuloMin.value ? ` (${rotuloMin.value})` : ''}${n === max && rotuloMax.value ? ` (${rotuloMax.value})` : ''}`
}

const ROSTOS = [
  { valor: 1, rotulo: 'Muito insatisfeito', cor: '#dc2626', boca: 'M8 17c2-2.5 6-2.5 8 0' },
  { valor: 2, rotulo: 'Insatisfeito', cor: '#ea580c', boca: 'M8.5 16.5c1.8-1.2 5.2-1.2 7 0' },
  { valor: 3, rotulo: 'Neutro', cor: '#ca8a04', boca: 'M8.5 15.5h7' },
  { valor: 4, rotulo: 'Satisfeito', cor: '#65a30d', boca: 'M8.5 14.5c1.8 1.4 5.2 1.4 7 0' },
  { valor: 5, rotulo: 'Muito satisfeito', cor: '#059669', boca: 'M8 14c2 3 6 3 8 0' },
]

const rotuloMin = computed(() =>
  props.pergunta.rotulo_min ?? (props.pergunta.tipo === 'nps' ? 'Nada provável' : props.pergunta.tipo === 'escala' ? '' : ''),
)
const rotuloMax = computed(() => props.pergunta.rotulo_max ?? (props.pergunta.tipo === 'nps' ? 'Muito provável' : ''))

const tipoEntrada = computed(() => {
  const f = props.pergunta.formato
  return f === 'email' ? 'email' : f === 'telefone' ? 'tel' : 'text'
})
const modoTeclado = computed(() => {
  const f = props.pergunta.formato
  return f === 'email' ? 'email' : f === 'telefone' ? 'tel' : f === 'numero' ? 'decimal' : 'text'
})
const autocompletar = computed(() => {
  const f = props.pergunta.formato
  return f === 'email' ? 'email' : f === 'telefone' ? 'tel' : 'off'
})
const textoAtual = computed(() => (typeof props.modelValue === 'string' ? props.modelValue : ''))
/** Etapa 5l: o texto de exemplo da pergunta; sem ele, o de sempre. */
const exemploTextoCurto = computed(
  () => props.pergunta.placeholder?.trim() || (props.pergunta.formato === 'email' ? 'seu@email.com' : props.pergunta.formato === 'telefone' ? '(11) 91234-5678' : 'Sua resposta'),
)
const exemploComentario = computed(() => props.pergunta.placeholder?.trim() || 'Escreva aqui, se quiser')

const classeOpcao =
  'flex min-h-12 cursor-pointer items-center gap-3 rounded-xl border-2 px-4 py-2.5 text-[0.95rem] font-medium text-slate-800 transition-colors has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-offset-2 has-[:focus-visible]:outline-[var(--cor)]'
</script>

<template>
  <fieldset
    class="min-w-0"
    @pointerdown="marcarPonteiro"
    @keydown="marcarTeclado"
    :aria-labelledby="idTitulo"
    :aria-describedby="descritoPor"
    :aria-invalid="erro ? 'true' : undefined"
    :data-pergunta="pergunta.id"
  >
    <legend class="sr-only">{{ titulo }}</legend>
    <h2 :id="idTitulo" tabindex="-1" class="text-lg font-bold leading-snug text-slate-900 focus:outline-none sm:text-xl" data-titulo-pergunta>
      <span v-if="numero" class="mr-1 text-slate-400">{{ numero }}.</span>
      {{ titulo }}
      <span v-if="pergunta.obrigatoria" class="text-red-600" aria-hidden="true">*</span>
      <span v-if="pergunta.obrigatoria" class="sr-only">(obrigatória)</span>
    </h2>
    <p v-if="descricao" :id="idDesc" class="mt-1 text-sm text-slate-600">{{ descricao }}</p>

    <div class="mt-4">
      <!-- NPS 0–10 e escala numérica: a régua de notas (em duas linhas no cartão estreito) -->
      <template v-if="pergunta.tipo === 'nps' || pergunta.tipo === 'escala'">
        <div
          role="radiogroup"
          :aria-labelledby="idTitulo"
          class="grid"
          :class="regua.duasLinhas ? CLASSE_REGUA_DUAS_LINHAS : CLASSE_REGUA_UMA_LINHA"
          :style="regua.estilo"
          :data-regua="regua.duasLinhas ? 'duas-linhas' : 'uma-linha'"
        >
          <label v-for="(n, i) in notas" :key="n" class="relative" :class="classeLugarNota(i)" :data-nota="n">
            <input type="radio" :name="id" :value="n" :checked="modelValue === n" class="peer sr-only" :aria-label="rotuloNota(n)" @change="escolher(n)" />
            <span
              class="flex cursor-pointer items-center justify-center rounded-lg border-2 font-bold transition-colors peer-focus-visible:outline-2 peer-focus-visible:outline-offset-2 peer-focus-visible:outline-slate-900"
              :class="pergunta.tipo === 'nps' ? ['h-12 text-base', classeNps(n, modelValue === n)] : ['h-11 text-sm', classeEscala(modelValue === n)]"
              aria-hidden="true"
            >{{ n }}</span>
          </label>
          <!-- Duas linhas: o rótulo mínimo embaixo da primeira nota e o máximo embaixo da última -->
          <template v-if="regua.duasLinhas">
            <span v-if="rotuloMin" class="col-span-full row-start-2 pb-1.5 text-xs text-slate-500 @min-[420px]/pesquisa:hidden" aria-hidden="true" data-rotulo-min>
              {{ rotuloMin }}
            </span>
            <span v-if="rotuloMax" class="row-start-4 text-right text-xs text-slate-500 [grid-column:1/var(--fim)] @min-[420px]/pesquisa:hidden" aria-hidden="true" data-rotulo-max>
              {{ rotuloMax }}
            </span>
          </template>
        </div>
        <div
          v-if="rotuloMin || rotuloMax"
          class="mt-2 justify-between gap-4 text-xs text-slate-500"
          :class="regua.duasLinhas ? 'hidden @min-[420px]/pesquisa:flex' : 'flex'"
          aria-hidden="true"
          data-rotulos-linha
        >
          <span>{{ rotuloMin }}</span><span class="text-right">{{ rotuloMax }}</span>
        </div>
      </template>

      <!-- CSAT: rostos 1–5 -->
      <div v-else-if="pergunta.tipo === 'csat'" role="radiogroup" :aria-labelledby="idTitulo" class="grid grid-cols-5 gap-2">
        <label v-for="r in ROSTOS" :key="r.valor" class="relative">
          <input type="radio" :name="id" :value="r.valor" :checked="modelValue === r.valor" class="peer sr-only" :aria-label="`${r.valor}: ${r.rotulo}`" @change="escolher(r.valor)" />
          <span
            class="flex cursor-pointer flex-col items-center gap-1 rounded-xl border-2 p-2 transition-colors peer-focus-visible:outline-2 peer-focus-visible:outline-offset-2 peer-focus-visible:outline-slate-900"
            :class="modelValue === r.valor ? 'bg-slate-50' : 'border-transparent hover:bg-slate-50'"
            :style="modelValue === r.valor ? { borderColor: r.cor } : undefined"
            aria-hidden="true"
          >
            <svg viewBox="0 0 24 24" class="size-10 sm:size-12" :style="{ color: r.cor, opacity: modelValue === undefined || modelValue === r.valor ? 1 : 0.45 }" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round">
              <circle cx="12" cy="12" r="10" :fill="modelValue === r.valor ? r.cor : 'none'" :fill-opacity="0.15" />
              <circle cx="9" cy="10" r="0.9" fill="currentColor" />
              <circle cx="15" cy="10" r="0.9" fill="currentColor" />
              <path :d="r.boca" />
            </svg>
            <span class="text-center text-[0.7rem] font-medium leading-tight text-slate-600 sm:text-xs">{{ r.rotulo }}</span>
          </span>
        </label>
      </div>

      <!-- Estrelas 1–5 -->
      <div v-else-if="pergunta.tipo === 'estrelas'" role="radiogroup" :aria-labelledby="idTitulo" class="flex gap-1" @mouseleave="estrelaHover = null">
        <label v-for="n in notas" :key="n" class="relative" @mouseenter="estrelaHover = n">
          <input type="radio" :name="id" :value="n" :checked="modelValue === n" class="peer sr-only" :aria-label="`${n} de 5 estrelas`" @change="escolher(n)" />
          <span class="flex size-12 cursor-pointer items-center justify-center rounded-lg peer-focus-visible:outline-2 peer-focus-visible:outline-slate-900" aria-hidden="true">
            <svg viewBox="0 0 24 24" class="size-10" stroke-width="1.5" stroke-linejoin="round"
              :fill="n <= (estrelaHover ?? (typeof modelValue === 'number' ? modelValue : 0)) ? '#f59e0b' : 'none'"
              :stroke="n <= (estrelaHover ?? (typeof modelValue === 'number' ? modelValue : 0)) ? '#d97706' : '#94a3b8'"
            >
              <path d="M12 2.8l2.8 5.8 6.3.9-4.6 4.4 1.1 6.3L12 17.2l-5.6 3 1.1-6.3L2.9 9.5l6.3-.9z" />
            </svg>
          </span>
        </label>
      </div>

      <!-- Texto curto -->
      <div v-else-if="pergunta.tipo === 'texto_curto'">
        <input
          :id="`${id}-entrada`"
          :type="tipoEntrada"
          :inputmode="modoTeclado"
          :autocomplete="autocompletar"
          :value="textoAtual"
          :maxlength="LIMITE_TEXTO_CURTO"
          :aria-labelledby="idTitulo"
          :aria-describedby="descritoPor"
          :aria-invalid="erro ? 'true' : undefined"
          class="h-12 w-full rounded-xl border-2 border-slate-200 bg-white px-4 text-base text-slate-900 placeholder:text-slate-400 focus:border-[var(--cor)] focus:outline-none"
          :placeholder="exemploTextoCurto"
          @input="texto"
        />
      </div>

      <!-- Comentário -->
      <div v-else-if="pergunta.tipo === 'comentario'">
        <textarea
          :value="textoAtual"
          rows="4"
          :maxlength="LIMITE_COMENTARIO"
          :aria-labelledby="idTitulo"
          :aria-describedby="descritoPor"
          :aria-invalid="erro ? 'true' : undefined"
          class="w-full resize-y rounded-xl border-2 border-slate-200 bg-white px-4 py-3 text-base text-slate-900 placeholder:text-slate-400 focus:border-[var(--cor)] focus:outline-none"
          :placeholder="exemploComentario"
          @input="texto"
        />
        <p v-if="textoAtual.length > LIMITE_COMENTARIO * 0.8" class="mt-1 text-right text-xs text-slate-500">{{ textoAtual.length }} de {{ LIMITE_COMENTARIO }}</p>
      </div>

      <!-- Escolha única em lista suspensa (etapa 5l): boa para muitas opções -->
      <div v-else-if="pergunta.tipo === 'escolha_unica' && pergunta.exibicao === 'lista'" class="relative">
        <select
          :id="`${id}-lista`"
          :value="typeof modelValue === 'string' ? modelValue : ''"
          :aria-labelledby="idTitulo"
          :aria-describedby="descritoPor"
          :aria-invalid="erro ? 'true' : undefined"
          class="h-12 w-full appearance-none rounded-xl border-2 border-slate-200 bg-white pl-4 pr-11 text-base text-slate-900 focus:border-[var(--cor)] focus:outline-none"
          data-lista-opcoes
          @change="escolherNaLista"
        >
          <option value="">Escolha uma opção</option>
          <option v-for="o in opcoes" :key="o" :value="o">{{ o }}</option>
        </select>
        <svg viewBox="0 0 24 24" class="pointer-events-none absolute right-4 top-1/2 size-5 -translate-y-1/2 text-slate-500" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M6 9l6 6 6-6" /></svg>
      </div>

      <!-- Escolha única -->
      <div v-else-if="pergunta.tipo === 'escolha_unica'" role="radiogroup" :aria-labelledby="idTitulo" class="flex flex-col gap-2">
        <label
          v-for="o in opcoes"
          :key="o"
          :class="[classeOpcao, modelValue === o ? 'border-[var(--cor)] bg-[var(--cor-suave)]' : 'border-slate-200 bg-white hover:border-slate-300']"
        >
          <input type="radio" :name="id" :value="o" :checked="modelValue === o" class="size-5 shrink-0 accent-[var(--cor)]" @change="escolher(o)" />
          <span>{{ o }}</span>
        </label>
      </div>

      <!-- Escolha múltipla -->
      <div v-else-if="pergunta.tipo === 'escolha_multipla'" class="flex flex-col gap-2">
        <p :id="`${id}-limite`" class="text-xs text-slate-500" data-dica-multipla>
          {{ maxSelecoes ? `Escolha até ${maxSelecoes} opções.` : 'Pode escolher mais de uma.' }}
        </p>
        <label
          v-for="o in opcoes"
          :key="o"
          :class="[
            classeOpcao,
            marcadas.includes(o) ? 'border-[var(--cor)] bg-[var(--cor-suave)]' : 'border-slate-200 bg-white hover:border-slate-300',
            noLimite && !marcadas.includes(o) ? 'cursor-not-allowed opacity-50 hover:border-slate-200' : '',
          ]"
        >
          <input
            type="checkbox"
            :value="o"
            :checked="marcadas.includes(o)"
            :disabled="noLimite && !marcadas.includes(o)"
            :aria-describedby="maxSelecoes ? `${id}-limite` : undefined"
            class="size-5 shrink-0 accent-[var(--cor)] disabled:cursor-not-allowed"
            @change="alternarMultipla(o, ($event.target as HTMLInputElement).checked)"
          />
          <span>{{ o }}</span>
        </label>
        <p v-if="maxSelecoes" class="sr-only" aria-live="polite">{{ anuncioLimite }}</p>
      </div>

      <!-- Sim / não -->
      <div v-else-if="pergunta.tipo === 'sim_nao'" role="radiogroup" :aria-labelledby="idTitulo" class="grid grid-cols-2 gap-2">
        <label
          v-for="o in [{ v: true, t: 'Sim' }, { v: false, t: 'Não' }]"
          :key="o.t"
          :class="[classeOpcao, 'justify-center', modelValue === o.v ? 'border-[var(--cor)] bg-[var(--cor-suave)]' : 'border-slate-200 bg-white hover:border-slate-300']"
        >
          <input type="radio" :name="id" :checked="modelValue === o.v" class="sr-only" @change="escolher(o.v)" />
          <span class="text-base font-bold">{{ o.t }}</span>
        </label>
      </div>

      <!-- Data -->
      <div v-else-if="pergunta.tipo === 'data'">
        <input
          type="date"
          :value="textoAtual"
          :aria-labelledby="idTitulo"
          :aria-describedby="descritoPor"
          :aria-invalid="erro ? 'true' : undefined"
          class="h-12 w-full max-w-xs rounded-xl border-2 border-slate-200 bg-white px-4 text-base text-slate-900 focus:border-[var(--cor)] focus:outline-none"
          @input="texto"
        />
      </div>
    </div>

    <p v-if="erro" :id="idErro" role="alert" class="mt-2 flex items-center gap-1.5 text-sm font-semibold text-red-700">
      <svg viewBox="0 0 24 24" class="size-4 shrink-0" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><circle cx="12" cy="12" r="10" /><path d="M12 7v6M12 16.5v.5" stroke-linecap="round" /></svg>
      {{ erro }}
    </p>
  </fieldset>
</template>

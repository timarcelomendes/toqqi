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
const titulo = computed(() => renderizarVariaveis(props.pergunta.titulo, props.variaveis))
const descricao = computed(() => renderizarVariaveis(props.pergunta.descricao, props.variaveis))
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
  // Mantém a ordem das opções.
  emit('update:modelValue', (props.pergunta.opcoes ?? []).filter((o) => novo.includes(o)))
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
      <!-- NPS 0–10 -->
      <template v-if="pergunta.tipo === 'nps'">
        <div role="radiogroup" :aria-labelledby="idTitulo" class="grid grid-cols-11 gap-[3px] sm:gap-1.5">
          <label v-for="n in notas" :key="n" class="relative">
            <input
              type="radio"
              :name="id"
              :value="n"
              :checked="modelValue === n"
              class="peer sr-only"
              :aria-label="`${n}${n === 0 && rotuloMin ? ` (${rotuloMin})` : ''}${n === 10 && rotuloMax ? ` (${rotuloMax})` : ''}`"
              @change="escolher(n)"
            />
            <span
              class="flex h-11 cursor-pointer items-center justify-center rounded-lg border-2 text-sm font-bold transition-colors peer-focus-visible:outline-2 peer-focus-visible:outline-offset-2 peer-focus-visible:outline-slate-900 sm:h-12 sm:text-base"
              :class="classeNps(n, modelValue === n)"
              aria-hidden="true"
            >{{ n }}</span>
          </label>
        </div>
        <div v-if="rotuloMin || rotuloMax" class="mt-2 flex justify-between gap-4 text-xs text-slate-500" aria-hidden="true">
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

      <!-- Escala -->
      <template v-else-if="pergunta.tipo === 'escala'">
        <div role="radiogroup" :aria-labelledby="idTitulo" class="grid gap-1.5" :style="{ gridTemplateColumns: `repeat(${notas.length}, minmax(0, 1fr))` }">
          <label v-for="n in notas" :key="n" class="relative">
            <input type="radio" :name="id" :value="n" :checked="modelValue === n" class="peer sr-only" :aria-label="String(n)" @change="escolher(n)" />
            <span
              class="flex h-11 cursor-pointer items-center justify-center rounded-lg border-2 text-sm font-bold transition-colors peer-focus-visible:outline-2 peer-focus-visible:outline-offset-2 peer-focus-visible:outline-slate-900"
              :class="modelValue === n ? 'border-[var(--cor)] bg-[var(--cor)] text-[var(--cor-texto)]' : 'border-slate-200 bg-white text-slate-700 hover:border-slate-300'"
              aria-hidden="true"
            >{{ n }}</span>
          </label>
        </div>
        <div v-if="pergunta.rotulo_min || pergunta.rotulo_max" class="mt-2 flex justify-between gap-4 text-xs text-slate-500" aria-hidden="true">
          <span>{{ pergunta.rotulo_min }}</span><span class="text-right">{{ pergunta.rotulo_max }}</span>
        </div>
      </template>

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
          :placeholder="pergunta.formato === 'email' ? 'seu@email.com' : pergunta.formato === 'telefone' ? '(11) 91234-5678' : 'Sua resposta'"
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
          placeholder="Escreva aqui, se quiser"
          @input="texto"
        />
        <p v-if="textoAtual.length > LIMITE_COMENTARIO * 0.8" class="mt-1 text-right text-xs text-slate-500">{{ textoAtual.length }} de {{ LIMITE_COMENTARIO }}</p>
      </div>

      <!-- Escolha única -->
      <div v-else-if="pergunta.tipo === 'escolha_unica'" role="radiogroup" :aria-labelledby="idTitulo" class="flex flex-col gap-2">
        <label
          v-for="o in pergunta.opcoes ?? []"
          :key="o"
          :class="[classeOpcao, modelValue === o ? 'border-[var(--cor)] bg-[var(--cor-suave)]' : 'border-slate-200 bg-white hover:border-slate-300']"
        >
          <input type="radio" :name="id" :value="o" :checked="modelValue === o" class="size-5 shrink-0 accent-[var(--cor)]" @change="escolher(o)" />
          <span>{{ o }}</span>
        </label>
      </div>

      <!-- Escolha múltipla -->
      <div v-else-if="pergunta.tipo === 'escolha_multipla'" class="flex flex-col gap-2">
        <p class="text-xs text-slate-500">Pode escolher mais de uma.</p>
        <label
          v-for="o in pergunta.opcoes ?? []"
          :key="o"
          :class="[classeOpcao, Array.isArray(modelValue) && modelValue.includes(o) ? 'border-[var(--cor)] bg-[var(--cor-suave)]' : 'border-slate-200 bg-white hover:border-slate-300']"
        >
          <input
            type="checkbox"
            :value="o"
            :checked="Array.isArray(modelValue) && modelValue.includes(o)"
            class="size-5 shrink-0 accent-[var(--cor)]"
            @change="alternarMultipla(o, ($event.target as HTMLInputElement).checked)"
          />
          <span>{{ o }}</span>
        </label>
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

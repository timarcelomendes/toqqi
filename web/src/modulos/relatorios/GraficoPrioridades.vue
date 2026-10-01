<script setup lang="ts">
// "O que resolver primeiro": cada tema é um ponto (nota média de quem citou × quantas vezes foi citado), com o nome
// escrito ao lado. Os do canto de cima, à esquerda (muito citados e com nota baixa), vêm primeiro. A lista ao lado
// do gráfico traz os mesmos números (alternativa em texto); setas e foco mostram cada tema.
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import type { PrioridadeTema } from '@/api/tipos'
import { formatarNumero } from '@/utils/formatos'
import { escala, formatarMedia1 } from '@/modulos/painel/logica'
import { corDoTema, escalaContagem, numero, posicionarRotulos } from './logica'
import { saiuComMouse, usarFocoGrafico } from '@/composables/focoGrafico'

const props = defineProps<{ prioridades: PrioridadeTema[] }>()

const M = { topo: 22, base: 40, esq: 40, dir: 16 }
const ALTURA = 280
const raiz = ref<HTMLElement | null>(null)
const largura = ref(560)
const ativo = ref<number | null>(null)
const anuncio = ref('')
let observador: ResizeObserver | null = null

onMounted(() => {
  if (raiz.value?.clientWidth) largura.value = raiz.value.clientWidth
  if (typeof ResizeObserver !== 'undefined' && raiz.value) {
    observador = new ResizeObserver((entradas) => {
      const w = entradas[0]?.contentRect.width
      if (w && Math.abs(w - largura.value) > 1) largura.value = w
    })
    observador.observe(raiz.value)
  }
})
onBeforeUnmount(() => observador?.disconnect())

const larguraPlot = computed(() => Math.max(80, largura.value - M.esq - M.dir))
const alturaPlot = ALTURA - M.topo - M.base
/** Só os temas com nota média (a ordem é a da API: o mais urgente primeiro). */
const pts = computed(() =>
  props.prioridades.filter((p) => numero(p.nota_media) !== null).map((p) => ({ ...p, media: numero(p.nota_media)! })),
)
const eixoY = computed(() => escalaContagem(Math.max(1, ...pts.value.map((p) => p.mencoes))))
const x = computed(() => escala([0, 10], [M.esq, M.esq + larguraPlot.value]))
const y = computed(() => escala([0, eixoY.value.max], [M.topo + alturaPlot, M.topo]))
const TICKS_X = [0, 2, 4, 6, 8, 10]

const rotulos = computed(() =>
  posicionarRotulos(
    pts.value.map((p) => ({ x: x.value(p.media), y: y.value(p.mencoes), texto: p.rotulo })),
    { esq: M.esq, dir: largura.value - M.dir, topo: 0, base: M.topo + alturaPlot },
  ),
)

function descrever(i: number): string {
  const p = pts.value[i]
  if (!p) return ''
  return `${i + 1}º: ${p.rotulo}, ${formatarNumero(p.mencoes)} ${p.mencoes === 1 ? 'menção' : 'menções'}, nota média ${formatarMedia1(p.media)}, ${formatarNumero(p.reclamacoes)} ${p.reclamacoes === 1 ? 'reclamação' : 'reclamações'}.`
}

/** O tema mais perto do ponteiro (mouse ou toque), até 26 px; fora disso, nenhum. */
function aoMover(e: PointerEvent) {
  const svg = e.currentTarget as SVGSVGElement
  const r = svg.getBoundingClientRect()
  if (!r.width || !r.height) return
  const px = ((e.clientX - r.left) / r.width) * largura.value
  const py = ((e.clientY - r.top) / r.height) * ALTURA
  let melhor: number | null = null
  let menor = 26 * 26
  pts.value.forEach((p, i) => {
    const dx = x.value(p.media) - px
    const dy = y.value(p.mencoes) - py
    if (dx * dx + dy * dy <= menor) {
      menor = dx * dx + dy * dy
      melhor = i
    }
  })
  ativo.value = melhor
}

function aoSairDoGrafico(e: PointerEvent) {
  if (saiuComMouse(e)) ativo.value = null
}

function aoTeclar(e: KeyboardEvent) {
  const n = pts.value.length
  if (!n) return
  const atual = ativo.value ?? -1
  let novo = atual
  if (e.key === 'ArrowRight' || e.key === 'ArrowDown') novo = Math.min(n - 1, atual + 1)
  else if (e.key === 'ArrowLeft' || e.key === 'ArrowUp') novo = Math.max(0, atual - 1)
  else if (e.key === 'Home') novo = 0
  else if (e.key === 'End') novo = n - 1
  else return
  e.preventDefault()
  ativo.value = novo
  anuncio.value = descrever(novo)
}

const foco = usarFocoGrafico()

/** Só o foco do teclado mostra o primeiro tema; com mouse ou toque, vale o tema embaixo do ponteiro. */
function aoFocar(e: FocusEvent) {
  if (!foco.veioDoTeclado(e)) return
  if (ativo.value === null && pts.value.length) {
    ativo.value = 0
    anuncio.value = descrever(0)
  }
}

function aoDesfocar() {
  foco.aoSair()
  ativo.value = null
}

const dica = computed(() => {
  if (ativo.value === null) return null
  const p = pts.value[ativo.value]
  if (!p) return null
  const px = x.value(p.media)
  const py = y.value(p.mencoes)
  return { p, px, py, lado: px < 110 ? 'esq' : px > largura.value - 110 ? 'dir' : 'meio', abaixo: py < 90 }
})
</script>

<template>
  <div ref="raiz" class="relative" data-grafico-prioridades>
    <div
      tabindex="0"
      role="group"
      aria-label="Gráfico dos temas: nota média de quem citou e número de menções. Use as setas para ver cada tema."
      class="rounded-lg focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-foco"
      @keydown="aoTeclar"
      @pointerdown="foco.aoApertar"
      @focus="aoFocar"
      @blur="aoDesfocar"
    >
      <svg
        :viewBox="`0 0 ${largura} ${ALTURA}`"
        :width="largura"
        :height="ALTURA"
        class="block h-auto w-full touch-pan-y select-none overflow-visible"
        aria-hidden="true"
        @pointermove="aoMover"
        @pointerdown="aoMover"
        @pointerleave="aoSairDoGrafico"
      >
        <!-- Grade das menções -->
        <template v-for="t in eixoY.ticks" :key="t">
          <line :x1="M.esq" :x2="largura - M.dir" :y1="y(t)" :y2="y(t)" :class="t === 0 ? 'stroke-borda-forte' : 'stroke-borda'" stroke-width="1" shape-rendering="crispEdges" />
          <text :x="M.esq - 8" :y="y(t)" text-anchor="end" dominant-baseline="middle" class="fill-texto-fraco text-[11px] tabular-nums">{{ formatarNumero(t) }}</text>
        </template>
        <!-- Notas -->
        <text v-for="t in TICKS_X" :key="t" :x="x(t)" :y="ALTURA - 22" text-anchor="middle" class="fill-texto-fraco text-[11px] tabular-nums">{{ t }}</text>
        <text :x="M.esq + larguraPlot / 2" :y="ALTURA - 4" text-anchor="middle" class="fill-texto-fraco text-[11px]">Nota média de quem citou (0 a 10)</text>
        <text :x="M.esq" :y="10" class="fill-texto-fraco text-[11px]">Menções</text>
        <text v-if="largura >= 480" :x="largura - M.dir" :y="10" text-anchor="end" class="fill-texto-fraco text-[11px] font-semibold">Resolver primeiro: canto de cima, à esquerda</text>
        <!-- Temas -->
        <template v-for="(p, i) in pts" :key="p.tema">
          <circle :data-tema="p.tema" :cx="x(p.media)" :cy="y(p.mencoes)" :r="i === ativo ? 7.5 : 6" class="stroke-superficie" :class="corDoTema(p.tema).preenchimento" stroke-width="2" />
          <text
            :x="rotulos[i]?.x"
            :y="rotulos[i]?.y"
            :text-anchor="rotulos[i]?.ancora"
            class="text-[11px] font-semibold"
            :class="i === ativo ? 'fill-texto' : 'fill-texto-suave'"
          >
            {{ p.rotulo }}
          </text>
        </template>
      </svg>
    </div>
    <div
      v-if="dica"
      class="pointer-events-none absolute z-10 w-max max-w-56 rounded-lg border border-borda bg-superficie px-3 py-2 text-xs shadow-lg"
      :style="{
        left: `${(dica.px / largura) * 100}%`,
        top: `${dica.abaixo ? dica.py + 14 : dica.py - 14}px`,
        translate: `${dica.lado === 'esq' ? '0' : dica.lado === 'dir' ? '-100%' : '-50%'} ${dica.abaixo ? '0' : '-100%'}`,
      }"
      aria-hidden="true"
    >
      <p class="text-sm font-bold text-texto">{{ dica.p.rotulo }}</p>
      <p class="text-texto-suave">{{ formatarNumero(dica.p.mencoes) }} {{ dica.p.mencoes === 1 ? 'menção' : 'menções' }} · nota média {{ formatarMedia1(dica.p.media) }}</p>
      <p class="text-texto-fraco">{{ formatarNumero(dica.p.reclamacoes) }} {{ dica.p.reclamacoes === 1 ? 'reclamação' : 'reclamações' }}</p>
    </div>
    <p class="sr-only" aria-live="polite">{{ anuncio }}</p>
  </div>
</template>

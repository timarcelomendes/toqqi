<script setup lang="ts">
// Matriz NPS × valor: cada ponto é uma empresa com NPS no período e valor mensal cadastrado. Valor em escala
// logarítmica (eixo X), NPS de −100 a 100 (eixo Y), linhas na mediana do valor e no NPS 0, o nome dos 4 quadrantes
// nos cantos e a cor do quadrante (que só reforça a posição). Passe o mouse ou use as setas para ver cada empresa;
// clique ou Enter abre o histórico. A contagem por quadrante, fora do gráfico, é a alternativa em texto.
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import type { Id, PontoMatriz, Quadrante } from '@/api/tipos'
import { formatarMoeda, formatarNumero } from '@/utils/formatos'
import { escala, formatarNps } from '@/modulos/painel/logica'
import { QUADRANTES, escalaLog, formatarMoedaCurta, numero } from './logica'
import { saiuComMouse, usarFocoGrafico } from '@/composables/focoGrafico'

const props = withDefaults(defineProps<{ pontos: PontoMatriz[]; mediana: number | null; destaque?: Quadrante | '' }>(), { destaque: '' })
const emit = defineEmits<{ abrir: [empresaId: Id, nome: string] }>()

const M = { topo: 14, base: 34, esq: 40, dir: 16 }
const raiz = ref<HTMLElement | null>(null)
const largura = ref(640)
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

const altura = computed(() => (largura.value < 480 ? 280 : 340))
const larguraPlot = computed(() => Math.max(80, largura.value - M.esq - M.dir))
const alturaPlot = computed(() => altura.value - M.topo - M.base)

/** Os pontos em ordem de valor (as setas andam da esquerda para a direita). */
const pts = computed(() =>
  props.pontos
    .map((p) => ({ ...p, v: numero(p.valor_mensal) ?? 0 }))
    .sort((a, b) => a.v - b.v || a.nps - b.nps || String(a.empresa.nome).localeCompare(String(b.empresa.nome), 'pt-BR')),
)
const eixoX = computed(() => escalaLog([...pts.value.map((p) => p.v), ...(props.mediana ? [props.mediana] : [])]))
const x = (v: number) => M.esq + eixoX.value.pos(v) * larguraPlot.value
const y = computed(() => escala([-100, 100], [M.topo + alturaPlot.value, M.topo]))
const TICKS_NPS = [-100, -50, 0, 50, 100]

/** Rótulos do valor que cabem (pelo menos 52 px entre eles). */
const rotulosX = computed(() => {
  const r: { v: number; px: number; texto: string }[] = []
  for (const v of eixoX.value.ticks) {
    const px = x(v)
    if (!r.length || px - r[r.length - 1]!.px >= 52) r.push({ v, px, texto: formatarMoedaCurta(v) })
  }
  return r
})

const xMediana = computed(() => (props.mediana ? x(props.mediana) : null))

function descrever(i: number): string {
  const p = pts.value[i]
  if (!p) return ''
  return `${p.empresa.nome}: NPS ${formatarNps(p.nps)}, ${formatarMoeda(p.v)} por mês, ${formatarNumero(p.respostas)} ${p.respostas === 1 ? 'resposta' : 'respostas'}, ${QUADRANTES[p.quadrante]?.rotulo ?? p.quadrante}.`
}

/** O ponto mais perto do ponteiro, até 24 px (ninguém precisa acertar um ponto de 10 px); fora disso, nenhum. */
function pontoPerto(e: MouseEvent): number | null {
  const svg = e.currentTarget as SVGSVGElement
  const r = svg.getBoundingClientRect()
  if (!r.width || !r.height) return null
  const px = ((e.clientX - r.left) / r.width) * largura.value
  const py = ((e.clientY - r.top) / r.height) * altura.value
  let melhor: number | null = null
  let menor = 24 * 24
  pts.value.forEach((p, i) => {
    const dx = x(p.v) - px
    const dy = y.value(p.nps) - py
    const d = dx * dx + dy * dy
    if (d <= menor) {
      menor = d
      melhor = i
    }
  })
  return melhor
}

function aoMover(e: PointerEvent) {
  ativo.value = pontoPerto(e)
}

function aoSairDoGrafico(e: PointerEvent) {
  if (saiuComMouse(e)) ativo.value = null
}

function abrir(i: number | null) {
  const p = i !== null ? pts.value[i] : null
  if (p) emit('abrir', p.empresa.id, p.empresa.nome)
}

/** Clique ou toque: abre a empresa embaixo do ponteiro (nunca a que estava escolhida pelo foco). */
function aoClicar(e: MouseEvent) {
  abrir(pontoPerto(e))
}

function aoTeclar(e: KeyboardEvent) {
  const n = pts.value.length
  if (!n) return
  const atual = ativo.value ?? -1
  let novo = atual
  if (e.key === 'ArrowRight' || e.key === 'ArrowDown') novo = Math.min(n - 1, atual + 1)
  else if (e.key === 'ArrowLeft' || e.key === 'ArrowUp') novo = Math.max(0, atual < 0 ? 0 : atual - 1)
  else if (e.key === 'Home') novo = 0
  else if (e.key === 'End') novo = n - 1
  else if (e.key === 'Enter' || e.key === ' ') {
    if (ativo.value !== null) {
      e.preventDefault()
      abrir(ativo.value)
    }
    return
  } else return
  e.preventDefault()
  ativo.value = novo
  anuncio.value = `${descrever(novo)} Enter abre o histórico.`
}

const foco = usarFocoGrafico()

/** Só o foco do teclado escolhe a primeira empresa; com mouse ou toque, vale o ponto embaixo do ponteiro. */
function aoFocar(e: FocusEvent) {
  if (!foco.veioDoTeclado(e)) return
  if (ativo.value === null && pts.value.length) {
    ativo.value = 0
    anuncio.value = `${descrever(0)} Use as setas para ver as outras empresas; Enter abre o histórico.`
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
  const px = x(p.v)
  const py = y.value(p.nps)
  const lado = px < 110 ? 'esq' : px > largura.value - 110 ? 'dir' : 'meio'
  return { p, px, py, lado, abaixo: py < 90 }
})

const descricao = computed(() => {
  const n = pts.value.length
  return `Matriz NPS por valor do contrato: ${formatarNumero(n)} ${n === 1 ? 'empresa' : 'empresas'}${props.mediana ? `; mediana do valor ${formatarMoeda(props.mediana)}` : ''}.`
})

const opacoFora = (q: Quadrante) => !!props.destaque && props.destaque !== q
</script>

<template>
  <div ref="raiz" class="relative" data-matriz>
    <div
      tabindex="0"
      role="group"
      :aria-label="`${descricao} Use as setas para ver cada empresa e Enter para abrir o histórico.`"
      class="rounded-lg focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-foco"
      @keydown="aoTeclar"
      @pointerdown="foco.aoApertar"
      @focus="aoFocar"
      @blur="aoDesfocar"
    >
      <svg
        :viewBox="`0 0 ${largura} ${altura}`"
        :width="largura"
        :height="altura"
        class="block h-auto w-full touch-pan-y select-none overflow-visible"
        :class="ativo !== null ? 'cursor-pointer' : ''"
        aria-hidden="true"
        @pointermove="aoMover"
        @pointerdown="aoMover"
        @pointerleave="aoSairDoGrafico"
        @click="aoClicar"
      >
        <!-- Grade do NPS -->
        <g>
          <template v-for="t in TICKS_NPS" :key="t">
            <line
              :x1="M.esq"
              :x2="largura - M.dir"
              :y1="y(t)"
              :y2="y(t)"
              :class="t === 0 ? 'stroke-borda-forte' : 'stroke-borda'"
              stroke-width="1"
              shape-rendering="crispEdges"
            />
            <text :x="M.esq - 8" :y="y(t)" text-anchor="end" dominant-baseline="middle" class="fill-texto-fraco text-[11px] tabular-nums">{{ formatarNps(t) }}</text>
          </template>
        </g>
        <!-- Eixo do valor (escala logarítmica) -->
        <text v-for="r in rotulosX" :key="r.v" :x="r.px" :y="altura - 10" text-anchor="middle" class="fill-texto-fraco text-[11px] tabular-nums">{{ r.texto }}</text>
        <!-- Mediana do valor -->
        <template v-if="xMediana !== null">
          <line :x1="xMediana" :x2="xMediana" :y1="M.topo" :y2="M.topo + alturaPlot" class="stroke-borda-forte" stroke-width="1" shape-rendering="crispEdges" />
        </template>
        <!-- Empresas (com anel da cor do fundo; a ativa por cima) -->
        <g>
          <circle
            v-for="(p, i) in pts"
            :key="String(p.empresa.id)"
            :data-empresa="p.empresa.id"
            :cx="x(p.v)"
            :cy="y(p.nps)"
            r="5"
            class="stroke-superficie transition-opacity"
            :class="[QUADRANTES[p.quadrante]?.ponto ?? 'fill-texto-fraco', opacoFora(p.quadrante) ? 'opacity-25' : '', i === ativo ? 'opacity-0' : '']"
            stroke-width="2"
          />
          <circle v-if="dica" :cx="x(dica.p.v)" :cy="y(dica.p.nps)" r="7.5" class="stroke-texto" :class="QUADRANTES[dica.p.quadrante]?.ponto" stroke-width="2" />
        </g>
        <!-- Nome dos quadrantes nos cantos, por cima dos pontos (com um contorno da cor do fundo para não sumir) -->
        <g class="stroke-superficie text-[11px] font-semibold [paint-order:stroke]" stroke-width="3" stroke-linejoin="round">
          <text :x="M.esq + 6" :y="M.topo + 12" class="fill-texto-fraco">{{ QUADRANTES.crescer.rotulo }}</text>
          <text :x="largura - M.dir - 6" :y="M.topo + 12" text-anchor="end" class="fill-texto-fraco">{{ QUADRANTES.manter.rotulo }}</text>
          <text :x="M.esq + 6" :y="M.topo + alturaPlot - 6" class="fill-texto-fraco">{{ QUADRANTES.corrigir.rotulo }}</text>
          <text :x="largura - M.dir - 6" :y="M.topo + alturaPlot - 6" text-anchor="end" class="fill-texto-fraco">{{ QUADRANTES.proteger.rotulo }}</text>
        </g>
      </svg>
    </div>

    <p v-if="xMediana !== null && mediana" class="mt-1 text-xs text-texto-fraco">
      Linha vertical: mediana do valor ({{ formatarMoeda(mediana) }} por mês). Linha horizontal: NPS 0.
    </p>

    <div
      v-if="dica"
      class="pointer-events-none absolute z-10 w-max max-w-60 rounded-lg border border-borda bg-superficie px-3 py-2 text-xs shadow-lg"
      :style="{
        left: `${(dica.px / largura) * 100}%`,
        top: `${dica.abaixo ? dica.py + 14 : dica.py - 14}px`,
        translate: `${dica.lado === 'esq' ? '0' : dica.lado === 'dir' ? '-100%' : '-50%'} ${dica.abaixo ? '0' : '-100%'}`,
      }"
      aria-hidden="true"
    >
      <p class="text-sm font-bold text-texto">{{ dica.p.empresa.nome }}</p>
      <p class="text-texto-suave">
        NPS <strong class="font-semibold text-texto">{{ formatarNps(dica.p.nps) }}</strong> · {{ formatarMoeda(dica.p.v) }}/mês
      </p>
      <p class="text-texto-fraco">{{ formatarNumero(dica.p.respostas) }} {{ dica.p.respostas === 1 ? 'resposta' : 'respostas' }} · {{ QUADRANTES[dica.p.quadrante]?.rotulo }}</p>
      <p class="mt-1 text-texto-fraco">Clique para ver o histórico</p>
    </div>
    <p class="sr-only" aria-live="polite">{{ anuncio }}</p>
  </div>
</template>

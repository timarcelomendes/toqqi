<script setup lang="ts">
// Temas semana a semana: uma linha por tema (cor fixa de cada tema), menções ou reclamações. Passe o mouse ou use
// as setas para ver cada semana (a dica lista os 6 temas); passar o mouse num nome da legenda destaca a linha.
// Os mesmos números existem em tabela ("Ver em tabela").
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import type { SemanaTemas } from '@/api/tipos'
import { formatarNumero } from '@/utils/formatos'
import { escala } from '@/modulos/painel/logica'
import { corDoTema, escalaContagem, rotuloSemana, seriesSemanais, type MedidaTema } from './logica'
import { saiuComMouse, usarFocoGrafico } from '@/composables/focoGrafico'

const props = defineProps<{ semanas: SemanaTemas[]; medida: MedidaTema; temas: { tema: string; rotulo: string }[] }>()
const verTabela = defineModel<boolean>('tabela', { default: false })

const ALTURA = 260
const M = { topo: 16, base: 30, esq: 36, dir: 16 }
const raiz = ref<HTMLElement | null>(null)
const largura = ref(640)
const ativo = ref<number | null>(null)
// Destaque de uma linha: fixo (clique ou Enter no nome da legenda) ou enquanto o mouse está sobre o nome.
const fixo = ref<string | null>(null)
const sobre = ref<string | null>(null)
const realce = computed(() => sobre.value ?? fixo.value)
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

const series = computed(() => seriesSemanais(props.semanas, props.medida, props.temas.map((t) => t.tema)))
const rotulos = computed(() => Object.fromEntries(props.temas.map((t) => [t.tema, t.rotulo])) as Record<string, string>)
const n = computed(() => props.semanas.length)
const eixoY = computed(() => escalaContagem(Math.max(1, ...series.value.flatMap((s) => s.valores))))
const larguraPlot = computed(() => Math.max(80, largura.value - M.esq - M.dir))
const alturaPlot = ALTURA - M.topo - M.base
const x = (i: number) => (n.value <= 1 ? M.esq + larguraPlot.value / 2 : M.esq + (i * larguraPlot.value) / (n.value - 1))
const y = computed(() => escala([0, eixoY.value.max], [M.topo + alturaPlot, M.topo]))
const passoX = computed(() => (n.value <= 1 ? larguraPlot.value : larguraPlot.value / (n.value - 1)))

function caminho(valores: number[]): string {
  return valores.map((v, i) => `${i ? 'L' : 'M'}${x(i).toFixed(1)},${y.value(v).toFixed(1)}`).join('')
}

// Datas no eixo: só as que cabem (sempre a última).
const rotulosX = computed(() => {
  const cabe = Math.max(1, Math.ceil(44 / passoX.value))
  return props.semanas
    .map((s, i) => ({ i, texto: rotuloSemana(s).split(' a ')[0]! }))
    .filter(({ i }) => i === n.value - 1 || ((n.value - 1 - i) % cabe === 0 && n.value - 1 - i >= cabe))
})

const nomeMedida = computed(() => (props.medida === 'mencoes' ? 'menções' : 'reclamações'))

function anunciar(i: number) {
  const s = props.semanas[i]
  if (!s) return
  anuncio.value = `Semana de ${rotuloSemana(s)}: ${series.value.map((x) => `${rotulos.value[x.tema] ?? x.tema} ${formatarNumero(x.valores[i] ?? 0)}`).join(', ')}.`
}

function aoMover(e: PointerEvent) {
  const svg = e.currentTarget as SVGSVGElement
  const r = svg.getBoundingClientRect()
  if (!r.width) return
  const px = ((e.clientX - r.left) / r.width) * largura.value
  const i = n.value <= 1 ? 0 : Math.round((px - M.esq) / passoX.value)
  ativo.value = Math.min(n.value - 1, Math.max(0, i))
}

function aoTeclar(e: KeyboardEvent) {
  if (!n.value) return
  const atual = ativo.value ?? n.value - 1
  let novo = atual
  if (e.key === 'ArrowLeft') novo = Math.max(0, atual - 1)
  else if (e.key === 'ArrowRight') novo = Math.min(n.value - 1, atual + 1)
  else if (e.key === 'Home') novo = 0
  else if (e.key === 'End') novo = n.value - 1
  else return
  e.preventDefault()
  ativo.value = novo
  anunciar(novo)
}

const foco = usarFocoGrafico()

/** Só o foco do teclado mostra a última semana; com mouse ou toque, vale a semana embaixo do ponteiro. */
function aoFocar(e: FocusEvent) {
  if (!foco.veioDoTeclado(e)) return
  if (ativo.value === null && n.value) {
    ativo.value = n.value - 1
    anunciar(n.value - 1)
  }
}

function aoDesfocar() {
  foco.aoSair()
  ativo.value = null
}

function aoSairDoGrafico(e: PointerEvent) {
  if (saiuComMouse(e)) ativo.value = null
}

/** A dica: os temas daquela semana, do maior para o menor. */
const dica = computed(() => {
  if (ativo.value === null) return null
  const i = ativo.value
  const s = props.semanas[i]
  if (!s) return null
  const linhas = series.value
    .map((x) => ({ tema: x.tema, rotulo: rotulos.value[x.tema] ?? x.tema, valor: x.valores[i] ?? 0 }))
    .sort((a, b) => b.valor - a.valor)
  const px = x(i)
  return { s, linhas, px, lado: px < 120 ? 'esq' : px > largura.value - 120 ? 'dir' : 'meio' }
})

const opaca = (tema: string) => (realce.value && realce.value !== tema ? 'opacity-20' : '')
</script>

<template>
  <div class="flex flex-col gap-3" data-grafico-semanal>
    <!-- Legenda: nome escrito ao lado do traço de cada tema -->
    <ul class="flex flex-wrap gap-x-4 gap-y-1.5 text-sm" aria-label="Legenda dos temas">
      <li v-for="t in temas" :key="t.tema">
        <button
          type="button"
          class="inline-flex min-h-8 items-center gap-1.5 rounded-lg px-1 text-texto-suave hover:text-texto"
          :class="realce === t.tema ? 'font-semibold text-texto' : ''"
          :aria-pressed="fixo === t.tema"
          @click="fixo = fixo === t.tema ? null : t.tema"
          @pointerenter="sobre = t.tema"
          @pointerleave="sobre = null"
        >
          <span class="h-0.5 w-4 rounded-full" :class="corDoTema(t.tema).fundo" aria-hidden="true" />
          {{ t.rotulo }}
        </button>
      </li>
    </ul>

    <div v-show="!verTabela" ref="raiz" class="relative">
      <div
        tabindex="0"
        role="group"
        :aria-label="`Gráfico de ${nomeMedida} por tema, semana a semana. Use as setas para ver cada semana.`"
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
          <template v-for="t in eixoY.ticks" :key="t">
            <line :x1="M.esq" :x2="largura - M.dir" :y1="y(t)" :y2="y(t)" :class="t === 0 ? 'stroke-borda-forte' : 'stroke-borda'" stroke-width="1" shape-rendering="crispEdges" />
            <text :x="M.esq - 8" :y="y(t)" text-anchor="end" dominant-baseline="middle" class="fill-texto-fraco text-[11px] tabular-nums">{{ formatarNumero(t) }}</text>
          </template>
          <text
            v-for="r in rotulosX"
            :key="r.i"
            :x="x(r.i)"
            :y="ALTURA - 8"
            text-anchor="middle"
            class="fill-texto-fraco text-[11px]"
            :class="r.i === ativo ? 'font-semibold !fill-texto' : ''"
          >
            {{ r.texto }}
          </text>
          <line v-if="ativo !== null" :x1="x(ativo)" :x2="x(ativo)" :y1="M.topo - 6" :y2="M.topo + alturaPlot" class="stroke-borda-forte" stroke-width="1" shape-rendering="crispEdges" />
          <path
            v-for="s in series"
            :key="s.tema"
            :d="caminho(s.valores)"
            fill="none"
            class="transition-opacity"
            :class="[corDoTema(s.tema).traco, opaca(s.tema)]"
            :stroke-width="realce === s.tema ? 3 : 2"
            stroke-linejoin="round"
            stroke-linecap="round"
          />
          <!-- Pontos da semana em foco (com anel da cor do fundo) -->
          <template v-if="ativo !== null">
            <circle
              v-for="s in series"
              :key="s.tema"
              :cx="x(ativo)"
              :cy="y(s.valores[ativo] ?? 0)"
              r="4"
              class="stroke-superficie"
              :class="[corDoTema(s.tema).preenchimento, opaca(s.tema)]"
              stroke-width="2"
            />
          </template>
          <!-- Uma semana só: sem linha, um ponto por tema -->
          <template v-if="n === 1 && ativo === null">
            <circle v-for="s in series" :key="`u-${s.tema}`" :cx="x(0)" :cy="y(s.valores[0] ?? 0)" r="4" class="stroke-superficie" :class="corDoTema(s.tema).preenchimento" stroke-width="2" />
          </template>
        </svg>
      </div>
      <div
        v-if="dica"
        class="pointer-events-none absolute top-0 z-10 w-max min-w-44 max-w-64 rounded-lg border border-borda bg-superficie px-3 py-2 text-xs shadow-lg"
        :style="{ left: `${(dica.px / largura) * 100}%`, translate: dica.lado === 'esq' ? '12px 0' : dica.lado === 'dir' ? 'calc(-100% - 12px) 0' : '12px 0' }"
        aria-hidden="true"
      >
        <p class="mb-1 font-semibold text-texto">Semana de {{ rotuloSemana(dica.s) }}</p>
        <ul class="flex flex-col gap-0.5">
          <li v-for="l in dica.linhas" :key="l.tema" class="flex items-center gap-2">
            <span class="h-0.5 w-3 shrink-0 rounded-full" :class="corDoTema(l.tema).fundo" />
            <strong class="w-6 text-right font-bold tabular-nums text-texto">{{ formatarNumero(l.valor) }}</strong>
            <span class="truncate text-texto-suave">{{ l.rotulo }}</span>
          </li>
        </ul>
      </div>
      <p class="sr-only" aria-live="polite">{{ anuncio }}</p>
    </div>

    <div v-if="verTabela" class="max-h-96 overflow-auto rounded-xl border border-borda">
      <table class="w-full text-sm">
        <caption class="sr-only">{{ nomeMedida }} por tema, semana a semana</caption>
        <thead class="sticky top-0 bg-superficie-2">
          <tr>
            <th scope="col" class="whitespace-nowrap px-3 py-2 text-left text-xs font-semibold uppercase tracking-wide text-texto-fraco">Semana</th>
            <th v-for="t in temas" :key="t.tema" scope="col" class="px-3 py-2 text-right text-xs font-semibold uppercase tracking-wide text-texto-fraco">{{ t.rotulo }}</th>
            <th scope="col" class="px-3 py-2 text-right text-xs font-semibold uppercase tracking-wide text-texto-fraco">Respostas</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="(s, i) in semanas" :key="s.inicio" class="border-t border-borda">
            <th scope="row" class="whitespace-nowrap px-3 py-2 text-left font-medium text-texto">{{ rotuloSemana(s) }}</th>
            <td v-for="x in series" :key="x.tema" class="px-3 py-2 text-right tabular-nums text-texto-suave">{{ formatarNumero(x.valores[i] ?? 0) }}</td>
            <td class="px-3 py-2 text-right tabular-nums text-texto-fraco">{{ formatarNumero(s.respostas) }}</td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

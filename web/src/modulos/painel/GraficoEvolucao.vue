<script setup lang="ts">
// Linha do NPS mês a mês (SVG feito à mão, sem biblioteca). Passe o mouse ou use as setas para ver
// cada mês; o mesmo conteúdo existe em tabela (botão "Ver em tabela").
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { formatarNumero } from '@/utils/formatos'
import { saiuComMouse, usarFocoGrafico } from '@/composables/focoGrafico'
import { completarMeses, dominioNps, escala, formatarMes, formatarNps } from './logica'

const props = defineProps<{ pontos: { mes: string; nps: number | null; total: number }[] }>()
/** Mostrar a tabela em vez do gráfico (o botão fica no cabeçalho do cartão). */
const verTabela = defineModel<boolean>('tabela', { default: false })

const ALTURA = 232
const M = { topo: 26, base: 30, esq: 40, dir: 22 }

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

/** Os meses com dados e os buracos entre eles (NPS vazio): a linha se interrompe onde falta mês. */
const serie = computed(() => completarMeses(props.pontos))
const n = computed(() => serie.value.length)
const valores = computed(() => serie.value.map((p) => p.nps).filter((v): v is number => typeof v === 'number'))
const dominio = computed(() => dominioNps(valores.value))
const larguraPlot = computed(() => Math.max(80, largura.value - M.esq - M.dir))
const alturaPlot = ALTURA - M.topo - M.base

const x = (i: number) => (n.value <= 1 ? M.esq + larguraPlot.value / 2 : M.esq + (i * larguraPlot.value) / (n.value - 1))
const y = computed(() => escala([dominio.value.min, dominio.value.max], [M.topo + alturaPlot, M.topo]))
const passoX = computed(() => (n.value <= 1 ? larguraPlot.value : larguraPlot.value / (n.value - 1)))

/** Caminho da linha; um mês sem NPS interrompe a linha. */
const caminho = computed(() => {
  let d = ''
  let novo = true
  serie.value.forEach((p, i) => {
    if (typeof p.nps !== 'number') {
      novo = true
      return
    }
    d += `${novo ? 'M' : 'L'}${x(i).toFixed(1)},${y.value(p.nps).toFixed(1)}`
    novo = false
  })
  return d
})

// Rótulos do eixo X: só os que cabem (sempre o último).
const rotulosX = computed(() => {
  const cabe = Math.max(1, Math.ceil(46 / passoX.value))
  return serie.value
    .map((p, i) => ({ i, texto: formatarMes(p.mes) }))
    .filter(({ i }) => i === n.value - 1 || ((n.value - 1 - i) % cabe === 0 && n.value - 1 - i >= cabe))
})
const mostrarMarcadores = computed(() => passoX.value >= 16)
const ultimoComValor = computed(() => {
  for (let i = n.value - 1; i >= 0; i--) if (typeof serie.value[i]?.nps === 'number') return i
  return -1
})

function anunciar(i: number) {
  const p = serie.value[i]
  if (!p) return
  anuncio.value = `${formatarMes(p.mes, 'longo')}: ${typeof p.nps === 'number' ? `NPS ${formatarNps(p.nps)}` : 'sem NPS'}, ${formatarNumero(p.total)} ${p.total === 1 ? 'resposta' : 'respostas'}.`
}

function aoMover(e: PointerEvent) {
  const svg = e.currentTarget as SVGSVGElement
  const r = svg.getBoundingClientRect()
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

/** Só o foco do teclado mostra o último mês; com mouse ou toque, vale o mês embaixo do ponteiro. */
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

/** No toque, a dica do mês tocado continua na tela depois de levantar o dedo. */
function aoSairDoGrafico(e: PointerEvent) {
  if (saiuComMouse(e)) ativo.value = null
}

const dica = computed(() => {
  if (ativo.value === null) return null
  const p = serie.value[ativo.value]
  if (!p) return null
  const px = x(ativo.value)
  const py = typeof p.nps === 'number' ? y.value(p.nps) : M.topo + alturaPlot / 2
  const lado = px < 90 ? 'esq' : px > largura.value - 90 ? 'dir' : 'meio'
  // Perto do topo, a dica vai para baixo do ponto (não cobre os botões de cima).
  const abaixo = py < 72
  return { p, px, py, lado, abaixo }
})

const descricao = computed(() => {
  if (!n.value) return 'Sem dados.'
  const ult = ultimoComValor.value >= 0 ? serie.value[ultimoComValor.value] : null
  return `NPS por mês, de ${formatarMes(serie.value[0]!.mes, 'longo')} a ${formatarMes(serie.value[n.value - 1]!.mes, 'longo')}.` + (ult ? ` Último: ${formatarNps(ult.nps)}.` : '')
})
</script>

<template>
  <div class="flex flex-col gap-3">
    <div v-show="!verTabela" ref="raiz" class="relative">
      <div
        tabindex="0"
        role="group"
        :aria-label="`Gráfico da evolução do NPS. ${descricao} Use as setas para ver cada mês.`"
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
          <!-- Grade (linhas finas e discretas) e o zero um pouco mais forte -->
          <g>
            <template v-for="t in dominio.ticks" :key="t">
              <line
                :x1="M.esq"
                :x2="largura - M.dir"
                :y1="y(t)"
                :y2="y(t)"
                :class="t === 0 ? 'stroke-borda-forte' : 'stroke-borda'"
                stroke-width="1"
                shape-rendering="crispEdges"
              />
              <text :x="M.esq - 8" :y="y(t)" text-anchor="end" dominant-baseline="middle" class="fill-texto-fraco text-[11px] tabular-nums">
                {{ formatarNps(t) }}
              </text>
            </template>
          </g>
          <!-- Meses -->
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
          <!-- Linha vertical que segue o mouse -->
          <line
            v-if="ativo !== null"
            :x1="x(ativo)"
            :x2="x(ativo)"
            :y1="M.topo - 6"
            :y2="M.topo + alturaPlot"
            class="stroke-borda-forte"
            stroke-width="1"
            shape-rendering="crispEdges"
          />
          <path :d="caminho" fill="none" class="stroke-grafico-serie" stroke-width="2" stroke-linejoin="round" stroke-linecap="round" />
          <!-- Pontos (com anel da cor do fundo) -->
          <template v-for="(p, i) in serie" :key="p.mes">
            <circle
              v-if="typeof p.nps === 'number' && (mostrarMarcadores || i === ultimoComValor || i === ativo || n === 1)"
              :cx="x(i)"
              :cy="y(p.nps)"
              :r="i === ativo ? 5.5 : 4"
              class="fill-grafico-serie stroke-superficie"
              stroke-width="2"
            />
          </template>
          <!-- Valor escrito só no último mês -->
          <text
            v-if="ultimoComValor >= 0 && ativo === null"
            :x="Math.min(Math.max(x(ultimoComValor), M.esq + 14), largura - 14)"
            :y="y(serie[ultimoComValor]!.nps as number) - 12"
            text-anchor="middle"
            class="fill-texto text-[13px] font-bold"
          >
            {{ formatarNps(serie[ultimoComValor]!.nps) }}
          </text>
        </svg>
      </div>

      <div
        v-if="dica"
        class="pointer-events-none absolute z-10 w-max max-w-48 rounded-lg border border-borda bg-superficie px-3 py-2 text-xs shadow-lg"
        :style="{
          left: `${(dica.px / largura) * 100}%`,
          top: `${dica.abaixo ? dica.py + 14 : dica.py - 14}px`,
          translate: `${dica.lado === 'esq' ? '0' : dica.lado === 'dir' ? '-100%' : '-50%'} ${dica.abaixo ? '0' : '-100%'}`,
        }"
        aria-hidden="true"
      >
        <p class="text-sm font-bold text-texto">{{ typeof dica.p.nps === 'number' ? `NPS ${formatarNps(dica.p.nps)}` : 'Sem NPS' }}</p>
        <p class="text-texto-suave">{{ formatarMes(dica.p.mes, 'longo') }}</p>
        <p class="text-texto-fraco">{{ formatarNumero(dica.p.total) }} {{ dica.p.total === 1 ? 'resposta' : 'respostas' }}</p>
      </div>
      <p class="sr-only" aria-live="polite">{{ anuncio }}</p>
      <p v-if="n === 1" class="mt-1 text-sm text-texto-fraco">Com respostas em mais meses, a linha da evolução aparece aqui.</p>
    </div>

    <div v-if="verTabela" class="max-h-80 overflow-y-auto rounded-xl border border-borda">
      <table class="w-full text-sm">
        <caption class="sr-only">NPS por mês</caption>
        <thead class="sticky top-0 bg-superficie-2">
          <tr>
            <th scope="col" class="px-4 py-2 text-left text-xs font-semibold uppercase tracking-wide text-texto-fraco">Mês</th>
            <th scope="col" class="px-4 py-2 text-right text-xs font-semibold uppercase tracking-wide text-texto-fraco">NPS</th>
            <th scope="col" class="px-4 py-2 text-right text-xs font-semibold uppercase tracking-wide text-texto-fraco">Respostas</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="p in serie" :key="p.mes" class="border-t border-borda">
            <th scope="row" class="px-4 py-2 text-left font-medium text-texto first-letter:uppercase">{{ formatarMes(p.mes, 'longo') }}</th>
            <td class="px-4 py-2 text-right font-semibold tabular-nums text-texto">{{ formatarNps(p.nps) }}</td>
            <td class="px-4 py-2 text-right tabular-nums text-texto-suave">{{ formatarNumero(p.total) }}</td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

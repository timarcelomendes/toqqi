<script setup lang="ts">
// Linha do NPS mês a mês (SVG feito à mão, sem biblioteca). Passe o mouse ou use as setas para ver
// cada mês; o mesmo conteúdo existe em tabela (botão "Ver em tabela").
// `destaque` (Início, painel v2): área azul bem clara sob a linha, faixa suave acima de 50, linha do zero sempre visível,
// meses do período (`no_periodo`) com fundo `marca-suave` atrás de tudo e uma barrinha coral no topo com "Período" (a
// faixa acima de 50 não passa por cima do período, para as cores não se misturarem) e o menor e o maior mês marcados
// com o valor (vermelho/verde); o valor do menor nunca encosta no nome do mês (perto do eixo, vai acima do ponto).
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { formatarNumero } from '@/utils/formatos'
import { saiuComMouse, usarFocoGrafico } from '@/composables/focoGrafico'
import { completarMeses, dominioNps, escala, extremosSerie, formatarMes, formatarNps } from './logica'

type Ponto = { mes: string; nps: number | null; total: number; no_periodo?: boolean }
const props = defineProps<{ pontos: Ponto[]; destaque?: boolean }>()
/** Mostrar a tabela em vez do gráfico (o botão fica no cabeçalho do cartão). */
const verTabela = defineModel<boolean>('tabela', { default: false })

const ALTURA = 232
const M = { topo: 26, base: 30, esq: 40, dir: 22 }
/** Com destaque, o topo tem a barrinha e o rótulo "Período" acima da área do gráfico. */
const TOPO_DESTAQUE = 42

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
const serie = computed(() => completarMeses(props.pontos) as Ponto[])
const n = computed(() => serie.value.length)
const valores = computed(() => serie.value.map((p) => p.nps).filter((v): v is number => typeof v === 'number'))
// Com destaque, o zero entra sempre na escala (a linha do zero separa o NPS negativo do positivo).
const dominio = computed(() => dominioNps(props.destaque && valores.value.length ? [...valores.value, 0] : valores.value))
/** Com destaque, sobra espaço à direita para o valor do último mês ao lado do ponto (não em cima da linha). */
const margemDir = computed(() => (props.destaque ? 40 : M.dir))
const larguraPlot = computed(() => Math.max(80, largura.value - M.esq - margemDir.value))
const topo = computed(() => (props.destaque ? TOPO_DESTAQUE : M.topo))
const alturaPlot = computed(() => ALTURA - topo.value - M.base)
const basePlot = computed(() => topo.value + alturaPlot.value)

const x = (i: number) => (n.value <= 1 ? M.esq + larguraPlot.value / 2 : M.esq + (i * larguraPlot.value) / (n.value - 1))
const y = computed(() => escala([dominio.value.min, dominio.value.max], [basePlot.value, topo.value]))
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

/** Área sob a linha (até a base do gráfico), um polígono por trecho contínuo. */
const areas = computed(() => {
  if (!props.destaque) return []
  const base = (basePlot.value).toFixed(1)
  const trechos: string[] = []
  let atual: string[] = []
  const fechar = () => {
    if (atual.length > 1) {
      const xs = atual.map((p) => p.split(',')[0])
      trechos.push(`${xs[0]},${base} ${atual.join(' ')} ${xs[xs.length - 1]},${base}`)
    }
    atual = []
  }
  serie.value.forEach((p, i) => {
    if (typeof p.nps !== 'number') return fechar()
    atual.push(`${x(i).toFixed(1)},${y.value(p.nps).toFixed(1)}`)
  })
  fechar()
  return trechos
})

/** Trechos horizontais fora do período (entre `x0` e `x1`): o que pinta o fundo não passa por cima do período. */
function foraDoPeriodo(x0: number, x1: number): { x: number; largura: number }[] {
  const per = periodo.value
  const pedacos: [number, number][] = per ? [[x0, Math.min(x1, per.x)], [Math.max(x0, per.x + per.largura), x1]] : [[x0, x1]]
  return pedacos.filter(([a, b]) => b - a > 0.5).map(([a, b]) => ({ x: a, largura: b - a }))
}

/** Faixa de fundo acima de 50 (só quando a escala passa de 50), fora do período (sem misturar cores). */
const faixa50 = computed(() => {
  if (!props.destaque || dominio.value.max <= 50) return []
  const altura = y.value(50) - topo.value
  return foraDoPeriodo(M.esq, M.esq + larguraPlot.value).map((p) => ({ ...p, y: topo.value, altura }))
})
/** A área azul também fica fora do período (recorte); dentro dele, só o fundo `marca-suave` e a linha. */
const recorteArea = computed(() => foraDoPeriodo(0, largura.value))
const idRecorte = `recorte-area-${Math.random().toString(36).slice(2, 9)}`

/** Fundo dos meses do período: um retângulo do primeiro ao último mês marcado (meia coluna de folga de cada lado). */
const periodo = computed(() => {
  if (!props.destaque) return null
  const idx = serie.value.map((p, i) => (p.no_periodo ? i : -1)).filter((i) => i >= 0)
  if (!idx.length || idx.length === n.value) return null
  const meio = n.value <= 1 ? larguraPlot.value / 2 : passoX.value / 2
  const x0 = Math.max(M.esq - 8, x(idx[0]!) - meio)
  const x1 = Math.min(largura.value - 4, x(idx[idx.length - 1]!) + meio)
  return { x: x0, largura: x1 - x0, meio: (x0 + x1) / 2 }
})

const extremos = computed(() => (props.destaque ? extremosSerie(serie.value) : { menor: null, maior: null }))
/**
 * Onde escrever o valor de um extremo: o último mês, à direita do ponto; o maior, acima; o menor, abaixo ou, se ali
 * encostaria no nome do mês, ao lado do ponto (à esquerda; perto da borda esquerda, à direita) — nunca sobre a linha.
 */
function rotuloExtremo(i: number, v: number): { x: number; y: number; ancora: 'start' | 'middle' | 'end' } {
  const px = x(i)
  const py = y.value(v)
  if (i === ultimoComValor.value) return { x: px + 10, y: py + 4, ancora: 'start' }
  const centro = Math.min(Math.max(px, M.esq + 14), largura.value - 14)
  if (i === extremos.value.maior) return { x: centro, y: py - 11, ancora: 'middle' }
  if (py + 20 <= basePlot.value - 2) return { x: centro, y: py + 20, ancora: 'middle' }
  return px - M.esq < 34 ? { x: px + 10, y: py + 4, ancora: 'start' } : { x: px - 10, y: py + 4, ancora: 'end' }
}
function ehExtremo(i: number) {
  return i === extremos.value.menor || i === extremos.value.maior
}

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
  anuncio.value = `${formatarMes(p.mes, 'longo')}: ${typeof p.nps === 'number' ? `NPS ${formatarNps(p.nps)}` : 'sem NPS'}, ${formatarNumero(p.total)} ${p.total === 1 ? 'resposta' : 'respostas'}${props.destaque && p.no_periodo ? ', no período do painel' : ''}.`
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
  const py = typeof p.nps === 'number' ? y.value(p.nps) : topo.value + alturaPlot.value / 2
  const lado = px < 90 ? 'esq' : px > largura.value - 90 ? 'dir' : 'meio'
  // Perto do topo, a dica vai para baixo do ponto (não cobre os botões de cima).
  const abaixo = py < 72
  return { p, px, py, lado, abaixo }
})

const descricao = computed(() => {
  if (!n.value) return 'Sem dados.'
  const ult = ultimoComValor.value >= 0 ? serie.value[ultimoComValor.value] : null
  return `NPS por mês, de ${formatarMes(serie.value[0]!.mes, 'longo')} a ${formatarMes(serie.value[n.value - 1]!.mes, 'longo')}.` +
    (ult ? ` Último: ${formatarNps(ult.nps)}.` : '') +
    (extremos.value.menor !== null && extremos.value.maior !== null
      ? ` Menor: ${formatarNps(serie.value[extremos.value.menor]!.nps)} em ${formatarMes(serie.value[extremos.value.menor]!.mes, 'longo')}; maior: ${formatarNps(serie.value[extremos.value.maior]!.nps)} em ${formatarMes(serie.value[extremos.value.maior]!.mes, 'longo')}.`
      : '')
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
          <!-- Fundo (destaque): meses do período atrás de tudo, com a barrinha coral e "Período" no topo; a faixa acima de 50
               fica fora do período (as cores não se misturam) -->
          <g v-if="periodo" data-periodo>
            <rect :x="periodo.x" :y="topo - 22" :width="periodo.largura" :height="alturaPlot + 22" rx="6" class="fill-marca-suave" />
            <rect :x="periodo.x" :y="topo - 22" :width="periodo.largura" height="3" rx="1.5" class="fill-marca" />
            <text :x="periodo.meio" :y="topo - 8" text-anchor="middle" class="fill-marca-texto text-[11px] font-semibold">Período</text>
          </g>
          <rect v-for="(f, i) in faixa50" :key="`f-${i}`" :x="f.x" :y="f.y" :width="f.largura" :height="f.altura" class="fill-sucesso-suave" opacity="0.8" />
          <!-- Grade (linhas finas e discretas) e o zero um pouco mais forte -->
          <g>
            <template v-for="t in dominio.ticks" :key="t">
              <line
                :x1="M.esq"
                :x2="largura - margemDir"
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
            :y1="topo - 6"
            :y2="basePlot"
            class="stroke-borda-forte"
            stroke-width="1"
            shape-rendering="crispEdges"
          />
          <clipPath v-if="areas.length" :id="idRecorte">
            <rect v-for="(r, i) in recorteArea" :key="i" :x="r.x" :y="0" :width="r.largura" :height="ALTURA" />
          </clipPath>
          <polygon v-for="(a, i) in areas" :key="`a-${i}`" :points="a" class="fill-grafico-serie" fill-opacity="0.07" :clip-path="`url(#${idRecorte})`" />
          <path :d="caminho" fill="none" class="stroke-grafico-serie" stroke-linejoin="round" stroke-linecap="round" :stroke-width="destaque ? 2.5 : 2" />
          <!-- Pontos (com anel da cor do fundo) -->
          <template v-for="(p, i) in serie" :key="p.mes">
            <circle
              v-if="typeof p.nps === 'number' && !ehExtremo(i) && (mostrarMarcadores || i === ultimoComValor || i === ativo || n === 1)"
              :cx="x(i)"
              :cy="y(p.nps)"
              :r="i === ativo ? 5.5 : 4"
              class="fill-grafico-serie stroke-superficie"
              stroke-width="2"
            />
          </template>
          <!-- Menor e maior mês (destaque): anel colorido e o valor escrito -->
          <template v-for="(p, i) in serie" :key="`e-${p.mes}`">
            <template v-if="ehExtremo(i) && typeof p.nps === 'number'">
              <circle
                :cx="x(i)"
                :cy="y(p.nps)"
                r="5.5"
                class="fill-superficie"
                :class="i === extremos.maior ? 'stroke-grafico-promotor' : 'stroke-grafico-detrator'"
                stroke-width="2.5"
                data-extremo
              />
              <text
                :x="rotuloExtremo(i, p.nps).x"
                :y="rotuloExtremo(i, p.nps).y"
                :text-anchor="rotuloExtremo(i, p.nps).ancora"
                class="text-[12px] font-bold"
                :class="i === extremos.maior ? 'fill-sucesso' : 'fill-erro'"
              >
                {{ formatarNps(p.nps) }}
              </text>
            </template>
          </template>
          <!-- Valor escrito só no último mês -->
          <text
            v-if="ultimoComValor >= 0 && ativo === null && !ehExtremo(ultimoComValor)"
            :x="destaque ? x(ultimoComValor) + 9 : Math.min(Math.max(x(ultimoComValor), M.esq + 14), largura - 14)"
            :y="destaque ? y(serie[ultimoComValor]!.nps as number) + 4 : y(serie[ultimoComValor]!.nps as number) - 12"
            :text-anchor="destaque ? 'start' : 'middle'"
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
        <p v-if="destaque && dica.p.no_periodo" class="text-marca-texto">No período do painel</p>
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
            <th v-if="destaque" scope="col" class="px-4 py-2 text-right text-xs font-semibold uppercase tracking-wide text-texto-fraco">No período</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="p in serie" :key="p.mes" class="border-t border-borda" :class="destaque && p.no_periodo ? 'bg-marca-suave/60' : ''">
            <th scope="row" class="px-4 py-2 text-left font-medium text-texto first-letter:uppercase">{{ formatarMes(p.mes, 'longo') }}</th>
            <td class="px-4 py-2 text-right font-semibold tabular-nums text-texto">{{ formatarNps(p.nps) }}</td>
            <td class="px-4 py-2 text-right tabular-nums text-texto-suave">{{ formatarNumero(p.total) }}</td>
            <td v-if="destaque" class="px-4 py-2 text-right text-texto-suave">{{ p.no_periodo ? 'Sim' : 'Não' }}</td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

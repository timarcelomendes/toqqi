<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { Download, MessageSquareText } from 'lucide-vue-next'
import { formulariosApi, mensagemDoErro, type Id, type Pergunta, type Resposta, type ResultadoPergunta, type Resultados } from '@/api'
import { avisar } from '@/composables/avisos'
import { formatarData, hojeIso } from '@/utils/datas'
import { formatarNumero, plural } from '@/utils/formatos'
import { CANAIS, GRUPOS_NOTA, tomGrupo } from '@/utils/rotulos'
import { ROTULOS_CONTEXTO, type CampoContexto } from '@/pesquisa/tipos'
import { renderizarVariaveis } from '@/pesquisa/variaveis'
import { quandoFoiResposta, seloOrigem } from '@/modulos/respostas/logica'
import { useSessaoStore } from '@/stores/sessao'
import Alerta from '@/components/ui/Alerta.vue'
import Botao from '@/components/ui/Botao.vue'
import Carregando from '@/components/ui/Carregando.vue'
import EstadoVazio from '@/components/ui/EstadoVazio.vue'
import Etiqueta from '@/components/ui/Etiqueta.vue'
import Paginacao from '@/components/ui/Paginacao.vue'
import Selecao from '@/components/ui/Selecao.vue'

const props = defineProps<{ formularioId: Id; perguntas: Pergunta[] }>()

type Periodo = '7' | '30' | '90' | '365' | 'tudo'
const PERIODOS: { valor: Periodo; rotulo: string }[] = [
  { valor: '7', rotulo: 'Últimos 7 dias' },
  { valor: '30', rotulo: 'Últimos 30 dias' },
  { valor: '90', rotulo: 'Últimos 90 dias' },
  { valor: '365', rotulo: 'Últimos 12 meses' },
  { valor: 'tudo', rotulo: 'Desde o começo' },
]
const periodo = ref<Periodo>('30')
const intervalo = computed(() => (periodo.value === 'tudo' ? {} : { de: hojeIso(-(Number(periodo.value) - 1)), ate: hojeIso() }))

const resultados = ref<Resultados | null>(null)
const respostas = ref<Resposta[]>([])
const total = ref(0)
const porPagina = ref(50)
const pagina = ref(1)
const carregando = ref(true)
const carregandoLista = ref(false)
const erro = ref<string | null>(null)
const baixando = ref(false)

async function carregar() {
  carregando.value = true
  erro.value = null
  pagina.value = 1
  try {
    const [r, l] = await Promise.all([
      formulariosApi.resultados(props.formularioId, intervalo.value),
      formulariosApi.respostas(props.formularioId, { ...intervalo.value, pagina: 1 }),
    ])
    resultados.value = r
    respostas.value = l.itens
    total.value = l.total
    porPagina.value = l.por_pagina || 50
  } catch (e) {
    erro.value = mensagemDoErro(e)
  } finally {
    carregando.value = false
  }
}

async function carregarPagina() {
  carregandoLista.value = true
  try {
    const l = await formulariosApi.respostas(props.formularioId, { ...intervalo.value, pagina: pagina.value })
    respostas.value = l.itens
    total.value = l.total
  } catch (e) {
    avisar.erro(mensagemDoErro(e))
  } finally {
    carregandoLista.value = false
  }
}

async function baixarCsv() {
  baixando.value = true
  try {
    await formulariosApi.baixarRespostasCsv(props.formularioId, intervalo.value)
  } catch (e) {
    avisar.erro(mensagemDoErro(e))
  } finally {
    baixando.value = false
  }
}

watch(periodo, carregar)
watch(pagina, (p, antes) => {
  if (p !== antes && !carregando.value) carregarPagina()
})
onMounted(carregar)

// NPS
const nps = computed(() => {
  const n = resultados.value?.nps
  if (!n) return null
  const soma = (n.promotores ?? 0) + (n.neutros ?? 0) + (n.detratores ?? 0)
  const pct = (v: number) => (soma ? Math.round((v / soma) * 100) : 0)
  return {
    valor: Math.round(n.valor),
    grupos: [
      { chave: 'promotores', rotulo: 'Promotores (9–10)', qtd: n.promotores, pct: pct(n.promotores), cor: 'bg-emerald-600', texto: 'text-sucesso' },
      { chave: 'neutros', rotulo: 'Neutros (7–8)', qtd: n.neutros, pct: pct(n.neutros), cor: 'bg-amber-400', texto: 'text-atencao' },
      { chave: 'detratores', rotulo: 'Detratores (0–6)', qtd: n.detratores, pct: pct(n.detratores), cor: 'bg-red-600', texto: 'text-erro' },
    ],
  }
})
const tomNps = computed(() => (!nps.value ? 'text-texto' : nps.value.valor >= 50 ? 'text-sucesso' : nps.value.valor >= 0 ? 'text-atencao' : 'text-erro'))
const zonaNps = computed(() => {
  const v = nps.value?.valor ?? 0
  return v >= 75 ? 'Excelente' : v >= 50 ? 'Muito bom' : v >= 0 ? 'Razoável' : 'Crítico'
})
// Ponteiro do medidor: -100 → 180°, 100 → 0°
const ponteiro = computed(() => {
  const v = Math.max(-100, Math.min(100, nps.value?.valor ?? 0))
  const ang = Math.PI * (1 - (v + 100) / 200)
  return { x: 60 + 44 * Math.cos(ang), y: 60 - 44 * Math.sin(ang) }
})

const sessao = useSessaoStore()
function faixaDoGrupo(rotulo: string): string {
  const faixa = rotulo.split(' (')[1]
  return faixa ? 'notas ' + faixa.replace(')', '') : ''
}
function tituloPergunta(r: ResultadoPergunta) {
  const bruto = r.titulo || props.perguntas.find((p) => p.id === r.id)?.titulo || 'Pergunta'
  // mostra o título como o cliente viu: {empresa} vira o nome da conta; {nome} some
  return renderizarVariaveis(bruto, { empresa: sessao.conta?.nome ?? '' })
}

/** Distribuição com todos os valores da faixa (inclusive os sem resposta). */
function barras(r: ResultadoPergunta) {
  const d = r.distribuicao ?? {}
  const chaves = Object.keys(d).map(Number).filter((n) => !Number.isNaN(n))
  const p = props.perguntas.find((x) => x.id === r.id)
  let min = chaves.length ? Math.min(...chaves) : 0
  let max = chaves.length ? Math.max(...chaves) : 0
  if (r.tipo === 'nps') [min, max] = [0, 10]
  else if (r.tipo === 'csat' || r.tipo === 'estrelas') [min, max] = [1, 5]
  else if (r.tipo === 'escala' && p) [min, max] = [p.min ?? min, p.max ?? max]
  const itens = []
  for (let v = min; v <= max; v++) itens.push({ valor: v, qtd: Number(d[String(v)] ?? 0) })
  const maior = Math.max(1, ...itens.map((i) => i.qtd))
  return itens.map((i) => ({ ...i, altura: (i.qtd / maior) * 100 }))
}

function corBarra(tipo: string, v: number) {
  if (tipo === 'nps') return v <= 6 ? 'bg-red-600' : v <= 8 ? 'bg-amber-400' : 'bg-emerald-600'
  if (tipo === 'csat' || tipo === 'estrelas') return v <= 2 ? 'bg-red-600' : v === 3 ? 'bg-amber-400' : 'bg-emerald-600'
  return 'bg-marca'
}

function opcoesOrdenadas(r: ResultadoPergunta) {
  const o = r.opcoes ?? {}
  const soma = Math.max(1, r.respostas || Object.values(o).reduce((a, b) => a + b, 0))
  return Object.entries(o)
    .map(([opcao, qtd]) => ({ opcao: opcao === 'true' ? 'Sim' : opcao === 'false' ? 'Não' : opcao, qtd, pct: Math.round((qtd / soma) * 100) }))
    .sort((a, b) => b.qtd - a.qtd)
}

function formatarMedia(m: number | null | undefined) {
  return typeof m === 'number' ? m.toLocaleString('pt-BR', { maximumFractionDigits: 1 }) : '—'
}

function chipsContexto(r: Resposta) {
  return Object.entries(r.contexto ?? {})
    .filter(([, v]) => v)
    .map(([k, v]) => `${ROTULOS_CONTEXTO[k as CampoContexto] ?? k}: ${v}`)
}
</script>

<template>
  <div class="flex flex-col gap-5">
    <div class="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
      <Selecao v-model="periodo" rotulo="Período" :opcoes="PERIODOS" class="sm:w-56" />
      <Botao variante="secundario" :carregando="baixando" :desabilitado="!total" @click="baixarCsv"><Download class="size-4" aria-hidden="true" /> Baixar planilha (CSV)</Botao>
    </div>

    <Carregando v-if="carregando" :linhas="4" />
    <Alerta v-else-if="erro" tom="erro">
      {{ erro }} <button type="button" class="link ml-1" @click="carregar">Tentar de novo</button>
    </Alerta>
    <div v-else-if="!resultados?.total" class="cartao">
      <EstadoVazio :icone="MessageSquareText" titulo="Nenhuma resposta neste período" descricao="Compartilhe o link ou o QR Code e as respostas aparecem aqui assim que chegarem." />
    </div>

    <template v-else-if="resultados">
      <!-- Resumo -->
      <div class="grid gap-4" :class="nps || resultados.csat ? 'lg:grid-cols-3' : ''">
        <section v-if="nps" class="cartao flex flex-col gap-4 p-5 lg:col-span-2" aria-labelledby="t-nps">
          <h2 id="t-nps" class="font-bold text-texto">NPS</h2>
          <div class="flex flex-col items-center gap-5 sm:flex-row">
            <div class="relative w-44 shrink-0">
              <svg viewBox="0 0 120 68" class="w-full" aria-hidden="true">
                <path d="M16 60 A44 44 0 0 1 104 60" fill="none" stroke="currentColor" stroke-width="10" stroke-linecap="round" class="text-superficie-2" />
                <path d="M16 60 A44 44 0 0 1 60 16" fill="none" stroke-width="10" stroke-linecap="round" class="stroke-red-500/70" />
                <path d="M60 16 A44 44 0 0 1 91.1 28.9" fill="none" stroke-width="10" class="stroke-amber-400/80" />
                <path d="M91.1 28.9 A44 44 0 0 1 104 60" fill="none" stroke-width="10" stroke-linecap="round" class="stroke-emerald-500/80" />
                <circle :cx="ponteiro.x" :cy="ponteiro.y" r="6" class="fill-superficie stroke-texto" stroke-width="3" />
              </svg>
              <p class="-mt-7 text-center">
                <span class="text-4xl font-extrabold tabular-nums" :class="tomNps">{{ nps.valor }}</span>
              </p>
              <p class="text-center text-xs font-semibold text-texto-fraco">{{ zonaNps }} · de −100 a 100</p>
              <p class="sr-only">NPS {{ nps.valor }}, {{ zonaNps }}.</p>
            </div>
            <div class="flex w-full flex-col gap-3">
              <div class="flex h-4 w-full gap-0.5 overflow-hidden rounded-full" aria-hidden="true">
                <div v-for="g in nps.grupos" :key="g.chave" :class="g.cor" :style="{ width: `${g.pct}%` }" :title="`${g.rotulo}: ${g.pct}%`" />
              </div>
              <ul class="grid grid-cols-3 gap-3 text-sm">
                <li v-for="g in nps.grupos" :key="g.chave">
                  <span class="flex min-w-0 items-center gap-1.5 font-semibold text-texto-suave"><span class="size-2.5 shrink-0 rounded-full" :class="g.cor" aria-hidden="true" /><span class="truncate">{{ g.rotulo.split(' (')[0] }}</span></span>
                  <span class="block text-xs text-texto-fraco">{{ faixaDoGrupo(g.rotulo) }}</span>
                  <span class="text-lg font-bold text-texto">{{ g.pct }}%</span>
                  <span class="block text-xs text-texto-fraco">{{ plural(g.qtd, 'pessoa', 'pessoas') }}</span>
                </li>
              </ul>
              <p class="text-xs text-texto-fraco">NPS = % de promotores − % de detratores.</p>
            </div>
          </div>
        </section>
        <section v-else-if="resultados.csat" class="cartao flex flex-col gap-2 p-5 lg:col-span-2" aria-labelledby="t-csat">
          <h2 id="t-csat" class="font-bold text-texto">Satisfação (CSAT)</h2>
          <p class="text-5xl font-extrabold tabular-nums" :class="resultados.csat.percentual >= 80 ? 'text-sucesso' : resultados.csat.percentual >= 60 ? 'text-atencao' : 'text-erro'">
            {{ formatarMedia(resultados.csat.percentual) }}%
          </p>
          <p class="text-sm text-texto-suave">das pessoas deram 4 ou 5. Média: <strong class="text-texto">{{ formatarMedia(resultados.csat.media) }}</strong> de 5.</p>
        </section>
        <section class="cartao flex flex-col justify-center gap-1 p-5" aria-labelledby="t-total">
          <h2 id="t-total" class="text-sm font-semibold text-texto-fraco">Respostas no período</h2>
          <p class="text-4xl font-extrabold tabular-nums text-texto">{{ formatarNumero(resultados.total) }}</p>
          <p v-if="nps && resultados.csat" class="text-sm text-texto-suave">CSAT: {{ formatarMedia(resultados.csat.percentual) }}% satisfeitos</p>
        </section>
      </div>

      <!-- Por pergunta -->
      <section aria-labelledby="t-perguntas" class="flex flex-col gap-3">
        <h2 id="t-perguntas" class="text-lg font-bold text-texto">Pergunta por pergunta</h2>
        <div class="grid gap-4 lg:grid-cols-2">
          <article v-for="r in resultados.perguntas" :key="r.id" class="cartao flex flex-col gap-3 p-5">
            <header>
              <h3 class="font-semibold text-texto">{{ tituloPergunta(r) }}</h3>
              <p class="text-xs text-texto-fraco">
                {{ plural(r.respostas, 'resposta', 'respostas') }}<template v-if="typeof r.media === 'number'"> · média {{ formatarMedia(r.media) }}</template>
              </p>
            </header>

            <!-- Distribuição de notas -->
            <div v-if="r.distribuicao">
              <div class="flex h-28 items-end gap-0.5" role="img" :aria-label="`Distribuição: ${barras(r).map((b) => `${b.valor}: ${b.qtd}`).join(', ')}`">
                <div v-for="b in barras(r)" :key="b.valor" class="group flex h-full flex-1 flex-col items-center justify-end" :title="`Nota ${b.valor}: ${b.qtd}`">
                  <span class="mb-0.5 text-[0.65rem] font-semibold tabular-nums text-texto-fraco">{{ b.qtd || '' }}</span>
                  <div class="w-full max-w-8 rounded-t-[4px]" :class="corBarra(r.tipo, b.valor)" :style="{ height: `${Math.max(b.altura, b.qtd ? 3 : 0)}%` }" />
                </div>
              </div>
              <div class="mt-1 flex gap-0.5 border-t border-borda pt-1" aria-hidden="true">
                <span v-for="b in barras(r)" :key="b.valor" class="flex-1 text-center text-xs font-semibold text-texto-suave">{{ b.valor }}</span>
              </div>
            </div>

            <!-- Opções -->
            <ul v-if="r.opcoes && Object.keys(r.opcoes).length" class="flex flex-col gap-2">
              <li v-for="o in opcoesOrdenadas(r)" :key="o.opcao" class="text-sm">
                <div class="flex justify-between gap-3">
                  <span class="min-w-0 truncate text-texto-suave">{{ o.opcao }}</span>
                  <span class="shrink-0 font-semibold tabular-nums text-texto">{{ o.qtd }} <span class="font-normal text-texto-fraco">({{ o.pct }}%)</span></span>
                </div>
                <div class="mt-1 h-2 rounded-full bg-superficie-2" aria-hidden="true"><div class="h-full rounded-full bg-marca" :style="{ width: `${o.pct}%` }" /></div>
              </li>
            </ul>

            <!-- Textos -->
            <ul v-if="r.textos?.length" class="flex max-h-64 flex-col divide-y divide-borda overflow-y-auto rounded-xl border border-borda">
              <li v-for="(t, i) in r.textos" :key="i" class="px-3 py-2 text-sm">
                <p class="whitespace-pre-line text-texto">{{ t.texto }}</p>
                <p class="text-xs text-texto-fraco">{{ formatarData(t.data) }}</p>
              </li>
            </ul>
            <p v-else-if="!r.distribuicao && !r.opcoes && !r.respostas" class="text-sm text-texto-fraco">Sem respostas no período.</p>
          </article>
        </div>
      </section>

      <!-- Lista de respostas -->
      <section class="cartao" aria-labelledby="t-lista">
        <h2 id="t-lista" class="border-b border-borda px-5 py-4 font-bold text-texto">Respostas</h2>
        <ol class="divide-y divide-borda" :aria-busy="carregandoLista || undefined" :class="{ 'opacity-60': carregandoLista }">
          <li v-for="r in respostas" :key="String(r.id)" class="flex gap-4 px-5 py-4">
            <span
              v-if="r.nota !== null && r.nota !== undefined"
              class="flex size-10 shrink-0 items-center justify-center rounded-xl text-base font-extrabold"
              :class="{
                'bg-sucesso-suave text-sucesso': tomGrupo(r.grupo, r.nota, r.tipo_nota) === 'sucesso',
                'bg-atencao-suave text-atencao': tomGrupo(r.grupo, r.nota, r.tipo_nota) === 'atencao',
                'bg-erro-suave text-erro': tomGrupo(r.grupo, r.nota, r.tipo_nota) === 'erro',
              }"
              :aria-label="`Nota ${r.nota}`"
            >{{ r.nota }}</span>
            <span v-else class="flex size-10 shrink-0 items-center justify-center rounded-xl bg-superficie-2 text-texto-fraco" aria-hidden="true"><MessageSquareText class="size-4" /></span>
            <div class="min-w-0 flex-1">
              <div class="flex flex-wrap items-center gap-x-2 gap-y-1">
                <p class="font-semibold text-texto">
                  <RouterLink v-if="r.contato" :to="`/contatos/${r.contato.id}`" class="hover:underline">{{ r.contato.nome }}</RouterLink>
                  <template v-else>Anônimo</template>
                </p>
                <span v-if="r.empresa" class="text-sm text-texto-suave">· {{ r.empresa.nome }}</span>
                <Etiqueta v-if="r.grupo" :tom="tomGrupo(r.grupo, r.nota, r.tipo_nota)">{{ GRUPOS_NOTA[r.grupo] ?? r.grupo }}</Etiqueta>
                <Etiqueta v-if="seloOrigem(r.origem)" tom="neutro">{{ seloOrigem(r.origem) }}</Etiqueta>
              </div>
              <!-- A data da resposta (a informada, nas registradas à mão e importadas); a de entrada só se não vier. -->
              <p class="text-xs text-texto-fraco">{{ quandoFoiResposta(r) }} · {{ CANAIS[r.canal] ?? r.canal }}</p>
              <p v-if="r.comentario" class="mt-1.5 whitespace-pre-line text-sm text-texto-suave">{{ r.comentario }}</p>
              <div v-if="chipsContexto(r).length || r.referencia" class="mt-2 flex flex-wrap gap-1.5">
                <Etiqueta v-if="r.referencia" tom="info">Ref.: {{ r.referencia }}</Etiqueta>
                <Etiqueta v-for="c in chipsContexto(r)" :key="c" tom="neutro">{{ c }}</Etiqueta>
              </div>
            </div>
          </li>
        </ol>
        <Paginacao v-model="pagina" :total="total" :por-pagina="porPagina" :carregando="carregandoLista" :nome-itens="total === 1 ? 'resposta' : 'respostas'" />
      </section>
    </template>
  </div>
</template>

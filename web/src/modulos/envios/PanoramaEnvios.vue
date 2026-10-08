<script setup lang="ts">
// O topo de Envios (docs/api-envios-panorama.md): em uma frase, o que o envio automático vai fazer e quando; as regras
// em uma linha; a agenda dos próximos 14 dias (pesquisas e lembretes por dia) e quantos responderam nos últimos 30.
// `recarregar` atualiza sem piscar depois de um envio ou de uma rodada pedida na hora.
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { Minus, TrendingDown, TrendingUp } from 'lucide-vue-next'
import { enviosApi, mensagemDoErro, type PanoramaEnvios } from '@/api'
import { hojeIso } from '@/utils/datas'
import { formatarNumero, plural } from '@/utils/formatos'
import Alerta from '@/components/ui/Alerta.vue'
import { ROTULO_CANAL, agenda, detalheDia, manchete, regras, respondidas, tempoAteMetade, totalAgenda, variacaoTaxa } from './panorama'

const dados = ref<PanoramaEnvios | null>(null)
const carregando = ref(true)
const erro = ref<string | null>(null)
let controle: AbortController | null = null

async function carregar(silencioso = false) {
  controle?.abort()
  const meu = (controle = new AbortController())
  if (!silencioso) carregando.value = !dados.value
  erro.value = null
  try {
    dados.value = await enviosApi.panorama(meu.signal)
  } catch (e) {
    if (e instanceof DOMException && e.name === 'AbortError') return
    if (!silencioso || !dados.value) erro.value = mensagemDoErro(e)
  } finally {
    if (controle === meu) carregando.value = false
  }
}

onMounted(() => carregar())
onBeforeUnmount(() => controle?.abort())
defineExpose({ recarregar: () => carregar(true) })

const hoje = hojeIso()
const a = computed(() => dados.value?.automatico ?? null)
const m = computed(() => (a.value ? manchete(a.value, hoje, Date.now()) : null))
const dias = computed(() => (dados.value ? agenda(dados.value, hoje) : []))
const r = computed(() => dados.value?.respostas ?? null)
const variacao = computed(() => (r.value ? variacaoTaxa(r.value) : null))
const tempo = computed(() => (r.value ? tempoAteMetade(r.value.horas_ate_metade) : null))
const semEnvio = computed(() => dias.value.some((d) => !d.sai && !d.hoje))

const COR_ESTADO = { sucesso: 'text-sucesso', atencao: 'text-atencao', neutro: 'text-texto-suave' } as const
const PONTO_ESTADO = { sucesso: 'bg-sucesso', atencao: 'bg-atencao', neutro: 'bg-texto-fraco' } as const
const COR_VARIACAO = { subiu: 'text-sucesso', caiu: 'text-atencao', igual: 'text-texto-fraco' } as const
const ICONE_VARIACAO = { subiu: TrendingUp, caiu: TrendingDown, igual: Minus } as const
/** Dia sem envio: listras finas no lugar das barras. */
const LISTRAS = { backgroundImage: 'repeating-linear-gradient(135deg, var(--t-superficie-2) 0 4px, transparent 4px 8px)' }
</script>

<template>
  <section class="cartao mb-6 p-5 sm:p-7" aria-labelledby="t-panorama-envios" :aria-busy="carregando || undefined" data-panorama-envios>
    <div v-if="carregando && !dados" class="animate-pulse" role="status" aria-label="Carregando o resumo dos envios">
      <div class="h-3.5 w-40 rounded bg-superficie-2" />
      <div class="mt-3 h-7 w-2/3 rounded-lg bg-superficie-2" />
      <div class="mt-2 h-3.5 w-1/2 rounded bg-superficie-2" />
      <div class="mt-8 flex h-24 items-end gap-1.5">
        <div v-for="i in 14" :key="i" class="flex-1 rounded-t bg-superficie-2" :style="{ height: `${20 + ((i * 37) % 70)}%` }" />
      </div>
    </div>

    <Alerta v-else-if="erro && !dados" tom="erro">
      Não deu para carregar o resumo dos envios: {{ erro }} <button type="button" class="link ml-1" @click="carregar()">Tentar de novo</button>
    </Alerta>

    <div v-else-if="dados && a && m && r" class="grid gap-x-10 gap-y-8 lg:grid-cols-[minmax(0,1fr)_15.5rem]">
      <div class="min-w-0">
        <p class="flex items-center gap-2 text-sm font-semibold" :class="COR_ESTADO[m.tom]" data-estado-envio>
          <span class="size-2 shrink-0 rounded-full" :class="PONTO_ESTADO[m.tom]" aria-hidden="true" />
          {{ m.estado }}
        </p>
        <h2 id="t-panorama-envios" class="mt-1.5 text-xl leading-snug font-bold text-texto sm:text-[1.6rem]" data-manchete>{{ m.titulo }}</h2>
        <p v-if="m.texto" class="mt-1 text-sm text-texto-suave" data-manchete-texto>{{ m.texto }}</p>
        <p class="mt-1 text-sm text-texto-fraco" data-regras>
          {{ regras(a) }} <RouterLink to="/configuracoes/envios" class="link whitespace-nowrap">Mudar as regras</RouterLink>
        </p>

        <!-- Os próximos 14 dias: pesquisas e lembretes por dia -->
        <figure class="mt-7" aria-labelledby="t-agenda-envios" data-agenda>
          <div class="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
            <p id="t-agenda-envios" class="text-sm font-semibold text-texto-suave" data-total-agenda>{{ totalAgenda(dados) }}</p>
            <p class="flex items-center gap-3 text-xs text-texto-fraco" data-legenda-agenda>
              <span class="inline-flex items-center gap-1.5"><span class="size-2.5 rounded-[3px] bg-grafico-tema-2" aria-hidden="true" />Pesquisas</span>
              <span class="inline-flex items-center gap-1.5"><span class="size-2.5 rounded-[3px] bg-grafico-serie" aria-hidden="true" />Lembretes</span>
            </p>
          </div>
          <ol class="mt-3 grid grid-cols-[repeat(14,minmax(0,1fr))] gap-1 sm:gap-1.5" aria-hidden="true">
            <li v-for="d in dias" :key="d.dia" class="flex min-w-0 flex-col items-center" :title="detalheDia(d, a.so_dias_uteis)" :data-dia="d.dia">
              <div class="flex h-24 w-full flex-col-reverse items-center gap-0.5 rounded-t-md border-b border-borda-forte" :style="d.sai ? undefined : LISTRAS">
                <span
                  v-if="d.pesquisas"
                  class="block w-full max-w-6 shrink-0 bg-grafico-tema-2"
                  :class="d.lembretes ? '' : 'rounded-t-[4px]'"
                  :style="{ height: `${d.alturaPesquisas}%` }"
                  data-barra-pesquisas
                />
                <span
                  v-if="d.lembretes"
                  class="block w-full max-w-6 shrink-0 rounded-t-[4px] bg-grafico-serie"
                  :style="{ height: `${d.alturaLembretes}%` }"
                  data-barra-lembretes
                />
              </div>
              <!-- No celular, só o dia do mês (o de hoje em destaque); a partir de 640 px, também o dia da semana -->
              <span class="mt-1.5 hidden max-w-full truncate text-[0.7rem] leading-tight font-semibold sm:block" :class="d.hoje ? 'text-texto' : 'text-texto-fraco'">{{
                d.rotulo
              }}</span>
              <span
                class="mt-1.5 text-[0.7rem] leading-tight tabular-nums sm:mt-0"
                :class="d.hoje ? 'font-bold text-texto underline decoration-marca decoration-2 underline-offset-4 sm:font-normal sm:text-texto-suave sm:no-underline' : 'text-texto-fraco'"
                >{{ d.numero }}</span
              >
            </li>
          </ol>
          <p v-if="semEnvio" class="mt-2 text-xs text-texto-fraco">
            Dias listrados não têm envio: o que cairia neles sai no próximo dia {{ a.so_dias_uteis ? 'útil' : 'com envio' }}.
          </p>
          <div class="sr-only">
            <table>
              <caption>Pesquisas e lembretes previstos nos próximos 14 dias</caption>
              <thead>
                <tr><th scope="col">Dia</th><th scope="col">Pesquisas</th><th scope="col">Lembretes</th></tr>
              </thead>
              <tbody>
                <tr v-for="d in dias" :key="d.dia">
                  <th scope="row">{{ d.longo }}{{ d.sai ? '' : ' (sem envio)' }}</th>
                  <td>{{ formatarNumero(d.pesquisas) }}</td>
                  <td>{{ formatarNumero(d.lembretes) }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </figure>
      </div>

      <!-- Quantos responderam -->
      <div class="border-t border-borda pt-6 lg:border-t-0 lg:border-l lg:pt-0 lg:pl-8" data-respostas-envios>
        <h3 class="text-sm font-semibold text-texto-suave">Taxa de resposta</h3>
        <p class="mt-2 text-5xl leading-none font-extrabold tracking-tight text-texto" data-taxa>
          {{ r.taxa === null ? '—' : `${formatarNumero(r.taxa)}%` }}
        </p>
        <p class="mt-2.5 text-sm text-texto-suave" data-respondidas>{{ respondidas(r) ?? 'Nenhuma pesquisa saiu nos últimos 30 dias.' }}</p>
        <p v-if="variacao" class="mt-1 flex items-center gap-1.5 text-sm font-semibold" :class="COR_VARIACAO[variacao.sentido]" data-variacao-taxa>
          <component :is="ICONE_VARIACAO[variacao.sentido]" class="size-4 shrink-0" aria-hidden="true" />
          {{ variacao.texto }}
        </p>
        <p v-if="tempo" class="mt-1 text-sm text-texto-fraco" data-tempo-resposta>{{ tempo }}</p>
        <ul v-if="r.canais.length > 1" class="mt-5 flex flex-col gap-3" aria-label="Por canal" data-canais>
          <li v-for="c in r.canais" :key="c.canal">
            <div class="flex items-baseline justify-between gap-2 text-sm">
              <span class="font-semibold text-texto">{{ ROTULO_CANAL[c.canal] }}</span>
              <span class="text-texto-suave">
                <strong class="font-bold text-texto">{{ c.taxa === null ? '—' : `${formatarNumero(c.taxa)}%` }}</strong>
                <span class="text-texto-fraco"> de {{ plural(c.enviadas, 'enviada', 'enviadas') }}</span>
              </span>
            </div>
            <div class="mt-1.5 h-2 w-full rounded-r-[4px] bg-superficie-2" aria-hidden="true">
              <div class="h-full rounded-r-[4px] bg-grafico-serie" :style="{ width: `${c.taxa ?? 0}%` }" />
            </div>
          </li>
        </ul>
      </div>
    </div>
  </section>
</template>

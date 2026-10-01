<script setup lang="ts">
// Relatórios › Temas: quanto da análise veio da IA, os picos de reclamação, o sentimento dos comentários, o gráfico semanal
// por tema (menções ou reclamações) e a tabela dos 6 temas com o sentimento de cada um. Clicar num tema leva para
// Respostas já filtrada.
import { computed, ref } from 'vue'
import { RouterLink } from 'vue-router'
import { ArrowDownRight, ArrowUpRight, LineChart, Minus, Table2 } from 'lucide-vue-next'
import { relatoriosApi } from '@/api'
import { useSessaoStore } from '@/stores/sessao'
import { formatarNumero, plural } from '@/utils/formatos'
import Alerta from '@/components/ui/Alerta.vue'
import BotoesSegmentados from '@/components/ui/BotoesSegmentados.vue'
import Etiqueta from '@/components/ui/Etiqueta.vue'
import FaixaPicos from '@/modulos/painel/FaixaPicos.vue'
import { formatarMedia1, tomNotaMedia, variacaoMencoes } from '@/modulos/painel/logica'
import BarraSentimento from './BarraSentimento.vue'
import GraficoSemanal from './GraficoSemanal.vue'
import { comunsParaApi, consultaRespostas, corDoTema, type FiltrosRelatorioTela, type MedidaTema } from './logica'
import { usarRelatorio } from './usarRelatorio'

const props = defineProps<{ hoje: string; pronto: boolean }>()
const filtros = defineModel<FiltrosRelatorioTela>('filtros', { required: true })
const sessao = useSessaoStore()

const consulta = computed(() => comunsParaApi(filtros.value, props.hoje))
const { dados, carregando, atualizando, erro, carregar } = usarRelatorio(
  (sinal) => relatoriosApi.temas(consulta.value, sinal),
  () => JSON.stringify(consulta.value),
  () => props.pronto,
)

const medida = ref<MedidaTema>('mencoes')
const MEDIDAS: { valor: MedidaTema; rotulo: string }[] = [
  { valor: 'mencoes', rotulo: 'Menções' },
  { valor: 'reclamacoes', rotulo: 'Reclamações' },
]
const emTabela = ref(false)
const podeVerRespostas = computed(() => sessao.pode('respostas.ver'))
const podeConfigurarIa = computed(() => sessao.pode('configuracoes.gerenciar'))
const base = computed(() => consultaRespostas(filtros.value, props.hoje))
const SETAS = { sobe: ArrowUpRight, desce: ArrowDownRight, igual: Minus }

const ia = computed(() => dados.value?.ia ?? null)
const temas = computed(() => dados.value?.temas ?? [])
const legenda = computed(() => temas.value.map((t) => ({ tema: t.tema, rotulo: t.rotulo })))
const semMencoes = computed(() => !!dados.value && temas.value.every((t) => !t.mencoes))
const sentimento = computed(() => dados.value?.sentimento ?? null)
const analisadas = computed(() => ia.value?.analisadas ?? 0)
const comComentario = computed(() => ia.value?.com_comentario ?? 0)
/** A coluna de sentimento é da IA: só com a IA ativa ou quando já há análises no período. */
const mostrarSentimento = computed(() => !!ia.value?.ativa || analisadas.value > 0)
</script>

<template>
  <div class="flex flex-col gap-4">
    <div v-if="carregando && !dados" class="flex flex-col gap-4" role="status" aria-label="Carregando os temas">
      <div class="h-14 animate-pulse rounded-xl bg-superficie-2" />
      <div class="cartao h-72 animate-pulse p-5"><div class="h-3 w-1/4 rounded bg-superficie-2" /></div>
      <span class="sr-only">Carregando…</span>
    </div>

    <Alerta v-else-if="erro && !dados" tom="erro">
      {{ erro }} <button type="button" class="link ml-1" @click="carregar">Tentar de novo</button>
    </Alerta>

    <div v-else-if="dados && ia && sentimento" class="flex flex-col gap-4 transition-opacity" :class="atualizando ? 'opacity-60' : ''" :aria-busy="atualizando || undefined">
      <Alerta v-if="erro" tom="erro">
        Não deu para atualizar com os filtros novos: {{ erro }} <button type="button" class="link ml-1" @click="carregar">Tentar de novo</button>
      </Alerta>

      <!-- De onde vêm os temas -->
      <Alerta v-if="ia.ativa" tom="info" titulo="Temas pela IA" data-aviso-ia>
        {{ formatarNumero(analisadas) }} de {{ plural(comComentario, 'comentário analisado', 'comentários analisados') }} pela IA neste período.
        <template v-if="analisadas < comComentario">
          Os outros usam as palavras-chave: estão na fila da IA, foram importados, são curtos demais ou não deu para
          analisar.<template v-if="podeConfigurarIa">
            Para pedir a análise dos comentários dos últimos 90 dias, use <RouterLink to="/configuracoes/ia" class="link">Configurações › IA</RouterLink>.</template
          >
        </template>
      </Alerta>
      <Alerta v-else tom="info" titulo="Temas por palavras-chave" data-aviso-ia>
        <template v-if="analisadas > 0">{{ plural(analisadas, 'comentário deste período tem', 'comentários deste período têm') }} análise da IA; os outros usam as palavras-chave.</template>
        <template v-else>Os temas saem das palavras dos comentários.</template>
        <template v-if="podeConfigurarIa"> Para a IA ler os comentários, veja <RouterLink to="/configuracoes/ia" class="link">Configurações › IA</RouterLink>.</template>
      </Alerta>

      <FaixaPicos :picos="dados.picos ?? []" :pode-ver-respostas="podeVerRespostas" />

      <!-- Sentimento dos comentários (só com análises da IA) -->
      <section v-if="analisadas > 0" class="cartao flex flex-col gap-3 p-5 sm:p-6" aria-labelledby="t-sentimento">
        <header>
          <h2 id="t-sentimento" class="text-base font-bold text-texto">Sentimento dos comentários</h2>
          <p class="text-sm text-texto-suave">Respostas com comentário do cliente, pelo sentimento geral que a IA leu.</p>
        </header>
        <BarraSentimento
          :positivo="sentimento.positivo"
          :neutro="sentimento.neutro"
          :misto="sentimento.misto"
          :negativo="sentimento.negativo"
          :sem-analise="sentimento.sem_analise"
        />
      </section>

      <!-- Semana a semana -->
      <section class="cartao flex min-w-0 flex-col gap-4 p-5 sm:p-6" aria-labelledby="t-semanal">
        <header class="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
          <div class="min-w-0">
            <h2 id="t-semanal" class="text-base font-bold text-texto">Semana a semana</h2>
            <p class="text-sm text-texto-suave">{{ medida === 'mencoes' ? 'Quantas respostas citaram cada tema.' : 'Quantas respostas reclamaram de cada tema.' }}</p>
          </div>
          <div class="flex flex-wrap items-center gap-2">
            <BotoesSegmentados v-model="medida" :opcoes="MEDIDAS" rotulo="O que mostrar no gráfico" />
            <button
              type="button"
              class="inline-flex h-10 items-center gap-1.5 rounded-xl px-3 text-sm font-semibold text-texto-suave hover:bg-superficie-2 hover:text-texto"
              :aria-pressed="emTabela"
              @click="emTabela = !emTabela"
            >
              <LineChart v-if="emTabela" class="size-4" aria-hidden="true" />
              <Table2 v-else class="size-4" aria-hidden="true" />
              {{ emTabela ? 'Ver gráfico' : 'Ver em tabela' }}
            </button>
          </div>
        </header>
        <GraficoSemanal v-if="dados.semanas.length" v-model:tabela="emTabela" :semanas="dados.semanas" :medida="medida" :temas="legenda" />
        <p v-else class="rounded-xl bg-superficie-2 p-4 text-sm text-texto-suave">Sem semanas para mostrar neste período.</p>
      </section>

      <!-- Os 6 temas -->
      <section class="cartao" aria-labelledby="t-tabela-temas">
        <header class="border-b border-borda p-5 sm:px-6">
          <h2 id="t-tabela-temas" class="text-base font-bold text-texto">Os 6 temas</h2>
          <p class="text-sm text-texto-suave">
            Respostas de NPS e CSAT. Nota média só das de NPS.
            <template v-if="mostrarSentimento">Reclamação: tema citado com sentimento negativo (ou, sem análise da IA, por um detrator ou insatisfeito).</template>
            <template v-else>Reclamação: tema citado por um detrator ou insatisfeito.</template>
          </p>
        </header>
        <p v-if="semMencoes" class="m-5 rounded-xl bg-superficie-2 p-4 text-sm text-texto-suave">Nenhum tema foi citado nos comentários deste período.</p>

        <!-- Computador (a partir de 1280 px) -->
        <div class="hidden overflow-x-auto xl:block">
          <table class="w-full text-sm">
            <caption class="sr-only">Os 6 temas</caption>
            <thead>
              <tr class="border-b border-borda">
                <th scope="col" class="px-4 py-3 pl-6 text-left text-xs font-semibold uppercase tracking-wide text-texto-fraco">Tema</th>
                <th scope="col" class="px-4 py-3 text-right text-xs font-semibold uppercase tracking-wide text-texto-fraco">Menções</th>
                <th scope="col" class="px-4 py-3 text-right text-xs font-semibold uppercase tracking-wide text-texto-fraco">Reclamações</th>
                <th scope="col" class="px-4 py-3 text-right text-xs font-semibold uppercase tracking-wide text-texto-fraco">Elogios</th>
                <th scope="col" class="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-texto-fraco">Nota média</th>
                <th scope="col" class="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-texto-fraco" :class="mostrarSentimento ? '' : 'pr-6'">Variação</th>
                <th v-if="mostrarSentimento" scope="col" class="w-[22%] px-4 py-3 pr-6 text-left text-xs font-semibold uppercase tracking-wide text-texto-fraco">Sentimento (IA)</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="t in temas" :key="t.tema" class="border-b border-borda last:border-0 hover:bg-superficie-2/50">
                <th scope="row" class="px-4 py-3 pl-6 text-left font-semibold">
                  <span class="flex items-center gap-2">
                    <span class="h-0.5 w-4 shrink-0 rounded-full" :class="corDoTema(t.tema).fundo" aria-hidden="true" />
                    <RouterLink v-if="podeVerRespostas" :to="{ path: '/respostas', query: { ...base, tema: t.tema } }" class="text-texto hover:underline">{{ t.rotulo }}</RouterLink>
                    <span v-else class="text-texto">{{ t.rotulo }}</span>
                  </span>
                </th>
                <td class="px-4 py-3 text-right tabular-nums text-texto">{{ formatarNumero(t.mencoes) }}</td>
                <td class="px-4 py-3 text-right tabular-nums">
                  <RouterLink
                    v-if="podeVerRespostas && t.reclamacoes"
                    :to="{ path: '/respostas', query: { ...base, tema: t.tema, reclamacao: 'true' } }"
                    class="font-semibold text-erro hover:underline"
                    :aria-label="`${formatarNumero(t.reclamacoes)} reclamações de ${t.rotulo}: ver as respostas`"
                  >
                    {{ formatarNumero(t.reclamacoes) }}
                  </RouterLink>
                  <span v-else class="text-texto-suave">{{ formatarNumero(t.reclamacoes) }}</span>
                </td>
                <td class="px-4 py-3 text-right tabular-nums text-texto-suave">{{ formatarNumero(t.elogios) }}</td>
                <td class="px-4 py-3">
                  <Etiqueta v-if="t.nota_media !== null" :tom="tomNotaMedia(t.nota_media)">{{ formatarMedia1(t.nota_media) }}</Etiqueta>
                  <span v-else class="text-texto-fraco">—</span>
                </td>
                <td class="px-4 py-3" :class="mostrarSentimento ? '' : 'pr-6'">
                  <span v-if="variacaoMencoes(t.variacao)" class="inline-flex items-center gap-1 whitespace-nowrap text-texto-suave">
                    <component :is="SETAS[variacaoMencoes(t.variacao)!.direcao]" class="size-4" aria-hidden="true" />
                    <span aria-hidden="true">{{ variacaoMencoes(t.variacao)!.texto }}</span>
                    <span class="sr-only">{{ variacaoMencoes(t.variacao)!.descricao }}</span>
                  </span>
                  <span v-else class="text-texto-fraco" title="Escolha um período para comparar com o anterior">—</span>
                </td>
                <td v-if="mostrarSentimento" class="px-4 py-3 pr-6">
                  <BarraSentimento
                    :positivo="t.sentimento.positivo"
                    :neutro="t.sentimento.neutro"
                    :negativo="t.sentimento.negativo"
                    :sem-analise="t.sentimento.sem_analise"
                    compacta
                  />
                  <p class="mt-1 text-xs text-texto-fraco">
                    <template v-if="t.sentimento.positivo + t.sentimento.neutro + t.sentimento.negativo">
                      {{ plural(t.sentimento.positivo, 'positivo', 'positivos') }} · {{ plural(t.sentimento.neutro, 'neutro', 'neutros') }} ·
                      {{ plural(t.sentimento.negativo, 'negativo', 'negativos') }}
                    </template>
                    <template v-else>Sem análise da IA</template>
                  </p>
                </td>
              </tr>
            </tbody>
          </table>
        </div>

        <!-- Celular e telas até 1280 px -->
        <ul class="flex flex-col divide-y divide-borda xl:hidden">
          <li v-for="t in temas" :key="t.tema" class="flex flex-col gap-2 px-4 py-4">
            <div class="flex items-center justify-between gap-3">
              <span class="flex min-w-0 items-center gap-2">
                <span class="h-0.5 w-4 shrink-0 rounded-full" :class="corDoTema(t.tema).fundo" aria-hidden="true" />
                <RouterLink v-if="podeVerRespostas" :to="{ path: '/respostas', query: { ...base, tema: t.tema } }" class="truncate font-semibold text-texto hover:underline">{{ t.rotulo }}</RouterLink>
                <span v-else class="truncate font-semibold text-texto">{{ t.rotulo }}</span>
              </span>
              <Etiqueta v-if="t.nota_media !== null" :tom="tomNotaMedia(t.nota_media)" class="shrink-0">nota média {{ formatarMedia1(t.nota_media) }}</Etiqueta>
            </div>
            <p class="flex flex-wrap gap-x-3 gap-y-1 text-sm text-texto-suave">
              <span><strong class="font-semibold text-texto">{{ formatarNumero(t.mencoes) }}</strong> {{ t.mencoes === 1 ? 'menção' : 'menções' }}</span>
              <RouterLink
                v-if="podeVerRespostas && t.reclamacoes"
                :to="{ path: '/respostas', query: { ...base, tema: t.tema, reclamacao: 'true' } }"
                class="font-semibold text-erro underline-offset-2 hover:underline"
              >
                {{ plural(t.reclamacoes, 'reclamação', 'reclamações') }}
              </RouterLink>
              <span v-else>{{ plural(t.reclamacoes, 'reclamação', 'reclamações') }}</span>
              <span>{{ plural(t.elogios, 'elogio', 'elogios') }}</span>
              <span v-if="variacaoMencoes(t.variacao)" class="inline-flex items-center gap-0.5">
                <component :is="SETAS[variacaoMencoes(t.variacao)!.direcao]" class="size-3.5" aria-hidden="true" />
                <span aria-hidden="true">{{ variacaoMencoes(t.variacao)!.texto }}</span>
                <span class="sr-only">{{ variacaoMencoes(t.variacao)!.descricao }}</span>
              </span>
            </p>
            <BarraSentimento
              v-if="mostrarSentimento && t.sentimento.positivo + t.sentimento.neutro + t.sentimento.negativo"
              :positivo="t.sentimento.positivo"
              :neutro="t.sentimento.neutro"
              :negativo="t.sentimento.negativo"
              :sem-analise="t.sentimento.sem_analise"
            />
          </li>
        </ul>
      </section>
    </div>
  </div>
</template>

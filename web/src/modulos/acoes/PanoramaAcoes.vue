<script setup lang="ts">
// O topo de Planos de ação (docs/api-acoes-panorama.md): em uma frase, como estão os prazos das ações abertas; a barra
// das abertas por prazo; quem está com quantas (e quantas vencidas), com um clique para ver só as de uma pessoa; e as
// concluídas nos últimos 30 dias, em quanto tempo e com quantos retornos ao cliente. Segue os filtros do quadro e
// busca de novo a cada atualização dele (`versao`).
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { Minus, TrendingDown, TrendingUp } from 'lucide-vue-next'
import { acoesApi, mensagemDoErro, type FiltrosAcoes, type Id, type PanoramaAcoes } from '@/api'
import { formatarNumero } from '@/utils/formatos'
import Alerta from '@/components/ui/Alerta.vue'
import { carga, comparacaoConcluidas, manchete, retorno, segmentosPrazo, tempoConclusao } from './panorama'

const props = defineProps<{
  filtros: FiltrosAcoes
  /** Muda a cada carga do quadro (filtros, mover, salvar): o resumo acompanha. */
  versao: number
  /** O filtro de responsável escolhido ("0" = sem responsável), para marcar a pessoa. */
  responsavel: Id | ''
  soVencidas: boolean
}>()
const emit = defineEmits<{ responsavel: [Id | '']; soVencidas: [boolean] }>()

const dados = ref<PanoramaAcoes | null>(null)
const carregando = ref(true)
const erro = ref<string | null>(null)
let controle: AbortController | null = null

async function carregar() {
  controle?.abort()
  const meu = (controle = new AbortController())
  carregando.value = !dados.value
  erro.value = null
  try {
    dados.value = await acoesApi.panorama(props.filtros, meu.signal)
  } catch (e) {
    if (e instanceof DOMException && e.name === 'AbortError') return
    if (!dados.value) erro.value = mensagemDoErro(e)
  } finally {
    if (controle === meu) carregando.value = false
  }
}

// O quadro carrega a cada mudança de filtro (e depois de mover ou salvar): a versão nova traz o resumo junto.
watch(() => props.versao, () => carregar(), { immediate: true })
onBeforeUnmount(() => controle?.abort())

const m = computed(() => (dados.value ? manchete(dados.value.prazos) : null))
const segmentos = computed(() => (dados.value ? segmentosPrazo(dados.value.prazos) : []))
const pessoas = computed(() => (dados.value ? carga(dados.value) : []))
const todasPessoas = ref(false)
const pessoasVisiveis = computed(() => (todasPessoas.value ? pessoas.value : pessoas.value.slice(0, 5)))
/** A pessoa escolhida no filtro, quando está na lista: o resumo diz de quem são os números. */
const escolhida = computed(() => (props.responsavel === '' ? null : (pessoas.value.find((p) => String(p.filtro) === String(props.responsavel)) ?? null)))
const c = computed(() => dados.value?.concluidas ?? null)
const comparacao = computed(() => (c.value ? comparacaoConcluidas(c.value) : null))

const COR_TITULO = { erro: 'text-erro', atencao: 'text-texto', sucesso: 'text-texto', neutro: 'text-texto' } as const
const COR_COMPARACAO = { subiu: 'text-sucesso', caiu: 'text-texto-fraco', igual: 'text-texto-fraco' } as const
const ICONE_COMPARACAO = { subiu: TrendingUp, caiu: TrendingDown, igual: Minus } as const

function escolher(filtro: Id) {
  emit('responsavel', String(props.responsavel) === String(filtro) ? '' : filtro)
}
</script>

<template>
  <section class="cartao mb-5 p-5 sm:p-6" aria-labelledby="t-panorama-acoes" :aria-busy="carregando || undefined" data-panorama-acoes>
    <div v-if="carregando && !dados" class="animate-pulse" role="status" aria-label="Carregando o resumo das ações">
      <div class="h-6 w-1/2 rounded-lg bg-superficie-2" />
      <div class="mt-4 h-3 w-full rounded bg-superficie-2" />
      <div class="mt-6 grid gap-3 sm:w-2/3">
        <div v-for="i in 3" :key="i" class="h-3 rounded bg-superficie-2" :style="{ width: `${90 - i * 20}%` }" />
      </div>
    </div>

    <Alerta v-else-if="erro && !dados" tom="erro">
      Não deu para carregar o resumo das ações: {{ erro }} <button type="button" class="link ml-1" @click="carregar()">Tentar de novo</button>
    </Alerta>

    <div v-else-if="dados && m && c" class="grid gap-x-10 gap-y-7 xl:grid-cols-[minmax(0,1fr)_18rem]">
      <div class="min-w-0">
        <h2 id="t-panorama-acoes" class="text-xl leading-snug font-bold sm:text-[1.45rem]" :class="COR_TITULO[m.tom]" data-manchete-acoes>{{ m.titulo }}</h2>
        <p v-if="m.texto" class="mt-0.5 text-sm text-texto-suave">{{ m.texto }}</p>
        <p v-if="escolhida" class="mt-0.5 text-sm text-texto-suave" data-filtro-pessoa>
          {{ escolhida.filtro === '0' ? 'Só as sem responsável.' : `Só as de ${escolhida.nome}.` }}
          <button type="button" class="link ml-1 font-semibold" @click="emit('responsavel', '')">Ver de todos</button>
        </p>

        <!-- As abertas por prazo: uma barra só, com a legenda escrita -->
        <div v-if="segmentos.length" class="mt-4" data-prazos>
          <div class="flex h-3 w-full gap-0.5" aria-hidden="true">
            <span
              v-for="(s, i) in segmentos"
              :key="s.chave"
              class="h-full"
              :class="[s.cor, i === segmentos.length - 1 ? 'rounded-r-[4px]' : '']"
              :style="{ width: `${s.largura}%` }"
              :data-segmento="s.chave"
            />
          </div>
          <ul class="mt-2.5 flex flex-wrap gap-x-4 gap-y-1.5 text-sm" aria-label="Ações abertas por prazo">
            <li v-for="s in segmentos" :key="s.chave" class="inline-flex items-center gap-1.5" :data-legenda-prazo="s.chave">
              <span class="size-2.5 rounded-[3px]" :class="s.cor" aria-hidden="true" />
              <button
                v-if="s.chave === 'vencidas'"
                type="button"
                class="rounded-sm text-left font-semibold underline-offset-4 hover:underline"
                :class="props.soVencidas ? 'text-erro' : 'text-texto'"
                :aria-pressed="props.soVencidas"
                @click="emit('soVencidas', !props.soVencidas)"
              >
                {{ formatarNumero(s.valor) }} {{ s.rotulo }}<span class="sr-only">: {{ props.soVencidas ? 'mostrar todas no quadro' : 'mostrar só as vencidas no quadro' }}</span>
              </button>
              <span v-else class="text-texto-suave"><strong class="font-semibold text-texto">{{ formatarNumero(s.valor) }}</strong> {{ s.rotulo }}</span>
            </li>
          </ul>
        </div>

        <!-- Quem está com quantas: um clique mostra só as ações da pessoa -->
        <div v-if="pessoas.length" class="mt-6" data-carga>
          <h3 class="text-sm font-semibold text-texto-suave">Por responsável</h3>
          <ul class="mt-2 grid gap-x-8 gap-y-1 sm:grid-cols-2">
            <li v-for="pessoa in pessoasVisiveis" :key="String(pessoa.filtro)">
              <button
                type="button"
                class="group -mx-2 w-[calc(100%+1rem)] rounded-lg px-2 py-1.5 text-left transition-colors"
                :class="String(props.responsavel) === String(pessoa.filtro) ? 'bg-marca-suave' : 'hover:bg-superficie-2'"
                :aria-pressed="String(props.responsavel) === String(pessoa.filtro)"
                :aria-label="`${pessoa.nome}: ${pessoa.detalhe}. ${String(props.responsavel) === String(pessoa.filtro) ? 'Mostrar de todos' : 'Mostrar só as ações dessa pessoa'}`"
                :data-pessoa="String(pessoa.filtro)"
                @click="escolher(pessoa.filtro)"
              >
                <span class="flex items-baseline justify-between gap-3 text-sm">
                  <span
                    class="truncate font-semibold"
                    :class="String(props.responsavel) === String(pessoa.filtro) ? 'text-marca-texto' : 'text-texto'"
                    >{{ pessoa.nome }}</span
                  >
                  <span class="shrink-0 text-xs" :class="pessoa.vencidas ? 'font-semibold text-erro' : 'text-texto-fraco'">{{ pessoa.detalhe }}</span>
                </span>
                <span class="mt-1 flex h-2 gap-0.5" :style="{ width: `${pessoa.largura}%` }" aria-hidden="true">
                  <span v-if="pessoa.vencidas" class="h-full bg-grafico-detrator" :class="pessoa.parteVencida >= 100 ? 'rounded-r-[4px]' : ''" :style="{ width: `${pessoa.parteVencida}%` }" />
                  <span v-if="pessoa.parteVencida < 100" class="h-full min-w-0.5 flex-1 rounded-r-[4px] bg-grafico-cinza" />
                </span>
              </button>
            </li>
          </ul>
          <button v-if="pessoas.length > 5 && !todasPessoas" type="button" class="link mt-1 inline-flex min-h-11 items-center text-sm sm:min-h-0" @click="todasPessoas = true">
            Ver mais {{ pessoas.length - 5 }}
          </button>
        </div>
      </div>

      <!-- As concluídas nos últimos 30 dias -->
      <div class="border-t border-borda pt-6 xl:border-t-0 xl:border-l xl:pt-0 xl:pl-8" data-concluidas>
        <h3 class="text-sm font-semibold text-texto-suave">Concluídas nos últimos 30 dias</h3>
        <p class="mt-2 text-5xl leading-none font-extrabold tracking-tight text-texto" data-total-concluidas>{{ formatarNumero(c.total) }}</p>
        <p v-if="comparacao" class="mt-2.5 flex items-center gap-1.5 text-sm font-semibold" :class="COR_COMPARACAO[comparacao.sentido]" data-comparacao-concluidas>
          <component :is="ICONE_COMPARACAO[comparacao.sentido]" class="size-4 shrink-0" aria-hidden="true" />
          {{ comparacao.texto }}
        </p>
        <p v-if="tempoConclusao(c)" class="mt-1 text-sm text-texto-suave" data-tempo-conclusao>{{ tempoConclusao(c) }}</p>
        <p v-if="retorno(c)" class="mt-1 text-sm text-texto-fraco" data-retorno>{{ retorno(c) }}</p>
      </div>
    </div>
  </section>
</template>

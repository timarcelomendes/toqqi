<script setup lang="ts">
// Tom dos comentários (análise da IA): % de negativos em destaque com a variação em pontos sobre o período anterior,
// barra empilhada negativo/misto/neutro/positivo (cores do sentimento do design-system, sempre com o nome e o número
// escritos) e quantas respostas vieram com comentário. Sem nada analisado: avisa que a análise está na fila (`pendentes`
// do próprio painel, que segue os filtros) ou convida a ligar a IA (link só para quem administra). Etapa 5h: com a IA
// ligada, "N comentários ainda não foram lidos pela IA." e, para quem administra, "Analisar agora" (os últimos 90 dias,
// POST /conta/ia/analisar-recentes; depois, o bloco passa a "analisando"). Tudo sai das props: trocar o filtro troca o
// bloco.
import { computed, ref, watch } from 'vue'
import { RouterLink } from 'vue-router'
import { Sparkles } from 'lucide-vue-next'
import { iaApi, mensagemDoErro, type TomComentarios } from '@/api'
import { avisar } from '@/composables/avisos'
import { useSessaoStore } from '@/stores/sessao'
import { formatarNumero } from '@/utils/formatos'
import Botao from '@/components/ui/Botao.vue'
import { estadoTom, resumoTom, textoNaoLidos } from './logica'

const props = defineProps<{ tom: TomComentarios; textoAnterior: string; /** Modo exemplo: sem botões. */ desativado?: boolean }>()
const sessao = useSessaoStore()
const podeConfigurarIa = computed(() => sessao.pode('configuracoes.gerenciar'))

/** Pediu "Analisar agora" e marcou algum: mostra "analisando" até o painel trazer números novos. */
const analisandoAgora = ref(false)
const pedindo = ref(false)
watch(
  () => props.tom,
  () => (analisandoAgora.value = false),
)
const resumo = computed(() => resumoTom(props.tom))
const estado = computed(() => (analisandoAgora.value ? 'analisando' : estadoTom(props.tom)))

async function analisarAgora() {
  if (pedindo.value || props.desativado) return
  pedindo.value = true
  try {
    const r = await iaApi.analisarRecentes()
    if (r.marcadas > 0) {
      analisandoAgora.value = true
      avisar.sucesso(r.marcadas === 1 ? '1 comentário foi para a análise da IA.' : `${formatarNumero(r.marcadas)} comentários foram para a análise da IA.`)
    } else {
      avisar.info('Nenhum comentário foi para a análise: só entram os dos últimos 90 dias, até o limite de análises do mês.')
    }
  } catch (e) {
    avisar.erro(mensagemDoErro(e))
  } finally {
    pedindo.value = false
  }
}
const variacao = computed(() => {
  const v = resumo.value?.variacao
  if (v === null || v === undefined) return null
  const n = Math.abs(v)
  return {
    seta: v > 0 ? '▲' : v < 0 ? '▼' : '=',
    texto: v === 0 ? 'igual' : `${n} ${n === 1 ? 'ponto' : 'pontos'}`,
    leitura: v === 0 ? 'o mesmo que no período anterior' : `${n} ${n === 1 ? 'ponto' : 'pontos'} ${v > 0 ? 'a mais' : 'a menos'} que no período anterior`,
    // Mais negativos é ruim (vermelho); menos, bom (verde).
    cor: v > 0 ? 'text-erro' : v < 0 ? 'text-sucesso' : 'text-texto-suave',
  }
})
/** "Nos 90 dias antes" / "No período anterior". */
const noAnterior = computed(() => (props.textoAnterior.startsWith('os ') ? `Nos ${props.textoAnterior.slice(3)}` : 'No período anterior'))
const rotuloBarra = computed(() =>
  resumo.value ? `Tom dos comentários: ${resumo.value.partes.map((p) => `${p.rotulo.toLowerCase()} ${formatarNumero(p.qtd)}`).join('; ')}` : '',
)
</script>

<template>
  <section class="cartao flex flex-col gap-3 p-5 sm:p-6" aria-labelledby="t-tom" data-tom>
    <header>
      <h2 id="t-tom" class="text-base font-bold text-texto">Tom dos comentários</h2>
      <p v-if="resumo && resumo.totalRespostas > 0" class="text-sm text-texto-suave">
        {{ formatarNumero(resumo.comComentario) }} de {{ formatarNumero(resumo.totalRespostas) }}
        {{ resumo.totalRespostas === 1 ? 'resposta veio' : 'respostas vieram' }} com comentário ({{ resumo.pctComentario }}%).
      </p>
    </header>

    <template v-if="resumo && estado === 'dados'">
      <p class="flex flex-wrap items-baseline gap-x-2">
        <span class="text-4xl font-extrabold leading-none tabular-nums text-erro">{{ resumo.pctNegativo }}%</span>
        <span class="text-sm text-texto-suave">negativos</span>
        <strong v-if="variacao" class="text-sm font-bold" :class="variacao.cor">
          <span aria-hidden="true">{{ variacao.seta }} {{ variacao.texto }}</span><span class="sr-only">, {{ variacao.leitura }}</span>
        </strong>
      </p>
      <div class="flex h-3 w-full gap-0.5" role="img" :aria-label="rotuloBarra">
        <template v-for="(p, i) in resumo.partes.filter((x) => x.qtd > 0)" :key="p.chave">
          <span
            class="h-full min-w-1"
            :class="[p.cor, i === 0 ? 'rounded-l-full' : '', i === resumo.partes.filter((x) => x.qtd > 0).length - 1 ? 'rounded-r-full' : '']"
            :style="{ flexGrow: p.fracao, flexBasis: 0 }"
          />
        </template>
      </div>
      <ul class="grid grid-cols-2 gap-x-4 gap-y-1 text-sm text-texto-suave">
        <li v-for="p in resumo.partes" :key="p.chave" class="inline-flex items-center gap-1.5">
          <span class="size-2.5 shrink-0 rounded-full" :class="p.cor" aria-hidden="true" />
          {{ p.rotulo }} <strong class="font-bold text-texto tabular-nums">{{ formatarNumero(p.qtd) }}</strong>
        </li>
      </ul>
      <p class="text-xs text-texto-fraco">
        Pela análise da IA<template v-if="resumo.pctNegativoAnterior !== null">. {{ noAnterior }}, {{ resumo.pctNegativoAnterior }}% eram negativos</template>.
        <template v-if="resumo.analisados < resumo.comComentario"> {{ formatarNumero(resumo.analisados) }} de {{ formatarNumero(resumo.comComentario) }} comentários analisados.</template>
      </p>
    </template>

    <p v-else-if="estado === 'sem_comentarios'" class="rounded-xl bg-superficie-2 p-4 text-sm text-texto-suave">Nenhum comentário neste período.</p>
    <p v-else-if="estado === 'analisando'" class="rounded-xl bg-superficie-2 p-4 text-sm text-texto-suave" data-tom-analisando>
      Os comentários ainda estão sendo analisados. O tom aparece aqui assim que a IA terminar.
    </p>
    <div v-else-if="estado === 'nao_lidos'" class="flex flex-col gap-3 rounded-xl bg-superficie-2 p-4 text-sm" data-tom-nao-lidos>
      <p class="flex min-w-0 items-start gap-3 text-texto-suave">
        <Sparkles class="mt-0.5 size-5 shrink-0 text-marca-texto" aria-hidden="true" />
        <span>{{ textoNaoLidos(tom.sem_analise ?? 0) }}</span>
      </p>
      <Botao
        v-if="podeConfigurarIa"
        variante="secundario"
        tamanho="sm"
        class="!h-10 ml-8 self-start"
        :carregando="pedindo"
        :desabilitado="desativado"
        data-analisar-agora
        @click="analisarAgora"
      >
        Analisar agora
      </Botao>
    </div>
    <p v-else-if="estado === 'curtos'" class="rounded-xl bg-superficie-2 p-4 text-sm text-texto-suave" data-tom-curtos>
      Os comentários deste período são curtos demais para a IA ler o tom.
    </p>
    <div v-else class="flex items-start gap-3 rounded-xl bg-superficie-2 p-4 text-sm" data-tom-ligar>
      <Sparkles class="mt-0.5 size-5 shrink-0 text-texto-fraco" aria-hidden="true" />
      <p class="text-texto-suave">
        <template v-if="podeConfigurarIa">
          Ligue a análise por IA em <RouterLink to="/configuracoes/ia" class="link">Configurações › IA</RouterLink> para ver o tom.
        </template>
        <template v-else>A análise por IA está desligada ou ainda não chegou a estes comentários.</template>
      </p>
    </div>
  </section>
</template>

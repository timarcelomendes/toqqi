<script setup lang="ts">
// Relatórios › Entregas: NPS, CSAT e reclamações por motorista, rota, filial ou transportadora (o contexto que vem
// no convite), com os principais temas, aviso de amostra pequena e o atalho para as respostas. Sem dados, explica
// como mandar essas informações.
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { RouterLink } from 'vue-router'
import { ArrowRight, Search, Truck } from 'lucide-vue-next'
import { relatoriosApi, type DimensaoEntrega } from '@/api'
import { useSessaoStore } from '@/stores/sessao'
import { formatarData } from '@/utils/datas'
import { formatarNumero, plural } from '@/utils/formatos'
import Alerta from '@/components/ui/Alerta.vue'
import BotoesSegmentados from '@/components/ui/BotoesSegmentados.vue'
import Botao from '@/components/ui/Botao.vue'
import Campo from '@/components/ui/Campo.vue'
import EstadoVazio from '@/components/ui/EstadoVazio.vue'
import Etiqueta from '@/components/ui/Etiqueta.vue'
import Paginacao from '@/components/ui/Paginacao.vue'
import Selecao from '@/components/ui/Selecao.vue'
import Tabela, { type Coluna } from '@/components/ui/Tabela.vue'
import { formatarMedia2, formatarPct, tomCsat } from '@/modulos/painel/logica'
import SeloNps from './SeloNps.vue'
import { DIMENSOES, LIMITE_BUSCA, ORDENS_ENTREGAS, consultaRespostas, entregasParaApi, rotuloDimensao, type FiltrosRelatorioTela } from './logica'
import { usarRelatorio } from './usarRelatorio'

const props = defineProps<{ hoje: string; pronto: boolean }>()
const filtros = defineModel<FiltrosRelatorioTela>('filtros', { required: true })
const sessao = useSessaoStore()

const consulta = computed(() => entregasParaApi(filtros.value, props.hoje))
const { dados, carregando, atualizando, erro, carregar } = usarRelatorio(
  (sinal) => relatoriosApi.entregas(consulta.value, sinal),
  () => JSON.stringify(consulta.value),
  () => props.pronto,
)

const busca = ref(filtros.value.busca)
let atrasoBusca: ReturnType<typeof setTimeout> | null = null
watch(busca, (v) => {
  if (atrasoBusca) clearTimeout(atrasoBusca)
  atrasoBusca = setTimeout(() => (filtros.value.busca = v.trim().slice(0, LIMITE_BUSCA)), 300)
})
watch(
  () => filtros.value.busca,
  (v) => {
    if (v !== busca.value.trim()) busca.value = v
  },
)
onBeforeUnmount(() => {
  if (atrasoBusca) clearTimeout(atrasoBusca)
})

const dimensao = computed(() => filtros.value.dimensao)
const nomeDimensao = computed(() => rotuloDimensao(dimensao.value))
const plural_ = computed(() => DIMENSOES.find((d) => d.valor === dimensao.value)?.plural ?? 'valores')
const itens = computed(() => dados.value?.itens ?? [])
const podeVerRespostas = computed(() => sessao.pode('respostas.ver'))
const pagina = computed({ get: () => filtros.value.pagina, set: (p: number) => (filtros.value.pagina = p) })

const CORES_TOM: Record<string, string> = { sucesso: 'text-sucesso', atencao: 'text-atencao', erro: 'text-erro' }
function corCsat(p: number | null) {
  return CORES_TOM[tomCsat(p)] ?? 'text-texto'
}

function escolherDimensao(d: DimensaoEntrega) {
  if (d === filtros.value.dimensao) return
  busca.value = ''
  Object.assign(filtros.value, { dimensao: d, busca: '', pagina: 1 })
}
const dimensaoEscolhida = computed<DimensaoEntrega>({ get: () => filtros.value.dimensao, set: escolherDimensao })

function linkRespostas(valor: string) {
  return { path: '/respostas', query: { ...consultaRespostas(filtros.value, props.hoje), [dimensao.value]: valor } }
}

const colunas = computed<Coluna[]>(() => [
  { chave: 'valor', rotulo: nomeDimensao.value, classe: 'w-[22%]' },
  { chave: 'respostas', rotulo: 'Respostas', alinhar: 'direita' },
  { chave: 'nps', rotulo: 'NPS' },
  { chave: 'csat', rotulo: 'CSAT' },
  { chave: 'reclamacoes', rotulo: 'Reclamações', alinhar: 'direita' },
  { chave: 'temas', rotulo: 'Principais temas' },
  { chave: 'ultima', rotulo: 'Última resposta' },
])
</script>

<template>
  <div class="flex flex-col gap-4">
    <!-- Por qual informação da entrega (rádios nativos: as setas trocam a opção) -->
    <BotoesSegmentados v-model="dimensaoEscolhida" :opcoes="DIMENSOES" rotulo="Agrupar as respostas por" bloco />

    <div v-if="carregando && !dados" class="cartao p-5" role="status" :aria-label="`Carregando o relatório por ${nomeDimensao.toLowerCase()}`">
      <div v-for="i in 4" :key="i" class="mb-4 h-4 animate-pulse rounded bg-superficie-2 last:mb-0" :style="{ width: `${90 - i * 12}%` }" />
      <span class="sr-only">Carregando…</span>
    </div>

    <Alerta v-else-if="erro && !dados" tom="erro">
      {{ erro }} <button type="button" class="link ml-1" @click="carregar">Tentar de novo</button>
    </Alerta>

    <section v-else-if="dados" class="cartao transition-opacity" :class="atualizando ? 'opacity-60' : ''" :aria-busy="atualizando || undefined" aria-labelledby="t-entregas">
      <h2 id="t-entregas" class="sr-only">Respostas por {{ nomeDimensao.toLowerCase() }}</h2>
      <Alerta v-if="erro" tom="erro" class="m-4">
        Não deu para atualizar: {{ erro }} <button type="button" class="link ml-1" @click="carregar">Tentar de novo</button>
      </Alerta>
      <div v-if="itens.length || filtros.busca" class="flex flex-col gap-3 border-b border-borda p-4 sm:flex-row sm:items-start sm:px-5">
        <Campo
          v-model="busca"
          :rotulo="`Buscar ${nomeDimensao.toLowerCase()}`"
          rotulo-oculto
          tipo="search"
          :maxlength="LIMITE_BUSCA"
          :placeholder="`Buscar ${nomeDimensao.toLowerCase()}`"
          class="sm:max-w-sm sm:flex-1"
        >
          <template #antes><Search class="size-4" aria-hidden="true" /></template>
        </Campo>
        <Selecao v-model="filtros.ordem" rotulo="Ordenar por" rotulo-oculto :opcoes="ORDENS_ENTREGAS" class="sm:ml-auto sm:w-56" />
      </div>
      <p v-if="dados.sem_valor > 0 && itens.length" class="border-b border-borda px-4 py-2.5 text-sm text-texto-fraco sm:px-5">
        {{ plural(dados.sem_valor, 'resposta', 'respostas') }} do período não {{ dados.sem_valor === 1 ? 'informa' : 'informam' }} {{ dimensao === 'filial' || dimensao === 'rota' || dimensao === 'transportadora' ? 'a' : 'o' }} {{ nomeDimensao.toLowerCase() }} e {{ dados.sem_valor === 1 ? 'fica' : 'ficam' }} fora desta lista.
      </p>

      <!-- Computador -->
      <div v-if="itens.length" class="hidden xl:block">
        <Tabela densa :colunas="colunas" :linhas="itens" :chave="(x) => x.valor" :legenda="`Respostas por ${nomeDimensao.toLowerCase()}`">
          <template #cel-valor="{ linha: x }">
            <p class="break-words font-semibold text-texto">{{ x.valor }}</p>
            <Etiqueta v-if="x.amostra_pequena" tom="atencao" class="mt-1" title="Menos de 5 respostas: os números podem mudar muito com uma resposta a mais.">Amostra pequena</Etiqueta>
            <RouterLink v-if="podeVerRespostas" :to="linkRespostas(x.valor)" class="link mt-1 flex min-h-8 w-fit items-center gap-1 whitespace-nowrap text-sm">
              Ver respostas<span class="sr-only"> de {{ x.valor }}</span> <ArrowRight class="size-4" aria-hidden="true" />
            </RouterLink>
          </template>
          <template #cel-respostas="{ linha: x }">
            <span class="tabular-nums text-texto">{{ formatarNumero(x.respostas) }}</span>
          </template>
          <template #cel-nps="{ linha: x }"><SeloNps :nps="x.nps" sem-respostas="Sem NPS" /></template>
          <template #cel-csat="{ linha: x }">
            <template v-if="x.csat.total && x.csat.percentual !== null">
              <span class="block font-semibold tabular-nums" :class="corCsat(x.csat.percentual)">
                {{ formatarPct(x.csat.percentual) }}
              </span>
              <span class="block whitespace-nowrap text-xs text-texto-fraco">média {{ formatarMedia2(x.csat.media) }}</span>
            </template>
            <span v-else class="whitespace-nowrap text-texto-fraco">Sem CSAT</span>
          </template>
          <template #cel-reclamacoes="{ linha: x }">
            <span class="tabular-nums" :class="x.reclamacoes ? 'font-semibold text-texto' : 'text-texto-fraco'">{{ formatarNumero(x.reclamacoes) }}</span>
          </template>
          <template #cel-temas="{ linha: x }">
            <div v-if="x.temas.length" class="flex flex-wrap gap-1">
              <Etiqueta v-for="t in x.temas" :key="t.tema" tom="info" :title="plural(t.mencoes, 'menção', 'menções')">
                {{ t.rotulo }}<span class="sr-only"> ({{ plural(t.mencoes, 'menção', 'menções') }})</span>
              </Etiqueta>
            </div>
            <span v-else class="text-texto-fraco">—</span>
          </template>
          <template #cel-ultima="{ linha: x }">
            <span class="whitespace-nowrap text-texto-suave">{{ formatarData(x.ultima_resposta) }}</span>
          </template>
        </Tabela>
      </div>

      <!-- Celular e tablet -->
      <ul class="flex flex-col divide-y divide-borda xl:hidden">
        <li v-for="x in itens" :key="x.valor" class="flex flex-col gap-2 px-4 py-4">
          <div class="flex items-start justify-between gap-3">
            <div class="min-w-0">
              <p class="break-words font-semibold text-texto">{{ x.valor }}</p>
              <p class="text-sm text-texto-fraco">{{ plural(x.respostas, 'resposta', 'respostas') }} · última em {{ formatarData(x.ultima_resposta) }}</p>
            </div>
            <SeloNps :nps="x.nps" compacto sem-respostas="Sem NPS" />
          </div>
          <div class="flex flex-wrap items-center gap-1.5">
            <Etiqueta v-if="x.amostra_pequena" tom="atencao">Amostra pequena</Etiqueta>
            <Etiqueta v-if="x.csat.total && x.csat.percentual !== null" :tom="tomCsat(x.csat.percentual)">CSAT {{ formatarPct(x.csat.percentual) }}</Etiqueta>
            <Etiqueta :tom="x.reclamacoes ? 'erro' : 'neutro'">{{ plural(x.reclamacoes, 'reclamação', 'reclamações') }}</Etiqueta>
            <Etiqueta v-for="t in x.temas" :key="t.tema" tom="info">{{ t.rotulo }}</Etiqueta>
          </div>
          <RouterLink v-if="podeVerRespostas" :to="linkRespostas(x.valor)" class="link inline-flex min-h-10 items-center gap-1 self-start text-sm">
            Ver respostas <ArrowRight class="size-4" aria-hidden="true" />
          </RouterLink>
        </li>
      </ul>

      <template v-if="!itens.length">
        <EstadoVazio v-if="filtros.busca" :icone="Search" :titulo="`Nenhum ${nomeDimensao.toLowerCase()} com essa busca`" descricao="Confira o nome ou limpe a busca.">
          <Botao variante="secundario" @click="busca = ''">Limpar busca</Botao>
        </EstadoVazio>
        <div v-else class="flex flex-col items-center gap-3 px-6 py-12 text-center" data-vazio-entregas>
          <div class="flex size-14 items-center justify-center rounded-2xl bg-marca-suave text-marca-texto"><Truck class="size-7" aria-hidden="true" /></div>
          <h3 class="text-base font-bold text-texto">Nenhuma resposta informa {{ dimensao === 'motorista' ? 'o motorista' : dimensao === 'rota' ? 'a rota' : dimensao === 'filial' ? 'a filial' : 'a transportadora' }}</h3>
          <div class="max-w-xl text-sm text-texto-suave">
            <p>Este relatório usa os dados da entrega que chegam junto com o convite. Para mandar {{ plural_ }}:</p>
            <ul class="mt-2 flex list-disc flex-col gap-1 pl-5 text-left">
              <li><strong class="font-semibold text-texto">Pela integração</strong> (o seu sistema avisa o Toqqi da entrega): no campo <code class="rounded bg-superficie-2 px-1">contexto</code>, informe motorista, rota, filial e transportadora.</li>
              <li><strong class="font-semibold text-texto">Pelo link da pesquisa</strong>: em Formulários › Compartilhar, monte o link com a rota ou o motorista (ex.: <code class="rounded bg-superficie-2 px-1">?motorista=João&amp;rota=Sul</code>).</li>
            </ul>
            <p v-if="dados.sem_valor > 0" class="mt-2">Neste período, {{ plural(dados.sem_valor, 'resposta chegou', 'respostas chegaram') }} sem essa informação.</p>
          </div>
          <Botao v-if="sessao.admin" variante="secundario" para="/integracoes">Ver as integrações</Botao>
        </div>
      </template>
      <Paginacao v-model="pagina" :total="dados.total" :por-pagina="dados.por_pagina || 50" :carregando="atualizando" :nome-itens="dados.total === 1 ? nomeDimensao.toLowerCase() : plural_" />
    </section>
  </div>
</template>

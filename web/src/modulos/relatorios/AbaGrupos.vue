<script setup lang="ts">
// Relatórios › Grupos de clientes: NPS por segmento, por grupo de empresas, por tempo como cliente e por valor do
// contrato (barras empilhadas detratores → neutros → promotores, com o NPS e o total) e "O que resolver primeiro"
// (gráfico menções × nota média + a lista em ordem). Só respostas NPS ligadas a uma empresa.
import { computed, reactive } from 'vue'
import { RouterLink } from 'vue-router'
import { BarChart3, Table2, Target } from 'lucide-vue-next'
import { relatoriosApi, type Id } from '@/api'
import { useCadastrosStore } from '@/stores/cadastros'
import { useSessaoStore } from '@/stores/sessao'
import { plural } from '@/utils/formatos'
import Alerta from '@/components/ui/Alerta.vue'
import Etiqueta from '@/components/ui/Etiqueta.vue'
import Selecao from '@/components/ui/Selecao.vue'
import { formatarMedia1, tomNotaMedia } from '@/modulos/painel/logica'
import GraficoPrioridades from './GraficoPrioridades.vue'
import ListaBarrasNps, { type LinhaNps } from './ListaBarrasNps.vue'
import { FAIXAS_TEMPO, FAIXAS_VALOR, consultaRespostas, corDoTema, gruposParaApi, type FiltrosRelatorioTela } from './logica'
import { usarRelatorio } from './usarRelatorio'

const props = defineProps<{ hoje: string; pronto: boolean }>()
const filtros = defineModel<FiltrosRelatorioTela>('filtros', { required: true })
const sessao = useSessaoStore()
const cadastros = useCadastrosStore()

const consulta = computed(() => gruposParaApi(filtros.value, props.hoje))
const { dados, carregando, atualizando, erro, carregar } = usarRelatorio(
  (sinal) => relatoriosApi.grupos(consulta.value, sinal),
  () => JSON.stringify(consulta.value),
  () => props.pronto,
)

const podeVerCadastros = computed(() => sessao.pode('contatos.ver'))
function opcoesSegmento(atual: Id | '') {
  const opcoes: { valor: Id; rotulo: string }[] = [{ valor: '0', rotulo: 'Sem segmento' }, ...cadastros.listas.segmentos.map((x) => ({ valor: x.id, rotulo: x.nome }))]
  if (atual !== '' && !opcoes.some((o) => String(o.valor) === String(atual))) opcoes.push({ valor: atual, rotulo: 'Escolhido no link' })
  return opcoes
}

const emTabela = reactive({ segmentos: false, grupos: false, tempo: false, valor: false })

const linhas = computed(() => {
  const d = dados.value
  if (!d) return null
  const ref = (r: { id: Id; nome: string } | null, sem: string, i: number) => ({ chave: r ? String(r.id) : `sem-${i}`, rotulo: r?.nome ?? sem })
  return {
    segmentos: d.segmentos.map((x, i): LinhaNps => ({ ...ref(x.segmento, 'Sem segmento', i), empresas: x.empresas, nps: x.nps })),
    grupos: d.grupos.map((x, i): LinhaNps => ({ ...ref(x.grupo, 'Sem grupo', i), empresas: x.empresas, nps: x.nps })),
    tempo: d.tempo_cliente.map((x): LinhaNps => ({ chave: x.faixa, rotulo: x.rotulo, empresas: x.empresas, nps: x.nps })),
    valor: d.valor.map((x): LinhaNps => ({ chave: x.faixa, rotulo: x.rotulo, empresas: x.empresas, nps: x.nps })),
  }
})
const semRespostas = computed(() => !!dados.value && !dados.value.segmentos.length && !dados.value.grupos.length)

const CARTOES = [
  { chave: 'segmentos', titulo: 'Por segmento', dimensao: 'Segmento', descricao: 'Do NPS mais baixo para o mais alto.' },
  { chave: 'grupos', titulo: 'Por grupo de empresas', dimensao: 'Grupo', descricao: 'Do NPS mais baixo para o mais alto.' },
  { chave: 'tempo', titulo: 'Por tempo como cliente', dimensao: 'Tempo como cliente', descricao: 'Desde o início do contrato (cliente desde).' },
  { chave: 'valor', titulo: 'Por valor do contrato', dimensao: 'Valor do contrato', descricao: 'Valor mensal cadastrado na empresa.' },
] as const

const podeVerRespostas = computed(() => sessao.pode('respostas.ver'))
const consultaBase = computed(() => ({ ...consultaRespostas(filtros.value, props.hoje), tipo_nota: 'nps' }))
</script>

<template>
  <div class="flex flex-col gap-4">
    <!-- Filtros desta aba -->
    <section class="grid grid-cols-1 gap-3 sm:grid-cols-3" aria-label="Filtros dos grupos de clientes">
      <Selecao
        v-if="podeVerCadastros || filtros.segmento_id !== ''"
        v-model="filtros.segmento_id"
        rotulo="Segmento"
        :opcoes="opcoesSegmento(filtros.segmento_id)"
        vazio="Todos os segmentos"
      />
      <Selecao v-model="filtros.faixa_valor" rotulo="Valor do contrato" :opcoes="FAIXAS_VALOR" vazio="Todos os valores" />
      <Selecao v-model="filtros.tempo_cliente" rotulo="Tempo como cliente" :opcoes="FAIXAS_TEMPO" vazio="Qualquer tempo" />
    </section>

    <div v-if="carregando && !dados" class="grid grid-cols-1 gap-4 lg:grid-cols-2" role="status" aria-label="Carregando os grupos de clientes">
      <div v-for="i in 4" :key="i" class="cartao h-56 animate-pulse p-5">
        <div class="h-3 w-1/3 rounded bg-superficie-2" />
        <div v-for="j in 3" :key="j" class="mt-6 h-3.5 rounded bg-superficie-2" />
      </div>
      <span class="sr-only">Carregando…</span>
    </div>

    <Alerta v-else-if="erro && !dados" tom="erro">
      {{ erro }} <button type="button" class="link ml-1" @click="carregar">Tentar de novo</button>
    </Alerta>

    <div v-else-if="dados && linhas" class="flex flex-col gap-4 transition-opacity" :class="atualizando ? 'opacity-60' : ''" :aria-busy="atualizando || undefined">
      <Alerta v-if="erro" tom="erro">
        Não deu para atualizar com os filtros novos: {{ erro }} <button type="button" class="link ml-1" @click="carregar">Tentar de novo</button>
      </Alerta>
      <Alerta v-if="semRespostas" tom="info" titulo="Nenhuma resposta de NPS de empresas neste filtro">
        Este relatório usa só as respostas de NPS ligadas a uma empresa. Tente um período maior ou tire algum filtro.
      </Alerta>

      <!-- Legenda das barras (vale para os quatro cartões) -->
      <ul class="flex flex-wrap gap-x-5 gap-y-1 text-sm text-texto-suave" aria-label="Legenda das barras">
        <li class="flex items-center gap-1.5"><span class="size-2.5 rounded-[3px] bg-grafico-detrator" aria-hidden="true" />Detratores (0 a 6)</li>
        <li class="flex items-center gap-1.5"><span class="size-2.5 rounded-[3px] bg-grafico-neutro" aria-hidden="true" />Neutros (7 e 8)</li>
        <li class="flex items-center gap-1.5"><span class="size-2.5 rounded-[3px] bg-grafico-promotor" aria-hidden="true" />Promotores (9 e 10)</li>
      </ul>

      <div class="grid grid-cols-1 items-start gap-4 lg:grid-cols-2">
        <section v-for="c in CARTOES" :key="c.chave" class="cartao flex min-w-0 flex-col gap-4 p-5 sm:p-6" :aria-labelledby="`t-grupos-${c.chave}`">
          <header class="flex items-start justify-between gap-3">
            <div class="min-w-0">
              <h2 :id="`t-grupos-${c.chave}`" class="text-base font-bold text-texto">{{ c.titulo }}</h2>
              <p class="text-sm text-texto-suave">{{ c.descricao }}</p>
            </div>
            <button
              v-if="linhas[c.chave].length"
              type="button"
              class="-mr-2 inline-flex h-10 shrink-0 items-center gap-1.5 rounded-xl px-3 text-sm font-semibold text-texto-suave hover:bg-superficie-2 hover:text-texto"
              :aria-pressed="emTabela[c.chave]"
              @click="emTabela[c.chave] = !emTabela[c.chave]"
            >
              <BarChart3 v-if="emTabela[c.chave]" class="size-4" aria-hidden="true" />
              <Table2 v-else class="size-4" aria-hidden="true" />
              {{ emTabela[c.chave] ? 'Ver barras' : 'Ver em tabela' }}
            </button>
          </header>
          <ListaBarrasNps :linhas="linhas[c.chave]" :em-tabela="emTabela[c.chave]" :titulo="`NPS ${c.titulo.toLowerCase()}`" :dimensao="c.dimensao" />
        </section>
      </div>

      <!-- O que resolver primeiro -->
      <section class="cartao flex flex-col gap-4 p-5 sm:p-6" aria-labelledby="t-prioridades">
        <header>
          <h2 id="t-prioridades" class="text-base font-bold text-texto">O que resolver primeiro</h2>
          <p class="text-sm text-texto-suave">Os temas mais citados e com a nota mais baixa vêm primeiro (temas citados em 2 ou mais respostas de NPS).</p>
        </header>
        <div v-if="dados.prioridades.length" class="grid grid-cols-1 gap-6 xl:grid-cols-[minmax(0,1fr)_20rem]">
          <GraficoPrioridades :prioridades="dados.prioridades" />
          <ol class="flex flex-col gap-1" aria-label="Temas em ordem de prioridade">
            <li v-for="(p, i) in dados.prioridades" :key="p.tema">
              <component
                :is="podeVerRespostas ? RouterLink : 'div'"
                :to="podeVerRespostas ? { path: '/respostas', query: { ...consultaBase, tema: p.tema } } : undefined"
                class="flex items-start gap-3 rounded-xl px-2 py-2"
                :class="podeVerRespostas ? 'group hover:bg-superficie-2' : ''"
              >
                <span class="mt-0.5 flex size-6 shrink-0 items-center justify-center rounded-full bg-superficie-2 text-xs font-bold text-texto">{{ i + 1 }}</span>
                <span class="min-w-0 flex-1">
                  <span class="flex items-center gap-2">
                    <span class="size-2.5 shrink-0 rounded-full" :class="corDoTema(p.tema).fundo" aria-hidden="true" />
                    <span class="min-w-0 break-words text-sm font-semibold text-texto group-hover:underline">{{ p.rotulo }}</span>
                  </span>
                  <span class="mt-1 flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-texto-fraco">
                    <span>{{ plural(p.mencoes, 'menção', 'menções') }} · {{ plural(p.reclamacoes, 'reclamação', 'reclamações') }}</span>
                    <Etiqueta v-if="p.nota_media !== null" :tom="tomNotaMedia(p.nota_media)">nota média {{ formatarMedia1(p.nota_media) }}</Etiqueta>
                  </span>
                </span>
              </component>
            </li>
          </ol>
        </div>
        <div v-else class="flex items-start gap-3 rounded-xl bg-superficie-2 p-4 text-sm">
          <Target class="mt-0.5 size-5 shrink-0 text-texto-fraco" aria-hidden="true" />
          <p class="text-texto-suave">Nenhum tema foi citado em 2 ou mais respostas de NPS neste filtro.</p>
        </div>
      </section>
    </div>
  </div>
</template>

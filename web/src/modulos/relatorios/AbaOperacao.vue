<script setup lang="ts">
// Relatórios › Operação: taxa de resposta e convites por canal (no período), as ações (concluídas no período, tempo
// médio para concluir, % no prazo; abertas e vencidas agora) e os contatos que ainda não responderam o último convite
// (essa lista não depende do período; os atrasados vêm primeiro, em destaque).
import { computed, ref, watch } from 'vue'
import { RouterLink } from 'vue-router'
import { AlertTriangle, ArrowRight, Mail, MessageCircle, UserCheck } from 'lucide-vue-next'
import { relatoriosApi, type ContatoSemResposta } from '@/api'
import { useSessaoStore } from '@/stores/sessao'
import { formatarData } from '@/utils/datas'
import { formatarNumero, plural } from '@/utils/formatos'
import Alerta from '@/components/ui/Alerta.vue'
import EstadoVazio from '@/components/ui/EstadoVazio.vue'
import Etiqueta from '@/components/ui/Etiqueta.vue'
import Paginacao from '@/components/ui/Paginacao.vue'
import Tabela, { type Coluna } from '@/components/ui/Tabela.vue'
import { CANAIS_ENVIO } from '@/modulos/envios/logica'
import { formatarMedia1, formatarPct } from '@/modulos/painel/logica'
import { comunsParaApi, type FiltrosRelatorioTela } from './logica'
import { usarRelatorio } from './usarRelatorio'

const props = defineProps<{ hoje: string; pronto: boolean }>()
const filtros = defineModel<FiltrosRelatorioTela>('filtros', { required: true })
const sessao = useSessaoStore()

const consulta = computed(() => comunsParaApi(filtros.value, props.hoje))
const { dados, carregando, atualizando, erro, carregar } = usarRelatorio(
  (sinal) => relatoriosApi.operacao(consulta.value, sinal),
  () => JSON.stringify(consulta.value),
  () => props.pronto,
)

const taxa = computed(() => dados.value?.taxa_resposta ?? null)
const acoes = computed(() => dados.value?.acoes ?? null)
const semResposta = computed(() => dados.value?.sem_resposta ?? null)
const canais = computed(() => dados.value?.canais ?? [])
const podeVerAcoes = computed(() => sessao.pode('acoes.ver'))
const podeVerContatos = computed(() => sessao.pode('contatos.ver'))
const podeExportar = computed(() => sessao.pode('painel.exportar'))

const ICONES_CANAL = { email: Mail, whatsapp: MessageCircle } as const
const iconeCanal = (c: string) => ICONES_CANAL[c as keyof typeof ICONES_CANAL] ?? Mail
const rotuloCanal = (c: string) => CANAIS_ENVIO[c as keyof typeof CANAIS_ENVIO] ?? c
/** Largura da barra do canal (a % que respondeu), sem passar de 100. */
const larguraBarra = (p: number | null) => `${Math.min(100, Math.max(0, p ?? 0))}%`

// ── Contatos sem resposta: a API manda até 1.000 (mais dias primeiro); a tela mostra de 50 em 50 ─────────────
const POR_PAGINA_LISTA = 50
const paginaLista = ref(1)
const itensSemResposta = computed<ContatoSemResposta[]>(() => semResposta.value?.itens ?? [])
const paginaAtual = computed(() => itensSemResposta.value.slice((paginaLista.value - 1) * POR_PAGINA_LISTA, paginaLista.value * POR_PAGINA_LISTA))
// Dados novos (outro grupo, "só ativas"): volta para o começo da lista.
watch(semResposta, () => (paginaLista.value = 1))
const cortada = computed(() => !!semResposta.value && semResposta.value.total > itensSemResposta.value.length)

const colunas: Coluna[] = [
  { chave: 'contato', rotulo: 'Contato', classe: 'w-[30%]' },
  { chave: 'empresa', rotulo: 'Empresa' },
  { chave: 'envio', rotulo: 'Último envio' },
  { chave: 'dias', rotulo: 'Sem resposta há', alinhar: 'direita' },
  { chave: 'situacao', rotulo: 'Situação' },
]
</script>

<template>
  <div class="flex flex-col gap-4">
    <!-- Primeira carga -->
    <div v-if="carregando && !dados" class="grid grid-cols-1 gap-4 lg:grid-cols-2" role="status" aria-label="Carregando o relatório de operação">
      <div v-for="i in 3" :key="i" class="cartao h-44 animate-pulse p-5" :class="i === 3 ? 'lg:col-span-2' : ''">
        <div class="h-3 w-1/3 rounded bg-superficie-2" />
        <div class="mt-4 h-9 w-1/4 rounded bg-superficie-2" />
        <div class="mt-4 h-3 w-2/3 rounded bg-superficie-2" />
      </div>
      <span class="sr-only">Carregando…</span>
    </div>

    <Alerta v-else-if="erro && !dados" tom="erro">
      {{ erro }} <button type="button" class="link ml-1" @click="carregar">Tentar de novo</button>
    </Alerta>

    <div v-else-if="dados && taxa && acoes && semResposta" class="flex flex-col gap-4 transition-opacity" :class="atualizando ? 'opacity-60' : ''" :aria-busy="atualizando || undefined">
      <Alerta v-if="erro" tom="erro">
        Não deu para atualizar com os filtros novos: {{ erro }} <button type="button" class="link ml-1" @click="carregar">Tentar de novo</button>
      </Alerta>

      <div class="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <!-- Taxa de resposta -->
        <section class="cartao flex flex-col gap-2 p-5 sm:p-6" aria-labelledby="t-op-taxa">
          <h2 id="t-op-taxa" class="text-sm font-semibold text-texto-suave">Taxa de resposta</h2>
          <template v-if="taxa.percentual !== null && taxa.convidados > 0">
            <p class="text-4xl font-extrabold leading-none text-texto">{{ formatarPct(taxa.percentual) }}</p>
            <p class="text-sm text-texto-suave">
              {{ formatarNumero(taxa.responderam) }} de {{ plural(taxa.convidados, 'contato', 'contatos') }} {{ taxa.responderam === 1 ? 'respondeu' : 'responderam' }}
            </p>
            <p class="text-xs text-texto-fraco">Conta os contatos que receberam a pesquisa no período e, desses, os que responderam no período.</p>
            <p v-if="taxa.amostra_pequena" class="mt-1 flex items-start gap-1.5 rounded-lg bg-atencao-suave px-2.5 py-2 text-xs text-atencao">
              <AlertTriangle class="mt-px size-3.5 shrink-0" aria-hidden="true" />
              <span><strong class="font-semibold">Amostra pequena:</strong> menos de 20% responderam; os números podem não mostrar o que todos pensam.</span>
            </p>
          </template>
          <template v-else>
            <p class="text-4xl font-extrabold leading-none text-texto-fraco" aria-hidden="true">—</p>
            <p class="text-sm text-texto-suave">Nenhuma pesquisa saiu no período, então não dá para calcular.</p>
          </template>
        </section>

        <!-- Convites por canal -->
        <section class="cartao flex flex-col gap-4 p-5 sm:p-6" aria-labelledby="t-op-canais">
          <h2 id="t-op-canais" class="text-sm font-semibold text-texto-suave">Convites por canal</h2>
          <ul class="flex flex-col gap-4">
            <li v-for="c in canais" :key="c.canal" class="flex flex-col gap-1.5">
              <div class="flex items-baseline justify-between gap-3">
                <span class="flex items-center gap-2 font-semibold text-texto">
                  <component :is="iconeCanal(c.canal)" class="size-4 self-center text-texto-fraco" aria-hidden="true" />
                  {{ rotuloCanal(c.canal) }}
                </span>
                <span v-if="c.convidados > 0" class="text-lg font-bold tabular-nums text-texto">{{ formatarPct(c.percentual) }}</span>
              </div>
              <template v-if="c.convidados > 0">
                <div class="h-2 w-full overflow-hidden rounded-full bg-superficie-2" aria-hidden="true">
                  <div class="h-full rounded-full bg-grafico-serie" :style="{ width: larguraBarra(c.percentual) }" />
                </div>
                <p class="text-sm text-texto-suave">
                  {{ formatarNumero(c.responderam) }} de {{ plural(c.convidados, 'convidado', 'convidados') }} {{ c.responderam === 1 ? 'respondeu' : 'responderam' }}
                </p>
              </template>
              <p v-else class="text-sm text-texto-fraco">Nenhum convite saiu por {{ rotuloCanal(c.canal) }} no período.</p>
            </li>
          </ul>
        </section>
      </div>

      <!-- Ações -->
      <section class="cartao flex flex-col gap-4 p-5 sm:p-6" aria-labelledby="t-op-acoes">
        <header class="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
          <div>
            <h2 id="t-op-acoes" class="text-base font-bold text-texto">Planos de ação</h2>
            <p class="text-sm text-texto-suave">Concluídas, tempo e prazo contam o período; abertas e vencidas são de agora.</p>
          </div>
          <RouterLink v-if="podeVerAcoes" to="/planos-de-acao" class="link inline-flex min-h-10 shrink-0 items-center gap-1 text-sm">
            Abrir os planos de ação <ArrowRight class="size-4" aria-hidden="true" />
          </RouterLink>
        </header>
        <dl class="grid grid-cols-2 gap-x-4 gap-y-5 xl:grid-cols-4">
          <div class="flex flex-col gap-1">
            <dt class="min-h-10 text-sm text-texto-suave sm:min-h-0">Concluídas no período</dt>
            <dd class="text-3xl font-extrabold leading-none tabular-nums text-texto">{{ formatarNumero(acoes.concluidas) }}</dd>
          </div>
          <div class="flex flex-col gap-1">
            <dt class="min-h-10 text-sm text-texto-suave sm:min-h-0">Tempo médio para concluir</dt>
            <dd v-if="acoes.tempo_medio_dias !== null" class="text-3xl font-extrabold leading-none tabular-nums text-texto">
              {{ formatarMedia1(acoes.tempo_medio_dias) }} <span class="text-base font-semibold text-texto-suave">{{ acoes.tempo_medio_dias === 1 ? 'dia' : 'dias' }}</span>
            </dd>
            <dd v-else class="text-sm text-texto-fraco"><span class="sr-only">Sem dados: </span>Nenhuma ação concluída no período.</dd>
          </div>
          <div class="flex flex-col gap-1">
            <dt class="min-h-10 text-sm text-texto-suave sm:min-h-0">Concluídas no prazo</dt>
            <dd v-if="acoes.no_prazo_percentual !== null" class="text-3xl font-extrabold leading-none tabular-nums text-texto">{{ formatarPct(acoes.no_prazo_percentual) }}</dd>
            <dd v-else class="text-sm text-texto-fraco"><span class="sr-only">Sem dados: </span>Nenhuma concluída no período tinha prazo.</dd>
            <dd v-if="acoes.no_prazo_percentual !== null" class="text-xs text-texto-fraco">das concluídas que tinham prazo</dd>
          </div>
          <div class="flex flex-col gap-1">
            <dt class="min-h-10 text-sm text-texto-suave sm:min-h-0">Abertas agora</dt>
            <dd class="text-3xl font-extrabold leading-none tabular-nums text-texto">{{ formatarNumero(acoes.abertas) }}</dd>
            <dd>
              <Etiqueta v-if="acoes.vencidas" tom="erro" ponto>{{ plural(acoes.vencidas, 'vencida', 'vencidas') }}</Etiqueta>
              <span v-else-if="acoes.abertas" class="text-xs text-texto-fraco">nenhuma vencida</span>
            </dd>
          </div>
        </dl>
      </section>

      <!-- Contatos sem resposta -->
      <section class="cartao" aria-labelledby="t-op-sem-resposta" data-sem-resposta>
        <header class="flex flex-col gap-1 border-b border-borda p-5 sm:px-6">
          <h2 id="t-op-sem-resposta" class="text-base font-bold text-texto">Contatos sem resposta</h2>
          <p class="text-sm text-texto-suave">
            Contatos ativos que receberam a pesquisa e ainda não responderam o último convite. Esta lista é de agora: não depende do período.
          </p>
          <p class="flex flex-wrap items-center gap-x-3 gap-y-1 pt-1 text-sm">
            <strong class="font-semibold text-texto">{{ plural(semResposta.total, 'contato', 'contatos') }}</strong>
            <Etiqueta v-if="semResposta.atrasados" tom="erro" ponto>{{ plural(semResposta.atrasados, 'atrasado', 'atrasados') }}</Etiqueta>
            <span class="text-texto-fraco">
              Atrasado = mais de {{ plural(semResposta.intervalo_dias, 'dia', 'dias') }} desde o envio (o intervalo entre envios da configuração).
            </span>
          </p>
        </header>

        <EstadoVazio
          v-if="!itensSemResposta.length"
          :icone="UserCheck"
          titulo="Ninguém esperando resposta"
          descricao="Todos os contatos que receberam o último convite já responderam."
        />
        <template v-else>
          <p v-if="cortada" class="border-b border-borda px-5 py-2.5 text-sm text-texto-fraco sm:px-6">
            Mostrando os {{ formatarNumero(itensSemResposta.length) }} há mais tempo sem resposta.<template v-if="podeExportar"> O CSV traz todos.</template>
          </p>

          <!-- Computador (a partir de 1280 px) -->
          <div class="hidden xl:block">
            <Tabela densa :colunas="colunas" :linhas="paginaAtual" :chave="(x) => String(x.contato.id)" legenda="Contatos sem resposta, há mais tempo primeiro">
              <template #cel-contato="{ linha: x }">
                <RouterLink v-if="podeVerContatos" :to="`/contatos/${x.contato.id}`" class="font-semibold text-texto hover:underline">{{ x.contato.nome }}</RouterLink>
                <span v-else class="font-semibold text-texto">{{ x.contato.nome }}</span>
                <span v-if="x.contato.email" class="block truncate text-xs text-texto-fraco">{{ x.contato.email }}</span>
              </template>
              <template #cel-empresa="{ linha: x }">
                <span :class="x.empresa ? 'text-texto-suave' : 'text-texto-fraco'">{{ x.empresa?.nome ?? 'Sem empresa' }}</span>
              </template>
              <template #cel-envio="{ linha: x }">
                <span class="whitespace-nowrap text-texto-suave">{{ formatarData(x.ultimo_envio) }}</span>
              </template>
              <template #cel-dias="{ linha: x }">
                <span class="whitespace-nowrap tabular-nums" :class="x.atrasado ? 'font-semibold text-erro' : 'text-texto'">{{ plural(x.dias, 'dia', 'dias') }}</span>
              </template>
              <template #cel-situacao="{ linha: x }">
                <Etiqueta v-if="x.atrasado" tom="erro" ponto>Atrasado</Etiqueta>
                <span v-else class="text-sm text-texto-fraco">No prazo</span>
              </template>
            </Tabela>
          </div>

          <!-- Celular, tablet e telas até 1280 px -->
          <ul class="flex flex-col divide-y divide-borda xl:hidden" aria-label="Contatos sem resposta, há mais tempo primeiro">
            <li v-for="x in paginaAtual" :key="String(x.contato.id)" class="flex items-start justify-between gap-3 px-4 py-3.5">
              <div class="min-w-0">
                <RouterLink v-if="podeVerContatos" :to="`/contatos/${x.contato.id}`" class="font-semibold text-texto hover:underline">{{ x.contato.nome }}</RouterLink>
                <p v-else class="font-semibold text-texto">{{ x.contato.nome }}</p>
                <p class="truncate text-sm text-texto-fraco">{{ x.empresa?.nome ?? 'Sem empresa' }}</p>
                <p class="text-sm text-texto-suave">Último envio em {{ formatarData(x.ultimo_envio) }}</p>
              </div>
              <div class="flex shrink-0 flex-col items-end gap-1">
                <span class="tabular-nums" :class="x.atrasado ? 'font-semibold text-erro' : 'text-texto'">{{ plural(x.dias, 'dia', 'dias') }}</span>
                <Etiqueta v-if="x.atrasado" tom="erro" ponto>Atrasado</Etiqueta>
              </div>
            </li>
          </ul>

          <Paginacao
            v-model="paginaLista"
            :total="itensSemResposta.length"
            :por-pagina="POR_PAGINA_LISTA"
            :nome-itens="itensSemResposta.length === 1 ? 'contato' : 'contatos'"
          />
        </template>
      </section>
    </div>
  </div>
</template>

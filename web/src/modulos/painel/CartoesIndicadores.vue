<script setup lang="ts">
// Faixa de indicadores compactos (auto-fit): receita em risco, planos de ação, CSAT e taxa de resposta. Indicador sem
// dado vira cartão apagado (fundo superficie-2, borda tracejada) com a frase curta e o atalho para resolver, só para
// quem pode abrir o destino.
import { computed } from 'vue'
import { RouterLink } from 'vue-router'
import { AlertTriangle } from 'lucide-vue-next'
import type { Painel } from '@/api/tipos'
import { useSessaoStore } from '@/stores/sessao'
import { formatarNumero, plural } from '@/utils/formatos'
import { formatarMedia2, formatarMoedaCurta, pctCarteira, tomCsat } from './logica'

const props = defineProps<{
  atencao: Painel['atencao']
  csat: Painel['csat']
  taxa: Painel['taxa_resposta']
  /** Etapa 5h, modo exemplo: sem links (os atalhos viram texto). */
  desativado?: boolean
}>()
const sessao = useSessaoStore()
/** O perfil abre o destino (e não é o modo exemplo). */
const pode = (permissao: Parameters<typeof sessao.pode>[0]) => !props.desativado && sessao.pode(permissao)

const COR = { sucesso: 'text-sucesso', atencao: 'text-atencao', erro: 'text-erro', neutro: 'text-texto', marca: 'text-texto', info: 'text-texto' } as const

const receita = computed(() => props.atencao?.receita_em_risco ?? { valor: 0, empresas: 0, sem_valor: 0, carteira: null })
const valorReceita = computed(() => Number(receita.value.valor) || 0)
const pct = computed(() => pctCarteira(receita.value.valor, receita.value.carteira))
const abertas = computed(() => props.atencao?.acoes_abertas ?? 0)
const vencidas = computed(() => props.atencao?.acoes_vencidas ?? 0)
/** A empresa com a ação mais urgente (a API manda em ordem de urgência). */
const urgente = computed(() => (props.atencao?.empresas ?? []).find((e) => e.acao_id !== null && e.acao_id !== undefined) ?? null)
const podeVerAcoes = computed(() => pode('acoes.ver'))
/** Nenhuma empresa do filtro tem valor mensal (carteira nula) e nada em risco: o número não diria nada. */
const semValores = computed(() => receita.value.carteira === null && valorReceita.value === 0)
const temCsat = computed(() => !!props.csat && props.csat.total > 0 && props.csat.percentual !== null)
const temTaxa = computed(() => !!props.taxa && props.taxa.percentual !== null && props.taxa.convidados > 0)

const CARTAO = 'flex min-w-0 flex-col gap-1 rounded-cartao p-4 sm:p-5'
const CHEIO = 'border border-borda bg-superficie shadow-cartao'
const APAGADO = 'border border-dashed border-borda-forte bg-superficie-2'
</script>

<template>
  <section class="grid grid-cols-1 gap-3 min-[420px]:grid-cols-2 lg:grid-cols-[repeat(auto-fit,minmax(13rem,1fr))] lg:gap-4" aria-label="Indicadores">
    <!-- Receita em risco -->
    <div v-if="semValores" :class="[CARTAO, APAGADO]" data-indicador="receita" data-apagado>
      <h2 class="text-sm font-semibold text-texto-suave">Receita em risco</h2>
      <p class="font-bold text-texto-suave">Cadastre o valor mensal das empresas</p>
      <RouterLink v-if="pode('contatos.editar')" to="/contatos?aba=empresas" class="link inline-flex min-h-11 items-center text-sm sm:min-h-0">
        Ir para Contatos › Empresas
      </RouterLink>
      <p v-else class="text-xs text-texto-fraco">Com o valor do contrato, o painel mostra quanto está em risco.</p>
    </div>
    <div v-else :class="[CARTAO, CHEIO]" data-indicador="receita">
      <h2 class="text-sm font-semibold text-texto-suave">Receita em risco</h2>
      <p class="text-2xl font-extrabold leading-tight" :class="valorReceita > 0 ? 'text-erro' : 'text-texto'">
        {{ formatarMoedaCurta(valorReceita) }}<span class="text-sm font-semibold text-texto-fraco"> /mês</span>
      </p>
      <p class="text-xs text-texto-suave">
        <template v-if="receita.empresas">
          {{ plural(receita.empresas, 'empresa', 'empresas') }} com detrator<template v-if="pct !== null"> · {{ pct }}% da carteira</template>
        </template>
        <template v-else>Nenhuma empresa teve detrator no período.</template>
      </p>
      <p v-if="receita.sem_valor" class="text-xs text-atencao">
        {{ receita.sem_valor === 1 ? '1 delas não tem' : `${formatarNumero(receita.sem_valor)} delas não têm` }} o valor do contrato.
        <RouterLink v-if="pode('contatos.ver')" to="/contatos?aba=empresas" class="link inline-flex min-h-11 items-center sm:min-h-0">Completar em Empresas</RouterLink>
      </p>
    </div>

    <!-- Planos de ação -->
    <div :class="[CARTAO, CHEIO]" data-indicador="planos">
      <h2 class="text-sm font-semibold text-texto-suave">Planos de ação</h2>
      <p class="text-2xl font-extrabold leading-tight text-texto">
        <RouterLink v-if="podeVerAcoes" to="/planos-de-acao" class="inline-flex min-h-11 items-center hover:underline sm:min-h-0">{{ plural(abertas, 'aberto', 'abertos') }}</RouterLink>
        <template v-else>{{ plural(abertas, 'aberto', 'abertos') }}</template>
      </p>
      <p class="flex items-center gap-1 text-xs" :class="vencidas ? 'font-semibold text-erro' : 'text-texto-suave'">
        <AlertTriangle v-if="vencidas" class="size-3.5 shrink-0" aria-hidden="true" />
        <RouterLink v-if="vencidas && podeVerAcoes" :to="{ path: '/planos-de-acao', query: { so_vencidas: 'true' } }" class="hover:underline">
          {{ plural(vencidas, 'vencido', 'vencidos') }}
        </RouterLink>
        <template v-else>{{ vencidas ? plural(vencidas, 'vencido', 'vencidos') : 'Nenhum vencido' }}</template>
      </p>
      <p v-if="urgente && podeVerAcoes" class="text-xs text-texto-suave">
        <RouterLink :to="`/planos-de-acao/${urgente.acao_id}`" class="link inline-flex min-h-11 items-center sm:min-h-0" data-tratar>
          Tratar {{ urgente.empresa.nome }}<span class="sr-only">: a ação mais urgente</span>
        </RouterLink>
      </p>
      <p v-else-if="urgente && desativado" class="text-xs font-semibold text-texto-suave" data-tratar>
        Tratar {{ urgente.empresa.nome }}<span class="sr-only">: a ação mais urgente</span>
      </p>
    </div>

    <!-- CSAT -->
    <div v-if="temCsat" :class="[CARTAO, CHEIO]" data-indicador="csat">
      <h2 class="text-sm font-semibold text-texto-suave">Satisfação (CSAT)</h2>
      <p class="text-2xl font-extrabold leading-tight" :class="COR[tomCsat(csat.percentual)]">{{ formatarNumero(csat.percentual) }}%</p>
      <p class="text-xs text-texto-suave">deram 4 ou 5 · média {{ formatarMedia2(csat.media) }} de 5 · {{ plural(csat.total, 'resposta', 'respostas') }}</p>
    </div>
    <div v-else :class="[CARTAO, APAGADO]" data-indicador="csat" data-apagado>
      <h2 class="text-sm font-semibold text-texto-suave">Satisfação (CSAT)</h2>
      <p class="font-bold text-texto-suave">Ainda sem respostas</p>
      <RouterLink v-if="pode('formularios.ver')" to="/formularios" class="link inline-flex min-h-11 items-center text-sm sm:min-h-0">
        Incluir a pergunta 1–5 num formulário
      </RouterLink>
      <p v-else class="text-xs text-texto-fraco">Nenhuma resposta de nota 1 a 5 no período.</p>
    </div>

    <!-- Taxa de resposta -->
    <div v-if="temTaxa" :class="[CARTAO, CHEIO]" data-indicador="taxa">
      <h2 class="text-sm font-semibold text-texto-suave">Taxa de resposta</h2>
      <p class="text-2xl font-extrabold leading-tight text-texto">{{ formatarNumero(taxa.percentual) }}%</p>
      <p class="text-xs text-texto-suave">
        {{ formatarNumero(taxa.responderam) }} de {{ plural(taxa.convidados, 'contato', 'contatos') }} {{ taxa.responderam === 1 ? 'respondeu' : 'responderam' }}
      </p>
      <p v-if="taxa.amostra_pequena" class="flex items-start gap-1 text-xs text-atencao">
        <AlertTriangle class="mt-px size-3.5 shrink-0" aria-hidden="true" />
        <span><strong class="font-semibold">Amostra pequena:</strong> menos de 20% responderam.</span>
      </p>
    </div>
    <div v-else :class="[CARTAO, APAGADO]" data-indicador="taxa" data-apagado>
      <h2 class="text-sm font-semibold text-texto-suave">Taxa de resposta</h2>
      <p class="font-bold text-texto-suave">Nenhum envio no período</p>
      <RouterLink v-if="pode('envios.ver')" to="/envios" class="link inline-flex min-h-11 items-center text-sm sm:min-h-0">Ir para Envios</RouterLink>
      <p v-else class="text-xs text-texto-fraco">Sem pesquisas enviadas, não dá para calcular.</p>
    </div>
  </section>
</template>

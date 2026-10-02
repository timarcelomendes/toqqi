<script setup lang="ts">
// Histórico de cobranças (as 12 mais recentes): vencimento, valor, forma, situação e o link da fatura no Asaas
// (abre em nova aba). Tabela a partir de 640 px; cartões no celular.
import { computed } from 'vue'
import { ExternalLink, Receipt } from 'lucide-vue-next'
import type { CobrancaAssinatura } from '@/api/tipos'
import { formatarData } from '@/utils/datas'
import { formatarMoeda } from '@/utils/formatos'
import EstadoVazio from '@/components/ui/EstadoVazio.vue'
import Etiqueta from '@/components/ui/Etiqueta.vue'
import Tabela, { type Coluna } from '@/components/ui/Tabela.vue'
import { linkDaCobranca, rotuloForma, situacaoCobranca } from './logica'

const props = defineProps<{ cobrancas: CobrancaAssinatura[] }>()

// As cobranças não têm id na API: a posição na lista serve de chave.
const linhas = computed(() => props.cobrancas.map((c, i) => ({ ...c, posicao: i, link: linkDaCobranca(c) })))
type Linha = (typeof linhas.value)[number]

const colunas: Coluna[] = [
  { chave: 'vencimento', rotulo: 'Vencimento' },
  { chave: 'valor', rotulo: 'Valor', alinhar: 'direita' },
  { chave: 'forma', rotulo: 'Forma' },
  { chave: 'situacao', rotulo: 'Situação' },
  { chave: 'pago_em', rotulo: 'Paga em', classe: 'hidden md:table-cell' },
  { chave: 'link', rotulo: 'Fatura', rotuloOculto: true, alinhar: 'direita' },
]
const chave = (c: Linha) => c.posicao
</script>

<template>
  <EstadoVazio v-if="!cobrancas.length" :icone="Receipt" titulo="Nenhuma cobrança ainda" descricao="As faturas da assinatura aparecem aqui." />
  <template v-else>
    <div class="hidden sm:block">
      <Tabela :colunas="colunas" :linhas="linhas" :chave="chave" legenda="Histórico de cobranças">
        <template #cel-vencimento="{ linha: c }">
          <span class="whitespace-nowrap font-semibold text-texto">{{ formatarData(c.vencimento) }}</span>
        </template>
        <template #cel-valor="{ linha: c }">
          <span class="whitespace-nowrap tabular-nums text-texto">{{ formatarMoeda(c.valor) }}</span>
        </template>
        <template #cel-forma="{ linha: c }">
          <span class="text-texto-suave">{{ rotuloForma(c) }}</span>
        </template>
        <template #cel-situacao="{ linha: c }">
          <Etiqueta :tom="situacaoCobranca(c.situacao).tom" ponto>{{ situacaoCobranca(c.situacao).rotulo }}</Etiqueta>
        </template>
        <template #cel-pago_em="{ linha: c }">
          <span class="whitespace-nowrap text-texto-suave">{{ formatarData(c.pago_em) }}</span>
        </template>
        <template #cel-link="{ linha: c }">
          <a v-if="c.link" :href="c.link" target="_blank" rel="noopener noreferrer" class="link inline-flex items-center gap-1 whitespace-nowrap">
            Ver fatura <ExternalLink class="size-3.5" aria-hidden="true" />
            <span class="sr-only">de {{ formatarData(c.vencimento) }} (abre em nova aba)</span>
          </a>
        </template>
      </Tabela>
    </div>
    <ul class="flex flex-col divide-y divide-borda sm:hidden" aria-label="Histórico de cobranças">
      <li v-for="c in linhas" :key="c.posicao" class="flex flex-col gap-1.5 px-4 py-3.5">
        <div class="flex items-start justify-between gap-3">
          <p class="font-semibold text-texto">
            {{ formatarData(c.vencimento) }}
            <span class="font-normal text-texto-suave">· {{ formatarMoeda(c.valor) }}</span>
          </p>
          <Etiqueta :tom="situacaoCobranca(c.situacao).tom" ponto>{{ situacaoCobranca(c.situacao).rotulo }}</Etiqueta>
        </div>
        <p v-if="rotuloForma(c) !== '—' || c.pago_em" class="text-sm text-texto-suave">
          {{ rotuloForma(c) }}<template v-if="c.pago_em"> · paga em {{ formatarData(c.pago_em) }}</template>
        </p>
        <a v-if="c.link" :href="c.link" target="_blank" rel="noopener noreferrer" class="link inline-flex min-h-10 items-center gap-1 self-start text-sm">
          Ver fatura <ExternalLink class="size-3.5" aria-hidden="true" />
          <span class="sr-only">de {{ formatarData(c.vencimento) }} (abre em nova aba)</span>
        </a>
      </li>
    </ul>
  </template>
</template>

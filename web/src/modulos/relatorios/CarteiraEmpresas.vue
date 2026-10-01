<script setup lang="ts">
// As empresas de uma carteira (Relatórios › Responsáveis, ao abrir uma linha): NPS, nota média ou "Sem respostas",
// valor, última resposta e ações abertas. O nome da empresa abre o histórico dela.
import { History } from 'lucide-vue-next'
import type { EmpresaDaCarteira, Id } from '@/api/tipos'
import { formatarData } from '@/utils/datas'
import { formatarMoeda, plural } from '@/utils/formatos'
import Alerta from '@/components/ui/Alerta.vue'
import Etiqueta from '@/components/ui/Etiqueta.vue'
import { formatarMedia1, tomNotaMedia } from '@/modulos/painel/logica'
import SeloNps from './SeloNps.vue'

defineProps<{ nome: string; carregando: boolean; erro: string | null; empresas: EmpresaDaCarteira[] | null }>()
const emit = defineEmits<{ historico: [id: Id]; tentar: [] }>()
</script>

<template>
  <div>
    <p v-if="carregando && !empresas" class="py-2 text-sm text-texto-fraco" role="status">Buscando as empresas…</p>
    <Alerta v-else-if="erro" tom="erro">
      {{ erro }} <button type="button" class="link ml-1" @click="emit('tentar')">Tentar de novo</button>
    </Alerta>
    <p v-else-if="!empresas?.length" class="py-2 text-sm text-texto-fraco">Nenhuma empresa nesta carteira com os filtros atuais.</p>
    <p v-if="carregando && empresas" class="sr-only" role="status">Atualizando as empresas com os filtros novos…</p>
    <ul v-if="empresas?.length && !erro" class="flex flex-col divide-y divide-borda transition-opacity" :class="carregando ? 'opacity-60' : ''" :aria-busy="carregando || undefined" :aria-label="`Empresas de ${nome}`">
      <li
        v-for="e in empresas"
        :key="String(e.empresa.id)"
        class="flex flex-col gap-1 py-2.5 xl:grid xl:grid-cols-[minmax(0,1fr)_3.5rem_7.5rem_9rem_8.5rem_7.5rem] xl:items-center xl:gap-3"
      >
        <button
          type="button"
          class="inline-flex min-h-8 min-w-0 items-center gap-1.5 text-left text-sm font-semibold text-texto hover:underline"
          :title="`Ver o histórico de ${e.empresa.nome}`"
          @click="emit('historico', e.empresa.id)"
        >
          <History class="size-3.5 shrink-0 text-texto-fraco" aria-hidden="true" />
          <span class="min-w-0 break-words">{{ e.empresa.nome }}</span>
        </button>
        <span class="flex flex-wrap items-center gap-x-3 gap-y-1 text-sm text-texto-suave xl:contents">
          <span v-if="e.nps.total" class="xl:text-right"><SeloNps :nps="e.nps" compacto /></span>
          <span v-else class="hidden xl:block xl:text-right" aria-hidden="true">—</span>
          <span>
            <Etiqueta v-if="e.nps.total && e.nota_media !== null" :tom="tomNotaMedia(e.nota_media)">nota média {{ formatarMedia1(e.nota_media) }}</Etiqueta>
            <span v-else-if="!e.nps.total" class="text-texto-fraco">Sem respostas</span>
          </span>
          <span class="tabular-nums xl:text-right" :class="e.valor_mensal !== null ? '' : 'text-texto-fraco'">
            {{ e.valor_mensal !== null ? `${formatarMoeda(e.valor_mensal)}/mês` : 'sem valor' }}
          </span>
          <span class="text-texto-fraco">{{ e.ultima_resposta ? `última ${formatarData(e.ultima_resposta.data)}` : 'nunca respondeu' }}</span>
          <span class="xl:text-right" :class="e.acoes_abertas ? 'text-texto' : 'text-texto-fraco'">{{ plural(e.acoes_abertas, 'ação aberta', 'ações abertas') }}</span>
        </span>
      </li>
    </ul>
  </div>
</template>

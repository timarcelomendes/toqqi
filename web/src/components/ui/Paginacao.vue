<script setup lang="ts">
import { computed } from 'vue'
import { ChevronLeft, ChevronRight } from 'lucide-vue-next'
import { formatarNumero } from '@/utils/formatos'
import Botao from './Botao.vue'

const props = defineProps<{ total: number; porPagina: number; carregando?: boolean; nomeItens?: string }>()
const pagina = defineModel<number>({ required: true })
const totalPaginas = computed(() => Math.max(1, Math.ceil(props.total / Math.max(1, props.porPagina))))
</script>

<template>
  <nav v-if="total > 0" class="flex flex-col items-center justify-between gap-3 border-t border-borda px-4 py-3 sm:flex-row sm:px-5" aria-label="Paginação">
    <p class="text-sm text-texto-fraco">
      {{ formatarNumero(total) }} {{ nomeItens ?? (total === 1 ? 'item' : 'itens') }}
    </p>
    <div v-if="totalPaginas > 1" class="flex items-center gap-2">
      <Botao variante="secundario" tamanho="sm" :desabilitado="pagina <= 1 || carregando" @click="pagina = pagina - 1">
        <ChevronLeft class="size-4" aria-hidden="true" /> Anterior
      </Botao>
      <p class="text-sm text-texto-suave" aria-live="polite">Página {{ pagina }} de {{ totalPaginas }}</p>
      <Botao variante="secundario" tamanho="sm" :desabilitado="pagina >= totalPaginas || carregando" @click="pagina = pagina + 1">
        Próxima <ChevronRight class="size-4" aria-hidden="true" />
      </Botao>
    </div>
  </nav>
</template>

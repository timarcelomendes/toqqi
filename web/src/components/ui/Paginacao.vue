<script setup lang="ts">
// Paginação de uma lista. Trocar de página pelos botões leva a tela ao começo da lista (o bloco onde a paginação
// está), quando ele ficou para cima — e não ao topo da página. Numa caixa com rolagem própria (o corpo de uma
// janela modal), é a caixa que volta ao começo.
import { computed, nextTick, ref } from 'vue'
import { ChevronLeft, ChevronRight } from 'lucide-vue-next'
import { formatarNumero } from '@/utils/formatos'
import Botao from './Botao.vue'

const props = defineProps<{ total: number; porPagina: number; carregando?: boolean; nomeItens?: string }>()
const pagina = defineModel<number>({ required: true })
const totalPaginas = computed(() => Math.max(1, Math.ceil(props.total / Math.max(1, props.porPagina))))
const raiz = ref<HTMLElement | null>(null)

async function irPara(p: number) {
  pagina.value = p
  await nextTick()
  const lista = raiz.value?.parentElement
  if (!lista) return
  const semMovimento = typeof window.matchMedia === 'function' && window.matchMedia('(prefers-reduced-motion: reduce)').matches
  const comportamento: ScrollBehavior = semMovimento ? 'auto' : 'smooth'
  // A lista é a própria caixa que rola (corpo de uma janela modal) e foi rolada: volta ao começo dela.
  if (lista.scrollTop > 0 && lista.scrollHeight > lista.clientHeight) {
    if (typeof lista.scrollTo === 'function') lista.scrollTo({ top: 0, behavior: comportamento })
    else lista.scrollTop = 0
    return
  }
  if (typeof lista.scrollIntoView !== 'function') return
  // A folga do topo fixo do app (scroll-padding-top no html): o começo da lista fica logo abaixo dele.
  const folga = Number.parseFloat(getComputedStyle(document.documentElement).scrollPaddingTop) || 0
  if (lista.getBoundingClientRect().top >= folga) return
  lista.scrollIntoView({ block: 'start', behavior: comportamento })
}
</script>

<template>
  <nav v-if="total > 0" ref="raiz" class="flex flex-col items-center justify-between gap-3 border-t border-borda px-4 py-3 sm:flex-row sm:px-5" aria-label="Paginação">
    <p class="text-sm text-texto-fraco">
      {{ formatarNumero(total) }} {{ nomeItens ?? (total === 1 ? 'item' : 'itens') }}
    </p>
    <div v-if="totalPaginas > 1" class="flex items-center gap-2">
      <Botao variante="secundario" tamanho="sm" :desabilitado="pagina <= 1 || carregando" @click="irPara(pagina - 1)">
        <ChevronLeft class="size-4" aria-hidden="true" /> Anterior
      </Botao>
      <p class="text-sm text-texto-suave" aria-live="polite">Página {{ pagina }} de {{ totalPaginas }}</p>
      <Botao variante="secundario" tamanho="sm" :desabilitado="pagina >= totalPaginas || carregando" @click="irPara(pagina + 1)">
        Próxima <ChevronRight class="size-4" aria-hidden="true" />
      </Botao>
    </div>
  </nav>
</template>

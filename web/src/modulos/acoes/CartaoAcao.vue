<script setup lang="ts">
// Cartão de uma ação no quadro. Arrasta entre colunas (mouse) ou usa "Mover para…" (teclado e toque).
import { computed } from 'vue'
import { ArrowRightLeft, Building2, GripVertical, UserRound } from 'lucide-vue-next'
import type { Acao, SituacaoAcao } from '@/api/tipos'
import ItemMenu from '@/components/app/ItemMenu.vue'
import Etiqueta from '@/components/ui/Etiqueta.vue'
import MenuSuspenso from '@/components/ui/MenuSuspenso.vue'
import SeloNota from '@/modulos/respostas/SeloNota.vue'
import { PRIORIDADES, destinos, seloPrazo } from './logica'

const props = defineProps<{
  acao: Acao
  podeMover: boolean
  /** Dá para arrastar (computador com mouse); no celular, só o menu "Mover". */
  arrastavel?: boolean
  ocupado?: boolean
  arrastando?: boolean
}>()
const emit = defineEmits<{ abrir: [Acao]; mover: [Acao, SituacaoAcao]; arrastar: [Acao, DragEvent]; soltar: [] }>()

const selo = computed(() => seloPrazo(props.acao))
const prioridade = computed(() => PRIORIDADES[props.acao.prioridade] ?? { rotulo: props.acao.prioridade, tom: 'neutro' as const })
const opcoes = computed(() => destinos(props.acao.situacao))
const comentario = computed(() => (props.acao.resposta?.comentario ?? '').trim() || null)

function aoArrastar(e: DragEvent) {
  if (!props.arrastavel || !e.dataTransfer) return
  e.dataTransfer.effectAllowed = 'move'
  e.dataTransfer.setData('text/plain', String(props.acao.id))
  emit('arrastar', props.acao, e)
}
</script>

<template>
  <article
    class="group relative flex flex-col gap-2 rounded-xl border bg-superficie p-3.5 shadow-sm transition"
    :class="[
      selo?.tipo === 'vencido' ? 'border-erro/40' : 'border-borda',
      arrastando ? 'opacity-40' : '',
      ocupado ? 'animate-pulse' : '',
      arrastavel ? 'cursor-grab active:cursor-grabbing' : '',
    ]"
    :draggable="arrastavel && !ocupado ? 'true' : undefined"
    :aria-busy="ocupado || undefined"
    @dragstart="aoArrastar"
    @dragend="emit('soltar')"
  >
    <div class="flex items-start gap-2">
      <GripVertical v-if="arrastavel" class="mt-0.5 size-4 shrink-0 text-texto-fraco/60" aria-hidden="true" />
      <h3 class="min-w-0 flex-1 text-sm font-semibold leading-snug text-texto">
        <button
          type="button"
          class="text-left after:absolute after:inset-0 after:rounded-xl hover:underline focus-visible:outline-none focus-visible:after:outline-2 focus-visible:after:outline-offset-2 focus-visible:after:outline-foco"
          @click="emit('abrir', acao)"
        >
          {{ acao.titulo }}
        </button>
      </h3>
      <SeloNota v-if="acao.nota !== null && acao.nota !== undefined" :nota="acao.nota" :grupo="acao.grupo" :tipo="acao.tipo_nota" tamanho="sm" class="relative" />
    </div>

    <!-- O que o cliente escreveu (o motivo da ação, em poucas linhas) -->
    <p v-if="comentario" class="line-clamp-2 text-xs leading-relaxed text-texto-suave" :title="comentario" data-comentario-cliente>“{{ comentario }}”</p>

    <p v-if="acao.empresa" class="flex min-w-0 items-center gap-1.5 text-xs text-texto-suave">
      <Building2 class="size-3.5 shrink-0" aria-hidden="true" /><span class="truncate">{{ acao.empresa.nome }}</span>
    </p>
    <p class="flex min-w-0 items-center gap-1.5 text-xs" :class="acao.responsavel ? 'text-texto-suave' : 'text-atencao'">
      <UserRound class="size-3.5 shrink-0" aria-hidden="true" />
      <span class="truncate">{{ acao.responsavel?.nome ?? 'Sem responsável' }}</span>
    </p>

    <div class="flex flex-wrap items-center gap-1.5">
      <Etiqueta :tom="prioridade.tom"><span class="sr-only">Prioridade </span>{{ prioridade.rotulo }}</Etiqueta>
      <Etiqueta v-if="selo" :tom="selo.tom" :ponto="selo.tipo !== 'data'" :title="selo.descricao">{{ selo.rotulo }}</Etiqueta>
      <span v-if="acao.situacao === 'concluida' && acao.concluida_por" class="text-xs text-texto-fraco">por {{ acao.concluida_por.nome }}</span>
      <MenuSuspenso v-if="podeMover" :rotulo="`Mover a ação ${acao.titulo} para…`" fixo class="relative ml-auto">
        <template #gatilho="{ props: p }">
          <button
            v-bind="p"
            type="button"
            class="-my-1 -mr-1.5 inline-flex h-10 items-center gap-1 rounded-lg px-2 text-xs font-semibold text-texto-suave hover:bg-superficie-2 hover:text-texto disabled:opacity-50"
            :disabled="ocupado"
          >
            <ArrowRightLeft class="size-4" aria-hidden="true" /> Mover
          </button>
        </template>
        <p class="px-3 pb-1 pt-1.5 text-xs font-semibold uppercase tracking-wide text-texto-fraco" role="none">Mover para</p>
        <ItemMenu v-for="d in opcoes" :key="d.situacao" @click="emit('mover', acao, d.situacao)">{{ d.rotulo }}</ItemMenu>
      </MenuSuspenso>
    </div>
  </article>
</template>

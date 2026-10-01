<script setup lang="ts">
// Painel que desliza da direita (no celular, ocupa a tela toda). Prende o foco, fecha com Esc,
// com clique fora ou no ×, e pode pedir confirmação antes de fechar (ex.: alterações não salvas).
import { computed, onBeforeUnmount, ref, toRef, useId, watch } from 'vue'
import { X } from 'lucide-vue-next'
import { useFocoPreso } from '@/composables/focoPreso'
import { liberarRolagem, travarRolagem } from '@/composables/rolagem'

const props = withDefaults(
  defineProps<{
    titulo: string
    descricao?: string
    largura?: 'md' | 'lg'
    /** Impede fechar (ex.: enquanto salva). */
    bloqueado?: boolean
    /** Chamado antes de fechar; devolva false para continuar aberto. */
    antesDeFechar?: () => boolean | Promise<boolean>
  }>(),
  { largura: 'md' },
)

const aberto = defineModel<boolean>('aberto', { default: false })
const emit = defineEmits<{ fechado: [] }>()
const painel = ref<HTMLElement | null>(null)
const id = useId()
let fechando = false

async function fechar() {
  if (props.bloqueado || fechando) return
  fechando = true
  try {
    if (props.antesDeFechar && !(await props.antesDeFechar())) return
    aberto.value = false
  } finally {
    fechando = false
  }
}

useFocoPreso(painel, toRef(aberto), fechar)

watch(
  aberto,
  (v, antes) => {
    if (v && !antes) travarRolagem()
    else if (!v && antes) {
      liberarRolagem()
      emit('fechado')
    }
  },
  { immediate: true },
)

onBeforeUnmount(() => {
  if (aberto.value) liberarRolagem()
})

const classeLargura = computed(() => (props.largura === 'lg' ? 'sm:max-w-2xl' : 'sm:max-w-xl'))
defineExpose({ fechar })
</script>

<template>
  <Teleport to="body">
    <div v-if="aberto" class="fixed inset-0 z-50 flex justify-end">
      <div class="absolute inset-0 bg-slate-950/45 backdrop-blur-[1px]" aria-hidden="true" @click="fechar" />
      <section
        ref="painel"
        role="dialog"
        aria-modal="true"
        :aria-labelledby="`${id}-titulo`"
        :aria-describedby="descricao ? `${id}-desc` : undefined"
        tabindex="-1"
        class="relative flex h-full w-full flex-col bg-superficie shadow-2xl animate-deslizar-direita focus:outline-none sm:border-l sm:border-borda"
        :class="classeLargura"
      >
        <header class="flex items-start gap-3 border-b border-borda px-4 py-3.5 sm:px-6 sm:py-4">
          <div class="min-w-0 flex-1">
            <slot name="antes-do-titulo" />
            <h2 :id="`${id}-titulo`" class="break-words text-lg font-bold text-texto">{{ titulo }}</h2>
            <p v-if="descricao" :id="`${id}-desc`" class="mt-0.5 text-sm text-texto-suave">{{ descricao }}</p>
            <slot name="cabecalho" />
          </div>
          <button
            type="button"
            class="-mr-1.5 flex size-10 shrink-0 items-center justify-center rounded-xl text-texto-fraco hover:bg-superficie-2 hover:text-texto disabled:opacity-50"
            aria-label="Fechar"
            :disabled="bloqueado"
            @click="fechar"
          >
            <X class="size-5" aria-hidden="true" />
          </button>
        </header>
        <div class="min-h-0 flex-1 overflow-y-auto overscroll-contain px-4 py-5 sm:px-6">
          <slot />
        </div>
        <footer v-if="$slots.rodape" class="flex flex-wrap items-center justify-end gap-2 border-t border-borda bg-superficie px-4 py-3 sm:px-6">
          <slot name="rodape" />
        </footer>
      </section>
    </div>
  </Teleport>
</template>

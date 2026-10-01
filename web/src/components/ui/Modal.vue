<script setup lang="ts">
import { computed, onBeforeUnmount, ref, toRef, useId, watch } from 'vue'
import { X } from 'lucide-vue-next'
import { useFocoPreso } from '@/composables/focoPreso'
import { liberarRolagem, travarRolagem } from '@/composables/rolagem'

const props = withDefaults(
  defineProps<{
    titulo: string
    descricao?: string
    tamanho?: 'sm' | 'md' | 'lg'
    /** Impede fechar (ex.: enquanto salva). */
    bloqueado?: boolean
    papel?: 'dialog' | 'alertdialog'
    /** Por cima de painéis e outros modais (ex.: confirmação aberta de dentro de um painel lateral). */
    elevado?: boolean
  }>(),
  { tamanho: 'md', papel: 'dialog' },
)

const aberto = defineModel<boolean>('aberto', { default: false })
const emit = defineEmits<{ fechado: [] }>()
const painel = ref<HTMLElement | null>(null)
const id = useId()

function fechar() {
  if (props.bloqueado) return
  aberto.value = false
}

useFocoPreso(painel, toRef(aberto), fechar)

// Trava a rolagem da página enquanto o modal está aberto (contando com outras janelas abertas por baixo).
watch(aberto, (v, antes) => {
  if (v && !antes) travarRolagem()
  else if (!v && antes) {
    liberarRolagem()
    emit('fechado')
  }
})

onBeforeUnmount(() => {
  if (aberto.value) liberarRolagem()
})

const largura = computed(() => ({ sm: 'sm:max-w-md', md: 'sm:max-w-lg', lg: 'sm:max-w-2xl' })[props.tamanho])
</script>

<template>
  <Teleport to="body">
    <div v-if="aberto" class="fixed inset-0 flex items-end justify-center sm:items-center sm:p-6" :class="elevado ? 'z-[58]' : 'z-50'">
      <div class="absolute inset-0 bg-slate-950/50 backdrop-blur-[2px]" aria-hidden="true" @click="fechar" />
      <div
        ref="painel"
        :role="papel"
        aria-modal="true"
        :aria-labelledby="`${id}-titulo`"
        :aria-describedby="descricao ? `${id}-desc` : undefined"
        tabindex="-1"
        class="relative flex max-h-[92dvh] w-full flex-col rounded-t-2xl bg-superficie shadow-2xl animate-surgir focus:outline-none sm:rounded-2xl"
        :class="largura"
      >
        <header class="flex items-start gap-4 border-b border-borda px-5 py-4 sm:px-6">
          <div class="min-w-0 flex-1">
            <h2 :id="`${id}-titulo`" class="text-lg font-bold text-texto">{{ titulo }}</h2>
            <p v-if="descricao" :id="`${id}-desc`" class="mt-1 text-sm text-texto-suave">{{ descricao }}</p>
          </div>
          <button
            type="button"
            class="-mr-2 -mt-1 flex size-9 items-center justify-center rounded-lg text-texto-fraco hover:bg-superficie-2 hover:text-texto disabled:opacity-50"
            aria-label="Fechar"
            :disabled="bloqueado"
            @click="fechar"
          >
            <X class="size-5" aria-hidden="true" />
          </button>
        </header>
        <div class="overflow-y-auto px-5 py-5 sm:px-6">
          <slot />
        </div>
        <footer v-if="$slots.rodape" class="flex flex-col-reverse gap-2 border-t border-borda px-5 py-4 sm:flex-row sm:justify-end sm:px-6">
          <slot name="rodape" />
        </footer>
      </div>
    </div>
  </Teleport>
</template>

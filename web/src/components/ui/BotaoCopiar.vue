<script setup lang="ts">
import { ref } from 'vue'
import { Check, Copy } from 'lucide-vue-next'
import { avisar } from '@/composables/avisos'
import Botao from './Botao.vue'

const props = withDefaults(
  defineProps<{ texto: string; rotulo?: string; copiado?: string; variante?: 'primario' | 'secundario' | 'fantasma'; tamanho?: 'sm' | 'md' }>(),
  { rotulo: 'Copiar', copiado: 'Copiado!', variante: 'secundario', tamanho: 'md' },
)
const ok = ref(false)

async function copiar() {
  try {
    await navigator.clipboard.writeText(props.texto)
    ok.value = true
    setTimeout(() => (ok.value = false), 2500)
  } catch {
    avisar.atencao('Não foi possível copiar. Selecione o texto e copie manualmente.')
  }
}
</script>

<template>
  <Botao :variante="variante" :tamanho="tamanho" @click="copiar">
    <Check v-if="ok" class="size-4 text-sucesso" aria-hidden="true" />
    <Copy v-else class="size-4" aria-hidden="true" />
    <span aria-live="polite">{{ ok ? copiado : rotulo }}</span>
  </Botao>
</template>

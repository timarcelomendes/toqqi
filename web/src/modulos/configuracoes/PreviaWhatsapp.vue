<script setup lang="ts">
// Prévia da mensagem do botão WhatsApp (Configurações › Envios e a pré-visualização do editor de formulários):
// um balão como o do aplicativo, com o link destacado. Só texto (nada de HTML vindo da mensagem).
import { computed } from 'vue'

const props = defineProps<{ texto: string; link: string }>()

const partes = computed(() => {
  const i = props.link ? props.texto.indexOf(props.link) : -1
  return i < 0
    ? { antes: props.texto, link: '', depois: '' }
    : { antes: props.texto.slice(0, i), link: props.link, depois: props.texto.slice(i + props.link.length) }
})
</script>

<template>
  <div class="rounded-2xl bg-[#e5ddd5] p-4" aria-label="Prévia da mensagem de WhatsApp" data-previa-whatsapp>
    <p class="ml-auto max-w-[85%] whitespace-pre-line break-words rounded-xl rounded-tr-sm bg-[#dcf8c6] px-3 py-2 text-sm text-slate-900 shadow-sm">
      {{ partes.antes }}<span v-if="partes.link" class="text-sky-700 underline">{{ partes.link }}</span>{{ partes.depois }}
    </p>
    <p class="mt-2 text-center text-xs text-slate-600">A mensagem abre pronta no WhatsApp; quem envia aperta o botão Enviar.</p>
  </div>
</template>

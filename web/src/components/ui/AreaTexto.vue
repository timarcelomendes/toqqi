<script setup lang="ts">
import { computed, ref, useId } from 'vue'

defineOptions({ inheritAttrs: false })

const props = withDefaults(
  defineProps<{
    rotulo: string
    erro?: string | null
    dica?: string
    opcional?: boolean
    linhas?: number
    rotuloOculto?: boolean
    maximo?: number
  }>(),
  { linhas: 3 },
)
const modelo = defineModel<string>({ default: '' })
const id = `area-${useId()}`
const descritoPor = computed(() => [props.erro ? `${id}-erro` : '', props.dica ? `${id}-dica` : ''].filter(Boolean).join(' ') || undefined)
const area = ref<HTMLTextAreaElement | null>(null)
defineExpose({ elemento: area })
</script>

<template>
  <div class="flex flex-col gap-1.5" :class="$attrs.class">
    <label :for="id" class="text-sm font-semibold text-texto" :class="{ 'sr-only': rotuloOculto }">
      {{ rotulo }} <span v-if="opcional" class="font-normal text-texto-fraco">(opcional)</span>
    </label>
    <textarea
      :id="id"
      ref="area"
      v-bind="{ ...$attrs, class: undefined }"
      v-model="modelo"
      :rows="linhas"
      :maxlength="maximo"
      :aria-invalid="erro ? 'true' : undefined"
      :aria-describedby="descritoPor"
      class="w-full resize-y rounded-xl border bg-superficie px-3.5 py-2.5 text-[0.95rem] text-texto placeholder:text-texto-fraco/80 transition-colors focus:outline-none focus:ring-3"
      :class="erro ? 'border-erro focus:ring-erro/20' : 'border-borda-forte hover:border-texto-fraco/60 focus:border-marca focus:ring-marca/20'"
    />
    <p v-if="erro" :id="`${id}-erro`" class="text-sm font-medium text-erro">{{ erro }}</p>
    <p v-if="dica" :id="`${id}-dica`" class="text-sm text-texto-fraco">{{ dica }}</p>
  </div>
</template>

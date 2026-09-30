<script setup lang="ts">
import { computed, ref, useId, useSlots } from 'vue'

defineOptions({ inheritAttrs: false })

const props = withDefaults(
  defineProps<{
    rotulo: string
    tipo?: string
    erro?: string | null
    dica?: string
    obrigatorio?: boolean
    opcional?: boolean
    desabilitado?: boolean
    /** Esconde o rótulo visualmente (continua para leitores de tela). */
    rotuloOculto?: boolean
    id?: string
  }>(),
  { tipo: 'text' },
)

const modelo = defineModel<string>({ default: '' })
const slots = useSlots()
const idGerado = useId()
const idCampo = computed(() => props.id ?? `campo-${idGerado}`)
const idDica = computed(() => `${idCampo.value}-dica`)
const idErro = computed(() => `${idCampo.value}-erro`)
const descritoPor = computed(
  () => [props.erro ? idErro.value : null, props.dica || slots.dica ? idDica.value : null].filter(Boolean).join(' ') || undefined,
)
const entrada = ref<HTMLInputElement | null>(null)
defineExpose({ focar: () => entrada.value?.focus() })
</script>

<template>
  <div class="flex flex-col gap-1.5" :class="$attrs.class">
    <label :for="idCampo" class="text-sm font-semibold text-texto" :class="{ 'sr-only': rotuloOculto }">
      {{ rotulo }}
      <span v-if="opcional" class="font-normal text-texto-fraco">(opcional)</span>
    </label>
    <div class="relative flex items-center">
      <span v-if="slots.antes" class="pointer-events-none absolute left-3 flex text-texto-fraco">
        <slot name="antes" />
      </span>
      <input
        :id="idCampo"
        ref="entrada"
        v-bind="{ ...$attrs, class: undefined }"
        v-model="modelo"
        :type="tipo"
        :required="obrigatorio"
        :disabled="desabilitado"
        :aria-invalid="erro ? 'true' : undefined"
        :aria-describedby="descritoPor"
        class="h-11 w-full rounded-xl border bg-superficie px-3.5 text-[0.95rem] text-texto placeholder:text-texto-fraco/80 transition-colors focus:outline-none focus-visible:outline-none focus:ring-3 disabled:cursor-not-allowed disabled:bg-superficie-2 disabled:text-texto-fraco"
        :class="[
          erro ? 'border-erro focus:ring-erro/20' : 'border-borda-forte hover:border-texto-fraco/60 focus:border-marca focus:ring-marca/20',
          slots.antes ? 'pl-10' : '',
          slots.depois ? 'pr-12' : '',
        ]"
      />
      <span v-if="slots.depois" class="absolute right-1.5 flex">
        <slot name="depois" />
      </span>
    </div>
    <p v-if="erro" :id="idErro" class="text-sm font-medium text-erro">{{ erro }}</p>
    <div v-if="dica || slots.dica" :id="idDica" class="text-sm text-texto-fraco">
      <slot name="dica">{{ dica }}</slot>
    </div>
  </div>
</template>

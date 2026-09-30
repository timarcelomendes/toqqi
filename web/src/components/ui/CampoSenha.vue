<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { Eye, EyeOff } from 'lucide-vue-next'
import type { RegrasSenha as TipoRegras } from '@/api/tipos'
import { useRegrasSenha } from '@/composables/regrasSenha'
import { senhaValida } from '@/utils/senha'
import Campo from './Campo.vue'
import RegrasSenha from './RegrasSenha.vue'

const props = withDefaults(
  defineProps<{
    rotulo?: string
    erro?: string | null
    dica?: string
    /** Mostra a lista de regras (use em "criar/trocar senha", não no login). */
    comRegras?: boolean
    /** Regras fixas (testes); se não vier, busca na API. */
    regras?: TipoRegras
    autocomplete?: string
    obrigatorio?: boolean
  }>(),
  { rotulo: 'Senha', autocomplete: 'current-password', obrigatorio: true },
)

const modelo = defineModel<string>({ default: '' })
/** true quando a senha cumpre todas as regras. */
const valida = defineModel<boolean>('valida', { default: false })
const visivel = ref(false)
const regrasApi = props.regras || !props.comRegras ? null : useRegrasSenha()
const regrasAtuais = computed<TipoRegras | null>(() => props.regras ?? regrasApi?.value ?? null)

watch(
  [modelo, regrasAtuais],
  () => {
    valida.value = regrasAtuais.value ? senhaValida(modelo.value, regrasAtuais.value) : modelo.value.length > 0
  },
  { immediate: true },
)
</script>

<template>
  <div class="flex flex-col gap-2">
    <Campo
      v-model="modelo"
      :rotulo="rotulo"
      :tipo="visivel ? 'text' : 'password'"
      :erro="erro"
      :dica="dica"
      :obrigatorio="obrigatorio"
      :autocomplete="autocomplete"
      autocapitalize="off"
      spellcheck="false"
    >
      <template #depois>
        <button
          type="button"
          class="flex size-9 items-center justify-center rounded-lg text-texto-fraco hover:bg-superficie-2 hover:text-texto"
          :aria-label="visivel ? 'Esconder senha' : 'Mostrar senha'"
          :aria-pressed="visivel"
          @click="visivel = !visivel"
        >
          <EyeOff v-if="visivel" class="size-5" aria-hidden="true" />
          <Eye v-else class="size-5" aria-hidden="true" />
        </button>
      </template>
    </Campo>
    <RegrasSenha v-if="comRegras && regrasAtuais" :senha="modelo" :regras="regrasAtuais" />
  </div>
</template>

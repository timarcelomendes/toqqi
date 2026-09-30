<script setup lang="ts">
import { computed } from 'vue'
import { Check, Circle, X } from 'lucide-vue-next'
import type { RegrasSenha } from '@/api/tipos'
import { verificarSenha } from '@/utils/senha'

const props = defineProps<{ senha: string; regras: RegrasSenha; id?: string }>()
const itens = computed(() => verificarSenha(props.senha, props.regras))
</script>

<template>
  <ul :id="id" class="grid gap-1 text-sm sm:grid-cols-2" aria-label="Regras da senha">
    <li
      v-for="item in itens"
      :key="item.chave"
      class="flex items-center gap-2"
      :class="item.ok ? 'text-sucesso' : senha && item.chave === 'maximo' ? 'text-erro' : 'text-texto-fraco'"
      :data-regra="item.chave"
      :data-ok="item.ok"
    >
      <Check v-if="item.ok" class="size-4 shrink-0" aria-hidden="true" />
      <X v-else-if="item.chave === 'maximo'" class="size-4 shrink-0" aria-hidden="true" />
      <Circle v-else class="size-3.5 shrink-0 mx-[1px]" aria-hidden="true" />
      <span>{{ item.rotulo }}<span class="sr-only">{{ item.ok ? ': ok' : ': falta' }}</span></span>
    </li>
  </ul>
</template>

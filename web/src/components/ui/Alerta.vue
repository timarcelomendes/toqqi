<script setup lang="ts">
import { AlertTriangle, CheckCircle2, Info, XCircle } from 'lucide-vue-next'

const props = withDefaults(defineProps<{ tom?: 'sucesso' | 'erro' | 'atencao' | 'info'; titulo?: string }>(), { tom: 'info' })
const icones = { sucesso: CheckCircle2, erro: XCircle, atencao: AlertTriangle, info: Info }
const cores = {
  sucesso: 'bg-sucesso-suave border-sucesso/25 text-sucesso',
  erro: 'bg-erro-suave border-erro/25 text-erro',
  atencao: 'bg-atencao-suave border-atencao/25 text-atencao',
  info: 'bg-info-suave border-info/25 text-info',
}
</script>

<template>
  <div :role="props.tom === 'erro' ? 'alert' : 'status'" class="flex gap-3 rounded-xl border p-3.5 text-sm" :class="cores[tom]">
    <component :is="icones[tom]" class="mt-0.5 size-5 shrink-0" aria-hidden="true" />
    <div class="min-w-0 flex-1">
      <p v-if="titulo" class="font-semibold">{{ titulo }}</p>
      <div class="text-texto-suave [&_a]:text-marca-texto"><slot /></div>
    </div>
  </div>
</template>

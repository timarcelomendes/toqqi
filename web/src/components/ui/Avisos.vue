<script setup lang="ts">
import { AlertTriangle, CheckCircle2, Info, X, XCircle } from 'lucide-vue-next'
import { avisos, fecharAviso, type Aviso, type TipoAviso } from '@/composables/avisos'

const icones = { sucesso: CheckCircle2, erro: XCircle, atencao: AlertTriangle, info: Info }
const cores: Record<TipoAviso, string> = {
  sucesso: 'text-sucesso',
  erro: 'text-erro',
  atencao: 'text-atencao',
  info: 'text-info',
}

function executar(a: Aviso) {
  fecharAviso(a.id)
  a.acao?.executar()
}
</script>

<template>
  <div
    class="pointer-events-none fixed inset-x-0 bottom-0 z-[60] flex flex-col items-center gap-2 p-4 sm:bottom-auto sm:left-auto sm:right-0 sm:top-0 sm:items-end"
    aria-live="polite"
    aria-relevant="additions"
  >
    <TransitionGroup
      enter-from-class="opacity-0 translate-y-2"
      enter-active-class="transition duration-200"
      leave-active-class="transition duration-150"
      leave-to-class="opacity-0"
    >
      <div
        v-for="a in avisos"
        :key="a.id"
        :role="a.tipo === 'erro' ? 'alert' : 'status'"
        class="pointer-events-auto flex w-full max-w-sm items-start gap-3 rounded-xl border border-borda bg-superficie p-4 shadow-lg"
      >
        <component :is="icones[a.tipo]" class="mt-0.5 size-5 shrink-0" :class="cores[a.tipo]" aria-hidden="true" />
        <div class="min-w-0 flex-1 text-sm">
          <p v-if="a.titulo" class="font-semibold text-texto">{{ a.titulo }}</p>
          <p class="text-texto-suave">{{ a.mensagem }}</p>
          <button v-if="a.acao" type="button" class="link mt-2" data-acao-aviso @click="executar(a)">{{ a.acao.rotulo }}</button>
        </div>
        <button
          type="button"
          class="-m-1 flex size-7 shrink-0 items-center justify-center rounded-md text-texto-fraco hover:bg-superficie-2 hover:text-texto"
          aria-label="Fechar aviso"
          @click="fecharAviso(a.id)"
        >
          <X class="size-4" aria-hidden="true" />
        </button>
      </div>
    </TransitionGroup>
  </div>
</template>

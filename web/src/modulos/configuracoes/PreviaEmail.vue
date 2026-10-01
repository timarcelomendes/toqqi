<script setup lang="ts">
// Como o e-mail chega para o cliente (aparência aproximada; o layout final é da plataforma).
import type { CorNota, PreviaEmail } from './mensagens'

defineProps<{ previa: PreviaEmail }>()

const cores: Record<CorNota, string> = {
  vermelho: 'bg-red-600 text-white',
  amarelo: 'bg-amber-400 text-slate-900',
  verde: 'bg-green-600 text-white',
}
</script>

<template>
  <article class="overflow-hidden rounded-2xl border border-borda bg-white text-slate-900 shadow-sm" aria-label="Prévia do e-mail">
    <header class="border-b border-slate-200 bg-slate-50 px-4 py-3 text-sm">
      <p class="truncate text-slate-600"><span class="text-slate-500">De:</span> <strong class="font-semibold text-slate-800">{{ previa.de }}</strong></p>
      <p v-if="previa.responderPara" class="truncate text-slate-600"><span class="text-slate-500">Responder para:</span> {{ previa.responderPara }}</p>
      <p class="mt-1 font-bold text-slate-900" data-teste="assunto">{{ previa.assunto || '(sem assunto)' }}</p>
    </header>
    <div class="flex flex-col gap-3 px-4 py-5 text-[0.95rem] leading-relaxed sm:px-6">
      <p v-for="(p, i) in previa.paragrafos" :key="i" class="whitespace-pre-line">{{ p }}</p>

      <div class="mt-2 rounded-xl bg-slate-50 p-3 sm:p-4" data-teste="bloco-nota">
        <template v-if="previa.bloco.tipo === 'nps'">
          <p class="sr-only">Botões de 0 a 10 para a pessoa escolher a nota: 0 a 6 em vermelho, 7 e 8 em amarelo, 9 e 10 em verde.</p>
          <div class="grid grid-cols-11 gap-1" aria-hidden="true">
            <span
              v-for="b in previa.bloco.botoes"
              :key="b.nota"
              class="flex aspect-square min-w-0 items-center justify-center rounded-md text-xs font-bold sm:text-sm"
              :class="cores[b.cor]"
              :data-cor="b.cor"
            >{{ b.nota }}</span>
          </div>
          <div class="mt-1.5 flex justify-between text-xs text-slate-500" aria-hidden="true">
            <span>{{ previa.bloco.rotuloMin }}</span><span>{{ previa.bloco.rotuloMax }}</span>
          </div>
        </template>
        <template v-else-if="previa.bloco.tipo === 'csat'">
          <p class="sr-only">Botões de 1 a 5 para a pessoa escolher a nota.</p>
          <div class="mx-auto grid max-w-xs grid-cols-5 gap-2" aria-hidden="true">
            <span v-for="b in previa.bloco.botoes" :key="b.nota" class="flex h-10 items-center justify-center rounded-lg font-bold" :class="cores[b.cor]" :data-cor="b.cor">{{ b.nota }}</span>
          </div>
        </template>
        <div v-else class="flex justify-center">
          <span class="rounded-lg bg-slate-900 px-5 py-2.5 text-sm font-bold text-white">{{ previa.bloco.texto }}</span>
        </div>
      </div>
    </div>
    <footer class="border-t border-slate-200 px-4 py-3 text-center text-xs text-slate-500 sm:px-6">
      <p>{{ previa.rodape }}</p>
      <p class="mt-1 underline" data-teste="descadastro">{{ previa.descadastro }}</p>
    </footer>
  </article>
</template>

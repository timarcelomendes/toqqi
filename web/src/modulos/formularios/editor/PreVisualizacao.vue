<script setup lang="ts">
import { ref } from 'vue'
import { RotateCcw } from 'lucide-vue-next'
import type { Pergunta, Tema } from '@/api/tipos'
import Pesquisa from '@/pesquisa/Pesquisa.vue'

defineProps<{ nome: string; perguntas: Pergunta[]; tema: Tema; nomeEmpresa: string }>()
const chave = ref(0)
</script>

<template>
  <div class="flex h-full flex-col overflow-hidden rounded-cartao border border-borda bg-slate-100">
    <div class="flex items-center justify-between gap-2 border-b border-borda bg-superficie px-3 py-2">
      <p class="text-xs font-semibold uppercase tracking-wide text-texto-fraco">Pré-visualização</p>
      <button type="button" class="inline-flex items-center gap-1 rounded-lg px-2 py-1 text-xs font-semibold text-texto-suave hover:bg-superficie-2" @click="chave++">
        <RotateCcw class="size-3.5" aria-hidden="true" /> Recomeçar
      </button>
    </div>
    <div class="flex-1 overflow-y-auto">
      <Pesquisa
        :key="chave"
        :formulario="{ nome, perguntas, tema }"
        :variaveis="{ empresa: nomeEmpresa, nome: 'Maria Souza', assunto: '', referencia: 'Pedido 12345' }"
        previa
      />
    </div>
    <p class="border-t border-borda bg-superficie px-3 py-2 text-xs text-texto-fraco">
      Exemplo com cliente “Maria” e referência “Pedido 12345”. Nada é gravado aqui.
    </p>
  </div>
</template>

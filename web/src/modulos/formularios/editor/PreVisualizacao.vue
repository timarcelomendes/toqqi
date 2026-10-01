<script setup lang="ts">
import { computed, ref } from 'vue'
import { ImageIcon, RotateCcw } from 'lucide-vue-next'
import type { Pergunta, Tema } from '@/api/tipos'
import { useSessaoStore } from '@/stores/sessao'
import { logoParaCliente } from '@/utils/imagens'
import Pesquisa from '@/pesquisa/Pesquisa.vue'

const props = defineProps<{ nome: string; perguntas: Pergunta[]; tema: Tema; nomeEmpresa: string }>()
const sessao = useSessaoStore()
const chave = ref(0)
// Sem logo no formulário, o cliente vê o logo da empresa (a API faz o mesmo na página pública e nos e-mails).
const logo = computed(() => logoParaCliente(props.tema.logo_url, sessao.conta?.logo_url))
const temaPrevia = computed<Tema>(() => ({ ...props.tema, logo_url: logo.value.url }))
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
        :formulario="{ nome, perguntas, tema: temaPrevia }"
        :variaveis="{ empresa: nomeEmpresa, nome: 'Maria Souza', assunto: '', referencia: 'Pedido 12345' }"
        previa
      />
    </div>
    <div class="flex flex-col gap-0.5 border-t border-borda bg-superficie px-3 py-2 text-xs text-texto-fraco">
      <p v-if="logo.daEmpresa" class="flex items-center gap-1.5 font-semibold text-texto-suave" data-aviso-logo>
        <ImageIcon class="size-3.5 shrink-0" aria-hidden="true" /> Usando o logo da empresa
      </p>
      <p>Exemplo com cliente “Maria” e referência “Pedido 12345”. Nada é gravado aqui.</p>
    </div>
  </div>
</template>

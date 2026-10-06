<script setup lang="ts">
// Topo do painel de edição: ícone, o que é o item ("P3 · Comentário") e as ações (duplicar, excluir). O título fica
// focável: ao escolher um item sem campo para focar, o foco vai para ele.
import type { Component } from 'vue'
import { Copy, Trash2 } from 'lucide-vue-next'
import Botao from '@/components/ui/Botao.vue'
import { tecla } from './textos'

defineProps<{ icone: Component; rotulo: string; detalhe?: string; podeEditar: boolean; semDuplicar?: boolean; semExcluir?: boolean }>()
const emit = defineEmits<{ duplicar: []; excluir: [] }>()
</script>

<template>
  <div class="flex items-start gap-3">
    <span class="flex size-10 shrink-0 items-center justify-center rounded-xl bg-marca-suave text-marca-texto" aria-hidden="true">
      <component :is="icone" class="size-5" />
    </span>
    <div class="min-w-0 flex-1">
      <h2 tabindex="-1" class="text-base font-bold text-texto focus:outline-none" data-titulo-edicao>{{ rotulo }}</h2>
      <p v-if="detalhe" class="text-sm text-texto-fraco">{{ detalhe }}</p>
    </div>
    <slot />
    <div v-if="podeEditar" class="flex shrink-0 items-center">
      <Botao v-if="!semDuplicar" variante="fantasma" tamanho="sm" :somente-icone="`Duplicar (${tecla('Ctrl+D')})`" data-duplicar-item @click="emit('duplicar')">
        <Copy class="size-4" aria-hidden="true" />
      </Botao>
      <Botao v-if="!semExcluir" variante="fantasma" tamanho="sm" somente-icone="Excluir" class="hover:text-erro" data-excluir-item @click="emit('excluir')">
        <Trash2 class="size-4" aria-hidden="true" />
      </Botao>
    </div>
  </div>
</template>

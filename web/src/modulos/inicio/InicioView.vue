<script setup lang="ts">
// Início: o Painel para quem tem painel.ver; para os outros, a tela de boas-vindas.
import { defineAsyncComponent } from 'vue'
import { useSessaoStore } from '@/stores/sessao'
import Carregando from '@/components/ui/Carregando.vue'
import BoasVindas from './BoasVindas.vue'

const PainelView = defineAsyncComponent({
  loader: () => import('@/modulos/painel/PainelView.vue'),
  loadingComponent: Carregando,
  delay: 150,
})
const sessao = useSessaoStore()
</script>

<template>
  <PainelView v-if="sessao.pode('painel.ver')" />
  <BoasVindas v-else />
</template>

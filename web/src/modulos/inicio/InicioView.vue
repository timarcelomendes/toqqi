<script setup lang="ts">
// Início: o Painel para quem tem painel.ver; para os outros, a tela de boas-vindas. No teste grátis, antes de
// assinar, quem cuida da assinatura vê também o cartão com os dias que faltam (CartaoTeste).
import { defineAsyncComponent } from 'vue'
import { useSessaoStore } from '@/stores/sessao'
import Carregando from '@/components/ui/Carregando.vue'
import BoasVindas from './BoasVindas.vue'
import CartaoTeste from './CartaoTeste.vue'

const PainelView = defineAsyncComponent({
  loader: () => import('@/modulos/painel/PainelView.vue'),
  loadingComponent: Carregando,
  delay: 150,
})
const sessao = useSessaoStore()
</script>

<template>
  <div>
    <CartaoTeste />
    <PainelView v-if="sessao.pode('painel.ver')" />
    <BoasVindas v-else />
  </div>
</template>

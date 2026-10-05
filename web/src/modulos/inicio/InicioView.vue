<script setup lang="ts">
// Início: o Painel para quem tem painel.ver; para os outros, a tela de boas-vindas. No teste grátis, antes de
// assinar, quem cuida da assinatura vê também o cartão com os dias que faltam (CartaoTeste). Etapa 5h: sem nenhuma
// resposta, o painel vira o "Comece por aqui"; no modo exemplo, a faixa fica no topo, acima de tudo.
import { defineAsyncComponent } from 'vue'
import { useSessaoStore } from '@/stores/sessao'
import Carregando from '@/components/ui/Carregando.vue'
import BoasVindas from './BoasVindas.vue'
import CartaoTeste from './CartaoTeste.vue'
import FaixaExemplo from './FaixaExemplo.vue'
import { usarModoExemplo } from './modoExemplo'

const PainelView = defineAsyncComponent({
  loader: () => import('@/modulos/painel/PainelView.vue'),
  loadingComponent: Carregando,
  delay: 150,
})
const sessao = useSessaoStore()
const { ativo: modoExemplo, desligar: sairDoExemplo } = usarModoExemplo()
</script>

<template>
  <div>
    <FaixaExemplo v-if="modoExemplo && sessao.pode('painel.ver')" @voltar="sairDoExemplo" />
    <CartaoTeste />
    <PainelView v-if="sessao.pode('painel.ver')" />
    <BoasVindas v-else />
  </div>
</template>

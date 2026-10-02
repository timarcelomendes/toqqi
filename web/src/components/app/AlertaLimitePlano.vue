<script setup lang="ts">
// Limite de contatos do plano (402 `limite_do_plano`) ao criar, importar ou reativar contatos. Quem cuida da
// assinatura vê "Ver planos" (leva para Assinatura); os outros, que precisam falar com o administrador.
import { computed } from 'vue'
import { ArrowRight } from 'lucide-vue-next'
import { useSessaoStore } from '@/stores/sessao'
import Alerta from '@/components/ui/Alerta.vue'

defineProps<{ mensagem?: string | null }>()
const sessao = useSessaoStore()
const podeAssinar = computed(() => sessao.pode('assinatura.gerenciar'))
</script>

<template>
  <Alerta tom="atencao" titulo="Você chegou ao limite do seu plano" data-limite-plano>
    <p>
      {{ mensagem || 'Seu plano não permite mais contatos ativos.' }}
      <template v-if="podeAssinar">Para cadastrar mais, troque para um plano maior ou desative contatos que não usa mais.</template>
      <template v-else>Para cadastrar mais, desative contatos que não usa mais ou peça ao administrador da conta para trocar de plano.</template>
    </p>
    <RouterLink v-if="podeAssinar" to="/assinatura" class="link mt-2 inline-flex min-h-8 items-center gap-1 font-semibold">
      Ver planos <ArrowRight class="size-4" aria-hidden="true" />
    </RouterLink>
  </Alerta>
</template>

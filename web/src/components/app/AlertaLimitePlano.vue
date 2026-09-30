<script setup lang="ts">
import Alerta from '@/components/ui/Alerta.vue'

defineProps<{ mensagem?: string | null }>()
</script>

<template>
  <Alerta tom="atencao" titulo="Você chegou ao limite do seu plano">
    {{ mensagem || 'Seu plano não permite mais contatos ativos.' }}
    Para cadastrar mais, <RouterLink to="/assinatura" class="link">veja as opções de plano</RouterLink>
    ou desative contatos que não usa mais.
  </Alerta>
</template>

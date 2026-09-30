<script setup lang="ts">
import Avisos from '@/components/ui/Avisos.vue'
import DialogoConfirmacao from '@/components/ui/DialogoConfirmacao.vue'
</script>

<template>
  <RouterView />
  <Avisos />
  <DialogoConfirmacao />
</template>

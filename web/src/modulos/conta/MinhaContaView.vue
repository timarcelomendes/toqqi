<script setup lang="ts">
import CabecalhoPagina from '@/components/app/CabecalhoPagina.vue'
import SecaoAparelhos from './SecaoAparelhos.vue'
import SecaoPerfil from './SecaoPerfil.vue'
import SecaoSenha from './SecaoSenha.vue'
import { ref } from 'vue'

const aparelhos = ref<InstanceType<typeof SecaoAparelhos> | null>(null)
</script>

<template>
  <CabecalhoPagina titulo="Minha conta" descricao="Seus dados, sua senha e os aparelhos onde você está conectado." />
  <div class="flex flex-col gap-6">
    <SecaoPerfil />
    <SecaoSenha @trocou="aparelhos?.carregar()" />
    <SecaoAparelhos ref="aparelhos" />
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useSessaoStore } from '@/stores/sessao'
import CabecalhoPagina from '@/components/app/CabecalhoPagina.vue'
import SecaoAparelhos from './SecaoAparelhos.vue'
import SecaoEmails from './SecaoEmails.vue'
import SecaoPerfil from './SecaoPerfil.vue'
import SecaoPrivacidade from './SecaoPrivacidade.vue'
import SecaoSenha from './SecaoSenha.vue'

const sessao = useSessaoStore()
const aparelhos = ref<InstanceType<typeof SecaoAparelhos> | null>(null)
</script>

<template>
  <CabecalhoPagina titulo="Minha conta" descricao="Seus dados, sua senha, os e-mails que você recebe, os aparelhos onde você está conectado e a privacidade." />
  <div class="flex flex-col gap-6">
    <SecaoPerfil />
    <!-- Resumo semanal e alertas: só para quem acompanha o painel -->
    <SecaoEmails v-if="sessao.pode('painel.ver')" />
    <SecaoSenha @trocou="aparelhos?.carregar()" />
    <SecaoAparelhos ref="aparelhos" />
    <SecaoPrivacidade />
  </div>
</template>

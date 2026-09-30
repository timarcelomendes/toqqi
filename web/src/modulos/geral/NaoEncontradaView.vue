<script setup lang="ts">
import { useSessaoStore } from '@/stores/sessao'
import Marca from '@/components/app/Marca.vue'
import Botao from '@/components/ui/Botao.vue'

const sessao = useSessaoStore()
</script>

<template>
  <main id="conteudo" class="flex min-h-dvh flex-col items-center justify-center px-4 text-center">
    <Marca tamanho="lg" />
    <p class="mt-10 text-7xl font-extrabold tracking-tight text-marca">404</p>
    <h1 class="mt-3 text-2xl font-bold text-texto">Essa página não existe</h1>
    <p class="mt-2 max-w-md text-texto-suave">O endereço pode estar errado ou a página mudou de lugar.</p>
    <Botao :para="sessao.logado ? '/inicio' : '/entrar'" tamanho="lg" class="mt-8">
      {{ sessao.logado ? 'Voltar para o início' : 'Ir para Entrar' }}
    </Botao>
  </main>
</template>

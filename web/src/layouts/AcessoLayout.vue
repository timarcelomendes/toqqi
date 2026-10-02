<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import BotaoTema from '@/components/app/BotaoTema.vue'
import Marca from '@/components/app/Marca.vue'

const rota = useRoute()
const largo = computed(() => rota.name === 'termos' || rota.name === 'privacidade')
const medio = computed(() => rota.name === 'aceite')
</script>

<template>
  <div class="relative flex min-h-dvh flex-col overflow-hidden">
    <!-- Fundo decorativo -->
    <div aria-hidden="true" class="pointer-events-none absolute inset-0 -z-10">
      <div class="absolute -top-40 left-1/2 h-[28rem] w-[48rem] -translate-x-1/2 rounded-full bg-coral-400/15 blur-3xl dark:bg-coral-500/10" />
      <div class="absolute -bottom-40 -right-20 h-80 w-80 rounded-full bg-coral-200/30 blur-3xl dark:bg-coral-800/15" />
    </div>

    <header class="flex items-center justify-between px-4 py-4 sm:px-8">
      <RouterLink to="/" class="rounded-lg" aria-label="Toqqi, página inicial"><Marca /></RouterLink>
      <BotaoTema />
    </header>

    <main id="conteudo" class="flex flex-1 items-start justify-center px-4 pb-10 pt-4 sm:items-center sm:pt-0">
      <div class="w-full" :class="largo ? 'max-w-3xl' : medio ? 'max-w-lg' : 'max-w-md'">
        <div class="cartao p-6 sm:p-8">
          <RouterView />
        </div>
      </div>
    </main>

    <footer class="flex flex-wrap items-center justify-center gap-x-4 gap-y-1 px-4 pb-6 text-sm text-texto-fraco">
      <span>© {{ new Date().getFullYear() }} Toqqi</span>
      <RouterLink to="/termos" class="hover:text-texto hover:underline">Termos de uso</RouterLink>
      <RouterLink to="/privacidade" class="hover:text-texto hover:underline">Privacidade</RouterLink>
    </footer>
  </div>
</template>

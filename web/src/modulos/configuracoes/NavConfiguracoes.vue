<script setup lang="ts">
// Seções de Configurações (Segurança, Envios, Planos de ação), mostradas conforme o perfil.
import { computed } from 'vue'
import { ClipboardList, Send, ShieldCheck } from 'lucide-vue-next'
import { useSessaoStore } from '@/stores/sessao'

const sessao = useSessaoStore()
const secoes = computed(() =>
  [
    { rotulo: 'Segurança', para: '/configuracoes/seguranca', icone: ShieldCheck, pode: sessao.pode('configuracoes.gerenciar') },
    { rotulo: 'Envios', para: '/configuracoes/envios', icone: Send, pode: sessao.pode('envios.ver') },
    { rotulo: 'Planos de ação', para: '/configuracoes/acoes', icone: ClipboardList, pode: sessao.pode('acoes.ver') },
  ].filter((s) => s.pode),
)
</script>

<template>
  <nav aria-label="Seções de configurações" class="mb-5 flex flex-wrap items-center gap-1.5">
    <span class="mr-1 text-sm text-texto-fraco">Configurações:</span>
    <RouterLink
      v-for="s in secoes"
      :key="s.para"
      v-slot="{ href, navigate, isActive }"
      :to="s.para"
      custom
    >
      <a
        :href="href"
        :aria-current="isActive ? 'page' : undefined"
        class="inline-flex h-10 items-center gap-1.5 rounded-xl px-3 text-sm font-semibold transition-colors"
        :class="isActive ? 'bg-marca-suave text-marca-texto' : 'text-texto-suave hover:bg-superficie-2 hover:text-texto'"
        @click="navigate"
      >
        <component :is="s.icone" class="size-4" aria-hidden="true" /> {{ s.rotulo }}
      </a>
    </RouterLink>
  </nav>
</template>

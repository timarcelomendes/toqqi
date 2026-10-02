<script setup lang="ts">
// Um trecho de texto dos documentos legais: string, ou pedaços com links. Sem v-html: tudo vira texto ou link.
// Link interno ("/termos", "/privacidade#cookies") usa RouterLink; e-mail ("mailto:") e outro site usam <a>.
import { computed } from 'vue'
import type { Texto } from './tipos'
import { tipoDeLink } from './documento'

const props = defineProps<{ texto: Texto }>()
const pedacos = computed(() => (typeof props.texto === 'string' ? [props.texto] : props.texto))
</script>

<template>
  <template v-for="(p, i) in pedacos" :key="i">
    <template v-if="typeof p === 'string'">{{ p }}</template>
    <RouterLink v-else-if="tipoDeLink(p.href) === 'interno'" :to="p.href" class="link">{{ p.texto }}</RouterLink>
    <a v-else-if="tipoDeLink(p.href) === 'email'" :href="p.href" class="link break-words">{{ p.texto }}</a>
    <a v-else-if="tipoDeLink(p.href) === 'externo'" :href="p.href" target="_blank" rel="noopener noreferrer" class="link break-words"
      >{{ p.texto }}<span class="sr-only"> (abre em nova aba)</span></a
    >
    <template v-else>{{ p.texto }}</template>
  </template>
</template>

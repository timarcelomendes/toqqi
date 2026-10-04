<script setup lang="ts">
// Chamada para uma jornada no topo de um tópico da Ajuda (docs/ajuda-jornadas.md §3): aparece no tópico "dono" (o do
// primeiro "Saiba mais" da jornada), com "Jornada · <título>", o objetivo e "Ver a jornada →", que leva ao cartão dela
// em /ajuda/jornadas (rola e põe o foco no título).
import { ArrowRight, Route } from 'lucide-vue-next'
import type { JornadaAjuda } from '@/api/tipos'
import { abrirAncora, destinoJornada } from './ancora'

defineProps<{ jornada: JornadaAjuda }>()
</script>

<template>
  <div
    class="flex items-start gap-3.5 rounded-cartao border border-marca/25 bg-marca-suave p-4 sm:items-center sm:gap-4 sm:p-5"
    :data-chamada-jornada="jornada.id"
  >
    <span class="flex size-9 shrink-0 items-center justify-center rounded-full bg-superficie text-marca-texto ring-1 ring-inset ring-marca/25" aria-hidden="true">
      <Route class="size-[1.125rem]" />
    </span>
    <div class="flex min-w-0 flex-1 flex-col gap-2 sm:flex-row sm:items-center sm:justify-between sm:gap-6">
      <div class="min-w-0">
        <!-- "Jornada · <título>" (o leitor de tela ouve "Jornada: <título>") -->
        <p class="break-words text-texto" data-chamada-titulo>
          <span class="text-xs font-semibold uppercase tracking-wider text-marca-texto">Jornada</span><span class="sr-only">:</span>{{ ' ' }}<span
            class="mx-0.5 text-texto-fraco"
            aria-hidden="true"
            >·</span
          >{{ ' ' }}<strong class="font-bold">{{ jornada.titulo }}</strong>
        </p>
        <p v-if="jornada.objetivo" class="mt-0.5 break-words text-sm text-texto-suave">{{ jornada.objetivo }}</p>
      </div>
      <RouterLink v-slot="{ href, navigate }" :to="destinoJornada(jornada.id)" custom>
        <a
          :href="href"
          class="link inline-flex shrink-0 items-center gap-1 self-start whitespace-nowrap text-sm sm:self-auto"
          data-ver-jornada
          @click="(e: MouseEvent) => abrirAncora(navigate, e, jornada.id)"
        >
          Ver a jornada<span class="sr-only">: {{ jornada.titulo }}</span>
          <ArrowRight class="size-4" aria-hidden="true" />
        </a>
      </RouterLink>
    </div>
  </div>
</template>

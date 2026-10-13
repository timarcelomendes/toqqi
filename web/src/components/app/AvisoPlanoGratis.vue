<script setup lang="ts">
// Plano Grátis (docs/api-plano-gratis.md): o que não faz parte do Grátis, na tela onde ele estaria (Equipe,
// Integrações, Formulários, Configurações de envio). O texto diz o que muda; embaixo, "Disponível a partir do plano
// Essencial." e "Ver planos" para quem cuida da assinatura (os outros leem que é com o administrador).
import { computed } from 'vue'
import { ArrowRight, Lock } from 'lucide-vue-next'
import { useSessaoStore } from '@/stores/sessao'
import { MSG_RECURSO, ROTA_PLANOS } from '@/modulos/assinatura/gratis'

withDefaults(defineProps<{ titulo?: string; texto: string; recurso?: boolean }>(), { titulo: 'Plano Grátis', recurso: true })
const sessao = useSessaoStore()
const podeAssinar = computed(() => sessao.pode('assinatura.gerenciar'))
</script>

<template>
  <div role="status" class="flex gap-3 rounded-xl border border-borda-forte bg-superficie-2 p-3.5 text-sm" data-aviso-plano-gratis>
    <Lock class="mt-0.5 size-5 shrink-0 text-texto-suave" aria-hidden="true" />
    <div class="min-w-0 flex-1">
      <p class="font-semibold text-texto">{{ titulo }}</p>
      <p class="text-texto-suave">
        {{ texto }}
        <template v-if="recurso">{{ MSG_RECURSO }}</template>
        <template v-if="!podeAssinar"> Fale com o administrador da conta.</template>
      </p>
      <RouterLink v-if="podeAssinar" :to="ROTA_PLANOS" class="link mt-2 inline-flex min-h-8 items-center gap-1 font-semibold" data-ver-planos>
        Ver planos <ArrowRight class="size-4" aria-hidden="true" />
      </RouterLink>
    </div>
  </div>
</template>

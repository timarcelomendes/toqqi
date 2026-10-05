<script setup lang="ts">
// A faixa do modo exemplo (etapa 5h, docs/api-etapa-5h.md §1): fica presa no topo do conteúdo (abaixo da barra do app)
// enquanto o Início mostra dados de exemplo, explica que os botões do painel não funcionam e tem a volta para os dados
// da conta. Recebe o foco ao aparecer, para quem usa leitor de tela saber que a tela mudou. No celular, compacta: a
// explicação fica só para o leitor de tela e o botão desce para a linha de baixo.
import { nextTick, onMounted, ref } from 'vue'
import { ArrowLeft, FlaskConical } from 'lucide-vue-next'
import Botao from '@/components/ui/Botao.vue'

const emit = defineEmits<{ voltar: [] }>()
const titulo = ref<HTMLElement | null>(null)

onMounted(async () => {
  await nextTick()
  titulo.value?.focus()
})
</script>

<template>
  <div
    class="sticky top-16 z-20 -mx-4 -mt-6 mb-5 border-b border-info/25 bg-info-suave/95 px-4 py-2.5 backdrop-blur sm:-mx-6 sm:-mt-8 sm:mb-6 sm:px-6 lg:-mx-10 lg:px-10"
    role="region"
    aria-label="Modo exemplo"
    data-faixa-exemplo
  >
    <div class="flex flex-col gap-2 sm:flex-row sm:items-center sm:gap-4">
      <div class="flex min-w-0 flex-1 items-center gap-3">
        <span class="flex size-8 shrink-0 items-center justify-center rounded-lg bg-superficie text-info" aria-hidden="true">
          <FlaskConical class="size-4" />
        </span>
        <p ref="titulo" tabindex="-1" class="min-w-0 flex-1 text-sm text-texto focus:outline-none">
          <strong class="font-bold">Você está vendo dados de exemplo.</strong>
          <span class="sr-only text-texto-suave sm:not-sr-only"> Nada disso está na sua conta e os botões do painel ficam desligados.</span>
        </p>
      </div>
      <Botao variante="secundario" tamanho="sm" class="!h-9 self-start sm:self-auto" data-voltar-exemplo @click="emit('voltar')">
        <ArrowLeft class="size-4" aria-hidden="true" /> Voltar para os meus dados
      </Botao>
    </div>
  </div>
</template>

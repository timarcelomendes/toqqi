<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { RouterLink, useRoute, useRouter } from 'vue-router'
import { ChevronDown, CreditCard, LogOut, Menu, UserRound, X } from 'lucide-vue-next'
import { useSessaoStore } from '@/stores/sessao'
import { useAssistenteStore } from '@/stores/assistente'
import { useFocoPreso } from '@/composables/focoPreso'
import { useMenuLateral } from '@/composables/menuLateral'
import { seloDoTeste } from '@/modulos/assinatura/logica'
import { iniciais, PERFIS } from '@/utils/rotulos'
import AvisoCobranca from '@/components/app/AvisoCobranca.vue'
import BotaoTema from '@/components/app/BotaoTema.vue'
import ItemMenu from '@/components/app/ItemMenu.vue'
import MenuSuspenso from '@/components/ui/MenuSuspenso.vue'
import AssistenteFlutuante from '@/modulos/assistente/AssistenteFlutuante.vue'
import ModalFeedback from '@/modulos/feedback/ModalFeedback.vue'
import BarraLateral from './BarraLateral.vue'

const sessao = useSessaoStore()
const assistente = useAssistenteStore()
const router = useRouter()
const rota = useRoute()
const { recolhido } = useMenuLateral()

const gavetaAberta = ref(false)
const gaveta = ref<HTMLElement | null>(null)
useFocoPreso(gaveta, gavetaAberta, () => (gavetaAberta.value = false))
watch(() => rota.fullPath, () => (gavetaAberta.value = false))
watch(gavetaAberta, (v) => (document.body.style.overflow = v ? 'hidden' : ''))

// Relógio de minuto em minuto: o selo do teste muda para "encerrado" na hora do fim, não só no dia seguinte.
const agora = ref(Date.now())
let relogio: ReturnType<typeof setInterval> | undefined

/** Selo do teste no cabeçalho, pela data e hora do fim (o último dia é o de São Paulo, como a API). Quem cuida da
 * assinatura clica e vai à tela de Assinatura ("Escolher plano" até assinar). */
const teste = computed(() => seloDoTeste(sessao.conta, sessao.pode('assinatura.gerenciar'), new Date(agora.value)))

/** A aba voltou a ficar visível: busca a sessão de novo, no máximo a cada 3 minutos (aviso do topo, envios). */
function aoVoltarParaAba() {
  if (document.visibilityState !== 'visible') return
  agora.value = Date.now()
  sessao.recarregarSeAntiga()
}

onMounted(() => {
  relogio = setInterval(() => (agora.value = Date.now()), 60_000)
  document.addEventListener('visibilitychange', aoVoltarParaAba)
})
onBeforeUnmount(() => {
  clearInterval(relogio)
  document.removeEventListener('visibilitychange', aoVoltarParaAba)
})

async function sair() {
  await sessao.sair()
  router.push({ name: 'entrar' })
}
</script>

<template>
  <div
    class="min-h-dvh transition-[padding] duration-200 motion-reduce:transition-none"
    :class="recolhido ? 'lg:pl-[4.5rem]' : 'lg:pl-64'"
  >
    <a href="#conteudo" class="sr-only z-[70] rounded-lg bg-superficie px-4 py-2 font-semibold focus:not-sr-only focus:fixed focus:left-4 focus:top-4">
      Pular para o conteúdo
    </a>

    <!-- Barra lateral (computador) -->
    <aside
      class="fixed inset-y-0 left-0 z-[35] hidden border-r border-borda bg-superficie transition-[width] duration-200 motion-reduce:transition-none lg:block"
      :class="recolhido ? 'w-[4.5rem]' : 'w-64'"
    >
      <BarraLateral recolhivel />
    </aside>

    <!-- Gaveta (celular) -->
    <div v-if="gavetaAberta" class="fixed inset-0 z-50 lg:hidden">
      <div class="absolute inset-0 bg-slate-950/50" aria-hidden="true" @click="gavetaAberta = false" />
      <div
        ref="gaveta"
        role="dialog"
        aria-modal="true"
        aria-label="Menu"
        tabindex="-1"
        class="relative h-full w-72 max-w-[85vw] bg-superficie shadow-2xl animate-deslizar focus:outline-none"
      >
        <button
          type="button"
          class="absolute right-3 top-3 z-10 flex size-10 items-center justify-center rounded-xl text-texto-suave hover:bg-superficie-2"
          aria-label="Fechar menu"
          @click="gavetaAberta = false"
        >
          <X class="size-5" aria-hidden="true" />
        </button>
        <BarraLateral @navegou="gavetaAberta = false" />
      </div>
    </div>

    <!-- Barra superior -->
    <header class="sticky top-0 z-30 flex h-16 items-center gap-2 border-b border-borda bg-superficie/85 px-3 backdrop-blur sm:px-6">
      <button
        type="button"
        class="flex size-10 items-center justify-center rounded-xl text-texto-suave hover:bg-superficie-2 lg:hidden"
        aria-label="Abrir menu"
        :aria-expanded="gavetaAberta"
        @click="gavetaAberta = true"
      >
        <Menu class="size-5" aria-hidden="true" />
      </button>
      <p class="min-w-0 truncate text-sm font-semibold text-texto-suave">{{ sessao.conta?.nome }}</p>
      <div class="flex-1" />
      <component
        :is="teste.link ? RouterLink : 'p'"
        v-if="teste"
        v-bind="teste.link ? { to: '/assinatura', 'aria-label': teste.convite ? `${teste.texto}. ${teste.convite}` : teste.texto } : {}"
        class="shrink-0 rounded-full bg-marca-suave px-3 py-1 text-xs font-semibold text-marca-texto"
        :class="teste.link ? 'hover:bg-coral-100 dark:hover:bg-coral-900/40' : ''"
        :title="teste.titulo"
        data-selo-teste
      >
        <span class="sm:hidden">{{ teste.curto }}</span>
        <span class="hidden sm:inline">{{ teste.texto }}</span>
        <span v-if="teste.convite" class="hidden sm:inline"> · <span class="underline underline-offset-2">{{ teste.convite }}</span></span>
      </component>
      <BotaoTema />
      <MenuSuspenso rotulo="Menu da sua conta">
        <template #gatilho="{ props }">
          <button
            type="button"
            v-bind="props"
            class="flex items-center gap-2 rounded-xl p-1 pr-2 hover:bg-superficie-2"
          >
            <span class="flex size-8 items-center justify-center rounded-full bg-marca-forte text-xs font-bold text-white" aria-hidden="true">
              {{ iniciais(sessao.usuario?.nome) }}
            </span>
            <span class="hidden max-w-40 truncate text-sm font-semibold text-texto md:block">{{ sessao.usuario?.nome }}</span>
            <ChevronDown class="size-4 text-texto-fraco" aria-hidden="true" />
          </button>
        </template>
        <div class="border-b border-borda px-3 pb-2.5 pt-1.5" role="none">
          <p class="truncate text-sm font-semibold text-texto">{{ sessao.usuario?.nome }}</p>
          <p class="truncate text-xs text-texto-fraco">{{ sessao.usuario?.email }}</p>
          <p v-if="sessao.usuario" class="mt-1 text-xs text-texto-fraco">{{ PERFIS[sessao.usuario.perfil]?.rotulo }}</p>
        </div>
        <div class="pt-1.5" role="none">
          <ItemMenu para="/minha-conta" :icone="UserRound">Minha conta</ItemMenu>
          <ItemMenu v-if="sessao.pode('assinatura.gerenciar')" para="/assinatura" :icone="CreditCard">Assinatura</ItemMenu>
          <ItemMenu :icone="LogOut" perigo @click="sair">Sair</ItemMenu>
        </div>
      </MenuSuspenso>
    </header>

    <!-- Etapa 5a: teste acabando, fatura atrasada, envios pausados... (conta.cobranca.aviso) -->
    <AvisoCobranca />

    <!-- Com o botão do assistente no canto, o fim do conteúdo ganha folga para ele não cobrir a última ação. -->
    <!-- Etapa 5l: telas com `larguraTotal` (o editor de formulário, em 3 colunas) usam a largura toda. -->
    <main
      id="conteudo"
      tabindex="-1"
      class="mx-auto w-full px-4 py-6 focus:outline-none sm:px-6 sm:py-8"
      :class="[rota.meta.larguraTotal ? 'max-w-none lg:px-6' : 'max-w-6xl lg:px-10', assistente.visivel ? 'pb-24 sm:pb-28 print:pb-6' : '']"
    >
      <!-- O editor de formulário guarda o documento por id: de um formulário direto para outro, monta de novo. -->
      <RouterView v-slot="{ Component, route: atual }">
        <component :is="Component" :key="atual.name === 'formulario' ? `formulario-${String(atual.params.id)}` : undefined" />
      </RouterView>
    </main>

    <!-- Etapa 5b: botão do assistente (canto inferior direito) e o painel da conversa -->
    <AssistenteFlutuante />

    <!-- Feedback: a janela "Enviar feedback" (aberta pelo menu e pelas telas de feedback) -->
    <ModalFeedback />
  </div>
</template>

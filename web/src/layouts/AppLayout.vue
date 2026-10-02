<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ChevronDown, CreditCard, LogOut, Menu, UserRound, X } from 'lucide-vue-next'
import { useSessaoStore } from '@/stores/sessao'
import { useFocoPreso } from '@/composables/focoPreso'
import { useMenuLateral } from '@/composables/menuLateral'
import { formatarData, diasAte } from '@/utils/datas'
import { testeValendo, ultimoDiaDoTeste } from '@/modulos/assinatura/logica'
import { iniciais, PERFIS } from '@/utils/rotulos'
import AvisoCobranca from '@/components/app/AvisoCobranca.vue'
import BotaoTema from '@/components/app/BotaoTema.vue'
import ItemMenu from '@/components/app/ItemMenu.vue'
import MenuSuspenso from '@/components/ui/MenuSuspenso.vue'
import BarraLateral from './BarraLateral.vue'

const sessao = useSessaoStore()
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

/** Selo do teste no cabeçalho, pela data e hora do fim (o último dia é o de São Paulo, como a API). */
const teste = computed(() => {
  const c = sessao.conta
  if (!c || c.situacao !== 'teste' || !c.teste_ate) return null
  const ultimo = ultimoDiaDoTeste(c.teste_ate)
  if (!testeValendo(c.teste_ate, new Date(agora.value))) return { data: formatarData(ultimo), dias: -1 }
  return { data: formatarData(ultimo), dias: diasAte(ultimo) }
})

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
      <p
        v-if="teste"
        class="hidden rounded-full bg-marca-suave px-3 py-1 text-xs font-semibold text-marca-texto sm:block"
        :title="`Teste grátis até ${teste.data}`"
      >
        <template v-if="teste.dias !== null && teste.dias >= 0">
          Teste grátis: {{ teste.dias === 0 ? 'termina hoje' : teste.dias === 1 ? 'falta 1 dia' : `faltam ${teste.dias} dias` }}
        </template>
        <template v-else>Teste grátis encerrado em {{ teste.data }}</template>
      </p>
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

    <main id="conteudo" tabindex="-1" class="mx-auto w-full max-w-6xl px-4 py-6 focus:outline-none sm:px-6 sm:py-8 lg:px-10">
      <RouterView />
    </main>
  </div>
</template>

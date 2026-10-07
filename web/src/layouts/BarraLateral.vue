<script setup lang="ts">
import { computed, watch } from 'vue'
import { useRoute } from 'vue-router'
import { MessageSquareHeart, PanelLeftClose, PanelLeftOpen } from 'lucide-vue-next'
import { useSessaoStore } from '@/stores/sessao'
import { useMenuLateral } from '@/composables/menuLateral'
import { textoPedidos, usarPedidosAcesso } from '@/composables/pedidosAcesso'
import { usarFeedback } from '@/composables/feedback'
import { textoAtencao, textoNovidades } from '@/modulos/feedback/logica'
import logo from '@/assets/logo.svg'
import Marca from '@/components/app/Marca.vue'
import { filtrarNavegacao, itemAtivo, navegacaoAdministracao, navegacaoPrincipal, navegacaoRodape, type ItemNavegacao } from './navegacao'

/** `recolhivel`: barra fixa do computador, que pode ficar só com os ícones. A gaveta do celular fica sempre aberta. */
const props = withDefaults(defineProps<{ recolhivel?: boolean }>(), { recolhivel: false })
defineEmits<{ navegou: [] }>()
const sessao = useSessaoStore()
const rota = useRoute()
const { recolhido, alternar } = useMenuLateral()
const compacto = computed(() => props.recolhivel && recolhido.value)

/** Ativo também nas páginas de dentro (ex.: /contatos/123 marca Contatos). */
function ativoNa(i: ItemNavegacao, isActive: boolean) {
  return itemAtivo(i, rota.path, rota.query, isActive)
}

const principal = computed(() => filtrarNavegacao(navegacaoPrincipal, sessao.pode, sessao.superadmin))
const administracao = computed(() => filtrarNavegacao(navegacaoAdministracao, sessao.pode, sessao.superadmin, sessao.admin))

// Pedidos de acesso esperando aprovação: o número ao lado de Equipe (relido a cada troca de página, no máximo a cada 60 s).
const pedidos = usarPedidosAcesso()
// Feedback: as respostas novas da equipe Toqqi (botão "Feedback", para todos) e, para a equipe, os feedbacks que pedem
// atenção (ao lado de Plataforma). Mesmo ritmo dos pedidos de acesso.
const feedback = usarFeedback()
watch(
  () => rota.fullPath,
  () => {
    void pedidos.atualizar(sessao.pode('equipe.gerenciar'))
    void feedback.atualizarNovidades()
    void feedback.atualizarAtencao(sessao.superadmin)
  },
  { immediate: true },
)
function contagem(i: ItemNavegacao): number {
  if (i.contador === 'pedidosAcesso') return pedidos.total.value
  if (i.contador === 'feedbackPlataforma') return feedback.atencao.value
  return 0
}
function textoContagem(i: ItemNavegacao): string {
  const n = contagem(i)
  return i.contador === 'feedbackPlataforma' ? textoAtencao(n) : textoPedidos(n)
}

function classes(ativo: boolean) {
  return [
    'group relative flex items-center rounded-xl py-2.5 text-sm font-semibold transition-colors',
    compacto.value ? 'justify-center px-0' : 'gap-3 px-3',
    ativo ? 'bg-marca-suave text-marca-texto' : 'text-texto-suave hover:bg-superficie-2 hover:text-texto',
  ]
}
function chave(i: ItemNavegacao) {
  return i.para
}
function dica(i: ItemNavegacao) {
  return i.emBreve ? `${i.rotulo} (em breve)` : i.rotulo
}
// Dica ao lado do ícone, com o menu recolhido (aparece ao passar o mouse ou ao chegar pelo teclado).
const classeDica =
  'pointer-events-none absolute left-full top-1/2 z-10 ml-3 -translate-y-1/2 whitespace-nowrap rounded-lg bg-texto px-2.5 py-1.5 ' +
  'text-xs font-semibold text-superficie opacity-0 shadow-lg transition-opacity group-hover:opacity-100 group-focus-visible:opacity-100'
</script>

<template>
  <div class="flex h-full flex-col">
    <div class="flex h-16 shrink-0 items-center" :class="compacto ? 'justify-center px-3' : 'px-5'">
      <RouterLink v-if="compacto" to="/inicio" class="rounded-lg" aria-label="Toqqi, início">
        <img :src="logo" alt="" aria-hidden="true" class="size-9" />
      </RouterLink>
      <RouterLink v-else to="/inicio" class="rounded-lg" aria-label="Toqqi, início" @click="$emit('navegou')"><Marca /></RouterLink>
    </div>
    <nav
      id="menu-lateral"
      aria-label="Menu principal"
      class="flex flex-1 flex-col gap-6 px-3 pb-4 pt-2"
      :class="compacto ? 'overflow-visible' : 'overflow-y-auto'"
    >
      <ul class="flex flex-col gap-0.5">
        <li v-for="item in principal" :key="chave(item)">
          <RouterLink v-slot="{ href, navigate, isActive }" :to="item.para" custom>
            <a :href="href" :class="classes(ativoNa(item, isActive))" :aria-current="ativoNa(item, isActive) ? 'page' : undefined" @click="(e) => { navigate(e); $emit('navegou') }">
              <component :is="item.icone" class="size-5 shrink-0" aria-hidden="true" />
              <span :class="compacto ? 'sr-only' : 'flex-1'">{{ compacto ? dica(item) : item.rotulo }}</span>
              <span v-if="item.emBreve && !compacto" class="rounded-full bg-superficie-2 px-2 py-0.5 text-[0.65rem] font-semibold uppercase tracking-wide text-texto-fraco group-hover:bg-borda">em breve</span>
              <span v-if="compacto" aria-hidden="true" :class="classeDica">{{ dica(item) }}</span>
            </a>
          </RouterLink>
        </li>
      </ul>
      <div v-if="administracao.length" class="mt-auto">
        <p v-if="!compacto" class="px-3 pb-2 text-xs font-semibold uppercase tracking-wider text-texto-fraco">Administração</p>
        <template v-else>
          <p class="sr-only">Administração</p>
          <hr class="mx-2 mb-2 border-borda" aria-hidden="true" />
        </template>
        <ul class="flex flex-col gap-0.5">
          <li v-for="item in administracao" :key="chave(item)">
            <RouterLink v-slot="{ href, navigate, isActive }" :to="item.para" custom>
              <a :href="href" :class="classes(ativoNa(item, isActive))" :aria-current="ativoNa(item, isActive) ? 'page' : undefined" @click="(e) => { navigate(e); $emit('navegou') }">
                <component :is="item.icone" class="size-5 shrink-0" aria-hidden="true" />
                <span :class="compacto ? 'sr-only' : 'flex-1'">
                  {{ item.rotulo }}<span v-if="contagem(item) > 0" class="sr-only">, {{ textoContagem(item) }}</span>
                </span>
                <span
                  v-if="contagem(item) > 0 && !compacto"
                  class="min-w-5 rounded-full bg-marca-forte px-1.5 text-center text-xs font-bold text-white"
                  aria-hidden="true"
                  data-contador-menu
                >{{ contagem(item) }}</span>
                <span
                  v-else-if="contagem(item) > 0"
                  class="absolute right-2 top-1.5 size-2 rounded-full bg-marca-forte ring-2 ring-superficie"
                  aria-hidden="true"
                  data-contador-menu
                />
                <span v-if="compacto" aria-hidden="true" :class="classeDica">
                  {{ item.rotulo }}<template v-if="contagem(item) > 0"> · {{ textoContagem(item) }}</template>
                </span>
              </a>
            </RouterLink>
          </li>
        </ul>
      </div>
    </nav>
    <div class="flex shrink-0 flex-col gap-0.5 border-t border-borda p-3">
      <!-- Ajuda (etapa 5b): também na gaveta do celular, que não tem o botão de recolher. -->
      <RouterLink v-for="item in navegacaoRodape" :key="chave(item)" v-slot="{ href, navigate, isActive }" :to="item.para" custom>
        <a :href="href" :class="classes(ativoNa(item, isActive))" :aria-current="ativoNa(item, isActive) ? 'page' : undefined" @click="(e) => { navigate(e); $emit('navegou') }">
          <component :is="item.icone" class="size-5 shrink-0" aria-hidden="true" />
          <span :class="compacto ? 'sr-only' : 'flex-1'">{{ item.rotulo }}</span>
          <span v-if="compacto" aria-hidden="true" :class="classeDica">{{ item.rotulo }}</span>
        </a>
      </RouterLink>
      <!-- Feedback: abre a janela por cima da tela atual (leva o caminho e o título dela). -->
      <button type="button" :class="classes(false)" class="w-full" data-botao-feedback @click="feedback.abrir(); $emit('navegou')">
        <MessageSquareHeart class="size-5 shrink-0" aria-hidden="true" />
        <span :class="compacto ? 'sr-only' : 'flex-1 text-left'">
          Feedback<span v-if="feedback.novidades.value > 0" class="sr-only">, {{ textoNovidades(feedback.novidades.value) }}</span>
        </span>
        <span
          v-if="feedback.novidades.value > 0 && !compacto"
          class="min-w-5 rounded-full bg-marca-forte px-1.5 text-center text-xs font-bold text-white"
          aria-hidden="true"
          data-contador-feedback
        >{{ feedback.novidades.value }}</span>
        <span
          v-else-if="feedback.novidades.value > 0"
          class="absolute right-2 top-1.5 size-2 rounded-full bg-marca-forte ring-2 ring-superficie"
          aria-hidden="true"
          data-contador-feedback
        />
        <span v-if="compacto" aria-hidden="true" :class="classeDica">
          Feedback<template v-if="feedback.novidades.value > 0"> · {{ textoNovidades(feedback.novidades.value) }}</template>
        </span>
      </button>
      <button
        v-if="recolhivel"
        type="button"
        :class="classes(false)"
        class="w-full"
        aria-controls="menu-lateral"
        :aria-expanded="!compacto"
        @click="alternar"
      >
        <PanelLeftOpen v-if="compacto" class="size-5 shrink-0" aria-hidden="true" />
        <PanelLeftClose v-else class="size-5 shrink-0" aria-hidden="true" />
        <span :class="compacto ? 'sr-only' : 'flex-1 text-left'">{{ compacto ? 'Expandir menu' : 'Recolher menu' }}</span>
        <span v-if="compacto" aria-hidden="true" :class="classeDica">Expandir menu</span>
      </button>
    </div>
  </div>
</template>

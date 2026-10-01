<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { PanelLeftClose, PanelLeftOpen } from 'lucide-vue-next'
import { useSessaoStore } from '@/stores/sessao'
import { useMenuLateral } from '@/composables/menuLateral'
import logo from '@/assets/logo.svg'
import Marca from '@/components/app/Marca.vue'
import { filtrarNavegacao, itemAtivo, navegacaoAdministracao, navegacaoPrincipal, type ItemNavegacao } from './navegacao'

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
                <span :class="compacto ? 'sr-only' : 'flex-1'">{{ item.rotulo }}</span>
                <span v-if="compacto" aria-hidden="true" :class="classeDica">{{ item.rotulo }}</span>
              </a>
            </RouterLink>
          </li>
        </ul>
      </div>
    </nav>
    <div v-if="recolhivel" class="shrink-0 border-t border-borda p-3">
      <button
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

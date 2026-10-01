<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { useSessaoStore } from '@/stores/sessao'
import Marca from '@/components/app/Marca.vue'
import { filtrarNavegacao, itemAtivo, navegacaoAdministracao, navegacaoPrincipal, type ItemNavegacao } from './navegacao'

defineEmits<{ navegou: [] }>()
const sessao = useSessaoStore()
const rota = useRoute()
/** Ativo também nas páginas de dentro (ex.: /contatos/123 marca Contatos). */
function ativoNa(i: ItemNavegacao, isActive: boolean) {
  return itemAtivo(i, rota.path, rota.query, isActive)
}

const principal = computed(() => filtrarNavegacao(navegacaoPrincipal, sessao.pode, sessao.superadmin))
const administracao = computed(() => filtrarNavegacao(navegacaoAdministracao, sessao.pode, sessao.superadmin, sessao.admin))

function classes(ativo: boolean) {
  return [
    'group flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-semibold transition-colors',
    ativo ? 'bg-marca-suave text-marca-texto' : 'text-texto-suave hover:bg-superficie-2 hover:text-texto',
  ]
}
function chave(i: ItemNavegacao) {
  return i.para
}
</script>

<template>
  <div class="flex h-full flex-col">
    <div class="flex h-16 shrink-0 items-center px-5">
      <RouterLink to="/inicio" class="rounded-lg" aria-label="Toqqi, início" @click="$emit('navegou')"><Marca /></RouterLink>
    </div>
    <nav aria-label="Menu principal" class="flex flex-1 flex-col gap-6 overflow-y-auto px-3 pb-4 pt-2">
      <ul class="flex flex-col gap-0.5">
        <li v-for="item in principal" :key="chave(item)">
          <RouterLink v-slot="{ href, navigate, isActive }" :to="item.para" custom>
            <a :href="href" :class="classes(ativoNa(item, isActive))" :aria-current="ativoNa(item, isActive) ? 'page' : undefined" @click="(e) => { navigate(e); $emit('navegou') }">
              <component :is="item.icone" class="size-5 shrink-0" aria-hidden="true" />
              <span class="flex-1">{{ item.rotulo }}</span>
              <span v-if="item.emBreve" class="rounded-full bg-superficie-2 px-2 py-0.5 text-[0.65rem] font-semibold uppercase tracking-wide text-texto-fraco group-hover:bg-borda">em breve</span>
            </a>
          </RouterLink>
        </li>
      </ul>
      <div v-if="administracao.length" class="mt-auto">
        <p class="px-3 pb-2 text-xs font-semibold uppercase tracking-wider text-texto-fraco">Administração</p>
        <ul class="flex flex-col gap-0.5">
          <li v-for="item in administracao" :key="chave(item)">
            <RouterLink v-slot="{ href, navigate, isActive }" :to="item.para" custom>
              <a :href="href" :class="classes(ativoNa(item, isActive))" :aria-current="ativoNa(item, isActive) ? 'page' : undefined" @click="(e) => { navigate(e); $emit('navegou') }">
                <component :is="item.icone" class="size-5 shrink-0" aria-hidden="true" />
                <span class="flex-1">{{ item.rotulo }}</span>
              </a>
            </RouterLink>
          </li>
        </ul>
      </div>
    </nav>
  </div>
</template>

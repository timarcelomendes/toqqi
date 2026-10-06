<script setup lang="ts">
// Menu "Inserir" (docs/api-etapa-5l.md §5.3): variáveis ({empresa}, {nome}, {assunto}, {referencia}) e respostas
// anteriores (`{{id}}` de uma pergunta antes deste item). Quem usa decide onde o texto entra (o cursor do campo).
import { computed } from 'vue'
import { Braces } from 'lucide-vue-next'
import type { Pergunta } from '@/api/tipos'
import ItemMenu from '@/components/app/ItemMenu.vue'
import MenuSuspenso from '@/components/ui/MenuSuspenso.vue'
import { nomeDoItem, numerosDasPerguntas } from '../logicaEditor'

const props = withDefaults(
  defineProps<{
    /** Para o leitor de tela: "Inserir no título". */
    rotulo: string
    /** Perguntas que podem ser citadas (as anteriores; nos finais, todas). */
    citaveis?: Pergunta[]
    /** Todos os itens (para os números P1, P2…). */
    itens?: Pergunta[]
    semVariaveis?: boolean
    alinhar?: 'esquerda' | 'direita'
  }>(),
  { citaveis: () => [], itens: () => [], semVariaveis: false, alinhar: 'direita' },
)
const emit = defineEmits<{ inserir: [texto: string] }>()

const VARIAVEIS = [
  { rotulo: 'Nome da empresa', texto: '{empresa}' },
  { rotulo: 'Nome do contato', texto: '{nome}' },
  { rotulo: 'Assunto', texto: '{assunto}' },
  { rotulo: 'Referência', texto: '{referencia}' },
]
const numeros = computed(() => numerosDasPerguntas(props.itens.length ? props.itens : props.citaveis))
</script>

<template>
  <MenuSuspenso :rotulo="rotulo" :alinhar="alinhar">
    <template #gatilho="{ props: gatilho }">
      <button
        v-bind="gatilho"
        type="button"
        class="inline-flex h-7 items-center gap-1 rounded-lg px-2 text-xs font-semibold text-texto-suave hover:bg-superficie-2 hover:text-texto disabled:opacity-50"
        data-menu-inserir
      >
        <Braces class="size-3.5" aria-hidden="true" /> Inserir
      </button>
    </template>
    <div class="max-h-80 w-72 overflow-y-auto">
      <div v-if="!semVariaveis" role="group" aria-label="Variáveis">
        <p class="px-3 pb-1 pt-1.5 text-xs font-bold uppercase tracking-wide text-texto-fraco" aria-hidden="true">Variáveis</p>
        <ItemMenu v-for="v in VARIAVEIS" :key="v.texto" :data-inserir="v.texto" @click="emit('inserir', v.texto)">
          <span class="flex-1">{{ v.rotulo }}</span>
          <code class="text-xs text-texto-fraco">{{ v.texto }}</code>
        </ItemMenu>
      </div>
      <div role="group" aria-label="Respostas anteriores" :class="semVariaveis ? '' : 'mt-1 border-t border-borda pt-1'">
        <p class="px-3 pb-1 pt-1.5 text-xs font-bold uppercase tracking-wide text-texto-fraco" aria-hidden="true">Respostas anteriores</p>
        <ItemMenu v-for="p in citaveis" :key="p.id" :data-inserir="`{{${p.id}}}`" @click="emit('inserir', `{{${p.id}}}`)">
          <span class="line-clamp-2 flex-1 text-left">{{ nomeDoItem(p, numeros, 70) }}</span>
        </ItemMenu>
        <p v-if="!citaveis.length" class="px-3 pb-2 text-xs text-texto-fraco" role="none">Nenhuma pergunta antes deste item.</p>
      </div>
    </div>
  </MenuSuspenso>
</template>

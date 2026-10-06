<script setup lang="ts">
// Menu "Adicionar" (docs/api-etapa-5l.md §5.3): busca no alto, opções agrupadas (Notas, Escolhas, Texto, Data,
// Conteúdo, Estrutura), cada uma com uma linha de descrição. Setas andam nas opções e Enter escolhe (padrão
// combobox + listbox: o foco fica na busca). Abre pelo "+ Adicionar", pelo "+" entre dois itens ou pela tecla "/".
import { computed, nextTick, ref, useId, watch } from 'vue'
import { Search } from 'lucide-vue-next'
import Modal from '@/components/ui/Modal.vue'
import { filtrarOpcoes, GRUPOS_ADICIONAR, type OpcaoAdicionar } from '../tiposPergunta'

defineProps<{ descricao?: string }>()
const aberto = defineModel<boolean>('aberto', { default: false })
const emit = defineEmits<{ escolher: [opcao: OpcaoAdicionar] }>()

const id = `adicionar-${useId()}`
const busca = ref('')
const ativa = ref(0)
const campo = ref<HTMLInputElement | null>(null)

const opcoes = computed(() => filtrarOpcoes(busca.value))
const grupos = computed(() =>
  GRUPOS_ADICIONAR.map((g) => ({ nome: g, opcoes: opcoes.value.filter((o) => o.grupo === g) })).filter((g) => g.opcoes.length),
)
/** A ordem das setas: a das opções na tela (grupo a grupo). */
const plana = computed(() => grupos.value.flatMap((g) => g.opcoes))
const idOpcao = (o: OpcaoAdicionar) => `${id}-${o.chave}`

watch(aberto, async (v) => {
  if (!v) return
  busca.value = ''
  ativa.value = 0
  await nextTick()
  campo.value?.focus()
})
watch(busca, () => (ativa.value = 0))

async function mostrarAtiva() {
  await nextTick()
  const o = plana.value[ativa.value]
  if (o) document.getElementById(idOpcao(o))?.scrollIntoView?.({ block: 'nearest' })
}

function aoTeclar(e: KeyboardEvent) {
  // A lista fica sempre à mostra (não é um popup da busca): Esc fecha o menu.
  if (e.key === 'Escape') {
    e.preventDefault()
    aberto.value = false
    return
  }
  const n = plana.value.length
  if (!n) return
  if (e.key === 'ArrowDown') ativa.value = (ativa.value + 1) % n
  else if (e.key === 'ArrowUp') ativa.value = (ativa.value - 1 + n) % n
  else if (e.key === 'Home' && e.ctrlKey) ativa.value = 0
  else if (e.key === 'End' && e.ctrlKey) ativa.value = n - 1
  else if (e.key === 'Enter') {
    e.preventDefault()
    const o = plana.value[ativa.value]
    if (o) escolher(o)
    return
  } else return
  e.preventDefault()
  void mostrarAtiva()
}

function escolher(o: OpcaoAdicionar) {
  emit('escolher', o)
  aberto.value = false
}
</script>

<template>
  <Modal v-model:aberto="aberto" titulo="Adicionar" :descricao="descricao" tamanho="lg">
    <div class="flex flex-col gap-4" data-menu-adicionar>
      <div class="relative">
        <Search class="pointer-events-none absolute left-3.5 top-1/2 size-4 -translate-y-1/2 text-texto-fraco" aria-hidden="true" />
        <input
          ref="campo"
          v-model="busca"
          type="search"
          role="combobox"
          aria-autocomplete="list"
          :aria-expanded="plana.length > 0"
          :aria-controls="`${id}-lista`"
          :aria-activedescendant="plana[ativa] ? idOpcao(plana[ativa]!) : undefined"
          aria-label="Buscar tipo de item"
          placeholder="Buscar: NPS, comentário, e-mail, HTML…"
          autocomplete="off"
          class="h-11 w-full rounded-xl border border-borda-forte bg-superficie pl-10 pr-3.5 text-[0.95rem] text-texto placeholder:text-texto-fraco/80 focus:border-marca focus:outline-none focus:ring-3 focus:ring-marca/20"
          data-autofoco
          data-busca-adicionar
          @keydown="aoTeclar"
        />
      </div>
      <div :id="`${id}-lista`" role="listbox" aria-label="Tipos de item" class="grid max-h-[60dvh] gap-x-4 gap-y-3 overflow-y-auto pr-1 sm:grid-cols-2">
        <div v-for="g in grupos" :key="g.nome" role="group" :aria-labelledby="`${id}-g-${g.nome}`" class="flex flex-col gap-1" :data-grupo="g.nome">
          <p :id="`${id}-g-${g.nome}`" class="px-2 pb-0.5 text-xs font-bold uppercase tracking-wide text-texto-fraco">{{ g.nome }}</p>
          <div
            v-for="o in g.opcoes"
            :id="idOpcao(o)"
            :key="o.chave"
            role="option"
            :aria-selected="plana[ativa]?.chave === o.chave"
            class="flex cursor-pointer items-start gap-3 rounded-xl px-2 py-2 transition-colors"
            :class="plana[ativa]?.chave === o.chave ? 'bg-marca-suave ring-1 ring-marca/40' : 'hover:bg-superficie-2'"
            :data-opcao="o.chave"
            @mousemove="ativa = plana.indexOf(o)"
            @click="escolher(o)"
          >
            <span class="flex size-8 shrink-0 items-center justify-center rounded-lg bg-superficie-2 text-marca-texto" aria-hidden="true">
              <component :is="o.icone" class="size-4" />
            </span>
            <span class="min-w-0">
              <span class="block text-sm font-bold text-texto">{{ o.rotulo }}</span>
              <span class="block text-xs leading-snug text-texto-suave">{{ o.descricao }}</span>
            </span>
          </div>
        </div>
        <p v-if="!plana.length" class="col-span-full py-6 text-center text-sm text-texto-fraco" role="status">Nada encontrado para “{{ busca }}”.</p>
      </div>
      <p class="text-xs text-texto-fraco">Dica: aperte <kbd class="rounded border border-borda-forte px-1 font-sans">/</kbd> fora de um campo de texto para abrir este menu.</p>
    </div>
  </Modal>
</template>

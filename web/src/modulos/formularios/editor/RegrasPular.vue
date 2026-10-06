<script setup lang="ts">
// "Depois desta pergunta" (docs/api-etapa-5l.md §5.3): regras "Se [condições] → Ir para [item posterior | Fim da
// pesquisa]", avaliadas na ordem (vale a primeira que combinar), com "+ Regra", reordenar e remover.
// Rodapé: "Senão: segue para a próxima".
import { computed } from 'vue'
import { ArrowDown, ArrowUp, CornerDownRight, Plus, Trash2 } from 'lucide-vue-next'
import type { Pergunta, Regra } from '@/api/tipos'
import { condicaoPadrao, destinosPara, fontesPara, MAX_REGRAS, nomeDoItem, numerosDasPerguntas, FIM } from '../logicaEditor'
import { idsDeRegras, novoId } from '../tiposPergunta'
import { errosDaLogica } from '../validacaoFormulario'
import { usarEditor } from './documento'
import ConstrutorGrupo from './ConstrutorGrupo.vue'
import SelecaoCompacta from './SelecaoCompacta.vue'

const props = defineProps<{ item: Pergunta; indice: number }>()
const editor = usarEditor()

const itens = computed(() => editor.doc.perguntas)
const numeros = computed(() => numerosDasPerguntas(itens.value))
const regras = computed(() => props.item.logica?.pular ?? [])
const fontes = computed(() => fontesPara(itens.value, 'pular', props.indice))
const destinos = computed(() => destinosPara(itens.value, props.indice))
const problemasDoItem = computed(() => editor.problemas.value.filter((p) => 'id' in p.alvo && p.alvo.id === props.item.id))

function erros(n: number) {
  return errosDaLogica(problemasDoItem.value, 'pular', n)
}

/** A condição da regra nova, na própria pergunta: "é Não" no sim/não, "não foi respondida" nos textos. */
function condicaoInicial(p: Pergunta) {
  if (p.tipo === 'sim_nao') return { fonte: p.id, op: 'igual' as const, valor: false }
  if (p.tipo === 'comentario' || (p.tipo === 'texto_curto' && p.formato !== 'numero')) return { fonte: p.id, op: 'nao_respondida' as const }
  return condicaoPadrao(p)
}

function adicionar() {
  if (regras.value.length >= MAX_REGRAS) return
  const regra: Regra = {
    id: novoId('r_', idsDeRegras(itens.value)),
    se: { juncao: 'todas', condicoes: [condicaoInicial(props.item)] },
    para: FIM,
  }
  props.item.logica = { ...(props.item.logica ?? {}), pular: [...regras.value, regra] }
}

function remover(i: number) {
  const lista = regras.value.filter((_, k) => k !== i)
  if (lista.length) props.item.logica!.pular = lista
  else {
    delete props.item.logica!.pular
    if (!props.item.logica!.mostrar_se) delete props.item.logica
  }
}

function mover(i: number, d: number) {
  const j = i + d
  if (j < 0 || j >= regras.value.length) return
  const lista = [...regras.value]
  const [r] = lista.splice(i, 1)
  lista.splice(j, 0, r!)
  props.item.logica!.pular = lista
}
</script>

<template>
  <div class="flex flex-col gap-3" data-logica-onde="pular">
    <ol class="flex flex-col gap-3">
      <li v-for="(r, i) in regras" :key="r.id || i" class="rounded-xl border border-borda bg-superficie-2/50 p-3" :data-regra="i + 1">
        <div class="mb-2 flex items-center gap-1">
          <p class="flex-1 text-xs font-bold uppercase tracking-wide text-texto-fraco">Regra {{ i + 1 }}</p>
          <button type="button" class="flex size-8 items-center justify-center rounded-lg text-texto-fraco hover:bg-superficie-2 hover:text-texto disabled:opacity-30" :disabled="i === 0" :aria-label="`Subir a regra ${i + 1}`" @click="mover(i, -1)">
            <ArrowUp class="size-4" aria-hidden="true" />
          </button>
          <button type="button" class="flex size-8 items-center justify-center rounded-lg text-texto-fraco hover:bg-superficie-2 hover:text-texto disabled:opacity-30" :disabled="i === regras.length - 1" :aria-label="`Descer a regra ${i + 1}`" @click="mover(i, 1)">
            <ArrowDown class="size-4" aria-hidden="true" />
          </button>
          <button type="button" class="flex size-8 items-center justify-center rounded-lg text-texto-fraco hover:bg-erro-suave hover:text-erro" :aria-label="`Remover a regra ${i + 1}`" data-remover-regra @click="remover(i)">
            <Trash2 class="size-4" aria-hidden="true" />
          </button>
        </div>
        <ConstrutorGrupo :grupo="r.se" :fontes="fontes" :itens="itens" prefixo="Se" :erros="erros(i + 1)" :contexto="`regra ${i + 1}`" @vazio="remover(i)" />
        <div class="mt-3 flex flex-wrap items-center gap-2">
          <span class="inline-flex items-center gap-1 text-sm font-semibold text-texto"><CornerDownRight class="size-4 text-texto-fraco" aria-hidden="true" /> Ir para</span>
          <SelecaoCompacta class="min-w-48 flex-1" :valor="r.para" :rotulo="`Para onde a regra ${i + 1} manda`" data-destino @escolher="(v) => (r.para = v)">
            <option v-if="r.para && r.para !== FIM && !destinos.some((d) => d.id === r.para)" :value="r.para">Item que não vale aqui</option>
            <option v-for="d in destinos" :key="d.id" :value="d.id">{{ nomeDoItem(d, numeros, 60) }}</option>
            <option :value="FIM">Fim da pesquisa</option>
          </SelecaoCompacta>
        </div>
        <ul v-if="erros(i + 1).geral.length" class="mt-2 flex flex-col gap-0.5">
          <li v-for="m in erros(i + 1).geral" :key="m" class="text-sm font-medium text-erro">{{ m }}</li>
        </ul>
      </li>
    </ol>
    <div class="flex flex-wrap items-center justify-between gap-2">
      <button
        type="button"
        class="inline-flex h-8 items-center gap-1 rounded-lg px-2 text-sm font-semibold text-marca-texto hover:bg-marca-suave disabled:opacity-50"
        :disabled="regras.length >= MAX_REGRAS"
        data-adicionar-regra
        @click="adicionar"
      >
        <Plus class="size-4" aria-hidden="true" /> Regra
      </button>
      <p class="text-sm text-texto-fraco">Senão: segue para a próxima.</p>
    </div>
  </div>
</template>

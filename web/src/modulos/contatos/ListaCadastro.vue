<script setup lang="ts">
// Um cadastro auxiliar (grupos, segmentos, perfis ou cargos) com incluir, renomear e excluir na própria lista.
import { computed, nextTick, ref } from 'vue'
import { Check, Pencil, Plus, Trash2, X } from 'lucide-vue-next'
import { cadastrosApi, mensagemDoErro, type Id, type ItemCadastro, type TipoCadastro } from '@/api'
import { avisar } from '@/composables/avisos'
import { confirmar } from '@/composables/confirmacao'
import { useCadastrosStore } from '@/stores/cadastros'
import { plural } from '@/utils/formatos'

const props = defineProps<{
  tipo: TipoCadastro
  titulo: string
  descricao: string
  singular: string
  /** Quem usa: "empresas" ou "contatos". */
  usadoPor: string
  podeEditar: boolean
  podeExcluir: boolean
}>()

const cadastros = useCadastrosStore()
const itens = computed(() => cadastros.listas[props.tipo])
const novoNome = ref('')
const erroNovo = ref<string | null>(null)
const adicionando = ref(false)
const editando = ref<Id | null>(null)
const nomeEdicao = ref('')
const erroEdicao = ref<string | null>(null)
const ocupado = ref<Id | null>(null)
const campoEdicao = ref<HTMLInputElement[]>([])
const idBase = `cad-${props.tipo}`

async function adicionar() {
  const nome = novoNome.value.trim()
  if (!nome) return
  adicionando.value = true
  erroNovo.value = null
  try {
    cadastros.colocar(props.tipo, await cadastrosApi.criar(props.tipo, nome))
    novoNome.value = ''
  } catch (e) {
    erroNovo.value = mensagemDoErro(e)
  } finally {
    adicionando.value = false
  }
}

async function editar(i: ItemCadastro) {
  editando.value = i.id
  nomeEdicao.value = i.nome
  erroEdicao.value = null
  await nextTick()
  campoEdicao.value[0]?.focus()
  campoEdicao.value[0]?.select()
}

async function salvarEdicao(i: ItemCadastro) {
  const nome = nomeEdicao.value.trim()
  if (!nome || nome === i.nome) {
    editando.value = null
    return
  }
  ocupado.value = i.id
  erroEdicao.value = null
  try {
    cadastros.colocar(props.tipo, await cadastrosApi.renomear(props.tipo, i.id, nome))
    editando.value = null
  } catch (e) {
    erroEdicao.value = mensagemDoErro(e)
  } finally {
    ocupado.value = null
  }
}

function teclaEdicao(e: KeyboardEvent, i: ItemCadastro) {
  if (e.key === 'Enter') {
    e.preventDefault()
    salvarEdicao(i)
  } else if (e.key === 'Escape') {
    editando.value = null
  }
}

async function excluir(i: ItemCadastro) {
  const ok = await confirmar({
    titulo: `Excluir “${i.nome}”?`,
    mensagem:
      i.em_uso > 0
        ? `${plural(i.em_uso, `${props.usadoPor.replace(/s$/, '')} usa`, `${props.usadoPor} usam`)} este ${props.singular}. Eles continuam cadastrados, só que sem ${props.singular}.`
        : `Ninguém usa este ${props.singular} ainda.`,
    confirmar: 'Excluir',
    perigo: true,
  })
  if (!ok) return
  ocupado.value = i.id
  try {
    await cadastrosApi.excluir(props.tipo, i.id)
    cadastros.tirar(props.tipo, i.id)
    avisar.sucesso(`“${i.nome}” foi excluído.`)
  } catch (e) {
    avisar.erro(mensagemDoErro(e))
  } finally {
    ocupado.value = null
  }
}
</script>

<template>
  <section class="cartao flex flex-col" :aria-labelledby="`${idBase}-titulo`">
    <header class="border-b border-borda px-5 py-4">
      <h3 :id="`${idBase}-titulo`" class="font-bold text-texto">{{ titulo }}</h3>
      <p class="text-sm text-texto-fraco">{{ descricao }}</p>
    </header>
    <ul class="flex-1 divide-y divide-borda">
      <li v-if="!itens.length" class="px-5 py-6 text-center text-sm text-texto-fraco">Nenhum {{ singular }} cadastrado.</li>
      <li v-for="i in itens" :key="String(i.id)" class="flex items-center gap-2 px-5 py-2.5">
        <template v-if="editando === i.id">
          <div class="flex min-w-0 flex-1 flex-col gap-1">
            <label :for="`${idBase}-ed-${i.id}`" class="sr-only">Novo nome para {{ i.nome }}</label>
            <input
              :id="`${idBase}-ed-${i.id}`"
              ref="campoEdicao"
              v-model="nomeEdicao"
              maxlength="120"
              class="h-9 w-full rounded-lg border border-borda-forte bg-superficie px-2.5 text-sm text-texto focus:border-marca focus:outline-none focus:ring-3 focus:ring-marca/20"
              :aria-invalid="erroEdicao ? 'true' : undefined"
              @keydown="teclaEdicao($event, i)"
            />
            <p v-if="erroEdicao" class="text-xs font-medium text-erro">{{ erroEdicao }}</p>
          </div>
          <button type="button" class="flex size-8 items-center justify-center rounded-lg text-sucesso hover:bg-superficie-2" aria-label="Salvar nome" :disabled="ocupado === i.id" @click="salvarEdicao(i)">
            <Check class="size-4" aria-hidden="true" />
          </button>
          <button type="button" class="flex size-8 items-center justify-center rounded-lg text-texto-fraco hover:bg-superficie-2" aria-label="Cancelar" @click="editando = null">
            <X class="size-4" aria-hidden="true" />
          </button>
        </template>
        <template v-else>
          <span class="min-w-0 flex-1 truncate text-sm font-medium text-texto">{{ i.nome }}</span>
          <span class="shrink-0 text-xs text-texto-fraco" :title="`${i.em_uso} ${usadoPor} usando`">{{ i.em_uso > 0 ? `em uso: ${i.em_uso}` : 'sem uso' }}</span>
          <button v-if="podeEditar" type="button" class="flex size-8 items-center justify-center rounded-lg text-texto-fraco hover:bg-superficie-2 hover:text-texto" :aria-label="`Renomear ${i.nome}`" @click="editar(i)">
            <Pencil class="size-4" aria-hidden="true" />
          </button>
          <button
            v-if="podeExcluir"
            type="button"
            class="flex size-8 items-center justify-center rounded-lg text-texto-fraco hover:bg-erro-suave hover:text-erro disabled:opacity-50"
            :aria-label="`Excluir ${i.nome}`"
            :disabled="ocupado === i.id"
            @click="excluir(i)"
          >
            <Trash2 class="size-4" aria-hidden="true" />
          </button>
        </template>
      </li>
    </ul>
    <form v-if="podeEditar" class="flex flex-col gap-1 border-t border-borda px-5 py-3" @submit.prevent="adicionar">
      <div class="flex gap-2">
        <label :for="`${idBase}-novo`" class="sr-only">Novo {{ singular }}</label>
        <input
          :id="`${idBase}-novo`"
          v-model="novoNome"
          maxlength="120"
          :placeholder="`Novo ${singular}`"
          class="h-9 min-w-0 flex-1 rounded-lg border border-borda-forte bg-superficie px-2.5 text-sm text-texto placeholder:text-texto-fraco/80 focus:border-marca focus:outline-none focus:ring-3 focus:ring-marca/20"
          :aria-invalid="erroNovo ? 'true' : undefined"
        />
        <button
          type="submit"
          class="inline-flex h-9 items-center gap-1 rounded-lg bg-superficie-2 px-3 text-sm font-semibold text-texto hover:bg-borda disabled:opacity-50"
          :disabled="adicionando || !novoNome.trim()"
        >
          <Plus class="size-4" aria-hidden="true" /> Adicionar
        </button>
      </div>
      <p v-if="erroNovo" class="text-xs font-medium text-erro" role="alert">{{ erroNovo }}</p>
    </form>
  </section>
</template>

<script setup lang="ts">
// Lista de um cadastro auxiliar (grupo, segmento, perfil, cargo) com "+ novo" na hora:
// cria pela API e já deixa o item novo escolhido.
import { computed, nextTick, onMounted, ref } from 'vue'
import { Plus } from 'lucide-vue-next'
import { ApiError, cadastrosApi, mensagemDoErro, type Id, type TipoCadastro } from '@/api'
import { useCadastrosStore } from '@/stores/cadastros'
import Botao from '@/components/ui/Botao.vue'
import Campo from '@/components/ui/Campo.vue'
import Selecao from '@/components/ui/Selecao.vue'

const SINGULAR: Record<TipoCadastro, { nome: string; novo: string }> = {
  grupos: { nome: 'grupo', novo: 'Novo grupo' },
  segmentos: { nome: 'segmento', novo: 'Novo segmento' },
  perfis: { nome: 'perfil', novo: 'Novo perfil' },
  cargos: { nome: 'cargo', novo: 'Novo cargo' },
}

const props = withDefaults(
  defineProps<{ tipo: TipoCadastro; rotulo: string; erro?: string | null; podeCriar?: boolean; vazio?: string; dica?: string }>(),
  { vazio: 'Nenhum' },
)
const modelo = defineModel<Id | ''>({ required: true })
const cadastros = useCadastrosStore()
const criando = ref(false)
const nome = ref('')
const salvando = ref(false)
const erroNovo = ref<string | null>(null)
const campo = ref<InstanceType<typeof Campo> | null>(null)

const opcoes = computed(() => cadastros.listas[props.tipo].map((i) => ({ valor: i.id, rotulo: i.nome })))

async function abrir() {
  criando.value = true
  nome.value = ''
  erroNovo.value = null
  await nextTick()
  campo.value?.focar()
}

async function criar() {
  const n = nome.value.trim()
  if (!n) {
    erroNovo.value = `Digite o nome do ${SINGULAR[props.tipo].nome}.`
    return
  }
  salvando.value = true
  erroNovo.value = null
  try {
    const item = await cadastrosApi.criar(props.tipo, n)
    cadastros.colocar(props.tipo, item)
    modelo.value = item.id
    criando.value = false
  } catch (e) {
    // Já existe: escolhe o que existe em vez de reclamar.
    const existente = cadastros.listas[props.tipo].find((i) => i.nome.toLocaleLowerCase('pt-BR') === n.toLocaleLowerCase('pt-BR'))
    if (e instanceof ApiError && e.codigo === 'nome_em_uso' && existente) {
      modelo.value = existente.id
      criando.value = false
    } else erroNovo.value = mensagemDoErro(e)
  } finally {
    salvando.value = false
  }
}

function aoTeclar(e: KeyboardEvent) {
  if (e.key === 'Enter') {
    e.preventDefault()
    criar()
  } else if (e.key === 'Escape') {
    e.stopPropagation()
    criando.value = false
  }
}

onMounted(() => cadastros.garantir([props.tipo]))
</script>

<template>
  <div class="flex flex-col gap-1.5">
    <Selecao v-if="!criando" v-model="modelo" :rotulo="rotulo" :opcoes="opcoes" :vazio="vazio" :erro="erro" :dica="dica" />
    <div v-else class="flex flex-col gap-1.5" role="group" :aria-label="SINGULAR[tipo].novo">
      <div class="flex items-end gap-2">
        <Campo
          ref="campo"
          v-model="nome"
          :rotulo="`${SINGULAR[tipo].novo} (${rotulo.toLowerCase()})`"
          :erro="erroNovo"
          class="flex-1"
          autocomplete="off"
          maxlength="120"
          @keydown="aoTeclar"
        />
        <div class="flex gap-1" :class="erroNovo ? 'mb-7' : ''">
          <Botao tamanho="md" :carregando="salvando" @click="criar">Adicionar</Botao>
          <Botao tamanho="md" variante="fantasma" :desabilitado="salvando" @click="criando = false">Cancelar</Botao>
        </div>
      </div>
    </div>
    <button v-if="podeCriar && !criando" type="button" class="link inline-flex w-fit items-center gap-1 text-sm" @click="abrir">
      <Plus class="size-3.5" aria-hidden="true" /> {{ SINGULAR[tipo].novo }}
    </button>
  </div>
</template>

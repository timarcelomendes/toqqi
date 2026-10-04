<script setup lang="ts">
// Plataforma › Parâmetros › Histórico de alterações (etapa 5g, §7): mais novos primeiro, com data e hora, o grupo, quem
// salvou e uma linha por mudança ("Preço do Essencial: R$ 149,00 → R$ 159,00"). Filtro "Grupo" e paginação.
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { History } from 'lucide-vue-next'
import { mensagemDoErro, parametrosApi, type GrupoParametros, type ItemHistoricoParametros } from '@/api'
import { formatarDataHora } from '@/utils/datas'
import Alerta from '@/components/ui/Alerta.vue'
import Carregando from '@/components/ui/Carregando.vue'
import EstadoVazio from '@/components/ui/EstadoVazio.vue'
import Etiqueta from '@/components/ui/Etiqueta.vue'
import Paginacao from '@/components/ui/Paginacao.vue'
import Selecao from '@/components/ui/Selecao.vue'
import { GRUPOS_PARAMETROS, linhaMudanca, rotuloGrupo } from './parametros'

const grupo = ref<GrupoParametros | ''>('')
const pagina = ref(1)
const itens = ref<ItemHistoricoParametros[]>([])
const total = ref(0)
const porPagina = ref(20)
const carregando = ref(true)
const erro = ref<string | null>(null)
let controlador: AbortController | null = null

async function carregar() {
  controlador?.abort()
  const meu = new AbortController()
  controlador = meu
  carregando.value = true
  erro.value = null
  try {
    const r = await parametrosApi.historico({ grupo: grupo.value, pagina: pagina.value }, meu.signal)
    itens.value = r.itens ?? []
    total.value = r.total ?? 0
    porPagina.value = r.por_pagina || 20
  } catch (e) {
    if (e instanceof DOMException && e.name === 'AbortError') return
    erro.value = mensagemDoErro(e)
  } finally {
    if (controlador === meu) carregando.value = false
  }
}

/** Depois de salvar um grupo: volta à primeira página (a alteração nova fica no topo). */
function recarregar() {
  if (pagina.value !== 1) pagina.value = 1
  else void carregar()
}

watch(grupo, () => {
  if (pagina.value !== 1) pagina.value = 1
  else void carregar()
})
watch(pagina, () => void carregar())

onMounted(carregar)
onBeforeUnmount(() => controlador?.abort())

defineExpose({ recarregar })
</script>

<template>
  <section class="cartao overflow-hidden" aria-labelledby="t-param-historico" data-historico-parametros>
    <div class="flex flex-col gap-3 border-b border-borda px-5 py-4 sm:flex-row sm:items-end sm:justify-between sm:px-6">
      <div class="min-w-0">
        <h2 id="t-param-historico" class="text-base font-bold text-texto">Histórico de alterações</h2>
        <p class="mt-0.5 text-sm text-texto-suave">Quem mudou o quê e quando, com o valor de antes e o de depois.</p>
      </div>
      <Selecao v-model="grupo" rotulo="Grupo" :opcoes="GRUPOS_PARAMETROS" vazio="Todos" class="sm:w-56" data-filtro-grupo />
    </div>

    <Alerta v-if="erro" tom="erro" class="m-4">
      {{ erro }} <button type="button" class="link ml-1" @click="carregar">Tentar de novo</button>
    </Alerta>
    <div v-else-if="carregando && !itens.length" class="p-5 sm:p-6"><Carregando :linhas="3" rotulo="Carregando o histórico" /></div>
    <EstadoVazio
      v-else-if="!itens.length"
      :icone="History"
      :titulo="grupo ? 'Nenhuma alteração neste grupo' : 'Nenhuma alteração ainda'"
      descricao="Quando alguém salvar um parâmetro, a mudança aparece aqui."
    />
    <template v-else>
      <ol class="divide-y divide-borda" :aria-busy="carregando || undefined">
        <li v-for="i in itens" :key="i.id" class="flex flex-col gap-2 px-5 py-4 sm:px-6" data-item-historico>
          <p class="flex flex-wrap items-center gap-x-2 gap-y-1 text-sm" data-cabecalho-item>
            <span class="font-semibold text-texto">{{ formatarDataHora(i.criado_em) }}</span>{{ ' ' }}<Etiqueta tom="neutro">{{ rotuloGrupo(i.grupo) }}</Etiqueta
            >{{ ' ' }}<span class="min-w-0 text-texto-suave [overflow-wrap:anywhere]">por {{ i.por }}</span>
          </p>
          <ul class="flex list-disc flex-col gap-1 pl-5 text-sm text-texto-suave [overflow-wrap:anywhere]">
            <li v-for="m in i.mudancas" :key="m.chave">{{ linhaMudanca(m) }}</li>
          </ul>
        </li>
      </ol>
      <Paginacao v-model="pagina" :total="total" :por-pagina="porPagina" :carregando="carregando" :nome-itens="total === 1 ? 'alteração' : 'alterações'" />
    </template>
  </section>
</template>

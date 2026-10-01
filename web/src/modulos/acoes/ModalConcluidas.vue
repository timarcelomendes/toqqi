<script setup lang="ts">
// Todas as ações concluídas (o quadro mostra só as 15 mais recentes), com os mesmos filtros do quadro.
import { ref, watch } from 'vue'
import { CheckCircle2 } from 'lucide-vue-next'
import { acoesApi, mensagemDoErro, type Acao, type FiltrosAcoes } from '@/api'
import { formatarData } from '@/utils/datas'
import { plural } from '@/utils/formatos'
import Alerta from '@/components/ui/Alerta.vue'
import Carregando from '@/components/ui/Carregando.vue'
import EstadoVazio from '@/components/ui/EstadoVazio.vue'
import Modal from '@/components/ui/Modal.vue'
import Paginacao from '@/components/ui/Paginacao.vue'

const props = defineProps<{ filtros: FiltrosAcoes }>()
const aberto = defineModel<boolean>('aberto', { default: false })
const emit = defineEmits<{ abrir: [Acao] }>()

const itens = ref<Acao[]>([])
const total = ref(0)
const porPagina = ref(20)
const pagina = ref(1)
const carregando = ref(false)
const erro = ref<string | null>(null)

async function carregar() {
  carregando.value = true
  erro.value = null
  try {
    const r = await acoesApi.listar({ ...props.filtros, situacao: 'concluida', pagina: pagina.value })
    itens.value = r.itens
    total.value = r.total
    porPagina.value = r.por_pagina || 20
  } catch (e) {
    erro.value = mensagemDoErro(e)
  } finally {
    carregando.value = false
  }
}

watch(aberto, (v) => {
  if (!v) return
  pagina.value = 1
  carregar()
})
watch(pagina, () => aberto.value && carregar())

function abrir(a: Acao) {
  aberto.value = false
  emit('abrir', a)
}
</script>

<template>
  <Modal v-model:aberto="aberto" titulo="Ações concluídas" :descricao="total ? `${plural(total, 'ação concluída', 'ações concluídas')}, as mais recentes primeiro.` : undefined" tamanho="lg">
    <Carregando v-if="carregando && !itens.length" :linhas="4" rotulo="Carregando as ações concluídas" />
    <Alerta v-else-if="erro" tom="erro">{{ erro }} <button type="button" class="link ml-1" @click="carregar">Tentar de novo</button></Alerta>
    <EstadoVazio v-else-if="!itens.length" :icone="CheckCircle2" titulo="Nenhuma ação concluída" descricao="Quando uma ação for concluída, ela aparece aqui." />
    <template v-else>
      <ul class="-mx-1 flex flex-col divide-y divide-borda" :class="carregando ? 'opacity-60' : ''">
        <li v-for="a in itens" :key="String(a.id)">
          <button type="button" class="flex w-full flex-col gap-0.5 rounded-lg px-1 py-3 text-left hover:bg-superficie-2" @click="abrir(a)">
            <span class="text-sm font-semibold text-texto">{{ a.titulo }}</span>
            <span class="text-xs text-texto-fraco">
              {{ [a.empresa?.nome, `concluída em ${formatarData(a.concluida_em)}`, a.concluida_por ? `por ${a.concluida_por.nome}` : ''].filter(Boolean).join(' · ') }}
            </span>
            <span v-if="a.resolucao" class="line-clamp-2 text-xs text-texto-suave">{{ a.resolucao }}</span>
          </button>
        </li>
      </ul>
    </template>
    <Paginacao v-if="total > porPagina" v-model="pagina" class="-mx-5 -mb-5 mt-3 sm:-mx-6" :total="total" :por-pagina="porPagina" :carregando="carregando" nome-itens="ações concluídas" />
  </Modal>
</template>

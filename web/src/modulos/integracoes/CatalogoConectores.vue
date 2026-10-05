<script setup lang="ts">
// Etapa 5j: catálogo dos conectores (CRM e ERP). Uma grade de cartões pequenos — logo, nome, tipo e situação —
// e o detalhe de cada um (o que faz, conectar, sincronizar) num painel lateral, para a tela não crescer com cada
// sistema novo. "Em breve" mostra o que vem depois, sem botão.
import { computed, onMounted, ref, type Component } from 'vue'
import { conectoresApi, mensagemDoErro } from '@/api'
import Alerta from '@/components/ui/Alerta.vue'
import Etiqueta from '@/components/ui/Etiqueta.vue'
import PainelLateral from '@/components/ui/PainelLateral.vue'
import LogoParceiro from './LogoParceiro.vue'
import SecaoOmie from './SecaoOmie.vue'
import SecaoRdStation from './SecaoRdStation.vue'

interface Item {
  chave: string
  nome: string
  tipo: 'CRM' | 'ERP'
  iniciais: string
  resumo: string
  componente?: Component
}

const ITENS: Item[] = [
  { chave: 'rdstation', nome: 'RD Station CRM', tipo: 'CRM', iniciais: 'RD', resumo: 'Empresas e contatos do CRM; pesquisa no negócio ganho.', componente: SecaoRdStation },
  { chave: 'omie', nome: 'Omie', tipo: 'ERP', iniciais: 'OM', resumo: 'Clientes do ERP; pesquisa no pedido faturado.', componente: SecaoOmie },
  { chave: 'pipedrive', nome: 'Pipedrive', tipo: 'CRM', iniciais: 'PD', resumo: '' },
  { chave: 'hubspot', nome: 'HubSpot', tipo: 'CRM', iniciais: 'HS', resumo: '' },
  { chave: 'bling', nome: 'Bling', tipo: 'ERP', iniciais: 'BL', resumo: '' },
]

const conectados = ref<Record<string, boolean>>({})
const erro = ref<string | null>(null)
const aberto = ref(false)
const atual = ref<Item | null>(null)

async function carregar() {
  try {
    const r = await conectoresApi.ver()
    conectados.value = { rdstation: r.rdstation_crm.conectado, omie: r.omie.conectado }
    erro.value = null
  } catch (e) {
    erro.value = mensagemDoErro(e)
  }
}
function abrir(i: Item) {
  if (!i.componente) return
  atual.value = i
  aberto.value = true
}
const ordenados = computed(() =>
  [...ITENS].sort((a, b) => Number(!!b.componente) - Number(!!a.componente) || Number(!!conectados.value[b.chave]) - Number(!!conectados.value[a.chave])),
)
onMounted(carregar)
</script>

<template>
  <section class="flex flex-col gap-3" aria-labelledby="t-catalogo" data-catalogo-conectores>
    <header>
      <h2 id="t-catalogo" class="text-base font-bold text-texto">CRM e ERP</h2>
      <p class="text-sm text-texto-suave">Traga empresas e contatos do sistema que você já usa e mande a pesquisa sozinha quando uma venda acontece.</p>
    </header>
    <Alerta v-if="erro" tom="erro">{{ erro }} <button type="button" class="link" @click="carregar">Tentar de novo</button></Alerta>
    <ul class="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
      <li v-for="i in ordenados" :key="i.chave">
        <button
          type="button"
          class="cartao flex h-full w-full items-center gap-3 p-4 text-left transition-colors enabled:hover:border-borda-forte disabled:cursor-default disabled:opacity-60"
          :disabled="!i.componente"
          :aria-label="i.componente ? `${i.nome}: ${conectados[i.chave] ? 'gerenciar' : 'conectar'}` : `${i.nome}: em breve`"
          :data-conector="i.chave"
          @click="abrir(i)"
        >
          <LogoParceiro :chave="i.chave" :nome="i.nome" :iniciais="i.iniciais" />
          <span class="min-w-0 flex-1">
            <span class="flex flex-wrap items-center gap-x-2">
              <span class="font-semibold text-texto">{{ i.nome }}</span>
              <span class="text-xs text-texto-fraco">{{ i.tipo }}</span>
            </span>
            <span v-if="i.resumo" class="line-clamp-2 text-sm text-texto-suave">{{ i.resumo }}</span>
          </span>
          <Etiqueta v-if="!i.componente" tom="neutro">Em breve</Etiqueta>
          <Etiqueta v-else-if="conectados[i.chave]" tom="sucesso" ponto>Conectado</Etiqueta>
          <span v-else class="shrink-0 text-sm font-semibold text-marca-texto">Conectar</span>
        </button>
      </li>
    </ul>
    <PainelLateral v-model:aberto="aberto" :titulo="atual?.nome ?? ''" :descricao="atual ? `${atual.tipo} · ${atual.resumo}` : undefined" largura="lg">
      <component :is="atual.componente" v-if="atual?.componente" embutido @mudou="carregar" />
    </PainelLateral>
  </section>
</template>

<script setup lang="ts">
// Etapa 5j: catálogo dos conectores (CRM e ERP). Uma grade de cartões pequenos — logo, nome, tipo e situação —
// e o detalhe de cada um (o que faz, conectar, sincronizar) num painel lateral, para a tela não crescer com cada
// sistema novo. "Em breve" mostra o que vem depois, sem botão.
import { computed, onMounted, ref, type Component } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { avisar } from '@/composables/avisos'
import { conectoresApi, mensagemDoErro } from '@/api'
import Alerta from '@/components/ui/Alerta.vue'
import Etiqueta from '@/components/ui/Etiqueta.vue'
import PainelLateral from '@/components/ui/PainelLateral.vue'
import LogoParceiro from './LogoParceiro.vue'
import SecaoBling from './SecaoBling.vue'
import SecaoCrm from './SecaoCrm.vue'
import SecaoOmie from './SecaoOmie.vue'
import SecaoRdStation from './SecaoRdStation.vue'

interface Item {
  chave: string
  nome: string
  tipo: 'CRM' | 'ERP'
  iniciais: string
  resumo: string
  componente?: Component
  /** Props do componente (o Pipedrive e o HubSpot usam a mesma tela, pela chave). */
  props?: Record<string, unknown>
}

const ITENS: Item[] = [
  { chave: 'rdstation', nome: 'RD Station CRM', tipo: 'CRM', iniciais: 'RD', resumo: 'Empresas e contatos do CRM; pesquisa no negócio ganho e a nota de volta na negociação.', componente: SecaoRdStation },
  { chave: 'omie', nome: 'Omie', tipo: 'ERP', iniciais: 'OM', resumo: 'Clientes do ERP; pesquisa no pedido faturado.', componente: SecaoOmie },
  { chave: 'pipedrive', nome: 'Pipedrive', tipo: 'CRM', iniciais: 'PD', resumo: 'Empresas e contatos do CRM; pesquisa no negócio ganho e a nota de volta no negócio.', componente: SecaoCrm, props: { chave: 'pipedrive' } },
  { chave: 'hubspot', nome: 'HubSpot', tipo: 'CRM', iniciais: 'HS', resumo: 'Empresas e contatos do CRM; pesquisa no negócio ganho.', componente: SecaoCrm, props: { chave: 'hubspot' } },
  { chave: 'bling', nome: 'Bling', tipo: 'ERP', iniciais: 'BL', resumo: 'Clientes do ERP; pesquisa na nota emitida.', componente: SecaoBling },
]

const MENSAGENS_BLING: Record<string, string> = {
  negado: 'A autorização no Bling foi cancelada.',
  plano: 'O Plano Grátis não inclui os conectores. Assine um plano para conectar o Bling.',
}

const emit = defineEmits<{ irParaApi: [] }>()
const conectados = ref<Record<string, boolean>>({})
/** Conectores que dependem de configuração do Toqqi ainda ausente (ex.: o aplicativo no Bling). */
const indisponiveis = ref<Set<string>>(new Set())
const ativo = (i: Item) => !!i.componente && !indisponiveis.value.has(i.chave)
const erro = ref<string | null>(null)
const aberto = ref(false)
const atual = ref<Item | null>(null)

async function carregar() {
  try {
    const r = await conectoresApi.ver()
    conectados.value = {
      rdstation: r.rdstation_crm.conectado, omie: r.omie.conectado, bling: r.bling.conectado,
      pipedrive: r.pipedrive?.conectado ?? false, hubspot: r.hubspot?.conectado ?? false,
    }
    indisponiveis.value = new Set(r.bling.disponivel ? [] : ['bling'])
    erro.value = null
  } catch (e) {
    erro.value = mensagemDoErro(e)
  }
}
function abrir(i: Item) {
  if (!ativo(i)) return
  atual.value = i
  aberto.value = true
}
const ordenados = computed(() =>
  [...ITENS].sort((a, b) => Number(ativo(b)) - Number(ativo(a)) || Number(!!conectados.value[b.chave]) - Number(!!conectados.value[a.chave])),
)
// Volta da autorização do Bling: ?conector=bling&resultado=ok|erro|negado → aviso e o painel aberto.
const rota = useRoute()
const router = useRouter()
onMounted(() => {
  carregar()
  const { conector, resultado, ...resto } = rota.query
  if (conector === 'bling' && resultado) {
    if (resultado === 'ok') avisar.sucesso('Bling conectado. Traga os clientes com “Sincronizar agora”.')
    else if (resultado === 'movido') avisar.sucesso('Bling conectado. Ele estava ligado a outra conta do Toqqi e passou para esta.')
    else avisar.erro(MENSAGENS_BLING[String(resultado)] ?? 'Não conseguimos conectar o Bling. Tente de novo.')
    router.replace({ query: resto })
    const item = ITENS.find((i) => i.chave === 'bling')
    if (item) abrir(item)
  }
})
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
          :disabled="!ativo(i)"
          :aria-label="ativo(i) ? `${i.nome}: ${conectados[i.chave] ? 'gerenciar' : 'conectar'}` : `${i.nome}: em breve`"
          :data-conector="i.chave"
          @click="abrir(i)"
        >
          <LogoParceiro :chave="i.chave" :nome="i.nome" :iniciais="i.iniciais" />
          <span class="min-w-0 flex-1">
            <span class="flex flex-wrap items-center gap-x-2">
              <span class="font-semibold text-texto">{{ i.nome }}</span>
              <span class="text-xs text-texto-fraco">{{ i.tipo }}</span>
            </span>
            <span v-if="i.resumo && ativo(i)" class="line-clamp-2 text-sm text-texto-suave">{{ i.resumo }}</span>
          </span>
          <Etiqueta v-if="!ativo(i)" tom="neutro">Em breve</Etiqueta>
          <Etiqueta v-else-if="conectados[i.chave]" tom="sucesso" ponto>Conectado</Etiqueta>
          <span v-else class="shrink-0 text-sm font-semibold text-marca-texto">Conectar</span>
        </button>
      </li>
    </ul>
    <p class="text-sm text-texto-suave" data-outro-sistema>
      Usa outro sistema? Ligue pela API do Toqqi ou sem programar, com Zapier, Make ou n8n.
      <button type="button" class="link" @click="emit('irParaApi')">Ver como</button>
    </p>
    <PainelLateral v-model:aberto="aberto" :titulo="atual?.nome ?? ''" :descricao="atual ? `${atual.tipo} · ${atual.resumo}` : undefined" largura="lg">
      <component :is="atual.componente" v-if="atual?.componente" v-bind="atual.props ?? {}" embutido @mudou="carregar" />
    </PainelLateral>
  </section>
</template>

<script setup lang="ts">
// Crescimento › Depoimentos (melhoria 5, prova social): os comentários de promotores que autorizaram a publicação na
// tela final da pesquisa. A equipe aprova (pode publicar) ou oculta e copia o texto pronto, com a assinatura
// ("Ana, Mercado Azul"), para o site, as redes ou uma proposta.
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { Quote, Settings } from 'lucide-vue-next'
import { crescimentoApi, mensagemDoErro, type ConfigCrescimento, type Depoimento, type SituacaoDepoimento } from '@/api'
import { avisar } from '@/composables/avisos'
import { useSessaoStore } from '@/stores/sessao'
import { formatarData } from '@/utils/datas'
import Alerta from '@/components/ui/Alerta.vue'
import Botao from '@/components/ui/Botao.vue'
import BotaoCopiar from '@/components/ui/BotaoCopiar.vue'
import BotoesSegmentados from '@/components/ui/BotoesSegmentados.vue'
import Carregando from '@/components/ui/Carregando.vue'
import EstadoVazio from '@/components/ui/EstadoVazio.vue'
import Etiqueta from '@/components/ui/Etiqueta.vue'
import Paginacao from '@/components/ui/Paginacao.vue'
import { FILTROS_DEPOIMENTO, SITUACOES_DEPOIMENTO, textoDepoimento, type FiltroDepoimento } from './logica'

const props = defineProps<{ config: ConfigCrescimento | null }>()
const sessao = useSessaoStore()
const podeTratar = computed(() => sessao.pode('crescimento.tratar'))
const podeConfigurar = computed(() => sessao.pode('configuracoes.gerenciar'))
const desligado = computed(() => !!props.config && !props.config.depoimentos_ativos)

const filtro = ref<FiltroDepoimento>('pendente')
const pagina = ref(1)
const POR_PAGINA = 20
const itens = ref<Depoimento[]>([])
const total = ref(0)
const resumo = ref<Record<SituacaoDepoimento, number>>({ pendente: 0, aprovado: 0, oculto: 0 })
const carregando = ref(true)
const erro = ref<string | null>(null)
const ocupado = ref<Depoimento['resposta_id'] | null>(null)
let controle: AbortController | null = null

async function carregar() {
  controle?.abort()
  controle = new AbortController()
  carregando.value = true
  erro.value = null
  try {
    const r = await crescimentoApi.depoimentos(
      { situacao: filtro.value === 'todos' ? '' : filtro.value, pagina: pagina.value, por_pagina: POR_PAGINA },
      controle.signal,
    )
    itens.value = r.itens
    total.value = r.total
    resumo.value = r.resumo
  } catch (e) {
    if (e instanceof DOMException) return
    erro.value = mensagemDoErro(e)
  } finally {
    carregando.value = false
  }
}
watch(filtro, () => {
  if (pagina.value !== 1) pagina.value = 1
  else void carregar()
})
watch(pagina, () => void carregar(), { immediate: true })
onBeforeUnmount(() => controle?.abort())

const opcoes = computed(() =>
  FILTROS_DEPOIMENTO.map((f) => ({ valor: f.valor, rotulo: f.valor === 'todos' ? f.rotulo : `${f.rotulo} (${resumo.value[f.valor]})` })),
)

async function mudar(d: Depoimento, situacao: SituacaoDepoimento) {
  ocupado.value = d.resposta_id
  try {
    await crescimentoApi.alterarDepoimento(d.resposta_id, situacao)
    avisar.sucesso(situacao === 'aprovado' ? 'Depoimento aprovado: pode publicar.' : situacao === 'oculto' ? 'Depoimento ocultado.' : 'Depoimento voltou para revisão.')
    await carregar()
  } catch (e) {
    avisar.erro(mensagemDoErro(e))
  } finally {
    ocupado.value = null
  }
}
</script>

<template>
  <div class="flex flex-col gap-4" data-aba-depoimentos>
    <Alerta v-if="desligado" tom="info">
      O pedido de depoimento está desligado: os promotores não veem a pergunta no fim da pesquisa.
      <RouterLink v-if="podeConfigurar" to="/configuracoes/crescimento" class="link ml-1 inline-flex items-center gap-1"><Settings class="size-3.5" aria-hidden="true" /> Ligar em Configurações</RouterLink>
    </Alerta>

    <div class="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
      <BotoesSegmentados v-model="filtro" :opcoes="opcoes" rotulo="Situação dos depoimentos" bloco />
      <p class="text-sm text-texto-suave">Só aparecem os comentários que o cliente autorizou publicar.</p>
    </div>

    <Alerta v-if="erro" tom="erro">
      {{ erro }} <button type="button" class="link ml-1" @click="carregar">Tentar de novo</button>
    </Alerta>
    <Carregando v-else-if="carregando && !itens.length" :linhas="3" />
    <div v-else-if="!itens.length" class="cartao">
      <EstadoVazio
        :icone="Quote"
        :titulo="filtro === 'pendente' ? 'Nenhum depoimento para revisar' : 'Nenhum depoimento aqui'"
        descricao="Quando um promotor deixar um comentário e autorizar a publicação no fim da pesquisa, ele aparece aqui para você aprovar."
      />
    </div>
    <ul v-else class="grid gap-3 lg:grid-cols-2" :class="{ 'opacity-60': carregando }">
      <li v-for="d in itens" :key="d.resposta_id" class="cartao flex flex-col gap-3 p-5" data-depoimento>
        <div class="flex items-start justify-between gap-3">
          <Quote class="size-5 shrink-0 text-marca" aria-hidden="true" />
          <Etiqueta :tom="SITUACOES_DEPOIMENTO[d.situacao].tom" ponto>{{ SITUACOES_DEPOIMENTO[d.situacao].rotulo }}</Etiqueta>
        </div>
        <blockquote class="whitespace-pre-line text-base text-texto">“{{ d.comentario }}”</blockquote>
        <p class="text-sm font-semibold text-texto-suave">— {{ d.assinatura }}</p>
        <p class="text-xs text-texto-fraco">
          Nota {{ d.nota ?? '—' }}<template v-if="d.tipo_nota"> ({{ d.tipo_nota.toUpperCase() }})</template> · autorizado em {{ formatarData(d.autorizado_em) }}
        </p>
        <div class="mt-auto flex flex-wrap gap-2 border-t border-borda pt-3">
          <BotaoCopiar :texto="textoDepoimento(d)" rotulo="Copiar texto" tamanho="sm" />
          <template v-if="podeTratar">
            <Botao v-if="d.situacao !== 'aprovado'" tamanho="sm" :carregando="ocupado === d.resposta_id" @click="mudar(d, 'aprovado')">Aprovar</Botao>
            <Botao v-if="d.situacao !== 'oculto'" tamanho="sm" variante="fantasma" :desabilitado="ocupado === d.resposta_id" @click="mudar(d, 'oculto')">Ocultar</Botao>
          </template>
        </div>
      </li>
    </ul>
    <Paginacao v-if="!erro && total > POR_PAGINA" v-model="pagina" :total="total" :por-pagina="POR_PAGINA" :carregando="carregando" nome-itens="depoimentos" />
  </div>
</template>

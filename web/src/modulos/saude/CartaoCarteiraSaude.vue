<script setup lang="ts">
// Etapa 5i: "Carteira por saúde" no Início — quantas empresas ativas (e quanto de receita por mês) estão Saudáveis, em
// Atenção, em Risco ou Sem dados agora, com atalho para a lista filtrada; e as renovações em Risco dos próximos 60 dias.
// É o estado de hoje: segue o grupo do filtro, não o período.
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { RouterLink } from 'vue-router'
import { mensagemDoErro, saudeApi, type CarteiraSaude, type Id } from '@/api'
import { useSessaoStore } from '@/stores/sessao'
import { formatarMoeda, formatarNumero } from '@/utils/formatos'
import SeloSaude from './SeloSaude.vue'
import { FAIXAS_SAUDE, textoRenova } from './logica'

const props = defineProps<{ grupoId: Id | '' }>()
const sessao = useSessaoStore()
const podeVerEmpresas = computed(() => sessao.pode('contatos.ver'))
const dados = ref<CarteiraSaude | null>(null)
const erro = ref<string | null>(null)
let controle: AbortController | null = null

async function carregar() {
  controle?.abort()
  controle = new AbortController()
  erro.value = null
  try {
    dados.value = await saudeApi.carteira(props.grupoId, controle.signal)
  } catch (e) {
    if (e instanceof DOMException) return
    erro.value = mensagemDoErro(e)
  }
}
watch(() => props.grupoId, carregar, { immediate: true })
onBeforeUnmount(() => controle?.abort())

const maior = computed(() => Math.max(1, ...FAIXAS_SAUDE.map((f) => dados.value?.faixas[f.valor].empresas ?? 0)))
const COR = { risco: 'bg-erro', atencao: 'bg-atencao', saudavel: 'bg-sucesso', sem_dados: 'bg-borda-forte' }
</script>

<template>
  <section v-if="dados || erro" class="cartao flex flex-col gap-3 p-5 sm:p-6" aria-labelledby="t-carteira-saude" data-carteira-saude>
    <header>
      <h2 id="t-carteira-saude" class="text-base font-bold text-texto">Carteira por saúde</h2>
      <p class="text-sm text-texto-suave">As empresas ativas hoje, pela nota de saúde (respostas, decisor, silêncio e planos dos últimos 6 meses).</p>
    </header>
    <p v-if="erro" class="text-sm text-erro">{{ erro }} <button type="button" class="link" @click="carregar">Tentar de novo</button></p>
    <p v-else-if="dados && !dados.empresas" class="text-sm text-texto-suave">Cadastre as empresas dos seus clientes para ver a saúde da carteira.</p>
    <template v-else-if="dados">
      <p v-if="dados.renovacoes_em_risco.primeira" class="rounded-xl bg-erro-suave p-3 text-sm font-semibold text-erro" data-renovacao-risco>
        <template v-if="dados.renovacoes_em_risco.empresas === 1">
          {{ dados.renovacoes_em_risco.primeira.empresa.nome }}: {{ textoRenova(dados.renovacoes_em_risco.primeira.dias).toLowerCase() }} e está em Risco
          ({{ formatarMoeda(dados.renovacoes_em_risco.receita) }} por mês).
        </template>
        <template v-else>
          {{ dados.renovacoes_em_risco.empresas }} empresas em Risco renovam nos próximos 60 dias, somando {{ formatarMoeda(dados.renovacoes_em_risco.receita) }} por mês.
        </template>
      </p>
      <ul class="flex flex-col gap-2.5">
        <li v-for="f in FAIXAS_SAUDE" :key="f.valor" class="grid grid-cols-[7.5rem_minmax(0,1fr)_auto] items-center gap-3 text-sm">
          <RouterLink v-if="podeVerEmpresas" :to="{ path: '/contatos', query: { aba: 'empresas', saude: f.valor } }" class="rounded-full hover:opacity-80" :aria-label="`Ver as empresas: ${f.rotulo}`">
            <SeloSaude :faixa="f.valor" :nota="null" />
          </RouterLink>
          <SeloSaude v-else :faixa="f.valor" :nota="null" />
          <div class="h-2 rounded-full bg-superficie-2" aria-hidden="true">
            <div class="h-2 rounded-full" :class="COR[f.valor]" :style="{ width: `${(dados.faixas[f.valor].empresas / maior) * 100}%` }" />
          </div>
          <span class="text-right tabular-nums text-texto">
            <strong>{{ formatarNumero(dados.faixas[f.valor].empresas) }}</strong>
            <span class="text-texto-suave"> · {{ formatarMoeda(dados.faixas[f.valor].receita) }}</span>
          </span>
        </li>
      </ul>
      <p v-if="dados.sem_valor" class="text-xs text-texto-fraco">{{ dados.sem_valor }} {{ dados.sem_valor === 1 ? 'empresa sem valor mensal' : 'empresas sem valor mensal' }}.</p>
    </template>
  </section>
</template>

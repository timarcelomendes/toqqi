<script setup lang="ts">
// Etapa 5i: renovações dos próximos 60 dias (e as que passaram há até 30), com a saúde de cada empresa. As em Risco ou
// Atenção que renovam logo vêm primeiro: é a lista de quem visitar antes da renovação.
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { mensagemDoErro, saudeApi, type Id, type RenovacaoProxima } from '@/api'
import { formatarData } from '@/utils/datas'
import { formatarMoeda } from '@/utils/formatos'
import SeloSaude from './SeloSaude.vue'

const props = defineProps<{ grupoId: Id | '' }>()
const itens = ref<RenovacaoProxima[] | null>(null)
const erro = ref<string | null>(null)
let controle: AbortController | null = null

async function carregar() {
  controle?.abort()
  controle = new AbortController()
  erro.value = null
  try {
    itens.value = (await saudeApi.renovacoes(props.grupoId, controle.signal)).itens
  } catch (e) {
    if (e instanceof DOMException) return
    erro.value = mensagemDoErro(e)
  }
}
watch(() => props.grupoId, carregar, { immediate: true })
onBeforeUnmount(() => controle?.abort())

function quando(dias: number): string {
  if (dias < 0) return `passou há ${-dias} ${dias === -1 ? 'dia' : 'dias'} — atualize a data`
  if (dias === 0) return 'hoje'
  return dias === 1 ? 'amanhã' : `em ${dias} dias`
}
const vazio = computed(() => itens.value !== null && !itens.value.length)
</script>

<template>
  <section class="cartao" aria-labelledby="t-renovacoes" data-renovacoes>
    <div class="border-b border-borda px-4 py-3.5 sm:px-5">
      <h2 id="t-renovacoes" class="font-bold text-texto">Renovações nos próximos 60 dias</h2>
      <p class="text-sm text-texto-suave">Com a saúde de cada empresa. As em Risco ou Atenção vêm primeiro.</p>
    </div>
    <p v-if="erro" class="px-4 py-3 text-sm text-erro sm:px-5">{{ erro }} <button type="button" class="link" @click="carregar">Tentar de novo</button></p>
    <p v-else-if="vazio" class="px-4 py-4 text-sm text-texto-suave sm:px-5">
      Nenhuma renovação nos próximos 60 dias. Preencha “Renovação do contrato” em Editar empresa para acompanhar aqui.
    </p>
    <ul v-else-if="itens" class="divide-y divide-borda">
      <li v-for="r in itens" :key="String(r.empresa.id)" class="flex flex-col gap-1 px-4 py-3 sm:flex-row sm:items-center sm:justify-between sm:px-5" :class="r.destaque ? 'bg-erro-suave/40' : ''" data-renovacao>
        <div class="min-w-0">
          <p class="font-semibold text-texto [overflow-wrap:anywhere]">{{ r.empresa.nome }}</p>
          <p class="text-sm text-texto-suave">
            Renova em {{ formatarData(r.renovacao_em) }} · {{ quando(r.dias) }}<template v-if="r.responsavel"> · {{ r.responsavel.nome }}</template>
          </p>
          <p v-if="r.saude.porques[0]" class="text-xs text-texto-fraco">{{ r.saude.porques[0].texto }}</p>
        </div>
        <div class="flex shrink-0 items-center gap-2 text-sm">
          <span class="tabular-nums">{{ formatarMoeda(r.valor_mensal) }}</span>
          <SeloSaude :faixa="r.saude.faixa" :nota="r.saude.nota" />
        </div>
      </li>
    </ul>
  </section>
</template>

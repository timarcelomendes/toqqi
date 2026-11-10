<script setup lang="ts">
// Plataforma › Visão geral: o teste de homologação que o Bling pede para publicar o Toqqi na Central de Extensões.
// Roda com o Bling conectado na conta de quem clica (Integrações › Bling) e mostra cada passo: status, tempo e o
// intervalo desde o pedido anterior (o Bling aceita até 2 s entre os pedidos e 10 s no total).
import { ref } from 'vue'
import { mensagemDoErro, plataformaApi, type HomologacaoBling } from '@/api'
import Alerta from '@/components/ui/Alerta.vue'
import Botao from '@/components/ui/Botao.vue'

const LIMITE_INTERVALO = 2000
const LIMITE_TOTAL = 10000

const rodando = ref(false)
const resultado = ref<HomologacaoBling | null>(null)
const erro = ref<string | null>(null)

async function rodar() {
  rodando.value = true
  erro.value = null
  resultado.value = null
  try {
    resultado.value = await plataformaApi.homologacaoBling()
  } catch (e) {
    erro.value = mensagemDoErro(e)
  } finally {
    rodando.value = false
  }
}

const seg = (ms: number | null) => (ms === null ? '—' : `${(ms / 1000).toFixed(2).replace('.', ',')} s`)
</script>

<template>
  <section class="cartao flex flex-col gap-4 p-5" aria-labelledby="t-homologacao-bling" data-homologacao-bling>
    <div class="flex flex-wrap items-start justify-between gap-3">
      <div class="min-w-0 max-w-2xl">
        <h2 id="t-homologacao-bling" class="font-bold text-texto">Homologação do Bling</h2>
        <p class="text-sm text-texto-suave">
          O teste que o Bling pede para publicar o Toqqi na Central de Extensões. Primeiro inicie a homologação no portal do
          Bling (aba “Homologação” do aplicativo); depois clique aqui. Usa o Bling conectado nesta conta.
        </p>
      </div>
      <Botao :carregando="rodando" data-rodar-homologacao @click="rodar">Rodar o teste</Botao>
    </div>
    <Alerta v-if="erro" tom="erro">{{ erro }}</Alerta>
    <template v-if="resultado">
      <Alerta :tom="resultado.ok ? 'sucesso' : 'erro'" data-resultado-homologacao>
        <template v-if="resultado.ok">
          Os 5 passos passaram em {{ seg(resultado.total_ms) }}. Volte ao portal do Bling e clique em “Solicitar revisão”.
        </template>
        <template v-else>{{ resultado.erro }}</template>
      </Alerta>
      <table v-if="resultado.passos.length" class="w-full text-sm">
        <thead>
          <tr class="border-b border-borda text-left text-texto-suave">
            <th class="py-2 pr-3 font-semibold">Passo</th>
            <th class="py-2 pr-3 font-semibold">Status</th>
            <th class="py-2 pr-3 font-semibold">Tempo</th>
            <th class="py-2 font-semibold">Depois do anterior</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="p in resultado.passos" :key="p.passo" class="border-b border-borda">
            <td class="py-2 pr-3 text-texto">
              {{ p.passo }} <span class="text-texto-fraco">({{ p.metodo }})</span>
              <span v-if="p.renovou" class="ml-1 text-xs text-texto-fraco">· token renovado</span>
            </td>
            <td class="py-2 pr-3 tabular-nums" :class="p.status < 400 ? 'text-sucesso' : 'text-erro'">{{ p.status }}</td>
            <td class="py-2 pr-3 tabular-nums text-texto-suave">{{ seg(p.ms) }}</td>
            <td class="py-2 tabular-nums" :class="(p.intervalo_ms ?? 0) > LIMITE_INTERVALO ? 'font-semibold text-erro' : 'text-texto-suave'">
              {{ seg(p.intervalo_ms) }}
            </td>
          </tr>
        </tbody>
      </table>
      <p v-if="(resultado.total_ms ?? 0) > LIMITE_TOTAL" class="text-sm font-semibold text-erro">Passou de 10 s no total: rode de novo.</p>
    </template>
  </section>
</template>

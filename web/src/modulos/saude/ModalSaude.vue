<script setup lang="ts">
// Etapa 5i: a saúde de uma empresa — nota, porquês, renovação e "Como a nota é calculada" (os 6 critérios).
import { ref, watch } from 'vue'
import { CircleCheck, CircleMinus, CircleX } from 'lucide-vue-next'
import { mensagemDoErro, saudeApi, type Empresa, type SaudeEmpresa } from '@/api'
import { formatarData } from '@/utils/datas'
import Alerta from '@/components/ui/Alerta.vue'
import Botao from '@/components/ui/Botao.vue'
import Modal from '@/components/ui/Modal.vue'
import SeloSaude from './SeloSaude.vue'
import { textoRenova } from './logica'

const props = defineProps<{ empresa: Empresa | null }>()
const aberto = defineModel<boolean>('aberto', { default: false })
const saude = ref<SaudeEmpresa | null>(null)
const carregando = ref(false)
const erro = ref<string | null>(null)
const vazia = ref(false)

const ICONE_TOM = { positivo: CircleCheck, neutro: CircleMinus, negativo: CircleX }
const COR_TOM = { positivo: 'text-sucesso', neutro: 'text-texto-fraco', negativo: 'text-erro' }

async function carregar() {
  if (!props.empresa) return
  carregando.value = true
  erro.value = null
  try {
    const r = await saudeApi.empresa(props.empresa.id)
    saude.value = r.saude
    vazia.value = r.saude === null
  } catch (e) {
    erro.value = mensagemDoErro(e)
  } finally {
    carregando.value = false
  }
}
watch(aberto, (v) => {
  if (v) {
    saude.value = null
    carregar()
  }
})
</script>

<template>
  <Modal v-model:aberto="aberto" titulo="Saúde da conta" :descricao="empresa?.nome">
    <div class="flex flex-col gap-4" data-modal-saude>
      <p v-if="carregando" class="text-sm text-texto-suave" role="status">Calculando…</p>
      <Alerta v-else-if="erro" tom="erro">{{ erro }} <button type="button" class="link" @click="carregar">Tentar de novo</button></Alerta>
      <p v-else-if="vazia" class="text-sm text-texto-suave">A saúde só é calculada para empresas ativas.</p>
      <template v-else-if="saude">
        <div class="flex flex-wrap items-center gap-3">
          <span v-if="saude.nota !== null" class="text-4xl font-extrabold tabular-nums text-texto">{{ saude.nota }}</span>
          <SeloSaude :faixa="saude.faixa" :nota="null" />
          <span v-if="saude.renovacao" class="text-sm font-semibold" :class="saude.destaque ? 'text-erro' : 'text-texto-suave'">
            {{ textoRenova(saude.renovacao.dias) }} ({{ formatarData(saude.renovacao.em) }})
          </span>
        </div>
        <p v-if="saude.faixa === 'sem_dados'" class="text-sm text-texto-suave">Ainda não há respostas desta empresa. A nota aparece depois das primeiras respostas (ou 30 dias depois do primeiro convite).</p>
        <ul v-if="saude.porques.length" class="flex flex-col gap-2">
          <li v-for="p in saude.porques" :key="p.texto" class="flex items-start gap-2 text-sm text-texto">
            <component :is="ICONE_TOM[p.tom]" class="mt-0.5 size-4 shrink-0" :class="COR_TOM[p.tom]" aria-hidden="true" />
            {{ p.texto }}
          </li>
        </ul>
        <details v-if="saude.criterios.length" class="rounded-xl border border-borda p-3 text-sm">
          <summary class="cursor-pointer font-semibold text-texto">Como a nota é calculada</summary>
          <table class="mt-3 w-full">
            <thead class="text-left text-xs text-texto-suave">
              <tr><th scope="col" class="py-1 pr-2 font-semibold">Critério</th><th scope="col" class="px-2 py-1 text-right font-semibold">Pontos</th><th scope="col" class="py-1 pl-2 font-semibold">Por quê</th></tr>
            </thead>
            <tbody class="divide-y divide-borda">
              <tr v-for="c in saude.criterios" :key="c.criterio">
                <th scope="row" class="py-1.5 pr-2 text-left font-medium text-texto">{{ c.rotulo }}</th>
                <td class="whitespace-nowrap px-2 py-1.5 text-right tabular-nums">{{ c.pontos }} de {{ c.maximo }}</td>
                <td class="py-1.5 pl-2 text-texto-suave">{{ c.texto || '—' }}</td>
              </tr>
            </tbody>
          </table>
          <p class="mt-2 text-xs text-texto-fraco">Últimos 6 meses. Saudável a partir de 70; Atenção de 45 a 69; Risco abaixo de 45.</p>
        </details>
      </template>
    </div>
    <template #rodape>
      <Botao variante="secundario" @click="aberto = false">Fechar</Botao>
    </template>
  </Modal>
</template>

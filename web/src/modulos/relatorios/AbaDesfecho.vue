<script setup lang="ts">
// Etapa 5i: Relatórios › Desfecho. Quem saiu, por quê, o que dizia antes de sair (a prova de que o NPS antecipa a
// saída) e quanto da receita ficou (GRR e NRR). Os dados vêm de "Marcar como perdida" e do histórico do valor mensal
// que o banco grava a cada mudança.
import { computed } from 'vue'
import { RouterLink } from 'vue-router'
import { UserX } from 'lucide-vue-next'
import { relatoriosApi, type BlocoAntesDeSair, type GrupoAntesDeSair } from '@/api'
import { useSessaoStore } from '@/stores/sessao'
import { formatarData } from '@/utils/datas'
import { formatarMoeda, formatarNumero } from '@/utils/formatos'
import Alerta from '@/components/ui/Alerta.vue'
import EstadoVazio from '@/components/ui/EstadoVazio.vue'
import Etiqueta from '@/components/ui/Etiqueta.vue'
import { desfechoParaApi, type FiltrosRelatorioTela } from './logica'
import { usarRelatorio } from './usarRelatorio'

const props = defineProps<{ hoje: string; pronto: boolean }>()
const filtros = defineModel<FiltrosRelatorioTela>('filtros', { required: true })
const sessao = useSessaoStore()
const podeVerEmpresas = computed(() => sessao.pode('contatos.ver'))

const consulta = computed(() => desfechoParaApi(filtros.value, props.hoje))
const { dados, carregando, atualizando, erro, carregar } = usarRelatorio(
  (sinal) => relatoriosApi.desfecho(consulta.value, sinal),
  () => JSON.stringify(consulta.value),
  () => props.pronto,
)

const GRUPOS: { chave: GrupoAntesDeSair; rotulo: string; cor: string; tom: 'erro' | 'atencao' | 'sucesso' | 'neutro' }[] = [
  { chave: 'detrator', rotulo: 'Detrator', cor: 'bg-red-600', tom: 'erro' },
  { chave: 'neutro', rotulo: 'Neutro', cor: 'bg-amber-500', tom: 'atencao' },
  { chave: 'promotor', rotulo: 'Promotor', cor: 'bg-emerald-600', tom: 'sucesso' },
  { chave: 'sem_resposta', rotulo: 'Sem resposta', cor: 'bg-slate-300 dark:bg-slate-600', tom: 'neutro' },
]
const rotuloGrupo = (g: GrupoAntesDeSair) => GRUPOS.find((x) => x.chave === g)!

const pct = (v: number | null | undefined) => (v === null || v === undefined ? '—' : `${String(v).replace('.', ',')}%`)
const ret = computed(() => dados.value?.retencao ?? null)
const antes = computed(() => dados.value?.antes_de_sair ?? null)
/** A frase-prova: quantos % das perdidas eram detratoras × a carteira ativa. */
const frase = computed(() => {
  const a = antes.value
  if (!a || !a.perdidas.total) return null
  const p = a.perdidas.percentuais.detrator ?? 0
  const c = a.carteira.percentuais.detrator
  return `${pct(p)} das empresas que saíram deram nota de detrator nos 90 dias antes de sair.` +
    (c !== null ? ` Na carteira ativa, ${pct(c)}.` : '')
})
const barras = computed(() =>
  antes.value
    ? ([['Empresas que saíram', antes.value.perdidas], ['Carteira ativa', antes.value.carteira]] as [string, BlocoAntesDeSair][])
    : [],
)
const maxMotivo = computed(() => Math.max(1, ...(dados.value?.motivos ?? []).map((m) => m.empresas)))
</script>

<template>
  <div class="flex flex-col gap-4" :class="{ 'opacity-60 transition-opacity': atualizando }" data-aba-desfecho>
    <div v-if="carregando && !dados" class="grid gap-4 lg:grid-cols-3" role="status" aria-label="Carregando o desfecho">
      <div v-for="i in 3" :key="i" class="cartao h-32 animate-pulse p-5"><div class="h-3 w-1/3 rounded bg-superficie-2" /></div>
    </div>
    <Alerta v-else-if="erro && !dados" tom="erro">
      {{ erro }} <button type="button" class="link" @click="carregar">Tentar de novo</button>
    </Alerta>

    <template v-else-if="dados">
      <!-- Cartões -->
      <section class="grid gap-3 sm:grid-cols-3" aria-label="Resumo do desfecho">
        <div class="cartao p-4 sm:p-5" data-cartao-perdidas>
          <h2 class="text-sm font-semibold text-texto-suave">Empresas perdidas</h2>
          <p class="mt-1 text-3xl font-extrabold tabular-nums text-texto">{{ formatarNumero(dados.perdidas.empresas) }}</p>
          <p class="text-sm text-texto-suave">
            {{ formatarMoeda(dados.perdidas.receita_mensal) }} por mês
            <template v-if="dados.perdidas.sem_valor"> · {{ dados.perdidas.sem_valor }} sem valor</template>
          </p>
        </div>
        <div class="cartao p-4 sm:p-5" data-cartao-grr>
          <h2 class="text-sm font-semibold text-texto-suave">Receita mantida (GRR)</h2>
          <p class="mt-1 text-3xl font-extrabold tabular-nums text-texto">{{ pct(ret?.grr) }}</p>
          <p class="text-sm text-texto-suave">Da receita do início, quanto ficou tirando perdas e reduções.</p>
        </div>
        <div class="cartao p-4 sm:p-5" data-cartao-nrr>
          <h2 class="text-sm font-semibold text-texto-suave">Receita líquida (NRR)</h2>
          <p class="mt-1 text-3xl font-extrabold tabular-nums text-texto">{{ pct(ret?.nrr) }}</p>
          <p class="text-sm text-texto-suave">Como o GRR, somando os aumentos de valor.</p>
        </div>
      </section>

      <!-- O que diziam antes de sair -->
      <section class="cartao p-4 sm:p-5" aria-labelledby="t-antes" data-antes-de-sair>
        <h2 id="t-antes" class="font-bold text-texto">O que diziam antes de sair</h2>
        <p v-if="frase" class="mt-1 text-sm text-texto" data-frase-prova>{{ frase }}</p>
        <p v-else class="mt-1 text-sm text-texto-suave">A pior nota NPS de cada empresa nos 90 dias antes de sair, comparada com a carteira ativa hoje.</p>
        <Alerta v-if="antes?.amostra_pequena && dados.perdidas.empresas" tom="info" class="mt-3">Poucas perdas para comparar: a diferença ainda pode ser acaso.</Alerta>
        <div class="mt-4 flex flex-col gap-4">
          <div v-for="[rotulo, bloco] in barras" :key="rotulo">
            <p class="mb-1 flex justify-between text-sm"><span class="font-semibold text-texto">{{ rotulo }}</span><span class="text-texto-suave">{{ formatarNumero(bloco.total) }} empresas</span></p>
            <div class="flex h-3 w-full gap-0.5 overflow-hidden rounded-full bg-superficie-2" aria-hidden="true">
              <span v-for="g in GRUPOS" :key="g.chave" :class="g.cor" :style="{ flexGrow: bloco[g.chave], flexBasis: 0 }" />
            </div>
          </div>
        </div>
        <div class="mt-4 overflow-x-auto">
          <table class="w-full text-sm">
            <caption class="sr-only">O que diziam antes de sair, em percentuais</caption>
            <thead class="text-left text-xs text-texto-suave">
              <tr><th scope="col" class="py-1.5 pr-3 font-semibold"></th><th v-for="g in GRUPOS" :key="g.chave" scope="col" class="px-2 py-1.5 text-right font-semibold"><span class="inline-flex items-center gap-1.5"><span class="size-2.5 rounded-full" :class="g.cor" aria-hidden="true" />{{ g.rotulo }}</span></th></tr>
            </thead>
            <tbody class="divide-y divide-borda">
              <tr v-for="[rotulo, bloco] in barras" :key="rotulo">
                <th scope="row" class="py-2 pr-3 text-left font-semibold text-texto">{{ rotulo }}</th>
                <td v-for="g in GRUPOS" :key="g.chave" class="px-2 py-2 text-right tabular-nums">{{ pct(bloco.percentuais[g.chave]) }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      <div class="grid gap-4 lg:grid-cols-2">
        <!-- Ponte da receita -->
        <section v-if="ret" class="cartao p-4 sm:p-5" aria-labelledby="t-ponte" data-ponte>
          <h2 id="t-ponte" class="font-bold text-texto">Receita mensal da carteira</h2>
          <p v-if="!ret.inicio.empresas" class="mt-2 text-sm text-texto-suave" data-ponte-vazia>
            Ainda não dá para medir a retenção neste período: o Toqqi começou a guardar o valor mensal de cada empresa há pouco.
            Com o passar dos meses, aqui aparece quanto da receita do início ficou.
          </p>
          <template v-else>
          <p class="text-sm text-texto-suave">De {{ formatarData(ret.inicio.data) }} a {{ formatarData(dados.periodo.ate) }}, das {{ formatarNumero(ret.inicio.empresas) }} empresas que já eram clientes no início.</p>
          <dl class="mt-3 grid grid-cols-[1fr_auto] gap-x-4 gap-y-1.5 text-sm">
            <dt class="text-texto-suave">No início</dt><dd class="text-right font-semibold tabular-nums">{{ formatarMoeda(ret.inicio.receita) }}</dd>
            <dt class="text-texto-suave">Perdida</dt><dd class="text-right tabular-nums text-erro">− {{ formatarMoeda(ret.perdida) }}</dd>
            <dt class="text-texto-suave">Redução de valor</dt><dd class="text-right tabular-nums text-erro">− {{ formatarMoeda(ret.reducao) }}</dd>
            <dt class="text-texto-suave">Aumento de valor</dt><dd class="text-right tabular-nums text-sucesso">+ {{ formatarMoeda(ret.aumento) }}</dd>
            <dt class="border-t border-borda pt-1.5 font-semibold text-texto">No fim</dt><dd class="border-t border-borda pt-1.5 text-right font-bold tabular-nums">{{ formatarMoeda(ret.fim) }}</dd>
          </dl>
          <p v-if="ret.novas.empresas" class="mt-2 text-xs text-texto-fraco">Fora da conta: {{ formatarNumero(ret.novas.empresas) }} {{ ret.novas.empresas === 1 ? 'empresa nova' : 'empresas novas' }} no período, {{ formatarMoeda(ret.novas.receita) }} por mês.</p>
          <p v-if="ret.historico_parcial" class="mt-2 text-xs text-texto-fraco">O valor mensal só passou a ser guardado em outubro de 2026: antes disso, a conta usa o valor que cada empresa tinha naquele dia.</p>
          </template>
        </section>

        <!-- Motivos -->
        <section class="cartao p-4 sm:p-5" aria-labelledby="t-motivos" data-motivos>
          <h2 id="t-motivos" class="font-bold text-texto">Motivos</h2>
          <ul class="mt-3 flex flex-col gap-2.5">
            <li v-for="m in dados.motivos" :key="m.motivo" class="text-sm">
              <p class="flex justify-between gap-3"><span class="text-texto">{{ m.rotulo }}</span><span class="tabular-nums text-texto-suave">{{ m.empresas }} · {{ formatarMoeda(m.receita_mensal) }}</span></p>
              <div class="mt-1 h-2 rounded-full bg-superficie-2" aria-hidden="true"><div class="h-2 rounded-full bg-marca" :style="{ width: `${(m.empresas / maxMotivo) * 100}%` }" /></div>
            </li>
          </ul>
        </section>
      </div>

      <!-- Perdidas -->
      <section class="cartao" aria-labelledby="t-perdidas" data-perdidas>
        <div class="border-b border-borda px-4 py-3.5 sm:px-5"><h2 id="t-perdidas" class="font-bold text-texto">Empresas perdidas no período</h2></div>
        <EstadoVazio
          v-if="!dados.perdidas.itens.length"
          :icone="UserX"
          titulo="Nenhuma empresa perdida neste período"
          descricao="Quando um cliente sair, use “Marcar como perdida” no menu da empresa (Contatos › Empresas): é assim que o Toqqi mede a retenção."
        />
        <ul v-else class="divide-y divide-borda">
          <li v-for="p in dados.perdidas.itens" :key="String(p.empresa.id)" class="flex flex-col gap-1 px-4 py-3 sm:flex-row sm:items-center sm:justify-between sm:px-5" data-perdida>
            <div class="min-w-0">
              <p class="font-semibold text-texto [overflow-wrap:anywhere]">
                <RouterLink v-if="podeVerEmpresas" :to="{ path: '/relatorios/historico', query: { empresa_id: String(p.empresa.id) } }" class="hover:underline">{{ p.empresa.nome }}</RouterLink>
                <template v-else>{{ p.empresa.nome }}</template>
              </p>
              <p class="text-sm text-texto-suave">
                {{ formatarData(p.perdida_em) }} · {{ p.motivo_rotulo }}<template v-if="p.motivo_detalhe"> · “{{ p.motivo_detalhe }}”</template>
                <template v-if="p.responsavel"> · {{ p.responsavel.nome }}</template>
              </p>
            </div>
            <div class="flex shrink-0 flex-wrap items-center gap-2 text-sm">
              <span class="tabular-nums text-texto">{{ formatarMoeda(p.valor_mensal) }}</span>
              <Etiqueta :tom="rotuloGrupo(p.antes).tom">{{ rotuloGrupo(p.antes).rotulo }}<template v-if="p.ultima_nota"> ({{ p.ultima_nota.nota }})</template></Etiqueta>
              <Etiqueta v-if="p.plano_antes" tom="neutro">Teve plano de ação</Etiqueta>
            </div>
          </li>
        </ul>
      </section>
    </template>
  </div>
</template>

<script setup lang="ts">
// Relatórios (etapa 4b): 7 abas com os filtros comuns (período, grupo de empresas, só empresas ativas) e os de cada
// aba, tudo no endereço (dá para compartilhar o link). "Exportar CSV" para quem tem painel.exportar, nas abas com CSV.
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Download } from 'lucide-vue-next'
import { mensagemDoErro, relatoriosApi } from '@/api'
import { avisar } from '@/composables/avisos'
import { useCadastrosStore } from '@/stores/cadastros'
import { useSessaoStore } from '@/stores/sessao'
import { hojeIso } from '@/utils/datas'
import { PERIODOS, erroPeriodoEscolhido, intervaloDoPeriodo } from '@/utils/periodo'
import CabecalhoPagina from '@/components/app/CabecalhoPagina.vue'
import Abas from '@/components/ui/Abas.vue'
import Botao from '@/components/ui/Botao.vue'
import Campo from '@/components/ui/Campo.vue'
import Interruptor from '@/components/ui/Interruptor.vue'
import Selecao from '@/components/ui/Selecao.vue'
import AbaEmpresas from './AbaEmpresas.vue'
import AbaEntregas from './AbaEntregas.vue'
import AbaGrupos from './AbaGrupos.vue'
import AbaHistorico from './AbaHistorico.vue'
import AbaOperacao from './AbaOperacao.vue'
import AbaResponsaveis from './AbaResponsaveis.vue'
import AbaTemas from './AbaTemas.vue'
import {
  ABAS_RELATORIO,
  ABA_PADRAO,
  comunsParaApi,
  consultaDaAba,
  ehAba,
  empresasParaApi,
  entregasParaApi,
  filtrosDaQuery,
  mesmaBusca,
  periodoParaApi,
  queryDosFiltros,
  rotuloAba,
  type AbaRelatorio,
  type Consulta,
  type FiltrosRelatorioTela,
} from './logica'

const rota = useRoute()
const router = useRouter()
const sessao = useSessaoStore()
const cadastros = useCadastrosStore()
const hoje = hojeIso()

const abaDaRota = (): AbaRelatorio | null => (ehAba(rota.params.aba) ? rota.params.aba : null)
const aba = ref<AbaRelatorio>(abaDaRota() ?? ABA_PADRAO)
const filtros = ref<FiltrosRelatorioTela>(filtrosDaQuery(aba.value, rota.query as Consulta))
const descricao = computed(() => ABAS_RELATORIO.find((a) => a.valor === aba.value)?.descricao)

// Aba que não existe no endereço: abre Empresas, com os filtros comuns.
if (!abaDaRota()) router.replace({ name: 'relatorios', params: { aba: ABA_PADRAO }, query: queryDosFiltros(ABA_PADRAO, filtros.value) })

// ── Filtros ↔ endereço ──────────────────────────────────────────────────────
let vindoDaRota = false

function escreverEndereco() {
  const q = queryDosFiltros(aba.value, filtros.value)
  const atual = Object.fromEntries(Object.entries(rota.query).filter(([, v]) => typeof v === 'string')) as Record<string, string>
  if (JSON.stringify(q) !== JSON.stringify(atual) || rota.params.aba !== aba.value) {
    router.replace({ name: 'relatorios', params: { aba: aba.value }, query: q })
  }
}

watch(
  () => ({ ...filtros.value }),
  (novo, antigo) => {
    if (vindoDaRota) {
      vindoDaRota = false
      return
    }
    // Mudou um filtro (não só a página): volta para a página 1.
    if (antigo && !mesmaBusca(aba.value, novo, antigo) && novo.pagina !== 1) {
      filtros.value.pagina = 1
      return
    }
    escreverEndereco()
  },
)

// Endereço mudou por fora (troca de aba, voltar do navegador, link de outra tela): a tela acompanha.
watch(
  () => [rota.params.aba, rota.query] as const,
  () => {
    if (rota.name !== 'relatorios') return
    const nova = abaDaRota()
    if (!nova) {
      router.replace({ name: 'relatorios', params: { aba: ABA_PADRAO }, query: queryDosFiltros(ABA_PADRAO, filtros.value) })
      return
    }
    const f = filtrosDaQuery(nova, rota.query as Consulta)
    if (nova !== aba.value) aba.value = nova
    // Só marca "veio do endereço" quando algo muda de fato (senão o aviso ficaria esperando uma mudança que não vem).
    if (JSON.stringify(f) !== JSON.stringify({ ...filtros.value })) {
      vindoDaRota = true
      Object.assign(filtros.value, f)
    }
  },
)

/** Trocar de aba leva os filtros comuns (o período só se a pessoa escolheu um). Fica no histórico do navegador. */
const abaModelo = computed<AbaRelatorio>({
  get: () => aba.value,
  set: (nova) => {
    if (nova !== aba.value) router.push({ name: 'relatorios', params: { aba: nova }, query: consultaDaAba(nova, aba.value, filtros.value) })
  },
})

/** Ir para outra aba já com um filtro dela (ex.: o histórico de uma empresa clicada na matriz). */
function navegar(para: AbaRelatorio, extra: Partial<FiltrosRelatorioTela> = {}) {
  router.push({ name: 'relatorios', params: { aba: para }, query: consultaDaAba(para, aba.value, filtros.value, extra) })
}

// Título da aba do navegador com a aba do relatório (o roteador põe só "Relatórios" a cada mudança de endereço,
// inclusive quando só os filtros mudam: por isso o título acompanha o endereço todo).
watch(
  () => [aba.value, rota.fullPath] as const,
  ([a]) => {
    if (rota.name === 'relatorios') document.title = `${rotuloAba(a)} · Relatórios · Toqqi`
  },
  { immediate: true, flush: 'post' },
)

// ── Filtros comuns ──────────────────────────────────────────────────────────
// Datas escolhidas à mão: as duas, válidas e na ordem; senão, avisa no campo e não busca de novo.
const erroDatas = computed(() => (filtros.value.periodo === 'personalizado' ? erroPeriodoEscolhido(filtros.value.de, filtros.value.ate) : null))
const podeVerCadastros = computed(() => sessao.pode('contatos.ver'))
const opcoesGrupo = computed(() => {
  const opcoes = cadastros.listas.grupos.map((g) => ({ valor: g.id, rotulo: g.nome }))
  if (filtros.value.grupo_id !== '' && !opcoes.some((o) => String(o.valor) === String(filtros.value.grupo_id))) opcoes.unshift({ valor: filtros.value.grupo_id, rotulo: 'Grupo escolhido' })
  return opcoes
})
// "Escolher as datas" começa com o intervalo que estava valendo (os números não pulam).
watch(
  () => filtros.value.periodo,
  (novo, antigo) => {
    if (novo !== 'personalizado' || filtros.value.de || filtros.value.ate) return
    const r = intervaloDoPeriodo(antigo, {}, hoje)
    filtros.value.de = r.de ?? ''
    filtros.value.ate = r.ate ?? hoje
  },
)

/** Onde a aba pode pôr um filtro dela, na mesma linha dos filtros comuns. */
const alvoFiltrosAba = ref<HTMLElement | null>(null)

// ── Exportar ────────────────────────────────────────────────────────────────
const baixando = ref(false)
const csv = computed<{ rotulo: string } | null>(() => {
  if (!sessao.pode('painel.exportar')) return null
  if (aba.value === 'empresas' || aba.value === 'entregas' || aba.value === 'responsaveis') return { rotulo: 'Exportar CSV' }
  if (aba.value === 'operacao') return { rotulo: 'Exportar contatos sem resposta (CSV)' }
  if (aba.value === 'historico' && filtros.value.empresa_id !== '') return { rotulo: 'Exportar CSV' }
  return null
})

async function exportar() {
  if (erroDatas.value || baixando.value) return
  baixando.value = true
  try {
    if (aba.value === 'empresas') await relatoriosApi.baixarEmpresas(empresasParaApi(filtros.value, hoje))
    else if (aba.value === 'entregas') await relatoriosApi.baixarEntregas(entregasParaApi(filtros.value, hoje))
    else if (aba.value === 'responsaveis') await relatoriosApi.baixarResponsaveis(comunsParaApi(filtros.value, hoje))
    else if (aba.value === 'operacao') await relatoriosApi.baixarSemResposta(comunsParaApi(filtros.value, hoje))
    else if (aba.value === 'historico' && filtros.value.empresa_id !== '') await relatoriosApi.baixarHistorico(filtros.value.empresa_id, periodoParaApi(filtros.value, hoje))
  } catch (e) {
    avisar.erro(mensagemDoErro(e))
  } finally {
    baixando.value = false
  }
}

onMounted(() => {
  if (podeVerCadastros.value) cadastros.garantir(['grupos', 'segmentos', 'responsaveis'])
})
</script>

<template>
  <CabecalhoPagina titulo="Relatórios" :descricao="descricao">
    <template v-if="csv" #acoes>
      <Botao variante="secundario" :carregando="baixando" :desabilitado="!!erroDatas" @click="exportar">
        <Download v-if="!baixando" class="size-4" aria-hidden="true" /> {{ csv.rotulo }}
      </Botao>
    </template>
  </CabecalhoPagina>

  <Abas v-model="abaModelo" :abas="ABAS_RELATORIO" rotulo="Relatórios">
    <!-- Filtros comuns: uma linha acima de tudo o que a aba mostra -->
    <section class="mb-6 flex flex-col gap-3 sm:flex-row sm:flex-wrap sm:items-start" aria-label="Filtros do relatório">
      <Selecao v-model="filtros.periodo" rotulo="Período" :opcoes="PERIODOS" class="sm:w-52" />
      <div v-if="filtros.periodo === 'personalizado'" class="grid grid-cols-2 gap-3 sm:flex sm:gap-3">
        <Campo v-model="filtros.de" rotulo="De" tipo="date" :max="filtros.ate || hoje" class="sm:w-40" :erro="erroDatas && erroDatas.includes('inicial') ? erroDatas : null" />
        <Campo v-model="filtros.ate" rotulo="Até" tipo="date" :min="filtros.de || undefined" :max="hoje" class="sm:w-40" :erro="erroDatas && !erroDatas.includes('inicial') ? erroDatas : null" />
      </div>
      <!-- Filtro que a própria aba põe nesta linha (a busca da empresa, no histórico) -->
      <div ref="alvoFiltrosAba" class="contents" />
      <template v-if="aba !== 'historico'">
        <!-- A lista de grupos vem dos cadastros (contatos.ver): sem acesso, só aparece se já vier no endereço. -->
        <Selecao
          v-if="(podeVerCadastros && cadastros.listas.grupos.length) || filtros.grupo_id !== ''"
          v-model="filtros.grupo_id"
          rotulo="Grupo de empresas"
          :opcoes="opcoesGrupo"
          vazio="Todos os grupos"
          class="sm:w-56"
        />
        <div class="flex min-h-11 items-center sm:mt-7">
          <Interruptor v-model="filtros.so_ativos" rotulo="Só empresas ativas" class="w-full sm:w-auto sm:gap-3" />
        </div>
      </template>
    </section>

    <AbaEmpresas v-if="aba === 'empresas'" v-model:filtros="filtros" :hoje="hoje" :pronto="!erroDatas" @navegar="navegar" />
    <AbaGrupos v-else-if="aba === 'grupos'" v-model:filtros="filtros" :hoje="hoje" :pronto="!erroDatas" />
    <AbaTemas v-else-if="aba === 'temas'" v-model:filtros="filtros" :hoje="hoje" :pronto="!erroDatas" />
    <AbaEntregas v-else-if="aba === 'entregas'" v-model:filtros="filtros" :hoje="hoje" :pronto="!erroDatas" />
    <AbaResponsaveis v-else-if="aba === 'responsaveis'" v-model:filtros="filtros" :hoje="hoje" :pronto="!erroDatas" @navegar="navegar" />
    <AbaOperacao v-else-if="aba === 'operacao'" v-model:filtros="filtros" :hoje="hoje" :pronto="!erroDatas" />
    <AbaHistorico v-else v-model:filtros="filtros" :hoje="hoje" :pronto="!erroDatas" :alvo-filtros="alvoFiltrosAba" />
  </Abas>
</template>

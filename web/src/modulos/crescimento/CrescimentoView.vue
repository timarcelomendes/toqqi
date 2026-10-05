<script setup lang="ts">
// Crescimento (etapa 5c): "retenha quem está insatisfeito e cresça com quem está feliz". No topo, o resumo dos últimos
// 90 dias; nas abas, as Indicações (promotores que indicaram outras empresas) e as Oportunidades (clientes felizes para
// uma oferta). A aba e os filtros dela ficam no endereço (/crescimento/oportunidades?lista=promotores).
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Download, Settings, UserPlus } from 'lucide-vue-next'
import { crescimentoApi, mensagemDoErro, type ConfigCrescimento } from '@/api'
import { avisar } from '@/composables/avisos'
import { useCadastrosStore } from '@/stores/cadastros'
import { useSessaoStore } from '@/stores/sessao'
import { hojeIso } from '@/utils/datas'
import { erroPeriodoEscolhido, intervaloDoPeriodo } from '@/utils/periodo'
import CabecalhoPagina from '@/components/app/CabecalhoPagina.vue'
import Abas from '@/components/ui/Abas.vue'
import Botao from '@/components/ui/Botao.vue'
import AbaIndicacoes from './AbaIndicacoes.vue'
import AbaDepoimentos from './AbaDepoimentos.vue'
import AbaOportunidades from './AbaOportunidades.vue'
import ModalNovaIndicacao from './ModalNovaIndicacao.vue'
import ResumoCrescimento from './ResumoCrescimento.vue'
import {
  ABAS_CRESCIMENTO,
  ABA_PADRAO,
  FILTROS_INDICACOES_PADRAO,
  FILTROS_OPORTUNIDADES_PADRAO,
  ehAbaCrescimento,
  filtrosIndicacoesDaQuery,
  filtrosIndicacoesParaApi,
  filtrosOportunidadesDaQuery,
  filtrosOportunidadesParaApi,
  mesmaBuscaIndicacoes,
  mesmaBuscaOportunidades,
  queryDosFiltrosIndicacoes,
  queryDosFiltrosOportunidades,
  rotuloAbaCrescimento,
  type AbaCrescimento,
  type FiltrosIndicacoesTela,
  type FiltrosOportunidadesTela,
} from './logica'

type Consulta = Record<string, string | null | (string | null)[] | undefined>

const rota = useRoute()
const router = useRouter()
const sessao = useSessaoStore()
const cadastros = useCadastrosStore()
const hoje = hojeIso()
const podeTratar = computed(() => sessao.pode('crescimento.tratar'))
const podeExportar = computed(() => sessao.pode('painel.exportar'))

const abaDaRota = (): AbaCrescimento | null => (ehAbaCrescimento(rota.params.aba) ? rota.params.aba : null)
const aba = ref<AbaCrescimento>(abaDaRota() ?? ABA_PADRAO)
const consultaDaRota = () => rota.query as Consulta
const filtrosInd = ref<FiltrosIndicacoesTela>(aba.value === 'indicacoes' ? filtrosIndicacoesDaQuery(consultaDaRota()) : { ...FILTROS_INDICACOES_PADRAO })
const filtrosOp = ref<FiltrosOportunidadesTela>(aba.value === 'oportunidades' ? filtrosOportunidadesDaQuery(consultaDaRota()) : { ...FILTROS_OPORTUNIDADES_PADRAO })

// Aba que não existe no endereço: abre Indicações.
if (!abaDaRota()) router.replace({ name: 'crescimento', params: { aba: ABA_PADRAO } })

// ── Filtros ↔ endereço ──────────────────────────────────────────────────────
const queryDaAba = (a: AbaCrescimento): Record<string, string> =>
  a === 'indicacoes' ? queryDosFiltrosIndicacoes(filtrosInd.value) : a === 'oportunidades' ? queryDosFiltrosOportunidades(filtrosOp.value) : {}
function mesmaQuery(a: Record<string, string>, b: Record<string, string>): boolean {
  const ordenar = (q: Record<string, string>) => JSON.stringify(Object.entries(q).sort(([x], [y]) => x.localeCompare(y)))
  return ordenar(a) === ordenar(b)
}
function escreverEndereco() {
  const q = queryDaAba(aba.value)
  const atual = Object.fromEntries(Object.entries(rota.query).filter(([, v]) => typeof v === 'string')) as Record<string, string>
  if (!mesmaQuery(q, atual) || rota.params.aba !== aba.value) router.replace({ name: 'crescimento', params: { aba: aba.value }, query: q })
}

let vindoDaRota = false
watch(
  () => ({ ...filtrosInd.value }),
  (novo, antigo) => {
    if (aba.value !== 'indicacoes') return
    if (vindoDaRota) {
      vindoDaRota = false
      return
    }
    // Mudou um filtro (não só a página): volta para a página 1.
    if (antigo && !mesmaBuscaIndicacoes(novo, antigo) && novo.pagina !== 1) {
      filtrosInd.value.pagina = 1
      return
    }
    escreverEndereco()
  },
)
watch(
  () => ({ ...filtrosOp.value }),
  (novo, antigo) => {
    if (aba.value !== 'oportunidades') return
    if (vindoDaRota) {
      vindoDaRota = false
      return
    }
    if (antigo && !mesmaBuscaOportunidades(novo, antigo) && novo.pagina !== 1) {
      filtrosOp.value.pagina = 1
      return
    }
    escreverEndereco()
  },
)

// Endereço mudou por fora (troca de aba, voltar do navegador, atalho do assistente): a tela acompanha.
watch(
  () => [rota.params.aba, rota.query] as const,
  () => {
    if (rota.name !== 'crescimento') return
    const nova = abaDaRota()
    if (!nova) {
      router.replace({ name: 'crescimento', params: { aba: ABA_PADRAO } })
      return
    }
    if (nova !== aba.value) aba.value = nova
    // Compara pelo endereço (o id escolhido na lista é número; o do endereço, texto).
    if (nova === 'indicacoes') {
      const f = filtrosIndicacoesDaQuery(consultaDaRota())
      if (!mesmaQuery(queryDosFiltrosIndicacoes(f), queryDosFiltrosIndicacoes(filtrosInd.value))) {
        vindoDaRota = true
        filtrosInd.value = f
      }
    } else if (nova === 'oportunidades') {
      const f = filtrosOportunidadesDaQuery(consultaDaRota())
      if (!mesmaQuery(queryDosFiltrosOportunidades(f), queryDosFiltrosOportunidades(filtrosOp.value))) {
        vindoDaRota = true
        filtrosOp.value = f
      }
    }
  },
)

/** Trocar de aba guarda os filtros de cada uma (voltar para a outra aba volta como estava). Fica no histórico. */
const abaModelo = computed<AbaCrescimento>({
  get: () => aba.value,
  set: (nova) => {
    if (nova !== aba.value) router.push({ name: 'crescimento', params: { aba: nova }, query: queryDaAba(nova) })
  },
})

// Título da aba do navegador com a aba da tela (o roteador põe só "Crescimento" a cada mudança de endereço).
watch(
  () => [aba.value, rota.fullPath] as const,
  ([a]) => {
    if (rota.name === 'crescimento') document.title = `${rotuloAbaCrescimento(a)} · Crescimento · Toqqi`
  },
  { immediate: true, flush: 'post' },
)

// Datas escolhidas à mão (Indicações): as duas, válidas e na ordem; senão, avisa no campo e não busca de novo.
const erroDatas = computed(() =>
  filtrosInd.value.periodo === 'personalizado' ? erroPeriodoEscolhido(filtrosInd.value.de, filtrosInd.value.ate) : null,
)
// "Escolher as datas" começa com o intervalo que estava valendo.
watch(
  () => filtrosInd.value.periodo,
  (novo, antigo) => {
    if (novo !== 'personalizado' || filtrosInd.value.de || filtrosInd.value.ate) return
    const r = intervaloDoPeriodo(antigo, {}, hoje)
    filtrosInd.value.de = r.de ?? ''
    filtrosInd.value.ate = r.ate ?? hoje
  },
)

// ── Configuração (texto da oferta e se o convite está ligado) ───────────────
// Enquanto não chega (ou se falhar), "Oferecer" fica desligado e o vazio de Indicações não diz se o convite está
// ligado; com erro, as abas mostram o aviso com "Tentar de novo".
const config = ref<ConfigCrescimento | null>(null)
const erroConfig = ref<string | null>(null)
let carregandoConfig = false
async function carregarConfig() {
  if (carregandoConfig) return
  carregandoConfig = true
  erroConfig.value = null
  try {
    config.value = await crescimentoApi.configuracao()
  } catch (e) {
    erroConfig.value = mensagemDoErro(e)
  } finally {
    carregandoConfig = false
  }
}

// ── Ações do topo ───────────────────────────────────────────────────────────
const resumo = ref<InstanceType<typeof ResumoCrescimento> | null>(null)
const abaIndicacoes = ref<InstanceType<typeof AbaIndicacoes> | null>(null)
const novaAberta = ref(false)
const baixando = ref(false)

function aoMudar() {
  resumo.value?.recarregar()
}
function aoCriar() {
  abaIndicacoes.value?.recarregar()
  aoMudar()
}

async function exportar() {
  if (baixando.value || (aba.value === 'indicacoes' && erroDatas.value)) return
  baixando.value = true
  try {
    if (aba.value === 'indicacoes') await crescimentoApi.baixarIndicacoes(filtrosIndicacoesParaApi(filtrosInd.value, hoje))
    else await crescimentoApi.baixarOportunidades(filtrosOportunidadesParaApi(filtrosOp.value))
  } catch (e) {
    avisar.erro(mensagemDoErro(e))
  } finally {
    baixando.value = false
  }
}

onMounted(() => {
  void carregarConfig()
  if (sessao.pode('contatos.ver')) cadastros.garantir(['grupos', 'responsaveis'])
})
</script>

<template>
  <CabecalhoPagina
    titulo="Crescimento"
    descricao="Retenha quem está insatisfeito e cresça com quem está feliz: as indicações dos seus promotores e os clientes prontos para uma oferta."
  >
    <template #acoes>
      <!-- Como em Planos de ação: o atalho para a configuração do módulo (quem não pode mudar, consulta) -->
      <Botao variante="fantasma" para="/configuracoes/crescimento"><Settings class="size-4" aria-hidden="true" /> Convite e oferta</Botao>
      <Botao v-if="podeExportar && aba !== 'depoimentos'" variante="secundario" :carregando="baixando" :desabilitado="aba === 'indicacoes' && !!erroDatas" @click="exportar">
        <Download v-if="!baixando" class="size-4" aria-hidden="true" /> Exportar CSV
      </Botao>
      <Botao v-if="aba === 'indicacoes' && podeTratar" @click="novaAberta = true"><UserPlus class="size-4" aria-hidden="true" /> Registrar indicação</Botao>
    </template>
  </CabecalhoPagina>

  <ResumoCrescimento ref="resumo" />

  <Abas v-model="abaModelo" :abas="ABAS_CRESCIMENTO" rotulo="Crescimento">
    <AbaIndicacoes
      v-if="aba === 'indicacoes'"
      ref="abaIndicacoes"
      v-model:filtros="filtrosInd"
      :hoje="hoje"
      :pronto="!erroDatas"
      :erro-datas="erroDatas"
      :config="config"
      :erro-config="erroConfig"
      @mudou="aoMudar"
      @recarregar-config="carregarConfig"
    />
    <AbaOportunidades v-else-if="aba === 'oportunidades'" v-model:filtros="filtrosOp" :config="config" :erro-config="erroConfig" @mudou="aoMudar" @recarregar-config="carregarConfig" />
    <AbaDepoimentos v-else :config="config" />
  </Abas>

  <ModalNovaIndicacao v-model:aberto="novaAberta" @criada="aoCriar" />
</template>

<script setup lang="ts">
// Relatórios › Histórico de uma empresa: escolha a empresa; o cabeçalho traz os dados do cadastro, o NPS, o CSAT, a
// cobertura e as ações; depois a evolução do NPS mês a mês e a linha do tempo das respostas (nota, contato e cargo,
// canal, comentário, temas, resumo e sentimento da IA, ação). Aqui só o período vale (grupo e "só ativas" não se aplicam).
import { computed, reactive, ref, watch } from 'vue'
import { RouterLink } from 'vue-router'
import { AlertTriangle, ArrowRight, History, LineChart, MessageSquareText, SearchX, Sparkles, Table2 } from 'lucide-vue-next'
import { relatoriosApi, type ItemLinhaDoTempo, type Referencia } from '@/api'
import { useSessaoStore } from '@/stores/sessao'
import { formatarData } from '@/utils/datas'
import { formatarMoeda, formatarNumero, plural } from '@/utils/formatos'
import { CANAIS } from '@/utils/rotulos'
import BarraGrupos from '@/components/app/BarraGrupos.vue'
import Alerta from '@/components/ui/Alerta.vue'
import Botao from '@/components/ui/Botao.vue'
import EstadoVazio from '@/components/ui/EstadoVazio.vue'
import Etiqueta from '@/components/ui/Etiqueta.vue'
import SeloAcao from '@/modulos/acoes/SeloAcao.vue'
import CampoEmpresa from '@/modulos/contatos/CampoEmpresa.vue'
import GraficoEvolucao from '@/modulos/painel/GraficoEvolucao.vue'
import { faixaNps, formatarMedia2, formatarMes, formatarNps, formatarPct, tomCsat, tomNps } from '@/modulos/painel/logica'
import SeloNota from '@/modulos/respostas/SeloNota.vue'
import { SENTIMENTOS, ehSentimento } from '@/modulos/respostas/ia'
import { quandoFoiResposta, rotuloTema, seloOrigem } from '@/modulos/respostas/logica'
import { LIMITE_BUSCA, agruparPorMes, descreverTempoCliente, nomeDoCampo, periodoParaApi, type FiltrosRelatorioTela } from './logica'
import { usarRelatorio } from './usarRelatorio'

const props = defineProps<{
  hoje: string
  pronto: boolean
  /** Onde pôr a busca da empresa (a linha dos filtros comuns); sem ele, a busca fica no começo da aba. */
  alvoFiltros?: HTMLElement | null
}>()
const filtros = defineModel<FiltrosRelatorioTela>('filtros', { required: true })
const sessao = useSessaoStore()

const podeVerContatos = computed(() => sessao.pode('contatos.ver'))
const podeVerRespostas = computed(() => sessao.pode('respostas.ver'))
const podeVerAcoes = computed(() => sessao.pode('acoes.ver'))
const podeExportar = computed(() => sessao.pode('painel.exportar'))

// ── Empresa escolhida (o id fica no endereço; o nome vem da busca ou dos dados) ─────────────────────────────
const nomes = reactive<Record<string, string>>({})
const empresaId = computed(() => filtros.value.empresa_id)
const escolhida = computed<Referencia | null>({
  get: () => (empresaId.value === '' ? null : { id: empresaId.value, nome: nomes[String(empresaId.value)] ?? '' }),
  set: (r) => {
    if (r) nomes[String(r.id)] = r.nome
    filtros.value.empresa_id = r ? r.id : ''
  },
})

/** Sem acesso à lista de empresas (contatos.ver), a busca usa o próprio relatório de empresas (pelo nome). */
async function buscarNoRelatorio(termo: string, sinal: AbortSignal): Promise<Referencia[]> {
  const busca = termo.trim().slice(0, LIMITE_BUSCA)
  const r = await relatoriosApi.empresas({ ...(busca ? { busca } : {}), so_ativos: false, ordem: 'nome', por_pagina: 8 }, sinal)
  return r.itens.map((x) => ({ id: x.empresa.id, nome: x.empresa.nome }))
}
const fonte = computed(() => (podeVerContatos.value ? undefined : buscarNoRelatorio))

// ── Dados ───────────────────────────────────────────────────────────────────
const consulta = computed(() => periodoParaApi(filtros.value, props.hoje))
const { dados, carregando, atualizando, erro, statusErro, carregar } = usarRelatorio(
  (sinal) => relatoriosApi.historico(String(empresaId.value), consulta.value, sinal),
  () => JSON.stringify({ empresa: String(empresaId.value), ...consulta.value }),
  () => props.pronto && empresaId.value !== '',
)

/** Os dados na tela são sempre da empresa escolhida (trocando de empresa, mostra o esqueleto até chegar a nova). */
const atual = computed(() => (dados.value && empresaId.value !== '' && String(dados.value.empresa.id) === String(empresaId.value) ? dados.value : null))
watch(atual, (d) => {
  if (d) nomes[String(d.empresa.id)] = d.empresa.nome
})
// Outra empresa: o erro da anterior não vale para ela.
watch(empresaId, () => {
  erro.value = null
  statusErro.value = null
})

const naoEncontrada = computed(() => !atual.value && statusErro.value === 404)
const esperando = computed(() => empresaId.value !== '' && props.pronto && !atual.value && !erro.value)

// ── Cabeçalho ───────────────────────────────────────────────────────────────
const empresa = computed(() => atual.value?.empresa ?? null)
const tempoCliente = computed(() => descreverTempoCliente(empresa.value?.cliente_desde, props.hoje))
const faixa = computed(() => (atual.value?.nps.total ? faixaNps(atual.value.nps.faixa, atual.value.nps.valor) : null))
const COR_TOM: Record<string, string> = { sucesso: 'text-sucesso', atencao: 'text-atencao', erro: 'text-erro' }
const corNps = computed(() => COR_TOM[tomNps(atual.value?.nps.valor)] ?? 'text-texto')
const corCsat = computed(() => COR_TOM[tomCsat(atual.value?.csat?.percentual)] ?? 'text-texto')

const linkRespostas = computed(() => {
  if (!empresa.value) return undefined
  const q: Record<string, string> = { empresa_id: String(empresa.value.id) }
  if (consulta.value.de) q.de = consulta.value.de
  if (consulta.value.ate) q.ate = consulta.value.ate
  return { path: '/respostas', query: q }
})
const linkAcoes = computed(() => (empresa.value ? { path: '/planos-de-acao', query: { empresa_id: String(empresa.value.id) } } : undefined))

const evolucaoEmTabela = ref(false)

// ── Linha do tempo ──────────────────────────────────────────────────────────
const meses = computed(() => agruparPorMes(atual.value?.linha_do_tempo ?? []))
const cortada = computed(() => !!atual.value && atual.value.total > atual.value.linha_do_tempo.length)

function contatoDe(r: ItemLinhaDoTempo): string {
  if (!r.contato) return ''
  return [nomeDoCampo(r.contato.cargo), nomeDoCampo(r.contato.perfil)].filter(Boolean).join(' · ')
}
const sentimentoDe = (r: ItemLinhaDoTempo) => (r.ia && ehSentimento(r.ia.sentimento) ? SENTIMENTOS[r.ia.sentimento] : null)
const rotuloCanal = (c: string) => CANAIS[c as keyof typeof CANAIS] ?? c
const rotuloTipo = (t: string | null) => (t === 'nps' ? 'NPS' : t === 'csat' ? 'CSAT' : null)
function linkResposta(r: ItemLinhaDoTempo) {
  return { path: '/respostas', query: { empresa_id: String(empresa.value?.id ?? ''), analisar: String(r.resposta_id) } }
}
</script>

<template>
  <div class="flex flex-col gap-4">
    <!-- Qual empresa (na linha dos filtros, ao lado do período) -->
    <Teleport :to="alvoFiltros ?? 'body'" :disabled="!alvoFiltros">
      <div class="w-full sm:w-80">
        <CampoEmpresa v-model="escolhida" rotulo="Empresa" placeholder="Digite o nome da empresa" :fonte="fonte" />
      </div>
    </Teleport>

    <div v-if="empresaId === ''" class="cartao">
      <EstadoVazio
        :icone="History"
        titulo="Escolha uma empresa"
        descricao="Busque pelo nome no campo acima para ver tudo o que ela respondeu: notas, comentários, temas e ações, mês a mês. Também dá para abrir pelo nome da empresa nas abas Empresas e Responsáveis."
      />
    </div>

    <div v-else-if="naoEncontrada" class="cartao">
      <EstadoVazio :icone="SearchX" titulo="Empresa não encontrada" descricao="Ela pode ter sido excluída, ou o link está incompleto. Busque a empresa pelo nome no campo acima." />
    </div>

    <Alerta v-else-if="erro && !atual" tom="erro">
      {{ erro }} <button type="button" class="link ml-1" @click="carregar">Tentar de novo</button>
    </Alerta>

    <!-- Carregando (primeira vez ou outra empresa) -->
    <div v-else-if="esperando || (carregando && !atual)" class="flex flex-col gap-4" role="status" aria-label="Carregando o histórico da empresa">
      <div class="cartao h-36 animate-pulse p-6">
        <div class="h-5 w-1/3 rounded bg-superficie-2" />
        <div class="mt-3 h-3 w-1/4 rounded bg-superficie-2" />
        <div class="mt-6 h-3 w-2/3 rounded bg-superficie-2" />
      </div>
      <div class="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <div v-for="i in 4" :key="i" class="cartao h-32 animate-pulse p-5">
          <div class="h-3 w-1/2 rounded bg-superficie-2" />
          <div class="mt-4 h-8 w-1/3 rounded bg-superficie-2" />
        </div>
      </div>
      <span class="sr-only">Carregando…</span>
    </div>

    <div v-else-if="atual && empresa" class="flex flex-col gap-4 transition-opacity" :class="atualizando ? 'opacity-60' : ''" :aria-busy="atualizando || undefined">
      <Alerta v-if="erro" tom="erro">
        Não deu para atualizar com o período novo: {{ erro }} <button type="button" class="link ml-1" @click="carregar">Tentar de novo</button>
      </Alerta>

      <!-- Dados do cadastro -->
      <section class="cartao flex flex-col gap-4 p-5 sm:p-6" aria-labelledby="t-hist-nome">
        <div class="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
          <div class="min-w-0">
            <h2 id="t-hist-nome" class="flex flex-wrap items-center gap-x-2 gap-y-1 text-xl font-bold text-texto">
              <span class="break-words">{{ empresa.nome }}</span>
              <Etiqueta v-if="!empresa.ativa">Inativa</Etiqueta>
            </h2>
            <p class="text-sm text-texto-suave">Histórico de respostas da empresa no período escolhido.</p>
          </div>
          <Botao v-if="podeVerRespostas && linkRespostas" variante="secundario" tamanho="sm" class="shrink-0 self-start" :para="linkRespostas">
            Ver as respostas <ArrowRight class="size-4" aria-hidden="true" />
          </Botao>
        </div>
        <dl class="grid grid-cols-2 gap-x-6 gap-y-3 text-sm sm:grid-cols-3 xl:grid-cols-5">
          <div class="min-w-0">
            <dt class="text-texto-fraco">Grupo</dt>
            <dd class="truncate font-semibold" :class="empresa.grupo ? 'text-texto' : 'text-texto-fraco'">{{ empresa.grupo?.nome ?? 'Sem grupo' }}</dd>
          </div>
          <div class="min-w-0">
            <dt class="text-texto-fraco">Segmento</dt>
            <dd class="truncate font-semibold" :class="empresa.segmento ? 'text-texto' : 'text-texto-fraco'">{{ empresa.segmento?.nome ?? 'Sem segmento' }}</dd>
          </div>
          <div class="min-w-0">
            <dt class="text-texto-fraco">Responsável</dt>
            <dd class="truncate font-semibold" :class="empresa.responsavel ? 'text-texto' : 'text-texto-fraco'">{{ empresa.responsavel?.nome ?? 'Sem responsável' }}</dd>
          </div>
          <div class="min-w-0">
            <dt class="text-texto-fraco">Valor mensal</dt>
            <dd class="font-semibold tabular-nums" :class="empresa.valor_mensal !== null ? 'text-texto' : 'text-texto-fraco'">{{ formatarMoeda(empresa.valor_mensal, 'Não informado') }}</dd>
          </div>
          <div class="min-w-0">
            <dt class="text-texto-fraco">Cliente desde</dt>
            <dd class="font-semibold" :class="empresa.cliente_desde ? 'text-texto' : 'text-texto-fraco'">
              {{ empresa.cliente_desde ? formatarData(empresa.cliente_desde) : 'Não informado' }}
              <span v-if="tempoCliente" class="block text-xs font-normal text-texto-fraco">{{ tempoCliente }}</span>
            </dd>
          </div>
        </dl>
      </section>

      <!-- Números do período -->
      <div class="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <section class="cartao flex flex-col gap-2 p-5" aria-labelledby="t-hist-nps">
          <h3 id="t-hist-nps" class="text-sm font-semibold text-texto-suave">NPS</h3>
          <template v-if="atual.nps.total && atual.nps.valor !== null">
            <p class="flex flex-wrap items-center gap-2">
              <span class="text-4xl font-extrabold leading-none tabular-nums" :class="corNps">{{ formatarNps(atual.nps.valor) }}</span>
              <Etiqueta v-if="faixa" :tom="faixa.tom">{{ faixa.rotulo }}</Etiqueta>
            </p>
            <BarraGrupos legenda="compacta" fina :detratores="atual.nps.detratores" :neutros="atual.nps.neutros" :promotores="atual.nps.promotores" />
          </template>
          <template v-else>
            <p class="text-4xl font-extrabold leading-none text-texto-fraco" aria-hidden="true">—</p>
            <p class="text-sm text-texto-suave">Nenhuma resposta de NPS no período.</p>
          </template>
        </section>

        <section class="cartao flex flex-col gap-2 p-5" aria-labelledby="t-hist-csat">
          <h3 id="t-hist-csat" class="text-sm font-semibold text-texto-suave">Satisfação (CSAT)</h3>
          <template v-if="atual.csat && atual.csat.total && atual.csat.percentual !== null">
            <p class="text-4xl font-extrabold leading-none tabular-nums" :class="corCsat">{{ formatarPct(atual.csat.percentual) }}</p>
            <p class="text-sm text-texto-suave">deram nota 4 ou 5</p>
            <p class="text-xs text-texto-fraco">Média {{ formatarMedia2(atual.csat.media) }} de 5 · {{ plural(atual.csat.total, 'resposta', 'respostas') }}</p>
          </template>
          <template v-else>
            <p class="text-4xl font-extrabold leading-none text-texto-fraco" aria-hidden="true">—</p>
            <p class="text-sm text-texto-suave">Nenhuma resposta de satisfação (nota de 1 a 5) no período.</p>
          </template>
        </section>

        <section class="cartao flex flex-col gap-2 p-5" aria-labelledby="t-hist-cobertura">
          <h3 id="t-hist-cobertura" class="text-sm font-semibold text-texto-suave">Cobertura</h3>
          <template v-if="atual.cobertura.contatos_ativos > 0">
            <p class="text-4xl font-extrabold leading-none tabular-nums text-texto">{{ formatarPct(atual.cobertura.percentual) }}</p>
            <p class="text-sm text-texto-suave">
              {{ formatarNumero(atual.cobertura.responderam) }} de {{ plural(atual.cobertura.contatos_ativos, 'contato ativo', 'contatos ativos') }}
              {{ atual.cobertura.responderam === 1 ? 'respondeu' : 'responderam' }} o NPS
            </p>
          </template>
          <template v-else>
            <p class="text-4xl font-extrabold leading-none text-texto-fraco" aria-hidden="true">—</p>
            <p class="text-sm text-texto-suave">A empresa não tem contatos ativos.</p>
          </template>
        </section>

        <section class="cartao flex flex-col gap-2 p-5" aria-labelledby="t-hist-acoes">
          <h3 id="t-hist-acoes" class="text-sm font-semibold text-texto-suave">Ações</h3>
          <p class="flex flex-wrap items-center gap-2">
            <span class="text-4xl font-extrabold leading-none tabular-nums text-texto">{{ formatarNumero(atual.acoes.abertas) }}</span>
            <span class="text-sm text-texto-suave">{{ atual.acoes.abertas === 1 ? 'aberta agora' : 'abertas agora' }}</span>
          </p>
          <p class="flex flex-wrap items-center gap-x-2 gap-y-1 text-sm text-texto-suave">
            <Etiqueta v-if="atual.acoes.vencidas" tom="erro" ponto>{{ plural(atual.acoes.vencidas, 'vencida', 'vencidas') }}</Etiqueta>
            <span>{{ plural(atual.acoes.concluidas, 'concluída', 'concluídas') }} no período</span>
          </p>
          <RouterLink v-if="podeVerAcoes && linkAcoes" :to="linkAcoes" class="link mt-auto inline-flex min-h-10 items-center gap-1 self-start text-sm">
            Ver no quadro <ArrowRight class="size-4" aria-hidden="true" />
          </RouterLink>
        </section>
      </div>

      <!-- Evolução -->
      <section class="cartao flex min-w-0 flex-col gap-3 p-5 sm:p-6" aria-labelledby="t-hist-evolucao">
        <header class="flex items-start justify-between gap-3">
          <div class="min-w-0">
            <h3 id="t-hist-evolucao" class="text-base font-bold text-texto">Evolução do NPS</h3>
            <p class="text-sm text-texto-suave">Mês a mês, nos meses com respostas (até os 24 mais recentes).</p>
          </div>
          <button
            v-if="atual.evolucao.length"
            type="button"
            class="-mr-2 inline-flex h-10 shrink-0 items-center gap-1.5 rounded-xl px-3 text-sm font-semibold text-texto-suave hover:bg-superficie-2 hover:text-texto"
            :aria-pressed="evolucaoEmTabela"
            @click="evolucaoEmTabela = !evolucaoEmTabela"
          >
            <LineChart v-if="evolucaoEmTabela" class="size-4" aria-hidden="true" />
            <Table2 v-else class="size-4" aria-hidden="true" />
            {{ evolucaoEmTabela ? 'Ver gráfico' : 'Ver em tabela' }}
          </button>
        </header>
        <GraficoEvolucao v-if="atual.evolucao.length" v-model:tabela="evolucaoEmTabela" :pontos="atual.evolucao" />
        <p v-else class="rounded-xl bg-superficie-2 p-4 text-sm text-texto-suave">Nenhuma resposta de NPS no período para mostrar a evolução.</p>
      </section>

      <!-- Linha do tempo -->
      <section class="cartao" aria-labelledby="t-hist-linha" data-linha-do-tempo>
        <header class="border-b border-borda p-5 sm:px-6">
          <h3 id="t-hist-linha" class="text-base font-bold text-texto">Linha do tempo</h3>
          <p class="text-sm text-texto-suave">{{ plural(atual.total, 'resposta', 'respostas') }} no período, da mais recente para a mais antiga.</p>
        </header>
        <p v-if="cortada" class="flex items-start gap-2 border-b border-borda bg-atencao-suave/50 px-5 py-2.5 text-sm text-texto-suave sm:px-6">
          <AlertTriangle class="mt-0.5 size-4 shrink-0 text-atencao" aria-hidden="true" />
          <span>
            Mostrando as {{ formatarNumero(atual.linha_do_tempo.length) }} mais recentes de {{ formatarNumero(atual.total) }}. Para ver as outras, escolha um período menor<template v-if="podeExportar"> ou exporte o CSV</template>.
          </span>
        </p>

        <EstadoVazio v-if="!atual.linha_do_tempo.length" :icone="MessageSquareText" titulo="Nenhuma resposta no período" descricao="Escolha um período maior (ou Tudo) para ver as respostas mais antigas." />

        <template v-else>
          <section v-for="g in meses" :key="g.mes || 'sem-data'" :aria-labelledby="`hist-mes-${g.mes || 'sem-data'}`">
            <h4 :id="`hist-mes-${g.mes || 'sem-data'}`" class="border-b border-borda bg-superficie-2/60 px-5 py-2 text-xs font-semibold uppercase tracking-wide text-texto-fraco sm:px-6">
              {{ g.mes ? formatarMes(g.mes, 'longo') : 'Sem data' }} · {{ plural(g.itens.length, 'resposta', 'respostas') }}
            </h4>
            <ol class="flex flex-col divide-y divide-borda">
              <li v-for="r in g.itens" :key="String(r.resposta_id)" class="flex gap-3 px-5 py-4 sm:gap-4 sm:px-6">
                <SeloNota :nota="r.nota" :grupo="r.grupo" :tipo="r.tipo_nota" />
                <div class="flex min-w-0 flex-1 flex-col gap-2">
                  <div class="flex flex-col gap-0.5 sm:flex-row sm:items-baseline sm:justify-between sm:gap-3">
                    <p class="min-w-0 text-sm">
                      <span class="font-semibold text-texto">{{ r.contato?.nome ?? 'Sem contato identificado' }}</span>
                      <span v-if="contatoDe(r)" class="text-texto-suave"> · {{ contatoDe(r) }}</span>
                    </p>
                    <p class="shrink-0 text-xs text-texto-fraco">
                      <time :datetime="r.data">{{ quandoFoiResposta(r) }}</time> · {{ rotuloCanal(r.canal) }}<template v-if="rotuloTipo(r.tipo_nota)"> · {{ rotuloTipo(r.tipo_nota) }}</template>
                    </p>
                  </div>

                  <blockquote v-if="r.comentario" class="whitespace-pre-line break-words border-l-2 border-borda-forte pl-3 text-sm text-texto">{{ r.comentario }}</blockquote>
                  <p v-else class="text-sm text-texto-fraco">Sem comentário.</p>

                  <div v-if="r.ia && (r.ia.resumo || sentimentoDe(r))" class="flex items-start gap-2 rounded-lg bg-superficie-2 px-3 py-2 text-sm" data-ia>
                    <Sparkles class="mt-0.5 size-4 shrink-0 text-texto-fraco" aria-hidden="true" />
                    <p class="min-w-0 flex-1">
                      <span class="sr-only">Análise da IA: </span>
                      <Etiqueta v-if="sentimentoDe(r)" :tom="sentimentoDe(r)!.tom" ponto class="mr-1.5 align-middle">{{ sentimentoDe(r)!.rotulo }}</Etiqueta>
                      <span v-if="r.ia.resumo" class="text-texto-suave">{{ r.ia.resumo }}</span>
                    </p>
                  </div>

                  <div v-if="r.temas.length || seloOrigem(r.origem) || r.acao || podeVerRespostas" class="flex flex-wrap items-center gap-x-3 gap-y-2">
                    <span v-if="r.temas.length" class="flex flex-wrap gap-1">
                      <span class="sr-only">Temas: </span>
                      <Etiqueta v-for="t in r.temas" :key="t" tom="info">{{ rotuloTema(t) }}</Etiqueta>
                    </span>
                    <Etiqueta v-if="seloOrigem(r.origem)">{{ seloOrigem(r.origem) }}</Etiqueta>
                    <span v-if="r.acao" class="inline-flex items-center gap-1.5 text-xs text-texto-fraco">
                      Ação: <SeloAcao :acao="{ ...r.acao, prazo: null, prazo_selo: null }" :link="podeVerAcoes" compacto />
                    </span>
                    <RouterLink v-if="podeVerRespostas" :to="linkResposta(r)" class="link ml-auto inline-flex min-h-8 items-center text-sm">
                      Abrir a resposta<span class="sr-only"> de {{ formatarData(r.data) }}</span>
                    </RouterLink>
                  </div>
                </div>
              </li>
            </ol>
          </section>
        </template>
      </section>
    </div>
  </div>
</template>

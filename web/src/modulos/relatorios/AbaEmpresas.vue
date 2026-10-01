<script setup lang="ts">
// Relatórios › Empresas: cartões (empresas com respostas, cobertura, receita em risco, empresas por faixa de NPS),
// a matriz NPS × valor com a contagem por quadrante (que também filtra a tabela) e a tabela das empresas, com
// filtros, ordenação e paginação. No celular, a tabela vira cartões.
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { Building2, History, Search, SlidersHorizontal, X } from 'lucide-vue-next'
import { relatoriosApi, type Id, type Quadrante } from '@/api'
import { useCadastrosStore } from '@/stores/cadastros'
import { useSessaoStore } from '@/stores/sessao'
import { formatarData } from '@/utils/datas'
import { formatarMoeda, formatarNumero, plural } from '@/utils/formatos'
import BarraGrupos from '@/components/app/BarraGrupos.vue'
import Alerta from '@/components/ui/Alerta.vue'
import Botao from '@/components/ui/Botao.vue'
import Campo from '@/components/ui/Campo.vue'
import EstadoVazio from '@/components/ui/EstadoVazio.vue'
import Etiqueta from '@/components/ui/Etiqueta.vue'
import Paginacao from '@/components/ui/Paginacao.vue'
import Selecao from '@/components/ui/Selecao.vue'
import Tabela, { type Coluna } from '@/components/ui/Tabela.vue'
import { FAIXAS_NPS, formatarPct } from '@/modulos/painel/logica'
import MatrizNpsValor from './MatrizNpsValor.vue'
import SeloNps from './SeloNps.vue'
import {
  FAIXAS_TEMPO,
  FAIXAS_VALOR,
  LIMITE_BUSCA,
  ORDEM_QUADRANTES,
  ORDENS_EMPRESAS,
  QUADRANTES,
  contarFiltrosDaAba,
  empresasParaApi,
  numero,
  partesMoedaCurta,
  type AbaRelatorio,
  type FiltrosRelatorioTela,
} from './logica'
import { usarRelatorio } from './usarRelatorio'

const props = defineProps<{ hoje: string; pronto: boolean }>()
const filtros = defineModel<FiltrosRelatorioTela>('filtros', { required: true })
const emit = defineEmits<{ navegar: [para: AbaRelatorio, extra: Partial<FiltrosRelatorioTela>] }>()
const sessao = useSessaoStore()
const cadastros = useCadastrosStore()

const consulta = computed(() => empresasParaApi(filtros.value, props.hoje))
const { dados, carregando, atualizando, erro, carregar } = usarRelatorio(
  (sinal) => relatoriosApi.empresas(consulta.value, sinal),
  () => JSON.stringify(consulta.value),
  () => props.pronto,
)

// ── Busca e filtros da tabela ───────────────────────────────────────────────
const busca = ref(filtros.value.busca)
let atrasoBusca: ReturnType<typeof setTimeout> | null = null
watch(busca, (v) => {
  if (atrasoBusca) clearTimeout(atrasoBusca)
  atrasoBusca = setTimeout(() => (filtros.value.busca = v.trim().slice(0, LIMITE_BUSCA)), 300)
})
watch(
  () => filtros.value.busca,
  (v) => {
    if (v !== busca.value.trim()) busca.value = v
  },
)
onBeforeUnmount(() => {
  if (atrasoBusca) clearTimeout(atrasoBusca)
})

const qtdFiltros = computed(() => contarFiltrosDaAba('empresas', filtros.value))
const filtrosAbertos = ref(qtdFiltros.value > 0)
const podeVerCadastros = computed(() => sessao.pode('contatos.ver'))

/** Opções de uma lista dos cadastros, com "Sem ..." (0) e o valor do endereço se ele não estiver na lista. */
function opcoesCom(lista: { id: Id; nome: string }[], sem: string, atual: Id | '') {
  const opcoes: { valor: Id; rotulo: string }[] = [{ valor: '0', rotulo: sem }, ...lista.map((x) => ({ valor: x.id, rotulo: x.nome }))]
  if (atual !== '' && !opcoes.some((o) => String(o.valor) === String(atual))) opcoes.push({ valor: atual, rotulo: 'Escolhido no link' })
  return opcoes
}
const opcoesRespostas = [
  { valor: 'com' as const, rotulo: 'Com respostas no período' },
  { valor: 'sem' as const, rotulo: 'Sem respostas no período' },
]

function limparFiltros() {
  Object.assign(filtros.value, { segmento_id: '', responsavel_id: '', faixa_valor: '', tempo_cliente: '', respostas: '', quadrante: '' })
}

function limparTudo() {
  busca.value = ''
  filtros.value.busca = ''
  limparFiltros()
}

function alternarQuadrante(q: Quadrante) {
  filtros.value.quadrante = filtros.value.quadrante === q ? '' : q
}

function abrirHistorico(id: Id) {
  emit('navegar', 'historico', { empresa_id: id })
}

const pagina = computed({ get: () => filtros.value.pagina, set: (p: number) => (filtros.value.pagina = p) })

// ── Números ─────────────────────────────────────────────────────────────────
const resumo = computed(() => dados.value?.resumo ?? null)
const matriz = computed(() => dados.value?.matriz ?? null)
const itens = computed(() => dados.value?.itens ?? [])
const mediana = computed(() => numero(matriz.value?.mediana_valor))
const FAIXAS_CARTAO = [
  { chave: 'excelente', rotulo: FAIXAS_NPS.excelente.rotulo, cor: 'bg-grafico-promotor' },
  { chave: 'muito_bom', rotulo: FAIXAS_NPS.muito_bom.rotulo, cor: 'bg-grafico-promotor' },
  { chave: 'pode_melhorar', rotulo: FAIXAS_NPS.pode_melhorar.rotulo, cor: 'bg-grafico-neutro' },
  { chave: 'critico', rotulo: FAIXAS_NPS.critico.rotulo, cor: 'bg-grafico-detrator' },
  { chave: 'sem_respostas', rotulo: 'Sem respostas', cor: 'bg-borda-forte' },
] as const
const temFiltroTabela = computed(() => qtdFiltros.value > 0 || !!filtros.value.busca)
const receitaCurta = computed(() => partesMoedaCurta(resumo.value?.receita.em_risco))

const colunas: Coluna[] = [
  { chave: 'empresa', rotulo: 'Empresa', classe: 'w-[24%]' },
  { chave: 'responsavel', rotulo: 'Responsável' },
  { chave: 'valor', rotulo: 'Valor mensal', alinhar: 'direita' },
  { chave: 'nps', rotulo: 'NPS' },
  { chave: 'respostas', rotulo: 'Respostas', classe: 'w-28' },
  { chave: 'cobertura', rotulo: 'Cobertura', alinhar: 'direita' },
  { chave: 'ultima', rotulo: 'Última resposta' },
  { chave: 'acoes', rotulo: 'Ações abertas', alinhar: 'centro' },
]
</script>

<template>
  <div class="flex flex-col gap-4">
    <!-- Primeira carga -->
    <div v-if="carregando && !dados" class="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4" role="status" aria-label="Carregando o relatório de empresas">
      <div v-for="i in 4" :key="i" class="cartao h-36 animate-pulse p-5">
        <div class="h-3 w-1/2 rounded bg-superficie-2" />
        <div class="mt-4 h-8 w-1/3 rounded bg-superficie-2" />
        <div class="mt-4 h-3 w-2/3 rounded bg-superficie-2" />
      </div>
      <span class="sr-only">Carregando…</span>
    </div>

    <Alerta v-else-if="erro && !dados" tom="erro">
      {{ erro }} <button type="button" class="link ml-1" @click="carregar">Tentar de novo</button>
    </Alerta>

    <div v-else-if="dados && resumo && matriz" class="flex flex-col gap-4 transition-opacity" :class="atualizando ? 'opacity-60' : ''" :aria-busy="atualizando || undefined">
      <Alerta v-if="erro" tom="erro">
        Não deu para atualizar com os filtros novos: {{ erro }} <button type="button" class="link ml-1" @click="carregar">Tentar de novo</button>
      </Alerta>

      <!-- Cartões -->
      <div class="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <section class="cartao flex flex-col gap-1.5 p-5" aria-labelledby="t-rel-com-respostas">
          <h2 id="t-rel-com-respostas" class="text-sm font-semibold text-texto-suave">Empresas com respostas</h2>
          <p class="text-4xl font-extrabold leading-none text-texto">{{ formatarNumero(resumo.com_respostas) }}</p>
          <p class="text-sm text-texto-suave">de {{ plural(resumo.empresas, 'empresa', 'empresas') }} no filtro</p>
        </section>
        <section class="cartao flex flex-col gap-1.5 p-5" aria-labelledby="t-rel-cobertura">
          <h2 id="t-rel-cobertura" class="text-sm font-semibold text-texto-suave">Cobertura geral</h2>
          <p class="text-4xl font-extrabold leading-none text-texto">{{ formatarPct(resumo.cobertura.percentual) }}</p>
          <p class="text-sm text-texto-suave">
            {{ formatarNumero(resumo.cobertura.responderam) }} de {{ plural(resumo.cobertura.contatos_ativos, 'contato ativo', 'contatos ativos') }}
            {{ resumo.cobertura.responderam === 1 ? 'respondeu' : 'responderam' }} o NPS
          </p>
        </section>
        <section class="cartao flex flex-col gap-1.5 p-5" aria-labelledby="t-rel-receita">
          <h2 id="t-rel-receita" class="text-sm font-semibold text-texto-suave">Receita em risco</h2>
          <!-- Valor curto no número grande (cabe no cartão); o valor exato fica na dica e para leitor de tela -->
          <p
            class="flex items-baseline gap-1 font-extrabold leading-none"
            :class="(numero(resumo.receita.em_risco) ?? 0) > 0 ? 'text-erro' : 'text-texto'"
            :title="formatarMoeda(resumo.receita.em_risco, 'R$ 0,00')"
          >
            <span class="text-base font-bold" aria-hidden="true">{{ receitaCurta?.negativo ? '−' : '' }}R$</span>
            <span class="text-4xl tabular-nums" aria-hidden="true">{{ receitaCurta?.numero ?? '0' }}</span>
            <span v-if="receitaCurta?.sufixo" class="text-base font-bold" aria-hidden="true">{{ receitaCurta.sufixo }}</span>
            <span class="sr-only">{{ formatarMoeda(resumo.receita.em_risco, 'R$ 0,00') }}</span>
          </p>
          <p class="text-sm text-texto-suave">
            <template v-if="resumo.receita.percentual !== null">{{ formatarPct(resumo.receita.percentual) }} da receita mensal · </template>
            {{ plural(resumo.receita.empresas_em_risco, 'empresa com detrator', 'empresas com detrator') }}
          </p>
          <p v-if="resumo.receita.sem_valor > 0" class="text-xs text-texto-fraco">
            {{ plural(resumo.receita.sem_valor, 'delas está', 'delas estão') }} sem valor cadastrado
          </p>
        </section>
        <section class="cartao flex flex-col gap-2 p-5" aria-labelledby="t-rel-faixas">
          <h2 id="t-rel-faixas" class="text-sm font-semibold text-texto-suave">Empresas por faixa de NPS</h2>
          <ul class="flex flex-col gap-1 text-sm">
            <li v-for="f in FAIXAS_CARTAO" :key="f.chave" class="flex items-center justify-between gap-3">
              <span class="flex items-center gap-2 text-texto-suave"><span class="size-2.5 rounded-[3px]" :class="f.cor" aria-hidden="true" />{{ f.rotulo }}</span>
              <strong class="font-semibold tabular-nums text-texto">{{ formatarNumero(resumo.por_faixa[f.chave] ?? 0) }}</strong>
            </li>
          </ul>
        </section>
      </div>

      <!-- Matriz NPS × valor -->
      <section class="cartao flex flex-col gap-4 p-5 sm:p-6" aria-labelledby="t-matriz">
        <header>
          <h2 id="t-matriz" class="text-base font-bold text-texto">NPS × valor do contrato</h2>
          <p class="text-sm text-texto-suave">Cada ponto é uma empresa com NPS no período e valor mensal cadastrado. O valor está em escala logarítmica.</p>
        </header>
        <template v-if="matriz.pontos.length">
          <div class="grid grid-cols-1 gap-5 lg:grid-cols-[minmax(0,1fr)_16rem]">
            <MatrizNpsValor :pontos="matriz.pontos" :mediana="mediana" :destaque="filtros.quadrante" @abrir="abrirHistorico" />
            <!-- Contagem por quadrante: a alternativa em texto do gráfico, e filtra a tabela -->
            <div class="flex flex-col gap-2">
              <p class="text-sm font-semibold text-texto">Empresas por quadrante</p>
              <ul class="grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-1">
                <li v-for="q in ORDEM_QUADRANTES" :key="q">
                  <button
                    type="button"
                    class="flex w-full items-start gap-2.5 rounded-xl border px-3 py-2.5 text-left transition-colors"
                    :class="filtros.quadrante === q ? 'border-marca bg-marca-suave' : 'border-borda hover:bg-superficie-2'"
                    :aria-pressed="filtros.quadrante === q"
                    @click="alternarQuadrante(q)"
                  >
                    <span class="mt-1 size-2.5 shrink-0 rounded-full" :class="QUADRANTES[q].fundo" aria-hidden="true" />
                    <span class="min-w-0 flex-1">
                      <span class="flex items-baseline justify-between gap-2">
                        <span class="text-sm font-semibold text-texto">{{ QUADRANTES[q].rotulo }}</span>
                        <span class="text-base font-bold tabular-nums text-texto">{{ formatarNumero(matriz.quadrantes[q] ?? 0) }}</span>
                      </span>
                      <span class="block text-xs text-texto-fraco">{{ QUADRANTES[q].descricao }}</span>
                    </span>
                  </button>
                </li>
              </ul>
              <p class="text-xs text-texto-fraco">Toque num quadrante para ver só essas empresas na tabela.</p>
            </div>
          </div>
          <p v-if="matriz.sem_valor > 0" class="text-sm text-texto-fraco">
            {{ plural(matriz.sem_valor, 'empresa com NPS está', 'empresas com NPS estão') }} fora do gráfico por não ter valor mensal cadastrado.
          </p>
        </template>
        <div v-else class="flex items-start gap-3 rounded-xl bg-superficie-2 p-4 text-sm">
          <Building2 class="mt-0.5 size-5 shrink-0 text-texto-fraco" aria-hidden="true" />
          <p class="text-texto-suave">
            Nenhuma empresa tem NPS no período e valor mensal cadastrado ao mesmo tempo.
            <template v-if="matriz.sem_valor > 0"> {{ plural(matriz.sem_valor, 'empresa tem', 'empresas têm') }} NPS, mas estão sem valor: cadastre em Contatos › Empresas.</template>
          </p>
        </div>
      </section>

      <!-- Tabela -->
      <section class="cartao" aria-labelledby="t-tabela-empresas">
        <div class="flex flex-col gap-3 border-b border-borda p-4 sm:px-5">
          <h2 id="t-tabela-empresas" class="sr-only">Empresas</h2>
          <div class="flex flex-col gap-3 lg:flex-row lg:items-start">
            <Campo v-model="busca" rotulo="Buscar empresa" rotulo-oculto tipo="search" :maxlength="LIMITE_BUSCA" placeholder="Nome da empresa" class="lg:max-w-sm lg:flex-1">
              <template #antes><Search class="size-4" aria-hidden="true" /></template>
            </Campo>
            <div class="flex flex-col gap-3 sm:flex-row sm:items-start lg:ml-auto">
              <Selecao v-model="filtros.ordem" rotulo="Ordenar por" rotulo-oculto :opcoes="ORDENS_EMPRESAS" class="sm:w-64" />
              <Botao variante="secundario" class="!h-11" :aria-expanded="filtrosAbertos" aria-controls="filtros-empresas" @click="filtrosAbertos = !filtrosAbertos">
                <SlidersHorizontal class="size-4" aria-hidden="true" /> Filtros
                <span v-if="qtdFiltros" class="rounded-full bg-marca-forte px-1.5 text-xs text-white">{{ qtdFiltros }}</span>
              </Botao>
            </div>
          </div>
          <div v-show="filtrosAbertos" id="filtros-empresas" class="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
            <Selecao
              v-if="podeVerCadastros || filtros.segmento_id !== ''"
              v-model="filtros.segmento_id"
              rotulo="Segmento"
              :opcoes="opcoesCom(cadastros.listas.segmentos, 'Sem segmento', filtros.segmento_id)"
              vazio="Todos"
            />
            <Selecao
              v-if="podeVerCadastros || filtros.responsavel_id !== ''"
              v-model="filtros.responsavel_id"
              rotulo="Responsável"
              :opcoes="opcoesCom(cadastros.listas.responsaveis, 'Sem responsável', filtros.responsavel_id)"
              vazio="Todos"
            />
            <Selecao v-model="filtros.faixa_valor" rotulo="Valor do contrato" :opcoes="FAIXAS_VALOR" vazio="Todos os valores" />
            <Selecao v-model="filtros.tempo_cliente" rotulo="Tempo como cliente" :opcoes="FAIXAS_TEMPO" vazio="Qualquer tempo" />
            <Selecao v-model="filtros.respostas" rotulo="Respostas" :opcoes="opcoesRespostas" vazio="Com e sem respostas" />
            <Selecao v-model="filtros.quadrante" rotulo="Quadrante da matriz" :opcoes="ORDEM_QUADRANTES.map((q) => ({ valor: q, rotulo: QUADRANTES[q].rotulo }))" vazio="Todos" />
            <div v-if="qtdFiltros" class="sm:col-span-2 lg:col-span-3">
              <Botao variante="fantasma" tamanho="sm" class="!h-10" @click="limparFiltros">Limpar filtros</Botao>
            </div>
          </div>
          <div v-if="filtros.quadrante" class="flex flex-wrap items-center gap-2 text-sm">
            <span class="text-texto-fraco">Mostrando:</span>
            <span class="inline-flex min-h-9 items-center gap-1.5 rounded-xl bg-superficie-2 pl-3 pr-1 font-semibold text-texto">
              <span class="size-2.5 rounded-full" :class="QUADRANTES[filtros.quadrante].fundo" aria-hidden="true" />
              {{ QUADRANTES[filtros.quadrante].rotulo }}
              <button type="button" class="flex size-8 items-center justify-center rounded-lg hover:bg-borda" aria-label="Tirar o filtro de quadrante" @click="filtros.quadrante = ''">
                <X class="size-4" aria-hidden="true" />
              </button>
            </span>
          </div>
        </div>

        <!-- Computador: tabela -->
        <div v-if="itens.length" class="hidden xl:block">
          <Tabela densa :colunas="colunas" :linhas="itens" :chave="(x) => x.empresa.id" legenda="Empresas do relatório">
            <template #cel-empresa="{ linha: x }">
              <button type="button" class="block max-w-full break-words text-left font-semibold text-texto hover:underline" @click="abrirHistorico(x.empresa.id)">
                {{ x.empresa.nome }}
              </button>
              <p v-if="x.grupo || x.segmento" class="text-xs text-texto-fraco">{{ [x.grupo?.nome, x.segmento?.nome].filter(Boolean).join(' · ') }}</p>
              <div v-if="x.em_risco || !x.empresa.ativa" class="mt-1 flex flex-wrap gap-1">
                <Etiqueta v-if="x.em_risco" tom="erro" ponto>Em risco</Etiqueta>
                <Etiqueta v-if="!x.empresa.ativa" tom="neutro">Inativa</Etiqueta>
              </div>
            </template>
            <template #cel-responsavel="{ linha: x }">
              <span :class="x.responsavel ? 'text-texto-suave' : 'text-texto-fraco'">{{ x.responsavel?.nome ?? 'Sem responsável' }}</span>
            </template>
            <template #cel-valor="{ linha: x }">
              <span v-if="x.valor_mensal !== null" class="whitespace-nowrap tabular-nums text-texto-suave">{{ formatarMoeda(x.valor_mensal) }}</span>
              <span v-else class="text-texto-fraco">Sem valor</span>
            </template>
            <template #cel-nps="{ linha: x }"><SeloNps :nps="x.nps" /></template>
            <template #cel-respostas="{ linha: x }">
              <span class="block text-sm tabular-nums text-texto">{{ formatarNumero(x.nps.total) }}</span>
              <BarraGrupos v-if="x.nps.total" class="mt-1" legenda="nenhuma" fina :detratores="x.nps.detratores" :neutros="x.nps.neutros" :promotores="x.nps.promotores" />
            </template>
            <template #cel-cobertura="{ linha: x }">
              <span class="block whitespace-nowrap font-semibold tabular-nums text-texto">{{ formatarPct(x.cobertura.percentual) }}</span>
              <span class="block whitespace-nowrap text-xs text-texto-fraco">{{ formatarNumero(x.cobertura.responderam) }} de {{ formatarNumero(x.cobertura.contatos_ativos) }}</span>
            </template>
            <template #cel-ultima="{ linha: x }">
              <template v-if="x.ultima_resposta">
                <span class="block whitespace-nowrap text-texto-suave">{{ formatarData(x.ultima_resposta.data) }}</span>
                <span v-if="typeof x.ultima_resposta.nota === 'number'" class="block text-xs text-texto-fraco">
                  nota {{ x.ultima_resposta.nota }}{{ x.ultima_resposta.tipo_nota === 'csat' ? ' (CSAT)' : '' }}
                </span>
              </template>
              <span v-else class="text-texto-fraco">Nunca respondeu</span>
            </template>
            <template #cel-acoes="{ linha: x }">
              <span class="tabular-nums" :class="x.acoes_abertas ? 'font-semibold text-texto' : 'text-texto-fraco'">{{ formatarNumero(x.acoes_abertas) }}</span>
            </template>
          </Tabela>
        </div>

        <!-- Celular e tablet: cartões -->
        <ul class="flex flex-col divide-y divide-borda xl:hidden">
          <li v-for="x in itens" :key="String(x.empresa.id)" class="flex flex-col gap-2.5 px-4 py-4">
            <div class="flex items-start justify-between gap-3">
              <div class="min-w-0">
                <p class="break-words font-semibold text-texto">{{ x.empresa.nome }}</p>
                <p class="text-sm text-texto-fraco">
                  {{ x.responsavel?.nome ?? 'Sem responsável' }} · {{ x.valor_mensal !== null ? `${formatarMoeda(x.valor_mensal)}/mês` : 'sem valor' }}
                </p>
              </div>
              <SeloNps :nps="x.nps" compacto />
            </div>
            <div v-if="x.em_risco || !x.empresa.ativa" class="flex flex-wrap gap-1">
              <Etiqueta v-if="x.em_risco" tom="erro" ponto>Em risco</Etiqueta>
              <Etiqueta v-if="!x.empresa.ativa" tom="neutro">Inativa</Etiqueta>
            </div>
            <BarraGrupos v-if="x.nps.total" legenda="compacta" :detratores="x.nps.detratores" :neutros="x.nps.neutros" :promotores="x.nps.promotores" />
            <dl class="grid grid-cols-2 gap-x-4 gap-y-1 text-sm">
              <div>
                <dt class="text-texto-fraco">Cobertura</dt>
                <dd class="font-semibold text-texto">{{ formatarPct(x.cobertura.percentual) }} <span class="font-normal text-texto-fraco">({{ formatarNumero(x.cobertura.responderam) }} de {{ formatarNumero(x.cobertura.contatos_ativos) }})</span></dd>
              </div>
              <div>
                <dt class="text-texto-fraco">Ações abertas</dt>
                <dd class="font-semibold text-texto">{{ formatarNumero(x.acoes_abertas) }}</dd>
              </div>
              <div class="col-span-2">
                <dt class="text-texto-fraco">Última resposta</dt>
                <dd class="text-texto">
                  <template v-if="x.ultima_resposta">{{ formatarData(x.ultima_resposta.data) }}<template v-if="typeof x.ultima_resposta.nota === 'number'"> · nota {{ x.ultima_resposta.nota }}</template></template>
                  <template v-else>Nunca respondeu</template>
                </dd>
              </div>
            </dl>
            <Botao variante="secundario" tamanho="sm" class="!h-10 self-start" @click="abrirHistorico(x.empresa.id)">
              <History class="size-4" aria-hidden="true" /> Ver histórico
            </Botao>
          </li>
        </ul>

        <template v-if="!itens.length">
          <EstadoVazio v-if="temFiltroTabela" :icone="Search" titulo="Nenhuma empresa com esses filtros" descricao="Tente outra busca ou limpe os filtros da tabela.">
            <Botao variante="secundario" @click="limparTudo">Limpar busca e filtros</Botao>
          </EstadoVazio>
          <EstadoVazio v-else :icone="Building2" titulo="Nenhuma empresa no filtro" descricao="Cadastre as empresas dos seus clientes em Contatos › Empresas para ver o NPS de cada uma." />
        </template>
        <Paginacao v-model="pagina" :total="dados.total" :por-pagina="dados.por_pagina || 50" :carregando="atualizando" :nome-itens="dados.total === 1 ? 'empresa' : 'empresas'" />
      </section>
    </div>
  </div>
</template>

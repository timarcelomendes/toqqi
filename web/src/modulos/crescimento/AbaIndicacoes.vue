<script setup lang="ts">
// Crescimento › Indicações: busca, situação (com a contagem, que também filtra), responsável e período; a lista em
// tabela a partir de 640 px e em cartões no celular; abrir uma indicação leva ao painel lateral.
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue'
import { Search, Settings, SlidersHorizontal, UserPlus } from 'lucide-vue-next'
import { crescimentoApi, type ConfigCrescimento, type Id, type Indicacao, type PaginaIndicacoes } from '@/api'
import { useCadastrosStore } from '@/stores/cadastros'
import { useSessaoStore } from '@/stores/sessao'
import { formatarData } from '@/utils/datas'
import { exibirTelefone, formatarMoeda, formatarNumero } from '@/utils/formatos'
import { PERIODOS } from '@/utils/periodo'
import Alerta from '@/components/ui/Alerta.vue'
import Botao from '@/components/ui/Botao.vue'
import Campo from '@/components/ui/Campo.vue'
import EstadoVazio from '@/components/ui/EstadoVazio.vue'
import Etiqueta from '@/components/ui/Etiqueta.vue'
import Paginacao from '@/components/ui/Paginacao.vue'
import Selecao from '@/components/ui/Selecao.vue'
import Tabela, { type Coluna } from '@/components/ui/Tabela.vue'
import TextoEmail from '@/components/ui/TextoEmail.vue'
import { usarRelatorio } from '@/modulos/relatorios/usarRelatorio'
import PainelIndicacao from './PainelIndicacao.vue'
import {
  FILTROS_INDICACOES_PADRAO,
  LIMITE_BUSCA,
  ORDEM_SITUACOES,
  SITUACOES_INDICACAO,
  contarFiltrosIndicacoes,
  filtrosIndicacoesParaApi,
  linhaVizinha,
  numeroDecimal,
  quemIndicou,
  semNomeDoIndicador,
  situacaoIndicacao,
  ultimaPaginaQueExiste,
  type FiltrosIndicacoesTela,
} from './logica'

const props = defineProps<{
  hoje: string
  pronto: boolean
  erroDatas: string | null
  /** null enquanto carrega ou se falhou: aí o vazio não diz se o convite está ligado. */
  config: ConfigCrescimento | null
  erroConfig: string | null
}>()
const filtros = defineModel<FiltrosIndicacoesTela>('filtros', { required: true })
const emit = defineEmits<{ mudou: []; recarregarConfig: [] }>()
const sessao = useSessaoStore()
const cadastros = useCadastrosStore()
const podeConfigurar = computed(() => sessao.pode('configuracoes.gerenciar'))
const podeTratar = computed(() => sessao.pode('crescimento.tratar'))
const podeVerCadastros = computed(() => sessao.pode('contatos.ver'))

const consulta = computed(() => filtrosIndicacoesParaApi(filtros.value, props.hoje))
const { dados, carregando, atualizando, erro, carregar } = usarRelatorio<PaginaIndicacoes>(
  (sinal) => crescimentoApi.indicacoes(consulta.value, sinal),
  () => JSON.stringify(consulta.value),
  () => props.pronto,
)
defineExpose({ recarregar: () => carregar() })

// ── Busca e filtros ─────────────────────────────────────────────────────────
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

const qtdFiltros = computed(() => contarFiltrosIndicacoes(filtros.value))
const filtrosAbertos = ref(qtdFiltros.value > 0)
const temFiltro = computed(() => qtdFiltros.value > 0 || !!filtros.value.busca || !!filtros.value.situacao)
// "Sem responsável" (0), como nos Relatórios e nos Planos de ação.
const opcoesResponsavel = computed(() => {
  const opcoes: { valor: Id; rotulo: string }[] = [{ valor: '0', rotulo: 'Sem responsável' }, ...cadastros.listas.responsaveis.map((r) => ({ valor: r.id, rotulo: r.nome }))]
  const atual = filtros.value.responsavel_id
  if (atual !== '' && !opcoes.some((o) => String(o.valor) === String(atual))) opcoes.push({ valor: atual, rotulo: 'Escolhido no link' })
  return opcoes
})
const opcoesPeriodo = PERIODOS.map((p) => ({ ...p, rotulo: p.valor === 'tudo' ? 'Em qualquer data' : p.rotulo }))

function limparFiltros() {
  Object.assign(filtros.value, { responsavel_id: '', periodo: 'tudo', de: '', ate: '' })
}
function limparTudo() {
  busca.value = ''
  Object.assign(filtros.value, { ...FILTROS_INDICACOES_PADRAO })
}

// Situação: "Todas" e as quatro, com a contagem do resumo (mesmo período e responsável da lista).
const resumo = computed(() => dados.value?.resumo ?? null)
const CONTAGEM = { nova: 'novas', em_contato: 'em_contato', cliente: 'clientes', nao_avancou: 'nao_avancou' } as const
const opcoesSituacao = computed(() => {
  const r = resumo.value
  const qtd = (s: (typeof ORDEM_SITUACOES)[number]) => (r ? (r[CONTAGEM[s]] ?? 0) : null)
  const total = r ? ORDEM_SITUACOES.reduce((n, s) => n + (qtd(s) ?? 0), 0) : null
  return [{ valor: '' as const, rotulo: 'Todas', qtd: total }, ...ORDEM_SITUACOES.map((s) => ({ valor: s, rotulo: SITUACOES_INDICACAO[s].filtro, qtd: qtd(s) }))]
})
const receita = computed(() => numeroDecimal(resumo.value?.receita_mensal) ?? 0)

const pagina = computed({ get: () => filtros.value.pagina, set: (p: number) => (filtros.value.pagina = p) })
const itens = computed(() => dados.value?.itens ?? [])

// Página vazia depois da primeira (a última indicação dela saiu, ou um endereço antigo): volta para a última que
// existe. Só com a resposta da página atual (a de uma página que já ficou para trás não conta).
watch(dados, (d) => {
  const atual = filtros.value.pagina
  if (!d || d.itens.length || atual <= 1 || (typeof d.pagina === 'number' && d.pagina !== atual)) return
  filtros.value.pagina = ultimaPaginaQueExiste(atual, d.total, d.por_pagina || 50)
})

/** O vazio só fala em ligar o convite quando sabe que ele está desligado; registrar à mão, só para quem pode. */
const descricaoVazio = computed(() => {
  const comoChega = 'quem der nota 9 ou 10 (ou 5 no CSAT) num convite da pesquisa vê, na tela final, um cartão para indicar outra empresa. As indicações aparecem aqui.'
  const registrar = podeTratar.value ? ' Indicação que chegou de outro jeito? Use “Registrar indicação”.' : ''
  return props.config?.indicacoes_ativas ? `O convite já está ligado: ${comoChega}${registrar}` : `Com o convite de indicação ligado, ${comoChega}${registrar}`
})

// ── Painel ──────────────────────────────────────────────────────────────────
const aberta = ref<Indicacao | null>(null)
const painelAberto = ref(false)
const anuncio = ref('')
const raiz = ref<HTMLElement | null>(null)
const tituloLista = ref<HTMLElement | null>(null)

// A ordem da lista da última vez em que a indicação do painel estava nela: se ela sair (excluída, ou fora do filtro
// depois de uma mudança), o foco, que voltaria para a linha dela, vai para a vizinha.
let ordemComAberta: string[] = []
watch([itens, aberta], ([lista, i]) => {
  const ordem = lista.map((x) => String(x.id))
  if (i && ordem.includes(String(i.id))) ordemComAberta = ordem
})

/** O botão que abre a indicação na lista que está à vista (a tabela a partir de 640 px, os cartões no celular). */
function botaoDaLinha(id: string): HTMLElement | null {
  const botoes = Array.from(raiz.value?.querySelectorAll<HTMLElement>('[data-abrir], [data-abrir-cartao]') ?? []).filter(
    (b) => (b.dataset.abrir ?? b.dataset.abrirCartao) === id,
  )
  return botoes.find((b) => b.getClientRects().length > 0) ?? botoes[0] ?? null
}

/**
 * Painel fechado e a linha da indicação dele fora da lista: o foco, sem a linha para voltar, cairia no body. Vai
 * para a linha seguinte (ou a anterior) ou, com a lista vazia, para o título da lista.
 */
async function focarSeSaiu() {
  const i = aberta.value
  if (!i || painelAberto.value) return
  await nextTick()
  const atuais = itens.value.map((x) => String(x.id))
  if (painelAberto.value || atuais.includes(String(i.id))) return
  const ativo = document.activeElement
  if (ativo instanceof HTMLElement && ativo !== document.body && ativo.isConnected) return // já está em outro lugar
  const vizinha = linhaVizinha(ordemComAberta, String(i.id), atuais)
  const alvo = (vizinha ? botaoDaLinha(vizinha) : null) ?? tituloLista.value
  alvo?.focus()
}

function abrir(i: Indicacao) {
  aberta.value = i
  painelAberto.value = true
}
function fechar() {
  painelAberto.value = false
  void focarSeSaiu()
}
function substituir(nova: Indicacao) {
  if (!dados.value) return
  dados.value = { ...dados.value, itens: dados.value.itens.map((x) => (String(x.id) === String(nova.id) ? nova : x)) }
}
async function aoSalvar(nova: Indicacao, antiga: Indicacao) {
  substituir(nova)
  aberta.value = nova
  if (nova.situacao !== antiga.situacao) {
    anuncio.value = `${nova.nome}: agora em “${situacaoIndicacao(nova.situacao).rotulo}”.`
    painelAberto.value = false
  }
  emit('mudou')
  // Com filtro, a linha pode sair da lista quando ela chega.
  await carregar()
  await focarSeSaiu()
}
async function aoExcluir(i: Indicacao) {
  painelAberto.value = false
  if (dados.value) dados.value = { ...dados.value, itens: dados.value.itens.filter((x) => String(x.id) !== String(i.id)), total: Math.max(0, dados.value.total - 1) }
  anuncio.value = `A indicação de ${i.nome} foi excluída.`
  emit('mudou')
  await focarSeSaiu()
  await carregar()
  await focarSeSaiu()
}

const colunas: Coluna[] = [
  { chave: 'indicacao', rotulo: 'Indicação', classe: 'w-[24%]' },
  { chave: 'contato', rotulo: 'Contato' },
  { chave: 'quem', rotulo: 'Quem indicou' },
  { chave: 'responsavel', rotulo: 'Responsável', classe: 'hidden lg:table-cell' },
  { chave: 'situacao', rotulo: 'Situação' },
  { chave: 'data', rotulo: 'Recebida', classe: 'hidden lg:table-cell' },
]
</script>

<template>
  <section ref="raiz" class="cartao" aria-labelledby="t-lista-indicacoes">
    <div class="flex flex-col gap-3 border-b border-borda p-4 sm:px-5">
      <!-- Recebe o foco quando a última linha sai da lista com o painel dela fechando -->
      <h2 id="t-lista-indicacoes" ref="tituloLista" tabindex="-1" class="sr-only">Indicações</h2>
      <div class="flex flex-col gap-3 md:flex-row md:items-center">
        <Campo
          v-model="busca"
          rotulo="Buscar indicações"
          rotulo-oculto
          tipo="search"
          :maxlength="LIMITE_BUSCA"
          placeholder="Nome, empresa ou contato"
          class="md:max-w-sm md:flex-1"
        >
          <template #antes><Search class="size-4" aria-hidden="true" /></template>
        </Campo>
        <Botao variante="secundario" class="!h-11 self-start md:ml-auto md:self-auto" :aria-expanded="filtrosAbertos" aria-controls="filtros-indicacoes" @click="filtrosAbertos = !filtrosAbertos">
          <SlidersHorizontal class="size-4" aria-hidden="true" /> Filtros
          <span v-if="qtdFiltros" class="rounded-full bg-marca-forte px-1.5 text-xs text-white">{{ qtdFiltros }}</span>
        </Botao>
      </div>
      <div v-show="filtrosAbertos" id="filtros-indicacoes" class="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <Selecao
          v-if="podeVerCadastros || filtros.responsavel_id !== ''"
          v-model="filtros.responsavel_id"
          rotulo="Responsável"
          :opcoes="opcoesResponsavel"
          vazio="Todos"
        />
        <Selecao v-model="filtros.periodo" rotulo="Recebidas" :opcoes="opcoesPeriodo" />
        <div v-if="filtros.periodo === 'personalizado'" class="grid grid-cols-2 gap-2 sm:col-span-2">
          <Campo v-model="filtros.de" rotulo="De" tipo="date" :max="filtros.ate || hoje" :erro="erroDatas" />
          <Campo v-model="filtros.ate" rotulo="Até" tipo="date" :min="filtros.de || undefined" :max="hoje" />
        </div>
        <div v-if="qtdFiltros" class="sm:col-span-2 lg:col-span-4">
          <Botao variante="fantasma" tamanho="sm" class="!h-10" @click="limparFiltros">Limpar filtros</Botao>
        </div>
      </div>

      <!-- Situação: a contagem de cada uma (mesmo período e responsável), que também filtra a lista -->
      <div role="group" aria-label="Situação" class="flex flex-wrap gap-2" data-situacoes>
        <button
          v-for="o in opcoesSituacao"
          :key="o.valor || 'todas'"
          type="button"
          class="inline-flex min-h-10 items-center gap-2 rounded-xl border px-3 text-sm font-semibold transition-colors"
          :class="filtros.situacao === o.valor ? 'border-marca bg-marca-suave text-marca-texto' : 'border-borda-forte text-texto-suave hover:bg-superficie-2 hover:text-texto'"
          :aria-pressed="filtros.situacao === o.valor"
          :data-situacao="o.valor || 'todas'"
          @click="filtros.situacao = o.valor"
        >
          {{ o.rotulo }}
          <span v-if="o.qtd !== null" class="tabular-nums" :class="filtros.situacao === o.valor ? 'text-marca-texto' : 'text-texto-fraco'">{{ formatarNumero(o.qtd) }}</span>
        </button>
      </div>
      <p v-if="receita > 0" class="text-sm text-texto-suave" data-receita-indicacoes>
        Receita mensal das que viraram cliente: <strong class="font-semibold text-texto">{{ formatarMoeda(receita) }}</strong>
      </p>
    </div>

    <!-- Primeira carga -->
    <div v-if="carregando && !dados" class="flex flex-col gap-3 p-5" role="status" aria-label="Carregando as indicações">
      <div v-for="i in 4" :key="i" class="h-12 animate-pulse rounded-xl bg-superficie-2" />
    </div>

    <Alerta v-else-if="erro && !dados" tom="erro" class="m-4">
      {{ erro }} <button type="button" class="link ml-1" @click="carregar">Tentar de novo</button>
    </Alerta>

    <div v-else-if="dados" class="transition-opacity" :class="atualizando ? 'opacity-60' : ''" :aria-busy="atualizando || undefined">
      <Alerta v-if="erro" tom="erro" class="m-4">
        Não deu para atualizar a lista: {{ erro }} <button type="button" class="link ml-1" @click="carregar">Tentar de novo</button>
      </Alerta>

      <!-- A partir de 640 px: tabela -->
      <div v-if="itens.length" class="hidden sm:block">
        <Tabela densa :colunas="colunas" :linhas="itens" :chave="(x) => x.id" legenda="Indicações recebidas">
          <template #cel-indicacao="{ linha: x }">
            <button type="button" class="block max-w-full break-words text-left font-semibold text-texto hover:underline" :data-abrir="String(x.id)" @click="abrir(x)">
              {{ x.nome }}
            </button>
            <p v-if="x.empresa" class="break-words text-xs text-texto-fraco">{{ x.empresa }}</p>
          </template>
          <template #cel-contato="{ linha: x }">
            <p v-if="exibirTelefone(x.telefone)" class="whitespace-nowrap text-texto-suave">{{ exibirTelefone(x.telefone) }}</p>
            <p v-if="x.email" class="text-texto-suave"><TextoEmail :email="x.email" /></p>
          </template>
          <template #cel-quem="{ linha: x }">
            <span class="break-words" :class="semNomeDoIndicador(x) ? 'text-texto-fraco' : 'text-texto-suave'">{{ quemIndicou(x) }}</span>
          </template>
          <template #cel-responsavel="{ linha: x }">
            <span :class="x.responsavel ? 'text-texto-suave' : 'text-texto-fraco'">{{ x.responsavel?.nome ?? 'Sem responsável' }}</span>
          </template>
          <template #cel-situacao="{ linha: x }">
            <Etiqueta :tom="situacaoIndicacao(x.situacao).tom" ponto>{{ situacaoIndicacao(x.situacao).rotulo }}</Etiqueta>
            <p v-if="x.situacao === 'cliente' && numeroDecimal(x.valor_mensal) !== null" class="mt-1 whitespace-nowrap text-xs text-texto-fraco">{{ formatarMoeda(x.valor_mensal) }}/mês</p>
            <!-- Até 1024 px, o responsável e a data ficam aqui (as colunas deles somem) -->
            <p class="mt-1 text-xs text-texto-fraco lg:hidden">{{ x.responsavel ? `Responsável: ${x.responsavel.nome}` : 'Sem responsável' }} · {{ formatarData(x.criada_em) }}</p>
          </template>
          <template #cel-data="{ linha: x }">
            <span class="whitespace-nowrap text-texto-suave">{{ formatarData(x.criada_em) }}</span>
          </template>
        </Tabela>
      </div>

      <!-- Celular: cartões -->
      <ul v-if="itens.length" class="flex flex-col divide-y divide-borda sm:hidden" aria-label="Indicações recebidas">
        <li v-for="x in itens" :key="String(x.id)" class="relative flex flex-col gap-1.5 px-4 py-4">
          <div class="flex items-start justify-between gap-3">
            <div class="min-w-0">
              <h3 class="font-semibold text-texto">
                <button type="button" class="break-words text-left after:absolute after:inset-0 after:content-['']" :data-abrir-cartao="String(x.id)" @click="abrir(x)">
                  {{ x.nome }}
                </button>
              </h3>
              <p v-if="x.empresa" class="break-words text-sm text-texto-suave">{{ x.empresa }}</p>
            </div>
            <Etiqueta :tom="situacaoIndicacao(x.situacao).tom" ponto>{{ situacaoIndicacao(x.situacao).rotulo }}</Etiqueta>
          </div>
          <p v-if="exibirTelefone(x.telefone)" class="whitespace-nowrap text-sm text-texto-suave">{{ exibirTelefone(x.telefone) }}</p>
          <p v-if="x.email" class="text-sm text-texto-suave"><TextoEmail :email="x.email" /></p>
          <p class="text-xs text-texto-fraco">Quem indicou: {{ quemIndicou(x) }}</p>
          <p class="text-xs text-texto-fraco">
            {{ x.responsavel ? `Responsável: ${x.responsavel.nome}` : 'Sem responsável' }} · {{ formatarData(x.criada_em) }}
            <template v-if="x.situacao === 'cliente' && numeroDecimal(x.valor_mensal) !== null"> · {{ formatarMoeda(x.valor_mensal) }}/mês</template>
          </p>
        </li>
      </ul>

      <!-- Vazia depois da primeira página: a lista volta para a última página que existe (sem dizer "nenhuma") -->
      <template v-if="!itens.length && filtros.pagina <= 1">
        <EstadoVazio v-if="temFiltro" :icone="Search" titulo="Nenhuma indicação com esses filtros" descricao="Tente outra busca ou limpe os filtros.">
          <Botao variante="secundario" @click="limparTudo">Limpar busca e filtros</Botao>
        </EstadoVazio>
        <!-- "Ligue o convite" só quando a configuração diz que ele está desligado -->
        <EstadoVazio
          v-else-if="config && !config.indicacoes_ativas"
          :icone="UserPlus"
          titulo="Nenhuma indicação ainda"
          descricao="Ligue o convite de indicação: quem der nota 9 ou 10 (ou 5 no CSAT) num convite da pesquisa vê, na tela final, um cartão para indicar outra empresa. As indicações chegam aqui, com o responsável certo."
        >
          <Botao v-if="podeConfigurar" para="/configuracoes/crescimento"><Settings class="size-4" aria-hidden="true" /> Ligar o convite</Botao>
          <p v-else class="max-w-md text-sm text-texto-fraco" data-pedir-admin>Peça a um administrador para ligar o convite em Configurações › Crescimento.</p>
        </EstadoVazio>
        <template v-else>
          <Alerta v-if="!config && erroConfig" tom="erro" class="m-4" data-erro-config>
            Não deu para saber se o convite de indicação está ligado: {{ erroConfig }}
            <button type="button" class="link ml-1" @click="emit('recarregarConfig')">Tentar de novo</button>
          </Alerta>
          <EstadoVazio :icone="UserPlus" titulo="Nenhuma indicação ainda" :descricao="descricaoVazio" data-vazio-indicacoes />
        </template>
      </template>

      <Paginacao
        v-model="pagina"
        :total="dados.total"
        :por-pagina="dados.por_pagina || 50"
        :carregando="atualizando"
        :nome-itens="dados.total === 1 ? 'indicação' : 'indicações'"
      />
    </div>
    <p class="sr-only" aria-live="polite">{{ anuncio }}</p>

    <PainelIndicacao :indicacao="aberta" :aberto="painelAberto" @fechar="fechar" @salva="aoSalvar" @excluida="aoExcluir" />
  </section>
</template>

<script setup lang="ts">
// Plataforma › Visão geral (etapa 5h, docs/api-etapa-5h.md §5): o negócio num relance para a equipe Toqqi. Indicadores
// (em teste, pagantes, receita mensal — com "sandbox" quando for —, testes acabando em 7 dias, novas em 30 dias e
// conversão do teste), a lista "Testes acabando" (e-mail do administrador para copiar, dias que faltam, ativação e
// último acesso) e a tabela das contas (busca pelo nome ou e-mail, filtro por situação e ordem por último acesso,
// criação ou respostas; tabela a partir de 1280 px e lista abaixo disso: com o menu lateral aberto, a tabela de seis
// colunas não cabe antes). Busca ao abrir a aba e em "Atualizar".
import { computed, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { Building2, CalendarCheck, RefreshCw, Search } from 'lucide-vue-next'
import { mensagemDoErro, plataformaApi, type ContaVisao, type VisaoPlataforma } from '@/api'
import { nomeDoPlano } from '@/modulos/assinatura/logica'
import { formatarData, formatarDataHora } from '@/utils/datas'
import { formatarNumero, plural } from '@/utils/formatos'
import type { Tom } from '@/utils/rotulos'
import Alerta from '@/components/ui/Alerta.vue'
import Botao from '@/components/ui/Botao.vue'
import BotaoCopiar from '@/components/ui/BotaoCopiar.vue'
import Campo from '@/components/ui/Campo.vue'
import Carregando from '@/components/ui/Carregando.vue'
import EstadoVazio from '@/components/ui/EstadoVazio.vue'
import Etiqueta from '@/components/ui/Etiqueta.vue'
import Selecao from '@/components/ui/Selecao.vue'
import Tabela, { type Coluna } from '@/components/ui/Tabela.vue'
import TextoEmail from '@/components/ui/TextoEmail.vue'
import MarcadoresAtivacao from './MarcadoresAtivacao.vue'
import {
  ORDENS_CONTAS,
  contasFiltradas,
  indicadores,
  leituraTeste,
  opcoesSituacao,
  rotuloSituacao,
  textoDiasRestantes,
  textoFalta,
  textoPlano,
  textoUltimoAcesso,
  tomDiasRestantes,
  type FiltroContas,
} from './visao'

const dados = ref<VisaoPlataforma | null>(null)
const carregando = ref(true)
const erro = ref<string | null>(null)
const filtro = reactive<FiltroContas>({ busca: '', situacao: '', ordem: 'ultimo_acesso' })
let controlador: AbortController | null = null

const COR: Record<Tom, string> = {
  neutro: 'text-texto',
  marca: 'text-texto',
  info: 'text-texto',
  sucesso: 'text-sucesso',
  atencao: 'text-atencao',
  erro: 'text-erro',
}

const cartoes = computed(() => (dados.value ? indicadores(dados.value.totais, dados.value.conversao, dados.value.testes_acabando.length) : []))
const contas = computed(() => (dados.value ? contasFiltradas(dados.value.contas, filtro) : []))
const situacoes = computed(() => opcoesSituacao(dados.value?.contas ?? []))
const filtrando = computed(() => !!filtro.busca.trim() || !!filtro.situacao)

// O plano fica numa linha só; "Último acesso" e "Respostas" têm largura fixa e a sobra vai para a coluna da conta (o
// e-mail do administrador numa linha a partir de 1280 px, com o menu lateral aberto).
const colunas: Coluna[] = [
  { chave: 'nome', rotulo: 'Conta', classe: 'min-w-48' },
  { chave: 'situacao', rotulo: 'Situação e plano', classe: 'min-w-40' },
  { chave: 'ativacao', rotulo: 'Ativação' },
  { chave: 'ultimo_acesso', rotulo: 'Último acesso', classe: 'w-32' },
  { chave: 'respostas', rotulo: 'Respostas em 30 dias', alinhar: 'direita', classe: 'w-28' },
  { chave: 'uso', rotulo: 'Uso' },
]

/** "Profissional · R$ 349,00/mês · criada em 01/09/2026" (a lista, abaixo de 1280 px). */
function pctTeste(v: number | null): string {
  return v === null ? '—' : `${Math.round(v * 100)}%`
}

function linhaPlano(c: ContaVisao): string {
  return `${textoPlano(c, nomeDoPlano)} · criada em ${formatarData(c.criada_em)}`
}

async function carregar() {
  controlador?.abort()
  controlador = new AbortController()
  carregando.value = true
  erro.value = null
  try {
    dados.value = await plataformaApi.visao(controlador.signal)
  } catch (e) {
    if (e instanceof DOMException && e.name === 'AbortError') return
    erro.value = mensagemDoErro(e)
  } finally {
    carregando.value = false
  }
}

function limparFiltros() {
  filtro.busca = ''
  filtro.situacao = ''
}

onMounted(carregar)
onBeforeUnmount(() => controlador?.abort())
</script>

<template>
  <!-- Uma raiz só: a Plataforma esconde a aba com v-show -->
  <div class="flex flex-col gap-6" data-aba-visao>
    <div v-if="carregando && !dados" class="cartao p-5"><Carregando :linhas="6" rotulo="Carregando a visão geral" /></div>
    <Alerta v-else-if="erro && !dados" tom="erro" data-erro-visao>
      {{ erro }} <button type="button" class="link ml-1" @click="carregar">Tentar de novo</button>
    </Alerta>

    <template v-else-if="dados">
      <div class="flex flex-wrap items-center justify-between gap-x-4 gap-y-2">
        <p class="text-sm text-texto-fraco" aria-live="polite" data-atualizado>
          <template v-if="carregando">Atualizando…</template>
          <template v-else>Números de {{ formatarDataHora(dados.gerado_em) }}</template>
        </p>
        <Botao variante="secundario" tamanho="sm" :carregando="carregando" data-atualizar @click="carregar">
          <RefreshCw class="size-4" aria-hidden="true" /> Atualizar
        </Botao>
      </div>
      <Alerta v-if="erro" tom="erro">{{ erro }}</Alerta>

      <!-- Indicadores: dois por linha no celular, três a partir das telas largas -->
      <section aria-label="Indicadores do negócio" class="grid grid-cols-2 gap-3 lg:grid-cols-3 lg:gap-4" data-indicadores>
        <div
          v-for="i in cartoes"
          :key="i.chave"
          class="flex min-w-0 flex-col gap-1 rounded-cartao border border-borda bg-superficie p-3.5 shadow-cartao sm:p-5"
          :data-indicador="i.chave"
        >
          <h2 class="text-sm font-semibold text-texto-suave">{{ i.rotulo }}</h2>
          <p class="flex flex-wrap items-center gap-x-2 gap-y-1 text-xl font-extrabold leading-tight tabular-nums sm:text-2xl" :class="COR[i.tom ?? 'neutro']">
            <span data-valor>{{ i.valor }}</span>
            <Etiqueta v-if="i.selo" tom="atencao" data-selo>{{ i.selo }}</Etiqueta>
          </p>
          <p class="text-xs" :class="i.tomDetalhe ? COR[i.tomDetalhe] : 'text-texto-suave'" data-detalhe>{{ i.detalhe }}</p>
        </div>
      </section>

      <!-- Testes acabando -->
      <section class="cartao" aria-labelledby="visao-acabando" data-testes-acabando>
        <div class="border-b border-borda px-4 py-3.5 sm:px-5">
          <h2 id="visao-acabando" class="font-bold text-texto">Testes acabando</h2>
          <p class="text-sm text-texto-suave">Contas em teste, ainda sem assinatura, que acabam nos próximos 7 dias.</p>
        </div>
        <EstadoVazio
          v-if="!dados.testes_acabando.length"
          :icone="CalendarCheck"
          titulo="Nenhum teste acaba nos próximos 7 dias"
          descricao="As contas em teste aparecem aqui na última semana, com o que falta para começarem a usar."
        />
        <ul v-else class="divide-y divide-borda">
          <li
            v-for="t in dados.testes_acabando"
            :key="String(t.id)"
            class="grid gap-3 px-4 py-4 sm:px-5 md:grid-cols-[minmax(0,1fr)_16rem] md:items-center md:gap-6"
            data-teste-acabando
          >
            <div class="min-w-0">
              <div class="flex flex-wrap items-center gap-x-2 gap-y-1">
                <p class="font-semibold text-texto [overflow-wrap:anywhere]">{{ t.nome }}</p>
                <Etiqueta :tom="tomDiasRestantes(t.dias)" data-dias>{{ textoDiasRestantes(t.dias) }}</Etiqueta>
              </div>
              <!-- O botão de copiar fica junto do e-mail, à esquerda (à direita, cairia sob o botão do ToqqiAI) -->
              <div class="mt-1 flex flex-wrap items-center gap-x-2 gap-y-1 text-sm text-texto-suave">
                <template v-if="t.email">
                  <TextoEmail :email="t.email" />
                  <BotaoCopiar :texto="t.email" rotulo="Copiar e-mail" tamanho="sm" variante="fantasma" class="-my-1" />
                </template>
                <span v-else class="text-texto-fraco">Sem administrador</span>
              </div>
              <p class="mt-1 text-xs text-texto-fraco">{{ textoUltimoAcesso(t.ultimo_acesso) }} · teste até {{ formatarData(t.teste_ate) }}</p>
            </div>
            <div class="flex flex-col gap-1">
              <MarcadoresAtivacao :ativacao="t.ativacao" />
              <p class="text-xs text-texto-suave">{{ textoFalta(t.ativacao) }}</p>
            </div>
          </li>
        </ul>
      </section>

      <!-- Melhoria 9: quanto o teste leva até a primeira resposta (para decidir a duração) -->
      <section v-if="dados.teste" class="cartao p-4 sm:p-5" aria-labelledby="visao-tempo-teste" data-tempo-teste>
        <h2 id="visao-tempo-teste" class="font-bold text-texto">Teste até a primeira resposta</h2>
        <p class="text-sm text-texto-suave">
          Contas com teste criadas de {{ formatarData(dados.teste.de) }} a {{ formatarData(dados.teste.ate) }}. Conta só resposta de cliente pela pesquisa (não as importadas).
        </p>
        <dl class="mt-3 grid grid-cols-2 gap-3 text-sm sm:grid-cols-4">
          <div><dt class="text-texto-fraco">Chegaram à 1ª resposta</dt><dd class="text-lg font-bold text-texto">{{ dados.teste.chegaram }} de {{ dados.teste.contas }}</dd></div>
          <div><dt class="text-texto-fraco">Em até 7 dias</dt><dd class="text-lg font-bold text-texto">{{ dados.teste.ate_7_dias }}</dd></div>
          <div><dt class="text-texto-fraco">Em até 14 dias</dt><dd class="text-lg font-bold text-texto">{{ dados.teste.ate_14_dias }}</dd></div>
          <div><dt class="text-texto-fraco">Mediana</dt><dd class="text-lg font-bold text-texto">{{ dados.teste.mediana_dias === null ? '—' : `${String(dados.teste.mediana_dias).replace('.', ',')} dias` }}</dd></div>
        </dl>
        <p class="mt-3 text-sm text-texto-suave">
          Assinaram: <strong>{{ pctTeste(dados.teste.conversao_com_resposta) }}</strong> de quem chegou à resposta e <strong>{{ pctTeste(dados.teste.conversao_sem_resposta) }}</strong> de quem não chegou.
        </p>
        <p class="mt-2 text-sm font-semibold text-texto" data-leitura-teste>{{ leituraTeste(dados.teste) }}</p>
      </section>

      <!-- Etapa 5i: de onde vieram os cadastros (utm, ex. o "Pesquisa feita com Toqqi") -->
      <section v-if="dados.origens" class="cartao" aria-labelledby="visao-origens" data-origens>
        <div class="border-b border-borda px-4 py-3.5 sm:px-5">
          <h2 id="visao-origens" class="font-bold text-texto">Cadastros por origem</h2>
          <p class="text-sm text-texto-suave">Contas criadas nos últimos {{ dados.origens.dias }} dias. A conversão aparece depois que o teste acaba.</p>
        </div>
        <div class="overflow-x-auto">
          <table class="w-full text-sm">
            <thead class="text-left text-xs text-texto-suave">
              <tr>
                <th scope="col" class="px-4 py-2 font-semibold sm:px-5">Origem</th>
                <th scope="col" class="px-3 py-2 text-right font-semibold">Cadastros</th>
                <th scope="col" class="px-4 py-2 text-right font-semibold sm:px-5">Pagantes</th>
              </tr>
            </thead>
            <tbody class="divide-y divide-borda">
              <tr v-for="o in dados.origens.itens" :key="o.rotulo" data-origem>
                <td class="px-4 py-2.5 text-texto [overflow-wrap:anywhere] sm:px-5">{{ o.rotulo }}</td>
                <td class="px-3 py-2.5 text-right tabular-nums">{{ o.cadastros }}</td>
                <td class="px-4 py-2.5 text-right tabular-nums sm:px-5">{{ o.pagantes }}</td>
              </tr>
              <tr data-origem-sem>
                <td class="px-4 py-2.5 text-texto-suave sm:px-5">Sem origem (acesso direto)</td>
                <td class="px-3 py-2.5 text-right tabular-nums">{{ dados.origens.sem_origem.cadastros }}</td>
                <td class="px-4 py-2.5 text-right tabular-nums sm:px-5">{{ dados.origens.sem_origem.pagantes }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      <!-- Contas -->
      <section class="cartao" aria-labelledby="visao-contas" data-contas-visao>
        <div class="flex flex-col gap-3 border-b border-borda p-4 sm:px-5">
          <div class="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
            <h2 id="visao-contas" class="font-bold text-texto">Contas</h2>
            <p class="text-sm text-texto-fraco" aria-live="polite" data-total-contas>
              {{ plural(contas.length, 'conta', 'contas') }}<template v-if="filtrando"> de {{ formatarNumero(dados.contas.length) }}</template>
            </p>
          </div>
          <div class="grid gap-3 sm:grid-cols-2 lg:grid-cols-[minmax(0,1fr)_14rem_12rem]">
            <Campo v-model="filtro.busca" rotulo="Buscar" tipo="search" placeholder="Nome da conta ou e-mail" class="sm:col-span-2 lg:col-span-1">
              <template #antes><Search class="size-4" aria-hidden="true" /></template>
            </Campo>
            <Selecao v-model="filtro.situacao" rotulo="Situação" :opcoes="situacoes" vazio="Todas" />
            <Selecao v-model="filtro.ordem" rotulo="Ordenar por" :opcoes="ORDENS_CONTAS" />
          </div>
          <p class="text-xs text-texto-fraco">Ativação: contatos, envios ligados, primeiro envio e primeira resposta, nessa ordem.</p>
        </div>

        <EstadoVazio
          v-if="!contas.length"
          :icone="filtrando ? Search : Building2"
          :titulo="filtrando ? 'Nenhuma conta com esses filtros' : 'Nenhuma conta ainda'"
          data-vazio-contas
        >
          <Botao v-if="filtrando" variante="secundario" tamanho="sm" @click="limparFiltros">Limpar filtros</Botao>
        </EstadoVazio>
        <template v-else>
          <!-- A partir de 1280 px: tabela -->
          <div class="hidden xl:block" data-tabela-contas>
            <Tabela :colunas="colunas" :linhas="contas" :chave="(c) => String(c.id)" legenda="Contas do Toqqi" densa>
              <template #cel-nome="{ linha: c }">
                <p class="font-semibold text-texto [overflow-wrap:anywhere]">{{ c.nome }}</p>
                <p v-if="c.admin_email" class="text-texto-suave"><TextoEmail :email="c.admin_email" /></p>
              </template>
              <template #cel-situacao="{ linha: c }">
                <Etiqueta :tom="rotuloSituacao(c.situacao).tom" data-situacao>{{ rotuloSituacao(c.situacao).rotulo }}</Etiqueta>
                <p class="mt-1 whitespace-nowrap text-xs text-texto-suave" data-plano>{{ textoPlano(c, nomeDoPlano) }}</p>
                <p class="text-xs text-texto-fraco">criada em {{ formatarData(c.criada_em) }}</p>
              </template>
              <template #cel-ativacao="{ linha: c }">
                <MarcadoresAtivacao :ativacao="c.ativacao" />
              </template>
              <template #cel-ultimo_acesso="{ linha: c }">
                <span class="text-texto-suave">{{ textoUltimoAcesso(c.ultimo_acesso) }}</span>
              </template>
              <template #cel-respostas="{ linha: c }">
                <p class="font-semibold tabular-nums text-texto">{{ formatarNumero(c.respostas_30d) }}</p>
                <p class="whitespace-nowrap text-xs text-texto-fraco">{{ formatarNumero(c.respostas_total) }} no total</p>
              </template>
              <template #cel-uso="{ linha: c }">
                <p class="whitespace-nowrap text-texto-suave"><span class="tabular-nums">{{ formatarNumero(c.contatos_ativos) }}</span> {{ c.contatos_ativos === 1 ? 'contato ativo' : 'contatos ativos' }}</p>
                <p class="whitespace-nowrap text-xs text-texto-fraco">{{ plural(c.convites_30d, 'convite', 'convites') }} em 30 dias</p>
                <p class="whitespace-nowrap text-xs text-texto-fraco">IA: {{ formatarNumero(c.ia_analises_mes) }} no mês</p>
              </template>
            </Tabela>
          </div>

          <!-- Celular, tablet e notebook com menos de 1280 px: lista -->
          <ul class="divide-y divide-borda xl:hidden" aria-label="Contas do Toqqi" data-lista-contas>
            <li v-for="c in contas" :key="String(c.id)" class="flex flex-col gap-2 px-4 py-3.5 sm:px-5" data-conta-visao>
              <div>
                <div class="flex flex-wrap items-start justify-between gap-2">
                  <p class="min-w-0 font-semibold text-texto [overflow-wrap:anywhere]">{{ c.nome }}</p>
                  <Etiqueta :tom="rotuloSituacao(c.situacao).tom">{{ rotuloSituacao(c.situacao).rotulo }}</Etiqueta>
                </div>
                <p v-if="c.admin_email" class="text-sm text-texto-suave"><TextoEmail :email="c.admin_email" /></p>
                <p class="text-xs text-texto-fraco">{{ linhaPlano(c) }}</p>
              </div>
              <div class="flex flex-wrap items-center gap-x-3 gap-y-1">
                <MarcadoresAtivacao :ativacao="c.ativacao" />
                <span class="text-xs text-texto-suave">{{ textoUltimoAcesso(c.ultimo_acesso) }}</span>
              </div>
              <dl class="grid grid-cols-2 gap-x-4 gap-y-1.5 text-xs sm:grid-cols-4">
                <div>
                  <dt class="text-texto-fraco">Respostas em 30 dias</dt>
                  <dd class="font-semibold tabular-nums text-texto">{{ formatarNumero(c.respostas_30d) }} <span class="font-normal text-texto-fraco">de {{ formatarNumero(c.respostas_total) }}</span></dd>
                </div>
                <div>
                  <dt class="text-texto-fraco">Contatos ativos</dt>
                  <dd class="font-semibold tabular-nums text-texto">{{ formatarNumero(c.contatos_ativos) }}</dd>
                </div>
                <div>
                  <dt class="text-texto-fraco">Convites em 30 dias</dt>
                  <dd class="font-semibold tabular-nums text-texto">{{ formatarNumero(c.convites_30d) }}</dd>
                </div>
                <div>
                  <dt class="text-texto-fraco">IA no mês</dt>
                  <dd class="font-semibold tabular-nums text-texto">{{ formatarNumero(c.ia_analises_mes) }}</dd>
                </div>
              </dl>
            </li>
          </ul>
        </template>
      </section>
    </template>
  </div>
</template>

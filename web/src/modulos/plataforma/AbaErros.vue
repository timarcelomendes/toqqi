<script setup lang="ts">
// Plataforma › Erros (etapa 5h, docs/api-etapa-5h.md §4): as falhas da API, do site e das tarefas, cada uma com quantas
// vezes aconteceu, onde, a versão e a pilha (sem dados pessoais: a API limpa antes de guardar). Filtros de origem,
// situação (abertos, resolvidos, todos) e período (7 ou 30 dias, pela última ocorrência); "Resolver" e "Reabrir" mudam o
// item na hora e ele fica na lista até a próxima busca (o foco continua no botão). Lista vazia: "Nenhum erro nos últimos
// N dias".
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { Bug, RefreshCw } from 'lucide-vue-next'
import { mensagemDoErro, plataformaApi, type ErroPlataforma } from '@/api'
import { avisar } from '@/composables/avisos'
import { formatarDataHora } from '@/utils/datas'
import Alerta from '@/components/ui/Alerta.vue'
import Botao from '@/components/ui/Botao.vue'
import Carregando from '@/components/ui/Carregando.vue'
import EstadoVazio from '@/components/ui/EstadoVazio.vue'
import Etiqueta from '@/components/ui/Etiqueta.vue'
import Selecao from '@/components/ui/Selecao.vue'
import {
  FILTROS_ERROS_PADRAO,
  ORIGENS_ERRO,
  PERIODOS_ERRO,
  SITUACOES_ERRO,
  descricaoVazio,
  rotuloOrigem,
  temFiltroErros,
  textoConta,
  textoOcorrencias,
  textoTotalErros,
  textoVazio,
  type FiltrosErrosTela,
} from './listaErros'

const filtros = reactive<FiltrosErrosTela>({ ...FILTROS_ERROS_PADRAO })
const itens = ref<ErroPlataforma[]>([])
const carregando = ref(true)
const carregou = ref(false)
const erro = ref<string | null>(null)
const ocupado = ref<string | null>(null)
/** Os filtros do último pedido (o total e o vazio falam deles, não do que está escolhido enquanto carrega). */
const aplicados = ref<FiltrosErrosTela>({ ...FILTROS_ERROS_PADRAO })
let controlador: AbortController | null = null

const temFiltro = computed(() => temFiltroErros(filtros))

async function carregar() {
  controlador?.abort()
  controlador = new AbortController()
  carregando.value = true
  erro.value = null
  const pedido = { ...filtros }
  try {
    itens.value = await plataformaApi.erros(pedido, controlador.signal)
    aplicados.value = pedido
    carregou.value = true
  } catch (e) {
    if (e instanceof DOMException && e.name === 'AbortError') return
    erro.value = mensagemDoErro(e)
  } finally {
    carregando.value = false
  }
}

watch(() => [filtros.origem, filtros.situacao, filtros.dias], () => void carregar())

async function alternar(e: ErroPlataforma) {
  if (ocupado.value) return
  const id = String(e.id)
  ocupado.value = id
  try {
    const novo = e.resolvido_em ? await plataformaApi.reabrirErro(e.id) : await plataformaApi.resolverErro(e.id)
    const i = itens.value.findIndex((x) => String(x.id) === id)
    if (i >= 0) itens.value.splice(i, 1, novo)
    avisar.sucesso(novo.resolvido_em ? `${e.tipo} marcado como resolvido.` : `${e.tipo} reaberto.`)
  } catch (err) {
    avisar.erro(mensagemDoErro(err))
  } finally {
    ocupado.value = null
  }
}

function limparFiltros() {
  Object.assign(filtros, FILTROS_ERROS_PADRAO)
}

onMounted(carregar)
onBeforeUnmount(() => controlador?.abort())
</script>

<template>
  <!-- Uma raiz só: a Plataforma esconde a aba com v-show -->
  <div class="flex flex-col gap-4" data-aba-erros>
    <div class="cartao grid gap-3 p-4 sm:grid-cols-3 sm:p-5" data-filtros-erros>
      <Selecao v-model="filtros.origem" rotulo="Origem" :opcoes="ORIGENS_ERRO" vazio="Todas" />
      <Selecao v-model="filtros.situacao" rotulo="Situação" :opcoes="SITUACOES_ERRO" />
      <Selecao v-model="filtros.dias" rotulo="Período" :opcoes="PERIODOS_ERRO" />
    </div>

    <div class="cartao">
      <div class="flex min-h-12 flex-wrap items-center justify-between gap-x-3 gap-y-2 border-b border-borda px-4 py-3 text-sm sm:px-5">
        <p class="text-texto-suave" aria-live="polite" data-total-erros>
          <template v-if="carregando">Carregando…</template>
          <template v-else-if="!erro">{{ textoTotalErros(itens.length, aplicados.situacao) }} nos últimos {{ aplicados.dias }} dias</template>
        </p>
        <div class="flex flex-wrap gap-2">
          <Botao v-if="temFiltro" variante="fantasma" tamanho="sm" data-limpar-filtros @click="limparFiltros">Limpar filtros</Botao>
          <Botao variante="secundario" tamanho="sm" :carregando="carregando && carregou" data-atualizar-erros @click="carregar">
            <RefreshCw class="size-4" aria-hidden="true" /> Atualizar
          </Botao>
        </div>
      </div>

      <div v-if="carregando && !carregou" class="p-5"><Carregando :linhas="4" rotulo="Carregando os erros" /></div>
      <Alerta v-else-if="erro" tom="erro" class="m-4" data-erro-erros>
        {{ erro }} <button type="button" class="link ml-1" @click="carregar">Tentar de novo</button>
      </Alerta>
      <EstadoVazio v-else-if="!itens.length" :icone="Bug" :titulo="textoVazio(aplicados.dias)" :descricao="descricaoVazio(aplicados)" data-vazio-erros />
      <ul v-else class="divide-y divide-borda" :class="{ 'opacity-60 transition-opacity': carregando }" :aria-busy="carregando" aria-label="Erros">
        <li v-for="e in itens" :key="String(e.id)" class="flex flex-col gap-2 px-4 py-4 sm:px-5" :data-erro="String(e.id)">
          <div class="flex flex-wrap items-start justify-between gap-x-4 gap-y-2">
            <div class="min-w-0 flex-1">
              <div class="flex flex-wrap items-center gap-2">
                <p class="font-semibold text-texto [overflow-wrap:anywhere]" data-tipo>{{ e.tipo }}</p>
                <Etiqueta :tom="rotuloOrigem(e.origem).tom" data-origem>{{ rotuloOrigem(e.origem).rotulo }}</Etiqueta>
                <Etiqueta v-if="e.resolvido_em" tom="sucesso" ponto data-resolvido>Resolvido</Etiqueta>
              </div>
              <p class="mt-1 text-sm text-texto-suave [overflow-wrap:anywhere]" data-mensagem>{{ e.mensagem || 'Sem mensagem.' }}</p>
            </div>
            <Botao
              :variante="e.resolvido_em ? 'fantasma' : 'secundario'"
              tamanho="sm"
              focavel
              :carregando="ocupado === String(e.id)"
              :data-alternar="e.resolvido_em ? 'reabrir' : 'resolver'"
              @click="alternar(e)"
            >
              {{ e.resolvido_em ? 'Reabrir' : 'Resolver' }}<span class="sr-only"> o erro {{ e.tipo }}</span>
            </Botao>
          </div>
          <p class="font-mono text-xs text-texto [overflow-wrap:anywhere]" data-local>{{ e.local || '—' }}</p>
          <dl class="flex flex-wrap gap-x-4 gap-y-1 text-xs text-texto-fraco">
            <div class="flex gap-1">
              <dt>Ocorrências:</dt>
              <dd class="font-semibold text-texto" data-ocorrencias>{{ textoOcorrencias(e.ocorrencias) }}</dd>
            </div>
            <div class="flex gap-1">
              <dt>Última:</dt>
              <dd>{{ formatarDataHora(e.ultima_em) }}</dd>
            </div>
            <div v-if="e.ocorrencias > 1" class="flex gap-1">
              <dt>Primeira:</dt>
              <dd>{{ formatarDataHora(e.primeira_em) }}</dd>
            </div>
            <div class="flex gap-1">
              <dt>Versão:</dt>
              <dd class="font-mono">{{ e.versao }}</dd>
            </div>
            <div v-if="textoConta(e)" class="flex gap-1">
              <dt>Conta:</dt>
              <dd data-conta>{{ textoConta(e) }}</dd>
            </div>
            <div v-if="e.ultimo_request_id" class="flex min-w-0 gap-1">
              <dt>Pedido:</dt>
              <dd class="font-mono [overflow-wrap:anywhere]">{{ e.ultimo_request_id }}</dd>
            </div>
            <div v-if="e.resolvido_em" class="flex gap-1">
              <dt>Resolvido em:</dt>
              <dd>{{ formatarDataHora(e.resolvido_em) }}</dd>
            </div>
          </dl>
          <details v-if="e.pilha" data-pilha>
            <summary class="w-fit cursor-pointer rounded-sm text-sm font-semibold text-marca-texto">Ver a pilha</summary>
            <pre class="mt-2 max-h-72 overflow-y-auto whitespace-pre-wrap rounded-xl bg-superficie-2 p-3 font-mono text-xs leading-relaxed text-texto-suave [overflow-wrap:anywhere]">{{ e.pilha }}</pre>
          </details>
        </li>
      </ul>
    </div>

    <div class="flex flex-col gap-1 text-sm text-texto-fraco" data-nota-erros>
      <p>Guardamos só o que ajuda a achar a falha (o tipo, a mensagem sem dados pessoais, onde aconteceu e a versão), por 30 dias depois da última vez.</p>
      <p>Com erro aberto, a equipe recebe um e-mail por dia, a partir das 8h. Uma nova ocorrência reabre o erro resolvido.</p>
    </div>
  </div>
</template>

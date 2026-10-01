<script setup lang="ts">
// Relatórios › Responsáveis: a carteira de cada responsável (empresas, NPS, receita, receita em risco, ações abertas
// e vencidas). Abrir uma linha mostra as empresas da carteira, com a nota média ou "Sem respostas". No computador é
// uma tabela; no celular, cartões.
import { computed, onBeforeUnmount, reactive, watch } from 'vue'
import { ChevronDown, ChevronRight, UserRound } from 'lucide-vue-next'
import { mensagemDoErro, relatoriosApi, type EmpresaDaCarteira, type Id, type ItemResponsavelRelatorio } from '@/api'
import { formatarMoeda, formatarNumero, plural } from '@/utils/formatos'
import { iniciais } from '@/utils/rotulos'
import BarraGrupos from '@/components/app/BarraGrupos.vue'
import Alerta from '@/components/ui/Alerta.vue'
import EstadoVazio from '@/components/ui/EstadoVazio.vue'
import Etiqueta from '@/components/ui/Etiqueta.vue'
import { formatarPct } from '@/modulos/painel/logica'
import CarteiraEmpresas from './CarteiraEmpresas.vue'
import SeloNps from './SeloNps.vue'
import { comunsParaApi, numero, type AbaRelatorio, type FiltrosRelatorioTela } from './logica'
import { usarRelatorio } from './usarRelatorio'

const props = defineProps<{ hoje: string; pronto: boolean }>()
const filtros = defineModel<FiltrosRelatorioTela>('filtros', { required: true })
const emit = defineEmits<{ navegar: [para: AbaRelatorio, extra: Partial<FiltrosRelatorioTela>] }>()

const consulta = computed(() => comunsParaApi(filtros.value, props.hoje))
const chaveConsulta = computed(() => JSON.stringify(consulta.value))
const { dados, carregando, atualizando, erro, carregar } = usarRelatorio(
  (sinal) => relatoriosApi.responsaveis(consulta.value, sinal),
  () => chaveConsulta.value,
  () => props.pronto,
)

const itens = computed(() => dados.value?.itens ?? [])

/**
 * Empresas de cada carteira (0 = sem responsável): buscadas ao abrir, guardadas com os filtros do pedido (`chave`) e
 * buscadas de novo quando os filtros mudam (na hora, se a carteira está aberta; ao abrir, se está fechada).
 */
interface Carteira {
  aberta: boolean
  carregando: boolean
  erro: string | null
  empresas: EmpresaDaCarteira[] | null
  /** Os filtros dos dados que estão na tela. */
  chave: string
}
const carteiras = reactive<Record<string, Carteira>>({})
/** O pedido em andamento de cada carteira: um novo cancela o anterior, e resposta de pedido velho é ignorada. */
const pedidos = new Map<string, { controle: AbortController; chave: string }>()

const idDe = (x: ItemResponsavelRelatorio): Id => x.responsavel?.id ?? 0
const chaveDe = (x: ItemResponsavelRelatorio) => String(idDe(x))
const nomeDe = (x: ItemResponsavelRelatorio) => x.responsavel?.nome ?? 'Sem responsável'
const aberta = (x: ItemResponsavelRelatorio) => !!carteiras[chaveDe(x)]?.aberta

async function buscarCarteira(id: Id) {
  const k = String(id)
  const c = carteiras[k]
  if (!c || !props.pronto) return
  // Os filtros do pedido são os de agora (lidos antes de esperar a resposta).
  const chave = chaveConsulta.value
  const filtrosDoPedido = consulta.value
  pedidos.get(k)?.controle.abort()
  const controle = new AbortController()
  pedidos.set(k, { controle, chave })
  const meu = () => pedidos.get(k)?.controle === controle
  c.carregando = true
  c.erro = null
  try {
    const empresas = await relatoriosApi.empresasDoResponsavel(id, filtrosDoPedido, controle.signal)
    if (!meu()) return
    c.empresas = empresas
    c.chave = chave
  } catch (e) {
    if (!meu() || (e instanceof DOMException && e.name === 'AbortError')) return
    c.erro = mensagemDoErro(e)
  } finally {
    if (meu()) {
      pedidos.delete(k)
      c.carregando = false
    }
  }
}

/** Os dados guardados (ou o pedido em andamento) são dos filtros de agora. */
function emDia(k: string, c: Carteira): boolean {
  const pedido = pedidos.get(k)
  return pedido ? pedido.chave === chaveConsulta.value : c.empresas !== null && c.chave === chaveConsulta.value
}

function alternar(x: ItemResponsavelRelatorio) {
  const k = chaveDe(x)
  const c = (carteiras[k] ??= { aberta: false, carregando: false, erro: null, empresas: null, chave: '' })
  c.aberta = !c.aberta
  // Busca ao abrir (ou de novo, se os filtros mudaram desde os dados guardados).
  if (c.aberta && !emDia(k, c)) buscarCarteira(idDe(x))
}

// Outro período, grupo ou "só ativas": as carteiras abertas buscam de novo na hora (as fechadas, quando abrirem).
watch([chaveConsulta, () => props.pronto], () => {
  for (const [k, c] of Object.entries(carteiras)) {
    if (c.aberta && !emDia(k, c)) buscarCarteira(k)
  }
})
onBeforeUnmount(() => {
  for (const p of pedidos.values()) p.controle.abort()
  pedidos.clear()
})

function abrirHistorico(id: Id) {
  emit('navegar', 'historico', { empresa_id: id })
}

const emRisco = (x: ItemResponsavelRelatorio) => (numero(x.receita_em_risco) ?? 0) > 0
const pctRisco = (x: ItemResponsavelRelatorio) => {
  const total = numero(x.receita) ?? 0
  return total > 0 ? Math.round(((numero(x.receita_em_risco) ?? 0) / total) * 1000) / 10 : null
}
const resumoLinha = (x: ItemResponsavelRelatorio) => `${plural(x.empresas, 'empresa', 'empresas')} · ${formatarNumero(x.empresas_com_respostas)} com respostas`
</script>

<template>
  <div class="flex flex-col gap-4">
    <div v-if="carregando && !dados" class="cartao p-5" role="status" aria-label="Carregando os responsáveis">
      <div v-for="i in 4" :key="i" class="mb-5 flex items-center gap-3 last:mb-0">
        <div class="size-10 animate-pulse rounded-full bg-superficie-2" />
        <div class="h-4 flex-1 animate-pulse rounded bg-superficie-2" />
      </div>
      <span class="sr-only">Carregando…</span>
    </div>

    <Alerta v-else-if="erro && !dados" tom="erro">
      {{ erro }} <button type="button" class="link ml-1" @click="carregar">Tentar de novo</button>
    </Alerta>

    <section v-else-if="dados" class="cartao transition-opacity" :class="atualizando ? 'opacity-60' : ''" :aria-busy="atualizando || undefined" aria-labelledby="t-carteiras">
      <header class="border-b border-borda p-5 sm:px-6">
        <h2 id="t-carteiras" class="text-base font-bold text-texto">Carteiras</h2>
        <p class="text-sm text-texto-suave">Responsável = quem cuida da empresa no cadastro. Do NPS mais baixo para o mais alto; quem não tem respostas fica no fim.</p>
      </header>
      <Alerta v-if="erro" tom="erro" class="m-4">
        Não deu para atualizar: {{ erro }} <button type="button" class="link ml-1" @click="carregar">Tentar de novo</button>
      </Alerta>

      <EstadoVazio v-if="!itens.length" :icone="UserRound" titulo="Nenhuma empresa neste filtro" descricao="As carteiras aparecem quando as empresas têm responsável no cadastro (Contatos › Empresas)." />

      <template v-else>
        <!-- Computador (a partir de 1280 px): tabela; o nome abre a lista de empresas da carteira. Se ainda faltar
             espaço (menu aberto e janela estreita), a tabela rola dentro do cartão, nunca a página. -->
        <div class="hidden overflow-x-auto xl:block">
          <table class="w-full border-collapse text-sm">
            <caption class="sr-only">Carteiras por responsável</caption>
            <thead>
              <tr class="border-b border-borda text-xs font-semibold uppercase tracking-wide text-texto-fraco">
                <th scope="col" class="py-2.5 pl-5 pr-3 text-left">Responsável</th>
                <th scope="col" class="px-3 py-2.5 text-left">NPS</th>
                <th scope="col" class="px-3 py-2.5 text-left">Respostas de NPS</th>
                <th scope="col" class="px-3 py-2.5 text-right">Receita mensal</th>
                <th scope="col" class="py-2.5 pl-3 pr-5 text-right">Ações abertas</th>
              </tr>
            </thead>
            <tbody>
              <template v-for="x in itens" :key="chaveDe(x)">
                <tr class="border-b border-borda" :class="aberta(x) ? 'bg-superficie-2/40' : ''">
                  <th scope="row" class="w-[34%] py-2.5 pl-3 pr-3 text-left font-normal">
                    <button
                      type="button"
                      class="flex w-full items-center gap-2.5 rounded-xl px-2 py-1.5 text-left transition-colors hover:bg-superficie-2"
                      :aria-expanded="aberta(x)"
                      :aria-controls="carteiras[chaveDe(x)] ? `carteira-${chaveDe(x)}` : undefined"
                      @click="alternar(x)"
                    >
                      <ChevronRight class="size-4 shrink-0 text-texto-fraco transition-transform" :class="aberta(x) ? 'rotate-90' : ''" aria-hidden="true" />
                      <span class="flex size-9 shrink-0 items-center justify-center rounded-full text-xs font-bold" :class="x.responsavel ? 'bg-marca-suave text-marca-texto' : 'bg-superficie-2 text-texto-fraco'" aria-hidden="true">
                        <img v-if="x.responsavel?.foto_url" :src="x.responsavel.foto_url" alt="" class="size-9 rounded-full object-cover" />
                        <template v-else-if="x.responsavel">{{ iniciais(x.responsavel.nome) }}</template>
                        <UserRound v-else class="size-4" />
                      </span>
                      <span class="min-w-0">
                        <span class="block break-words font-semibold text-texto">{{ nomeDe(x) }}</span>
                        <span class="block text-xs text-texto-fraco">{{ resumoLinha(x) }}</span>
                      </span>
                    </button>
                  </th>
                  <td class="px-3 py-2.5"><SeloNps :nps="x.nps" /></td>
                  <td class="px-3 py-2.5">
                    <BarraGrupos v-if="x.nps.total" legenda="nenhuma" fina class="min-w-24" :detratores="x.nps.detratores" :neutros="x.nps.neutros" :promotores="x.nps.promotores" />
                    <span class="mt-1 block text-xs text-texto-fraco">{{ plural(x.nps.total, 'resposta', 'respostas') }}</span>
                  </td>
                  <td class="px-3 py-2.5 text-right">
                    <span class="block whitespace-nowrap tabular-nums text-texto">{{ formatarMoeda(x.receita, 'R$ 0,00') }}</span>
                    <span v-if="emRisco(x)" class="block text-xs font-semibold text-erro">
                      <span class="whitespace-nowrap">{{ formatarMoeda(x.receita_em_risco) }}</span> em risco<template v-if="pctRisco(x) !== null"> ({{ formatarPct(pctRisco(x)) }})</template>
                    </span>
                    <span v-else class="block text-xs text-texto-fraco">nada em risco</span>
                  </td>
                  <td class="py-2.5 pl-3 pr-5 text-right">
                    <span class="block tabular-nums" :class="x.acoes_abertas ? 'font-semibold text-texto' : 'text-texto-fraco'">{{ formatarNumero(x.acoes_abertas) }}</span>
                    <Etiqueta v-if="x.acoes_vencidas" tom="erro" ponto class="mt-1">{{ plural(x.acoes_vencidas, 'vencida', 'vencidas') }}</Etiqueta>
                  </td>
                </tr>
                <tr v-if="carteiras[chaveDe(x)]" v-show="aberta(x)" :id="`carteira-${chaveDe(x)}`" class="border-b border-borda bg-superficie-2/40">
                  <td colspan="5" class="px-5 pb-3 pt-1">
                    <CarteiraEmpresas
                      :nome="nomeDe(x)"
                      :carregando="carteiras[chaveDe(x)]!.carregando"
                      :erro="carteiras[chaveDe(x)]!.erro"
                      :empresas="carteiras[chaveDe(x)]!.empresas"
                      class="pl-9"
                      @historico="abrirHistorico"
                      @tentar="buscarCarteira(idDe(x))"
                    />
                  </td>
                </tr>
              </template>
            </tbody>
          </table>
        </div>

        <!-- Celular, tablet e telas até 1280 px: cartões; o cabeçalho do cartão abre a lista de empresas -->
        <ul class="flex flex-col divide-y divide-borda xl:hidden">
          <li v-for="x in itens" :key="chaveDe(x)" class="flex flex-col">
            <button
              type="button"
              class="flex w-full items-center gap-3 px-4 pb-2 pt-4 text-left transition-colors hover:bg-superficie-2/50 sm:px-6"
              :aria-expanded="aberta(x)"
              :aria-controls="carteiras[chaveDe(x)] ? `carteira-m-${chaveDe(x)}` : undefined"
              @click="alternar(x)"
            >
              <span class="flex size-10 shrink-0 items-center justify-center rounded-full text-sm font-bold" :class="x.responsavel ? 'bg-marca-suave text-marca-texto' : 'bg-superficie-2 text-texto-fraco'" aria-hidden="true">
                <img v-if="x.responsavel?.foto_url" :src="x.responsavel.foto_url" alt="" class="size-10 rounded-full object-cover" />
                <template v-else-if="x.responsavel">{{ iniciais(x.responsavel.nome) }}</template>
                <UserRound v-else class="size-5" />
              </span>
              <span class="min-w-0 flex-1">
                <span class="block truncate font-semibold text-texto">{{ nomeDe(x) }}</span>
                <span class="block text-sm text-texto-fraco">{{ resumoLinha(x) }}</span>
              </span>
              <SeloNps :nps="x.nps" compacto />
              <ChevronDown class="size-5 shrink-0 text-texto-fraco transition-transform" :class="aberta(x) ? 'rotate-180' : ''" aria-hidden="true" />
            </button>
            <div class="flex flex-col gap-2 px-4 pb-4 sm:px-6">
              <BarraGrupos v-if="x.nps.total" legenda="nenhuma" fina :detratores="x.nps.detratores" :neutros="x.nps.neutros" :promotores="x.nps.promotores" />
              <p class="flex flex-wrap gap-x-4 gap-y-1 text-sm">
                <span class="text-texto-suave">Receita <strong class="font-semibold text-texto">{{ formatarMoeda(x.receita, 'R$ 0,00') }}</strong></span>
                <span :class="emRisco(x) ? 'text-erro' : 'text-texto-fraco'">
                  Em risco <strong class="font-semibold">{{ formatarMoeda(x.receita_em_risco, 'R$ 0,00') }}</strong><template v-if="emRisco(x) && pctRisco(x) !== null"> ({{ formatarPct(pctRisco(x)) }})</template>
                </span>
              </p>
              <p class="text-sm text-texto-suave">
                {{ plural(x.nps.total, 'resposta', 'respostas') }} de NPS ·
                <strong class="font-semibold text-texto">{{ formatarNumero(x.acoes_abertas) }}</strong> {{ x.acoes_abertas === 1 ? 'ação aberta' : 'ações abertas' }}
                <Etiqueta v-if="x.acoes_vencidas" tom="erro" ponto class="ml-1">{{ plural(x.acoes_vencidas, 'vencida', 'vencidas') }}</Etiqueta>
              </p>
            </div>
            <div v-if="carteiras[chaveDe(x)]" v-show="aberta(x)" :id="`carteira-m-${chaveDe(x)}`" class="border-t border-borda bg-superficie-2/40 px-4 py-2 sm:px-6">
              <CarteiraEmpresas
                :nome="nomeDe(x)"
                :carregando="carteiras[chaveDe(x)]!.carregando"
                :erro="carteiras[chaveDe(x)]!.erro"
                :empresas="carteiras[chaveDe(x)]!.empresas"
                @historico="abrirHistorico"
                @tentar="buscarCarteira(idDe(x))"
              />
            </div>
          </li>
        </ul>
      </template>
    </section>
  </div>
</template>

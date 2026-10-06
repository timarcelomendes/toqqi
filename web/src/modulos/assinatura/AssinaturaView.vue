<script setup lang="ts">
// Assinatura (etapa 5a, só com `assinatura.gerenciar`).
// - Sem assinatura: a situação da conta, os contatos ativos, os 3 planos e, escolhido um, o formulário de cobrança
//   (preenchido com os dados da empresa) com o resumo da primeira fatura e "Assinar".
// - Com assinatura: o plano e a situação, a fatura em aberto ("Pagar" abre a fatura do Asaas em nova aba), o próximo
//   vencimento, trocar de plano, os dados de cobrança, cancelar e o histórico de cobranças.
// - Depois de assinar (ou de clicar em "Pagar"), busca de novo a cada 10 s por até 2 min, até a fatura esperada
//   aparecer paga (o Asaas cria a do mês seguinte até 40 dias antes: pode haver outra em aberto). Quando a conta
//   difere da sessão (pagou noutro aparelho, venceu...), atualiza a sessão: o aviso do topo e os envios dependem dela.
// - Etapa 5g: assinar e trocar de plano mandam sempre o preço que a tela mostrou; se ele mudou (409 `preco_mudou`), a
//   tela busca os planos de novo e mostra a mensagem da API (ninguém paga o que não viu). Se a API recusar o preço
//   mandado (422 no campo `preco`, ex.: página aberta antes de uma atualização do site), o alerta traz a mensagem dela
//   ("Recarregue a página para ver o preço atual do plano.") e "Recarregar", que recarrega a página.
// - Etapa 5k: antes dos planos, Mensal ou Anual (com o desconto) e, no mensal, Pix (com desconto) ou cartão e boleto;
//   os cartões mostram o valor da fatura nessa escolha, e o Personalizado entra com a calculadora. O que vai em
//   `preco` é sempre o valor mostrado (a API refaz a conta e devolve 409 `preco_mudou` se mudou).
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { ArrowRightLeft, CreditCard, ExternalLink, FileText, Pencil, RefreshCw, XCircle } from 'lucide-vue-next'
import { assinaturaApi, mensagemDoErro, type EstadoAssinatura, type FaturaAberta } from '@/api'
import { publicoApi } from '@/api/publico'
import type { PlanoAssinatura } from '@/api/tipos'
import { avisar } from '@/composables/avisos'
import { confirmar } from '@/composables/confirmacao'
import { useFormulario } from '@/composables/formulario'
import { useSessaoStore } from '@/stores/sessao'
import { formatarData } from '@/utils/datas'
import { exibirTelefone, formatarDocumento, formatarMoeda, formatarNumero } from '@/utils/formatos'
import CabecalhoPagina from '@/components/app/CabecalhoPagina.vue'
import Alerta from '@/components/ui/Alerta.vue'
import Botao from '@/components/ui/Botao.vue'
import Carregando from '@/components/ui/Carregando.vue'
import Etiqueta from '@/components/ui/Etiqueta.vue'
import Medidor from '@/components/ui/Medidor.vue'
import BotoesSegmentados from '@/components/ui/BotoesSegmentados.vue'
import type { Ciclo, Forma } from '@/utils/precos'
import CamposCobranca from './CamposCobranca.vue'
import ComparativoPlanos from './ComparativoPlanos.vue'
import EscolhaPlano from './EscolhaPlano.vue'
import HistoricoCobrancas from './HistoricoCobrancas.vue'
import ModalDadosCobranca from './ModalDadosCobranca.vue'
import ModalTrocarPlano from './ModalTrocarPlano.vue'
import {
  INTERVALO_ESPERA_MS,
  LIMITE_ESPERA_MS,
  TEMPO_CONFIRMACAO,
  corpoCobranca,
  emAberto,
  faturaFutura,
  faturasEmAberto,
  faturasPagas,
  formCobrancaDe,
  listaDeDatas,
  mensagemCancelamento,
  mesmaFatura,
  planoPorChave,
  proximoVencimento,
  resumoPrimeiraFatura,
  situacaoCobranca,
  situacaoNaTela,
  textoPeriodo,
  validarCobranca,
  contatosSugeridos,
  descontosDe,
  exibido,
  planoPersonalizado,
  tabelaDe,
  textoForma,
  textoPorPeriodo,
  type FormCobranca,
  type PlanoExibido,
} from './logica'

const sessao = useSessaoStore()
const dados = ref<EstadoAssinatura | null>(null)
const carregando = ref(true)
const erroCarga = ref<string | null>(null)

const assinatura = computed(() => dados.value?.assinatura ?? null)
const fatura = computed(() => (emAberto(dados.value?.fatura_aberta) ? dados.value!.fatura_aberta : null))
/** Conta ativa e a fatura em aberto só vence daqui a mais de 5 dias: "Próxima fatura", sem pressa de pagar. */
const futura = computed(() => !!dados.value && faturaFutura(dados.value))
/** As outras faturas em aberto (além da mostrada no cartão). */
const outrasAbertas = computed(() => (dados.value && fatura.value ? faturasEmAberto(dados.value).filter((f) => !mesmaFatura(f, fatura.value!)) : []))
const cortesia = computed(() => dados.value?.conta.situacao === 'cortesia')
const situacao = computed(() => (dados.value ? situacaoNaTela(dados.value) : null))
const planoAtual = computed(() => (dados.value ? planoPorChave(dados.value.planos, assinatura.value?.plano ?? dados.value.conta.plano) : null))
const limite = computed(() => {
  if (cortesia.value || !dados.value) return null
  if ((assinatura.value?.plano ?? dados.value.conta.plano) === 'personalizado') return dados.value.conta.contatos_personalizado ?? null
  return planoAtual.value?.contatos ?? null
})
const proximo = computed(() => (dados.value ? proximoVencimento(dados.value) : null))
const titulo = computed(() =>
  assinatura.value ? `Plano ${assinatura.value.nome ?? planoAtual.value?.nome ?? assinatura.value.plano}` : (situacao.value?.titulo ?? 'Assinatura'),
)
const cicloAtual = computed<Ciclo>(() => assinatura.value?.ciclo ?? 'mensal')

function aplicar(e: EstadoAssinatura) {
  const antes = dados.value
  dados.value = e
  ultimaBusca = Date.now()
  sincronizarSessao(e)
  if (antes) reagir(antes, e)
}

/** Busca /eu de novo (o aviso do topo, o plano e se os envios estão liberados); duas chamadas juntas viram uma. */
let recarregandoSessao: Promise<unknown> | null = null
function atualizarSessao() {
  recarregandoSessao ??= sessao
    .recarregar()
    .catch(() => undefined)
    .finally(() => (recarregandoSessao = null))
}

async function carregar() {
  carregando.value = true
  erroCarga.value = null
  try {
    const e = await assinaturaApi.obter()
    dados.value = e
    ultimaBusca = Date.now()
    form.value = formCobrancaDe(e.dados_sugeridos)
    contatosPers.value = contatosSugeridos(e.contatos_ativos, tabelaDe(e))
    sincronizarSessao(e)
    completarLimites(e)
  } catch (e) {
    erroCarga.value = mensagemDoErro(e)
  } finally {
    carregando.value = false
  }
}

/**
 * A sessão (buscada ao abrir o app) diz outra coisa que a tela: pagou pelo e-mail do Asaas ou noutro aparelho, a
 * fatura venceu, assinou noutra aba. Busca /eu de novo para o aviso do topo e os envios acompanharem.
 */
function sincronizarSessao(e: EstadoAssinatura) {
  const c = sessao.conta
  if (!c) return
  const cobranca = c.cobranca
  const assinadaDifere = typeof cobranca?.assinada === 'boolean' && cobranca.assinada !== !!e.assinatura
  if (c.situacao !== e.conta.situacao || cobranca?.liberada !== e.conta.liberada || assinadaDifere) atualizarSessao()
}

/** Pagamentos que chegaram desde a busca anterior; a fatura esperada paga (ou cancelada) encerra a espera. */
function reagir(antes: EstadoAssinatura, depois: EstadoAssinatura) {
  const esperada = alvo
  const esperadaPaga = !!esperada && depois.cobrancas.some((c) => c.situacao === 'paga' && mesmaFatura(c, esperada))
  if (esperadaPaga || faturasPagas(antes.cobrancas, depois.cobrancas).length) {
    avisar.sucesso(depois.conta.situacao === 'ativa' ? 'Pagamento confirmado. Sua assinatura está ativa.' : 'Pagamento confirmado.')
  }
  const esperadaCancelada = !!esperada && depois.cobrancas.some((c) => c.situacao === 'removida' && mesmaFatura(c, esperada))
  if (esperadaPaga || esperadaCancelada) pararEspera()
}

/** Busca de novo sem trocar a tela pelo esqueleto (se falhar, fica o que está na tela). */
async function atualizar(): Promise<boolean> {
  try {
    aplicar(await assinaturaApi.obter())
    return true
  } catch {
    return false
  }
}

// ── Espera pelo pagamento ────────────────────────────────────────────────────
type FaturaEsperada = Pick<FaturaAberta, 'vencimento' | 'link'>
const esperando = ref(false)
/** A fatura que a pessoa está pagando (null logo depois de assinar, se o Asaas ainda não mandou a primeira). */
let alvo: FaturaEsperada | null = null
let temporizador: ReturnType<typeof setTimeout> | null = null
let inicioEspera = 0
let ultimaBusca = 0
/** Cada espera nova (ou parada) invalida as anteriores: uma busca que volta depois não agenda outra rodada. */
let geracao = 0

function pararEspera() {
  geracao++
  if (temporizador) clearTimeout(temporizador)
  temporizador = null
  esperando.value = false
  alvo = null
}

/** Espera o pagamento de `f` (ou, sem ela, a primeira fatura chegar e ser paga): busca de 10 em 10 s, por até 2 min. */
function esperarPagamento(f: FaturaEsperada | null) {
  pararEspera()
  if (!dados.value?.assinatura) return
  alvo = f ? { vencimento: f.vencimento, link: f.link } : null
  inicioEspera = Date.now()
  esperando.value = true
  agendar(geracao)
}

function agendar(minha: number) {
  temporizador = setTimeout(async () => {
    temporizador = null
    await atualizar()
    if (minha !== geracao) return
    if (Date.now() - inicioEspera >= LIMITE_ESPERA_MS) {
      pararEspera()
      return
    }
    // Assinou e a fatura ainda não tinha chegado do Asaas: agora espera o pagamento dela.
    if (!alvo && fatura.value) alvo = { vencimento: fatura.value.vencimento, link: fatura.value.link }
    agendar(minha)
  }, INTERVALO_ESPERA_MS)
}

/** Voltou para a aba (talvez depois de pagar na do Asaas ou noutro aparelho): confere de novo, no máximo a cada 10 s. */
function aoVoltarParaAba() {
  if (document.visibilityState !== 'visible' || esperando.value || !dados.value) return
  if (Date.now() - ultimaBusca >= INTERVALO_ESPERA_MS) atualizar()
}

const atualizando = ref(false)
async function atualizarAgora() {
  if (atualizando.value) return
  atualizando.value = true
  const antes = JSON.stringify(dados.value)
  const ok = await atualizar()
  atualizando.value = false
  if (!ok) avisar.erro('Não deu para conferir agora. Tente de novo em instantes.')
  else if (JSON.stringify(dados.value) === antes) {
    avisar.info(fatura.value && !futura.value ? `Conferido: nada mudou, a fatura continua em aberto. A confirmação leva: ${TEMPO_CONFIRMACAO}.` : 'Conferido: nada mudou.')
  }
}

// ── Assinar ──────────────────────────────────────────────────────────────────
const planoEscolhido = ref<string | null>(null)
const ciclo = ref<Ciclo>('mensal')
/** Pix é a sugestão (o desconto aparece já no cartão); cartão e boleto pagam o preço cheio. */
const forma = ref<Forma>('pix')
const contatosPers = ref(1000)
const cotaPers = ref(500)
const descontos = computed(() => descontosDe(dados.value))
const tabela = computed(() => tabelaDe(dados.value))
const OPCOES_CICLO = computed(() => [
  { valor: 'mensal' as Ciclo, rotulo: 'Mensal' },
  { valor: 'anual' as Ciclo, rotulo: descontos.value.anual ? `Anual: ${descontos.value.anual}% off` : 'Anual' },
])
const OPCOES_FORMA = computed(() => [
  { valor: 'pix' as Forma, rotulo: descontos.value.pix ? `Pix: ${descontos.value.pix}% off` : 'Pix' },
  { valor: 'qualquer' as Forma, rotulo: 'Cartão ou boleto' },
])
const planosExibidos = computed<PlanoExibido[]>(() =>
  dados.value ? planosCompletos.value.map((p) => exibido(p, ciclo.value, forma.value, descontos.value)) : [],
)
const persExibido = computed<PlanoExibido | null>(() => {
  const p = planoPersonalizado(tabela.value, contatosPers.value, cotaPers.value)
  return p ? { ...exibido(p, ciclo.value, forma.value, descontos.value), cota_ia: p.cota_ia } : null
})
const plano = computed<PlanoExibido | null>(() => {
  if (!dados.value || !planoEscolhido.value) return null
  if (planoEscolhido.value === 'personalizado') return persExibido.value
  return planoPorChave(planosExibidos.value, planoEscolhido.value)
})
/**
 * Cota do ToqqiAI, comentários lidos pela IA e WhatsApp de cada plano: vêm em GET /assinatura; se a API ainda não os
 * manda (subiu depois do site), completa com GET /publico/planos, que os tem desde a 5g.
 */
const limitesPublicos = ref<Record<string, Pick<PlanoAssinatura, 'ia_cota' | 'ia_teto' | 'whatsapp'>>>({})
async function completarLimites(e: EstadoAssinatura) {
  if (e.planos.every((p) => p.ia_cota !== undefined && p.ia_teto !== undefined)) return
  try {
    const pub = await publicoApi.planos()
    limitesPublicos.value = Object.fromEntries(
      pub.planos.map((p) => [String(p.chave), { ia_cota: p.ia_cota, ia_teto: p.ia_teto, whatsapp: p.whatsapp ?? null }]),
    )
  } catch {
    /* sem resposta: a comparação mostra "—" nessas linhas */
  }
}
const planosCompletos = computed<PlanoAssinatura[]>(() =>
  (dados.value?.planos ?? []).map((p) => ({ ...(limitesPublicos.value[String(p.chave)] ?? {}), ...Object.fromEntries(Object.entries(p).filter(([, v]) => v !== undefined)) }) as PlanoAssinatura),
)

/** Com assinatura: os planos no ciclo e na forma dela (a comparação mostra o que cada um custaria hoje). */
const planosDaAssinatura = computed<PlanoExibido[]>(() =>
  dados.value && assinatura.value
    ? planosCompletos.value.map((p) => exibido(p, cicloAtual.value, assinatura.value!.forma ?? 'qualquer', descontos.value))
    : [],
)
const persDaAssinatura = computed<PlanoExibido | null>(() => {
  const a = assinatura.value
  if (!a) return null
  const contatos = a.plano === 'personalizado' && a.contatos ? a.contatos : contatosPers.value
  const cota = a.plano === 'personalizado' && a.cota_ia ? a.cota_ia : cotaPers.value
  const p = planoPersonalizado(tabela.value, contatos, cota)
  return p ? { ...exibido(p, cicloAtual.value, a.forma ?? 'qualquer', descontos.value), cota_ia: p.cota_ia } : null
})
const trocaInicial = ref<string | null>(null)
function trocarPara(chave: string | null) {
  trocaInicial.value = chave
  trocarAberto.value = true
}
const plano_cabe = computed(() => !plano.value || plano.value.contatos === null || dados.value!.contatos_ativos <= plano.value.contatos)
const resumo = computed(() => (dados.value && plano.value ? resumoPrimeiraFatura(plano.value, dados.value.conta, new Date(), plano.value.ciclo) : null))
const emTeste = computed(() => dados.value?.conta.situacao === 'teste')
const form = ref<FormCobranca>(formCobrancaDe(null))
const locais = reactive<Partial<Record<keyof FormCobranca, string>>>({})
const { enviando, erroGeral, codigoErro, erros, executar, limpar } = useFormulario()
const errosForm = computed(() => ({
  razao_social: locais.razao_social ?? erros.razao_social,
  documento: locais.documento ?? erros.documento,
  email_cobranca: locais.email_cobranca ?? erros.email_cobranca,
  telefone: locais.telefone ?? erros.telefone,
}))
const secaoForm = ref<HTMLElement | null>(null)
const formAssinar = ref<HTMLFormElement | null>(null)
/** 422 no campo `preco`: a API não aceitou o preço que esta tela mandou; só recarregando a página. */
const erroPreco = computed(() => erros.preco ?? null)

function recarregarPagina() {
  location.reload()
}

function limparErros() {
  limpar()
  for (const k of Object.keys(locais) as (keyof FormCobranca)[]) delete locais[k]
}

/** Escolheu com mouse ou toque e o formulário ficou lá embaixo: leva a tela até ele (com o teclado, o Tab chega lá). */
async function aoEscolherPlano(_chave: string, porPonteiro: boolean) {
  if (!porPonteiro) return
  await nextTick()
  const s = secaoForm.value
  if (!s || typeof s.scrollIntoView !== 'function') return
  if (s.getBoundingClientRect().top > window.innerHeight * 0.6) {
    const semMovimento = typeof window.matchMedia === 'function' && window.matchMedia('(prefers-reduced-motion: reduce)').matches
    s.scrollIntoView({ block: 'start', behavior: semMovimento ? 'auto' : 'smooth' })
  }
}

async function focarPrimeiroErro() {
  await nextTick()
  formAssinar.value?.querySelector<HTMLElement>('[aria-invalid="true"]')?.focus()
}

async function assinar() {
  const p = plano.value
  if (!dados.value || !p || enviando.value) return
  limparErros()
  const v = validarCobranca(form.value)
  if (Object.keys(v).length) {
    Object.assign(locais, v)
    erroGeral.value = 'Confira os campos destacados.'
    focarPrimeiroErro()
    return
  }
  if (!plano_cabe.value) {
    erroGeral.value = `Você tem ${formatarNumero(dados.value.contatos_ativos)} contatos ativos: escolha pelo menos esse número no Personalizado.`
    return
  }
  const r = await executar(() =>
    assinaturaApi.assinar({
      ...corpoCobranca(form.value),
      plano: p.chave,
      ciclo: p.ciclo,
      forma: p.forma,
      ...(p.chave === 'personalizado' ? { contatos: p.contatos, cota_ia: p.cota_ia } : {}),
      preco: p.preco,
    }),
  )
  if (!r) {
    // Já tem assinatura ou virou cortesia (outra aba, a equipe Toqqi): mostra como está agora.
    if (codigoErro.value === 'ja_assinada' || codigoErro.value === 'cortesia') {
      avisar.atencao(erroGeral.value ?? 'A situação da assinatura mudou.')
      await carregar()
    } else if (codigoErro.value === 'limite_do_plano') {
      // A contagem de contatos ativos mudou desde que a tela abriu: os cartões mostram a de agora.
      await atualizar()
    } else if (codigoErro.value === 'preco_mudou') {
      // O preço do plano mudou desde que a tela abriu: os cartões e o resumo da fatura mostram o de agora.
      await atualizar()
    } else if (erroPreco.value) {
      // Nenhum campo do formulário a corrigir: o foco vai ao "Recarregar" do alerta.
      await nextTick()
      formAssinar.value?.querySelector<HTMLElement>('[data-recarregar]')?.focus()
    } else focarPrimeiroErro()
    return
  }
  planoEscolhido.value = null
  aplicar(r)
  atualizarSessao()
  const f = emAberto(r.fatura_aberta) ? r.fatura_aberta : null
  avisar.sucesso(f ? `Assinatura feita! A primeira fatura vence em ${formatarData(f.vencimento)}.` : 'Assinatura feita!')
  // Sem a fatura ainda (o Asaas demorou), espera ela chegar também.
  esperarPagamento(f)
  await nextTick()
  document.getElementById(f ? 't-fatura' : 't-situacao')?.focus()
}

// ── Trocar de plano, dados de cobrança e cancelar ───────────────────────────
const trocarAberto = ref(false)
const dadosAberto = ref(false)
const cancelando = ref(false)

function aoMudarAssinatura(e: EstadoAssinatura) {
  aplicar(e)
  // O plano da conta (limite de contatos) está na sessão.
  atualizarSessao()
}

async function cancelar() {
  const d = dados.value
  if (!d?.assinatura || cancelando.value) return
  const ok = await confirmar({
    titulo: 'Cancelar a assinatura?',
    mensagem: mensagemCancelamento(d),
    confirmar: 'Cancelar assinatura',
    cancelar: 'Manter assinatura',
    perigo: true,
  })
  if (!ok) return
  cancelando.value = true
  try {
    const r = await assinaturaApi.cancelar()
    pararEspera()
    aplicar(r)
    atualizarSessao()
    avisar.sucesso(r.conta.pago_ate && r.conta.liberada ? `Assinatura cancelada. Você usa até ${formatarData(r.conta.pago_ate)}.` : 'Assinatura cancelada.')
    await nextTick()
    document.getElementById('t-situacao')?.focus()
  } catch (e) {
    avisar.erro(mensagemDoErro(e))
  } finally {
    cancelando.value = false
  }
}

onMounted(() => {
  carregar()
  document.addEventListener('visibilitychange', aoVoltarParaAba)
})
onBeforeUnmount(() => {
  pararEspera()
  document.removeEventListener('visibilitychange', aoVoltarParaAba)
})

</script>

<template>
  <CabecalhoPagina
    titulo="Assinatura"
    descricao="Seu plano, as faturas e os dados de cobrança. A cobrança é feita pelo Asaas, por Pix, boleto ou cartão."
  />

  <Carregando v-if="carregando" :linhas="4" rotulo="Carregando a assinatura" />
  <Alerta v-else-if="erroCarga" tom="erro">
    {{ erroCarga }} <button type="button" class="link ml-1" @click="carregar">Tentar de novo</button>
  </Alerta>

  <div v-else-if="dados && situacao" class="flex flex-col gap-6">
    <Alerta v-if="!dados.disponivel" tom="info" data-indisponivel>A cobrança online ainda não está disponível. Fale com a equipe Toqqi.</Alerta>

    <!-- Situação (sem assinatura) ou o plano assinado -->
    <section class="cartao flex flex-col gap-5 p-5 sm:p-6" aria-labelledby="t-situacao" data-situacao-conta>
      <div class="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div class="min-w-0">
          <div class="flex flex-wrap items-center gap-x-3 gap-y-2">
            <h2 id="t-situacao" tabindex="-1" class="text-lg font-bold text-texto focus:outline-none">{{ titulo }}</h2>
            <Etiqueta :tom="situacao.tom" ponto data-selo-situacao>{{ situacao.rotulo }}</Etiqueta>
          </div>
          <p v-if="situacao.descricao" class="mt-1.5 text-sm text-texto-suave">{{ situacao.descricao }}</p>
        </div>
        <p v-if="assinatura" class="shrink-0 sm:text-right">
          <span class="block text-2xl font-bold tabular-nums text-texto">{{ formatarMoeda(assinatura.valor) }}</span>{{ ' ' }}<span class="text-sm text-texto-suave">{{ cicloAtual === 'anual' ? 'por ano' : 'por mês' }}</span>
          <span v-if="assinatura.forma === 'pix' || cicloAtual === 'anual'" class="block text-xs text-texto-fraco" data-condicao>{{ cicloAtual === 'anual' ? 'Assinatura anual' : 'Mensal com Pix' }}</span>
        </p>
      </div>

      <dl class="grid grid-cols-2 gap-3 lg:grid-cols-3">
        <div class="col-span-2 flex flex-col gap-2 rounded-xl bg-superficie-2 p-4 lg:col-span-1">
          <dt class="text-sm text-texto-fraco">Contatos ativos</dt>
          <dd class="flex flex-col gap-2">
            <p class="text-sm text-texto-suave" data-uso>
              <strong class="text-lg font-bold tabular-nums text-texto">{{ formatarNumero(dados.contatos_ativos) }}</strong>
              <template v-if="limite !== null"> de {{ formatarNumero(limite) }}</template>
              <template v-else> (sem limite)</template>
            </p>
            <Medidor
              v-if="limite !== null"
              :valor="dados.contatos_ativos"
              :maximo="limite"
              rotulo="Contatos ativos do plano"
              :texto="`${formatarNumero(dados.contatos_ativos)} de ${formatarNumero(limite)} contatos ativos`"
            />
            <p v-if="limite !== null && planoAtual && !assinatura" class="text-xs text-texto-fraco">Limite do plano {{ planoAtual.nome }}{{ emTeste ? ', o do teste' : '' }}.</p>
          </dd>
        </div>
        <div v-if="proximo" class="flex flex-col gap-1 rounded-xl bg-superficie-2 p-4">
          <dt class="text-sm text-texto-fraco">Próximo vencimento</dt>
          <dd class="text-lg font-bold tabular-nums text-texto" data-proximo-vencimento>{{ formatarData(proximo) }}</dd>
        </div>
        <div v-if="assinatura" class="flex flex-col gap-1 rounded-xl bg-superficie-2 p-4">
          <dt class="text-sm text-texto-fraco">Assinada em</dt>
          <dd class="text-lg font-bold tabular-nums text-texto">{{ formatarData(assinatura.criada_em) }}</dd>
        </div>
      </dl>

      <p v-if="assinatura && !fatura && !dados.cobrancas.length" class="text-sm text-texto-suave" aria-live="polite">
        A primeira fatura (vencimento em {{ formatarData(assinatura.primeiro_vencimento) }}) aparece aqui assim que o Asaas gerar{{
          esperando ? ': a tela se atualiza sozinha.' : '.'
        }}
        <button v-if="!esperando" type="button" class="link ml-1" :disabled="atualizando" @click="atualizarAgora">Atualizar</button>
      </p>

      <div v-if="assinatura" class="flex flex-col gap-2 border-t border-borda pt-4 sm:flex-row sm:flex-wrap">
        <Botao variante="secundario" :desabilitado="!dados.disponivel" @click="trocarPara(null)">
          <ArrowRightLeft class="size-4" aria-hidden="true" /> Trocar de plano
        </Botao>
        <Botao variante="perigo-suave" :carregando="cancelando" :desabilitado="!dados.disponivel" @click="cancelar">
          <XCircle v-if="!cancelando" class="size-4" aria-hidden="true" /> Cancelar assinatura
        </Botao>
      </div>
    </section>

    <!-- A fatura para pagar agora; com a conta ativa e o vencimento daqui a mais de 5 dias, a "Próxima fatura" -->
    <section v-if="assinatura && fatura" class="cartao flex flex-col gap-4 p-5 sm:p-6" aria-labelledby="t-fatura" data-fatura-aberta :data-modo="futura ? 'proxima' : 'pagar'">
      <div class="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div class="min-w-0">
          <div class="flex flex-wrap items-center gap-x-3 gap-y-2">
            <h2 id="t-fatura" tabindex="-1" class="text-base font-bold text-texto focus:outline-none">{{ futura ? 'Próxima fatura' : 'Fatura em aberto' }}</h2>
            <Etiqueta v-if="!futura" :tom="situacaoCobranca(fatura.situacao).tom" ponto>{{ situacaoCobranca(fatura.situacao).rotulo }}</Etiqueta>
          </div>
          <p class="mt-1.5 text-sm text-texto-suave">
            <strong class="font-semibold text-texto">{{ formatarMoeda(fatura.valor) }}</strong>,
            {{ fatura.situacao === 'vencida' ? 'venceu em' : 'vence em' }} {{ formatarData(fatura.vencimento) }}
            e cobre de <span class="whitespace-nowrap" data-periodo>{{ textoPeriodo(fatura.vencimento, false, cicloAtual) }}</span>.
            {{ futura ? `Se quiser, pague antes. ${textoForma(assinatura.forma)}` : textoForma(assinatura.forma) }}
          </p>
          <p v-if="outrasAbertas.length" class="mt-1 text-sm text-texto-suave" data-outras-abertas>
            Também em aberto: {{ outrasAbertas.length === 1 ? 'a fatura' : `${outrasAbertas.length} faturas` }} com vencimento em
            {{ listaDeDatas(outrasAbertas.map((f) => f.vencimento).sort()) }}.
          </p>
        </div>
        <template v-if="fatura.link">
          <Botao v-if="futura" :href="fatura.link" variante="secundario" class="w-full shrink-0 sm:w-auto" data-ver-fatura @click="esperarPagamento(fatura)">
            <ExternalLink class="size-4" aria-hidden="true" /> Ver fatura
          </Botao>
          <Botao v-else :href="fatura.link" tamanho="lg" class="w-full shrink-0 sm:w-auto" data-pagar @click="esperarPagamento(fatura)">
            <CreditCard class="size-5" aria-hidden="true" /> Pagar
          </Botao>
        </template>
      </div>
      <p v-if="!fatura.link" class="text-sm text-texto-suave">O Asaas ainda está preparando a fatura. Atualize em instantes.</p>
      <div class="flex flex-col gap-2 border-t border-borda pt-3 text-sm sm:flex-row sm:items-center sm:justify-between">
        <p class="text-texto-suave" aria-live="polite" data-espera>
          {{
            esperando
              ? 'Esperando a confirmação do pagamento: a tela se atualiza sozinha.'
              : futura
                ? 'Pagou antes do vencimento? A confirmação chega sozinha.'
                : `Pagou? A confirmação chega sozinha: ${TEMPO_CONFIRMACAO}.`
          }}
        </p>
        <Botao variante="fantasma" tamanho="sm" class="self-start sm:self-auto" :carregando="atualizando" @click="atualizarAgora">
          <RefreshCw v-if="!atualizando" class="size-4" aria-hidden="true" /> Atualizar
        </Botao>
      </div>
    </section>

    <!-- Com assinatura: todos os planos, com o atual marcado (etapa 5k) -->
    <section v-if="assinatura" class="flex flex-col gap-4" aria-labelledby="t-comparar" data-planos-assinada>
      <div>
        <h2 id="t-comparar" class="text-lg font-bold text-texto">Planos</h2>
        <p class="mt-1 text-sm text-texto-suave">
          {{
            cicloAtual === 'anual'
              ? 'Valores no anual, como a sua assinatura. Na assinatura anual, a troca de plano é feita pela equipe Toqqi.'
              : assinatura.forma === 'pix'
                ? 'Valores no mensal com Pix, como a sua assinatura. Trocar vale para as próximas faturas e as pendentes.'
                : 'Valores no mensal, como a sua assinatura. Trocar vale para as próximas faturas e as pendentes.'
          }}
        </p>
      </div>
      <ComparativoPlanos
        v-model:contatos="contatosPers"
        v-model:cota-ia="cotaPers"
        :planos="planosDaAssinatura"
        :tabela="tabela"
        :personalizado="persDaAssinatura"
        :atual="assinatura.plano"
        personalizado-contratado
        :pode-trocar="dados.disponivel && cicloAtual === 'mensal'"
        @trocar="trocarPara"
      />
    </section>

    <!-- Sem assinatura: planos e formulário de cobrança -->
    <template v-if="!assinatura && !cortesia">
      <section class="flex flex-col gap-4" aria-labelledby="t-planos">
        <div>
          <h2 id="t-planos" class="text-lg font-bold text-texto">Escolha um plano</h2>
          <p class="mt-1 text-sm text-texto-suave">Sem fidelidade: cancele quando quiser, sem multa. WhatsApp automático sem franquia em todos.</p>
        </div>
        <div class="flex flex-col gap-3 sm:flex-row sm:flex-wrap sm:items-center sm:gap-4" data-pagamento>
          <BotoesSegmentados v-model="ciclo" :opcoes="OPCOES_CICLO" rotulo="Ciclo da cobrança" bloco :desabilitado="!dados.disponivel || enviando" />
          <BotoesSegmentados v-if="ciclo === 'mensal'" v-model="forma" :opcoes="OPCOES_FORMA" rotulo="Forma de pagamento" bloco :desabilitado="!dados.disponivel || enviando" />
          <p class="text-sm text-texto-suave" aria-live="polite" data-texto-pagamento>
            {{
              ciclo === 'anual'
                ? `Um pagamento por ano, por Pix, boleto ou cartão${descontos.anual ? `, com ${descontos.anual}% de desconto` : ''}.`
                : forma === 'pix'
                  ? `Todo mês por Pix${descontos.pix ? `, com ${descontos.pix}% de desconto` : ''}.`
                  : 'Todo mês, por cartão ou boleto (a fatura também aceita Pix, sem o desconto).'
            }}
          </p>
        </div>
        <EscolhaPlano
          v-model="planoEscolhido"
          v-model:contatos="contatosPers"
          v-model:cota-ia="cotaPers"
          :planos="planosExibidos"
          :personalizado="persExibido"
          :tabela="tabela"
          :contatos-ativos="dados.contatos_ativos"
          rotulo="Planos"
          :atual="emTeste ? dados.conta.plano : null"
          rotulo-atual="Plano do seu teste"
          :desabilitado="!dados.disponivel || enviando"
          @escolheu="aoEscolherPlano"
        />
        <details class="group" data-comparar-planos>
          <summary class="link w-fit cursor-pointer text-sm font-semibold">Comparar os planos em detalhe</summary>
          <div class="mt-4">
            <ComparativoPlanos v-model:contatos="contatosPers" v-model:cota-ia="cotaPers" :planos="planosExibidos" :tabela="tabela" :personalizado="persExibido" :atual="emTeste ? dados.conta.plano : null" rotulo-atual="Plano do seu teste" />
          </div>
        </details>
      </section>

      <section v-if="plano && resumo" ref="secaoForm" class="cartao p-5 sm:p-6" aria-labelledby="t-cobranca" data-form-assinar>
        <form ref="formAssinar" class="flex flex-col gap-5" novalidate @submit.prevent="assinar">
          <div>
            <h2 id="t-cobranca" class="text-lg font-bold text-texto">Dados de cobrança</h2>
            <p class="mt-1 text-sm text-texto-suave">Vieram dos dados da empresa. Confira antes de assinar: as faturas saem com eles.</p>
          </div>
          <Alerta
            v-if="erroGeral"
            :tom="erroPreco || codigoErro === 'limite_do_plano' || codigoErro === 'preco_mudou' ? 'atencao' : 'erro'"
            data-erro-assinar
          >
            {{ erroPreco ?? erroGeral }}
            <button v-if="erroPreco" type="button" class="link ml-1" data-recarregar @click="recarregarPagina">Recarregar</button>
            <RouterLink v-if="codigoErro === 'limite_do_plano' && sessao.pode('contatos.ver')" to="/contatos" class="link ml-1">Ver contatos</RouterLink>
          </Alerta>
          <CamposCobranca v-model="form" :erros="errosForm" :desabilitado="enviando" />
          <div class="flex flex-col gap-1 rounded-xl bg-superficie-2 p-4 text-sm" data-resumo>
            <p class="font-semibold text-texto" aria-live="polite">{{ resumo.texto }}</p>
            <p v-if="resumo.envios" class="text-texto-suave">{{ resumo.envios }}</p>
            <p class="text-texto-suave">{{ textoForma(plano.forma) }}</p>
          </div>
          <div class="flex sm:justify-end">
            <Botao tipo="submit" tamanho="lg" class="w-full sm:w-auto" :carregando="enviando" :desabilitado="!dados.disponivel || !plano_cabe">
              Assinar {{ plano.chave === 'personalizado' ? 'o Personalizado' : `o plano ${plano.nome}` }}<span class="hidden sm:inline">&nbsp;· {{ textoPorPeriodo(plano.preco, plano.ciclo) }}</span>
            </Botao>
          </div>
        </form>
      </section>
    </template>

    <!-- Dados de cobrança da assinatura -->
    <section v-if="assinatura" class="cartao grid grid-cols-1 gap-6 p-5 sm:p-6 md:grid-cols-3" aria-labelledby="t-dados" data-dados-cobranca>
      <div>
        <div class="mb-3 flex size-10 items-center justify-center rounded-xl bg-marca-suave text-marca-texto"><FileText class="size-5" aria-hidden="true" /></div>
        <h2 id="t-dados" class="text-base font-bold text-texto">Dados de cobrança</h2>
        <p class="mt-1 text-sm text-texto-suave">As faturas saem com estes dados.</p>
      </div>
      <div class="flex min-w-0 flex-col gap-4 md:col-span-2">
        <dl class="grid grid-cols-1 gap-x-6 gap-y-3 text-sm sm:grid-cols-2">
          <div class="min-w-0 sm:col-span-2">
            <dt class="text-texto-fraco">Razão social</dt>
            <dd class="break-words font-semibold text-texto">{{ assinatura.dados.razao_social }}</dd>
          </div>
          <div class="min-w-0">
            <dt class="text-texto-fraco">CPF ou CNPJ</dt>
            <dd class="font-semibold tabular-nums text-texto">{{ formatarDocumento(assinatura.dados.documento) }}</dd>
          </div>
          <div class="min-w-0">
            <dt class="text-texto-fraco">Telefone</dt>
            <dd class="font-semibold tabular-nums text-texto">{{ exibirTelefone(assinatura.dados.telefone) }}</dd>
          </div>
          <div class="min-w-0 sm:col-span-2">
            <dt class="text-texto-fraco">E-mail de cobrança</dt>
            <dd class="break-all font-semibold text-texto">{{ assinatura.dados.email_cobranca }}</dd>
          </div>
        </dl>
        <Botao variante="secundario" class="self-start" :desabilitado="!dados.disponivel" @click="dadosAberto = true">
          <Pencil class="size-4" aria-hidden="true" /> Editar dados de cobrança
        </Botao>
      </div>
    </section>

    <!-- Histórico de cobranças -->
    <section v-if="assinatura || dados.cobrancas.length" class="cartao overflow-hidden" aria-labelledby="t-historico" data-historico>
      <div class="border-b border-borda px-5 py-4 sm:px-6">
        <h2 id="t-historico" class="text-base font-bold text-texto">Histórico de cobranças</h2>
        <p class="mt-0.5 text-sm text-texto-suave">As 12 mais recentes. "Ver fatura" abre a página da fatura no Asaas.</p>
      </div>
      <HistoricoCobrancas :cobrancas="dados.cobrancas" :ciclo="cicloAtual" />
    </section>
  </div>

  <ModalTrocarPlano v-if="dados?.assinatura" v-model:aberto="trocarAberto" :estado="dados" :inicial="trocaInicial" :contatos-iniciais="contatosPers" :cota-inicial="cotaPers" @trocado="aoMudarAssinatura" @recarregar="atualizar" />
  <ModalDadosCobranca v-if="dados?.assinatura" v-model:aberto="dadosAberto" :dados="dados.assinatura.dados" :disponivel="dados.disponivel" @salvo="aplicar" />
</template>

// Regras puras da assinatura (etapa 5a, sem Vue): o aviso do topo das telas, a situação da conta na tela de
// Assinatura, a primeira fatura, os planos e o limite de contatos, as cobranças e o formulário de cobrança (as mesmas
// máscaras e mensagens de Configurações › Empresa). Datas de calendário em AAAA-MM-DD, no dia de São Paulo.
import type {
  AvisoCobranca,
  CobrancaAssinatura,
  CobrancaConta,
  Conta,
  DadosCobranca,
  EstadoAssinatura,
  FaturaAberta,
  PlanoAssinatura,
} from '@/api/tipos'
import { FUSO, formatarData, formatarDiaMes } from '@/utils/datas'
import { formatarDocumento, formatarMoeda, formatarNumero } from '@/utils/formatos'
import { somarDias } from '@/utils/periodo'
import type { Tom } from '@/utils/rotulos'
import { apenasDigitos, emailValido, normalizarDocumento } from '@/utils/validacao'
import { MENSAGENS, documentoValido, erroTelefone, telefoneDoCampo } from '@/modulos/configuracoes/empresa'

// ── Datas ───────────────────────────────────────────────────────────────────

const fmtDiaIso = new Intl.DateTimeFormat('en-CA', { timeZone: FUSO, year: 'numeric', month: '2-digit', day: '2-digit' })
const DATA_PURA = /^\d{4}-\d{2}-\d{2}$/

/** Dia (AAAA-MM-DD) de um momento em São Paulo. */
export function diaEmSaoPaulo(momento: Date | number): string {
  return fmtDiaIso.format(momento)
}

/**
 * Último dia do teste (São Paulo), como a API: um fim exatamente à meia-noite fica no dia anterior.
 * `teste_ate` vem com data e hora; uma data pura já é o último dia.
 */
export function ultimoDiaDoTeste(testeAte: string | null | undefined): string | null {
  if (!testeAte) return null
  if (DATA_PURA.test(testeAte)) return testeAte
  const t = Date.parse(testeAte)
  return Number.isNaN(t) ? null : diaEmSaoPaulo(t - 1)
}

/** O teste ainda vale (o fim é depois de agora). */
export function testeValendo(testeAte: string | null | undefined, agora: Date = new Date()): boolean {
  if (!testeAte) return false
  const fim = DATA_PURA.test(testeAte) ? Date.parse(`${somarDias(testeAte, 1)}T00:00:00-03:00`) : Date.parse(testeAte)
  return !Number.isNaN(fim) && agora.getTime() < fim
}

export type MotivoVencimento = 'teste' | 'pago' | 'amanha'

/**
 * Vencimento da primeira fatura de uma assinatura nova (seção 0 do contrato): o último dia do teste, se ele ainda
 * vale; o dia seguinte ao `pago_ate`, se ainda no futuro; com os dois, o mais tarde; senão, amanhã.
 */
export function primeiroVencimento(
  conta: { teste_ate: string | null; pago_ate: string | null },
  agora: Date = new Date(),
): { data: string; motivo: MotivoVencimento } {
  const hoje = diaEmSaoPaulo(agora)
  const candidatos: { data: string; motivo: MotivoVencimento }[] = []
  const ultimo = ultimoDiaDoTeste(conta.teste_ate)
  if (ultimo && testeValendo(conta.teste_ate, agora)) candidatos.push({ data: ultimo, motivo: 'teste' })
  if (conta.pago_ate && conta.pago_ate >= hoje) candidatos.push({ data: somarDias(conta.pago_ate, 1), motivo: 'pago' })
  if (!candidatos.length) return { data: somarDias(hoje, 1), motivo: 'amanha' }
  return candidatos.reduce((a, b) => (b.data > a.data ? b : a))
}

/** Mesmo dia no mês seguinte (31/01 → 28/02 ou 29/02), como `mais_um_mes` na API. */
function maisUmMes(iso: string): string {
  const a = Number(iso.slice(0, 4))
  const m = Number(iso.slice(5, 7))
  const d = Number(iso.slice(8, 10))
  const ano = m === 12 ? a + 1 : a
  const mes = m === 12 ? 1 : m + 1
  const ultimo = new Date(Date.UTC(ano, mes, 0)).getUTCDate() // último dia do mês `mes` (1 a 12)
  return `${ano}-${String(mes).padStart(2, '0')}-${String(Math.min(d, ultimo)).padStart(2, '0')}`
}

/** Último dia coberto por uma fatura: vencimento + 1 mês − 1 dia (a regra do `pago_ate` na API). */
export function fimDoPeriodo(vencimento: string): string {
  return somarDias(maisUmMes(vencimento), -1)
}

/**
 * Período coberto por uma fatura: "16/10 a 15/11/2026" (mesmo ano) ou "16/12/2026 a 15/01/2027". `curto` (no
 * histórico, logo abaixo do vencimento, que já mostra o ano): "16/10 a 15/11", "16/12 a 15/01".
 */
export function textoPeriodo(vencimento: string, curto = false): string {
  const fim = fimDoPeriodo(vencimento)
  if (curto) return `${formatarDiaMes(vencimento)} a ${formatarDiaMes(fim)}`
  const inicio = vencimento.slice(0, 4) === fim.slice(0, 4) ? formatarDiaMes(vencimento) : formatarData(vencimento)
  return `${inicio} a ${formatarData(fim)}`
}

/** "Depois, todo dia 15." (dias 29 a 31 não existem em todo mês: aí a fatura vem no último dia.) */
export function textoDepois(vencimento: string): string {
  const dia = Number(vencimento.slice(8, 10))
  return dia >= 29 ? `Depois, todo dia ${dia} (ou no último dia do mês, nos meses mais curtos).` : `Depois, todo dia ${dia}.`
}

export const TEMPO_CONFIRMACAO = 'Pix e cartão em segundos, boleto em até 3 dias úteis'

/** Depois de assinar (ou de "Pagar"), a tela busca de novo a cada 10 s, por até 2 min, enquanto a fatura está em aberto. */
export const INTERVALO_ESPERA_MS = 10_000
export const LIMITE_ESPERA_MS = 120_000

/** Resumo da primeira fatura no formulário de assinar ("Primeira fatura de R$ 349,00 com vencimento em…", o período
 * que ela cobre e o dia das próximas). */
export function resumoPrimeiraFatura(
  plano: Pick<PlanoAssinatura, 'preco'>,
  conta: { teste_ate: string | null; pago_ate: string | null },
  agora: Date = new Date(),
): { texto: string; envios: string | null; vencimento: string } {
  const { data, motivo } = primeiroVencimento(conta, agora)
  const valor = formatarMoeda(plano.preco)
  const hoje = diaEmSaoPaulo(agora)
  const quando =
    motivo === 'amanha'
      ? `amanhã, ${formatarData(data)}`
      : data === hoje
        ? `hoje, ${formatarData(data)}`
        : `em ${formatarData(data)}`
  const porque = motivo === 'teste' ? ', no fim do teste' : motivo === 'pago' ? ', no dia seguinte ao fim do período já pago' : ''
  return {
    texto: `Primeira fatura de ${valor} com vencimento ${quando}${porque}. Ela cobre de ${textoPeriodo(data)}. ${textoDepois(data)}`,
    // Sem teste nem período pago, os envios estão parados até o pagamento.
    envios: motivo === 'amanha' ? `Os envios voltam assim que o pagamento for confirmado: ${TEMPO_CONFIRMACAO}.` : null,
    vencimento: data,
  }
}

// ── Aviso do topo das telas (conta.cobranca.aviso) ──────────────────────────

export type AcaoAviso = 'escolher' | 'pagar' | 'ver'

export interface TextoAviso {
  texto: string
  tom: 'info' | 'atencao' | 'erro'
  acao: AcaoAviso
  /** Só os informativos podem ser fechados (voltam na próxima sessão do navegador). */
  dispensavel: boolean
}

export const ROTULOS_ACAO_AVISO: Record<AcaoAviso, string> = {
  escolher: 'Escolher plano',
  pagar: 'Pagar agora',
  ver: 'Ver assinatura',
}

export const FALE_COM_ADMIN = 'Fale com o administrador da conta.'

/** Texto, cor e botão do aviso. `cobranca` completa o atraso (o vencimento da fatura) e diz se os envios seguem. */
export function textoDoAviso(
  aviso: AvisoCobranca | null | undefined,
  cobranca?: Partial<Pick<CobrancaConta, 'atrasada_desde' | 'liberada'>> | null,
): TextoAviso | null {
  if (!aviso) return null
  const dia = (d: string | null | undefined) => (d ? formatarDiaMes(d) : null)
  switch (aviso.tipo) {
    case 'teste_acabando': {
      const d = aviso.dias
      const quando =
        d === 0 ? 'hoje' : d === 1 ? 'amanhã' : typeof d === 'number' && d > 1 ? `em ${d} dias` : dia(aviso.data) ? `em ${dia(aviso.data)}` : 'em breve'
      return { texto: `Seu teste grátis termina ${quando}.`, tom: typeof d === 'number' && d <= 1 ? 'atencao' : 'info', acao: 'escolher', dispensavel: true }
    }
    case 'teste_expirado':
      return { texto: 'Seu teste grátis terminou. Os envios estão pausados; seus dados continuam guardados.', tom: 'atencao', acao: 'escolher', dispensavel: false }
    case 'atrasada': {
      const venceu = dia(cobranca?.atrasada_desde)
      const param = dia(aviso.data)
      const inicio = venceu ? `A fatura venceu em ${venceu}.` : 'A fatura da assinatura está vencida.'
      const fim = param ? (aviso.dias === 1 ? `amanhã, ${param},` : `em ${param}`) : 'em breve'
      return { texto: `${inicio} Os envios param ${fim} se ela não for paga.`, tom: 'atencao', acao: 'pagar', dispensavel: false }
    }
    case 'pausada':
      return { texto: 'Envios pausados por falta de pagamento. Seus dados continuam guardados.', tom: 'erro', acao: 'pagar', dispensavel: false }
    case 'cancelada': {
      const ate = aviso.dias === 0 ? 'hoje' : dia(aviso.data)
      return { texto: ate ? `Assinatura cancelada. Você usa até ${ate}.` : 'Assinatura cancelada.', tom: 'info', acao: 'escolher', dispensavel: true }
    }
    case 'aguardando_pagamento': {
      // Já assinou e a primeira fatura está em aberto. No teste (envios seguem): só o lembrete do vencimento; sem teste
      // válido (envios pausados até pagar): o que falta para voltar.
      if (cobranca?.liberada === false) {
        return {
          texto: 'Aguardando o pagamento da primeira fatura. Os envios voltam assim que ele for confirmado.',
          tom: 'atencao',
          acao: 'pagar',
          dispensavel: false,
        }
      }
      const d = aviso.dias
      const quando =
        d === 0 ? 'hoje' : d === 1 ? 'amanhã' : dia(aviso.data) ? `em ${dia(aviso.data)}` : typeof d === 'number' && d > 1 ? `em ${d} dias` : 'em breve'
      return { texto: `A primeira fatura da assinatura vence ${quando}.`, tom: typeof d === 'number' && d <= 1 ? 'atencao' : 'info', acao: 'pagar', dispensavel: true }
    }
    case 'cancelada_encerrada':
      return {
        texto: 'Assinatura cancelada e o período pago terminou. Os envios estão pausados; seus dados continuam guardados.',
        tom: 'atencao',
        acao: 'escolher',
        dispensavel: false,
      }
    default:
      // Tipo novo da API: avisa sem inventar o texto.
      return { texto: 'Há um aviso sobre a assinatura da conta.', tom: 'info', acao: 'ver', dispensavel: true }
  }
}

/** Chave para lembrar que a pessoa fechou este aviso (o mesmo aviso com outra data volta a aparecer). */
export function chaveDoAviso(aviso: AvisoCobranca): string {
  return `${aviso.tipo}:${aviso.data ?? ''}:${aviso.dias ?? ''}`
}

// ── Situação da conta na tela de Assinatura ─────────────────────────────────

export interface SituacaoNaTela {
  rotulo: string
  tom: Tom
  titulo: string
  descricao: string
}

/** Selo, título e explicação da situação, com ou sem assinatura. */
export function situacaoNaTela(e: Pick<EstadoAssinatura, 'conta' | 'assinatura'>, agora: Date = new Date()): SituacaoNaTela {
  const c = e.conta
  const ultimo = ultimoDiaDoTeste(c.teste_ate)
  const hoje = diaEmSaoPaulo(agora)
  if (c.situacao === 'cortesia') {
    return { rotulo: 'Cortesia', tom: 'marca', titulo: 'Conta cortesia', descricao: 'Sua conta usa o Toqqi sem cobrança: não precisa assinar.' }
  }
  if (e.assinatura) {
    const a = e.assinatura
    if (c.situacao === 'ativa') {
      return { rotulo: 'Ativa', tom: 'sucesso', titulo: 'Assinatura ativa', descricao: c.pago_ate ? `Pago até ${formatarData(c.pago_ate)}.` : 'Pagamento em dia.' }
    }
    if (c.situacao === 'atrasada') {
      const venceu = c.atrasada_desde ? ` em ${formatarData(c.atrasada_desde)}` : ''
      return c.liberada
        ? {
            rotulo: 'Atrasada',
            tom: 'erro',
            titulo: 'Pagamento atrasado',
            descricao: `A fatura venceu${venceu}. ${c.pausa_em ? `Os envios param em ${formatarData(c.pausa_em)}` : 'Os envios param em breve'} se ela não for paga.`,
          }
        : { rotulo: 'Atrasada', tom: 'erro', titulo: 'Envios pausados', descricao: `A fatura venceu${venceu} e os envios estão pausados por falta de pagamento.` }
    }
    if (c.situacao === 'teste') {
      return {
        rotulo: 'Em teste',
        tom: 'info',
        titulo: 'Assinada durante o teste',
        descricao: `${ultimo ? `O teste vai até ${formatarData(ultimo)}. ` : ''}A primeira fatura vence em ${formatarData(a.primeiro_vencimento)}.`,
      }
    }
    // Assinou sem teste valendo e sem período pago (teste_expirado ou cancelada): espera a primeira fatura.
    return {
      rotulo: 'Aguardando pagamento',
      tom: 'atencao',
      titulo: 'Aguardando o pagamento',
      descricao: `Os envios voltam assim que a primeira fatura for paga: ${TEMPO_CONFIRMACAO}.`,
    }
  }
  // Teste que já acabou e a API ainda não marcou (a tarefa passa de hora em hora): mostra como encerrado.
  const testeAcabou = c.situacao === 'teste_expirado' || (c.situacao === 'teste' && !!c.teste_ate && !testeValendo(c.teste_ate, agora))
  if (c.situacao === 'teste' && !testeAcabou) {
    const dias = ultimo ? Math.round((Date.parse(`${ultimo}T12:00:00Z`) - Date.parse(`${hoje}T12:00:00Z`)) / 86_400_000) : null
    const falta = dias === null ? '' : dias <= 0 ? ' Termina hoje.' : dias === 1 ? ' Falta 1 dia.' : ` Faltam ${dias} dias.`
    return {
      rotulo: 'Em teste',
      tom: 'info',
      titulo: ultimo ? `Teste grátis até ${formatarData(ultimo)}` : 'Teste grátis',
      descricao: `Assine quando quiser: a primeira fatura vence no último dia do teste.${falta}`,
    }
  }
  if (testeAcabou) {
    return {
      rotulo: 'Teste encerrado',
      tom: 'atencao',
      titulo: ultimo ? `Seu teste grátis terminou em ${formatarData(ultimo)}` : 'Seu teste grátis terminou',
      descricao: 'Os envios estão pausados; seus dados continuam guardados. Escolha um plano para voltar a enviar.',
    }
  }
  if (c.situacao === 'cancelada') {
    return c.liberada && c.pago_ate
      ? { rotulo: 'Cancelada', tom: 'neutro', titulo: 'Assinatura cancelada', descricao: `Você usa até ${formatarData(c.pago_ate)}. Para continuar depois disso, escolha um plano.` }
      : { rotulo: 'Cancelada', tom: 'neutro', titulo: 'Assinatura cancelada', descricao: 'O período pago terminou e os envios estão pausados; seus dados continuam guardados.' }
  }
  return { rotulo: c.situacao, tom: 'neutro', titulo: 'Assinatura', descricao: '' }
}

// ── Planos e limite de contatos ─────────────────────────────────────────────

export const RECURSOS_PLANOS = 'Envios, formulários e usuários ilimitados'

/** Nomes dos planos para telas que não buscam a lista (Plataforma). */
export const NOMES_PLANOS: Record<string, string> = { essencial: 'Essencial', profissional: 'Profissional', empresa: 'Empresa' }

export function nomeDoPlano(chave: string | null | undefined): string {
  if (!chave) return '—'
  return NOMES_PLANOS[chave] ?? chave.charAt(0).toUpperCase() + chave.slice(1)
}

export function rotuloLimite(contatos: number | null | undefined): string {
  return contatos === null || contatos === undefined ? 'Contatos ativos sem limite' : `Até ${formatarNumero(contatos)} contatos ativos`
}

/**
 * Etapa 5g: quem já assina paga o valor contratado, mesmo depois de o preço do plano mudar. No cartão do plano atual (ao
 * trocar de plano): "Você paga R$ 349,00; hoje o plano custa R$ 399,00." (null quando os dois são iguais).
 */
export function textoContratado(contratado: PlanoAssinatura['preco'] | null | undefined, precoAtual: PlanoAssinatura['preco']): string | null {
  if (contratado === null || contratado === undefined || contratado === '') return null
  const a = Math.round(Number(contratado) * 100)
  const b = Math.round(Number(precoAtual) * 100)
  if (!Number.isFinite(a) || !Number.isFinite(b) || a === b) return null
  return `Você paga ${formatarMoeda(contratado)}; hoje o plano custa ${formatarMoeda(precoAtual)}.`
}

/** O plano comporta os contatos ativos de hoje. */
export function cabeNoPlano(plano: Pick<PlanoAssinatura, 'contatos'>, contatosAtivos: number): boolean {
  return plano.contatos === null || contatosAtivos <= plano.contatos
}

/** O mesmo texto do 422 `limite_do_plano` da API. */
export function mensagemLimite(plano: Pick<PlanoAssinatura, 'nome' | 'contatos'>, contatosAtivos: number, acao: 'assinar' | 'trocar'): string {
  return `Você tem ${formatarNumero(contatosAtivos)} contatos ativos; o plano ${plano.nome} permite até ${formatarNumero(plano.contatos ?? 0)}. Desative contatos antes de ${acao}.`
}

export function planoPorChave<P extends Pick<PlanoAssinatura, 'chave'>>(planos: readonly P[], chave: string | null | undefined): P | null {
  return planos.find((p) => p.chave === chave) ?? null
}

/** Lista "15/10/2026", "15/10/2026 e 15/11/2026", "15/09/2026, 15/10/2026 e 15/11/2026". */
export function listaDeDatas(datas: string[]): string {
  const f = datas.map((d) => formatarData(d))
  return f.length <= 1 ? (f[0] ?? '') : `${f.slice(0, -1).join(', ')} e ${f[f.length - 1]}`
}

/**
 * Efeito de trocar de plano: o valor (as faturas pendentes mudam junto; as vencidas, não — como a API faz com
 * `updatePendingPayments`) e o limite de contatos.
 */
export function efeitoTroca(
  e: Pick<EstadoAssinatura, 'assinatura' | 'fatura_aberta' | 'contatos_ativos'> & Partial<Pick<EstadoAssinatura, 'cobrancas'>>,
  novo: PlanoAssinatura,
): { valor: string; fatura: string | null; vencidas: string | null; limite: string; cabe: boolean; aviso: string | null } {
  const de = e.assinatura ? formatarMoeda(e.assinatura.valor) : null
  const para = formatarMoeda(novo.preco)
  const abertas = faturasEmAberto(e)
  const pendentes = abertas.filter((f) => f.situacao === 'pendente').map((f) => f.vencimento).sort()
  const vencidas = abertas.filter((f) => f.situacao === 'vencida')
  const cabe = cabeNoPlano(novo, e.contatos_ativos)
  return {
    valor: de ? `O valor passa de ${de} para ${para} por mês.` : `O valor passa a ser ${para} por mês.`,
    fatura: !pendentes.length
      ? null
      : pendentes.length === 1
        ? `A fatura pendente, que vence em ${formatarData(pendentes[0])}, também passa para ${para}.`
        : `As ${pendentes.length} faturas pendentes (vencimentos em ${listaDeDatas(pendentes)}) também passam para ${para}.`,
    vencidas: !vencidas.length
      ? null
      : vencidas.length === 1
        ? `A fatura vencida em ${formatarData(vencidas[0]!.vencimento)} continua com o valor de antes.`
        : `As ${vencidas.length} faturas vencidas continuam com o valor de antes.`,
    limite:
      novo.contatos === null
        ? `Os contatos ativos ficam sem limite (hoje você tem ${formatarNumero(e.contatos_ativos)}).`
        : `O limite passa a ser de ${formatarNumero(novo.contatos)} contatos ativos (hoje você tem ${formatarNumero(e.contatos_ativos)}).`,
    cabe,
    aviso: cabe ? null : mensagemLimite(novo, e.contatos_ativos, 'trocar'),
  }
}

// ── Faturas e cobranças ─────────────────────────────────────────────────────

export const SITUACOES_COBRANCA: Record<string, { rotulo: string; tom: Tom }> = {
  pendente: { rotulo: 'Em aberto', tom: 'info' },
  paga: { rotulo: 'Paga', tom: 'sucesso' },
  vencida: { rotulo: 'Vencida', tom: 'erro' },
  estornada: { rotulo: 'Estornada', tom: 'atencao' },
  removida: { rotulo: 'Cancelada', tom: 'neutro' },
}

export function situacaoCobranca(v: string | null | undefined): { rotulo: string; tom: Tom } {
  return (v && SITUACOES_COBRANCA[v]) || { rotulo: v || '—', tom: 'neutro' }
}

export const FORMAS_PAGAMENTO: Record<string, string> = { pix: 'Pix', boleto: 'Boleto', cartao: 'Cartão' }

export function emAberto(f: Pick<FaturaAberta, 'situacao'> | null | undefined): boolean {
  return !!f && (f.situacao === 'pendente' || f.situacao === 'vencida')
}

/** A mesma fatura em duas buscas: pelo link (único no Asaas) ou, sem ele, pelo vencimento. */
export function mesmaFatura(a: Pick<FaturaAberta, 'vencimento' | 'link'>, b: Pick<FaturaAberta, 'vencimento' | 'link'>): boolean {
  return a.link && b.link ? a.link === b.link : a.vencimento === b.vencimento
}

/**
 * Faturas em aberto (pendentes e vencidas) do histórico. O Asaas cria a fatura de cada mês até 40 dias antes, então
 * pode haver mais de uma; `fatura_aberta` é só a mais antiga.
 */
export function faturasEmAberto(e: Pick<EstadoAssinatura, 'fatura_aberta'> & Partial<Pick<EstadoAssinatura, 'cobrancas'>>): FaturaAberta[] {
  const abertas: FaturaAberta[] = (e.cobrancas ?? []).filter(emAberto)
  const f = e.fatura_aberta
  if (f && emAberto(f) && !abertas.some((a) => mesmaFatura(a, f))) abertas.push(f)
  return abertas
}

/** Faturas que estavam em aberto na busca anterior e agora aparecem pagas. */
export function faturasPagas(antes: CobrancaAssinatura[], depois: CobrancaAssinatura[]): CobrancaAssinatura[] {
  return depois.filter((c) => c.situacao === 'paga' && antes.some((a) => emAberto(a) && mesmaFatura(a, c)))
}

/** Com a conta ativa, a fatura pendente que vence daqui a mais de 5 dias ainda não é para pagar: é a "Próxima fatura". */
export const DIAS_PROXIMA_FATURA = 5

export function faturaFutura(e: Pick<EstadoAssinatura, 'conta' | 'fatura_aberta'>, agora: Date = new Date()): boolean {
  const f = e.fatura_aberta
  if (!f || e.conta.situacao !== 'ativa' || f.situacao !== 'pendente') return false
  return f.vencimento > somarDias(diaEmSaoPaulo(agora), DIAS_PROXIMA_FATURA)
}

/** Forma de pagamento: em aberto e sem forma, o cliente ainda escolhe na fatura. */
export function rotuloForma(c: Pick<CobrancaAssinatura, 'forma' | 'situacao'>): string {
  if (c.forma) return FORMAS_PAGAMENTO[c.forma] ?? c.forma
  return emAberto(c) ? 'A escolher' : '—'
}

/** O link da fatura só serve enquanto ela existe no Asaas (cancelada some de lá). */
export function linkDaCobranca(c: Pick<CobrancaAssinatura, 'link' | 'situacao'>): string | null {
  return c.link && c.situacao !== 'removida' ? c.link : null
}

/**
 * Próximo vencimento: o da fatura pendente; senão, o dia seguinte ao fim do período pago; senão, o primeiro
 * vencimento (assinatura recém-feita). Com fatura vencida, null (a tela mostra a vencida).
 */
export function proximoVencimento(e: Pick<EstadoAssinatura, 'conta' | 'assinatura' | 'fatura_aberta'>, agora: Date = new Date()): string | null {
  if (!e.assinatura) return null
  const f = e.fatura_aberta
  if (f?.situacao === 'vencida') return null
  if (f?.situacao === 'pendente') return f.vencimento
  const hoje = diaEmSaoPaulo(agora)
  if (e.conta.pago_ate) {
    const seguinte = somarDias(e.conta.pago_ate, 1)
    if (seguinte >= hoje) return seguinte
  }
  return e.assinatura.primeiro_vencimento >= hoje ? e.assinatura.primeiro_vencimento : null
}

/** Texto da confirmação de cancelar ("Você continua usando até 14/11/2026. Sem multa."). */
export function mensagemCancelamento(
  e: Pick<EstadoAssinatura, 'conta' | 'fatura_aberta'> & Partial<Pick<EstadoAssinatura, 'cobrancas'>>,
  agora: Date = new Date(),
): string {
  const c = e.conta
  const hoje = diaEmSaoPaulo(agora)
  const ultimo = ultimoDiaDoTeste(c.teste_ate)
  let uso: string
  if (c.pago_ate && c.pago_ate >= hoje) uso = `Você continua usando até ${formatarData(c.pago_ate)}. Sem multa e sem devolução.`
  else if (c.situacao === 'teste' && ultimo && testeValendo(c.teste_ate, agora)) uso = `Você volta para o teste grátis, que vai até ${formatarData(ultimo)}. Sem multa.`
  else uso = 'Os envios ficam pausados até você assinar de novo; seus dados continuam guardados. Sem multa.'
  const abertas = faturasEmAberto(e).length
  if (!abertas) return uso
  return abertas === 1 ? `${uso} A fatura em aberto é cancelada no Asaas.` : `${uso} As ${abertas} faturas em aberto são canceladas no Asaas.`
}

// ── Formulário de cobrança ──────────────────────────────────────────────────

export interface FormCobranca {
  razao_social: string
  documento: string
  email_cobranca: string
  telefone: string
}

export const MAX_RAZAO_SOCIAL = 200

/** As mesmas mensagens da API (422 `campos`). */
export const MENSAGENS_COBRANCA = {
  razao_social: 'Informe a razão social (ou o nome completo, para CPF).',
  razaoLonga: `Use no máximo ${MAX_RAZAO_SOCIAL} caracteres.`,
  documentoVazio: 'Informe o CPF ou o CNPJ.',
  documento: MENSAGENS.documento,
  emailVazio: 'Informe o e-mail que recebe as faturas.',
  email: MENSAGENS.email_contato,
  telefoneVazio: 'Informe o telefone com DDD.',
  telefoneBrasil: 'Informe um telefone do Brasil com DDD.',
} as const

/** Dados da API (sugeridos ou os da assinatura) → campos com máscara. */
export function formCobrancaDe(d: Partial<Record<keyof FormCobranca, string | null>> | null | undefined): FormCobranca {
  return {
    razao_social: d?.razao_social ?? '',
    documento: formatarDocumento(d?.documento ?? ''),
    email_cobranca: d?.email_cobranca ?? '',
    telefone: telefoneDoCampo(d?.telefone),
  }
}

/** Campos → corpo da API: sem espaços sobrando, telefone só com dígitos e documento sem pontuação (em maiúsculas). */
export function corpoCobranca(f: FormCobranca): DadosCobranca {
  return {
    razao_social: f.razao_social.trim().replace(/\s+/g, ' '),
    documento: normalizarDocumento(f.documento),
    email_cobranca: f.email_cobranca.trim(),
    telefone: apenasDigitos(f.telefone),
  }
}

/** Erros por campo antes de enviar (todos obrigatórios; o telefone precisa ser do Brasil, como pede o Asaas). */
export function validarCobranca(f: FormCobranca): Partial<Record<keyof FormCobranca, string>> {
  const e: Partial<Record<keyof FormCobranca, string>> = {}
  const razao = f.razao_social.trim()
  if (!razao) e.razao_social = MENSAGENS_COBRANCA.razao_social
  else if (razao.replace(/\s+/g, ' ').length > MAX_RAZAO_SOCIAL) e.razao_social = MENSAGENS_COBRANCA.razaoLonga
  if (!normalizarDocumento(f.documento)) e.documento = MENSAGENS_COBRANCA.documentoVazio
  else if (!documentoValido(f.documento)) e.documento = MENSAGENS_COBRANCA.documento
  if (!f.email_cobranca.trim()) e.email_cobranca = MENSAGENS_COBRANCA.emailVazio
  else if (!emailValido(f.email_cobranca)) e.email_cobranca = MENSAGENS_COBRANCA.email
  const tel = apenasDigitos(f.telefone)
  if (!tel) e.telefone = MENSAGENS_COBRANCA.telefoneVazio
  else {
    const problema = erroTelefone(f.telefone)
    if (problema) e.telefone = problema
    else {
      const comPais = tel.length <= 11 ? `55${tel}` : tel
      if (!comPais.startsWith('55') || (comPais.length !== 12 && comPais.length !== 13)) e.telefone = MENSAGENS_COBRANCA.telefoneBrasil
    }
  }
  return e
}

/** Mudou algo de verdade? (máscara, espaços e o 55 do telefone não contam). */
export function mesmosDadosCobranca(a: FormCobranca, b: FormCobranca): boolean {
  const norm = (f: FormCobranca) => {
    const c = corpoCobranca(f)
    return { ...c, email_cobranca: c.email_cobranca.toLowerCase(), telefone: c.telefone.length <= 11 ? `55${c.telefone}` : c.telefone }
  }
  return JSON.stringify(norm(a)) === JSON.stringify(norm(b))
}

// ── Teste grátis: selo do topo e cartão do Início ──────────────────────────────

type ContaTeste = Pick<Conta, 'situacao' | 'teste_ate' | 'plano'> & { cobranca?: Pick<CobrancaConta, 'assinada'> | null }

/** Dias inteiros de hoje (São Paulo) até o último dia do teste; 0 = termina hoje. */
export function diasDeTeste(ultimo: string, agora: Date = new Date()): number {
  const hoje = Date.parse(`${diaEmSaoPaulo(agora)}T00:00:00Z`)
  return Math.round((Date.parse(`${ultimo}T00:00:00Z`) - hoje) / 86_400_000)
}

function textoFalta(dias: number): string {
  return dias <= 0 ? 'termina hoje' : dias === 1 ? 'falta 1 dia' : `faltam ${dias} dias`
}

export interface SeloTeste {
  /** Texto das telas maiores ("Teste grátis: faltam 9 dias"). */
  texto: string
  /** Texto do celular ("Teste: 9 dias"). */
  curto: string
  titulo: string
  /** Leva a /assinatura (quem cuida da assinatura); com o rótulo do convite, quando ainda não assinou. */
  link: boolean
  convite: string | null
}

/**
 * Selo do topo enquanto a conta está em teste. Quem cuida da assinatura clica e vai à tela de Assinatura, com o convite
 * "Escolher plano" até assinar; os outros só leem.
 */
export function seloDoTeste(conta: ContaTeste | null | undefined, podeGerenciar: boolean, agora: Date = new Date()): SeloTeste | null {
  if (!conta || conta.situacao !== 'teste' || !conta.teste_ate) return null
  const ultimo = ultimoDiaDoTeste(conta.teste_ate)
  if (!ultimo) return null
  const data = formatarData(ultimo)
  const assinada = !!conta.cobranca?.assinada
  const convite = podeGerenciar && !assinada ? 'Escolher plano' : null
  if (!testeValendo(conta.teste_ate, agora)) {
    return { texto: `Teste grátis encerrado em ${data}`, curto: 'Teste encerrado', titulo: `Teste grátis encerrado em ${data}`, link: podeGerenciar, convite }
  }
  const dias = diasDeTeste(ultimo, agora)
  return {
    texto: `Teste grátis: ${textoFalta(dias)}`,
    curto: dias <= 0 ? 'Teste: hoje' : dias === 1 ? 'Teste: 1 dia' : `Teste: ${dias} dias`,
    titulo: `Teste grátis até ${data}`,
    link: podeGerenciar,
    convite,
  }
}

export interface CartaoTeste {
  data: string
  dias: number
  plano: string
}

/**
 * Cartão do Início para quem cuida da assinatura, durante o teste e antes de assinar. Nos últimos dias
 * (`DIAS_AVISO_TESTE`, o mesmo da API) quem avisa é a faixa do topo ("teste acabando"), então o cartão sai.
 */
export const DIAS_AVISO_TESTE = 5

export function cartaoDoTeste(conta: ContaTeste | null | undefined, podeGerenciar: boolean, agora: Date = new Date()): CartaoTeste | null {
  if (!podeGerenciar || !conta || conta.situacao !== 'teste' || conta.cobranca?.assinada) return null
  if (!testeValendo(conta.teste_ate, agora)) return null
  const ultimo = ultimoDiaDoTeste(conta.teste_ate)
  if (!ultimo) return null
  const dias = diasDeTeste(ultimo, agora)
  if (dias <= DIAS_AVISO_TESTE) return null
  return { data: formatarData(ultimo), dias, plano: nomeDoPlano(conta.plano) }
}

// Regras puras de Plataforma › Visão geral (etapa 5h, docs/api-etapa-5h.md §5): indicadores, textos dos testes
// acabando, ativação, busca, filtro e ordem da tabela de contas.
import type { AtivacaoConta, ContaVisao, ConversaoVisao, SituacaoVisao, TempoTeste, TotaisVisao } from '@/api/tipos'
import { diasAte, formatarData, formatarDiaMes } from '@/utils/datas'
import { formatarMoeda, formatarNumero, plural } from '@/utils/formatos'
import { situacaoConta, type Tom } from '@/utils/rotulos'

// ── Ativação ─────────────────────────────────────────────────────────────────

export const PASSOS_ATIVACAO: { chave: keyof AtivacaoConta; rotulo: string }[] = [
  { chave: 'contatos', rotulo: 'Contatos' },
  { chave: 'envios_ligados', rotulo: 'Envios ligados' },
  { chave: 'primeiro_envio', rotulo: 'Primeiro envio' },
  { chave: 'primeira_resposta', rotulo: 'Primeira resposta' },
]

export function passosFeitos(a: AtivacaoConta | null | undefined): number {
  return PASSOS_ATIVACAO.filter((p) => !!a?.[p.chave]).length
}

/** "Falta: primeiro envio e primeira resposta." / "Ativação completa." / "Nenhum passo feito." */
export function textoFalta(a: AtivacaoConta | null | undefined): string {
  const faltam = PASSOS_ATIVACAO.filter((p) => !a?.[p.chave]).map((p) => p.rotulo.toLowerCase())
  if (!faltam.length) return 'Ativação completa.'
  if (faltam.length === PASSOS_ATIVACAO.length) return 'Nenhum passo feito.'
  const lista = faltam.length === 1 ? faltam[0]! : `${faltam.slice(0, -1).join(', ')} e ${faltam.at(-1)}`
  return `Falta: ${lista}.`
}

/** O nome para o leitor de tela: "Ativação: 2 de 4. Feitos: contatos e envios ligados." */
export function rotuloAtivacao(a: AtivacaoConta | null | undefined): string {
  const feitos = PASSOS_ATIVACAO.filter((p) => !!a?.[p.chave]).map((p) => p.rotulo.toLowerCase())
  const lista = feitos.length <= 1 ? feitos.join('') : `${feitos.slice(0, -1).join(', ')} e ${feitos.at(-1)}`
  return `Ativação: ${feitos.length} de ${PASSOS_ATIVACAO.length}.${feitos.length ? ` Feitos: ${lista}.` : ''}`
}

// ── Situação ─────────────────────────────────────────────────────────────────

export const SITUACOES_VISAO: SituacaoVisao[] = ['teste', 'teste_expirado', 'ativa', 'atrasada', 'pausada', 'cancelada', 'cortesia']

/** Rótulo e cor da situação (a `pausada`: atrasada depois dos 7 dias, envios parados). */
export function rotuloSituacao(s: string | null | undefined): { rotulo: string; tom: Tom } {
  if (s === 'pausada') return { rotulo: 'Pausada', tom: 'erro' }
  if (s === 'atrasada') return { rotulo: 'Atrasada', tom: 'atencao' }
  return situacaoConta(s)
}

// ── Indicadores ──────────────────────────────────────────────────────────────

export interface Indicador {
  chave: string
  rotulo: string
  valor: string
  /** Linha de baixo. */
  detalhe: string
  /** Selo ao lado do valor (ex.: "sandbox"). */
  selo?: string
  /** Cor do valor (sem: a do texto). */
  tom?: Tom
  /** Cor da linha de baixo (sem: a do texto suave). */
  tomDetalhe?: Tom
}

const fmtPct = new Intl.NumberFormat('pt-BR', { maximumFractionDigits: 1 })

/** "75%" (taxa de 0 a 1), ou "—" sem contas no período. */
export function textoTaxa(taxa: number | null | undefined): string {
  return typeof taxa === 'number' && Number.isFinite(taxa) ? `${fmtPct.format(taxa * 100)}%` : '—'
}

/** "3 de 4 contas criadas entre 05/08 e 19/09 assinaram." / "Nenhuma conta com teste criada entre …". */
export function textoConversao(c: ConversaoVisao): string {
  const entre = `entre ${formatarDiaMes(c.de)} e ${formatarDiaMes(c.ate)}`
  if (!c.contas) return `Nenhuma conta com teste criada ${entre}.`
  const contas = c.contas === 1 ? `1 conta criada ${entre}` : `${formatarNumero(c.contas)} contas criadas ${entre}`
  return `${formatarNumero(c.assinaram)} de ${contas} ${c.assinaram === 1 ? 'assinou' : 'assinaram'}.`
}

export function indicadores(t: TotaisVisao, conversao: ConversaoVisao, testesAcabando: number): Indicador[] {
  const s = t.por_situacao ?? {}
  const n = (k: string) => s[k] ?? 0
  const encerrados = n('teste_expirado')
  const devendo = n('atrasada') + n('pausada')
  return [
    {
      chave: 'teste',
      rotulo: 'Em teste',
      valor: formatarNumero(n('teste')),
      detalhe: encerrados ? `${plural(encerrados, 'teste encerrado', 'testes encerrados')} sem assinar` : 'Nenhum teste encerrado sem assinar',
    },
    {
      chave: 'pagantes',
      rotulo: 'Pagantes',
      valor: formatarNumero(t.pagantes),
      detalhe: devendo ? `${plural(devendo, 'com fatura atrasada', 'com fatura atrasada')} · ${plural(t.contas, 'conta', 'contas')} no total` : `de ${plural(t.contas, 'conta', 'contas')}`,
      tomDetalhe: devendo ? 'atencao' : undefined,
    },
    {
      chave: 'receita',
      rotulo: 'Receita mensal',
      valor: formatarMoeda(t.receita_mensal, 'R$ 0,00'),
      detalhe: t.pagantes ? `das ${plural(t.pagantes, 'assinatura ativa', 'assinaturas ativas')}` : 'Nenhuma assinatura ativa',
      selo: t.ambiente === 'sandbox' ? 'sandbox' : undefined,
    },
    {
      chave: 'acabando',
      rotulo: 'Testes acabando em 7 dias',
      valor: formatarNumero(testesAcabando),
      detalhe: testesAcabando ? 'A lista está logo abaixo' : 'Nenhum teste acaba nesta semana',
      tom: testesAcabando ? 'atencao' : undefined,
    },
    {
      chave: 'novas',
      rotulo: 'Novas em 30 dias',
      valor: formatarNumero(t.novas_30d),
      detalhe: `${plural(t.novas_7d, 'nova', 'novas')} nos últimos 7 dias`,
    },
    {
      chave: 'conversao',
      rotulo: 'Conversão do teste',
      valor: textoTaxa(conversao.taxa),
      detalhe: textoConversao(conversao),
    },
  ]
}

// ── Datas ────────────────────────────────────────────────────────────────────

/** "Acaba hoje" / "Acaba amanhã" / "Faltam 3 dias". */
export function textoDiasRestantes(dias: number): string {
  if (dias <= 0) return 'Acaba hoje'
  if (dias === 1) return 'Acaba amanhã'
  return `Faltam ${dias} dias`
}

export function tomDiasRestantes(dias: number): Tom {
  return dias <= 1 ? 'erro' : dias <= 3 ? 'atencao' : 'info'
}

/** "Entrou hoje" / "Entrou ontem" / "Entrou há 5 dias" / "Entrou em 02/08/2026" (mais de 30 dias) / "Nunca entrou". */
export function textoUltimoAcesso(iso: string | null | undefined): string {
  if (!iso) return 'Nunca entrou'
  const dias = diasAte(iso)
  if (dias === null) return 'Nunca entrou'
  if (dias >= 0) return 'Entrou hoje'
  if (dias === -1) return 'Entrou ontem'
  if (dias >= -30) return `Entrou há ${-dias} dias`
  return `Entrou em ${formatarData(iso)}`
}

// ── Tabela de contas ─────────────────────────────────────────────────────────

export type OrdemContas = 'ultimo_acesso' | 'criacao' | 'respostas'

export const ORDENS_CONTAS: { valor: OrdemContas; rotulo: string }[] = [
  { valor: 'ultimo_acesso', rotulo: 'Último acesso' },
  { valor: 'criacao', rotulo: 'Criação' },
  { valor: 'respostas', rotulo: 'Respostas' },
]

export interface FiltroContas {
  busca: string
  situacao: string
  ordem: OrdemContas
}

const tempo = (iso: string | null | undefined) => (iso ? new Date(iso).getTime() || 0 : 0)

/** Busca (nome da conta ou e-mail do administrador, sem diferenciar maiúsculas e acentos), situação e ordem. */
export function contasFiltradas(contas: ContaVisao[], f: FiltroContas): ContaVisao[] {
  const sem = (s: string) => s.normalize('NFD').replace(/\p{Diacritic}/gu, '').toLowerCase()
  const busca = sem(f.busca.trim())
  const lista = contas.filter(
    (c) => (!f.situacao || c.situacao === f.situacao) && (!busca || sem(c.nome).includes(busca) || sem(c.admin_email ?? '').includes(busca)),
  )
  const criterio: Record<OrdemContas, (a: ContaVisao, b: ContaVisao) => number> = {
    // quem nunca entrou fica no fim
    ultimo_acesso: (a, b) => tempo(b.ultimo_acesso) - tempo(a.ultimo_acesso),
    criacao: (a, b) => tempo(b.criada_em) - tempo(a.criada_em),
    respostas: (a, b) => b.respostas_30d - a.respostas_30d || b.respostas_total - a.respostas_total,
  }
  return [...lista].sort((a, b) => criterio[f.ordem](a, b) || tempo(b.criada_em) - tempo(a.criada_em))
}

/** Situações para o filtro, só as que aparecem nas contas, com a contagem: "Em teste (3)". */
export function opcoesSituacao(contas: ContaVisao[]): { valor: string; rotulo: string }[] {
  const contagem = new Map<string, number>()
  for (const c of contas) contagem.set(c.situacao, (contagem.get(c.situacao) ?? 0) + 1)
  const ordem = [...SITUACOES_VISAO, ...[...contagem.keys()].filter((s) => !SITUACOES_VISAO.includes(s as SituacaoVisao))]
  return ordem.filter((s) => contagem.has(s)).map((s) => ({ valor: s, rotulo: `${rotuloSituacao(s).rotulo} (${contagem.get(s)})` }))
}

/** "Profissional · R$ 349,00/mês" com assinatura; sem ela, "Profissional · sem assinatura" (o plano da conta). */
export function textoPlano(c: Pick<ContaVisao, 'plano' | 'assinatura'>, nomeDoPlano: (p: string) => string): string {
  if (c.assinatura) return `${nomeDoPlano(c.assinatura.plano)} · ${formatarMoeda(c.assinatura.valor)}/mês`
  return c.plano ? `${nomeDoPlano(c.plano)} · sem assinatura` : 'Sem assinatura'
}

/**
 * Melhoria 9: uma leitura do tempo do teste para decidir a duração (7 dias, 14 ou "até as primeiras respostas"). Só
 * opina com pelo menos 10 contas na janela.
 */
export function leituraTeste(t: TempoTeste): string {
  if (t.contas < 10) return 'Ainda são poucas contas para decidir (precisa de pelo menos 10 testes na janela).'
  const chegaram = t.chegaram / t.contas
  if (chegaram < 0.4) {
    return 'A maioria dos testes não chega à primeira resposta: estender o prazo não resolve sozinho; vale testar "até as primeiras respostas" e ajudar no primeiro envio.'
  }
  if (t.chegaram && t.ate_7_dias / t.chegaram >= 0.8) return 'Quase todos que respondem chegam lá em até 7 dias: um teste de 7 dias seria suficiente.'
  return 'Uma parte boa só chega à primeira resposta entre o 7º e o 14º dia: manter os 14 dias.'
}

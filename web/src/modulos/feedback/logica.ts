// Regras puras do feedback (docs/api-feedback.md): tipos, situações, textos e o depoimento. Sem Vue, para testar.
import type { ImpactoFeedback, MensagemFeedback, SituacaoFeedback, TipoFeedback } from '@/api/feedback'
import type { Tom } from '@/utils/rotulos'

export const MAX_TEXTO = 5000
export const MAX_IMAGENS = 3
/** Até 1 MB por imagem (a API recusa acima). */
export const LIMITE_IMAGEM = 1024 * 1024

export interface InfoTipo {
  /** Rótulo curto (lista, filtros, etiqueta). */
  rotulo: string
  /** O cartão da escolha do tipo. */
  titulo: string
  descricao: string
  /** O rótulo da caixa de texto. */
  pergunta: string
  exemplo: string
  /** O que a tela diz depois de enviar. */
  enviado: string
  tom: Tom
}

export const TIPOS_FEEDBACK: Record<TipoFeedback, InfoTipo> = {
  erro: {
    rotulo: 'Erro',
    titulo: 'Algo deu errado',
    descricao: 'Algo não funcionou como deveria.',
    pergunta: 'O que aconteceu?',
    exemplo: 'Ex.: cliquei em Salvar no formulário e apareceu “Algo deu errado”. Esperava que salvasse.',
    enviado: 'Vamos investigar e te contamos por aqui e por e-mail assim que tivermos novidade.',
    tom: 'erro',
  },
  sugestao: {
    rotulo: 'Sugestão',
    titulo: 'Tenho uma ideia',
    descricao: 'Algo novo que o Toqqi poderia ter.',
    pergunta: 'Qual é a sua ideia?',
    exemplo: 'Ex.: seria ótimo mandar o relatório de empresas por e-mail toda segunda.',
    enviado: 'Toda ideia é lida pela equipe. Você acompanha a situação dela por aqui.',
    tom: 'info',
  },
  melhoria: {
    rotulo: 'Melhoria',
    titulo: 'Dá para melhorar',
    descricao: 'Algo que já existe pode ficar melhor.',
    pergunta: 'O que pode ficar melhor?',
    exemplo: 'Ex.: o filtro de período podia lembrar a última escolha.',
    enviado: 'Vamos avaliar e te contamos o que decidirmos por aqui.',
    tom: 'atencao',
  },
  elogio: {
    rotulo: 'Elogio',
    titulo: 'Gostei!',
    descricao: 'Conte o que funcionou bem para você.',
    pergunta: 'O que você gostou?',
    exemplo: 'Ex.: o resumo da IA no Início economiza meu tempo toda semana.',
    enviado: 'Obrigado! Isso faz o dia da equipe Toqqi.',
    tom: 'sucesso',
  },
}

export const ORDEM_TIPOS: TipoFeedback[] = ['erro', 'sugestao', 'melhoria', 'elogio']

export const SITUACOES_FEEDBACK: Record<SituacaoFeedback, { rotulo: string; tom: Tom }> = {
  recebido: { rotulo: 'Recebido', tom: 'neutro' },
  em_analise: { rotulo: 'Em análise', tom: 'info' },
  planejado: { rotulo: 'Planejado', tom: 'marca' },
  concluido: { rotulo: 'Concluído', tom: 'sucesso' },
  encerrado: { rotulo: 'Encerrado', tom: 'neutro' },
}

export const OPCOES_SITUACAO: { valor: SituacaoFeedback; rotulo: string }[] = (
  Object.keys(SITUACOES_FEEDBACK) as SituacaoFeedback[]
).map((valor) => ({ valor, rotulo: SITUACOES_FEEDBACK[valor].rotulo }))

export const IMPACTOS: { valor: ImpactoFeedback; rotulo: string; extenso: string }[] = [
  { valor: 'bloqueia', rotulo: 'Estou travado', extenso: 'Impede o trabalho' },
  { valor: 'atrapalha', rotulo: 'Atrapalha', extenso: 'Atrapalha, mas dá para seguir' },
  { valor: 'detalhe', rotulo: 'É um detalhe', extenso: 'É um detalhe' },
]

export function rotuloImpacto(i: ImpactoFeedback | null | undefined): string | null {
  return IMPACTOS.find((x) => x.valor === i)?.extenso ?? null
}

/** Tipo e situação com rótulo e tom; um valor desconhecido aparece como veio. */
export function infoTipo(t: string): InfoTipo {
  return TIPOS_FEEDBACK[t as TipoFeedback] ?? { ...TIPOS_FEEDBACK.sugestao, rotulo: t, titulo: t, tom: 'neutro' }
}

export function infoSituacao(s: string): { rotulo: string; tom: Tom } {
  return SITUACOES_FEEDBACK[s as SituacaoFeedback] ?? { rotulo: s, tom: 'neutro' }
}

/** O erro da caixa de texto antes de enviar (a API confere de novo), ou null. */
export function erroDoTexto(texto: string, comImagens = false): string | null {
  const t = texto.trim()
  if (!t && !comImagens) return 'Escreva o que você quer contar.'
  if (t.length > MAX_TEXTO) return `Use até ${MAX_TEXTO.toLocaleString('pt-BR')} caracteres.`
  return null
}

/** “O Toqqi mudou nosso atendimento.” — Ana Souza, Alfa Ltda (para colar no site). */
export function textoDepoimento(texto: string, nome: string | null | undefined, conta: string | null | undefined): string {
  const autor = [nome?.trim(), conta?.trim()].filter(Boolean).join(', ')
  const corpo = `“${texto.trim().replace(/\s+/g, ' ')}”`
  return autor ? `${corpo} — ${autor}` : corpo
}

/** "1 resposta nova" / "3 respostas novas" (menu e leitores de tela). */
export function textoNovidades(n: number): string {
  return n === 1 ? '1 resposta nova' : `${n} respostas novas`
}

/** "1 feedback novo" / "2 feedbacks novos" (Plataforma). */
export function textoAtencao(n: number): string {
  return n === 1 ? '1 feedback precisa de atenção' : `${n} feedbacks precisam de atenção`
}

/** Mudança de situação feita pela equipe, como aparece na conversa. */
export function textoMudanca(m: Pick<MensagemFeedback, 'situacao'>): string | null {
  return m.situacao ? `Situação: ${infoSituacao(m.situacao).rotulo}` : null
}

const FUSO = 'America/Sao_Paulo'

function diaEmSaoPaulo(d: Date): string {
  return d.toLocaleDateString('en-CA', { timeZone: FUSO })
}

/** "agora há pouco", "há 12 min", "hoje às 14:20", "ontem às 09:05", "06/10 às 21:30" ou "06/10/2025 às 21:30". */
export function rotuloQuando(iso: string | null | undefined, agora = new Date()): string {
  if (!iso) return '—'
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return '—'
  const minutos = Math.floor((agora.getTime() - d.getTime()) / 60000)
  if (minutos < 1 && minutos > -2) return 'agora há pouco'
  if (minutos >= 1 && minutos < 60) return `há ${minutos} min`
  const hora = d.toLocaleTimeString('pt-BR', { timeZone: FUSO, hour: '2-digit', minute: '2-digit' })
  const dia = diaEmSaoPaulo(d)
  if (dia === diaEmSaoPaulo(agora)) return `hoje às ${hora}`
  if (dia === diaEmSaoPaulo(new Date(agora.getTime() - 86_400_000))) return `ontem às ${hora}`
  const mesmoAno = dia.slice(0, 4) === diaEmSaoPaulo(agora).slice(0, 4)
  const data = d.toLocaleDateString('pt-BR', { timeZone: FUSO, day: '2-digit', month: '2-digit', ...(mesmoAno ? {} : { year: 'numeric' }) })
  return `${data} às ${hora}`
}

/**
 * Onde a pessoa estava quando abriu o feedback: o caminho e o título da tela. Em "Seus feedbacks" (onde a tela atual
 * não diz nada), vale a tela anterior, quando o navegador sabe qual foi.
 */
export function telaDeOrigem(
  atual: { path: string; titulo?: string | null },
  anterior?: { path: string; titulo?: string | null } | null,
): { pagina: string; titulo: string | null } | null {
  const util = (t: { path: string; titulo?: string | null } | null | undefined) =>
    !!t && t.path.startsWith('/') && !t.path.startsWith('/feedback')
  const escolhida = util(atual) ? atual : util(anterior) ? anterior! : null
  if (!escolhida) return null
  return { pagina: escolhida.path.split(/[?#]/)[0]!.slice(0, 200), titulo: escolhida.titulo?.slice(0, 120) || null }
}

/** Tamanho em KB ou MB, para a lista de imagens. */
export function tamanhoArquivo(bytes: number): string {
  if (bytes < 1024 * 1024) return `${Math.max(1, Math.round(bytes / 1024))} KB`
  return `${(bytes / (1024 * 1024)).toLocaleString('pt-BR', { maximumFractionDigits: 1 })} MB`
}

/** Largura e altura dentro de `maximo` no lado maior, mantendo a proporção. */
export function medidasReduzidas(largura: number, altura: number, maximo: number): { largura: number; altura: number } {
  const maior = Math.max(largura, altura)
  if (maior <= maximo) return { largura, altura }
  const f = maximo / maior
  return { largura: Math.max(1, Math.round(largura * f)), altura: Math.max(1, Math.round(altura * f)) }
}

/** O nome do arquivo depois da conversão (troca a extensão; colada da área de transferência vira "print-1.png"). */
export function nomeDaImagem(original: string | null | undefined, tipo: 'image/png' | 'image/jpeg', indice = 1): string {
  const ext = tipo === 'image/png' ? 'png' : 'jpg'
  const base = (original ?? '').replace(/\.[^.]*$/, '').replace(/[\\/]/g, '').trim()
  return `${base && base !== 'image' ? base : `print-${indice}`}.${ext}`.slice(0, 120)
}

// Regras puras do topo de Envios (docs/api-envios-panorama.md): a frase do envio automático (o que acontece e quando),
// as regras de envio em uma linha, a agenda dos próximos 14 dias e quantos responderam. Sem Vue, para testar.
import type { PanoramaEnvios, RespostasEnvios } from '@/api/tipos'
import { formatarNumero, plural } from '@/utils/formatos'

type Automatico = PanoramaEnvios['automatico']

const DIAS_SEMANA = ['domingo', 'segunda-feira', 'terça-feira', 'quarta-feira', 'quinta-feira', 'sexta-feira', 'sábado']
const DIAS_CURTOS = ['dom', 'seg', 'ter', 'qua', 'qui', 'sex', 'sáb']

/** "2026-10-08" → Date ao meio-dia (sem fuso no meio do caminho). */
function dataDoDia(iso: string): Date {
  const [a, m, d] = iso.slice(0, 10).split('-').map(Number) as [number, number, number]
  return new Date(a, m - 1, d, 12)
}

function diasEntre(de: string, ate: string): number {
  return Math.round((dataDoDia(ate).getTime() - dataDoDia(de).getTime()) / 86_400_000)
}

/** "08:00" → "8h"; "14:30" → "14h30". */
export function hora(hhmm: string): string {
  const [h, m] = hhmm.split(':')
  return `${Number(h)}h${m && m !== '00' ? m : ''}`
}

/** A parte "dia" de um momento, a partir de hoje: "hoje", "amanhã", "na segunda-feira", "em 12/10". */
export function quandoDia(dia: string, hoje: string): string {
  const n = diasEntre(hoje, dia)
  if (n <= 0) return 'hoje'
  if (n === 1) return 'amanhã'
  const d = dataDoDia(dia)
  if (n < 7) return `${d.getDay() === 0 || d.getDay() === 6 ? 'no' : 'na'} ${DIAS_SEMANA[d.getDay()]}`
  return `em ${String(d.getDate()).padStart(2, '0')}/${String(d.getMonth() + 1).padStart(2, '0')}`
}

/** "2026-10-08T14:00:00-03:00" → "hoje às 14h" (a hora já vem em São Paulo). */
export function quandoRodada(iso: string, hoje: string): string {
  const hhmm = iso.slice(11, 16)
  return `${quandoDia(iso.slice(0, 10), hoje)} às ${hora(hhmm)}`
}

export interface Manchete {
  /** O estado em poucas palavras, ao lado do ponto colorido. */
  estado: string
  tom: 'sucesso' | 'atencao' | 'neutro'
  titulo: string
  texto: string | null
}

/**
 * O que está acontecendo com o envio, em uma frase. `agora` (ms) decide se a rodada prevista já pode sair (as tarefas
 * passam a cada 30 minutos: "nos próximos 30 minutos").
 */
export function manchete(a: Automatico, hoje: string, agora: number): Manchete {
  if (a.estado === 'desligado')
    return { estado: 'Envios desligados', tom: 'neutro', titulo: 'Nenhuma pesquisa ou lembrete sai agora', texto: 'Ligue os envios em Configurações de envio.' }
  if (a.estado === 'parado')
    return { estado: 'Envios parados', tom: 'atencao', titulo: 'Os envios estão parados', texto: 'Resolva o que o aviso logo abaixo pede para eles voltarem a sair.' }
  if (a.estado === 'manual')
    return {
      estado: 'Envio automático desligado',
      tom: 'neutro',
      titulo: 'As pesquisas só saem quando alguém envia por aqui',
      texto: a.lembretes ? 'Os lembretes de quem não respondeu continuam saindo sozinhos.' : null,
    }
  if (!a.na_fila)
    return {
      estado: 'Envio automático ligado',
      tom: 'sucesso',
      titulo: a.fora_da_rodada ? 'Ninguém na fila pode receber agora' : 'Ninguém na fila agora',
      texto: a.fora_da_rodada
        ? `${plural(a.fora_da_rodada, 'contato está', 'contatos estão')} na fila, mas sem ${a.canal === 'email' ? 'e-mail' : 'e-mail nem telefone'}, em descanso ou com envios que falharam.`
        : a.proximo_contato
          ? `O próximo contato entra na fila ${quandoDia(a.proximo_contato, hoje)}.`
          : 'Todos já receberam a pesquisa dentro do intervalo.',
    }
  const leva = Math.min(a.na_fila, a.por_rodada)
  const fora = a.fora_da_rodada
    ? `${plural(a.fora_da_rodada, 'contato da fila fica', 'contatos da fila ficam')} de fora: sem ${a.canal === 'email' ? 'e-mail' : 'e-mail nem telefone'}, em descanso ou com envios que falharam.`
    : null
  const quando = !a.proxima_rodada ? null : new Date(a.proxima_rodada).getTime() <= agora ? 'nos próximos 30 minutos' : quandoRodada(a.proxima_rodada, hoje)
  return {
    estado: 'Envio automático ligado',
    tom: 'sucesso',
    titulo: quando ? `Próxima rodada ${quando}, para ${plural(leva, 'contato', 'contatos')}` : `${plural(a.na_fila, 'contato', 'contatos')} na fila`,
    texto:
      [
        a.na_fila > a.por_rodada ? `Cada rodada leva até ${formatarNumero(a.por_rodada)}; os outros ${formatarNumero(a.na_fila - a.por_rodada)} vão nas seguintes.` : null,
        fora,
      ]
        .filter(Boolean)
        .join(' ') || null,
  }
}

const CANAIS: Record<Automatico['canal'], string> = { email: 'por e-mail', whatsapp: 'pelo WhatsApp', whatsapp_e_email: 'pelo WhatsApp e por e-mail' }

/** "Em dias úteis, das 8h às 18h, por e-mail, a cada 90 dias por contato." */
export function regras(a: Automatico): string {
  const dias = a.so_dias_uteis ? 'Em dias úteis' : 'Todos os dias'
  return `${dias}, das ${hora(a.janela_inicio)} às ${hora(a.janela_fim)}, ${CANAIS[a.canal] ?? 'por e-mail'}, a cada ${formatarNumero(a.intervalo_dias)} dias por contato.`
}

// ── Agenda ──────────────────────────────────────────────────────────────────

export interface DiaAgenda {
  dia: string
  /** "Hoje", "qui"… */
  rotulo: string
  /** Dia do mês. */
  numero: string
  /** "quinta-feira, 9 de outubro" (dica e leitores de tela). */
  longo: string
  pesquisas: number
  lembretes: number
  /** Altura de cada parte, em % do dia com mais envios (com valor, nunca menos de 4%). */
  alturaPesquisas: number
  alturaLembretes: number
  sai: boolean
  hoje: boolean
}

const MESES = ['janeiro', 'fevereiro', 'março', 'abril', 'maio', 'junho', 'julho', 'agosto', 'setembro', 'outubro', 'novembro', 'dezembro']

export function agenda(p: PanoramaEnvios, hoje: string): DiaAgenda[] {
  const maior = Math.max(0, ...p.agenda.map((d) => d.pesquisas + d.lembretes))
  const altura = (n: number) => (maior > 0 && n > 0 ? Math.max(4, Math.round((n / maior) * 100)) : 0)
  return p.agenda.map((d) => {
    const data = dataDoDia(d.dia)
    const eHoje = d.dia === hoje
    return {
      dia: d.dia,
      rotulo: eHoje ? 'Hoje' : (DIAS_CURTOS[data.getDay()] ?? ''),
      numero: String(data.getDate()),
      longo: `${eHoje ? 'hoje, ' : ''}${DIAS_SEMANA[data.getDay()]}, ${data.getDate()} de ${MESES[data.getMonth()]}`,
      pesquisas: d.pesquisas,
      lembretes: d.lembretes,
      alturaPesquisas: altura(d.pesquisas),
      alturaLembretes: altura(d.lembretes),
      sai: d.sai,
      hoje: eHoje,
    }
  })
}

/** "15 pesquisas e 6 lembretes nos próximos 14 dias"; "Nada previsto nos próximos 14 dias". */
export function totalAgenda(p: PanoramaEnvios): string {
  const pesquisas = p.agenda.reduce((n, d) => n + d.pesquisas, 0)
  const lembretes = p.agenda.reduce((n, d) => n + d.lembretes, 0)
  const partes = [pesquisas ? plural(pesquisas, 'pesquisa', 'pesquisas') : '', lembretes ? plural(lembretes, 'lembrete', 'lembretes') : ''].filter(Boolean)
  return partes.length ? `${partes.join(' e ')} nos próximos 14 dias` : 'Nada previsto nos próximos 14 dias'
}

/** A dica de um dia: "quinta-feira, 9 de outubro: 12 pesquisas e 3 lembretes" ou "… sem envio (fim de semana)". */
export function detalheDia(d: DiaAgenda, soDiasUteis: boolean): string {
  if (!d.sai) return `${d.longo}: sem envio${d.hoje ? ' (a janela de hoje já fechou)' : soDiasUteis ? ' (só dias úteis)' : ''}`
  const partes = [d.pesquisas ? plural(d.pesquisas, 'pesquisa', 'pesquisas') : '', d.lembretes ? plural(d.lembretes, 'lembrete', 'lembretes') : ''].filter(Boolean)
  return `${d.longo}: ${partes.length ? partes.join(' e ') : 'nada previsto'}`
}

// ── Respostas ───────────────────────────────────────────────────────────────

/** "17 de 36 pesquisas enviadas nos últimos 30 dias foram respondidas"; sem envio: null. */
export function respondidas(r: RespostasEnvios): string | null {
  if (!r.enviadas) return null
  const foram = r.respondidas === 1 ? 'foi respondida' : 'foram respondidas'
  return `${formatarNumero(r.respondidas)} de ${plural(r.enviadas, 'pesquisa enviada', 'pesquisas enviadas')} nos últimos 30 dias ${foram}`
}

export interface VariacaoTaxa {
  texto: string
  sentido: 'subiu' | 'caiu' | 'igual'
}

/** A taxa contra a dos 30 dias anteriores, em pontos; null sem uma das duas. */
export function variacaoTaxa(r: PanoramaEnvios['respostas']): VariacaoTaxa | null {
  if (r.taxa === null || r.anterior.taxa === null) return null
  const d = r.taxa - r.anterior.taxa
  if (d === 0) return { texto: 'Igual aos 30 dias anteriores', sentido: 'igual' }
  const pontos = plural(Math.abs(d), 'ponto', 'pontos')
  return d > 0 ? { texto: `${pontos} acima dos 30 dias anteriores`, sentido: 'subiu' } : { texto: `${pontos} abaixo dos 30 dias anteriores`, sentido: 'caiu' }
}

/** "Metade respondeu em até 6 horas" / "… em até 2 dias"; null sem respostas. */
export function tempoAteMetade(horas: number | null): string | null {
  if (horas === null) return null
  if (horas < 1) return 'Metade respondeu em menos de 1 hora'
  if (horas < 36) return `Metade respondeu em até ${plural(Math.round(horas), 'hora', 'horas')}`
  return `Metade respondeu em até ${plural(Math.round(horas / 24), 'dia', 'dias')}`
}

export const ROTULO_CANAL: Record<'email' | 'whatsapp', string> = { email: 'E-mail', whatsapp: 'WhatsApp' }

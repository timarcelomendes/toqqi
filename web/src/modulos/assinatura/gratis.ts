// Plano Grátis (docs/api-plano-gratis.md; sem Vue): os textos e as regras das telas. A conta que termina o teste sem
// assinar, a que cancelou e viu o período pago acabar e a que ficou 30 dias com a fatura vencida passam para o Grátis.
// Nada é apagado por causa de limite: o que passa dele fica parado, à vista, com o caminho para assinar ao lado.
import type { LimitesGratis, MotivoGratis, ResumoGratis } from '@/api/tipos'
import { formatarDiaMes } from '@/utils/datas'
import { formatarNumero } from '@/utils/formatos'

/** O que aparece onde um recurso não faz parte do Grátis (com "Ver planos" ao lado). */
export const MSG_RECURSO = 'Disponível a partir do plano Essencial.'
export const ROTA_PLANOS = '/assinatura'

/** Os números do Grátis quando a API ainda não mandou os da conta (os padrões da plataforma). */
export const LIMITES_PADRAO: LimitesGratis = {
  contatos: 100,
  envios_mes: 200,
  envios_dia: 100,
  usuarios: 1,
  formularios: 2,
  ia_cota: 10,
  dias_sem_uso: 180,
  descanso_minimo: 30,
}

const MESES = ['janeiro', 'fevereiro', 'março', 'abril', 'maio', 'junho', 'julho', 'agosto', 'setembro', 'outubro', 'novembro', 'dezembro']

export function ehGratis(conta: { situacao?: string | null } | null | undefined): boolean {
  return conta?.situacao === 'gratis'
}

/** "1 usuário" ou "até 3 usuários". */
export function textoUsuarios(n: number): string {
  return n === 1 ? '1 usuário' : `até ${formatarNumero(n)} usuários`
}

/** "até 100 contatos e 200 envios por e-mail por mês". */
export function resumoDosLimites(l: { contatos: number; envios_mes: number }): string {
  return `até ${formatarNumero(l.contatos)} contatos e ${formatarNumero(l.envios_mes)} envios por e-mail por mês`
}

/** Os limites a partir do resumo da conta (ou os padrões). */
export function limitesDoResumo(g: ResumoGratis | null | undefined): { contatos: number; envios_mes: number } {
  return g ? { contatos: g.contatos.limite, envios_mes: g.envios.limite_mes } : LIMITES_PADRAO
}

/** "1º de novembro" (AAAA-MM-DD). */
export function diaPorExtenso(dia: string): string {
  const [, m, d] = dia.split('-').map(Number)
  if (!m || !d) return dia
  return `${d === 1 ? '1º' : d} de ${MESES[m - 1]}`
}

/** Aviso do topo nos 7 primeiros dias do Grátis, pelo motivo da passagem. */
export function textoDaPassagem(motivo: MotivoGratis | null | undefined, g?: ResumoGratis | null): string {
  const limites = resumoDosLimites(limitesDoResumo(g))
  if (motivo === 'cancelamento') return `O período pago terminou e a conta passou para o Grátis: ${limites}.`
  if (motivo === 'atraso') return `A assinatura foi cancelada por falta de pagamento e a conta passou para o Grátis: ${limites}.`
  return `Seu teste acabou e a conta passou para o Grátis: ${limites}.`
}

export type AcaoGratis = 'planos' | 'contatos' | 'feedback'

export interface AvisoGratis {
  /** Lembrar que a pessoa fechou (o mesmo aviso, no mesmo dia ou mês, não volta na sessão). */
  chave: string
  texto: string
  tom: 'info' | 'atencao' | 'erro'
  /** Botões, na ordem; "planos" só para quem cuida da assinatura. */
  acoes: AcaoGratis[]
  dispensavel: boolean
}

export const ROTULOS_ACAO_GRATIS: Record<AcaoGratis, string> = {
  planos: 'Ver planos',
  contatos: 'Ver contatos',
  feedback: 'Falar com a equipe',
}

export const ROTAS_ACAO_GRATIS: Record<AcaoGratis, string> = {
  planos: ROTA_PLANOS,
  contatos: '/contatos',
  feedback: '/feedback',
}

/**
 * O aviso do topo quando a conta Grátis passou de um limite, do mais grave ao mais leve: envios pausados pela nota de
 * risco, mais contatos ativos que o limite (os envios param até ficarem dentro dele), os e-mails do mês acabaram, os
 * do dia acabaram. Null quando nada passou.
 */
export function avisoDoGratis(g: ResumoGratis | null | undefined): AvisoGratis | null {
  if (!g) return null
  if (g.pausada_por_risco) {
    return {
      chave: 'gratis:revisao',
      texto: 'Os envios estão pausados enquanto a equipe Toqqi confere a conta. Isso costuma levar até 1 dia útil.',
      tom: 'atencao',
      acoes: ['feedback'],
      dispensavel: false,
    }
  }
  if (g.contatos.ativos > g.contatos.limite) {
    return {
      chave: `gratis:contatos:${g.contatos.limite}`,
      texto: `Sua conta tem ${formatarNumero(g.contatos.ativos)} contatos ativos. O Grátis envia para até ${formatarNumero(g.contatos.limite)}: escolha quais manter ativos ou assine um plano.`,
      tom: 'atencao',
      acoes: ['contatos', 'planos'],
      dispensavel: false,
    }
  }
  const e = g.envios
  if (e.mes >= e.limite_mes) {
    return {
      chave: `gratis:mes:${e.volta_mes}`,
      texto: `Os envios por e-mail deste mês acabaram (${formatarNumero(e.mes)} de ${formatarNumero(e.limite_mes)}). Voltam em ${diaPorExtenso(e.volta_mes)}, ou assine para continuar agora.`,
      tom: 'info',
      acoes: ['planos'],
      dispensavel: true,
    }
  }
  if (e.dia >= e.limite_dia) {
    return {
      chave: `gratis:dia:${e.volta_dia}`,
      texto: `Os envios por e-mail de hoje acabaram (${formatarNumero(e.dia)} de ${formatarNumero(e.limite_dia)}). Voltam amanhã.`,
      tom: 'info',
      acoes: ['planos'],
      dispensavel: true,
    }
  }
  return null
}

export interface UsoGratis {
  chave: 'contatos' | 'envios' | 'ia'
  rotulo: string
  usado: number
  limite: number
  /** "37 de 100". */
  texto: string
  /** O que acontece no limite (embaixo do medidor). */
  dica: string
}

/** Os medidores da tela de Assinatura (contatos ativos, envios do mês, ToqqiAI do mês). */
export function usoDoGratis(g: ResumoGratis): UsoGratis[] {
  const de = (usado: number, limite: number) => `${formatarNumero(usado)} de ${formatarNumero(limite)}`
  return [
    {
      chave: 'contatos',
      rotulo: 'Contatos ativos',
      usado: g.contatos.ativos,
      limite: g.contatos.limite,
      texto: de(g.contatos.ativos, g.contatos.limite),
      dica:
        g.contatos.ativos > g.contatos.limite
          ? 'Acima do limite: os envios voltam quando ficarem dentro dele.'
          : 'Contatos inativos não contam.',
    },
    {
      chave: 'envios',
      rotulo: 'Envios por e-mail no mês',
      usado: g.envios.mes,
      limite: g.envios.limite_mes,
      texto: de(g.envios.mes, g.envios.limite_mes),
      dica: `Até ${formatarNumero(g.envios.limite_dia)} por dia. Zeram em ${formatarDiaMes(g.envios.volta_mes)}.`,
    },
    {
      chave: 'ia',
      rotulo: 'ToqqiAI no mês',
      usado: g.ia.usadas,
      limite: g.ia.limite,
      texto: de(g.ia.usadas, g.ia.limite),
      dica: 'Perguntas e análises pedidas ao ToqqiAI.',
    },
  ]
}

/** O que muda no Grátis, para o cartão da tela de Assinatura (sem os números do uso). */
export function itensDoGratis(l: Pick<LimitesGratis, 'usuarios' | 'formularios'>): string[] {
  return [
    `${textoUsuarios(l.usuarios)} e até ${formatarNumero(l.formularios)} formulários recebendo respostas`,
    'E-mail, link público, link de cada contato e WhatsApp automático',
    'Sem RD Station, Omie, Bling, chave de API e webhooks (ficam guardados)',
    '"Pesquisa feita com Toqqi" sempre aparece',
  ]
}

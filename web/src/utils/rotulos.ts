import { formatarDiaMes } from './datas'
import type { CanalConfig, CanalResposta, EventoWebhook, Gravidade, ItemAuditoria, Perfil, SituacaoContato, SituacaoUsuario, TipoFormulario } from '@/api/tipos'

export type Tom = 'neutro' | 'marca' | 'sucesso' | 'atencao' | 'erro' | 'info'

export const PERFIS: Record<Perfil, { rotulo: string; descricao: string; tom: Tom }> = {
  admin: { rotulo: 'Administrador', descricao: 'Pode tudo, inclusive equipe e configurações.', tom: 'marca' },
  gestor: { rotulo: 'Gestor', descricao: 'Trabalha no dia a dia com o que você liberar.', tom: 'info' },
  consulta: { rotulo: 'Consulta', descricao: 'Só olha: ideal para quem acompanha resultados.', tom: 'neutro' },
}

export const SITUACOES_USUARIO: Record<SituacaoUsuario, { rotulo: string; tom: Tom }> = {
  ativo: { rotulo: 'Ativo', tom: 'sucesso' },
  pendente: { rotulo: 'Pendente de aprovação', tom: 'atencao' },
  bloqueado: { rotulo: 'Bloqueado', tom: 'erro' },
}

export const GRAVIDADES: Record<Gravidade, { rotulo: string; tom: Tom }> = {
  info: { rotulo: 'Informação', tom: 'info' },
  sucesso: { rotulo: 'Sucesso', tom: 'sucesso' },
  atencao: { rotulo: 'Atenção', tom: 'atencao' },
  erro: { rotulo: 'Erro', tom: 'erro' },
}

/** Situação da conta (etapa 5a: teste, teste_expirado, ativa, atrasada, cancelada, cortesia); outras aparecem como vieram. */
const SITUACOES_CONTA: Record<string, { rotulo: string; tom: Tom }> = {
  teste: { rotulo: 'Em teste', tom: 'info' },
  teste_expirado: { rotulo: 'Teste encerrado', tom: 'atencao' },
  cortesia: { rotulo: 'Cortesia', tom: 'marca' },
  ativa: { rotulo: 'Ativa', tom: 'sucesso' },
  atrasada: { rotulo: 'Atrasada', tom: 'erro' },
  ativo: { rotulo: 'Ativa', tom: 'sucesso' },
  expirada: { rotulo: 'Teste encerrado', tom: 'atencao' },
  vencida: { rotulo: 'Vencida', tom: 'atencao' },
  suspensa: { rotulo: 'Suspensa', tom: 'erro' },
  bloqueada: { rotulo: 'Bloqueada', tom: 'erro' },
  cancelada: { rotulo: 'Cancelada', tom: 'neutro' },
}

export function situacaoConta(valor: string | null | undefined): { rotulo: string; tom: Tom } {
  if (!valor) return { rotulo: '—', tom: 'neutro' }
  return SITUACOES_CONTA[valor] ?? { rotulo: valor.charAt(0).toUpperCase() + valor.slice(1), tom: 'neutro' }
}

export function iniciais(nome: string | null | undefined): string {
  const partes = (nome ?? '').trim().split(/\s+/).filter(Boolean)
  if (!partes.length) return '?'
  const primeira = partes[0]!.charAt(0)
  const ultima = partes.length > 1 ? partes[partes.length - 1]!.charAt(0) : ''
  return (primeira + ultima).toUpperCase()
}

/** Situação de envio do contato, em português simples (a mesma na fila de envios e em Contatos). */
export const SITUACOES_CONTATO: Record<SituacaoContato, { rotulo: string; tom: Tom; descricao: string }> = {
  na_fila: { rotulo: 'Na fila', tom: 'info', descricao: 'Pode receber a pesquisa agora.' },
  enviando: { rotulo: 'Enviando...', tom: 'marca', descricao: 'A pesquisa está saindo neste momento.' },
  aguardando: { rotulo: 'Aguardando resposta', tom: 'atencao', descricao: 'Recebeu a pesquisa e ainda não respondeu.' },
  respondeu: { rotulo: 'Respondeu', tom: 'sucesso', descricao: 'Respondeu a última pesquisa.' },
  nao_saiu: { rotulo: 'Não saiu', tom: 'erro', descricao: 'A última pesquisa não conseguiu ser entregue.' },
  saiu_da_lista: { rotulo: 'Saiu da lista', tom: 'neutro', descricao: 'Pediu para não receber mais pesquisas.' },
  inativo: { rotulo: 'Inativo', tom: 'neutro', descricao: 'Contato desativado: não recebe pesquisas.' },
  aguardando_intervalo: { rotulo: 'Aguardando o próximo envio', tom: 'neutro', descricao: 'Já recebeu e volta para a fila na data do próximo envio.' },
}

/**
 * Rótulo e cor da situação. `aguardando_intervalo` mostra a data ("Próximo envio em 12/03") quando vier.
 * `nunca_enviado` (etapa 2) é tratado como "Na fila"; `enviando: true` vale mais que a situação.
 */
export function situacaoContato(
  v: string | null | undefined,
  extra: { proximo_envio?: string | null; enviando?: boolean } = {},
): { rotulo: string; tom: Tom } {
  if (extra.enviando) return SITUACOES_CONTATO.enviando
  const chave = (v === 'nunca_enviado' ? 'na_fila' : v) as SituacaoContato | null | undefined
  if (chave === 'aguardando_intervalo') {
    const data = formatarDiaMes(extra.proximo_envio, '')
    return { rotulo: data ? `Próximo envio em ${data}` : SITUACOES_CONTATO.aguardando_intervalo.rotulo, tom: 'neutro' }
  }
  return (chave && SITUACOES_CONTATO[chave]) || { rotulo: v || '—', tom: 'neutro' }
}

/** Cor de uma nota no estilo NPS: 0–6 vermelho, 7–8 amarelo, 9–10 verde. */
export function tomNotaNps(nota: number | null | undefined): Tom {
  if (typeof nota !== 'number') return 'neutro'
  return nota <= 6 ? 'erro' : nota <= 8 ? 'atencao' : 'sucesso'
}

/** Cor pelo grupo da resposta (quando a API manda o grupo). */
export function tomGrupo(grupo: string | null | undefined, nota?: number | null, tipo?: 'nps' | 'csat' | null): Tom {
  if (grupo === 'promotor' || grupo === 'satisfeito') return 'sucesso'
  if (grupo === 'neutro') return 'atencao'
  if (grupo === 'detrator' || grupo === 'insatisfeito') return 'erro'
  if (tipo === 'csat' && typeof nota === 'number') return nota <= 2 ? 'erro' : nota === 3 ? 'atencao' : 'sucesso'
  return tomNotaNps(nota)
}

export const GRUPOS_NOTA: Record<string, string> = {
  promotor: 'Promotor',
  neutro: 'Neutro',
  detrator: 'Detrator',
  satisfeito: 'Satisfeito',
  insatisfeito: 'Insatisfeito',
}

export const CANAIS: Record<CanalResposta, string> = {
  email: 'E-mail',
  whatsapp: 'WhatsApp',
  link: 'Link',
  qr: 'QR Code',
  widget: 'Widget no site',
  api: 'Integração',
  importacao: 'Importação',
  manual: 'Manual',
  telefone: 'Telefone',
  reuniao: 'Reunião',
}

export const TIPOS_FORMULARIO: Record<TipoFormulario, { rotulo: string; tom: Tom }> = {
  nps: { rotulo: 'NPS', tom: 'marca' },
  csat: { rotulo: 'CSAT', tom: 'info' },
  personalizado: { rotulo: 'Personalizado', tom: 'neutro' },
}

// ── Etapa 3b ────────────────────────────────────────────────────────────────

/** Canal das pesquisas (Configurações de envio), com a explicação em português simples. */
export const CANAIS_CONFIG: Record<CanalConfig, { rotulo: string; descricao: string; recomendado?: boolean }> = {
  email: {
    rotulo: 'Só e-mail',
    descricao: 'A pesquisa vai para o e-mail do cliente. Quem não tem e-mail cadastrado fica de fora.',
  },
  whatsapp: {
    rotulo: 'WhatsApp',
    descricao: 'A pesquisa chega no WhatsApp do cliente, sem ninguém precisar apertar Enviar. Quem não tem telefone recebe por e-mail.',
  },
  whatsapp_e_email: {
    rotulo: 'WhatsApp com e-mail de reserva',
    descricao: 'Tenta primeiro pelo WhatsApp. Se a mensagem não sair ou o cliente não tiver telefone, vai por e-mail.',
    recomendado: true,
  },
}

/** Eventos dos avisos para outros sistemas (webhooks). */
export const EVENTOS_WEBHOOK: Record<EventoWebhook, { rotulo: string; descricao: string }> = {
  'resposta.criada': { rotulo: 'Nova resposta', descricao: 'Quando um cliente responde uma pesquisa.' },
  // O cliente mudou a resposta (docs/api-editar-resposta.md)
  'resposta.atualizada': {
    rotulo: 'Cliente mudou a resposta',
    descricao: 'Quando um cliente muda a resposta (nos formulários em que isso está ligado).',
  },
  'contato.descadastrado': { rotulo: 'Cliente saiu da lista', descricao: 'Quando alguém pede para não receber mais pesquisas.' },
  // Etapa 5c
  'indicacao.criada': { rotulo: 'Nova indicação', descricao: 'Quando chega uma indicação nova, feita pela pesquisa ou registrada pela equipe.' },
  'indicacao.atualizada': {
    rotulo: 'Indicação mudou de situação',
    descricao: 'Quando a equipe marca uma indicação como em contato, virou cliente ou não avançou.',
  },
  // Desfecho (etapa 5i)
  'empresa.perdida': { rotulo: 'Empresa perdida', descricao: 'Quando a equipe marca uma empresa como perdida (com o motivo).' },
  'empresa.reativada': { rotulo: 'Empresa voltou a ser cliente', descricao: 'Quando uma empresa perdida volta a ser cliente.' },
}

export function rotuloEventoWebhook(v: string | null | undefined): string {
  return (v && EVENTOS_WEBHOOK[v as EventoWebhook]?.rotulo) || v || '—'
}

/**
 * Nome do evento na Auditoria: o `rotulo` que vem pronto da API; quando o detalhe diz que veio do cadastro
 * (`origem: "cadastro"`, ex.: `termos_aceitos`), acrescenta " no cadastro". Ver docs/api-aceite-lgpd.md §3.
 */
export function rotuloEventoAuditoria(item: Pick<ItemAuditoria, 'evento' | 'rotulo' | 'detalhe'>): string {
  const nome = item.rotulo || item.evento
  const origem = item.detalhe && typeof item.detalhe === 'object' ? (item.detalhe as Record<string, unknown>).origem : null
  return origem === 'cadastro' ? `${nome} no cadastro` : nome
}

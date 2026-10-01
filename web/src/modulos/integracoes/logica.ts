// Regras puras da tela de Integrações (sem Vue): franquia do WhatsApp, exemplos prontos,
// segredo mostrado uma vez, canais disponíveis e paginação das entregas.
import type {
  CanalConfig,
  EntregaWebhook,
  FranquiaWhatsapp,
  Pagina,
  Webhook,
  WhatsappIntegracao,
} from '@/api/tipos'
import { formatarMoeda, formatarNumero } from '@/utils/formatos'
import type { Tom } from '@/utils/rotulos'

// ── Franquia do WhatsApp ─────────────────────────────────────────────────────

/** A partir de quanto da franquia usada o aviso muda de cor (mesmo limiar do e-mail aos admins). */
export const LIMIAR_AVISO_FRANQUIA = 0.8

export type NivelFranquia = 'ok' | 'atencao' | 'esgotada'

export interface EstadoFranquia {
  usadas: number
  limite: number
  restantes: number
  /** 0–100, para a barra. Só chega a 100 quando acabou de verdade. */
  percentual: number
  nivel: NivelFranquia
  tom: Tom
  /** "32 de 90 no mês". */
  resumo: string
}

export function estadoFranquia(f: Pick<FranquiaWhatsapp, 'limite' | 'usadas_mes'> | null | undefined): EstadoFranquia {
  const limite = Math.max(0, Math.floor(Number(f?.limite) || 0))
  const usadas = Math.max(0, Math.floor(Number(f?.usadas_mes) || 0))
  const fracao = limite > 0 ? usadas / limite : 1
  const nivel: NivelFranquia = fracao >= 1 ? 'esgotada' : fracao >= LIMIAR_AVISO_FRANQUIA ? 'atencao' : 'ok'
  // Arredonda para baixo: 199 de 200 mostra 99%, nunca "100%" sem ter acabado.
  const percentual = nivel === 'esgotada' ? 100 : Math.min(99, Math.floor(fracao * 100))
  return {
    usadas,
    limite,
    restantes: Math.max(0, limite - usadas),
    percentual,
    nivel,
    tom: nivel === 'esgotada' ? 'erro' : nivel === 'atencao' ? 'atencao' : 'sucesso',
    resumo: `${formatarNumero(usadas)} de ${formatarNumero(limite)} no mês`,
  }
}

/** Explicação da franquia em português simples, conforme o estado e o excedente. */
export function explicacaoFranquia(f: FranquiaWhatsapp): string {
  const e = estadoFranquia(f)
  const valor = formatarMoeda(f.valor_excedente ?? 1.5)
  if (e.nivel === 'esgotada') {
    return f.excedente_ativo
      ? `A franquia deste mês acabou. Como as mensagens extras estão liberadas, as pesquisas continuam saindo pelo WhatsApp e cada uma custa ${valor}` +
          (f.excedentes_mes ? ` (${formatarNumero(f.excedentes_mes)} ${f.excedentes_mes === 1 ? 'extra' : 'extras'} até agora).` : '.')
      : 'A franquia deste mês acabou. Até o mês virar, as pesquisas vão por e-mail para quem tem e-mail cadastrado.'
  }
  const restam = `${formatarNumero(e.restantes)} ${e.restantes === 1 ? 'mensagem' : 'mensagens'}`
  if (e.nivel === 'atencao') return `Restam ${restam} neste mês. Quando acabar, as pesquisas passam a ir por e-mail.`
  return `Restam ${restam} neste mês. A contagem recomeça no dia 1º.`
}

// ── Exemplos prontos (para quem cuida do sistema da empresa) ─────────────────

/** O que aparece no lugar da chave nos exemplos (ela só é mostrada uma vez). */
export const CHAVE_EXEMPLO = 'COLE_SUA_CHAVE_AQUI'

/** Corpo realista para "o pedido foi entregue, pesquise este cliente". */
export const EXEMPLO_PESQUISA = {
  nome: 'Maria Silva',
  email: 'maria@mercadobompreco.com.br',
  telefone: '11912345678',
  empresa: { nome: 'Mercado Bom Preço', documento: '12.345.678/0001-90' },
  evento: 'pedido_entregue',
  referencia: 'Pedido 48213',
  contexto: {
    pedido: '48213',
    nota_fiscal: '000123456',
    rota: 'Rota 12 - Zona Norte',
    motorista: 'Carlos Souza',
    filial: 'Campinas',
  },
  id_evento: 'pedido-48213-entregue',
} as const

/** Junta a base da API com o caminho, sem barra dobrada. */
export function urlApi(base: string, caminho: string): string {
  return `${base.replace(/\/+$/, '')}/${caminho.replace(/^\/+/, '')}`
}

/** Protege um texto para ir entre aspas simples no shell (o ' vira '\''). */
export function aspasShell(texto: string): string {
  return `'${texto.replace(/'/g, `'\\''`)}'`
}

/** cURL de POST /integracao/pesquisas com a chave no cabeçalho e o corpo em JSON. */
export function exemploCurl(base: string, chave: string = CHAVE_EXEMPLO, corpo: unknown = EXEMPLO_PESQUISA): string {
  return [
    `curl -X POST "${urlApi(base, '/integracao/pesquisas')}" \\`,
    `  -H "X-Api-Key: ${chave}" \\`,
    `  -H "Content-Type: application/json" \\`,
    `  -d ${aspasShell(JSON.stringify(corpo, null, 2))}`,
  ].join('\n')
}

/** cURL de GET /integracao/teste: confere se a chave funciona. */
export function exemploCurlTeste(base: string, chave: string = CHAVE_EXEMPLO): string {
  return [`curl "${urlApi(base, '/integracao/teste')}" \\`, `  -H "X-Api-Key: ${chave}"`].join('\n')
}

/** Campos aceitos em POST /integracao/pesquisas, para a tabela da tela. */
export const CAMPOS_PESQUISA: { campo: string; exemplo: string; descricao: string }[] = [
  { campo: 'email', exemplo: 'maria@cliente.com.br', descricao: 'E-mail do cliente. Precisa de e-mail ou telefone.' },
  { campo: 'telefone', exemplo: '11912345678', descricao: 'Celular com DDD (para o WhatsApp). Precisa de e-mail ou telefone.' },
  { campo: 'nome', exemplo: 'Maria Silva', descricao: 'Nome do cliente (até 120 letras).' },
  { campo: 'codigo_externo', exemplo: 'CLI-0042', descricao: 'Código do cliente no seu sistema. Ajuda a achar o contato certo.' },
  { campo: 'empresa', exemplo: '{"nome": "...", "documento": "...", "codigo_externo": "..."}', descricao: 'Empresa do cliente. Se não existir, é criada.' },
  { campo: 'evento', exemplo: 'pedido_entregue', descricao: 'O que aconteceu (até 60 letras).' },
  { campo: 'referencia', exemplo: 'Pedido 48213', descricao: 'Número do pedido ou atendimento (até 120 letras). Aparece na mensagem.' },
  { campo: 'contexto', exemplo: '{"pedido", "nota_fiscal", "rota", "motorista", "filial", "transportadora"}', descricao: 'Detalhes da entrega, para os relatórios por motorista, rota e filial.' },
  { campo: 'tipo', exemplo: 'nps ou csat', descricao: 'Qual pesquisa usar. Padrão: csat quando há referência, senão nps.' },
  { campo: 'formulario_id', exemplo: '12', descricao: 'Um formulário específico, no lugar do padrão.' },
  { campo: 'canal', exemplo: 'auto, email, whatsapp ou link', descricao: 'Por onde enviar. "auto" escolhe sozinho; "link" só devolve o link da pesquisa.' },
  { campo: 'enviar', exemplo: 'true', descricao: 'Use false para só gerar o link, sem enviar.' },
  { campo: 'ignorar_descanso', exemplo: 'false', descricao: 'Envia mesmo se o cliente recebeu outra pesquisa há pouco tempo.' },
  { campo: 'id_evento', exemplo: 'pedido-48213-entregue', descricao: 'Identificador único do aviso. Repetido em até 24 h, não envia de novo.' },
]

// ── Segredo mostrado uma vez (chave e segredo dos webhooks) ──────────────────

export interface EstadoSegredo {
  valor: string | null
  /** A pessoa confirmou que guardou. Só então a janela fecha. */
  guardado: boolean
}

export const segredoVazio = (): EstadoSegredo => ({ valor: null, guardado: false })

export function mostrarSegredo(valor: string): EstadoSegredo {
  return { valor, guardado: false }
}

export function confirmarGuardado(e: EstadoSegredo, guardado = true): EstadoSegredo {
  return { ...e, guardado }
}

export function podeFecharSegredo(e: EstadoSegredo): boolean {
  return !e.valor || e.guardado
}

/** Fecha e apaga o valor da memória da tela; se ainda não confirmou, continua aberto. */
export function fecharSegredo(e: EstadoSegredo): EstadoSegredo {
  return podeFecharSegredo(e) ? segredoVazio() : e
}

/** "tq_live_ab12…" (garante as reticências no fim do prefixo). */
export function prefixoMascarado(prefixo: string | null | undefined): string {
  if (!prefixo) return '—'
  const limpo = prefixo.replace(/(…|\.\.\.)+$/, '')
  return `${limpo}…`
}

// ── Canais de envio (Configurações de envio) ─────────────────────────────────

export interface DisponibilidadeCanal {
  disponivel: boolean
  motivo: string | null
}

export function canalUsaWhatsapp(canal: CanalConfig | null | undefined): boolean {
  return canal === 'whatsapp' || canal === 'whatsapp_e_email'
}

/**
 * O que dá para escolher: e-mail sempre; WhatsApp só com o WhatsApp automático conectado.
 * `wa` null = não deu para consultar (fica indisponível, com o motivo).
 */
export function disponibilidadeCanais(wa: Pick<WhatsappIntegracao, 'conectado'> | null | undefined): Record<CanalConfig, DisponibilidadeCanal> {
  const whats: DisponibilidadeCanal = !wa
    ? { disponivel: false, motivo: 'Não conseguimos verificar o WhatsApp agora.' }
    : wa.conectado
      ? { disponivel: true, motivo: null }
      : { disponivel: false, motivo: 'Conecte o WhatsApp automático em Integrações para usar.' }
  return {
    email: { disponivel: true, motivo: null },
    whatsapp: whats,
    whatsapp_e_email: { ...whats },
  }
}

/** Aviso para o canal já escolhido quando o WhatsApp não está em condições de enviar. */
export function avisoCanal(
  canal: CanalConfig | null | undefined,
  wa: Pick<WhatsappIntegracao, 'conectado' | 'ativo' | 'franquia'> | null | undefined,
): string | null {
  if (!canalUsaWhatsapp(canal) || !wa) return null
  if (!wa.conectado) return 'O WhatsApp automático não está conectado. Enquanto isso, as pesquisas vão por e-mail.'
  if (!wa.ativo) return 'O WhatsApp automático está desligado em Integrações. Enquanto isso, as pesquisas vão por e-mail.'
  if (estadoFranquia(wa.franquia).nivel === 'esgotada' && !wa.franquia.excedente_ativo) {
    return 'A franquia de WhatsApp deste mês acabou. Até o mês virar, as pesquisas vão por e-mail.'
  }
  return null
}

// ── Webhooks ─────────────────────────────────────────────────────────────────

/** Falhas seguidas que desligam o webhook (regra da API). */
export const FALHAS_PARA_DESATIVAR = 10

/** Checagem rápida do endereço antes de enviar (a API confere de novo, inclusive o DNS). */
export function validarUrlWebhook(url: string): string | null {
  const t = url.trim()
  if (!t) return 'Informe o endereço que vai receber os avisos.'
  let u: URL
  try {
    u = new URL(t)
  } catch {
    return 'Confira o endereço. Ele deve ser parecido com https://seusistema.com.br/toqqi.'
  }
  if (u.protocol !== 'https:') return 'Use um endereço seguro, que comece com https://.'
  const host = u.hostname.toLowerCase().replace(/^\[|\]$/g, '')
  const privado =
    host === 'localhost' ||
    host.endsWith('.localhost') ||
    host.endsWith('.local') ||
    /^(127|10|0)\./.test(host) ||
    /^192\.168\./.test(host) ||
    /^169\.254\./.test(host) ||
    /^172\.(1[6-9]|2\d|3[01])\./.test(host) ||
    host === '::1' ||
    /^f[cd][0-9a-f]{2}:/.test(host) ||
    /^fe80:/.test(host)
  if (privado) return 'Use um endereço público da internet. Endereços internos da sua rede não são aceitos.'
  return null
}

export function situacaoWebhook(w: Pick<Webhook, 'ativo' | 'ultima_entrega' | 'falhas_seguidas'>): { rotulo: string; tom: Tom } {
  if (!w.ativo) {
    return w.falhas_seguidas >= FALHAS_PARA_DESATIVAR ? { rotulo: 'Desligado por falhas', tom: 'erro' } : { rotulo: 'Desligado', tom: 'neutro' }
  }
  if (!w.ultima_entrega) return { rotulo: 'Sem avisos ainda', tom: 'neutro' }
  return w.ultima_entrega.ok ? { rotulo: 'Funcionando', tom: 'sucesso' } : { rotulo: 'Com falha', tom: 'erro' }
}

/** Página mínima para considerar que pode haver mais entregas quando a API manda só a lista. */
export const PAGINA_MINIMA_ENTREGAS = 20

/**
 * Normaliza a resposta de GET /entregas (lista simples, como no contrato, ou paginada).
 * Na lista simples, há mais se esta página veio "cheia" (do tamanho da primeira).
 */
export function lerPaginaEntregas(
  r: EntregaWebhook[] | Pagina<EntregaWebhook> | null | undefined,
  pagina: number,
  tamanhoPrimeira: number,
): { itens: EntregaWebhook[]; temMais: boolean; tamanho: number } {
  if (!r) return { itens: [], temMais: false, tamanho: tamanhoPrimeira }
  if (Array.isArray(r)) {
    const tamanho = pagina === 1 ? r.length : tamanhoPrimeira
    const temMais = r.length > 0 && r.length >= Math.max(tamanho, PAGINA_MINIMA_ENTREGAS)
    return { itens: r, temMais, tamanho }
  }
  const itens = r.itens ?? []
  return { itens, temMais: pagina * (r.por_pagina || itens.length || 1) < (r.total ?? 0), tamanho: r.por_pagina || itens.length }
}

// ── Modelo de mensagem do WhatsApp (criado pelo cliente no WhatsApp Manager) ─

export function modeloSugerido(enderecoApp: string) {
  const base = enderecoApp.replace(/\/+$/, '')
  return {
    nome: 'pesquisa_satisfacao',
    categoria: 'Utilidade',
    idioma: 'Português (BR) — pt_BR',
    corpo:
      'Olá, {{1}}! Aqui é da {{2}}.\n\nQueremos saber como foi {{3}}. Sua opinião leva menos de 1 minuto e ajuda a gente a melhorar.\n\nToque no botão abaixo para responder.',
    rodape: 'Para não receber mais pesquisas, responda SAIR.',
    botaoTexto: 'Responder pesquisa',
    botaoUrl: `${base}/r/{{1}}`,
    exemplos: { '{{1}}': 'Maria', '{{2}}': 'nome da sua empresa', '{{3}}': 'seu pedido 48213' },
  }
}

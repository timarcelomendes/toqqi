// Detalhe de cada registro em Auditoria › Atividades (regras puras, sem Vue). Os eventos da etapa 5f
// (docs/api-etapa-5f.md §2 a §6) ganham rótulos e valores em português: contagens com milhar, datas, tamanho do
// arquivo, o começo das chaves. Os outros eventos, e as chaves que a tela não conhece (ou que vierem num formato
// inesperado), seguem como sempre: a chave com espaços no lugar de "_" e o valor como veio (objetos em JSON).
import type { ItemAuditoria } from '@/api/tipos'
import { formatarData } from '@/utils/datas'
import { formatarNumero, formatarTamanho, plural } from '@/utils/formatos'
import { juntar, ROTULOS_OPCAO } from '@/modulos/configuracoes/dadosConta'
import { prefixoMascarado } from '@/modulos/integracoes/logica'

export interface CampoDetalhe {
  rotulo: string
  valor: string
  /** Sem formatação própria: o rótulo é a chave crua (a tela põe as iniciais em maiúscula, como sempre fez). */
  generico?: boolean
  /** Código (o começo de uma chave): a tela mostra em fonte de largura fixa. */
  codigo?: boolean
}

type Detalhe = Record<string, unknown>
/** `undefined`: formato inesperado (a chave vai para o genérico); `null`: tratada, sem nada a mostrar. */
type Formato = (valor: unknown) => CampoDetalhe | CampoDetalhe[] | null | undefined

/** O texto do detalhe, quando a API mandou texto em vez de objeto. */
export function textoDetalhe(d: ItemAuditoria['detalhe']): string | null {
  if (d === null || d === undefined || d === '') return null
  return typeof d === 'string' ? d : null
}

/** O jeito de sempre: "prefixo anterior" → o valor cru (objetos em JSON). */
function generico(chave: string, valor: unknown): CampoDetalhe {
  return { rotulo: chave.replace(/_/g, ' '), valor: typeof valor === 'object' ? JSON.stringify(valor) : String(valor), generico: true }
}

const ehNumero = (v: unknown): v is number => typeof v === 'number' && Number.isFinite(v) && v >= 0
const ehObjeto = (v: unknown): v is Detalhe => !!v && typeof v === 'object' && !Array.isArray(v)
const comMaiuscula = (s: string) => s.charAt(0).toLocaleUpperCase('pt-BR') + s.slice(1)
/** O valor da tabela para a chave, só se for dela ("constructor" e afins não contam). */
const daTabela = <T>(tabela: Record<string, T>, chave: string): T | undefined => (Object.hasOwn(tabela, chave) ? tabela[chave] : undefined)

/** As contagens de um objeto {chave: número}; outro formato → null. */
function contagens(v: unknown): Record<string, number> | null {
  if (!ehObjeto(v)) return null
  return Object.values(v).every(ehNumero) ? (v as Record<string, number>) : null
}

/** "1.234 contatos, 5.678 respostas e 1 oferta": na ordem da lista, só o que passa de zero; chaves novas no fim. */
function listaContagens(valores: Record<string, number>, nomes: readonly (readonly [string, string, string])[]): string[] {
  const conhecidas = new Set(nomes.map(([chave]) => chave))
  const partes = nomes.filter(([chave]) => (valores[chave] ?? 0) > 0).map(([chave, um, varios]) => plural(valores[chave]!, um, varios))
  for (const [chave, n] of Object.entries(valores)) {
    if (!conhecidas.has(chave) && n > 0) partes.push(`${formatarNumero(n)} ${chave.replace(/_/g, ' ')}`)
  }
  return partes
}

// ── Zona de risco: {opcao, apagados, mantidos} ──────────────────────────────

/** O que a zona de risco apaga, na ordem da tela de Dados da conta. */
const APAGADOS = [
  ['empresas', 'empresa', 'empresas'],
  ['contatos', 'contato', 'contatos'],
  ['respostas', 'resposta', 'respostas'],
  ['convites', 'convite', 'convites'],
  ['envios', 'envio', 'envios'],
  ['acoes', 'plano de ação', 'planos de ação'],
  ['indicacoes', 'indicação', 'indicações'],
  ['ofertas', 'oferta', 'ofertas'],
] as const
/** Contagens que não são apagadas: perdem o vínculo (ações sem a resposta, CSAT sem o contato). */
const DESLIGADOS = {
  acoes_sem_vinculo: { rotulo: 'Sem vínculo', um: 'plano de ação', varios: 'planos de ação' },
  csat_sem_contato: { rotulo: 'Sem contato', um: 'resposta CSAT', varios: 'respostas CSAT' },
} as const
const MANTIDOS = [
  ['usuarios', 'usuário', 'usuários'],
  ['formularios', 'formulário', 'formulários'],
  ['csat', 'resposta CSAT', 'respostas CSAT'],
  ['descadastros', 'na lista de descadastro', 'na lista de descadastro'],
] as const

const zonaRisco: Record<string, Formato> = {
  opcao: (v) => (typeof v === 'string' && v ? { rotulo: 'Opção', valor: daTabela<{ rotulo: string }>(ROTULOS_OPCAO, v)?.rotulo ?? v } : undefined),
  apagados: (v) => {
    const c = contagens(v)
    if (!c) return undefined
    const apagados: Record<string, number> = {}
    for (const [chave, n] of Object.entries(c)) if (!Object.hasOwn(DESLIGADOS, chave)) apagados[chave] = n
    const lista = listaContagens(apagados, APAGADOS)
    const campos: CampoDetalhe[] = [{ rotulo: 'Apagados', valor: lista.length ? juntar(lista) : 'Nada (não havia o que apagar)' }]
    for (const [chave, d] of Object.entries(DESLIGADOS)) {
      const n = c[chave] ?? 0
      if (n > 0) campos.push({ rotulo: d.rotulo, valor: plural(n, d.um, d.varios) })
    }
    return campos
  },
  mantidos: (v) => {
    const c = contagens(v)
    if (!c) return undefined
    const lista = listaContagens(c, MANTIDOS)
    return lista.length ? { rotulo: 'Mantidos', valor: juntar(lista) } : null
  },
}

// ── Exportações ─────────────────────────────────────────────────────────────

/** {arquivos, linhas: {arquivo: n}, bytes}: quantos arquivos, o total de linhas das planilhas e o tamanho do .zip. */
const exportacaoConta: Record<string, Formato> = {
  arquivos: (v) => (ehNumero(v) ? { rotulo: 'Arquivos', valor: formatarNumero(v) } : undefined),
  linhas: (v) => {
    if (ehNumero(v)) return { rotulo: 'Linhas', valor: formatarNumero(v) }
    const c = contagens(v)
    if (!c) return undefined
    const total = Object.values(c).reduce((a, n) => a + n, 0)
    return { rotulo: 'Linhas', valor: `${formatarNumero(total)}, somando todas as planilhas` }
  },
  bytes: (v) => (ehNumero(v) ? { rotulo: 'Tamanho', valor: formatarTamanho(v) } : undefined),
}

const LISTAS: Record<string, string> = { contatos: 'Contatos', empresas: 'Empresas' }

/** {lista, linhas}: "Exportar CSV" em Contatos ou Empresas. */
const exportacaoCsv: Record<string, Formato> = {
  lista: (v) => (typeof v === 'string' && v ? { rotulo: 'Lista', valor: daTabela(LISTAS, v) ?? v } : undefined),
  linhas: (v) => (ehNumero(v) ? { rotulo: 'Linhas', valor: formatarNumero(v) } : undefined),
}

// ── Envio automático e lembretes: {agendados|enviados, ignorados, executado_agora} ──

interface Automacao {
  /** A chave da contagem (`agendados` no envio automático, `enviados` nos lembretes) e como ela aparece. */
  chave: string
  rotulo: string
  saiu: [string, string, string]
  /** Quem ficou de fora (`ignorados`), no singular e no plural. */
  fora: [string, string]
  /** O item do menu de Envios que roda na hora (`executado_agora`). */
  botao: string
}

function automacao(a: Automacao): Record<string, Formato> {
  const [um, varios, nenhum] = a.saiu
  return {
    [a.chave]: (v) => (ehNumero(v) ? { rotulo: a.rotulo, valor: v ? plural(v, um, varios) : nenhum } : undefined),
    ignorados: (v) => {
      if (!ehNumero(v)) return undefined
      return v ? { rotulo: 'Ficaram de fora', valor: `${plural(v, a.fora[0], a.fora[1])}, pelas regras de envio` } : null
    },
    executado_agora: (v) =>
      typeof v === 'boolean' ? { rotulo: 'Disparo', valor: v ? `Na hora, pelo “${a.botao}”` : 'Sozinho, no horário de envio' } : undefined,
  }
}

// ── Integrações: chave e webhooks ───────────────────────────────────────────

const prefixo = (rotulo: string): Formato => (v) =>
  typeof v === 'string' && v ? { rotulo, valor: prefixoMascarado(v), codigo: true } : undefined

const endereco: Formato = (v) => (typeof v === 'string' && v ? { rotulo: 'Endereço', valor: v } : undefined)
const numeroWebhook: Formato = (v) =>
  (typeof v === 'number' && Number.isFinite(v)) || (typeof v === 'string' && v) ? { rotulo: 'Webhook', valor: `nº ${v}` } : undefined

/** O que mudou num webhook (as chaves de PATCH /integracoes/webhooks/{id}; "segredo" = gerou um novo). */
const CAMPOS_WEBHOOK: Record<string, string> = {
  url: 'endereço',
  eventos: 'eventos',
  ativo: 'situação (ligado ou desligado)',
  segredo: 'segredo (um novo foi gerado)',
}

const camposWebhook: Formato = (v) => {
  if (!Array.isArray(v) || !v.length || !v.every((c) => typeof c === 'string')) return undefined
  const ordem = Object.keys(CAMPOS_WEBHOOK)
  const nomes = [...(v as string[])]
    .sort((a, b) => (ordem.indexOf(a) + 1 || ordem.length + 1) - (ordem.indexOf(b) + 1 || ordem.length + 1))
    .map((c) => daTabela(CAMPOS_WEBHOOK, c) ?? c.replace(/_/g, ' '))
  return { rotulo: 'O que mudou', valor: comMaiuscula(juntar(nomes)) }
}

// ── Exclusão automática: {exclusao_em, encerrada_em, admins} ────────────────

const data = (rotulo: string): Formato => (v) => {
  const texto = typeof v === 'string' ? formatarData(v, '') : ''
  return texto ? { rotulo, valor: texto } : undefined
}

/** Cada evento com formato próprio: as chaves na ordem em que aparecem (as outras vão para o genérico, depois). */
const FORMATOS: Record<string, Record<string, Formato>> = {
  zona_risco: zonaRisco,
  exportacao_conta: exportacaoConta,
  exportacao_csv: exportacaoCsv,
  envio_automatico: automacao({
    chave: 'agendados',
    rotulo: 'Enviadas',
    saiu: ['pesquisa', 'pesquisas', 'Nenhuma pesquisa'],
    fora: ['contato', 'contatos'],
    botao: 'Rodar envio automático agora',
  }),
  lembretes_automaticos: automacao({
    chave: 'enviados',
    rotulo: 'Enviados',
    saiu: ['lembrete', 'lembretes', 'Nenhum lembrete'],
    fora: ['lembrete', 'lembretes'],
    botao: 'Enviar lembretes agora',
  }),
  chave_gerada: { prefixo: prefixo('Chave') },
  chave_regerada: { prefixo: prefixo('Chave nova'), prefixo_anterior: prefixo('Chave anterior') },
  // Ao criar, `campos` é sempre endereço e eventos: não diz nada além do próprio evento.
  webhook_criado: { url: endereco, webhook_id: numeroWebhook, campos: (v) => (Array.isArray(v) ? null : undefined) },
  webhook_alterado: { webhook_id: numeroWebhook, campos: camposWebhook },
  webhook_excluido: { url: endereco, webhook_id: numeroWebhook },
  webhook_desativado: { url: endereco, webhook_id: numeroWebhook },
  exclusao_avisada: {
    exclusao_em: data('Exclusão em'),
    encerrada_em: data('Encerrada em'),
    admins: (v) => (ehNumero(v) ? { rotulo: 'Avisados', valor: v ? `${plural(v, 'administrador', 'administradores')}, por e-mail` : 'Nenhum administrador ativo' } : undefined),
  },
}

/** As linhas do detalhe de um registro (sem o grupo, o evento e o IP, que a tela acrescenta). */
export function camposDetalhe(item: Pick<ItemAuditoria, 'evento' | 'detalhe'>): CampoDetalhe[] {
  const d = item.detalhe
  if (!d || typeof d !== 'object') return []
  const detalhe = d as Detalhe
  const formatos = daTabela(FORMATOS, item.evento) ?? {}
  const campos: CampoDetalhe[] = []
  const tratadas = new Set<string>()
  for (const [chave, formatar] of Object.entries(formatos)) {
    if (!Object.hasOwn(detalhe, chave)) continue
    const r = formatar(detalhe[chave])
    if (r === undefined) continue
    tratadas.add(chave)
    if (r) campos.push(...(Array.isArray(r) ? r : [r]))
  }
  for (const [chave, valor] of Object.entries(detalhe)) if (!tratadas.has(chave)) campos.push(generico(chave, valor))
  return campos
}

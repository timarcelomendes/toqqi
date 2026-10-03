// Regras puras de Configurações › Dados da conta (etapa 5f, docs/api-etapa-5f.md §2, §3 e §10), sem Vue: os textos das
// opções da Zona de risco com as contagens (plurais e milhar em pt-BR), o que sempre fica, a confirmação APAGAR, o
// resumo do que foi apagado, as mensagens de erro e o aviso do topo quando a conta encerrada tem dia para ser excluída.
import { ApiError } from '@/api/erros'
import type { ContagemZonaContatos, ContagemZonaTudo, MantidosZonaRisco, OpcaoZonaRisco, ZonaRisco } from '@/api/tipos'
import { formatarData } from '@/utils/datas'
import { formatarNumero, plural } from '@/utils/formatos'

export const ROTA_DADOS_CONTA = '/configuracoes/dados-da-conta'

// ── Exportar todos os dados ─────────────────────────────────────────────────

export const TEXTO_EXPORTACAO = 'Um arquivo .zip com uma planilha (CSV) por assunto. Senhas e chaves não vão.'
export const TEXTO_GERANDO = 'Gerando o arquivo… pode levar até um minuto.'
export const TEXTO_EXPORTACAO_PRONTA = 'Pronto: o arquivo foi gerado. Confira os downloads do navegador.'

/** O andamento do .zip, na página e no diálogo da Zona de risco (as duas regiões são `aria-live`). */
export interface MensagemExportacao {
  tom: 'info' | 'erro' | 'sucesso'
  texto: string
}

/** Gerando → "Gerando o arquivo…"; erro → a mensagem; pronto → "Pronto: …"; senão nada. */
export function mensagemExportacao(estado: { baixando: boolean; erro: string | null; pronta: boolean }): MensagemExportacao | null {
  if (estado.baixando) return { tom: 'info', texto: TEXTO_GERANDO }
  if (estado.erro) return { tom: 'erro', texto: estado.erro }
  if (estado.pronta) return { tom: 'sucesso', texto: TEXTO_EXPORTACAO_PRONTA }
  return null
}

/**
 * Mensagem de um erro ao baixar o .zip: a da API (409 `exportacao_em_andamento`: "Já tem uma exportação sendo gerada
 * nesta conta. Aguarde terminar."). O 429 daqui é de 5 por hora: o texto padrão ("Aguarde um minuto") não serve.
 */
export function mensagemErroExportacao(e: unknown): string {
  if (e instanceof ApiError && e.status === 429) return 'Você chegou ao limite de 5 exportações por hora. Tente de novo mais tarde.'
  return e instanceof ApiError ? e.mensagem : 'Não deu para gerar o arquivo. Tente de novo em instantes.'
}

// ── Zona de risco ───────────────────────────────────────────────────────────

export const OPCOES_ZONA: readonly OpcaoZonaRisco[] = ['respostas', 'contatos', 'tudo']

/** Rótulo do rádio e o objeto do título do diálogo ("Apagar as respostas?"). */
export const ROTULOS_OPCAO: Record<OpcaoZonaRisco, { rotulo: string; titulo: string }> = {
  respostas: { rotulo: 'Respostas', titulo: 'Apagar as respostas?' },
  contatos: { rotulo: 'Contatos', titulo: 'Apagar os contatos?' },
  tudo: { rotulo: 'Recomeçar do zero', titulo: 'Apagar tudo?' },
}

/** Singular e plural de cada coisa apagada, na ordem em que aparecem nos textos. */
const ITENS: { chave: keyof ContagemZonaTudo; um: string; varios: string; curto: [string, string] }[] = [
  { chave: 'empresas', um: 'empresa', varios: 'empresas', curto: ['empresa', 'empresas'] },
  { chave: 'contatos', um: 'contato', varios: 'contatos', curto: ['contato', 'contatos'] },
  {
    chave: 'respostas',
    um: 'resposta NPS ou de formulário personalizado',
    varios: 'respostas NPS e de formulários personalizados',
    curto: ['resposta', 'respostas'],
  },
  { chave: 'convites', um: 'convite', varios: 'convites', curto: ['convite', 'convites'] },
  { chave: 'envios', um: 'envio', varios: 'envios', curto: ['envio', 'envios'] },
  { chave: 'acoes', um: 'plano de ação', varios: 'planos de ação', curto: ['plano de ação', 'planos de ação'] },
  { chave: 'indicacoes', um: 'indicação', varios: 'indicações', curto: ['indicação', 'indicações'] },
  { chave: 'ofertas', um: 'oferta', varios: 'ofertas', curto: ['oferta', 'ofertas'] },
]

/** Contagens que não são apagadas: ações que perdem o vínculo e CSAT que perdem o contato. */
const NAO_APAGADOS = new Set(['acoes_sem_vinculo', 'csat_sem_contato'])

/** "a", "a e b", "a, b e c". */
export function juntar(itens: readonly string[]): string {
  if (itens.length <= 1) return itens[0] ?? ''
  return `${itens.slice(0, -1).join(', ')} e ${itens[itens.length - 1]}`
}

/** Número seguro (a API manda inteiros; qualquer outra coisa conta como 0). */
function n(v: unknown): number {
  return typeof v === 'number' && Number.isFinite(v) && v > 0 ? Math.floor(v) : 0
}

/** As contagens da opção (cumulativas, como a API manda). */
export function contagensDaOpcao(zona: ZonaRisco, opcao: OpcaoZonaRisco): Record<string, number> {
  return { ...(zona.opcoes[opcao] as unknown as Record<string, number>) }
}

/** A opção apaga alguma coisa? (Sem nada para apagar, o botão "Apagar…" fica desligado.) */
export function apagaAlgo(contagens: Record<string, number> | null | undefined): boolean {
  if (!contagens) return false
  return Object.entries(contagens).some(([chave, v]) => !NAO_APAGADOS.has(chave) && n(v) > 0)
}

/** "1.234 respostas NPS e de formulários personalizados, 12 convites e 30 envios" (só o que é maior que zero). */
function listaApagados(contagens: Record<string, number>, curto = false): string {
  const partes = ITENS.filter((i) => n(contagens[i.chave]) > 0).map((i) => {
    const qtd = n(contagens[i.chave])
    return curto ? plural(qtd, i.curto[0], i.curto[1]) : plural(qtd, i.um, i.varios)
  })
  return juntar(partes)
}

/**
 * O que a opção apaga, com as contagens do GET (frases curtas, para o rádio e para o diálogo). Ex.: "Apaga 1.234
 * respostas NPS e de formulários personalizados, inclusive arquivadas. 56 planos de ação ficam sem o vínculo."
 */
export function textoOpcao(opcao: OpcaoZonaRisco, zona: ZonaRisco): string {
  if (opcao === 'respostas') {
    const r = zona.opcoes.respostas
    const qtd = n(r.respostas)
    const acoes = n(r.acoes_sem_vinculo)
    if (!qtd) return 'Não há respostas NPS nem de formulários personalizados para apagar.'
    const frases = [
      qtd === 1
        ? 'Apaga 1 resposta NPS ou de formulário personalizado, inclusive arquivada.'
        : `Apaga ${formatarNumero(qtd)} respostas NPS e de formulários personalizados, inclusive arquivadas.`,
    ]
    if (acoes) frases.push(`${plural(acoes, 'plano de ação fica', 'planos de ação ficam')} sem o vínculo.`)
    return frases.join(' ')
  }
  if (opcao === 'contatos') {
    const c: ContagemZonaContatos = zona.opcoes.contatos
    const contagens = c as unknown as Record<string, number>
    if (!apagaAlgo(contagens)) return 'Não há contatos nem respostas para apagar.'
    const frases = [`Apaga ${listaApagados(contagens)}, com o histórico de importações.`]
    const csat = n(c.csat_sem_contato)
    if (csat) frases.push(`${plural(csat, 'resposta CSAT fica', 'respostas CSAT ficam')}, sem o contato.`)
    frases.push('Planos de ação, indicações e ofertas ficam, sem o contato.')
    return frases.join(' ')
  }
  const t = zona.opcoes.tudo as unknown as Record<string, number>
  if (!apagaAlgo(t)) return 'Não há nada para apagar.'
  return [
    `Apaga ${listaApagados(t)}, com o histórico de importações.`,
    'As respostas CSAT ficam, sem o contato e sem a empresa. Responsáveis e cadastros (grupos, segmentos, perfis e cargos) também ficam.',
  ].join(' ')
}

/** "Sempre fica: usuários, configurações, formulários, 340 respostas CSAT e a lista de descadastro (12)." */
export function textoSempreFica(m: Partial<MantidosZonaRisco> | null | undefined): string {
  const csat = n(m?.csat)
  const itens = ['usuários', 'configurações', 'formulários']
  if (csat) itens.push(plural(csat, 'resposta CSAT', 'respostas CSAT'))
  itens.push(`a lista de descadastro (${formatarNumero(n(m?.descadastros))})`)
  return `Sempre fica: ${juntar(itens)}.`
}

export const PALAVRA_CONFIRMACAO = 'APAGAR'

/** A mesma regra da API: APAGAR sem espaços nas pontas, em qualquer caixa ("apagar", " Apagar "). */
export function confirmacaoValida(v: string | null | undefined): boolean {
  return (v ?? '').trim().toLocaleUpperCase('pt-BR') === PALAVRA_CONFIRMACAO
}

/** "Pronto: apagamos 300 empresas, 5.000 contatos e 50.000 respostas." (o resumo do POST, só o que foi apagado). */
export function textoResultado(apagados: Record<string, number> | null | undefined): string {
  const lista = apagados ? listaApagados(apagados, true) : ''
  return lista ? `Pronto: apagamos ${lista}.` : 'Pronto: não havia nada para apagar.'
}

/** Mensagem de erro do POST da Zona de risco (a da API; o 429 daqui é de 5 por hora). */
export function mensagemErroZona(e: unknown): string {
  if (e instanceof ApiError && e.status === 429) return 'Você chegou ao limite de 5 tentativas por hora. Tente de novo mais tarde.'
  return e instanceof ApiError ? e.mensagem : 'Não deu para apagar agora e nada foi apagado. Tente de novo em instantes.'
}

// ── Exclusão automática da conta encerrada (aviso do topo e Plataforma) ──────

export interface TextoAvisoExclusao {
  texto: string
  /** Administrador: "Baixar os dados" (Dados da conta) e "Escolher plano" (Assinatura); os outros só leem. */
  admin: boolean
}

/**
 * Aviso do topo com `cobranca.exclusao_em`: o administrador lê "Os dados desta conta serão excluídos em dd/mm/aaaa.
 * Baixe uma cópia ou assine um plano."; os outros, "… Fale com o administrador da conta.". Sem data válida, nada.
 */
export function textoAvisoExclusao(exclusaoEm: string | null | undefined, admin: boolean): TextoAvisoExclusao | null {
  const data = formatarData(exclusaoEm, '')
  if (!data) return null
  const inicio = `Os dados desta conta serão excluídos em ${data}.`
  return { texto: admin ? `${inicio} Baixe uma cópia ou assine um plano.` : `${inicio} Fale com o administrador da conta.`, admin }
}

/** Selo da Plataforma: "Exclusão em 15/01/2027" (null sem data). */
export function seloExclusao(exclusaoEm: string | null | undefined): string | null {
  const data = formatarData(exclusaoEm, '')
  return data ? `Exclusão em ${data}` : null
}

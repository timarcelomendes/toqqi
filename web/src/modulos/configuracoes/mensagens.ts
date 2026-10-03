// Regras puras das Configurações de envio: variáveis dos textos, inserção no cursor,
// prévia do e-mail e conferência antes de salvar. Sem Vue, para testar com facilidade.
import type { Agradecimentos, ConfigEnvios, TipoFormulario } from '@/api/tipos'
import type { Pergunta } from '@/pesquisa/tipos'
import { renderizarVariaveis } from '@/pesquisa/variaveis'
import { corDestaque, corTextoBotao, textoOuNulo, validarVisual } from './visualEmail'

export type ChaveVariavel = 'nome' | 'empresa' | 'empresa_cliente' | 'link' | 'nota' | 'motivo' | 'representante'

export interface VariavelMensagem {
  chave: ChaveVariavel
  texto: string
  rotulo: string
}

export const VARIAVEIS: Record<ChaveVariavel, VariavelMensagem> = {
  nome: { chave: 'nome', texto: '{nome}', rotulo: 'Primeiro nome do cliente' },
  empresa: { chave: 'empresa', texto: '{empresa}', rotulo: 'Nome da sua empresa' },
  empresa_cliente: { chave: 'empresa_cliente', texto: '{empresa_cliente}', rotulo: 'Empresa do cliente' },
  link: { chave: 'link', texto: '{link}', rotulo: 'Link da pesquisa' },
  nota: { chave: 'nota', texto: '{nota}', rotulo: 'Nota que o cliente deu' },
  motivo: { chave: 'motivo', texto: '{motivo}', rotulo: 'O que o cliente comentou (numa linha, até 200 caracteres)' },
  representante: { chave: 'representante', texto: '{representante}', rotulo: 'Primeiro nome de quem oferece (quem está usando o Toqqi)' },
}

/**
 * Quais variáveis cada texto aceita (o contrato: {link} só no WhatsApp; {nota} e {motivo}, da etapa 5e, só no
 * agradecimento).
 */
export const VARIAVEIS_EMAIL: VariavelMensagem[] = [VARIAVEIS.nome, VARIAVEIS.empresa, VARIAVEIS.empresa_cliente]
export const VARIAVEIS_WHATSAPP: VariavelMensagem[] = [...VARIAVEIS_EMAIL, VARIAVEIS.link]
export const VARIAVEIS_AGRADECIMENTO: VariavelMensagem[] = [VARIAVEIS.nome, VARIAVEIS.empresa, VARIAVEIS.nota, VARIAVEIS.motivo]
/** Etapa 5c (Configurações › Crescimento): o convite de indicação e a recompensa; a oferta pelo WhatsApp. */
export const VARIAVEIS_CONVITE_INDICACAO: VariavelMensagem[] = [VARIAVEIS.nome, VARIAVEIS.empresa]
export const VARIAVEIS_OFERTA: VariavelMensagem[] = [VARIAVEIS.nome, VARIAVEIS.empresa, VARIAVEIS.empresa_cliente, VARIAVEIS.representante]

export const LIMITE_ASSUNTO = 150
export const LIMITE_TEXTO = 2000
export const DIAS_LEMBRETES_PADRAO = [3, 7, 15]

/**
 * Insere `trecho` no lugar da seleção (ou do cursor) e devolve o texto novo e onde o cursor fica.
 * Sem posição conhecida, coloca no fim.
 */
export function inserirNoCursor(
  texto: string,
  trecho: string,
  inicio?: number | null,
  fim?: number | null,
): { texto: string; cursor: number } {
  const tam = texto.length
  const ini = Math.min(Math.max(inicio ?? tam, 0), tam)
  const fi = Math.min(Math.max(fim ?? ini, ini), tam)
  return { texto: texto.slice(0, ini) + trecho + texto.slice(fi), cursor: ini + trecho.length }
}

export interface ValoresExemplo {
  nome?: string | null
  empresa?: string | null
  empresa_cliente?: string | null
  link?: string | null
  nota?: string | number | null
  /** O comentário do cliente (o agradecimento usa numa linha, até 200 caracteres). */
  motivo?: string | null
}

/** {motivo} vai até 200 caracteres. */
export const LIMITE_MOTIVO = 200

/** {motivo}: o comentário do cliente numa linha (quebras e espaços seguidos viram um espaço), cortado em 200 caracteres. */
export function motivoEmUmaLinha(comentario: string | null | undefined): string {
  const linha = (comentario ?? '').replace(/\s+/g, ' ').trim()
  // Por caractere (não por unidade UTF-16), para não partir um emoji no meio.
  return Array.from(linha).slice(0, LIMITE_MOTIVO).join('').trimEnd()
}

/**
 * Troca as variáveis como a plataforma faz: {nome} é o primeiro nome e, se vazio, leva junto a
 * vírgula e o espaço antes ("Olá, {nome}!" → "Olá!"). Variáveis desconhecidas ficam como estão.
 */
export function renderizarMensagem(texto: string | null | undefined, v: ValoresExemplo = {}): string {
  if (!texto) return ''
  const nome = (v.nome ?? '').trim().split(/\s+/)[0] ?? ''
  let s = texto
  if (nome) s = s.replace(/\{nome\}/g, () => nome)
  else {
    s = s.replace(/^\s*\{nome\}\s*,?\s*(\S?)/, (_m, c: string) => c.toUpperCase())
    s = s.replace(/,?[ \t]*\{nome\}/g, '')
  }
  // Funções de troca: um "$" no texto do cliente (ex.: "R$ 10") não vira padrão de substituição.
  s = s
    .replace(/\{empresa_cliente\}/g, () => (v.empresa_cliente ?? '').trim())
    .replace(/\{empresa\}/g, () => (v.empresa ?? '').trim())
    .replace(/\{link\}/g, () => (v.link ?? '').trim())
    .replace(/\{nota\}/g, () => (v.nota === null || v.nota === undefined ? '' : String(v.nota).trim()))
    .replace(/\{motivo\}/g, () => motivoEmUmaLinha(v.motivo))
  return s
    .split('\n')
    .map((l) => l.replace(/[ \t]{2,}/g, ' ').replace(/ ([!?.,;:])/g, '$1').trimEnd())
    .join('\n')
    .trim()
}

/** Parágrafos do e-mail: separados por linha em branco (quebras simples ficam dentro do parágrafo). */
export function paragrafos(texto: string): string[] {
  return texto
    .split(/\n[ \t]*\n+/)
    .map((p) => p.trim())
    .filter(Boolean)
}

export type CorNota = 'vermelho' | 'amarelo' | 'verde'

/** NPS: 0–6 vermelho, 7–8 amarelo, 9–10 verde. */
export function corNotaNps(n: number): CorNota {
  return n <= 6 ? 'vermelho' : n <= 8 ? 'amarelo' : 'verde'
}

/** CSAT/estrelas (1–5): 1–2 vermelho, 3 amarelo, 4–5 verde. */
export function corNotaCsat(n: number): CorNota {
  return n <= 2 ? 'vermelho' : n === 3 ? 'amarelo' : 'verde'
}

type BotoesNota = { titulo: string; botoes: { nota: number; cor: CorNota }[]; rotuloMin: string; rotuloMax: string }
export type BlocoNota = ({ tipo: 'nps' } & BotoesNota) | ({ tipo: 'csat' } & BotoesNota) | { tipo: 'botao'; texto: string }

/** A pergunta principal do formulário (a que vira os botões de nota): o e-mail mostra o título dela acima dos botões
 *  e os rótulos dela nas pontas (sem rótulo, os padrões). */
export type PerguntaDoBloco = Pick<Pergunta, 'titulo' | 'rotulo_min' | 'rotulo_max'>

/** O bloco da nota como no e-mail de verdade (`bloco_da_nota` da API): título da pergunta com as variáveis do
 *  formulário, botões 0–10 (NPS) ou 1–5 (CSAT/estrelas) com os rótulos, ou o botão "Responder pesquisa". */
export function blocoNota(
  tipo: TipoFormulario | null | undefined,
  pergunta: PerguntaDoBloco | null = null,
  valores: ValoresExemplo = {},
): BlocoNota {
  if (tipo === 'personalizado') return { tipo: 'botao', texto: 'Responder pesquisa' }
  const titulo = renderizarVariaveis(pergunta?.titulo ?? '', { empresa: valores.empresa ?? '', nome: valores.nome ?? '' })
  if (tipo === 'csat')
    return {
      tipo: 'csat',
      titulo,
      botoes: [1, 2, 3, 4, 5].map((nota) => ({ nota, cor: corNotaCsat(nota) })),
      rotuloMin: pergunta?.rotulo_min || 'Muito insatisfeito',
      rotuloMax: pergunta?.rotulo_max || 'Muito satisfeito',
    }
  return {
    tipo: 'nps',
    titulo,
    botoes: Array.from({ length: 11 }, (_, nota) => ({ nota, cor: corNotaNps(nota) })),
    rotuloMin: pergunta?.rotulo_min || 'Nada provável',
    rotuloMax: pergunta?.rotulo_max || 'Muito provável',
  }
}

/** Os três e-mails de pesquisa (o de teste é um convite). */
export type QualEmail = 'convite' | 'lembrete' | 'agradecimento'
export type GrupoAgradecimento = keyof Agradecimentos

export interface PreviaEmail {
  qual: QualEmail
  de: string
  /** Logo do cabeçalho: o do formulário dos convites, senão o da empresa; null = sem logo (ou "Mostrar o logo" desligado). */
  logo: string | null
  responderPara: string | null
  assunto: string
  /** Cor de destaque (#RRGGBB): a faixa do topo, o botão "Responder pesquisa" e os links do corpo. */
  cor: string
  /** Texto do botão sobre a cor de destaque: branco com contraste ≥ 4,5:1, senão #111827. */
  corTextoBotao: string
  /** A imagem de topo do banco (largura toda do cartão, altura proporcional), ou null. */
  imagemTopo: { url: string; largura: number | null; altura: number | null } | null
  paragrafos: string[]
  /** Botões da nota (convite e lembrete); o agradecimento não tem. */
  bloco: BlocoNota | null
  /** Parágrafos da assinatura da conta (texto puro, como foi escrito: sem trocar variáveis). */
  assinatura: string[]
  /** O rodapé da conta (texto puro, com as quebras de linha), antes das duas linhas fixas; null sem rodapé. */
  rodapeConta: string | null
  /** As duas linhas fixas, que entram sempre. */
  rodape: string
  descadastro: string
}

/** O que a prévia usa da configuração (os campos do visual podem faltar na API antiga). */
export type ConfigPrevia = Pick<
  ConfigEnvios,
  'remetente_nome' | 'responder_para' | 'assunto_convite' | 'texto_convite' | 'assunto_lembrete' | 'texto_lembrete'
> &
  Partial<Pick<ConfigEnvios, 'agradecimento' | 'email_cor' | 'email_mostrar_logo' | 'email_imagem_topo' | 'email_assinatura' | 'email_rodape'>>

export interface OpcoesPrevia {
  /** Cor do tema do formulário do envio (vale quando a conta não escolheu uma cor própria). */
  temaCor?: string | null
  /** Agradecimento: o texto de qual grupo (padrão: nota alta). */
  grupo?: GrupoAgradecimento
  /** A pergunta principal do formulário do envio (título e rótulos do bloco da nota). */
  pergunta?: PerguntaDoBloco | null
}

/** Nota e comentário de exemplo do agradecimento, por grupo (NPS de 0 a 10; CSAT de 1 a 5). */
export function exemploAgradecimento(grupo: GrupoAgradecimento, tipoFormulario: TipoFormulario | null | undefined): { nota: number; motivo: string } {
  const csat = tipoFormulario === 'csat'
  if (grupo === 'detrator') return { nota: csat ? 2 : 4, motivo: 'A entrega atrasou dois dias e ninguém avisou.' }
  if (grupo === 'neutro') return { nota: csat ? 3 : 7, motivo: 'Gostei, mas a entrega poderia ser mais rápida.' }
  return { nota: csat ? 5 : 10, motivo: 'O atendimento foi rápido e muito atencioso.' }
}

/**
 * Monta a prévia do convite, do lembrete ou do agradecimento com valores de exemplo, na mesma ordem e com as mesmas
 * regras da API (docs/api-etapa-5e.md §2.2): faixa na cor de destaque → logo (se houver e "Mostrar o logo" estiver
 * ligado) → imagem de topo → textos → bloco da nota → assinatura → rodapé da conta e as duas linhas fixas.
 */
export function montarPreviaEmail(
  config: ConfigPrevia,
  qual: QualEmail,
  tipoFormulario: TipoFormulario | null | undefined,
  exemplo: ValoresExemplo,
  logo: string | null = null,
  opcoes: OpcoesPrevia = {},
): PreviaEmail {
  const empresa = (exemplo.empresa ?? '').trim()
  const remetente = (config.remetente_nome ?? '').trim() || empresa || 'Sua empresa'
  const cor = corDestaque(config.email_cor, opcoes.temaCor)
  const topo = config.email_imagem_topo
  let assunto: string
  let texto: string
  let valores = exemplo
  if (qual === 'agradecimento') {
    const grupo = opcoes.grupo ?? 'promotor'
    const ex = exemploAgradecimento(grupo, tipoFormulario)
    valores = { ...exemplo, nota: exemplo.nota ?? ex.nota, motivo: exemplo.motivo ?? ex.motivo }
    // O assunto do agradecimento é fixo (a API não deixa mudar).
    assunto = empresa ? `${empresa} agradece a sua resposta` : 'Obrigado pela sua resposta'
    texto = config.agradecimento?.[grupo] ?? ''
  } else {
    assunto = renderizarMensagem(qual === 'convite' ? config.assunto_convite : config.assunto_lembrete, valores)
    texto = qual === 'convite' ? config.texto_convite : config.texto_lembrete
  }
  return {
    qual,
    de: `${remetente} via Toqqi`,
    logo: config.email_mostrar_logo === false ? null : logo || null,
    responderPara: (config.responder_para ?? '').trim() || null,
    assunto,
    cor,
    corTextoBotao: corTextoBotao(cor),
    imagemTopo: topo?.url ? { url: topo.url, largura: topo.largura ?? null, altura: topo.altura ?? null } : null,
    paragrafos: paragrafos(renderizarMensagem(texto, valores)),
    bloco: qual === 'agradecimento' ? null : blocoNota(tipoFormulario, opcoes.pergunta ?? null, valores),
    assinatura: paragrafos(textoOuNulo(config.email_assinatura) ?? ''),
    rodapeConta: textoOuNulo(config.email_rodape),
    rodape: `Você recebeu esta pesquisa porque é cliente de ${empresa || 'sua empresa'}.`,
    descadastro: 'Não quero mais receber pesquisas',
  }
}

/** Ajusta a lista de dias ao número de lembretes, mantendo o que já existe e sempre crescente (1–30). */
export function ajustarDiasLembretes(dias: number[], quantidade: number): number[] {
  const n = Math.max(0, Math.min(3, Math.trunc(quantidade)))
  const saida: number[] = []
  for (let i = 0; i < n; i++) {
    const anterior = saida[i - 1] ?? 0
    const atual = dias[i]
    let d = typeof atual === 'number' && Number.isFinite(atual) ? atual : (DIAS_LEMBRETES_PADRAO[i] ?? anterior + 1)
    if (d <= anterior) d = anterior + 1
    saida.push(Math.min(30, d))
  }
  return saida
}

function inteiroEntre(v: unknown, min: number, max: number): boolean {
  return typeof v === 'number' && Number.isInteger(v) && v >= min && v <= max
}

const EMAIL = /^[^\s@]+@[^\s@]+\.[^\s@]+$/

/**
 * Confere a configuração antes de salvar (as mesmas regras da API, para avisar na hora).
 * Devolve erros por campo, com as mesmas chaves que a API usa em `campos`. Etapa 5e: também o visual dos e-mails
 * (só os campos que vieram).
 */
export function validarConfig(c: Omit<ConfigEnvios, 'email_imagem_topo'>): Record<string, string> {
  const e: Record<string, string> = validarVisual(c)
  if (!inteiroEntre(c.intervalo_dias, 30, 365)) e.intervalo_dias = 'Use um número entre 30 e 365 dias.'
  if (!inteiroEntre(c.descanso_dias, 0, 180)) e.descanso_dias = 'Use um número entre 0 e 180 dias.'
  if (!inteiroEntre(c.lembretes, 0, 3)) e.lembretes = 'Escolha de 0 a 3 lembretes.'
  else {
    const dias = c.dias_lembretes ?? []
    if (dias.length !== c.lembretes) e.dias_lembretes = 'Informe o dia de cada lembrete.'
    else if (dias.some((d) => !inteiroEntre(d, 1, 30))) e.dias_lembretes = 'Cada lembrete precisa ser entre 1 e 30 dias depois do convite.'
    else if (dias.some((d, i) => i > 0 && d <= dias[i - 1]!)) e.dias_lembretes = 'Cada lembrete precisa vir depois do anterior.'
  }
  const hora = /^([01]\d|2[0-3]):[0-5]\d$/
  if (!hora.test(c.janela_inicio ?? '')) e.janela_inicio = 'Informe um horário, por exemplo 08:00.'
  if (!hora.test(c.janela_fim ?? '')) e.janela_fim = 'Informe um horário, por exemplo 18:00.'
  else if (!e.janela_inicio && c.janela_fim <= c.janela_inicio) e.janela_fim = 'O fim precisa ser depois do início.'
  if (c.responder_para && c.responder_para.trim() && !EMAIL.test(c.responder_para.trim())) e.responder_para = 'Confira o e-mail.'
  if (c.remetente_nome && c.remetente_nome.length > 100) e.remetente_nome = 'Use até 100 caracteres.'
  for (const k of ['assunto_convite', 'assunto_lembrete'] as const) {
    const v = (c[k] ?? '').trim()
    if (!v) e[k] = 'Escreva o assunto.'
    else if (v.length > LIMITE_ASSUNTO) e[k] = `Use até ${LIMITE_ASSUNTO} caracteres.`
  }
  for (const k of ['texto_convite', 'texto_lembrete', 'texto_whatsapp'] as const) {
    const v = (c[k] ?? '').trim()
    if (!v) e[k] = 'Escreva o texto.'
    else if (v.length > LIMITE_TEXTO) e[k] = `Use até ${LIMITE_TEXTO} caracteres.`
  }
  if (!e.texto_whatsapp && !(c.texto_whatsapp ?? '').includes('{link}')) {
    e.texto_whatsapp = 'Inclua {link}: é por ele que a pessoa abre a pesquisa.'
  }
  if (c.agradecimento_ativo) {
    for (const g of ['promotor', 'neutro', 'detrator'] as const) {
      const v = (c.agradecimento?.[g] ?? '').trim()
      if (!v) e[`agradecimento.${g}`] = 'Escreva o texto.'
      else if (v.length > LIMITE_TEXTO) e[`agradecimento.${g}`] = `Use até ${LIMITE_TEXTO} caracteres.`
    }
  }
  return e
}

/** A API pode mandar "dias_lembretes.1" ou "agradecimento[promotor]": normaliza para a chave que a tela usa. */
export function normalizarCampos(campos: Record<string, string>): Record<string, string> {
  const saida: Record<string, string> = {}
  for (const [k, msg] of Object.entries(campos)) {
    let chave = k.replace(/\[(\w+)\]/g, '.$1')
    if (chave.startsWith('dias_lembretes')) chave = 'dias_lembretes'
    saida[chave] ??= msg
  }
  return saida
}

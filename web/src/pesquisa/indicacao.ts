// Etapa 5c: regras puras do convite de indicação (cartão da tela final da pesquisa e registro à mão em Crescimento).
// As mesmas regras da API, para avisar na hora. Sem dependências do app: a página pública precisa continuar leve.
import { emailValido } from './validacao'
import type { ConviteIndicacao, DadosIndicacao, TelaFinalDepoimento, TipoPergunta } from './tipos'

export const MINIMO_NOME_INDICACAO = 2
export const LIMITE_NOME_INDICACAO = 120
export const LIMITE_EMPRESA_INDICACAO = 120
export const LIMITE_OBSERVACAO_INDICACAO = 500
/** No máximo 3 indicações por convite (a 4ª volta 409 `limite_indicacoes`). */
export const MAXIMO_INDICACOES = 3
export const MENSAGEM_OBRIGADO_INDICACAO = 'Obrigado pela indicação!'

/** Erro que o envio da indicação pode lançar: mensagem para mostrar, erros por campo e o código da API. */
export interface ErroIndicacao {
  mensagem?: string
  campos?: Record<string, string>
  codigo?: string
}

/** O que a pessoa digitou no formulário (texto livre). */
export interface CamposIndicacao {
  nome: string
  empresa: string
  telefone: string
  email: string
  observacao: string
}

export function camposIndicacaoVazios(): CamposIndicacao {
  return { nome: '', empresa: '', telefone: '', email: '', observacao: '' }
}

/** A nota principal dá direito ao convite? NPS 9 ou 10; CSAT (ou estrelas) 5. */
export function notaDaDireitoAIndicacao(tipo: TipoPergunta | null | undefined, nota: unknown): boolean {
  if (typeof nota !== 'number' || !Number.isInteger(nota)) return false
  if (tipo === 'nps') return nota >= 9 && nota <= 10
  if (tipo === 'csat' || tipo === 'estrelas') return nota === 5
  return false
}

/** O `indicacao` da resposta da API, só se vier no formato certo (texto puro); senão null. */
export function lerConviteIndicacao(v: unknown): ConviteIndicacao | null {
  if (!v || typeof v !== 'object' || Array.isArray(v)) return null
  const o = v as Record<string, unknown>
  const titulo = typeof o.titulo === 'string' ? o.titulo.trim() : ''
  const texto = typeof o.texto === 'string' ? o.texto.trim() : ''
  if (!titulo && !texto) return null
  const recompensa = typeof o.recompensa === 'string' && o.recompensa.trim() ? o.recompensa.trim() : null
  return { titulo, texto, recompensa }
}

const digitos = (v: string) => v.replace(/\D/g, '')

// Caracteres de controle (a API também tira); a quebra de linha só fica na observação.
const CONTROLE = /[\u0000-\u0008\u000B\u000C\u000E-\u001F\u007F]/g
const CONTROLE_E_QUEBRA = /[\u0000-\u001F\u007F]+/g

export function limparLinha(v: string): string {
  return v.replace(CONTROLE_E_QUEBRA, ' ').replace(/\s{2,}/g, ' ').trim()
}

export function limparTexto(v: string): string {
  return v.replace(/\r\n?/g, '\n').replace(CONTROLE, '').trim()
}

/**
 * Telefone brasileiro como a API aceita: DDD e número (10 ou 11 dígitos, sem o zero da operadora) ou já com o 55
 * (12 ou 13). Vazio não é erro aqui (a regra "telefone ou e-mail" fica em `validarIndicacao`).
 */
export function erroTelefoneIndicacao(v: string): string | null {
  const d = digitos(v)
  if (!d) return null
  if ((d.length === 10 || d.length === 11) && d.startsWith('0')) return 'Informe o DDD sem o zero da operadora.'
  if (d.length < 10 || d.length > 13) return 'Informe DDD e número, ex.: (11) 91234-5678.'
  return null
}

/** Erros por campo, com as mesmas chaves da API (`confirmo` só no cartão público). */
export function validarIndicacao(c: CamposIndicacao, opcoes: { confirmo?: boolean } = {}): Record<string, string> {
  const e: Record<string, string> = {}
  const nome = limparLinha(c.nome)
  if (!nome) e.nome = 'Informe o nome de quem você indica.'
  else if (nome.length < MINIMO_NOME_INDICACAO) e.nome = 'O nome precisa ter pelo menos 2 letras.'
  else if (nome.length > LIMITE_NOME_INDICACAO) e.nome = `Use até ${LIMITE_NOME_INDICACAO} caracteres.`
  if (limparLinha(c.empresa).length > LIMITE_EMPRESA_INDICACAO) e.empresa = `Use até ${LIMITE_EMPRESA_INDICACAO} caracteres.`
  const tel = erroTelefoneIndicacao(c.telefone)
  if (tel) e.telefone = tel
  const email = c.email.trim()
  if (email && !emailValido(email)) e.email = 'Confira o e-mail: parece que falta alguma parte.'
  if (!digitos(c.telefone) && !email) e.telefone = 'Informe o WhatsApp ou o e-mail (pelo menos um dos dois).'
  if (limparTexto(c.observacao).length > LIMITE_OBSERVACAO_INDICACAO) e.observacao = `Use até ${LIMITE_OBSERVACAO_INDICACAO} caracteres.`
  if (opcoes.confirmo === false) e.confirmo = 'Marque a confirmação para enviar.'
  return e
}

/** Os campos prontos para a API: textos limpos, telefone só com dígitos e vazios como null. */
export function camposParaApi(c: CamposIndicacao): Pick<DadosIndicacao, 'nome' | 'empresa' | 'telefone' | 'email' | 'observacao'> {
  return {
    nome: limparLinha(c.nome),
    empresa: limparLinha(c.empresa) || null,
    telefone: digitos(c.telefone) || null,
    email: c.email.trim() || null,
    observacao: limparTexto(c.observacao) || null,
  }
}

/** Corpo de POST /publico/convites/{token}/indicacoes. */
export function montarIndicacao(c: CamposIndicacao, podeIdentificar: boolean, confirmo: boolean): DadosIndicacao {
  return { ...camposParaApi(c), pode_identificar: podeIdentificar, confirmo }
}

/** A API pode mandar `telefone`, `campos.telefone` ou `indicacao.telefone`: fica a última parte que é um campo do formulário. */
export function camposDoServidor(campos: Record<string, string> | undefined): Record<string, string> {
  const conhecidos = new Set(['nome', 'empresa', 'telefone', 'email', 'observacao', 'confirmo', 'pode_identificar'])
  const saida: Record<string, string> = {}
  for (const [chave, msg] of Object.entries(campos ?? {})) {
    const campo = chave.split('.').reverse().find((p) => conhecidos.has(p))
    if (campo && !saida[campo]) saida[campo] = msg
  }
  return saida
}

/** Melhoria 5: o bloco `depoimento` da tela final, conferido (link só https; nada a mostrar vira null). */
export function lerDepoimento(v: unknown): TelaFinalDepoimento | null {
  if (!v || typeof v !== 'object') return null
  const o = v as Record<string, unknown>
  const url = typeof o.avaliar_url === 'string' && /^https:\/\/\S+$/i.test(o.avaliar_url) ? o.avaliar_url : null
  const pedir = o.pedir === true
  if (!pedir && !url) return null
  return { pedir, avaliar_url: url, avaliar_rotulo: typeof o.avaliar_rotulo === 'string' && o.avaliar_rotulo ? o.avaliar_rotulo : 'Deixar uma avaliação' }
}

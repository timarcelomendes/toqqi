/** Erro vindo da API, já no formato que as telas usam. */
export class ApiError extends Error {
  readonly status: number
  readonly codigo: string
  readonly campos: Record<string, string>

  constructor(status: number, codigo: string, mensagem: string, campos: Record<string, string> = {}) {
    super(mensagem)
    this.name = 'ApiError'
    this.status = status
    this.codigo = codigo
    this.campos = campos
  }

  /** Texto pronto para mostrar ao usuário. */
  get mensagem(): string {
    return this.message
  }

  /** Mensagem de um campo específico, se a API mandou. */
  campo(nome: string): string | undefined {
    return this.campos[nome]
  }
}

export const MENSAGEM_MUITAS_TENTATIVAS = 'Muitas tentativas. Aguarde um minuto.'
export const MENSAGEM_SEM_CONEXAO =
  'Não conseguimos falar com o servidor. Confira sua internet e tente de novo.'
export const MENSAGEM_INESPERADA = 'Algo deu errado do nosso lado. Tente de novo em instantes.'
export const MENSAGEM_SEM_PERMISSAO = 'Seu perfil não tem permissão para fazer isso.'
export const MENSAGEM_SESSAO_INVALIDA = 'Sua sessão terminou. Entre de novo para continuar.'

function ehObjeto(v: unknown): v is Record<string, unknown> {
  return typeof v === 'object' && v !== null && !Array.isArray(v)
}

/** Converte o corpo de campos em Record<string, string>, ignorando o que não for texto. */
function lerCampos(v: unknown): Record<string, string> {
  if (!ehObjeto(v)) return {}
  const campos: Record<string, string> = {}
  for (const [chave, valor] of Object.entries(v)) {
    if (typeof valor === 'string') campos[chave] = valor
    else if (Array.isArray(valor) && typeof valor[0] === 'string') campos[chave] = valor.join(' ')
  }
  return campos
}

function codigoPadrao(status: number): string {
  if (status === 401) return 'sessao_invalida'
  if (status === 403) return 'sem_permissao'
  if (status === 404) return 'nao_encontrado'
  if (status === 429) return 'muitas_tentativas'
  if (status >= 500) return 'erro_servidor'
  return 'erro'
}

function mensagemPadrao(status: number): string {
  if (status === 401) return MENSAGEM_SESSAO_INVALIDA
  if (status === 403) return MENSAGEM_SEM_PERMISSAO
  if (status === 404) return 'Não encontramos o que você procurou.'
  if (status === 429) return MENSAGEM_MUITAS_TENTATIVAS
  return MENSAGEM_INESPERADA
}

/**
 * Lê uma resposta de erro da API: `{erro: {codigo, mensagem, campos}}`.
 * Se o corpo vier em outro formato (ou vazio), cai em textos padrão por status.
 */
export function lerErroApi(status: number, corpo: unknown): ApiError {
  const erro = ehObjeto(corpo) && ehObjeto(corpo.erro) ? corpo.erro : null
  const codigo = erro && typeof erro.codigo === 'string' && erro.codigo ? erro.codigo : codigoPadrao(status)
  let mensagem =
    erro && typeof erro.mensagem === 'string' && erro.mensagem.trim() ? erro.mensagem : mensagemPadrao(status)
  // 429 sempre com o mesmo texto, simples e direto.
  if (status === 429) mensagem = MENSAGEM_MUITAS_TENTATIVAS
  return new ApiError(status, codigo, mensagem, erro ? lerCampos(erro.campos) : {})
}

/** Erro de rede (sem resposta do servidor). */
export function erroDeConexao(): ApiError {
  return new ApiError(0, 'sem_conexao', MENSAGEM_SEM_CONEXAO)
}

/** Texto para mostrar a partir de qualquer erro capturado. */
export function mensagemDoErro(e: unknown): string {
  if (e instanceof ApiError) return e.mensagem
  return MENSAGEM_INESPERADA
}

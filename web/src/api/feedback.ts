// Feedback (docs/api-feedback.md): quem usa o Toqqi relata erros, dá ideias, pede melhorias e elogia; a equipe Toqqi
// responde em Plataforma › Feedback. Envios com imagem vão como multipart (FormData); as imagens voltam só pelas rotas
// com o token (blob), nunca por URL pública.
import { api, obterBlob } from './cliente'

export type TipoFeedback = 'erro' | 'sugestao' | 'melhoria' | 'elogio'
export type SituacaoFeedback = 'recebido' | 'em_analise' | 'planejado' | 'concluido' | 'encerrado'
export type ImpactoFeedback = 'bloqueia' | 'atrapalha' | 'detalhe'
export type FiltroSituacaoFeedback = 'abertos' | 'concluidos' | 'encerrados' | 'todos'

export interface ImagemFeedback {
  id: number
  tipo: string
  tamanho: number
  largura: number | null
  altura: number | null
  nome: string | null
}

export interface MensagemFeedback {
  id: number
  autor: 'usuario' | 'equipe'
  /** O nome de quem escreveu (null: a pessoa saiu da conta). */
  autor_nome: string | null
  /** Vazio numa mudança de situação sem texto. */
  texto: string
  /** A situação nova, quando a equipe mudou junto com a mensagem. */
  situacao: SituacaoFeedback | null
  criado_em: string
  imagens: ImagemFeedback[]
}

export interface FeedbackResumo {
  id: number
  tipo: TipoFeedback
  situacao: SituacaoFeedback
  impacto: ImpactoFeedback | null
  autoriza_depoimento: boolean
  /** O começo do relato, numa linha (até 160 caracteres). */
  trecho: string
  /** Mensagens com texto (o relato conta). */
  mensagens: number
  imagens: number
  pagina_titulo: string | null
  criado_em: string
  atualizado_em: string
}

export interface FeedbackDoUsuario extends FeedbackResumo {
  /** A equipe respondeu ou mudou a situação depois da última vez que a pessoa abriu a conversa. */
  novidade: boolean
}

export interface ListaFeedbacks {
  itens: FeedbackDoUsuario[]
  novidades: number
}

export interface Feedback {
  id: number
  tipo: TipoFeedback
  situacao: SituacaoFeedback
  impacto: ImpactoFeedback | null
  autoriza_depoimento: boolean
  pagina: string | null
  pagina_titulo: string | null
  criado_em: string
  atualizado_em: string
  mensagens: MensagemFeedback[]
}

/** Uma imagem pronta para enviar (já convertida e reduzida pelo site). */
export interface ArquivoFeedback {
  blob: Blob
  nome: string
}

export interface NovoFeedback {
  tipo: TipoFeedback
  texto: string
  impacto?: ImpactoFeedback | null
  autoriza_depoimento?: boolean
  /** Navegador, tamanho da tela, versão do site e diagnóstico (só com ele marcado). */
  detalhes: boolean
  pagina?: string | null
  pagina_titulo?: string | null
  tela?: string | null
  versao_site?: string | null
  /** JSON de `utils/diagnostico` ({erros, pedidos}). */
  diagnostico?: string | null
  imagens?: ArquivoFeedback[]
}

/** O FormData do envio: campos vazios ficam de fora; as imagens vão no campo `imagens`, com o nome do arquivo. */
export function formularioDoFeedback(dados: NovoFeedback): FormData {
  const f = new FormData()
  f.append('tipo', dados.tipo)
  f.append('texto', dados.texto)
  if (dados.impacto) f.append('impacto', dados.impacto)
  if (dados.autoriza_depoimento) f.append('autoriza_depoimento', 'true')
  f.append('detalhes', dados.detalhes ? 'true' : 'false')
  for (const campo of ['pagina', 'pagina_titulo'] as const) {
    const v = dados[campo]
    if (v) f.append(campo, v)
  }
  if (dados.detalhes) {
    for (const campo of ['tela', 'versao_site', 'diagnostico'] as const) {
      const v = dados[campo]
      if (v) f.append(campo, v)
    }
  }
  for (const i of dados.imagens ?? []) f.append('imagens', i.blob, i.nome)
  return f
}

export function formularioDaMensagem(texto: string, imagens: ArquivoFeedback[] = []): FormData {
  const f = new FormData()
  if (texto) f.append('texto', texto)
  for (const i of imagens) f.append('imagens', i.blob, i.nome)
  return f
}

const id = (v: number) => encodeURIComponent(String(v))

export const feedbackApi = {
  listar: (sinal?: AbortSignal) => api.get<ListaFeedbacks>('/feedback', { sinal }),
  /** O número do menu: feedbacks com resposta ou mudança de situação que a pessoa ainda não viu. */
  novidades: () => api.get<{ novidades: number }>('/feedback/novidades', { semTratamentoGlobal: true }),
  criar: (dados: NovoFeedback) => api.post<Feedback>('/feedback', formularioDoFeedback(dados)),
  /** Abrir marca como visto. */
  detalhe: (feedbackId: number, sinal?: AbortSignal) => api.get<Feedback>(`/feedback/${id(feedbackId)}`, { sinal }),
  responder: (feedbackId: number, texto: string, imagens: ArquivoFeedback[] = []) =>
    api.post<Feedback>(`/feedback/${id(feedbackId)}/mensagens`, formularioDaMensagem(texto, imagens)),
  autorizarDepoimento: (feedbackId: number, autoriza: boolean) =>
    api.patch<Feedback>(`/feedback/${id(feedbackId)}`, { autoriza_depoimento: autoriza }),
  imagem: (feedbackId: number, imagemId: number, sinal?: AbortSignal) =>
    obterBlob(`/feedback/${id(feedbackId)}/imagens/${id(imagemId)}`, sinal),
}

// ---- Plataforma › Feedback (só superadmin) -------------------------------------------------------------------------

export interface FeedbackPlataformaResumo extends FeedbackResumo {
  conta_id: number
  conta_nome: string
  autor_nome: string | null
  autor_email: string | null
  /** Feedback novo ou mensagem da pessoa que a equipe ainda não viu. */
  atencao: boolean
}

export interface ContagemFeedback {
  atencao: number
  abertos: number
}

export interface ListaFeedbacksPlataforma {
  itens: FeedbackPlataformaResumo[]
  contagem: ContagemFeedback
}

export interface ErroDiagnostico {
  quando: string | null
  tipo: string
  mensagem: string
  local: string
}

export interface PedidoDiagnostico {
  quando: string | null
  metodo: string
  caminho: string
  status: number
  codigo: string | null
  request_id: string | null
}

export interface FeedbackPlataforma {
  id: number
  tipo: TipoFeedback
  situacao: SituacaoFeedback
  impacto: ImpactoFeedback | null
  autoriza_depoimento: boolean
  criado_em: string
  atualizado_em: string
  conta: { id: number; nome: string; plano: string; situacao: string }
  /** null: a pessoa saiu da conta. */
  autor: { id: number; nome: string; email: string; perfil: string; cargo: string | null; situacao: string } | null
  contexto: {
    pagina: string | null
    pagina_titulo: string | null
    navegador: string | null
    tela: string | null
    versao_site: string | null
    diagnostico: { erros?: ErroDiagnostico[]; pedidos?: PedidoDiagnostico[] } | null
  }
  nota_interna: string
  mensagens: MensagemFeedback[]
}

export interface FiltrosFeedbackPlataforma {
  tipo?: TipoFeedback | ''
  situacao?: FiltroSituacaoFeedback
  busca?: string
}

export const plataformaFeedbackApi = {
  listar: (filtros: FiltrosFeedbackPlataforma = {}, sinal?: AbortSignal) =>
    api.get<ListaFeedbacksPlataforma>('/plataforma/feedback', { query: { ...filtros }, sinal }),
  contagem: () => api.get<ContagemFeedback>('/plataforma/feedback/contagem', { semTratamentoGlobal: true }),
  /** Abrir marca como visto pela equipe. */
  detalhe: (feedbackId: number, sinal?: AbortSignal) =>
    api.get<FeedbackPlataforma>(`/plataforma/feedback/${id(feedbackId)}`, { sinal }),
  /** Texto e/ou situação nova numa mensagem; com texto, a pessoa recebe e-mail. */
  responder: (feedbackId: number, dados: { texto: string; situacao?: SituacaoFeedback | null }) =>
    api.post<FeedbackPlataforma>(`/plataforma/feedback/${id(feedbackId)}/mensagens`, dados),
  /** Situação (entra na conversa, sem e-mail) e/ou nota interna. */
  alterar: (feedbackId: number, dados: { situacao?: SituacaoFeedback; nota_interna?: string }) =>
    api.patch<FeedbackPlataforma>(`/plataforma/feedback/${id(feedbackId)}`, dados),
  imagem: (feedbackId: number, imagemId: number, sinal?: AbortSignal) =>
    obterBlob(`/plataforma/feedback/${id(feedbackId)}/imagens/${id(imagemId)}`, sinal),
}

// Endpoints da etapa 5e (docs/api-etapa-5e.md): o banco de imagens da conta (a imagem de topo dos e-mails) e
// Auditoria › E-mails enviados. O visual dos e-mails vai junto da configuração de envio (`enviosApi`).
import { api } from './cliente'
import type { BancoImagens, FiltrosEmailsEnviados, Id, ImagemBanco, PaginaEmailsEnviados } from './tipos'

const seg = (v: Id) => encodeURIComponent(String(v))

export const imagensApi = {
  /** `configuracoes.gerenciar`. Só as imagens do banco (os logos ficam de fora), mais novas primeiro. */
  listar: (sinal?: AbortSignal) => api.get<BancoImagens>('/imagens', { sinal }),
  /**
   * Multipart `arquivo`: PNG ou JPEG (conferido pelos bytes) de até 1 MB → 201 com o item. Tipo ou tamanho errado →
   * 422 no campo `arquivo`; com 30 imagens → 409 `limite_imagens`.
   */
  enviar: (arquivo: File) => {
    const corpo = new FormData()
    corpo.append('arquivo', arquivo)
    return api.post<ImagemBanco>('/imagens', corpo)
  },
  /** 204. A imagem de topo dos e-mails → 409 `imagem_em_uso`; de outra conta ou que não existe → 404. */
  excluir: (id: Id) => api.delete(`/imagens/${seg(id)}`),
}

export const emailsEnviadosApi = {
  /** `auditoria.ver`. Mais novos primeiro; `busca` no destinatário e no assunto; `falhas_7_dias` não usa os filtros. */
  listar: (filtros: FiltrosEmailsEnviados = {}, sinal?: AbortSignal) =>
    api.get<PaginaEmailsEnviados>('/auditoria/emails', { query: { ...filtros }, sinal }),
}

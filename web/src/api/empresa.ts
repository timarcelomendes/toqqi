// Dados da empresa e imagens (docs/api-dados-empresa.md): Configurações › Empresa e o logo do formulário.
import { api } from './cliente'
import type { DadosEmpresaConta, DadosEmpresaContaIn, Id } from './tipos'

const seg = (v: Id) => encodeURIComponent(String(v))

function comArquivo(arquivo: File): FormData {
  const corpo = new FormData()
  corpo.append('arquivo', arquivo)
  return corpo
}

export const empresaApi = {
  obter: () => api.get<DadosEmpresaConta>('/conta/dados'),
  /** Todos os campos de texto (opcionais vazios = null). */
  salvar: (dados: DadosEmpresaContaIn) => api.put<DadosEmpresaConta>('/conta/dados', dados),
  /** PNG ou JPG de até 300 KB (o servidor confere pelos primeiros bytes). */
  enviarLogo: (arquivo: File) => api.put<DadosEmpresaConta>('/conta/logo', comArquivo(arquivo)),
  removerLogo: () => api.delete('/conta/logo'),
}

export const logoFormularioApi = {
  /** Guarda o logo do formulário e devolve a URL pública; ela só vale no formulário quando ele é salvo (tema.logo_url). */
  enviar: (formularioId: Id, arquivo: File) => api.post<{ logo_url: string }>(`/formularios/${seg(formularioId)}/logo`, comArquivo(arquivo)),
}

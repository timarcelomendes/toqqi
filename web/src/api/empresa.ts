// Dados da empresa e imagens (docs/api-dados-empresa.md): Configurações › Empresa e o logo do formulário. Etapa 5h:
// a marca nas pesquisas (a cor da conta e se já tem logo), no "Comece por aqui" do Início.
import { api } from './cliente'
import type { DadosEmpresaConta, DadosEmpresaContaIn, Id, MarcaConta, ResultadoMarca } from './tipos'

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

/** Etapa 5h (docs/api-etapa-5h.md §1): sua marca nas pesquisas. O logo vai por `empresaApi.enviarLogo`. */
export const marcaApi = {
  /** {cor, tem_logo}: qualquer perfil da conta lê. */
  obter: () => api.get<MarcaConta>('/conta/marca'),
  /**
   * Só configuracoes.gerenciar. Grava a cor dos e-mails e troca a dos formulários que ainda estão na cor dos modelos;
   * 422 `dados_invalidos` (campo `cor`) fora do formato #RRGGBB.
   */
  salvar: (cor: string) => api.put<ResultadoMarca>('/conta/marca', { cor }),
}

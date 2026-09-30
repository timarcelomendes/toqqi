// Endpoints das páginas públicas (sem login). Importado pela entrada leve `responder.html`:
// não pode puxar Pinia, router nem o resto do app.
import { api } from './cliente'
import type { CanalPublico } from '@/pesquisa/contexto'
import type { Contexto, FormularioPublico, Respostas, TelaFinal, Variaveis } from '@/pesquisa/tipos'

export interface PesquisaPublica {
  formulario: FormularioPublico
  variaveis: Partial<Variaveis>
  ja_respondido?: boolean
}

const publico = { autenticar: false, semTratamentoGlobal: true } as const
const seg = (v: string) => encodeURIComponent(v)

export const publicoApi = {
  convite: (token: string) => api.get<PesquisaPublica>(`/publico/convites/${seg(token)}`, publico),
  responderConvite: (token: string, respostas: Respostas) =>
    api.post<TelaFinal | undefined>(`/publico/convites/${seg(token)}/responder`, { respostas }, publico),
  formulario: (codigo: string) => api.get<PesquisaPublica>(`/publico/formularios/${seg(codigo)}`, publico),
  responderFormulario: (
    codigo: string,
    dados: { respostas: Respostas; canal?: CanalPublico; referencia?: string; contexto?: Contexto },
  ) => api.post<TelaFinal | undefined>(`/publico/formularios/${seg(codigo)}/responder`, dados, publico),
}

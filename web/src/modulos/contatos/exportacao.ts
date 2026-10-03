// Filtros das abas Contatos e Empresas → a consulta de GET /contatos e /empresas (a lista) e de GET /contatos.csv e
// /empresas.csv ("Exportar CSV", etapa 5f §2.2): a mesma função monta as duas, então o CSV traz o que a lista mostra.
// Sem a página e sem os vazios (busca sem espaços nas pontas).
import type { FiltrosContatos, FiltrosEmpresas } from '@/api/etapa2'
import type { Id, Referencia } from '@/api/tipos'

/** Os filtros como a aba Contatos guarda (a empresa escolhida inteira, para mostrar o nome). */
export interface FiltrosContatosTela {
  busca: string
  empresa: Referencia | null
  grupo_id: Id | ''
  responsavel_id: Id | ''
  perfil_id: Id | ''
  ativo: 'true' | 'false' | 'todos'
}

export interface FiltrosEmpresasTela {
  busca: string
  grupo_id: Id | ''
  segmento_id: Id | ''
  responsavel_id: Id | ''
  ativa: 'true' | 'false' | 'todas'
}

const vazio = (v: unknown) => v === undefined || v === null || v === ''

/** Tira as chaves vazias (o cliente também tira, mas assim a consulta fica igual à que vai no endereço). */
function semVazios<T extends object>(o: T): T {
  return Object.fromEntries(Object.entries(o).filter(([, v]) => !vazio(v))) as T
}

export function consultaContatos(f: FiltrosContatosTela): FiltrosContatos {
  return semVazios<FiltrosContatos>({
    busca: f.busca.trim(),
    empresa_id: f.empresa?.id ?? '',
    grupo_id: f.grupo_id,
    responsavel_id: f.responsavel_id,
    perfil_id: f.perfil_id,
    ativo: f.ativo,
  })
}

export function consultaEmpresas(f: FiltrosEmpresasTela): FiltrosEmpresas {
  return semVazios<FiltrosEmpresas>({
    busca: f.busca.trim(),
    grupo_id: f.grupo_id,
    segmento_id: f.segmento_id,
    responsavel_id: f.responsavel_id,
    ativa: f.ativa,
  })
}

/** O texto da consulta, como vai no endereço ("busca=ana&grupo_id=3&ativo=todos"). */
export function textoConsulta(c: FiltrosContatos | FiltrosEmpresas): string {
  return new URLSearchParams(Object.entries(c).map(([k, v]) => [k, String(v)])).toString()
}

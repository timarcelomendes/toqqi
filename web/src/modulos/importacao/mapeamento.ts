import type {
  AnaliseImportacao,
  CampoImportacao,
  ChaveImportacao,
  CorpoImportacao,
  CorpoImportacaoRespostas,
  Id,
  TipoImportacao,
} from '@/api/tipos'

export const LIMITE_ARQUIVO = 5 * 1024 * 1024
export const EXTENSOES_ACEITAS = ['.csv', '.xlsx', '.xls']

/** coluna do arquivo → chave do campo ('' = não importar). */
export type Mapeamento = Record<string, string>

/** Confere extensão e tamanho antes de enviar. */
export function validarArquivo(arquivo: { name: string; size: number }): string | null {
  const nome = arquivo.name.toLowerCase()
  if (!EXTENSOES_ACEITAS.some((e) => nome.endsWith(e))) return 'Use uma planilha .csv, .xlsx ou .xls.'
  if (arquivo.size === 0) return 'Esse arquivo está vazio.'
  if (arquivo.size > LIMITE_ARQUIVO) return 'O arquivo passa de 5 MB. Divida em partes menores e importe uma de cada vez.'
  return null
}

/** Começa pelo que a API sugeriu; colunas sem sugestão (ou com campo repetido) ficam "não importar". */
export function mapeamentoInicial(colunas: string[], sugerido: Record<string, string | null | undefined>, campos?: CampoImportacao[]): Mapeamento {
  const validos = campos ? new Set(campos.map((c) => c.chave)) : null
  const usados = new Set<string>()
  const m: Mapeamento = {}
  for (const col of colunas) {
    const s = sugerido[col] ?? ''
    if (s && (!validos || validos.has(s)) && !usados.has(s)) {
      m[col] = s
      usados.add(s)
    } else m[col] = ''
  }
  return m
}

/** Campos escolhidos em mais de uma coluna. */
export function camposDuplicados(m: Mapeamento): string[] {
  const contagem = new Map<string, number>()
  for (const campo of Object.values(m)) if (campo) contagem.set(campo, (contagem.get(campo) ?? 0) + 1)
  return [...contagem.entries()].filter(([, n]) => n > 1).map(([c]) => c)
}

export function camposMapeados(m: Mapeamento): Set<string> {
  return new Set(Object.values(m).filter(Boolean))
}

/** Campos obrigatórios que ainda não têm coluna. */
export function obrigatoriosFaltando(m: Mapeamento, campos: CampoImportacao[]): CampoImportacao[] {
  const usados = camposMapeados(m)
  return campos.filter((c) => c.obrigatorio && !usados.has(c.chave))
}

/** A regra de contato: e-mail OU telefone precisa estar na planilha. */
export function faltaEmailOuTelefone(m: Mapeamento): boolean {
  const usados = camposMapeados(m)
  return !usados.has('email') && !usados.has('telefone')
}

const ORDEM_CHAVES: ChaveImportacao[] = ['email', 'codigo_externo', 'telefone']

/** Chaves que dá para usar (o campo precisa estar mapeado). */
export function chavesPossiveis(m: Mapeamento): ChaveImportacao[] {
  const usados = camposMapeados(m)
  return ORDEM_CHAVES.filter((c) => usados.has(c))
}

/** Mantém a chave atual se ainda vale; senão a primeira possível (e-mail > código > telefone). */
export function escolherChave(m: Mapeamento, atual: ChaveImportacao | null): ChaveImportacao | null {
  const possiveis = chavesPossiveis(m)
  if (atual && possiveis.includes(atual)) return atual
  return possiveis[0] ?? null
}

/** O que vai para a API: só as colunas que serão importadas. */
export function mapeamentoParaEnvio(m: Mapeamento): Record<string, string> {
  return Object.fromEntries(Object.entries(m).filter(([, c]) => !!c))
}

/**
 * Problemas que impedem conferir (mensagens prontas para mostrar).
 * Respostas antigas: valem só as colunas obrigatórias que a API indicar (e-mail, data e nota) e não há chave a escolher.
 */
export function pendenciasMapeamento(
  m: Mapeamento,
  campos: CampoImportacao[],
  chave: ChaveImportacao | null,
  tipo: TipoImportacao = 'contatos',
): string[] {
  const p: string[] = []
  const rotulo = (k: string) => campos.find((c) => c.chave === k)?.rotulo ?? k
  for (const c of camposDuplicados(m)) p.push(`“${rotulo(c)}” foi escolhido em mais de uma coluna.`)
  for (const c of obrigatoriosFaltando(m, campos)) p.push(`Falta indicar a coluna de “${c.rotulo}”.`)
  if (tipo === 'respostas') return p
  if (faltaEmailOuTelefone(m)) p.push('Indique a coluna de e-mail ou a de telefone (pelo menos uma).')
  if (!chave) p.push('Escolha como reconhecer quem já está cadastrado.')
  return p
}

// ── Tipo da importação (etapa 4a) ────────────────────────────────────────────

export const TIPOS_IMPORTACAO: Record<
  TipoImportacao,
  { rotulo: string; descricao: string; titulo: string; subtitulo: string; item: [string, string]; voltar: { rotulo: string; para: string } }
> = {
  contatos: {
    rotulo: 'Contatos',
    descricao: 'Seus clientes: nome, e-mail ou telefone, empresa e cargo.',
    titulo: 'Importar contatos',
    subtitulo: 'Traga seus clientes de uma planilha do Excel ou de outro sistema, sem digitar um por um.',
    item: ['contato', 'contatos'],
    voltar: { rotulo: 'Contatos', para: '/contatos' },
  },
  respostas: {
    rotulo: 'Respostas antigas',
    descricao: 'Notas que seus clientes deram antes de usar o Toqqi, para ver o histórico completo.',
    titulo: 'Importar respostas antigas',
    subtitulo: 'Traga as notas que seus clientes já deram, de outra ferramenta ou de uma planilha, para o histórico ficar completo.',
    item: ['resposta', 'respostas'],
    voltar: { rotulo: 'Respostas', para: '/respostas' },
  },
}

/** `?tipo=respostas` escolhe respostas antigas; qualquer outra coisa, contatos. */
export function tipoDaQuery(v: unknown): TipoImportacao {
  const s = Array.isArray(v) ? v[0] : v
  return s === 'respostas' ? 'respostas' : 'contatos'
}

/** Corpo de conferir/importar conforme o tipo (respostas: sem chave e sem grupo). Null enquanto falta a chave dos contatos. */
export function corpoParaTipo(
  tipo: TipoImportacao,
  m: Mapeamento,
  opcoes: { chave: ChaveImportacao | null; atualizar_existentes: boolean; grupo_id?: Id | '' },
): CorpoImportacao | CorpoImportacaoRespostas | null {
  const mapeamento = mapeamentoParaEnvio(m)
  if (tipo === 'respostas') return { mapeamento, atualizar_existentes: opcoes.atualizar_existentes }
  if (!opcoes.chave) return null
  return {
    mapeamento,
    chave: opcoes.chave,
    atualizar_existentes: opcoes.atualizar_existentes,
    ...(opcoes.grupo_id !== undefined && opcoes.grupo_id !== '' ? { grupo_id: opcoes.grupo_id } : {}),
  }
}

/** Até `n` valores de exemplo de uma coluna, vindos da amostra (objeto por coluna ou lista por posição). */
export function exemplosDaColuna(analise: Pick<AnaliseImportacao, 'colunas' | 'amostra'>, coluna: string, n = 3): string[] {
  const i = analise.colunas.indexOf(coluna)
  const saida: string[] = []
  for (const linha of analise.amostra ?? []) {
    const v = Array.isArray(linha.valores) ? linha.valores[i] : (linha.valores as Record<string, unknown>)?.[coluna]
    if (v === null || v === undefined) continue
    const t = String(v).trim()
    if (t) saida.push(t)
    if (saida.length >= n) break
  }
  return saida
}

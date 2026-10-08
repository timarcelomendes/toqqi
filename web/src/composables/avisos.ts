import { reactive } from 'vue'

export type TipoAviso = 'sucesso' | 'erro' | 'atencao' | 'info'

/** Um botão no aviso (ex.: "Atualizar a página"): faz a ação e fecha o aviso. */
export interface AcaoAviso {
  rotulo: string
  executar: () => void
}

export interface Aviso {
  id: number
  tipo: TipoAviso
  mensagem: string
  titulo?: string
  duracao: number
  acao?: AcaoAviso
}

let proximoId = 1
export const avisos = reactive<Aviso[]>([])
const temporizadores = new Map<number, ReturnType<typeof setTimeout>>()

export function fecharAviso(id: number): void {
  const i = avisos.findIndex((a) => a.id === id)
  if (i >= 0) avisos.splice(i, 1)
  const t = temporizadores.get(id)
  if (t) clearTimeout(t)
  temporizadores.delete(id)
}

/** Mostra um aviso. `duracao` 0: fica até a pessoa fechar (ou usar a `acao`). */
export function avisar(opcoes: { tipo?: TipoAviso; mensagem: string; titulo?: string; duracao?: number; acao?: AcaoAviso }): number {
  // Evita empilhar a mesma mensagem várias vezes (ex.: vários 403 ao mesmo tempo).
  const repetido = avisos.find((a) => a.mensagem === opcoes.mensagem)
  if (repetido) return repetido.id
  const id = proximoId++
  const tipo = opcoes.tipo ?? 'info'
  const duracao = opcoes.duracao ?? (tipo === 'erro' ? 7000 : 4500)
  avisos.push({ id, tipo, mensagem: opcoes.mensagem, titulo: opcoes.titulo, duracao, acao: opcoes.acao })
  if (avisos.length > 4) fecharAviso(avisos[0]!.id)
  if (duracao > 0) temporizadores.set(id, setTimeout(() => fecharAviso(id), duracao))
  return id
}

avisar.sucesso = (mensagem: string, titulo?: string) => avisar({ tipo: 'sucesso', mensagem, titulo })
avisar.erro = (mensagem: string, titulo?: string) => avisar({ tipo: 'erro', mensagem, titulo })
avisar.atencao = (mensagem: string, titulo?: string) => avisar({ tipo: 'atencao', mensagem, titulo })
avisar.info = (mensagem: string, titulo?: string) => avisar({ tipo: 'info', mensagem, titulo })

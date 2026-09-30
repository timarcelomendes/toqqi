import { defineStore } from 'pinia'
import { reactive } from 'vue'
import { cadastrosApi, responsaveisApi, type Id, type ItemCadastro, type Responsavel, type TipoCadastro } from '@/api'

type Lista = TipoCadastro | 'responsaveis'

/**
 * Listas auxiliares (grupos, segmentos, perfis, cargos e responsáveis), buscadas uma vez
 * e reaproveitadas pelos filtros e formulários. `garantir` só busca o que ainda não veio.
 */
export const useCadastrosStore = defineStore('cadastros', () => {
  const listas = reactive({
    grupos: [] as ItemCadastro[],
    segmentos: [] as ItemCadastro[],
    perfis: [] as ItemCadastro[],
    cargos: [] as ItemCadastro[],
    responsaveis: [] as Responsavel[],
  })
  const carregado = reactive<Record<Lista, boolean>>({ grupos: false, segmentos: false, perfis: false, cargos: false, responsaveis: false })
  const pedidos = new Map<Lista, Promise<void>>()

  function ordenar<T extends { nome: string }>(l: T[]): T[] {
    return [...l].sort((a, b) => a.nome.localeCompare(b.nome, 'pt-BR'))
  }

  async function carregar(tipo: Lista): Promise<void> {
    const pedido = (async () => {
      if (tipo === 'responsaveis') listas.responsaveis = ordenar(await responsaveisApi.listar())
      else listas[tipo] = ordenar(await cadastrosApi.listar(tipo))
      carregado[tipo] = true
    })()
    pedidos.set(tipo, pedido)
    try {
      await pedido
    } finally {
      pedidos.delete(tipo)
    }
  }

  /** Busca as listas que ainda não foram carregadas (erros são ignorados: a tela segue com lista vazia). */
  async function garantir(tipos: Lista[]): Promise<void> {
    await Promise.all(
      tipos.map((t) => (carregado[t] ? undefined : (pedidos.get(t) ?? carregar(t)).catch(() => undefined))),
    )
  }

  function colocar(tipo: TipoCadastro, item: ItemCadastro) {
    const i = listas[tipo].findIndex((x) => String(x.id) === String(item.id))
    const nova = [...listas[tipo]]
    if (i >= 0) nova.splice(i, 1, item)
    else nova.push(item)
    listas[tipo] = ordenar(nova)
  }

  function tirar(tipo: TipoCadastro, id: Id) {
    listas[tipo] = listas[tipo].filter((x) => String(x.id) !== String(id))
  }

  function colocarResponsavel(r: Responsavel) {
    const i = listas.responsaveis.findIndex((x) => String(x.id) === String(r.id))
    const nova = [...listas.responsaveis]
    if (i >= 0) nova.splice(i, 1, r)
    else nova.push(r)
    listas.responsaveis = ordenar(nova)
  }

  function tirarResponsavel(id: Id) {
    listas.responsaveis = listas.responsaveis.filter((x) => String(x.id) !== String(id))
  }

  return { listas, carregado, carregar, garantir, colocar, tirar, colocarResponsavel, tirarResponsavel }
})

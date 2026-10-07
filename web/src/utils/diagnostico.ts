// Diagnóstico para o feedback de erro (docs/api-feedback.md §2.3): os últimos erros do site e os últimos pedidos à API
// que falharam neste carregamento da página. Fica só na memória do navegador: sai daqui apenas quando a pessoa envia um
// feedback de erro com "Enviar detalhes técnicos" marcado (a API limpa de novo os textos antes de guardar).
// Leve de propósito: o aviso de erros (`utils/erros.ts`) e o cliente da API (`api/cliente.ts`) registram aqui.

export interface ErroRecente {
  quando: string
  tipo: string
  mensagem: string
  local: string
}

export interface PedidoQueFalhou {
  quando: string
  metodo: string
  caminho: string
  status: number
  codigo: string | null
  request_id: string | null
}

export interface Diagnostico {
  erros: ErroRecente[]
  pedidos: PedidoQueFalhou[]
}

export const MAX_DIAGNOSTICO = 10

const erros: ErroRecente[] = []
const pedidos: PedidoQueFalhou[] = []

function guardar<T>(lista: T[], item: T): void {
  lista.push(item)
  if (lista.length > MAX_DIAGNOSTICO) lista.splice(0, lista.length - MAX_DIAGNOSTICO)
}

/** Um erro do site (o mesmo tipo e mensagem seguidos viram um só, com a hora da última vez). */
export function registrarErroDoSite(e: { tipo: string; mensagem: string; local: string }, agora = new Date()): void {
  try {
    const item: ErroRecente = {
      quando: agora.toISOString(),
      tipo: String(e.tipo || 'Error').slice(0, 80),
      mensagem: String(e.mensagem ?? '').slice(0, 300),
      local: String(e.local ?? '').slice(0, 200),
    }
    const ultimo = erros[erros.length - 1]
    if (ultimo && ultimo.tipo === item.tipo && ultimo.mensagem === item.mensagem && ultimo.local === item.local) {
      ultimo.quando = item.quando
      return
    }
    guardar(erros, item)
  } catch {
    /* o diagnóstico nunca quebra a página */
  }
}

/** Um pedido à API que falhou (status 0 = não chegou à API). O caminho vai sem query nem hash. */
export function registrarPedidoQueFalhou(
  p: { metodo: string; caminho: string; status: number; codigo?: string | null; requestId?: string | null },
  agora = new Date(),
): void {
  try {
    guardar(pedidos, {
      quando: agora.toISOString(),
      metodo: p.metodo,
      caminho: (p.caminho.split(/[?#]/)[0] ?? '').slice(0, 200),
      status: p.status,
      codigo: p.codigo && /^[a-z][a-z0-9_]{0,59}$/.test(p.codigo) ? p.codigo : null,
      request_id: p.requestId && /^[A-Za-z0-9_-]{1,64}$/.test(p.requestId) ? p.requestId : null,
    })
  } catch {
    /* idem */
  }
}

/** Uma cópia do que há agora (os mais antigos primeiro). */
export function diagnosticoAtual(): Diagnostico {
  return { erros: erros.map((e) => ({ ...e })), pedidos: pedidos.map((p) => ({ ...p })) }
}

/** O diagnóstico em texto para o envio, ou null quando não há nada. */
export function diagnosticoParaEnvio(d: Diagnostico = diagnosticoAtual()): string | null {
  return d.erros.length || d.pedidos.length ? JSON.stringify(d) : null
}

/** "1280x800": a janela do navegador agora. */
export function tamanhoDaJanela(): string | null {
  if (typeof window === 'undefined') return null
  const l = Math.round(window.innerWidth)
  const a = Math.round(window.innerHeight)
  return l > 9 && a > 9 ? `${l}x${a}` : null
}

/** Só para os testes. */
export function limparDiagnostico(): void {
  erros.splice(0)
  pedidos.splice(0)
}

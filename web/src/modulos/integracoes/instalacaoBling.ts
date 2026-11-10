// Instalação do Toqqi pela loja do Bling (Central de Extensões): a API manda a pessoa a /conectar/bling?instalacao=…
// O código fica guardado neste navegador por até 24 h (o mesmo prazo da API), para sobreviver ao cadastro, à
// confirmação do e-mail e ao entrar; ao ligar (ou ao vencer), some. Sem armazenamento (aba privada etc.), vale só a URL.
const CHAVE = 'toqqi.bling.instalacao'
const VALIDADE_MS = 24 * 60 * 60 * 1000

export function guardarInstalacao(codigo: string, agora = Date.now()): void {
  try {
    localStorage.setItem(CHAVE, JSON.stringify({ codigo, expira: agora + VALIDADE_MS }))
  } catch {
    /* sem armazenamento: segue pela URL */
  }
}

export function instalacaoGuardada(agora = Date.now()): string | null {
  try {
    const bruto = localStorage.getItem(CHAVE)
    if (!bruto) return null
    const { codigo, expira } = JSON.parse(bruto) as { codigo?: unknown; expira?: unknown }
    if (typeof codigo === 'string' && typeof expira === 'number' && expira > agora) return codigo
    localStorage.removeItem(CHAVE)
  } catch {
    /* ilegível ou sem armazenamento */
  }
  return null
}

export function esquecerInstalacao(): void {
  try {
    localStorage.removeItem(CHAVE)
  } catch {
    /* sem armazenamento */
  }
}

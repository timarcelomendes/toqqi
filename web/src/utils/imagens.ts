// Imagens enviadas para a API (logo da empresa e do formulário): as mesmas regras do servidor.

/** Até 300 KB (307.200 bytes), como a API. */
export const LIMITE_LOGO = 300 * 1024

/** A mesma mensagem da API (422 `arquivo`). */
export const MENSAGEM_LOGO = 'Use uma imagem PNG ou JPG de até 300 KB.'

/** Para o seletor de arquivos: só PNG e JPG. */
export const ACEITA_LOGO = 'image/png,image/jpeg'

const PNG = [0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]
const JPEG = [0xff, 0xd8, 0xff]

async function inicioDoArquivo(f: Blob, n: number): Promise<Uint8Array | null> {
  try {
    const parte = f.slice(0, n)
    if (typeof parte.arrayBuffer === 'function') return new Uint8Array(await parte.arrayBuffer())
    return await new Promise((resolver) => {
      const leitor = new FileReader()
      leitor.onload = () => resolver(leitor.result instanceof ArrayBuffer ? new Uint8Array(leitor.result) : null)
      leitor.onerror = () => resolver(null)
      leitor.readAsArrayBuffer(parte)
    })
  } catch {
    return null
  }
}

const comeca = (b: Uint8Array, assinatura: number[]) => assinatura.every((v, i) => b[i] === v)

/**
 * Confere o arquivo antes de enviar: até 300 KB e PNG ou JPG de verdade (pelos primeiros bytes, como o servidor,
 * e não pela extensão). Devolve a mensagem do problema ou null se está tudo certo.
 */
export async function conferirLogo(f: File): Promise<string | null> {
  if (!f.size || f.size > LIMITE_LOGO) return MENSAGEM_LOGO
  const inicio = await inicioDoArquivo(f, 8)
  if (inicio) return comeca(inicio, PNG) || comeca(inicio, JPEG) ? null : MENSAGEM_LOGO
  // Sem conseguir ler (navegador antigo): vale o tipo informado; o servidor confere de novo.
  return f.type === 'image/png' || f.type === 'image/jpeg' ? null : MENSAGEM_LOGO
}

/** Imagem guardada pela própria plataforma (logo enviado como arquivo): `.../publico/imagens/{chave}`. */
export function ehImagemDaPlataforma(url: string | null | undefined): boolean {
  return !!url && /\/publico\/imagens\/[\w-]+$/.test(url)
}

/**
 * O logo que o cliente vê, como a API faz nas páginas públicas e nos e-mails: o do formulário; sem ele, o da empresa.
 * `daEmpresa` diz quando a prévia está usando o logo da empresa (para avisar no editor).
 */
export function logoParaCliente(
  logoFormulario: string | null | undefined,
  logoEmpresa: string | null | undefined,
): { url: string | null; daEmpresa: boolean } {
  const proprio = logoFormulario?.trim()
  if (proprio) return { url: proprio, daEmpresa: false }
  const daEmpresa = logoEmpresa?.trim()
  return daEmpresa ? { url: daEmpresa, daEmpresa: true } : { url: null, daEmpresa: false }
}

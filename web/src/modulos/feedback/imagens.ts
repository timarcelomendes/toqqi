// Imagens do feedback no navegador: prints colados (Ctrl+V), arrastados ou escolhidos viram PNG ou JPG de até 1 MB antes
// de sair (a API só aceita esses dois, até 1 MB). PNG ou JPG que já cabem vão como estão; o resto é redesenhado num
// canvas (até 1920 px no lado maior; PNG primeiro quando a origem é PNG, para o texto dos prints ficar nítido; depois
// JPG em qualidades menores). Sem canvas (navegador antigo, testes), só passam os PNG e JPG que já cabem.
import type { ArquivoFeedback } from '@/api/feedback'
import { conferirImagem } from '@/utils/imagens'
import { LIMITE_IMAGEM, medidasReduzidas, nomeDaImagem } from './logica'

/** Acima disso nem tenta abrir (memória do celular). */
export const LIMITE_ORIGINAL = 15 * 1024 * 1024
export const MSG_GRANDE_DEMAIS = 'Esta imagem é grande demais. Use uma de até 15 MB.'
export const MSG_NAO_ABRIU = 'Não conseguimos abrir esta imagem. Use um print em PNG ou JPG.'
export const MSG_NAO_REDUZIU = 'Não conseguimos reduzir esta imagem para 1 MB. Tente recortar o print.'

const TENTATIVAS: { lado: number; tipo: 'image/png' | 'image/jpeg'; qualidade?: number; soPng?: boolean }[] = [
  { lado: 1920, tipo: 'image/png', soPng: true },
  { lado: 1920, tipo: 'image/jpeg', qualidade: 0.85 },
  { lado: 1600, tipo: 'image/jpeg', qualidade: 0.75 },
  { lado: 1280, tipo: 'image/jpeg', qualidade: 0.7 },
]

interface Desenhavel {
  largura: number
  altura: number
  fonte: CanvasImageSource
  liberar: () => void
}

async function abrir(arquivo: Blob): Promise<Desenhavel | null> {
  try {
    if (typeof createImageBitmap === 'function') {
      const b = await createImageBitmap(arquivo)
      return { largura: b.width, altura: b.height, fonte: b, liberar: () => b.close?.() }
    }
  } catch {
    /* tenta pelo <img> */
  }
  if (typeof Image === 'undefined' || typeof URL.createObjectURL !== 'function') return null
  const url = URL.createObjectURL(arquivo)
  try {
    const img = new Image()
    await new Promise<void>((ok, falhou) => {
      img.onload = () => ok()
      img.onerror = () => falhou(new Error('imagem'))
      img.src = url
    })
    return img.naturalWidth > 0
      ? { largura: img.naturalWidth, altura: img.naturalHeight, fonte: img, liberar: () => URL.revokeObjectURL(url) }
      : null
  } catch {
    URL.revokeObjectURL(url)
    return null
  }
}

function desenhar(d: Desenhavel, lado: number, tipo: 'image/png' | 'image/jpeg', qualidade?: number): Promise<Blob | null> {
  const { largura, altura } = medidasReduzidas(d.largura, d.altura, lado)
  const canvas = document.createElement('canvas')
  canvas.width = largura
  canvas.height = altura
  let ctx: CanvasRenderingContext2D | null = null
  try {
    ctx = canvas.getContext('2d')
  } catch {
    ctx = null
  }
  if (!ctx) return Promise.resolve(null)
  if (tipo === 'image/jpeg') {
    ctx.fillStyle = '#ffffff' // JPG não tem transparência: o fundo transparente vira branco, não preto
    ctx.fillRect(0, 0, largura, altura)
  }
  ctx.drawImage(d.fonte, 0, 0, largura, altura)
  return new Promise((resolver) => {
    try {
      canvas.toBlob((b) => resolver(b), tipo, qualidade)
    } catch {
      resolver(null)
    }
  })
}

/** A imagem pronta para enviar, ou um Error com a mensagem para a pessoa. `indice`: o número no nome dos prints colados. */
export async function prepararImagem(arquivo: Blob, indice = 1): Promise<ArquivoFeedback> {
  const nome = arquivo instanceof File ? arquivo.name : null
  if (!arquivo.size) throw new Error(MSG_NAO_ABRIU)
  if (arquivo.size > LIMITE_ORIGINAL) throw new Error(MSG_GRANDE_DEMAIS)
  const tipo = arquivo.type === 'image/png' ? 'image/png' : 'image/jpeg'
  // PNG ou JPG de verdade (pelos primeiros bytes, como a API) que já cabe: vai como está
  if (arquivo.size <= LIMITE_IMAGEM && arquivo instanceof File && !(await conferirImagem(arquivo, LIMITE_IMAGEM, 'x'))) {
    return { blob: arquivo, nome: nomeDaImagem(nome, tipo, indice) }
  }
  const d = await abrir(arquivo)
  if (!d) throw new Error(MSG_NAO_ABRIU)
  try {
    for (const t of TENTATIVAS) {
      if (t.soPng && arquivo.type !== 'image/png') continue
      const blob = await desenhar(d, t.lado, t.tipo, t.qualidade)
      if (!blob) throw new Error(MSG_NAO_ABRIU)
      if (blob.size <= LIMITE_IMAGEM) return { blob, nome: nomeDaImagem(nome, t.tipo, indice) }
    }
  } finally {
    d.liberar()
  }
  throw new Error(MSG_NAO_REDUZIU)
}

/** As imagens de uma colagem (Ctrl+V): só os itens de imagem da área de transferência. */
export function imagensDaColagem(e: ClipboardEvent): File[] {
  const itens = Array.from(e.clipboardData?.items ?? [])
  return itens
    .filter((i) => i.kind === 'file' && i.type.startsWith('image/'))
    .map((i) => i.getAsFile())
    .filter((f): f is File => !!f)
}

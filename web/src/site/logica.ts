/** Regras da página do site (rota "/"), sem DOM, para os testes. */

/** 262399.99 → "R$ 262.399,99" (sempre com centavos, como no painel). */
export function formatarReais(valor: number): string {
  return 'R$ ' + valor.toLocaleString('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

/** Passo seguinte do "Como funciona" (1 → 2 → 3 → 4 → 1). */
export function proximoPasso(atual: number, total = 4): number {
  return (atual % total) + 1
}

/** Valor do contador em `k` (0 a 1) com desaceleração no fim; termina exatamente em `fim`. */
export function valorContador(fim: number, k: number): number {
  if (k >= 1) return fim
  if (k <= 0) return 0
  return Math.round(fim * (1 - Math.pow(1 - k, 3)))
}

export interface SessaoGuardada {
  token?: unknown
  expira_em?: unknown
}

/**
 * Quem já entrou neste navegador vê "Abrir o Toqqi" em vez de "Entrar". Lê o mesmo item que o app guarda
 * (`toqqi.sessao`, stores/sessao.ts) só para decidir o rótulo; nada é enviado.
 */
export function temSessao(bruto: string | null, agora = Date.now()): boolean {
  if (!bruto) return false
  try {
    const dados = JSON.parse(bruto) as SessaoGuardada
    if (!dados || typeof dados.token !== 'string' || !dados.token) return false
    if (typeof dados.expira_em === 'string') {
      const fim = Date.parse(dados.expira_em)
      if (!Number.isNaN(fim) && fim <= agora) return false
    }
    return true
  } catch {
    return false
  }
}

export interface FalaConversa {
  pergunta: string
  status: string[]
  consultou: string
  resposta: string
}

/** A conversa de exemplo do ToqqiAI (dados fictícios, os mesmos do resto da página). */
export const CONVERSA: FalaConversa[] = [
  {
    pergunta: 'Por que o NPS caiu em setembro?',
    status: ['Consultando a evolução mensal…', 'Lendo os comentários de setembro…'],
    consultou: 'Consultou: evolução mensal · comentários',
    resposta:
      'O NPS de setembro foi 14, contra 43 em julho. A queda vem quase toda de Prazo e entrega: 6 reclamações entre 28 e 30/09, todas citando a transportadora nova.',
  },
  {
    pergunta: 'Quais clientes grandes estão em risco?',
    status: ['Buscando as empresas…', 'Conferindo os indicadores…'],
    consultou: 'Consultou: empresas · indicadores',
    resposta:
      'Duas empresas acima da mediana de valor têm NPS negativo: Pequi Marista (R$ 52.000/mês, com o Felipe) e Embalagens Meia Ponte (R$ 31.200/mês, com a Carla). A Embalagens deu nota 4 e reclamou da entrega.',
  },
  {
    pergunta: 'Como mudo o prazo dos planos de ação?',
    status: ['Procurando na Ajuda…'],
    consultou: 'Consultou: Ajuda',
    resposta:
      'Em Configurações › Planos de ação, no campo “Prazo para tratar”, informe os dias de detrator, neutro e promotor (de 1 a 90) e clique em “Salvar alterações”. O botão “Prazos automáticos”, na tela Planos de ação, leva direto até lá.',
  },
]

export const COTA_EXEMPLO = 500

// ── Números dos planos (etapa 5g) ───────────────────────────────────────────
// O HTML traz os padrões do código (para buscadores e quem não roda JavaScript); depois de abrir, o site busca
// GET /publico/planos e troca cada `<span data-p="{chave}">` pelo valor de agora (Plataforma › Parâmetros).

/** Quanto o site espera a resposta antes de desistir (e ficar com o HTML). */
export const TEMPO_PLANOS_MS = 5000

/** Os padrões do código (docs/api-etapa-5g.md §2) que o HTML mostra em cada `data-p`. */
export const PADROES_SITE: Record<string, string | number | null> = {
  'planos.essencial.preco': '149.00',
  'planos.profissional.preco': '349.00',
  'planos.empresa.preco': '799.00',
  'planos.essencial.contatos': 300,
  'planos.profissional.contatos': 1500,
  'planos.empresa.contatos': 5000,
  'ia.cota.essencial': 100,
  'ia.cota.profissional': 500,
  'ia.cota.empresa': 2000,
  'ia.cota.teste': 50,
  'ia.teto.essencial': 1000,
  'ia.teto.profissional': 5000,
  'ia.teto.empresa': 15000,
  'ia.teto.teste': 500,
  'whatsapp.franquia.essencial': null,
  'whatsapp.franquia.profissional': null,
  'whatsapp.franquia.empresa': null,
  'teste.dias': 14,
  'ia.analises.detalhado': 3,
  // etapa 5k
  'planos.desconto.pix': 3,
  'planos.desconto.anual': 10,
  'planos.personalizado.base': '99.00',
}

type Objeto = Record<string, unknown>
const ehObjeto = (v: unknown): v is Objeto => typeof v === 'object' && v !== null && !Array.isArray(v)

/**
 * Acha o valor de uma chave do §2 no corpo de GET /publico/planos (`{planos: [{chave, preco, contatos, whatsapp,
 * ia_cota, ia_teto}], teste: {dias, plano, whatsapp, ia_teto}, ia_analises: {…}}`). Chave que não está lá → undefined.
 */
export function valorPublico(corpo: unknown, chave: string): unknown {
  if (!ehObjeto(corpo)) return undefined
  const [grupo, a, b] = chave.split('.')
  const plano = (k: string | undefined): Objeto | undefined =>
    Array.isArray(corpo.planos) ? (corpo.planos as unknown[]).find((p): p is Objeto => ehObjeto(p) && p.chave === k) : undefined
  const teste = ehObjeto(corpo.teste) ? corpo.teste : undefined
  const campo = (o: Objeto | undefined, nome: string) => (o && nome in o ? o[nome] : undefined)
  if (grupo === 'planos' && b === 'preco') return campo(plano(a), 'preco')
  if (grupo === 'planos' && b === 'contatos') return campo(plano(a), 'contatos')
  if (grupo === 'ia' && a === 'cota') return b === 'teste' ? campo(teste, 'ia_cota') : campo(plano(b), 'ia_cota')
  if (grupo === 'planos' && a === 'desconto') return ehObjeto(corpo.descontos) ? campo(corpo.descontos, b ?? '') : undefined
  if (grupo === 'planos' && a === 'personalizado') return ehObjeto(corpo.personalizado) ? campo(corpo.personalizado, b ?? '') : undefined
  if (grupo === 'ia' && a === 'teto') return b === 'teste' ? campo(teste, 'ia_teto') : campo(plano(b), 'ia_teto')
  if (grupo === 'whatsapp' && a === 'franquia') return b === 'teste' ? campo(teste, 'whatsapp') : campo(plano(b), 'whatsapp')
  if (grupo === 'teste' && (a === 'dias' || a === 'plano')) return campo(teste, a)
  if (grupo === 'ia' && a === 'analises') return ehObjeto(corpo.ia_analises) ? campo(corpo.ia_analises, b ?? '') : undefined
  return undefined
}

const fmtInteiro = new Intl.NumberFormat('pt-BR', { maximumFractionDigits: 0 })
const fmtCentavos = new Intl.NumberFormat('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 })

/**
 * O texto do `data-p` para o valor: preço inteiro "149" (com centavos, "149,90"); contatos sem limite "sem limite"
 * ("Sem limite" com `data-p-maiuscula`); os outros, inteiros com milhar ("1.500"). Valor que não serve → null (o HTML fica).
 */
export function textoNumeroSite(chave: string, valor: unknown, maiuscula = false): string | null {
  if (chave.endsWith('.preco') || chave === 'planos.personalizado.base') {
    const n = typeof valor === 'number' ? valor : typeof valor === 'string' && valor.trim() ? Number(valor) : Number.NaN
    if (!Number.isFinite(n) || n < 0) return null
    const centavos = Math.round(n * 100)
    return centavos % 100 === 0 ? fmtInteiro.format(centavos / 100) : fmtCentavos.format(centavos / 100)
  }
  if (chave.endsWith('.contatos') && valor === null) return maiuscula ? 'Sem limite' : 'sem limite'
  // etapa 5k: WhatsApp sem franquia (o padrão)
  if (chave.startsWith('whatsapp.franquia.') && valor === null) return maiuscula ? 'Sem franquia' : 'sem franquia'
  if (typeof valor !== 'number' || !Number.isInteger(valor) || valor < 0) return null
  return fmtInteiro.format(valor)
}

/** O "Restam N" da conversa: a cota do Profissional menos as perguntas respondidas (nunca negativo). */
export function restamNaConversa(cota: number, respondidas: number): number {
  return Math.max(0, cota - respondidas)
}

/** O "Restam N" da conversa parada (a do HTML, com as 3 perguntas já respondidas). */
export function restamParado(cota: number): number {
  return restamNaConversa(cota, CONVERSA.length)
}

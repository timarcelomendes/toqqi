// Modo exemplo do Início (etapa 5h, docs/api-etapa-5h.md §1): um `Painel` fictício e completo, só do site (nada é
// gravado na conta), com as datas relativas a hoje e os nomes e números inventados. Os números fecham entre si: o NPS e
// as porcentagens saem das contagens; as empresas do ranking somam as respostas do período (as que faltam são de
// empresas com menos de 3 respostas ou sem empresa); a receita em risco soma o valor das empresas com detrator; o tom
// soma os analisados; os planos abertos são os das empresas da lista de atenção; a evolução marca os meses do período.
import type { EmpresaNps, Painel } from '@/api/tipos'
import { somarDias } from '@/utils/periodo'

/** Dias do período do exemplo (o padrão do Início: últimos 90 dias). */
export const DIAS_EXEMPLO = 90

interface EmpresaExemplo {
  id: number
  nome: string
  valor: number | null
  /** Promotores, neutros e detratores no período. */
  p: number
  n: number
  d: number
}

/** As empresas com respostas no período (as 10 primeiras têm 3 ou mais e entram no ranking). */
const EMPRESAS: EmpresaExemplo[] = [
  { id: 9001, nome: 'Mercearia Lua Nova', valor: 18500, p: 1, n: 1, d: 3 },
  { id: 9002, nome: 'Atacado Ventania', valor: 32000, p: 1, n: 0, d: 2 },
  { id: 9003, nome: 'Supermercado Bem-te-vi', valor: 12800, p: 2, n: 1, d: 2 },
  { id: 9004, nome: 'Hotel Mirante do Sol', valor: 9600, p: 2, n: 2, d: 1 },
  { id: 9005, nome: 'Farmácia Ipê Amarelo', valor: 7400, p: 3, n: 1, d: 1 },
  { id: 9006, nome: 'Padaria Grão de Ouro', valor: 4200, p: 3, n: 1, d: 0 },
  { id: 9007, nome: 'Hortifruti Quintal Verde', valor: 6100, p: 4, n: 0, d: 0 },
  { id: 9008, nome: 'Restaurante Sabor da Vila', valor: null, p: 2, n: 1, d: 0 },
  { id: 9009, nome: 'Cantina Dona Lia', valor: 3900, p: 2, n: 2, d: 1 },
  { id: 9010, nome: 'Mercadinho Estrela Guia', valor: 2700, p: 1, n: 1, d: 1 },
  // menos de 3 respostas: fora do ranking, mas contam no NPS e na receita em risco
  { id: 9011, nome: 'Açougue Boi Manso', valor: 5300, p: 1, n: 0, d: 1 },
  { id: 9012, nome: 'Conveniência Rota Nove', valor: 4800, p: 1, n: 1, d: 0 },
]
/** Respostas de NPS sem empresa (contatos avulsos). */
const SEM_EMPRESA = { p: 2, n: 0, d: 0 }
/** Soma do valor mensal de todas as empresas da carteira (inclusive as que não responderam no período). */
const CARTEIRA = 264500

const ref = (e: EmpresaExemplo) => ({ id: e.id, nome: e.nome })
const porNome = (nome: string) => EMPRESAS.find((e) => e.nome === nome)!

function nps(p: number, d: number, total: number): number | null {
  return total ? Math.round(((p - d) / total) * 100) : null
}

function pct(parte: number, total: number): number {
  return total ? Math.round((parte / total) * 1000) / 10 : 0
}

/** "AAAA-MM-DD" + hora de São Paulo → data e hora ISO (como a API manda). */
function momento(dia: string, hora = '10:30'): string {
  return `${dia}T${hora}:00-03:00`
}

/** Os 12 meses (AAAA-MM) que terminam no mês de `hoje`. */
function meses12(hoje: string): string[] {
  const [a, m] = hoje.split('-').map(Number) as [number, number]
  const lista: string[] = []
  for (let i = 11; i >= 0; i--) {
    const d = new Date(Date.UTC(a, m - 1 - i, 1))
    lista.push(`${d.getUTCFullYear()}-${String(d.getUTCMonth() + 1).padStart(2, '0')}`)
  }
  return lista
}

/** Último dia (AAAA-MM-DD) do mês AAAA-MM. */
function fimDoMes(mes: string): string {
  const [a, m] = mes.split('-').map(Number) as [number, number]
  return new Date(Date.UTC(a, m, 0)).toISOString().slice(0, 10)
}

/**
 * NPS e respostas de cada um dos 12 meses (do mais antigo ao atual): caiu nos últimos meses, com o pico de prazo. Os 4
 * últimos são os do período (25/11/12 em 48: 4/2/2, 8/4/3, 9/3/5 e 4/2/2), os 4 antes deles somam o NPS de 38 do
 * período anterior (aproximado).
 */
const SERIE: { nps: number; total: number }[] = [
  { nps: 45, total: 12 },
  { nps: 48, total: 14 },
  { nps: 41, total: 11 },
  { nps: 47, total: 15 },
  { nps: 50, total: 13 },
  { nps: 44, total: 16 },
  { nps: 37, total: 14 },
  { nps: 33, total: 15 },
  { nps: 25, total: 8 },
  { nps: 33, total: 15 },
  { nps: 24, total: 17 },
  { nps: 25, total: 8 },
]

/** O Painel fictício do modo exemplo, para o dia `hoje` (AAAA-MM-DD). */
export function painelExemplo(hoje: string): Painel {
  const de = somarDias(hoje, -(DIAS_EXEMPLO - 1))
  const dia = (n: number) => somarDias(hoje, -n)

  // NPS do período: as empresas + os avulsos (25 promotores, 11 neutros, 12 detratores em 48)
  const p = EMPRESAS.reduce((s, e) => s + e.p, SEM_EMPRESA.p)
  const n = EMPRESAS.reduce((s, e) => s + e.n, SEM_EMPRESA.n)
  const d = EMPRESAS.reduce((s, e) => s + e.d, SEM_EMPRESA.d)
  const total = p + n + d
  const valorNps = nps(p, d, total)!
  const anterior = 38

  // receita em risco: as empresas com detrator no período
  const comDetrator = EMPRESAS.filter((e) => e.d > 0)
  const valorEmRisco = comDetrator.reduce((s, e) => s + (e.valor ?? 0), 0)
  // planos abertos: os das empresas da lista de atenção (Ventania tem dois, um vencido)
  const ventania = porNome('Atacado Ventania')
  const luaNova = porNome('Mercearia Lua Nova')
  const bemTeVi = porNome('Supermercado Bem-te-vi')
  const mirante = porNome('Hotel Mirante do Sol')
  const atencaoEmpresas = [
    { e: ventania, abertas: 2, vencidas: 1, desde: dia(20), resp: 'Renata Lima', acao: 9101, comentario: 'Caixas amassadas de novo na última entrega.' },
    { e: luaNova, abertas: 1, vencidas: 0, desde: dia(12), resp: 'Otávio Reis', acao: 9103, comentario: 'A entrega chegou dois dias depois do combinado e ninguém avisou.' },
    { e: bemTeVi, abertas: 1, vencidas: 0, desde: dia(9), resp: 'Renata Lima', acao: 9104, comentario: 'O boleto veio com valor errado duas vezes este mês.' },
    { e: mirante, abertas: 1, vencidas: 0, desde: dia(4), resp: null, acao: 9105, comentario: 'O pedido veio incompleto e a reposição demorou.' },
  ]
  const abertas = atencaoEmpresas.reduce((s, x) => s + x.abertas, 0)
  const vencidas = atencaoEmpresas.reduce((s, x) => s + x.vencidas, 0)
  const comPlano = new Set(atencaoEmpresas.map((x) => x.e.id))

  // ranking: empresas com 3 ou mais respostas; metade (arredondada para cima, até 6) para "Cuidar primeiro"
  const ranking: EmpresaNps[] = EMPRESAS.filter((e) => e.p + e.n + e.d >= 3).map((e) => ({
    empresa: ref(e),
    nps: nps(e.p, e.d, e.p + e.n + e.d)!,
    respostas: e.p + e.n + e.d,
    valor_mensal: e.valor === null ? null : e.valor.toFixed(2),
  }))
  const piores = [...ranking].sort((a, b) => a.nps - b.nps || b.respostas - a.respostas || a.empresa.nome.localeCompare(b.empresa.nome))
  const qtdMenor = Math.min(6, Math.ceil(ranking.length / 2))
  const menor = piores.slice(0, qtdMenor)
  const usados = new Set(menor.map((x) => x.empresa.id))
  const maior = ranking
    .filter((x) => !usados.has(x.empresa.id))
    .sort((a, b) => b.nps - a.nps || b.respostas - a.respostas || a.empresa.nome.localeCompare(b.empresa.nome))
    .slice(0, 6)

  // evolução: 12 meses terminando no mês atual; os meses que cruzam o período ficam marcados
  const evolucao12m = meses12(hoje).map((mes, i) => ({
    mes,
    nps: SERIE[i]!.nps,
    total: SERIE[i]!.total,
    no_periodo: fimDoMes(mes) >= de && `${mes}-01` <= hoje,
  }))

  // tom: 41 dos 68 (NPS + CSAT) vieram com comentário, todos analisados
  const tom = { negativo: 13, misto: 6, neutro: 7, positivo: 15 }
  const analisados = tom.negativo + tom.misto + tom.neutro + tom.positivo
  const csat = { total: 20, satisfeitos: 15, soma: 80 }

  return {
    periodo: { de, ate: hoje, anterior: { de: somarDias(de, -DIAS_EXEMPLO), ate: somarDias(de, -1) } },
    nps: {
      valor: valorNps,
      faixa: valorNps >= 75 ? 'excelente' : valorNps >= 50 ? 'muito_bom' : valorNps >= 0 ? 'pode_melhorar' : 'critico',
      promotores: p,
      neutros: n,
      detratores: d,
      total,
      pct: { promotores: pct(p, total), neutros: pct(n, total), detratores: pct(d, total) },
      // decisores: 8 promotores, 3 neutros e 3 detratores
      decisores: { valor: nps(8, 3, 14), total: 14 },
    },
    variacao: { valor: valorNps - anterior, anterior },
    csat: { percentual: Math.round((csat.satisfeitos / csat.total) * 100), media: csat.soma / csat.total, total: csat.total, satisfeitos: csat.satisfeitos },
    taxa_resposta: { percentual: Math.round((52 / 120) * 100), responderam: 52, convidados: 120, amostra_pequena: false },
    movimentacao: {
      resgatados: 3,
      deixaram_de_ser_promotores: 2,
      itens: [
        { tipo: 'resgatado', contato: { id: 9201, nome: 'Heitor Campos' }, empresa: ref(porNome('Hortifruti Quintal Verde')), nota_anterior: 4, nota_atual: 10, data_anterior: momento(dia(150)), data_atual: momento(dia(2)) },
        { tipo: 'deixou_de_ser_promotor', contato: { id: 9202, nome: 'Larissa Moura' }, empresa: ref(luaNova), nota_anterior: 9, nota_atual: 3, data_anterior: momento(dia(120)), data_atual: momento(dia(1)) },
        { tipo: 'resgatado', contato: { id: 9203, nome: 'Gabriela Nunes' }, empresa: ref(porNome('Padaria Grão de Ouro')), nota_anterior: 6, nota_atual: 9, data_anterior: momento(dia(100)), data_atual: momento(dia(5)) },
        { tipo: 'deixou_de_ser_promotor', contato: { id: 9204, nome: 'Bruno Tavares' }, empresa: ref(ventania), nota_anterior: 10, nota_atual: 6, data_anterior: momento(dia(140)), data_atual: momento(dia(11)) },
        { tipo: 'resgatado', contato: { id: 9205, nome: 'Isabela Rocha' }, empresa: ref(porNome('Farmácia Ipê Amarelo')), nota_anterior: 5, nota_atual: 9, data_anterior: momento(dia(160)), data_atual: momento(dia(16)) },
      ],
    },
    atencao: {
      acoes_abertas: abertas,
      acoes_vencidas: vencidas,
      tudo_em_dia: abertas === 0,
      empresas: atencaoEmpresas.map((x) => ({
        empresa: ref(x.e),
        nps: nps(x.e.p, x.e.d, x.e.p + x.e.n + x.e.d),
        acoes_abertas: x.abertas,
        acoes_vencidas: x.vencidas,
        desde: momento(x.desde, '09:00'),
        responsavel: x.resp ? { id: x.resp === 'Renata Lima' ? 9301 : 9302, nome: x.resp } : null,
        ultimo_comentario_detrator: x.comentario,
        acao_id: x.acao,
      })),
      receita_em_risco: { valor: valorEmRisco, empresas: comDetrator.length, sem_valor: comDetrator.filter((e) => e.valor === null).length, carteira: CARTEIRA },
      // as empresas com detrator e sem plano aberto
      detratores_sem_plano: comDetrator.filter((e) => !comPlano.has(e.id)).length,
    },
    temas: [
      { chave: 'prazo_entrega', rotulo: 'Prazo e entrega', mencoes: 17, nota_media: 5.8, reclamacoes: 9, variacao: 6 },
      { chave: 'atendimento', rotulo: 'Atendimento', mencoes: 12, nota_media: 8.4, reclamacoes: 2, variacao: -1 },
      { chave: 'preco_condicoes', rotulo: 'Preço e condições', mencoes: 9, nota_media: 6.1, reclamacoes: 5, variacao: 2 },
      { chave: 'produto_avarias', rotulo: 'Produto e avarias', mencoes: 6, nota_media: 5.2, reclamacoes: 4, variacao: 3 },
      { chave: 'comunicacao', rotulo: 'Comunicação', mencoes: 4, nota_media: 7.5, reclamacoes: 1, variacao: 0 },
    ],
    comentarios: [
      { resposta_id: 9401, data: momento(dia(1), '16:12'), nota: 3, tipo_nota: 'nps', grupo: 'detrator', comentario: 'A entrega chegou dois dias depois do combinado e ninguém avisou.', contato: { id: 9202, nome: 'Larissa Moura' }, empresa: ref(luaNova) },
      { resposta_id: 9402, data: momento(dia(2), '11:40'), nota: 10, tipo_nota: 'nps', grupo: 'promotor', comentario: 'Atendimento rápido e o vendedor sempre resolve na hora.', contato: { id: 9201, nome: 'Heitor Campos' }, empresa: ref(porNome('Hortifruti Quintal Verde')) },
      { resposta_id: 9403, data: momento(dia(3), '09:05'), nota: 2, tipo_nota: 'csat', grupo: 'insatisfeito', comentario: 'Caixas amassadas de novo na última entrega.', contato: { id: 9204, nome: 'Bruno Tavares' }, empresa: ref(ventania) },
      { resposta_id: 9404, data: momento(dia(4), '14:22'), nota: 8, tipo_nota: 'nps', grupo: 'neutro', comentario: 'Bom preço, mas o pedido mínimo subiu muito.', contato: { id: 9206, nome: 'Elisa Prado' }, empresa: ref(porNome('Farmácia Ipê Amarelo')) },
      { resposta_id: 9405, data: momento(dia(5), '10:48'), nota: 9, tipo_nota: 'nps', grupo: 'promotor', comentario: 'Entrega no prazo e produtos sempre bem embalados.', contato: { id: 9203, nome: 'Gabriela Nunes' }, empresa: ref(porNome('Padaria Grão de Ouro')) },
      { resposta_id: 9406, data: momento(dia(6), '17:30'), nota: 5, tipo_nota: 'nps', grupo: 'detrator', comentario: 'O boleto veio com valor errado duas vezes este mês.', contato: { id: 9207, nome: 'Diego Fontes' }, empresa: ref(bemTeVi) },
    ],
    evolucao: evolucao12m.filter((x) => x.no_periodo).map(({ mes, nps: v, total: t }) => ({ mes, nps: v, total: t })),
    evolucao_12m: evolucao12m,
    empresas: { menor, maior },
    palavras: [
      { palavra: 'entrega', total: 14 },
      { palavra: 'prazo', total: 9 },
      { palavra: 'atendimento', total: 8 },
      { palavra: 'preço', total: 7 },
      { palavra: 'pedido', total: 6 },
      { palavra: 'vendedor', total: 5 },
      { palavra: 'rápido', total: 5 },
      { palavra: 'atraso', total: 4 },
      { palavra: 'boleto', total: 3 },
      { palavra: 'embalagem', total: 3 },
      { palavra: 'caixas', total: 3 },
      { palavra: 'frete', total: 2 },
      { palavra: 'reposição', total: 2 },
      { palavra: 'motorista', total: 2 },
    ],
    primeiros_passos: { contatos: true, envios_ligados: true, primeiro_envio: true, primeira_resposta: true },
    picos: [{ tema: 'prazo_entrega', rotulo: 'Prazo e entrega', reclamacoes: 5, media_anterior: 1.2, de: dia(6), ate: hoje }],
    tom: {
      analisados,
      com_comentario: analisados,
      total_respostas: total + csat.total,
      pendentes: 0,
      ...tom,
      anterior: { analisados: 37, negativo: 8 },
      ia_ligada: true,
      sem_analise: 0,
    },
  }
}

/** O "Resumo da IA" do exemplo (no modo exemplo, o cartão mostra este texto e não gera). */
export const RESUMO_IA_EXEMPLO = {
  melhorar: 'Prazo e entrega concentra 9 reclamações no período e ajudou a derrubar o NPS para 27, 11 pontos abaixo dos 90 dias antes.',
  funciona: 'O atendimento segue como ponto forte: 12 menções, nota média 8,4 e elogios à rapidez dos vendedores.',
  proximo_passo: 'Crie os planos das 4 empresas com detrator sem plano e combine com a logística um aviso ao cliente quando a entrega atrasar.',
} as const

// Etapa 5h (docs/api-etapa-5h.md §1 e §2): as regras puras do primeiro dia — "Comece por aqui", a cor da marca, o modo
// exemplo (o Painel fictício fecha as contas), o tom com a IA ligada e o botão "Criar planos para N empresas".
import { describe, expect, it } from 'vitest'
import type { Painel } from '@/api/tipos'
import { somarDias } from '@/utils/periodo'
import {
  CORES_MARCA,
  COR_DOS_MODELOS,
  contraste,
  corDoTexto,
  exemploNaConsulta,
  marcaFeita,
  normalizarCor,
  progressoPassos,
  proximoPasso,
  semRespostas,
  textoCorSalva,
} from '@/modulos/inicio/logica'
import { textoIaImportados } from '@/modulos/importacao/mapeamento'
import { DIAS_EXEMPLO, RESUMO_IA_EXEMPLO, painelExemplo } from '@/modulos/painel/exemplo'
import {
  acoesManchete,
  estadoTom,
  faixaDoNps,
  montarManchete,
  montarPassos,
  rotuloCriarPlanos,
  textoDasPartes,
  textoNaoLidos,
  textoPlanosCriados,
  type EntradaManchete,
} from '@/modulos/painel/logica'

const todas = () => true

describe('Comece por aqui', () => {
  it('troca o painel só sem nenhuma resposta (a importada conta); sem o bloco (servidor antigo), não troca', () => {
    expect(semRespostas({ contatos: true, envios_ligados: false, primeiro_envio: false, primeira_resposta: false })).toBe(true)
    expect(semRespostas({ contatos: true, envios_ligados: false, primeiro_envio: false, primeira_resposta: true })).toBe(false)
    expect(semRespostas({ primeira_resposta: 3 })).toBe(false)
    expect(semRespostas({ primeira_resposta: 0 })).toBe(true)
    expect(semRespostas(null)).toBe(false)
    expect(semRespostas(undefined)).toBe(false)
  })

  it('o próximo passo é o primeiro não feito; o progresso conta os feitos', () => {
    const passos = montarPassos({ contatos: true, envios_ligados: false, primeiro_envio: false, primeira_resposta: false }, todas)
    expect(proximoPasso(passos)?.chave).toBe('envios_ligados')
    expect(progressoPassos(passos)).toEqual({ feitos: 1, total: 4, texto: '1 de 4 feitos' })
    const nenhum = montarPassos({}, todas)
    expect(proximoPasso(nenhum)?.chave).toBe('contatos')
    expect(progressoPassos(nenhum).texto).toBe('0 de 4 feitos')
    const um = montarPassos({ contatos: false, envios_ligados: true }, todas)
    expect(proximoPasso(um)?.chave).toBe('contatos') // o primeiro não feito, mesmo fora de ordem
    expect(progressoPassos(um).texto).toBe('1 de 4 feitos')
    expect(proximoPasso(montarPassos({ contatos: true, envios_ligados: true, primeiro_envio: true, primeira_resposta: true }, todas))).toBeNull()
  })
})

describe('sua marca nas pesquisas', () => {
  it('cor no formato #RRGGBB (o # pode faltar), em maiúsculas; o resto é inválido', () => {
    expect(normalizarCor(' #d63a18 ')).toBe('#D63A18')
    expect(normalizarCor('0e7490')).toBe('#0E7490')
    for (const ruim of ['', '   ', '#D63A1', '#GGGGGG', '#D63A18AA', 'azul', 'rgb(1,2,3)', null, undefined]) expect(normalizarCor(ruim)).toBeNull()
  })

  it('as 8 sugestões são diferentes, válidas e com texto branco legível (4,5:1); a dos modelos fica de fora', () => {
    expect(CORES_MARCA).toHaveLength(8)
    expect(new Set(CORES_MARCA.map((c) => c.cor)).size).toBe(8)
    for (const c of CORES_MARCA) {
      expect(normalizarCor(c.cor)).toBe(c.cor)
      expect(contraste(c.cor, '#FFFFFF')).toBeGreaterThanOrEqual(4.5)
      expect(corDoTexto(c.cor)).toBe('#FFFFFF')
      expect(c.nome).toBeTruthy()
    }
    expect(CORES_MARCA.map((c) => c.cor)).not.toContain(COR_DOS_MODELOS)
  })

  it('o texto em cima da cor: branco com 4,5:1 ou mais; senão, quase preto', () => {
    expect(corDoTexto('#000000')).toBe('#FFFFFF')
    expect(corDoTexto('#FDE047')).toBe('#111827')
    expect(corDoTexto('#FFFFFF')).toBe('#111827')
    expect(corDoTexto('#767676')).toBe('#FFFFFF') // o limite: 4,54:1
    expect(corDoTexto('#777777')).toBe('#111827')
    expect(Math.round(contraste('#000000', '#FFFFFF'))).toBe(21)
  })

  it('feito = tem logo ou cor própria; o aviso diz quantos formulários mudaram', () => {
    expect(marcaFeita({ cor: null, tem_logo: false })).toBe(false)
    expect(marcaFeita({ cor: '#D63A18', tem_logo: false })).toBe(true)
    expect(marcaFeita({ cor: null, tem_logo: true })).toBe(true)
    expect(marcaFeita(null)).toBe(false)
    expect(textoCorSalva(0)).toBe('Cor salva: os e-mails das pesquisas já usam a nova cor.')
    expect(textoCorSalva(1)).toBe('Cor salva: os e-mails e 1 formulário já usam a nova cor.')
    expect(textoCorSalva(3)).toBe('Cor salva: os e-mails e 3 formulários já usam a nova cor.')
  })
})

describe('modo exemplo', () => {
  it('?exemplo=1 no endereço abre direto nele (outros valores, não)', () => {
    expect(exemploNaConsulta('1')).toBe(true)
    expect(exemploNaConsulta(['1', '0'])).toBe(true)
    for (const v of ['0', 'sim', '', null, undefined]) expect(exemploNaConsulta(v)).toBe(false)
  })

  it('o Painel de exemplo fecha as contas: NPS, porcentagens, empresas, receita, planos e tom', () => {
    const hoje = '2026-10-04'
    const p: Painel = painelExemplo(hoje)
    // período e anterior relativos a hoje
    expect(p.periodo).toEqual({ de: somarDias(hoje, -(DIAS_EXEMPLO - 1)), ate: hoje, anterior: { de: somarDias(hoje, -179), ate: somarDias(hoje, -90) } })
    // NPS a partir das contagens
    const { promotores: pr, neutros: ne, detratores: de, total } = p.nps
    expect(pr + ne + de).toBe(total)
    expect(p.nps.valor).toBe(Math.round(((pr - de) / total) * 100))
    expect(p.nps.faixa).toBe(faixaDoNps(p.nps.valor))
    expect(p.nps.pct.promotores + p.nps.pct.neutros + p.nps.pct.detratores).toBeCloseTo(100, 0)
    expect(p.variacao!.valor).toBe(p.nps.valor! - p.variacao!.anterior)
    // o ranking: só empresas com 3+ respostas, sem repetir, e não passa do total do período
    const ranking = [...p.empresas.menor, ...p.empresas.maior]
    expect(ranking.every((e) => e.respostas >= 3)).toBe(true)
    expect(new Set(ranking.map((e) => e.empresa.id)).size).toBe(ranking.length)
    expect(ranking.reduce((s, e) => s + e.respostas, 0)).toBeLessThanOrEqual(total)
    expect(Math.max(...p.empresas.menor.map((e) => e.nps))).toBeLessThanOrEqual(Math.min(...p.empresas.maior.map((e) => e.nps)))
    // planos: os abertos e os vencidos somam os das empresas da lista; a receita cabe na carteira
    expect(p.atencao.empresas.reduce((s, e) => s + e.acoes_abertas, 0)).toBe(p.atencao.acoes_abertas)
    expect(p.atencao.empresas.reduce((s, e) => s + e.acoes_vencidas, 0)).toBe(p.atencao.acoes_vencidas)
    const risco = p.atencao.receita_em_risco
    expect(Number(risco.valor)).toBeGreaterThan(0)
    expect(Number(risco.valor)).toBeLessThan(Number(risco.carteira))
    expect(p.atencao.detratores_sem_plano).toBe(risco.empresas - p.atencao.empresas.length)
    // tom: as partes somam os analisados; os analisados cabem nos comentários e nas respostas
    const t = p.tom!
    expect(t.negativo + t.misto + t.neutro + t.positivo).toBe(t.analisados)
    expect(t.analisados).toBeLessThanOrEqual(t.com_comentario)
    expect(t.total_respostas).toBe(total + p.csat.total)
    expect(t.ia_ligada).toBe(true)
    // CSAT, taxa e decisores
    expect(p.csat.percentual).toBe(Math.round((p.csat.satisfeitos / p.csat.total) * 100))
    expect(p.taxa_resposta.percentual).toBe(Math.round((p.taxa_resposta.responderam / p.taxa_resposta.convidados) * 100))
    expect(p.nps.decisores.total).toBeLessThanOrEqual(total)
    // evolução: 12 meses terminando no mês de hoje, os do período marcados; os meses do período somam o total
    expect(p.evolucao_12m).toHaveLength(12)
    expect(p.evolucao_12m!.at(-1)!.mes).toBe('2026-10')
    expect(p.evolucao_12m!.filter((m) => m.no_periodo).map((m) => m.mes)).toEqual(['2026-07', '2026-08', '2026-09', '2026-10'])
    expect(p.evolucao_12m!.filter((m) => m.no_periodo).reduce((s, m) => s + m.total, 0)).toBe(total)
    // movimentação, comentários (mais recentes primeiro) e o pico (dos últimos 7 dias) dentro do período
    expect(p.movimentacao.itens.filter((m) => m.tipo === 'resgatado')).toHaveLength(p.movimentacao.resgatados)
    expect(p.movimentacao.itens.filter((m) => m.tipo !== 'resgatado')).toHaveLength(p.movimentacao.deixaram_de_ser_promotores)
    const datas = p.comentarios.map((c) => c.data)
    expect([...datas].sort().reverse()).toEqual(datas)
    expect(datas.every((d) => d.slice(0, 10) >= p.periodo.de! && d.slice(0, 10) <= hoje)).toBe(true)
    expect(p.picos![0]!.ate).toBe(hoje)
    expect(p.picos![0]!.reclamacoes).toBeLessThanOrEqual(p.temas.find((x) => x.chave === p.picos![0]!.tema)!.reclamacoes!)
    expect(p.primeiros_passos).toEqual({ contatos: true, envios_ligados: true, primeiro_envio: true, primeira_resposta: true })
    // o resumo da IA do exemplo cita os números do painel
    expect(RESUMO_IA_EXEMPLO.melhorar).toContain(`NPS para ${p.nps.valor}`)
    expect(RESUMO_IA_EXEMPLO.proximo_passo).toContain(`${p.atencao.detratores_sem_plano} empresas`)
  })

  it('a manchete do exemplo mostra o pico, a queda e a receita; e oferece criar os planos', () => {
    const p = painelExemplo('2026-10-04')
    const e: EntradaManchete = { nps: p.nps, variacao: p.variacao, diasAnteriores: 90, picos: p.picos, picosValem: true, atencao: p.atencao }
    const m = montarManchete(e)
    expect(textoDasPartes(m.titulo)).toBe('O NPS caiu 11 pontos. 5 reclamações de Prazo e entrega em 7 dias, quando a média era 1,2 por semana.')
    expect(textoDasPartes(m.apoio)).toBe('8 empresas tiveram detrator no período, somando R$ 92,2 mil por mês em contrato. 5 planos abertos, 1 vencido.')
    const acoes = acoesManchete(e, m, { podeVerRespostas: true, podeVerAcoes: true, toqqiAI: true, consultaNps: {}, podeTratarAcoes: true })
    expect(acoes.map((a) => a.rotulo)).toEqual(['Ver as 5 reclamações', 'Criar planos para 4 empresas', 'Ver o plano vencido'])
  })

  it('datas relativas: em outro dia, o período e os meses acompanham', () => {
    const p = painelExemplo('2027-03-31')
    expect(p.periodo.ate).toBe('2027-03-31')
    expect(p.evolucao_12m!.at(-1)!.mes).toBe('2027-03')
    expect(p.comentarios[0]!.data.startsWith('2027-03-30')).toBe(true)
  })
})

describe('tom dos comentários com a IA ligada', () => {
  const base = { analisados: 0, com_comentario: 12, pendentes: 0 }
  it('ligada e com comentários não lidos: "nao_lidos"; ligada sem nenhum que a IA leia: "curtos"', () => {
    expect(estadoTom({ ...base, ia_ligada: true, sem_analise: 12 })).toBe('nao_lidos')
    expect(estadoTom({ ...base, ia_ligada: true, sem_analise: 0 })).toBe('curtos')
  })
  it('desligada (ou servidor sem o campo): o convite de hoje; fila, dados e sem comentários continuam', () => {
    expect(estadoTom({ ...base, ia_ligada: false, sem_analise: 12 })).toBe('ligar')
    expect(estadoTom({ ...base, sem_analise: 12 })).toBe('ligar')
    expect(estadoTom({ ...base, ia_ligada: true, sem_analise: 12, pendentes: 3 })).toBe('analisando')
    expect(estadoTom({ ...base, ia_ligada: true, sem_analise: 4, analisados: 8 })).toBe('dados')
    expect(estadoTom({ ...base, com_comentario: 0, ia_ligada: true })).toBe('sem_comentarios')
  })
  it('o texto dos não lidos', () => {
    expect(textoNaoLidos(1)).toBe('1 comentário ainda não foi lido pela IA.')
    expect(textoNaoLidos(1234)).toBe('1.234 comentários ainda não foram lidos pela IA.')
  })
})

describe('planos para os detratores sem plano', () => {
  const p = painelExemplo('2026-10-04')
  const entrada = (semPlano: number, extra: Partial<EntradaManchete> = {}): EntradaManchete => ({
    nps: p.nps,
    variacao: null,
    diasAnteriores: null,
    picos: [],
    atencao: { ...p.atencao, acoes_abertas: 0, acoes_vencidas: 0, detratores_sem_plano: semPlano },
    ...extra,
  })
  const opcoes = { podeVerRespostas: true, podeVerAcoes: true, toqqiAI: false, consultaNps: { tipo_nota: 'nps' } }

  it('"Criar planos para N empresas" (ou "para 1 empresa") só com detrator sem plano e para quem trata planos', () => {
    let acoes = acoesManchete(entrada(3), { pico: null }, { ...opcoes, podeTratarAcoes: true })
    expect(acoes.map((a) => [a.tipo, a.rotulo])).toEqual([['criar_planos', 'Criar planos para 3 empresas'], ['detratores', 'Ver os detratores']])
    expect(acoes[0]!.para).toBeUndefined()
    acoes = acoesManchete(entrada(1), { pico: null }, { ...opcoes, podeTratarAcoes: true })
    expect(acoes[0]!.rotulo).toBe('Criar planos para 1 empresa')
    expect(acoesManchete(entrada(3), { pico: null }, { ...opcoes, podeTratarAcoes: false }).some((a) => a.tipo === 'criar_planos')).toBe(false)
    expect(acoesManchete(entrada(0), { pico: null }, { ...opcoes, podeTratarAcoes: true }).some((a) => a.tipo === 'criar_planos')).toBe(false)
    const { detratores_sem_plano: _x, ...antigo } = entrada(0).atencao
    expect(acoesManchete(entrada(0, { atencao: antigo }), { pico: null }, { ...opcoes, podeTratarAcoes: true }).some((a) => a.tipo === 'criar_planos')).toBe(false)
  })

  it('no máximo 3 botões: com pico e ToqqiAI, o ToqqiAI fica de fora', () => {
    const e = entrada(2, { picos: p.picos, picosValem: true })
    const m = montarManchete(e)
    const acoes = acoesManchete(e, m, { ...opcoes, toqqiAI: true, podeTratarAcoes: true })
    expect(acoes.map((a) => a.tipo)).toEqual(['pico', 'criar_planos', 'detratores'])
  })

  it('os textos do botão e do aviso', () => {
    expect(rotuloCriarPlanos(1)).toBe('Criar planos para 1 empresa')
    expect(rotuloCriarPlanos(1500)).toBe('Criar planos para 1.500 empresas')
    expect(textoPlanosCriados({ criadas: 1, restantes: 0 })).toBe('1 plano criado.')
    expect(textoPlanosCriados({ criadas: 4, restantes: 0 })).toBe('4 planos criados.')
    expect(textoPlanosCriados({ criadas: 100, restantes: 1 })).toBe('100 planos criados. Falta 1 empresa: use o botão de novo para criar os próximos.')
    expect(textoPlanosCriados({ criadas: 100, restantes: 20 })).toBe('100 planos criados. Faltam 20 empresas: use o botão de novo para criar os próximos.')
    expect(textoPlanosCriados({ criadas: 0, restantes: 0 })).toBe('Nenhum plano novo: as empresas com detrator já têm plano aberto.')
  })
})

describe('importação de respostas', () => {
  it('o aviso da IA nos importados', () => {
    expect(textoIaImportados(1)).toBe('A IA vai ler o comentário dos últimos 90 dias: o tom e os temas aparecem no Início em alguns minutos.')
    expect(textoIaImportados(12)).toBe('A IA vai ler os 12 comentários dos últimos 90 dias: o tom e os temas aparecem no Início em alguns minutos.')
    expect(textoIaImportados(1200)).toContain('os 1.200 comentários')
  })
})

// Etapa 5h (docs/api-etapa-5h.md §4 e §5): as regras puras da Plataforma — abas e endereços, indicadores e textos da
// Visão geral (dias, último acesso, conversão, ativação), busca, filtro e ordem das contas, e os textos de Erros.
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { ContaVisao, TotaisVisao } from '@/api/tipos'
import { nomeDoPlano } from '@/modulos/assinatura/logica'
import { ABAS_PLATAFORMA, abaPlataformaDaRota, caminhoDaAba } from '@/modulos/plataforma/abas'
import {
  FILTROS_ERROS_PADRAO,
  descricaoVazio,
  rotuloOrigem,
  temFiltroErros,
  textoConta,
  textoOcorrencias,
  textoTotalErros,
  textoVazio,
} from '@/modulos/plataforma/listaErros'
import {
  contasFiltradas,
  indicadores,
  opcoesSituacao,
  passosFeitos,
  rotuloAtivacao,
  rotuloSituacao,
  textoConversao,
  textoDiasRestantes,
  textoFalta,
  textoPlano,
  textoTaxa,
  textoUltimoAcesso,
  tomDiasRestantes,
} from '@/modulos/plataforma/visao'

const t = (s: string) => s.replace(/\u00a0/g, ' ')
const AGORA = new Date('2026-10-04T15:00:00-03:00')

beforeEach(() => vi.useFakeTimers({ now: AGORA, toFake: ['Date'] }))
afterEach(() => vi.useRealTimers())

describe('abas da Plataforma', () => {
  it('cinco, nesta ordem, cada uma com o seu endereço (Feedback desde docs/api-feedback.md)', () => {
    expect(ABAS_PLATAFORMA.map((a) => a.rotulo)).toEqual(['Visão geral', 'Contas', 'Parâmetros', 'Erros', 'Feedback'])
    expect(ABAS_PLATAFORMA.map((a) => caminhoDaAba(a.valor))).toEqual(['/plataforma', '/plataforma/contas', '/plataforma/parametros', '/plataforma/erros', '/plataforma/feedback'])
  })

  it('a aba do endereço: o parâmetro da rota, o último pedaço do caminho ou a Visão geral', () => {
    expect(abaPlataformaDaRota('erros')).toBe('erros')
    expect(abaPlataformaDaRota(['contas'])).toBe('contas')
    expect(abaPlataformaDaRota(undefined)).toBe('visao')
    expect(abaPlataformaDaRota('', '/plataforma')).toBe('visao')
    expect(abaPlataformaDaRota(undefined, '/plataforma/contas')).toBe('contas')
    expect(abaPlataformaDaRota(undefined, '/plataforma/erros/')).toBe('erros')
    expect(abaPlataformaDaRota('visao', '/plataforma/visao')).toBe('visao')
    expect(abaPlataformaDaRota('outra')).toBe('visao')
  })
})

describe('Visão geral: textos', () => {
  it('dias que faltam e a cor', () => {
    expect([0, 1, 2, 5, -1].map(textoDiasRestantes)).toEqual(['Acaba hoje', 'Acaba amanhã', 'Faltam 2 dias', 'Faltam 5 dias', 'Acaba hoje'])
    expect([0, 1, 2, 3, 4, 7].map(tomDiasRestantes)).toEqual(['erro', 'erro', 'atencao', 'atencao', 'info', 'info'])
  })

  it('último acesso: hoje, ontem, há N dias, a data depois de 30 dias, nunca', () => {
    expect(textoUltimoAcesso('2026-10-04T08:00:00-03:00')).toBe('Entrou hoje')
    expect(textoUltimoAcesso('2026-10-03T23:00:00-03:00')).toBe('Entrou ontem')
    expect(textoUltimoAcesso('2026-09-29T12:00:00-03:00')).toBe('Entrou há 5 dias')
    expect(textoUltimoAcesso('2026-09-04T12:00:00-03:00')).toBe('Entrou há 30 dias')
    expect(textoUltimoAcesso('2026-08-02T12:00:00-03:00')).toBe('Entrou em 02/08/2026')
    expect(textoUltimoAcesso(null)).toBe('Nunca entrou')
    expect(textoUltimoAcesso('não é data')).toBe('Nunca entrou')
  })

  it('taxa e conversão', () => {
    expect([0.75, 0, 1, 0.3333, null].map(textoTaxa)).toEqual(['75%', '0%', '100%', '33,3%', '—'])
    expect(textoConversao({ de: '2026-08-05', ate: '2026-09-19', contas: 1, assinaram: 1, taxa: 1 })).toBe('1 de 1 conta criada entre 05/08 e 19/09 assinou.')
    expect(textoConversao({ de: '2026-08-05', ate: '2026-09-19', contas: 12, assinaram: 0, taxa: 0 })).toBe('0 de 12 contas criadas entre 05/08 e 19/09 assinaram.')
    expect(textoConversao({ de: '2026-08-05', ate: '2026-09-19', contas: 0, assinaram: 0, taxa: null })).toBe('Nenhuma conta com teste criada entre 05/08 e 19/09.')
  })

  it('ativação: passos feitos, o que falta e o nome para o leitor de tela', () => {
    const a = (contatos: boolean, envios_ligados: boolean, primeiro_envio: boolean, primeira_resposta: boolean) => ({ contatos, envios_ligados, primeiro_envio, primeira_resposta })
    expect(passosFeitos(a(true, false, true, false))).toBe(2)
    expect(passosFeitos(null)).toBe(0)
    expect(textoFalta(a(true, true, true, true))).toBe('Ativação completa.')
    expect(textoFalta(a(false, false, false, false))).toBe('Nenhum passo feito.')
    expect(textoFalta(a(true, true, true, false))).toBe('Falta: primeira resposta.')
    expect(textoFalta(a(true, false, false, false))).toBe('Falta: envios ligados, primeiro envio e primeira resposta.')
    expect(rotuloAtivacao(a(false, false, false, false))).toBe('Ativação: 0 de 4.')
    expect(rotuloAtivacao(a(true, false, false, false))).toBe('Ativação: 1 de 4. Feitos: contatos.')
    expect(rotuloAtivacao(a(true, true, true, false))).toBe('Ativação: 3 de 4. Feitos: contatos, envios ligados e primeiro envio.')
  })

  it('situação: pausada e atrasada com as cores; as outras como no resto do app', () => {
    expect(rotuloSituacao('pausada')).toEqual({ rotulo: 'Pausada', tom: 'erro' })
    expect(rotuloSituacao('atrasada')).toEqual({ rotulo: 'Atrasada', tom: 'atencao' })
    expect(rotuloSituacao('teste')).toEqual({ rotulo: 'Em teste', tom: 'info' })
    expect(rotuloSituacao('teste_expirado').rotulo).toBe('Teste encerrado')
  })

  it('plano: com assinatura, o valor; sem, o plano da conta', () => {
    expect(t(textoPlano({ plano: 'essencial', assinatura: { plano: 'empresa', valor: '799.00' } }, nomeDoPlano))).toBe('Empresa · R$ 799,00/mês')
    expect(textoPlano({ plano: 'profissional', assinatura: null }, nomeDoPlano)).toBe('Profissional · sem assinatura')
    expect(textoPlano({ plano: null, assinatura: null }, nomeDoPlano)).toBe('Sem assinatura')
  })
})

describe('Visão geral: indicadores', () => {
  const totais = (extra: Partial<TotaisVisao> = {}): TotaisVisao => ({
    contas: 10,
    por_situacao: { teste: 4, teste_expirado: 0, ativa: 3, atrasada: 0, pausada: 0, cancelada: 2, cortesia: 1 },
    pagantes: 3,
    receita_mensal: '1047.00',
    ambiente: null,
    novas_7d: 0,
    novas_30d: 1,
    ...extra,
  })
  const conversao = { de: '2026-08-05', ate: '2026-09-19', contas: 0, assinaram: 0, taxa: null }

  it('seis, nesta ordem, com os textos de quando não há nada', () => {
    const lista = indicadores(totais({ pagantes: 0, receita_mensal: 0 }), conversao, 0)
    expect(lista.map((i) => i.rotulo)).toEqual(['Em teste', 'Pagantes', 'Receita mensal', 'Testes acabando em 7 dias', 'Novas em 30 dias', 'Conversão do teste'])
    expect(lista.map((i) => t(i.valor))).toEqual(['4', '0', 'R$ 0,00', '0', '1', '—'])
    expect(lista.map((i) => i.detalhe)).toEqual([
      'Nenhum teste encerrado sem assinar',
      'de 10 contas',
      'Nenhuma assinatura ativa',
      'Nenhum teste acaba nesta semana',
      '0 novas nos últimos 7 dias',
      'Nenhuma conta com teste criada entre 05/08 e 19/09.',
    ])
    expect(lista.some((i) => i.selo)).toBe(false)
  })

  it('o "sandbox" na receita e o âmbar quando há atraso ou testes acabando', () => {
    const lista = indicadores(totais({ ambiente: 'sandbox', por_situacao: { teste: 1, atrasada: 1, pausada: 2 } }), conversao, 2)
    const por = Object.fromEntries(lista.map((i) => [i.chave, i]))
    expect(por.receita!.selo).toBe('sandbox')
    expect(t(por.receita!.valor)).toBe('R$ 1.047,00')
    expect(por.pagantes!.detalhe).toBe('3 com fatura atrasada · 10 contas no total')
    expect([por.pagantes!.tom, por.pagantes!.tomDetalhe]).toEqual([undefined, 'atencao'])
    expect(por.acabando!.tom).toBe('atencao')
    expect(por.teste!.detalhe).toBe('Nenhum teste encerrado sem assinar')
    expect(indicadores(totais({ ambiente: 'producao' }), conversao, 0).find((i) => i.chave === 'receita')!.selo).toBeUndefined()
  })
})

describe('Visão geral: tabela das contas', () => {
  const c = (id: number, nome: string, extra: Partial<ContaVisao> = {}): ContaVisao => ({
    id,
    nome,
    situacao: 'teste',
    plano: 'profissional',
    criada_em: `2026-09-${String(10 + id).padStart(2, '0')}T12:00:00Z`,
    teste_ate: null,
    ultimo_acesso: null,
    usuarios: 1,
    admin_email: `adm${id}@x.com.br`,
    contatos_ativos: 0,
    convites_30d: 0,
    respostas_30d: 0,
    respostas_total: 0,
    ativacao: { contatos: false, envios_ligados: false, primeiro_envio: false, primeira_resposta: false },
    ia_analises_mes: 0,
    assinatura: null,
    ...extra,
  })
  const contas = [
    c(1, 'Ação Café', { ultimo_acesso: '2026-10-01T12:00:00Z', respostas_30d: 5, respostas_total: 9 }),
    c(2, 'Bento', { situacao: 'ativa', ultimo_acesso: '2026-10-03T12:00:00Z', respostas_30d: 5, respostas_total: 20 }),
    c(3, 'Cia', { situacao: 'nova_situacao', respostas_30d: 1 }),
    c(4, 'Dado', { situacao: 'pausada' }),
  ]
  const nomes = (l: ContaVisao[]) => l.map((x) => x.nome)

  it('ordens: último acesso (nunca entrou no fim, desempate pela mais nova), criação e respostas', () => {
    expect(nomes(contasFiltradas(contas, { busca: '', situacao: '', ordem: 'ultimo_acesso' }))).toEqual(['Bento', 'Ação Café', 'Dado', 'Cia'])
    expect(nomes(contasFiltradas(contas, { busca: '', situacao: '', ordem: 'criacao' }))).toEqual(['Dado', 'Cia', 'Bento', 'Ação Café'])
    expect(nomes(contasFiltradas(contas, { busca: '', situacao: '', ordem: 'respostas' }))).toEqual(['Bento', 'Ação Café', 'Cia', 'Dado'])
    expect(contas.map((x) => x.nome)).toEqual(['Ação Café', 'Bento', 'Cia', 'Dado']) // não muda a lista de entrada
  })

  it('busca sem acento e sem maiúsculas (nome ou e-mail) e situação', () => {
    expect(nomes(contasFiltradas(contas, { busca: '  acao ', situacao: '', ordem: 'criacao' }))).toEqual(['Ação Café'])
    expect(nomes(contasFiltradas(contas, { busca: 'ADM2@', situacao: '', ordem: 'criacao' }))).toEqual(['Bento'])
    expect(nomes(contasFiltradas(contas, { busca: '', situacao: 'pausada', ordem: 'criacao' }))).toEqual(['Dado'])
    expect(nomes(contasFiltradas(contas, { busca: 'bento', situacao: 'teste', ordem: 'criacao' }))).toEqual([])
  })

  it('opções de situação: só as que aparecem, na ordem das situações, com a contagem; desconhecida no fim', () => {
    expect(opcoesSituacao(contas)).toEqual([
      { valor: 'teste', rotulo: 'Em teste (1)' },
      { valor: 'ativa', rotulo: 'Ativa (1)' },
      { valor: 'pausada', rotulo: 'Pausada (1)' },
      { valor: 'nova_situacao', rotulo: 'Nova_situacao (1)' },
    ])
    expect(opcoesSituacao([])).toEqual([])
  })
})

describe('Erros: textos', () => {
  it('origem, ocorrências, total, conta e o aviso vazio', () => {
    expect([rotuloOrigem('api'), rotuloOrigem('site'), rotuloOrigem('tarefa'), rotuloOrigem('outra')]).toEqual([
      { rotulo: 'API', tom: 'info' },
      { rotulo: 'Site', tom: 'marca' },
      { rotulo: 'Tarefa', tom: 'neutro' },
      { rotulo: 'outra', tom: 'neutro' },
    ])
    expect([1, 2, 1250].map(textoOcorrencias).map(t)).toEqual(['1 vez', '2 vezes', '1.250 vezes'])
    expect(textoTotalErros(1, 'abertos')).toBe('1 erro aberto')
    expect(textoTotalErros(3, 'resolvidos')).toBe('3 erros resolvidos')
    expect(textoTotalErros(0, 'todos')).toBe('0 erros')
    expect(textoConta({ conta_id: 2, conta_nome: 'Alfa' })).toBe('Alfa')
    expect(textoConta({ conta_id: 9, conta_nome: null })).toBe('Conta 9 (excluída)')
    expect(textoConta({ conta_id: null, conta_nome: null })).toBeNull()
    expect(textoVazio(7)).toBe('Nenhum erro nos últimos 7 dias')
    expect(textoVazio(30)).toBe('Nenhum erro nos últimos 30 dias')
    expect(descricaoVazio(FILTROS_ERROS_PADRAO)).toBe('Nada aberto. Os erros da API, do site e das tarefas aparecem aqui assim que acontecem.')
    expect(descricaoVazio({ origem: 'site', situacao: 'resolvidos', dias: 30 })).toBe('Nenhum erro resolvido (Site) nesse período.')
    expect(descricaoVazio({ origem: '', situacao: 'todos', dias: 7 })).toBe('Os erros da API, do site e das tarefas aparecem aqui assim que acontecem.')
    expect(temFiltroErros(FILTROS_ERROS_PADRAO)).toBe(false)
    expect(temFiltroErros({ ...FILTROS_ERROS_PADRAO, dias: 30 })).toBe(true)
  })
})

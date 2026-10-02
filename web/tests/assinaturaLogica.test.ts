// Regras puras da assinatura (etapa 5a): datas em São Paulo, primeira fatura, avisos do topo, situação na tela,
// planos e limite, cobranças e o formulário de cobrança.
import { describe, expect, it } from 'vitest'
import type { EstadoAssinatura, PlanoAssinatura } from '@/api/tipos'
import {
  cabeNoPlano,
  chaveDoAviso,
  corpoCobranca,
  efeitoTroca,
  fimDoPeriodo,
  formCobrancaDe,
  linkDaCobranca,
  mensagemCancelamento,
  mensagemLimite,
  mesmosDadosCobranca,
  primeiroVencimento,
  proximoVencimento,
  resumoPrimeiraFatura,
  rotuloForma,
  rotuloLimite,
  situacaoCobranca,
  situacaoNaTela,
  textoDepois,
  textoPeriodo,
  textoDoAviso,
  faturaFutura,
  faturasPagas,
  mesmaFatura,
  ultimoDiaDoTeste,
  validarCobranca,
} from '@/modulos/assinatura/logica'

/** Intl usa espaço sem quebra em "R$ 349,00". */
const t = (s: string | null | undefined) => (s ?? '').replace(/ /g, ' ')
const AGORA = new Date('2026-10-01T12:00:00-03:00')

const PLANOS: PlanoAssinatura[] = [
  { chave: 'essencial', nome: 'Essencial', preco: '149.00', contatos: 300 },
  { chave: 'profissional', nome: 'Profissional', preco: '349.00', contatos: 1500 },
  { chave: 'empresa', nome: 'Empresa', preco: 799, contatos: null },
]
const [ESSENCIAL, PROFISSIONAL, EMPRESA] = PLANOS as [PlanoAssinatura, PlanoAssinatura, PlanoAssinatura]

function estado(parcial: Omit<Partial<EstadoAssinatura>, 'conta'> & { conta?: Partial<EstadoAssinatura['conta']> } = {}): EstadoAssinatura {
  return {
    contatos_ativos: 240,
    disponivel: true,
    planos: PLANOS,
    dados_sugeridos: { razao_social: null, documento: null, email_cobranca: null, telefone: null },
    assinatura: null,
    fatura_aberta: null,
    cobrancas: [],
    ...parcial,
    conta: { situacao: 'teste', plano: 'profissional', teste_ate: null, pago_ate: null, atrasada_desde: null, liberada: true, pausa_em: null, ...parcial.conta },
  }
}
const ASSINATURA = {
  plano: 'profissional',
  valor: '349.00',
  situacao: 'ativa',
  criada_em: '2026-10-01T15:00:00Z',
  cancelada_em: null,
  primeiro_vencimento: '2026-10-15',
  dados: { razao_social: 'Distribuidora Sol', documento: '11222333000181', email_cobranca: 'fin@sol.com.br', telefone: '5511987654321' },
}

describe('datas da assinatura (São Paulo)', () => {
  it('último dia do teste: o dia do fim; fim à meia-noite fica no dia anterior', () => {
    expect(ultimoDiaDoTeste('2026-10-15T14:30:00-03:00')).toBe('2026-10-15')
    expect(ultimoDiaDoTeste('2026-10-15T00:00:00-03:00')).toBe('2026-10-14')
    expect(ultimoDiaDoTeste('2026-10-15T03:00:00Z')).toBe('2026-10-14')
    expect(ultimoDiaDoTeste('2026-10-16T02:00:00Z')).toBe('2026-10-15')
    expect(ultimoDiaDoTeste('2026-10-15')).toBe('2026-10-15')
    expect(ultimoDiaDoTeste(null)).toBeNull()
  })

  it('primeira fatura: no último dia do teste, no dia seguinte ao período pago, o mais tarde dos dois ou amanhã', () => {
    expect(primeiroVencimento({ teste_ate: '2026-10-15T14:30:00-03:00', pago_ate: null }, AGORA)).toEqual({ data: '2026-10-15', motivo: 'teste' })
    expect(primeiroVencimento({ teste_ate: '2026-09-20T10:00:00-03:00', pago_ate: null }, AGORA)).toEqual({ data: '2026-10-02', motivo: 'amanha' })
    expect(primeiroVencimento({ teste_ate: null, pago_ate: '2026-11-14' }, AGORA)).toEqual({ data: '2026-11-15', motivo: 'pago' })
    expect(primeiroVencimento({ teste_ate: '2026-10-15T14:30:00-03:00', pago_ate: '2026-10-20' }, AGORA)).toEqual({ data: '2026-10-21', motivo: 'pago' })
    expect(primeiroVencimento({ teste_ate: null, pago_ate: '2026-09-30' }, AGORA)).toEqual({ data: '2026-10-02', motivo: 'amanha' })
    // Hoje é o último dia do período pago: ainda vale.
    expect(primeiroVencimento({ teste_ate: null, pago_ate: '2026-10-01' }, AGORA)).toEqual({ data: '2026-10-02', motivo: 'pago' })
  })

  it('"amanhã" é o de São Paulo, mesmo de noite (em UTC já é outro dia)', () => {
    const noite = new Date('2026-10-01T23:30:00-03:00')
    expect(primeiroVencimento({ teste_ate: null, pago_ate: null }, noite).data).toBe('2026-10-02')
  })

  it('depois, todo dia N (29 a 31 lembram dos meses mais curtos)', () => {
    expect(textoDepois('2026-10-15')).toBe('Depois, todo dia 15.')
    expect(textoDepois('2026-10-02')).toBe('Depois, todo dia 2.')
    expect(textoDepois('2026-10-31')).toBe('Depois, todo dia 31 (ou no último dia do mês, nos meses mais curtos).')
  })

  it('período coberto por uma fatura: do vencimento até a véspera do mesmo dia no mês seguinte (como o pago_ate)', () => {
    expect(fimDoPeriodo('2026-10-16')).toBe('2026-11-15')
    expect(fimDoPeriodo('2026-11-01')).toBe('2026-11-30')
    expect(fimDoPeriodo('2026-12-16')).toBe('2027-01-15')
    expect(fimDoPeriodo('2026-10-31')).toBe('2026-11-29') // 31/11 não existe: o mês seguinte começa em 30/11
    expect(fimDoPeriodo('2027-01-31')).toBe('2027-02-27')
    expect(fimDoPeriodo('2028-01-31')).toBe('2028-02-28') // ano bissexto
    expect(textoPeriodo('2026-10-16')).toBe('16/10 a 15/11/2026')
    expect(textoPeriodo('2026-12-01')).toBe('01/12 a 31/12/2026')
    expect(textoPeriodo('2026-12-16')).toBe('16/12/2026 a 15/01/2027')
    expect(textoPeriodo('2026-10-16', true)).toBe('16/10 a 15/11') // no histórico, logo abaixo do vencimento
    expect(textoPeriodo('2026-12-16', true)).toBe('16/12 a 15/01')
  })

  it('resumo da primeira fatura como no contrato', () => {
    const r = resumoPrimeiraFatura(PROFISSIONAL, { teste_ate: '2026-10-15T14:30:00-03:00', pago_ate: null }, AGORA)
    expect(t(r.texto)).toBe('Primeira fatura de R$ 349,00 com vencimento em 15/10/2026, no fim do teste. Ela cobre de 15/10 a 14/11/2026. Depois, todo dia 15.')
    expect(r.envios).toBeNull()
    const vencido = resumoPrimeiraFatura(ESSENCIAL, { teste_ate: '2026-09-20T10:00:00-03:00', pago_ate: null }, AGORA)
    expect(t(vencido.texto)).toBe('Primeira fatura de R$ 149,00 com vencimento amanhã, 02/10/2026. Ela cobre de 02/10 a 01/11/2026. Depois, todo dia 2.')
    expect(vencido.envios).toBe('Os envios voltam assim que o pagamento for confirmado: Pix e cartão em segundos, boleto em até 3 dias úteis.')
    const pago = resumoPrimeiraFatura(EMPRESA, { teste_ate: null, pago_ate: '2026-11-14' }, AGORA)
    expect(t(pago.texto)).toBe('Primeira fatura de R$ 799,00 com vencimento em 15/11/2026, no dia seguinte ao fim do período já pago. Ela cobre de 15/11 a 14/12/2026. Depois, todo dia 15.')
    const hoje = resumoPrimeiraFatura(PROFISSIONAL, { teste_ate: '2026-10-01T20:00:00-03:00', pago_ate: null }, AGORA)
    expect(t(hoje.texto)).toContain('com vencimento hoje, 01/10/2026, no fim do teste.')
  })
})

describe('aviso do topo das telas', () => {
  it('teste acabando: em N dias, amanhã ou hoje; pode ser fechado', () => {
    expect(textoDoAviso({ tipo: 'teste_acabando', data: '2026-10-04', dias: 3 })).toEqual({
      texto: 'Seu teste grátis termina em 3 dias.',
      tom: 'info',
      acao: 'escolher',
      dispensavel: true,
    })
    expect(textoDoAviso({ tipo: 'teste_acabando', data: '2026-10-02', dias: 1 })?.texto).toBe('Seu teste grátis termina amanhã.')
    expect(textoDoAviso({ tipo: 'teste_acabando', data: '2026-10-01', dias: 0 })).toMatchObject({ texto: 'Seu teste grátis termina hoje.', tom: 'atencao' })
  })

  it('teste encerrado, atrasada e pausada não podem ser fechados', () => {
    // já assinou: o lembrete da primeira fatura (no teste) ou o que falta para os envios voltarem (sem teste válido)
    expect(textoDoAviso({ tipo: 'aguardando_pagamento', data: '2026-10-15', dias: 5 }, { liberada: true })).toEqual({
      texto: 'A primeira fatura da assinatura vence em 15/10.',
      tom: 'info',
      acao: 'pagar',
      dispensavel: true,
    })
    expect(textoDoAviso({ tipo: 'aguardando_pagamento', data: '2026-10-02', dias: 1 }, { liberada: true })?.texto).toBe(
      'A primeira fatura da assinatura vence amanhã.',
    )
    expect(textoDoAviso({ tipo: 'aguardando_pagamento', data: '2026-10-02', dias: 1 }, { liberada: false })).toEqual({
      texto: 'Aguardando o pagamento da primeira fatura. Os envios voltam assim que ele for confirmado.',
      tom: 'atencao',
      acao: 'pagar',
      dispensavel: false,
    })
    expect(textoDoAviso({ tipo: 'teste_expirado', data: '2026-09-30', dias: null })).toEqual({
      texto: 'Seu teste grátis terminou. Os envios estão pausados; seus dados continuam guardados.',
      tom: 'atencao',
      acao: 'escolher',
      dispensavel: false,
    })
    const atrasada = textoDoAviso({ tipo: 'atrasada', data: '2026-10-18', dias: 5 }, { atrasada_desde: '2026-10-10' })
    expect(atrasada).toEqual({ texto: 'A fatura venceu em 10/10. Os envios param em 18/10 se ela não for paga.', tom: 'atencao', acao: 'pagar', dispensavel: false })
    expect(textoDoAviso({ tipo: 'atrasada', data: '2026-10-18', dias: 1 }, { atrasada_desde: '2026-10-10' })?.texto).toBe(
      'A fatura venceu em 10/10. Os envios param amanhã, 18/10, se ela não for paga.',
    )
    expect(textoDoAviso({ tipo: 'pausada', data: '2026-10-10', dias: null })).toMatchObject({
      texto: 'Envios pausados por falta de pagamento. Seus dados continuam guardados.',
      tom: 'erro',
      acao: 'pagar',
      dispensavel: false,
    })
  })

  it('cancelada (ainda no período pago) e cancelada encerrada', () => {
    expect(textoDoAviso({ tipo: 'cancelada', data: '2026-11-14', dias: 44 })).toEqual({
      texto: 'Assinatura cancelada. Você usa até 14/11.',
      tom: 'info',
      acao: 'escolher',
      dispensavel: true,
    })
    expect(textoDoAviso({ tipo: 'cancelada', data: '2026-10-01', dias: 0 })?.texto).toBe('Assinatura cancelada. Você usa até hoje.')
    expect(textoDoAviso({ tipo: 'cancelada_encerrada', data: '2026-09-14', dias: null })).toMatchObject({ acao: 'escolher', dispensavel: false, tom: 'atencao' })
  })

  it('sem aviso, nada; tipo desconhecido, um aviso genérico que leva à assinatura', () => {
    expect(textoDoAviso(null)).toBeNull()
    expect(textoDoAviso({ tipo: 'novidade', data: null, dias: null })).toMatchObject({ acao: 'ver', dispensavel: true })
  })

  it('a chave de "fechado" muda quando o aviso muda', () => {
    expect(chaveDoAviso({ tipo: 'teste_acabando', data: '2026-10-04', dias: 3 })).not.toBe(chaveDoAviso({ tipo: 'teste_acabando', data: '2026-10-04', dias: 2 }))
  })
})

describe('situação na tela de Assinatura', () => {
  it('sem assinatura: teste com a data de fim, teste encerrado e cancelada', () => {
    const teste = situacaoNaTela(estado({ conta: { teste_ate: '2026-10-15T14:30:00-03:00' } }), AGORA)
    expect(teste).toMatchObject({ rotulo: 'Em teste', titulo: 'Teste grátis até 15/10/2026' })
    expect(teste.descricao).toContain('Faltam 14 dias.')
    expect(situacaoNaTela(estado({ conta: { situacao: 'teste_expirado', teste_ate: '2026-09-20T10:00:00-03:00', liberada: false } }), AGORA)).toMatchObject({
      rotulo: 'Teste encerrado',
      titulo: 'Seu teste grátis terminou em 20/09/2026',
    })
    expect(situacaoNaTela(estado({ conta: { situacao: 'cancelada', pago_ate: '2026-11-14', liberada: true } }), AGORA).descricao).toContain('Você usa até 14/11/2026.')
    expect(situacaoNaTela(estado({ conta: { situacao: 'cancelada', pago_ate: '2026-09-14', liberada: false } }), AGORA).descricao).toContain('os envios estão pausados')
  })

  it('teste que já acabou e a API ainda não marcou: aparece como encerrado', () => {
    expect(situacaoNaTela(estado({ conta: { situacao: 'teste', teste_ate: '2026-09-30T10:00:00-03:00', liberada: false } }), AGORA)).toMatchObject({
      rotulo: 'Teste encerrado',
      titulo: 'Seu teste grátis terminou em 30/09/2026',
    })
  })

  it('com assinatura: ativa, atrasada, no teste e aguardando o primeiro pagamento', () => {
    expect(situacaoNaTela(estado({ assinatura: ASSINATURA, conta: { situacao: 'ativa', pago_ate: '2026-11-14' } }), AGORA)).toMatchObject({
      rotulo: 'Ativa',
      tom: 'sucesso',
      descricao: 'Pago até 14/11/2026.',
    })
    const atrasada = situacaoNaTela(
      estado({ assinatura: ASSINATURA, conta: { situacao: 'atrasada', atrasada_desde: '2026-10-10', pausa_em: '2026-10-18T03:00:00Z', liberada: true } }),
      AGORA,
    )
    expect(atrasada.descricao).toBe('A fatura venceu em 10/10/2026. Os envios param em 18/10/2026 se ela não for paga.')
    expect(situacaoNaTela(estado({ assinatura: ASSINATURA, conta: { situacao: 'atrasada', atrasada_desde: '2026-10-10', liberada: false } }), AGORA).titulo).toBe('Envios pausados')
    expect(situacaoNaTela(estado({ assinatura: ASSINATURA, conta: { teste_ate: '2026-10-15T14:30:00-03:00' } }), AGORA).descricao).toBe(
      'O teste vai até 15/10/2026. A primeira fatura vence em 15/10/2026.',
    )
    expect(situacaoNaTela(estado({ assinatura: ASSINATURA, conta: { situacao: 'teste_expirado', liberada: false } }), AGORA).rotulo).toBe('Aguardando pagamento')
    // Já pagou antes, cancelou, o período acabou e assinou de novo: a API devolve "cancelada" com assinatura.
    expect(situacaoNaTela(estado({ assinatura: ASSINATURA, conta: { situacao: 'cancelada', pago_ate: '2026-09-14', liberada: false } }), AGORA).rotulo).toBe(
      'Aguardando pagamento',
    )
  })

  it('cortesia não precisa assinar', () => {
    expect(situacaoNaTela(estado({ conta: { situacao: 'cortesia' } }), AGORA)).toMatchObject({ rotulo: 'Cortesia', tom: 'marca' })
  })
})

describe('planos e limite de contatos', () => {
  it('limite escrito, cabe ou não cabe, e o mesmo texto do 422 da API', () => {
    expect(rotuloLimite(1500)).toBe('Até 1.500 contatos ativos')
    expect(rotuloLimite(null)).toBe('Contatos ativos sem limite')
    expect(cabeNoPlano(ESSENCIAL, 300)).toBe(true)
    expect(cabeNoPlano(ESSENCIAL, 301)).toBe(false)
    expect(cabeNoPlano(EMPRESA, 90_000)).toBe(true)
    expect(mensagemLimite(ESSENCIAL, 320, 'trocar')).toBe('Você tem 320 contatos ativos; o plano Essencial permite até 300. Desative contatos antes de trocar.')
  })

  it('trocar de plano: novo valor, a fatura pendente muda junto, o limite e o aviso de contatos demais', () => {
    const e = estado({ assinatura: ASSINATURA, fatura_aberta: { valor: '349.00', vencimento: '2026-10-15', situacao: 'pendente', link: 'https://x' }, contatos_ativos: 320 })
    const maior = efeitoTroca(e, EMPRESA)
    expect(t(maior.valor)).toBe('O valor passa de R$ 349,00 para R$ 799,00 por mês.')
    // só a pendente muda junto (a vencida, não): o texto diz "pendente"
    expect(t(maior.fatura)).toBe('A fatura pendente, que vence em 15/10/2026, também passa para R$ 799,00.')
    expect(maior.limite).toBe('Os contatos ativos ficam sem limite (hoje você tem 320).')
    expect(maior.cabe).toBe(true)
    const menor = efeitoTroca(e, ESSENCIAL)
    expect(menor.cabe).toBe(false)
    expect(menor.aviso).toBe('Você tem 320 contatos ativos; o plano Essencial permite até 300. Desative contatos antes de trocar.')
    // Fatura vencida não muda de valor (a API só atualiza as pendentes).
    expect(efeitoTroca({ ...e, fatura_aberta: { ...e.fatura_aberta!, situacao: 'vencida' } }, EMPRESA).fatura).toBeNull()
  })
})

describe('faturas e cobranças', () => {
  it('situação, forma e link de cada cobrança', () => {
    expect(situacaoCobranca('pendente')).toEqual({ rotulo: 'Em aberto', tom: 'info' })
    expect(situacaoCobranca('removida').rotulo).toBe('Cancelada')
    expect(situacaoCobranca('nova').rotulo).toBe('nova')
    expect(rotuloForma({ forma: 'pix', situacao: 'paga' })).toBe('Pix')
    expect(rotuloForma({ forma: 'cartao', situacao: 'paga' })).toBe('Cartão')
    expect(rotuloForma({ forma: null, situacao: 'pendente' })).toBe('A escolher')
    expect(rotuloForma({ forma: null, situacao: 'removida' })).toBe('—')
    expect(linkDaCobranca({ link: 'https://asaas/f/1', situacao: 'paga' })).toBe('https://asaas/f/1')
    expect(linkDaCobranca({ link: 'https://asaas/f/1', situacao: 'removida' })).toBeNull()
  })

  it('próximo vencimento: o da pendente, o dia seguinte ao período pago ou o primeiro vencimento', () => {
    const base = { assinatura: ASSINATURA }
    expect(proximoVencimento(estado({ ...base, fatura_aberta: { valor: 1, vencimento: '2026-10-15', situacao: 'pendente', link: null } }), AGORA)).toBe('2026-10-15')
    expect(proximoVencimento(estado({ ...base, fatura_aberta: { valor: 1, vencimento: '2026-09-15', situacao: 'vencida', link: null } }), AGORA)).toBeNull()
    expect(proximoVencimento(estado({ ...base, conta: { situacao: 'ativa', pago_ate: '2026-11-14' } }), AGORA)).toBe('2026-11-15')
    expect(proximoVencimento(estado(base), AGORA)).toBe('2026-10-15')
    expect(proximoVencimento(estado(), AGORA)).toBeNull()
  })

  it('confirmação de cancelar: até quando usa, sem multa', () => {
    const aberta = { valor: 1, vencimento: '2026-11-15', situacao: 'pendente', link: null }
    expect(mensagemCancelamento(estado({ conta: { situacao: 'ativa', pago_ate: '2026-11-14' } }), AGORA)).toBe('Você continua usando até 14/11/2026. Sem multa e sem devolução.')
    expect(mensagemCancelamento(estado({ conta: { situacao: 'ativa', pago_ate: '2026-11-14' }, fatura_aberta: aberta }), AGORA)).toBe(
      'Você continua usando até 14/11/2026. Sem multa e sem devolução. A fatura em aberto é cancelada no Asaas.',
    )
    expect(mensagemCancelamento(estado({ conta: { teste_ate: '2026-10-15T14:30:00-03:00' } }), AGORA)).toBe('Você volta para o teste grátis, que vai até 15/10/2026. Sem multa.')
    expect(mensagemCancelamento(estado({ conta: { situacao: 'teste_expirado', liberada: false } }), AGORA)).toContain('Os envios ficam pausados')
  })
})

describe('formulário de cobrança', () => {
  it('dados da API → campos com máscara → corpo só com dígitos', () => {
    const f = formCobrancaDe(ASSINATURA.dados)
    expect(f).toEqual({ razao_social: 'Distribuidora Sol', documento: '11.222.333/0001-81', email_cobranca: 'fin@sol.com.br', telefone: '(11) 98765-4321' })
    expect(corpoCobranca({ ...f, razao_social: '  Distribuidora   Sol ' })).toEqual({
      razao_social: 'Distribuidora Sol',
      documento: '11222333000181',
      email_cobranca: 'fin@sol.com.br',
      telefone: '11987654321',
    })
    expect(formCobrancaDe(null)).toEqual({ razao_social: '', documento: '', email_cobranca: '', telefone: '' })
  })

  it('todos obrigatórios, com as mensagens da API', () => {
    expect(validarCobranca({ razao_social: ' ', documento: '', email_cobranca: '', telefone: '' })).toEqual({
      razao_social: 'Informe a razão social (ou o nome completo, para CPF).',
      documento: 'Informe o CPF ou o CNPJ.',
      email_cobranca: 'Informe o e-mail que recebe as faturas.',
      telefone: 'Informe o telefone com DDD.',
    })
    const erros = validarCobranca({ razao_social: 'x'.repeat(201), documento: '111.111.111-11', email_cobranca: 'fin@', telefone: '(01) 2345-6789' })
    expect(erros.razao_social).toBe('Use no máximo 200 caracteres.')
    expect(erros.documento).toBe('CNPJ ou CPF inválido. Confira os números.')
    expect(erros.email_cobranca).toBe('Informe um e-mail válido, como nome@empresa.com.br.')
    expect(erros.telefone).toBe('Informe o telefone com DDD, sem o zero da operadora.')
    expect(validarCobranca({ razao_social: 'Ana', documento: '529.982.247-25', email_cobranca: 'a@b.com', telefone: '+351912345678' }).telefone).toBe(
      'Informe um telefone do Brasil com DDD.',
    )
    expect(validarCobranca({ razao_social: 'Ana Souza', documento: '529.982.247-25', email_cobranca: 'ana@b.com', telefone: '(11) 98765-4321' })).toEqual({})
  })

  it('máscara, espaços, o 55 do telefone e maiúsculas no e-mail não contam como mudança', () => {
    const a = formCobrancaDe(ASSINATURA.dados)
    expect(mesmosDadosCobranca(a, { ...a, documento: '11222333000181', telefone: '11987654321', email_cobranca: 'FIN@sol.com.br ' })).toBe(true)
    expect(mesmosDadosCobranca(a, { ...a, telefone: '(11) 98765-0000' })).toBe(false)
  })
})

describe('pagamento com outra fatura já em aberto (o Asaas cria a do mês seguinte até 40 dias antes)', () => {
  const LINK1 = 'https://asaas.teste/i/1'
  const LINK2 = 'https://asaas.teste/i/2'
  const cob = (vencimento: string, situacao: string, link: string) => ({ valor: '349.00', vencimento, situacao, forma: null, pago_em: null, link })

  it('a fatura esperada aparece paga mesmo com a próxima em aberto', () => {
    const antes = [cob('2026-10-15', 'pendente', LINK1), cob('2026-11-15', 'pendente', LINK2)]
    const depois = [cob('2026-10-15', 'paga', LINK1), cob('2026-11-15', 'pendente', LINK2)]
    expect(faturasPagas(antes as never, depois as never).map((c) => c.link)).toEqual([LINK1])
    expect(mesmaFatura({ vencimento: '2026-10-15', link: LINK1 }, { vencimento: '2026-10-15', link: LINK2 })).toBe(false)
    expect(mesmaFatura({ vencimento: '2026-10-15', link: null } as never, { vencimento: '2026-10-15', link: null } as never)).toBe(true)
  })

  it('conta ativa com a pendente vencendo daqui a mais de 5 dias: é a "Próxima fatura", não "Pagar"', () => {
    const agora = new Date('2026-10-16T12:00:00-03:00')
    const conta = { situacao: 'ativa' } as never
    expect(faturaFutura({ conta, fatura_aberta: { valor: '349.00', vencimento: '2026-11-15', situacao: 'pendente', link: LINK2 } } as never, agora)).toBe(true)
    expect(faturaFutura({ conta, fatura_aberta: { valor: '349.00', vencimento: '2026-10-20', situacao: 'pendente', link: LINK2 } } as never, agora)).toBe(false)
    expect(faturaFutura({ conta: { situacao: 'atrasada' } as never, fatura_aberta: { valor: '349.00', vencimento: '2026-11-15', situacao: 'pendente', link: LINK2 } } as never, agora)).toBe(false)
  })
})

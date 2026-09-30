import { describe, expect, it } from 'vitest'
import { renderizarVariaveis } from '@/pesquisa/variaveis'

describe('renderizarVariaveis', () => {
  it('troca todas as variáveis', () => {
    expect(
      renderizarVariaveis('Olá, {nome}! A {empresa} quer saber sobre {assunto} ({referencia}).', {
        nome: 'Maria Souza',
        empresa: 'Transportes Rápido',
        assunto: 'a entrega de ontem',
        referencia: 'Pedido 123',
      }),
    ).toBe('Olá, Maria! A Transportes Rápido quer saber sobre a entrega de ontem (Pedido 123).')
  })

  it('{nome} usa só o primeiro nome', () => {
    expect(renderizarVariaveis('Oi {nome}', { nome: '  João Pedro da Silva ' })).toBe('Oi João')
  })

  it('{nome} vazio leva junto a vírgula e o espaço antes', () => {
    expect(renderizarVariaveis('Olá, {nome}!', {})).toBe('Olá!')
    expect(renderizarVariaveis('Olá, {nome}! Tudo bem?', { nome: '' })).toBe('Olá! Tudo bem?')
    expect(renderizarVariaveis('Obrigado {nome}.', { nome: '   ' })).toBe('Obrigado.')
    expect(renderizarVariaveis('Oi {nome}, tudo bem?', {})).toBe('Oi, tudo bem?')
  })

  it('{nome} vazio no começo não deixa vírgula solta e mantém a maiúscula', () => {
    expect(renderizarVariaveis('{nome}, como foi a entrega?', {})).toBe('Como foi a entrega?')
  })

  it('{assunto} vazio vira "o nosso atendimento"', () => {
    expect(renderizarVariaveis('Como você avalia {assunto}?', { assunto: '' })).toBe('Como você avalia o nosso atendimento?')
  })

  it('variáveis vazias não deixam espaço duplo; desconhecidas ficam como estão', () => {
    expect(renderizarVariaveis('Pedido {referencia} entregue', {})).toBe('Pedido entregue')
    expect(renderizarVariaveis('Valor {outra}', {})).toBe('Valor {outra}')
  })

  it('texto vazio ou nulo vira string vazia', () => {
    expect(renderizarVariaveis(null)).toBe('')
    expect(renderizarVariaveis(undefined)).toBe('')
  })
})

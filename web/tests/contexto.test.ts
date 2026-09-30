import { describe, expect, it } from 'vitest'
import { lerParametros, montarLinkComContexto } from '@/pesquisa/contexto'

describe('montarLinkComContexto', () => {
  it('sem valores devolve o link puro', () => {
    expect(montarLinkComContexto('https://app.toqqi.com/', 'Ab12Cd34')).toBe('https://app.toqqi.com/f/Ab12Cd34')
  })

  it('inclui só os campos preenchidos, na ordem dos campos, com ref no fim', () => {
    const url = montarLinkComContexto('https://app.toqqi.com', 'Ab12Cd34', {
      referencia: 'NF 99',
      motorista: 'João',
      pedido: ' 123 ',
      rota: 'Sul',
      filial: '',
    })
    expect(url).toBe('https://app.toqqi.com/f/Ab12Cd34?pedido=123&rota=Sul&motorista=Jo%C3%A3o&ref=NF+99')
  })

  it('canal vai primeiro quando informado', () => {
    expect(montarLinkComContexto('https://x.com', 'c', { canal: 'qr', pedido: '1' })).toBe('https://x.com/f/c?canal=qr&pedido=1')
  })

  it('o que monta, a página pública lê de volta', () => {
    const url = new URL(montarLinkComContexto('https://x.com', 'c', { pedido: '1', nota_fiscal: '55', transportadora: 'Veloz', referencia: 'R1' }))
    const p = lerParametros(url.search)
    expect(p.contexto).toEqual({ pedido: '1', nota_fiscal: '55', transportadora: 'Veloz' })
    expect(p.referencia).toBe('R1')
    expect(p.canal).toBe('link')
  })
})

describe('lerParametros', () => {
  it('lê nota, canal, embed e ignora valores estranhos', () => {
    expect(lerParametros('?nota=9&canal=widget&embed=1')).toMatchObject({ nota: 9, canal: 'widget', embed: true })
    expect(lerParametros('?nota=abc&canal=hack')).toMatchObject({ nota: null, canal: 'link', embed: false })
    expect(lerParametros('?nota=0').nota).toBe(0)
  })
})

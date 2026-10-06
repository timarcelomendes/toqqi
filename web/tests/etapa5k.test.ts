// Etapa 5k (docs/api-etapa-5k.md): a conta do valor de cada fatura (a mesma da API, com os mesmos exemplos de
// api/tests/test_planos_5k.py), os períodos do anual e o WhatsApp sem franquia.
import { describe, expect, it } from 'vitest'
import {
  TABELA_PADRAO,
  ajustarContatos,
  contatosValidos,
  nomePersonalizado,
  paraApi,
  precoPersonalizado,
  valorFatura,
} from '@/utils/precos'
import { exibido, fimDoPeriodo, planoPersonalizado, textoDepois, textoPeriodo } from '@/modulos/assinatura/logica'
import { avisoCanal, estadoFranquia, explicacaoFranquia } from '@/modulos/integracoes/logica'

const D = { pix: 3, anual: 10 }

describe('valor de cada fatura (igual à API)', () => {
  it.each([
    [14900, 'mensal', 'qualquer', '149.00'],
    [14900, 'mensal', 'pix', '144.53'],
    [34900, 'anual', 'qualquer', '3769.20'],
    [79900, 'mensal', 'pix', '775.03'],
    [39900, 'anual', 'qualquer', '4309.20'],
  ] as const)('%i por mês, %s, %s → %s', (mes, ciclo, forma, valor) => {
    expect(paraApi(valorFatura(mes, ciclo, forma, D))).toBe(valor)
  })

  it.each([
    [1500, 500, '399.00'],
    [5000, 2000, '874.00'],
    [10000, 2000, '1424.00'],
    [12000, 5000, '1674.00'],
    [100, 100, '117.00'],
    [2000, 500, '454.00'],
  ])('Personalizado com %i contatos e %i perguntas = %s', (contatos, cota, valor) => {
    expect(paraApi(precoPersonalizado(contatos, cota))).toBe(valor)
  })

  it('fora da tabela não tem preço; o campo arredonda para o passo e a faixa', () => {
    expect(precoPersonalizado(150, 100)).toBeNaN()
    expect(precoPersonalizado(200, 300)).toBeNaN()
    expect(contatosValidos(100_100)).toBe(false)
    expect(ajustarContatos(1234)).toBe(1200)
    expect(ajustarContatos(40)).toBe(100)
    expect(ajustarContatos(500_000)).toBe(100_000)
    expect(ajustarContatos(Number.NaN)).toBe(100)
    expect(nomePersonalizado(2000, 500)).toBe('Personalizado (2.000 contatos, 500 perguntas)')
  })

  it('a tabela vem da API (texto decimal) e muda a conta', () => {
    const t = { ...TABELA_PADRAO, base: '109.00', faixas: [{ ate: 1500, preco: '20.00' }, { ate: 10000, preco: '12.00' }, { ate: null, preco: '7.00' }] }
    expect(paraApi(precoPersonalizado(5000, 2000, t))).toBe('949.00') // 109 + 15×20 + 35×12 + 120
  })

  it('o plano exibido: Pix só no mensal; no anual, o preço cheio é 12 meses', () => {
    const p = { chave: 'essencial', nome: 'Essencial', preco: '149.00', contatos: 300 }
    expect(exibido(p, 'mensal', 'pix', D)).toMatchObject({ preco: '144.53', cheio: '149.00', forma: 'pix', ciclo: 'mensal' })
    expect(exibido(p, 'anual', 'pix', D)).toMatchObject({ preco: '1609.20', cheio: '1788.00', forma: 'qualquer', ciclo: 'anual' })
    expect(planoPersonalizado(TABELA_PADRAO, 1500, 500)).toEqual({
      chave: 'personalizado', nome: 'Personalizado (1.500 contatos, 500 perguntas)', preco: '399.00', contatos: 1500, cota_ia: 500,
    })
    expect(planoPersonalizado(TABELA_PADRAO, 150, 500)).toBeNull()
  })
})

describe('período do anual', () => {
  it('vencimento + 1 ano − 1 dia (29/02 → 27/02 do ano seguinte)', () => {
    expect(fimDoPeriodo('2026-10-15', 'anual')).toBe('2027-10-14')
    expect(fimDoPeriodo('2028-02-29', 'anual')).toBe('2029-02-27')
    expect(fimDoPeriodo('2026-10-15')).toBe('2026-11-14')
    expect(textoPeriodo('2026-10-15', true, 'anual')).toBe('15/10/2026 a 14/10/2027')
    expect(textoDepois('2026-10-15', 'anual')).toBe('Depois, todo ano em 15/10.')
  })
})

describe('WhatsApp sem franquia', () => {
  const sem = { plano: 'profissional', limite: null, usadas_mes: 1234, excedente_ativo: false, excedentes_mes: 0, valor_excedente: 1.5 }
  it('sem barra nem avisos; só conta as mensagens', () => {
    const e = estadoFranquia(sem)
    expect(e).toMatchObject({ semLimite: true, nivel: 'ok', usadas: 1234 })
    expect(e.resumo).toBe('1.234 mensagens no mês, sem franquia')
    expect(explicacaoFranquia(sem)).toContain('a Meta cobra cada mensagem direto da sua conta')
    expect(avisoCanal('whatsapp', { conectado: true, ativo: true, franquia: sem })).toBeNull()
  })
  it('com franquia, segue como antes', () => {
    const com = { ...sem, limite: 100, usadas_mes: 100 }
    expect(estadoFranquia(com)).toMatchObject({ semLimite: false, nivel: 'esgotada' })
    expect(avisoCanal('whatsapp', { conectado: true, ativo: true, franquia: com })).toContain('acabou')
  })
})

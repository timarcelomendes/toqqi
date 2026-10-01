import { describe, expect, it } from 'vitest'
import { situacaoContato, SITUACOES_CONTATO } from '@/utils/rotulos'
import {
  LIMITE_SELECAO,
  alternarPagina,
  alternarSelecao,
  estadoPagina,
  podeEnviarEmail,
  podeEnviarWhatsapp,
  situacaoEnvio,
  temEnviando,
  type Selecao,
} from '@/modulos/envios/logica'

describe('situação do contato em português simples', () => {
  it('usa os rótulos combinados com o cliente', () => {
    expect(situacaoContato('na_fila').rotulo).toBe('Na fila')
    expect(situacaoContato('aguardando').rotulo).toBe('Aguardando resposta')
    expect(situacaoContato('respondeu').rotulo).toBe('Respondeu')
    expect(situacaoContato('nao_saiu').rotulo).toBe('Não saiu')
    expect(situacaoContato('saiu_da_lista').rotulo).toBe('Saiu da lista')
    expect(situacaoContato('inativo').rotulo).toBe('Inativo')
    expect(situacaoContato('enviando').rotulo).toBe('Enviando...')
  })

  it('aguardando_intervalo mostra a data do próximo envio (dd/mm)', () => {
    expect(situacaoContato('aguardando_intervalo', { proximo_envio: '2026-03-12' }).rotulo).toBe('Próximo envio em 12/03')
    expect(situacaoContato('aguardando_intervalo', {}).rotulo).toBe(SITUACOES_CONTATO.aguardando_intervalo.rotulo)
  })

  it('"enviando: true" vale mais que a situação', () => {
    expect(situacaoContato('na_fila', { enviando: true }).rotulo).toBe('Enviando...')
  })

  it('nunca_enviado (etapa 2) vira "Na fila"; valor desconhecido aparece como veio', () => {
    expect(situacaoContato('nunca_enviado').rotulo).toBe('Na fila')
    expect(situacaoContato('outra_coisa')).toEqual({ rotulo: 'outra_coisa', tom: 'neutro' })
    expect(situacaoContato(null).rotulo).toBe('—')
  })

  it('cores: erro para "Não saiu", sucesso para "Respondeu"', () => {
    expect(situacaoContato('nao_saiu').tom).toBe('erro')
    expect(situacaoContato('respondeu').tom).toBe('sucesso')
  })
})

describe('situação de cada envio (histórico)', () => {
  it('traduz os valores da API', () => {
    expect(situacaoEnvio('pendente').rotulo).toBe('Enviando...')
    expect(situacaoEnvio('enviado').rotulo).toBe('Enviado')
    expect(situacaoEnvio('erro')).toEqual({ rotulo: 'Não saiu', tom: 'erro' })
    expect(situacaoEnvio('aberto_no_whatsapp').rotulo).toBe('Aberto no WhatsApp')
  })
})

describe('seleção com limite de 500', () => {
  const c = (id: number) => ({ id, nome: `Pessoa ${id}` })

  it('marca e desmarca', () => {
    const sel: Selecao = new Map()
    expect(alternarSelecao(sel, c(1))).toBe('adicionado')
    expect(sel.size).toBe(1)
    expect(alternarSelecao(sel, c(1))).toBe('removido')
    expect(sel.size).toBe(0)
  })

  it('não passa do limite', () => {
    const sel: Selecao = new Map()
    for (let i = 0; i < LIMITE_SELECAO; i++) alternarSelecao(sel, c(i))
    expect(sel.size).toBe(500)
    expect(alternarSelecao(sel, c(9999))).toBe('limite')
    expect(sel.size).toBe(500)
    // Desmarcar continua funcionando no limite.
    expect(alternarSelecao(sel, c(0))).toBe('removido')
  })

  it('marcar a página respeita o limite e diz quantos ficaram de fora', () => {
    const sel: Selecao = new Map()
    const pagina = Array.from({ length: 5 }, (_, i) => c(i))
    const r = alternarPagina(sel, pagina, 3)
    expect(r).toEqual({ adicionados: 3, removidos: 0, foraDoLimite: 2 })
    expect(estadoPagina(sel, pagina)).toBe('alguns')
  })

  it('marcar a página toda duas vezes desmarca', () => {
    const sel: Selecao = new Map()
    const pagina = [c(1), c(2)]
    alternarPagina(sel, pagina)
    expect(estadoPagina(sel, pagina)).toBe('todos')
    expect(alternarPagina(sel, pagina).removidos).toBe(2)
    expect(estadoPagina(sel, pagina)).toBe('nenhum')
  })

  it('ids número e texto são o mesmo contato', () => {
    const sel: Selecao = new Map()
    alternarSelecao(sel, { id: 7, nome: 'A' })
    expect(alternarSelecao(sel, { id: '7', nome: 'A' })).toBe('removido')
  })
})

describe('quem pode receber e atualização automática', () => {
  const base = { ativo: true, email: 'a@b.com', telefone: '5511999999999', situacao: 'na_fila' as const, enviando: false }

  it('e-mail: precisa estar ativo, com e-mail, na lista e não saindo agora', () => {
    expect(podeEnviarEmail(base)).toBe(true)
    expect(podeEnviarEmail({ ...base, email: null })).toBe(false)
    expect(podeEnviarEmail({ ...base, ativo: false })).toBe(false)
    expect(podeEnviarEmail({ ...base, situacao: 'saiu_da_lista' })).toBe(false)
    expect(podeEnviarEmail({ ...base, enviando: true })).toBe(false)
  })

  it('WhatsApp: precisa de telefone', () => {
    expect(podeEnviarWhatsapp(base)).toBe(true)
    expect(podeEnviarWhatsapp({ ...base, telefone: null })).toBe(false)
    expect(podeEnviarWhatsapp({ ...base, situacao: 'saiu_da_lista' })).toBe(false)
  })

  it('recarrega enquanto houver alguém saindo', () => {
    expect(temEnviando([{ enviando: false, situacao: 'na_fila' }])).toBe(false)
    expect(temEnviando([{ enviando: true, situacao: 'na_fila' }])).toBe(true)
    expect(temEnviando([{ enviando: false, situacao: 'enviando' }])).toBe(true)
  })
})

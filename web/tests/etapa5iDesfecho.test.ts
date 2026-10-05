// Etapa 5i, desfecho (versão enxuta): os motivos iguais aos da API, o selo da situação e os filtros da aba Desfecho
// (sem "só ativas": as perdidas são inativas).
import { describe, expect, it } from 'vitest'
import { MOTIVOS_PERDA, seloSituacao, situacaoEmpresa, textoMarco } from '@/modulos/contatos/desfecho'
import { desfechoParaApi, periodoPadrao } from '@/modulos/relatorios/logica'

describe('desfecho', () => {
  it('motivos na ordem da API', () => {
    expect(MOTIVOS_PERDA.map((m) => m.valor)).toEqual(['preco', 'concorrente', 'atendimento', 'produto', 'encerrou', 'outro'])
  })

  it('selo da situação', () => {
    expect(seloSituacao({ ativa: false, situacao: 'perdida', perdida_em: '2026-03-15' })).toEqual({ texto: 'Perdida em 15/03/2026', tom: 'erro' })
    expect(seloSituacao({ ativa: true, situacao: 'ativa' }).texto).toBe('Ativa')
    expect(seloSituacao({ ativa: false, situacao: 'pausada' }).texto).toBe('Inativa')
    expect(situacaoEmpresa({ ativa: false, perdida_em: '2026-01-01' })).toBe('perdida')
  })

  it('aba Desfecho: 12 meses e sem "só ativas"', () => {
    expect(periodoPadrao('desfecho')).toBe('365')
    const f = desfechoParaApi(
      { periodo: '365', de: '', ate: '', grupo_id: 3, so_ativos: true, segmento_id: '', responsavel_id: 7, faixa_valor: '', tempo_cliente: '' } as never,
      '2026-10-05',
    )
    expect(f).not.toHaveProperty('so_ativos')
    expect(f).toMatchObject({ grupo_id: 3, responsavel_id: 7, ate: '2026-10-05' })
  })
})

describe('linha do tempo da empresa', () => {
  const base = { id: 1, data: '2026-10-01', valor_antes: null, valor_depois: null, motivo: null, motivo_rotulo: null, motivo_detalhe: null, contatos: null, origem: 'tela', origem_rotulo: 'pela tela', usuario: { id: 1, nome: 'Ana' }, criado_em: '2026-10-01T10:00:00Z' }
  it('descreve entrada, valor, perda e retorno', () => {
    expect(textoMarco({ ...base, tipo: 'entrada', valor_depois: 1000 }).titulo).toMatch(/^Virou cliente com R\$\s1\.000,00 por mês$/)
    const v = textoMarco({ ...base, tipo: 'valor', valor_antes: 1000, valor_depois: 800 })
    expect(v.tom).toBe('atencao')
    const p = textoMarco({ ...base, tipo: 'perdida', motivo: 'preco', motivo_rotulo: 'Preço', contatos: 2, origem: 'api', origem_rotulo: 'pela integração', usuario: null })
    expect(p).toEqual({ titulo: 'Perdida (Preço)', detalhe: '2 contatos desativados · pela integração', tom: 'erro' })
    expect(textoMarco({ ...base, tipo: 'reativada' }).detalhe).toBe('Ana, pela tela')
  })
})

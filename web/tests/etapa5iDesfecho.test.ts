// Etapa 5i, desfecho (versão enxuta): os motivos iguais aos da API, o selo da situação e os filtros da aba Desfecho
// (sem "só ativas": as perdidas são inativas).
import { describe, expect, it } from 'vitest'
import { MOTIVOS_PERDA, seloSituacao, situacaoEmpresa } from '@/modulos/contatos/desfecho'
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

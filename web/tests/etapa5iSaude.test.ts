// Etapa 5i, saúde da conta: rótulos das faixas (Risco primeiro), o texto da renovação e o selo (ícone + texto + nota).
import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import SeloSaude from '@/modulos/saude/SeloSaude.vue'
import { FAIXAS_SAUDE, infoFaixa, textoRenova } from '@/modulos/saude/logica'

describe('saúde da conta', () => {
  it('faixas na ordem de prioridade', () => {
    expect(FAIXAS_SAUDE.map((f) => f.rotulo)).toEqual(['Risco', 'Atenção', 'Saudável', 'Sem dados'])
    expect(infoFaixa('risco').tom).toBe('erro')
  })

  it('texto da renovação', () => {
    expect([textoRenova(0), textoRenova(1), textoRenova(23)]).toEqual(['Renova hoje', 'Renova amanhã', 'Renova em 23 dias'])
  })

  it('selo com texto e nota (a cor não é a única pista)', () => {
    expect(mount(SeloSaude, { props: { faixa: 'risco', nota: 22 } }).text()).toBe('Risco · 22')
    expect(mount(SeloSaude, { props: { faixa: 'sem_dados', nota: null } }).text()).toBe('Sem dados')
    expect(mount(SeloSaude, { props: { faixa: 'saudavel', nota: 89 } }).find('svg').exists()).toBe(true)
  })
})

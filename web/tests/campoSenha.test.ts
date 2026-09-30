import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import { nextTick } from 'vue'
import CampoSenha from '@/components/ui/CampoSenha.vue'
import { gerarSenhaForte, senhaValida, verificarSenha } from '@/utils/senha'
import type { RegrasSenha } from '@/api/tipos'

const regras: RegrasSenha = { minimo: 8, maximo: 70, exige: ['maiuscula', 'numero', 'simbolo'] }

describe('regras de senha', () => {
  it('marca cada regra cumprida ou não', () => {
    const itens = verificarSenha('abc', regras)
    expect(itens.map((i) => [i.chave, i.ok])).toEqual([
      ['minimo', false],
      ['maiuscula', false],
      ['numero', false],
      ['simbolo', false],
    ])
    expect(senhaValida('Toqqi#2026', regras)).toBe(true)
  })

  it('só mostra a regra de máximo quando passa do limite', () => {
    expect(verificarSenha('A1!aaaaa', regras).some((i) => i.chave === 'maximo')).toBe(false)
    const longa = 'A1!' + 'a'.repeat(80)
    expect(verificarSenha(longa, regras).find((i) => i.chave === 'maximo')?.ok).toBe(false)
    expect(senhaValida(longa, regras)).toBe(false)
  })

  it('senha gerada sempre cumpre as regras', () => {
    for (let i = 0; i < 50; i++) expect(senhaValida(gerarSenhaForte(regras), regras)).toBe(true)
  })
})

describe('CampoSenha', () => {
  it('mostra a lista de regras e atualiza enquanto digita', async () => {
    const w = mount(CampoSenha, { props: { modelValue: '', comRegras: true, regras, 'onUpdate:modelValue': (v: string) => w.setProps({ modelValue: v }) } })
    const okDe = (chave: string) => w.find(`[data-regra="${chave}"]`).attributes('data-ok')
    expect(w.findAll('[data-regra]')).toHaveLength(4)
    expect(okDe('maiuscula')).toBe('false')

    await w.find('input').setValue('Senha')
    expect(okDe('maiuscula')).toBe('true')
    expect(okDe('minimo')).toBe('false')

    await w.find('input').setValue('Senha#123')
    expect(w.findAll('[data-ok="false"]')).toHaveLength(0)
  })

  it('emite valida=true só quando todas as regras batem', async () => {
    const w = mount(CampoSenha, { props: { modelValue: 'fraca', comRegras: true, regras } })
    await nextTick()
    // Começa inválida (padrão false): nada a emitir.
    expect(w.emitted('update:valida')).toBeUndefined()
    await w.setProps({ modelValue: 'Forte#2026' })
    expect(w.emitted('update:valida')?.at(-1)).toEqual([true])
    await w.setProps({ modelValue: 'Forte' })
    expect(w.emitted('update:valida')?.at(-1)).toEqual([false])
  })

  it('botão de mostrar/esconder troca o tipo do campo', async () => {
    const w = mount(CampoSenha, { props: { modelValue: 'x', regras } })
    expect(w.find('input').attributes('type')).toBe('password')
    await w.find('button').trigger('click')
    expect(w.find('input').attributes('type')).toBe('text')
    expect(w.find('button').attributes('aria-label')).toBe('Esconder senha')
  })
})

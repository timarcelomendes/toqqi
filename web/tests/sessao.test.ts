import { beforeEach, describe, expect, it } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { useSessaoStore } from '@/stores/sessao'
import type { Sessao } from '@/api/tipos'

function sessaoFalsa(permissoes: string[]): Sessao {
  return {
    token: 'tok-123',
    expira_em: new Date(Date.now() + 3_600_000).toISOString(),
    usuario: {
      id: 1,
      nome: 'Ana Souza',
      email: 'ana@transportes.com.br',
      cargo: 'Gerente',
      perfil: 'gestor',
      situacao: 'ativo',
      email_confirmado: true,
      ultimo_acesso: null,
      superadmin: false,
    },
    conta: { id: 9, nome: 'Transportes Sul', plano: null, situacao: 'teste', teste_ate: '2026-10-14' },
    permissoes,
  }
}

describe('sessão', () => {
  beforeEach(() => {
    localStorage.clear()
    sessionStorage.clear()
    setActivePinia(createPinia())
  })

  it('pode() responde conforme as permissões recebidas', () => {
    const s = useSessaoStore()
    expect(s.pode('contatos.ver')).toBe(false)
    s.definirSessao(sessaoFalsa(['contatos.ver', 'painel.ver']), false)
    expect(s.pode('contatos.ver')).toBe(true)
    expect(s.pode('painel.ver')).toBe(true)
    expect(s.pode('equipe.gerenciar')).toBe(false)
    expect(s.logado).toBe(true)
    expect(s.superadmin).toBe(false)
  })

  it('"lembrar" guarda no localStorage; sem lembrar, no sessionStorage', () => {
    const s = useSessaoStore()
    s.definirSessao(sessaoFalsa([]), true)
    expect(localStorage.getItem('toqqi.sessao')).toContain('tok-123')
    expect(sessionStorage.getItem('toqqi.sessao')).toBeNull()

    s.definirSessao(sessaoFalsa([]), false)
    expect(localStorage.getItem('toqqi.sessao')).toBeNull()
    expect(sessionStorage.getItem('toqqi.sessao')).toContain('tok-123')
  })

  it('limpar() apaga token, permissões e guarda a mensagem para a tela de entrar', () => {
    const s = useSessaoStore()
    s.definirSessao(sessaoFalsa(['auditoria.ver']), true)
    s.limpar('Sua sessão expirou.')
    expect(s.token).toBeNull()
    expect(s.logado).toBe(false)
    expect(s.pode('auditoria.ver')).toBe(false)
    expect(s.avisoEntrar).toBe('Sua sessão expirou.')
    expect(localStorage.getItem('toqqi.sessao')).toBeNull()
  })
})

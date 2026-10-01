import { describe, expect, it } from 'vitest'
import { itemAtivo, navegacaoPrincipal } from '@/layouts/navegacao'
import { router } from '@/router'

const item = (rotulo: string) => navegacaoPrincipal.find((i) => i.rotulo === rotulo)!

describe('menu e rotas da etapa 4a', () => {
  it('Respostas e Planos de ação saíram do "em breve" (Relatórios saiu na 4b)', () => {
    expect(item('Respostas').emBreve).toBeFalsy()
    expect(item('Planos de ação').emBreve).toBeFalsy()
    expect(item('Relatórios').emBreve).toBeFalsy()
  })

  it('cada rota nova pede a permissão certa', () => {
    expect(router.resolve('/respostas').meta.permissao).toBe('respostas.ver')
    const acao = router.resolve('/planos-de-acao/12')
    expect(acao.name).toBe('planos-de-acao')
    expect(acao.params.id).toBe('12')
    expect(acao.meta.permissao).toBe('acoes.ver')
    expect(router.resolve('/planos-de-acao').name).toBe('planos-de-acao')
    expect(router.resolve('/configuracoes/acoes').meta.permissao).toBe('acoes.ver')
    expect(router.resolve('/contatos/importar').meta.permissao).toBe('importacao.usar')
  })

  it('item marcado no menu: páginas de dentro e "importar respostas antigas" em Respostas', () => {
    expect(itemAtivo(item('Planos de ação'), '/planos-de-acao/12', {}, false)).toBe(true)
    expect(itemAtivo(item('Contatos'), '/contatos/importar', {}, false)).toBe(true)
    expect(itemAtivo(item('Contatos'), '/contatos/importar', { tipo: 'respostas' }, false)).toBe(false)
    expect(itemAtivo(item('Respostas'), '/contatos/importar', { tipo: 'respostas' }, false)).toBe(true)
    expect(itemAtivo(item('Respostas'), '/respostas', { analisar: '5' }, true)).toBe(true)
    expect(itemAtivo(item('Início'), '/respostas', {}, false)).toBe(false)
  })
})

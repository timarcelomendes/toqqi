// Auditoria › Atividades: o detalhe dos eventos da etapa 5f em português (docs/api-etapa-5f.md §2 a §6), com o
// genérico de sempre para os outros eventos e para as chaves desconhecidas; o tamanho de arquivo; e a tela usando isso.
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { enableAutoUnmount, flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { camposDetalhe, textoDetalhe, type CampoDetalhe } from '@/modulos/auditoria/detalhes'
import AbaAtividades from '@/modulos/auditoria/AbaAtividades.vue'
import { formatarTamanho } from '@/utils/formatos'
import { apiFalsa } from './apiFalsa'

/** As linhas como "Rótulo: valor" (o genérico marcado com *), para comparar de uma vez. */
const linhas = (evento: string, detalhe: Record<string, unknown> | string | null) =>
  camposDetalhe({ evento, detalhe }).map((c: CampoDetalhe) => `${c.generico ? '*' : ''}${c.rotulo}: ${c.valor}`)

describe('zona_risco {opcao, apagados, mantidos}', () => {
  it('Recomeçar do zero: opção pelo nome da tela, apagados na ordem de Dados da conta, com milhar e sem os zeros', () => {
    // A ordem das chaves é a do jsonb (por tamanho), como chegou no teste integrado
    const detalhe = {
      opcao: 'tudo',
      apagados: { acoes: 18, envios: 0, ofertas: 1, contatos: 1234, convites: 5678, empresas: 27, respostas: 15234, indicacoes: 2, csat_sem_contato: 340 },
      mantidos: { csat: 412, usuarios: 5, formularios: 3, descadastros: 12 },
    }
    expect(linhas('zona_risco', detalhe)).toEqual([
      'Opção: Recomeçar do zero',
      'Apagados: 27 empresas, 1.234 contatos, 15.234 respostas, 5.678 convites, 18 planos de ação, 2 indicações e 1 oferta',
      'Sem contato: 340 respostas CSAT',
      'Mantidos: 5 usuários, 3 formulários, 412 respostas CSAT e 12 na lista de descadastro',
    ])
  })

  it('Contatos e Respostas: singular, "Sem vínculo" das ações e nada para apagar', () => {
    expect(linhas('zona_risco', { opcao: 'contatos', apagados: { contatos: 1234, respostas: 5678, convites: 0, envios: 1, csat_sem_contato: 0 }, mantidos: { csat: 1, usuarios: 1, formularios: 1, descadastros: 0 } })).toEqual([
      'Opção: Contatos',
      'Apagados: 1.234 contatos, 5.678 respostas e 1 envio',
      'Mantidos: 1 usuário, 1 formulário e 1 resposta CSAT',
    ])
    expect(linhas('zona_risco', { opcao: 'respostas', apagados: { respostas: 1, acoes_sem_vinculo: 56 }, mantidos: {} })).toEqual([
      'Opção: Respostas',
      'Apagados: 1 resposta',
      'Sem vínculo: 56 planos de ação',
    ])
    expect(linhas('zona_risco', { opcao: 'respostas', apagados: { respostas: 0, acoes_sem_vinculo: 0 }, mantidos: { csat: 0 } })).toEqual([
      'Opção: Respostas',
      'Apagados: Nada (não havia o que apagar)',
    ])
  })

  it('chaves desconhecidas: contagem nova entra no fim da lista; chave nova no topo e formato inesperado vão para o genérico', () => {
    expect(linhas('zona_risco', { opcao: 'nova', apagados: { contatos: 2, pareceres_ia: 3 }, mantidos: { usuarios: 2 }, motivo: 'teste' })).toEqual([
      'Opção: nova',
      'Apagados: 2 contatos e 3 pareceres ia',
      'Mantidos: 2 usuários',
      '*motivo: teste',
    ])
    expect(linhas('zona_risco', { opcao: 'tudo', apagados: 'muitos', mantidos: { csat: 'x' } })).toEqual([
      'Opção: Recomeçar do zero',
      '*apagados: muitos',
      '*mantidos: {"csat":"x"}',
    ])
  })
})

describe('exportações', () => {
  it('exportacao_conta {arquivos, linhas, bytes}: arquivos, total de linhas e tamanho, nessa ordem', () => {
    const detalhe = { bytes: 1834567, linhas: { 'empresas.csv': 27, 'contatos.csv': 1234, 'respostas.csv': 15234, 'auditoria.csv': 456 }, arquivos: 21 }
    expect(linhas('exportacao_conta', detalhe)).toEqual(['Arquivos: 21', 'Linhas: 16.951, somando todas as planilhas', 'Tamanho: 1,7 MB'])
    expect(linhas('exportacao_conta', { arquivos: 21, linhas: 0, bytes: 900 })).toEqual(['Arquivos: 21', 'Linhas: 0', 'Tamanho: 900 bytes'])
  })

  it('exportacao_csv {lista, linhas}: o nome da aba e as linhas com milhar', () => {
    expect(linhas('exportacao_csv', { lista: 'contatos', linhas: 1234 })).toEqual(['Lista: Contatos', 'Linhas: 1.234'])
    expect(linhas('exportacao_csv', { lista: 'empresas', linhas: 1 })).toEqual(['Lista: Empresas', 'Linhas: 1'])
    expect(linhas('exportacao_csv', { lista: 'outra', linhas: 'x' })).toEqual(['Lista: outra', '*linhas: x'])
  })

  it('formatarTamanho: bytes, KB e MB como nas outras telas (1 KB = 1.024 bytes)', () => {
    expect(formatarTamanho(1)).toBe('1 byte')
    expect(formatarTamanho(512)).toBe('512 bytes')
    expect(formatarTamanho(2048)).toBe('2 KB')
    expect(formatarTamanho(870_810)).toBe('850,4 KB')
    expect(formatarTamanho(1_834_567)).toBe('1,7 MB')
    expect(formatarTamanho(1024 * 1024 - 1)).toBe('1 MB')
    expect(formatarTamanho(5 * 1024 ** 3)).toBe('5 GB')
    expect(formatarTamanho(Number.NaN)).toBe('—')
  })
})

describe('envio automático e lembretes', () => {
  it('envio_automatico {agendados, ignorados, executado_agora}', () => {
    expect(linhas('envio_automatico', { agendados: 1200, ignorados: 3, executado_agora: false })).toEqual([
      'Enviadas: 1.200 pesquisas',
      'Ficaram de fora: 3 contatos, pelas regras de envio',
      'Disparo: Sozinho, no horário de envio',
    ])
    expect(linhas('envio_automatico', { agendados: 0, ignorados: 0, executado_agora: true })).toEqual([
      'Enviadas: Nenhuma pesquisa',
      'Disparo: Na hora, pelo “Rodar envio automático agora”',
    ])
  })

  it('lembretes_automaticos {enviados, ignorados, executado_agora}', () => {
    expect(linhas('lembretes_automaticos', { enviados: 1, ignorados: 2, executado_agora: true })).toEqual([
      'Enviados: 1 lembrete',
      'Ficaram de fora: 2 lembretes, pelas regras de envio',
      'Disparo: Na hora, pelo “Enviar lembretes agora”',
    ])
  })
})

describe('integrações', () => {
  it('chave_regerada {prefixo, prefixo_anterior}: o começo das duas chaves, como código', () => {
    const campos = camposDetalhe({ evento: 'chave_regerada', detalhe: { prefixo: 'tq_live_Ab3x…', prefixo_anterior: 'tq_live_Zz9q' } })
    expect(campos).toEqual([
      { rotulo: 'Chave nova', valor: 'tq_live_Ab3x…', codigo: true },
      { rotulo: 'Chave anterior', valor: 'tq_live_Zz9q…', codigo: true },
    ])
  })

  it('webhooks: endereço, número e o que mudou (em português e na ordem do formulário)', () => {
    const url = 'https://erp.exemplo.com.br/avisos'
    expect(linhas('webhook_criado', { url, campos: ['url', 'eventos'], webhook_id: 3 })).toEqual([`Endereço: ${url}`, 'Webhook: nº 3'])
    expect(linhas('webhook_alterado', { campos: ['ativo', 'eventos', 'url'], webhook_id: 3 })).toEqual([
      'Webhook: nº 3',
      'O que mudou: Endereço, eventos e situação (ligado ou desligado)',
    ])
    expect(linhas('webhook_alterado', { campos: ['segredo'], webhook_id: 3 })).toEqual(['Webhook: nº 3', 'O que mudou: Segredo (um novo foi gerado)'])
    expect(linhas('webhook_excluido', { url, webhook_id: 3 })).toEqual([`Endereço: ${url}`, 'Webhook: nº 3'])
  })
})

describe('exclusao_avisada {exclusao_em, encerrada_em, admins}', () => {
  it('as datas em dd/mm/aaaa e quantos administradores foram avisados', () => {
    expect(linhas('exclusao_avisada', { admins: 2, exclusao_em: '2027-01-15', encerrada_em: '2026-10-17' })).toEqual([
      'Exclusão em: 15/01/2027',
      'Encerrada em: 17/10/2026',
      'Avisados: 2 administradores, por e-mail',
    ])
    expect(linhas('exclusao_avisada', { admins: 0, exclusao_em: 'amanhã', encerrada_em: '2026-10-17' })).toEqual([
      'Encerrada em: 17/10/2026',
      'Avisados: Nenhum administrador ativo',
      '*exclusao em: amanhã',
    ])
  })
})

describe('os outros eventos seguem o genérico de sempre', () => {
  it('chave com espaços no lugar de "_", valor como veio (objetos em JSON); texto e vazio', () => {
    expect(camposDetalhe({ evento: 'contato_excluido', detalhe: { nome: 'Rafael', email_antigo: 'r@x.com', campos: ['a'], extra: null } })).toEqual([
      { rotulo: 'nome', valor: 'Rafael', generico: true },
      { rotulo: 'email antigo', valor: 'r@x.com', generico: true },
      { rotulo: 'campos', valor: '["a"]', generico: true },
      { rotulo: 'extra', valor: 'null', generico: true },
    ])
    expect(camposDetalhe({ evento: 'zona_risco', detalhe: 'texto livre' })).toEqual([])
    expect(camposDetalhe({ evento: 'zona_risco', detalhe: null })).toEqual([])
    expect(textoDetalhe('Linha 1\nLinha 2')).toBe('Linha 1\nLinha 2')
    expect(textoDetalhe('')).toBeNull()
    expect(textoDetalhe({ a: 1 })).toBeNull()
  })
})

// ───────────────────────── Na tela ─────────────────────────

enableAutoUnmount(afterEach)
beforeEach(() => setActivePinia(createPinia()))
afterEach(() => {
  vi.unstubAllGlobals()
  document.body.innerHTML = ''
})

describe('Auditoria › Atividades: o detalhe aberto', () => {
  it('zona_risco em português (sem as iniciais forçadas) e o genérico com as iniciais em maiúscula, como antes', async () => {
    const item = (id: number, evento: string, detalhe: Record<string, unknown>) => ({
      id, criado_em: '2026-10-03T01:53:00-03:00', evento, rotulo: evento, gravidade: 'atencao', usuario: { id: 1, nome: 'Ana' }, detalhe, ip: null, grupo: 'exclusoes',
    })
    apiFalsa({
      'GET /auditoria': () => ({
        itens: [
          item(1, 'zona_risco', { opcao: 'contatos', apagados: { contatos: 1234, respostas: 5678 }, mantidos: { usuarios: 4 } }),
          item(2, 'contato_excluido', { nome_contato: 'Rafael' }),
        ],
        total: 2,
        pagina: 1,
        por_pagina: 20,
      }),
      'GET /auditoria/grupos': () => [{ chave: 'exclusoes', rotulo: 'Exclusões definitivas' }],
    })
    const w = mount(AbaAtividades, { attachTo: document.body })
    await flushPromises()
    for (const b of w.findAll('li > button[aria-expanded]')) await b.trigger('click')

    const pares = (id: number) => {
      const dts = w.get(`#detalhe-${id}`).findAll('dt')
      const dds = w.get(`#detalhe-${id}`).findAll('dd')
      return dts.map((dt, i) => ({ rotulo: dt.text(), valor: dds[i]!.text(), capitalize: dt.classes().includes('capitalize') }))
    }
    expect(pares(1).slice(0, 3)).toEqual([
      { rotulo: 'Opção', valor: 'Contatos', capitalize: false },
      { rotulo: 'Apagados', valor: '1.234 contatos e 5.678 respostas', capitalize: false },
      { rotulo: 'Mantidos', valor: '4 usuários', capitalize: false },
    ])
    expect(pares(1).map((p) => p.rotulo)).toEqual(['Opção', 'Apagados', 'Mantidos', 'Grupo', 'Evento'])
    expect(w.get('#detalhe-1').text()).not.toContain('{')
    expect(pares(2)[0]).toEqual({ rotulo: 'nome contato', valor: 'Rafael', capitalize: true })
  })
})

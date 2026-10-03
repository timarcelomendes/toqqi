import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import type { ConfigEnvios } from '@/api/tipos'
import {
  ajustarDiasLembretes,
  blocoNota,
  inserirNoCursor,
  montarPreviaEmail,
  normalizarCampos,
  paragrafos,
  renderizarMensagem,
  validarConfig,
} from '@/modulos/configuracoes/mensagens'
import PreviaEmail from '@/modulos/configuracoes/PreviaEmail.vue'

const config = (): ConfigEnvios => ({
  envios_ativos: true,
  envio_automatico: false,
  formulario_id: 1,
  intervalo_dias: 90,
  descanso_dias: 30,
  lembretes: 3,
  dias_lembretes: [3, 7, 15],
  janela_inicio: '08:00',
  janela_fim: '18:00',
  so_dias_uteis: true,
  responder_para: null,
  remetente_nome: null,
  assunto_convite: '{empresa} quer saber a sua opinião',
  texto_convite: 'Olá, {nome}!\n\nSua opinião ajuda a {empresa} a melhorar. Leva menos de um minuto.',
  assunto_lembrete: 'Lembrete: {empresa} quer saber a sua opinião',
  texto_lembrete: 'Olá, {nome}! Ainda dá tempo de responder...',
  texto_whatsapp: 'Olá, {nome}! Aqui é da {empresa}. Pode responder uma pesquisa rápida? Leva 1 minuto: {link}',
  agradecimento_ativo: true,
  agradecimento: { promotor: 'Obrigado!', neutro: 'Obrigado.', detrator: 'Sentimos muito.' },
})

describe('inserir variável no cursor', () => {
  it('insere na posição do cursor e devolve o cursor depois dela', () => {
    expect(inserirNoCursor('Olá, !', '{nome}', 5, 5)).toEqual({ texto: 'Olá, {nome}!', cursor: 11 })
  })

  it('substitui o trecho selecionado', () => {
    expect(inserirNoCursor('Olá, Fulano!', '{nome}', 5, 11)).toEqual({ texto: 'Olá, {nome}!', cursor: 11 })
  })

  it('sem posição conhecida, coloca no fim; posições fora do texto são corrigidas', () => {
    expect(inserirNoCursor('Link: ', '{link}')).toEqual({ texto: 'Link: {link}', cursor: 12 })
    expect(inserirNoCursor('abc', 'X', 99, 120).texto).toBe('abcX')
    expect(inserirNoCursor('abc', 'X', -5, null).texto).toBe('Xabc')
  })
})

describe('renderizar mensagem', () => {
  const vars = { nome: 'Maria Silva', empresa: 'Acme', empresa_cliente: 'Mercado Bom Preço', link: 'https://x/r/1', nota: 10 }

  it('troca {nome} (primeiro nome), {empresa}, {empresa_cliente}, {link} e {nota}', () => {
    expect(renderizarMensagem('Olá, {nome}! A {empresa} agradece a {empresa_cliente}. {link} Nota {nota}', vars)).toBe(
      'Olá, Maria! A Acme agradece a Mercado Bom Preço. https://x/r/1 Nota 10',
    )
  })

  it('{empresa_cliente} não é confundido com {empresa}', () => {
    expect(renderizarMensagem('{empresa_cliente}/{empresa}', vars)).toBe('Mercado Bom Preço/Acme')
  })

  it('{nome} vazio leva a vírgula antes', () => {
    expect(renderizarMensagem('Olá, {nome}!', {})).toBe('Olá!')
    expect(renderizarMensagem('{nome}, tudo bem?', {})).toBe('Tudo bem?')
  })

  it('mantém as quebras de linha e as variáveis desconhecidas', () => {
    expect(renderizarMensagem('Oi\n\n{outra}', {})).toBe('Oi\n\n{outra}')
  })

  it('parágrafos separados por linha em branco', () => {
    expect(paragrafos('Um\nainda um\n\n  \nDois')).toEqual(['Um\nainda um', 'Dois'])
  })
})

describe('prévia do e-mail', () => {
  const exemplo = { nome: 'Maria', empresa: 'Acme', empresa_cliente: 'Mercado' }

  it('NPS: 11 botões com as cores 0–6 vermelho, 7–8 amarelo, 9–10 verde', () => {
    const b = blocoNota('nps')
    expect(b.tipo).toBe('nps')
    if (b.tipo !== 'nps') return
    expect(b.botoes).toHaveLength(11)
    expect(b.botoes.filter((x) => x.cor === 'vermelho').map((x) => x.nota)).toEqual([0, 1, 2, 3, 4, 5, 6])
    expect(b.botoes.filter((x) => x.cor === 'amarelo').map((x) => x.nota)).toEqual([7, 8])
    expect(b.botoes.filter((x) => x.cor === 'verde').map((x) => x.nota)).toEqual([9, 10])
    expect([b.rotuloMin, b.rotuloMax]).toEqual(['Nada provável', 'Muito provável'])
  })

  it('CSAT: 5 botões com os rótulos padrão; personalizado: botão "Responder pesquisa"', () => {
    const csat = blocoNota('csat')
    expect(csat.tipo === 'csat' && csat.botoes.map((x) => x.nota)).toEqual([1, 2, 3, 4, 5])
    expect(csat.tipo === 'csat' && [csat.titulo, csat.rotuloMin, csat.rotuloMax]).toEqual(['', 'Muito insatisfeito', 'Muito satisfeito'])
    expect(blocoNota('personalizado')).toEqual({ tipo: 'botao', texto: 'Responder pesquisa' })
  })

  it('título e rótulos da pergunta principal, com as variáveis do formulário (como o bloco da nota da API)', () => {
    const p = { titulo: 'De 0 a 10, quanto você indicaria a {empresa}, {nome}?', rotulo_min: 'Jamais', rotulo_max: 'Com certeza' }
    const b = blocoNota('nps', p, { nome: 'Maria Souza', empresa: 'Acme' })
    expect(b.tipo === 'nps' && [b.titulo, b.rotuloMin, b.rotuloMax]).toEqual(['De 0 a 10, quanto você indicaria a Acme, Maria?', 'Jamais', 'Com certeza'])
    // rótulo vazio usa o padrão
    const c = blocoNota('csat', { titulo: 'Como foi?', rotulo_min: '', rotulo_max: null })
    expect(c.tipo === 'csat' && [c.titulo, c.rotuloMin, c.rotuloMax]).toEqual(['Como foi?', 'Muito insatisfeito', 'Muito satisfeito'])
  })

  it('monta remetente, assunto, parágrafos e rodapé', () => {
    const p = montarPreviaEmail(config(), 'convite', 'nps', exemplo)
    expect(p.de).toBe('Acme via Toqqi')
    expect(p.assunto).toBe('Acme quer saber a sua opinião')
    expect(p.paragrafos).toEqual(['Olá, Maria!', 'Sua opinião ajuda a Acme a melhorar. Leva menos de um minuto.'])
    expect(p.rodape).toBe('Você recebeu esta pesquisa porque é cliente de Acme.')
    expect(p.descadastro).toBe('Não quero mais receber pesquisas')
    expect(p.responderPara).toBeNull()
  })

  it('lembrete usa assunto e texto de lembrete; remetente próprio quando preenchido', () => {
    const p = montarPreviaEmail({ ...config(), remetente_nome: 'Loja Acme', responder_para: 'sac@acme.com' }, 'lembrete', 'nps', exemplo)
    expect(p.de).toBe('Loja Acme via Toqqi')
    expect(p.responderPara).toBe('sac@acme.com')
    expect(p.assunto).toBe('Lembrete: Acme quer saber a sua opinião')
  })

  it('o componente mostra os 11 botões coloridos e o link de sair da lista', () => {
    const w = mount(PreviaEmail, { props: { previa: montarPreviaEmail(config(), 'convite', 'nps', exemplo) } })
    const botoes = w.findAll('[data-cor]')
    expect(botoes).toHaveLength(11)
    expect(botoes[6]!.attributes('data-cor')).toBe('vermelho')
    expect(botoes[7]!.attributes('data-cor')).toBe('amarelo')
    expect(botoes[10]!.attributes('data-cor')).toBe('verde')
    expect(w.get('[data-teste="assunto"]').text()).toBe('Acme quer saber a sua opinião')
    expect(w.get('[data-teste="descadastro"]').text()).toBe('Não quero mais receber pesquisas')
    expect(w.find('[data-teste="logo"]').exists()).toBe(false) // sem logo, sem cabeçalho (como o e-mail real)
  })

  it('com logo, a prévia ganha o cabeçalho com a imagem (nome da empresa como texto alternativo)', () => {
    const logo = 'https://api.toqqi.com/api/v1/publico/imagens/abc'
    const p = montarPreviaEmail(config(), 'convite', 'nps', exemplo, logo)
    expect(p.logo).toBe(logo)
    const w = mount(PreviaEmail, { props: { previa: p, empresa: 'Acme' } })
    const img = w.get('[data-teste="logo"] img')
    expect(img.attributes('src')).toBe(logo)
    expect(img.attributes('alt')).toBe('Acme')
    expect(montarPreviaEmail(config(), 'convite', 'nps', exemplo, '').logo).toBeNull()
  })
})

describe('lembretes e conferência antes de salvar', () => {
  it('ajusta os dias ao número de lembretes, sempre crescentes', () => {
    expect(ajustarDiasLembretes([3, 7, 15], 1)).toEqual([3])
    expect(ajustarDiasLembretes([3], 3)).toEqual([3, 7, 15])
    expect(ajustarDiasLembretes([10], 2)).toEqual([10, 11])
    expect(ajustarDiasLembretes([], 0)).toEqual([])
    expect(ajustarDiasLembretes([29, 30], 3)).toEqual([29, 30, 30])
  })

  it('configuração padrão passa', () => {
    expect(validarConfig(config())).toEqual({})
  })

  it('aponta os problemas por campo', () => {
    const e = validarConfig({
      ...config(),
      intervalo_dias: 10,
      descanso_dias: 200,
      dias_lembretes: [7, 3, 15],
      janela_inicio: '18:00',
      janela_fim: '08:00',
      texto_whatsapp: 'Responda aí',
      responder_para: 'nao-e-email',
      assunto_convite: '',
      agradecimento: { promotor: '', neutro: 'ok', detrator: 'ok' },
    })
    expect(Object.keys(e).sort()).toEqual(
      [
        'agradecimento.promotor',
        'assunto_convite',
        'descanso_dias',
        'dias_lembretes',
        'intervalo_dias',
        'janela_fim',
        'responder_para',
        'texto_whatsapp',
      ].sort(),
    )
    expect(e.texto_whatsapp).toContain('{link}')
  })

  it('quantidade de dias diferente do número de lembretes', () => {
    expect(validarConfig({ ...config(), lembretes: 2, dias_lembretes: [3] }).dias_lembretes).toBeTruthy()
    expect(validarConfig({ ...config(), lembretes: 0, dias_lembretes: [] })).toEqual({})
  })

  it('agradecimento desligado não exige textos', () => {
    expect(validarConfig({ ...config(), agradecimento_ativo: false, agradecimento: { promotor: '', neutro: '', detrator: '' } })).toEqual({})
  })

  it('normaliza as chaves de erro da API', () => {
    expect(normalizarCampos({ 'dias_lembretes.1': 'x', 'agradecimento[promotor]': 'y', janela_fim: 'z' })).toEqual({
      dias_lembretes: 'x',
      'agradecimento.promotor': 'y',
      janela_fim: 'z',
    })
  })
})

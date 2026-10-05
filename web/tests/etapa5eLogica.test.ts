// Etapa 5e (docs/api-etapa-5e.md), regras puras: cor de destaque e contraste do texto do botão, conferência do visual,
// prévia do e-mail com o visual (ordem, cores, assinatura, rodapé, {motivo}), banco de imagens, Auditoria › E-mails
// enviados (abas, período, "Ver só as falhas") e a versão 3 da Política de privacidade.
import { describe, expect, it } from 'vitest'
import type { ConfigEnvios } from '@/api/tipos'
import {
  COR_PADRAO_EMAIL,
  SUGESTOES_COR_EMAIL,
  TEXTO_CLARO_BOTAO,
  TEXTO_ESCURO_BOTAO,
  alturaImagemTopo,
  contraste,
  corDestaque,
  corHexValida,
  corTextoBotao,
  normalizarCorHex,
  textoDimensoes,
  textoDoBotaoEscuro,
  textoOuNulo,
  validarVisual,
} from '@/modulos/configuracoes/visualEmail'
import { VARIAVEIS_AGRADECIMENTO, montarPreviaEmail, motivoEmUmaLinha, renderizarMensagem, validarConfig, type ConfigPrevia } from '@/modulos/configuracoes/mensagens'
import {
  bancoCheio,
  detalhesImagem,
  mensagemLimiteBanco,
  mesmaImagem,
  nomeImagem,
  paraImagemTopo,
  tamanhoArquivo,
  textoQuantidadeImagens,
} from '@/modulos/configuracoes/bancoImagens'
import {
  ABAS_AUDITORIA,
  FILTROS_EMAILS_PADRAO,
  TIPOS_EMAIL,
  abaAuditoriaDaRota,
  ehSoFalhas,
  erroPeriodoEmails,
  filtrosEmailsParaApi,
  filtrosSoFalhas,
  primeiroDiaGuardado,
  rotuloTipoEmail,
  situacaoEmail,
  temFiltroEmails,
  textoFalhas,
  textoTotalEmails,
} from '@/modulos/auditoria/emails'
import { conferirImagemBanco, LIMITE_IMAGEM_BANCO, MENSAGEM_IMAGEM_BANCO } from '@/utils/imagens'
import { PRIVACIDADE } from '@/modulos/geral/legal/privacidade'
import { VERSAO_DOCUMENTOS, VIGENTE_DESDE } from '@/modulos/geral/legal/versao'
import { textoVersao } from '@/modulos/geral/legal/aceite'

describe('cor de destaque e contraste do texto do botão', () => {
  it('lê #RRGGBB com ou sem "#", em maiúsculas ou minúsculas', () => {
    expect(normalizarCorHex('d63a18')).toBe('#D63A18')
    expect(normalizarCorHex('  #2563eb ')).toBe('#2563EB')
    expect(normalizarCorHex('#abc')).toBeNull()
    expect(normalizarCorHex('#GGGGGG')).toBeNull()
    expect(normalizarCorHex('')).toBeNull()
    expect(corHexValida('#d63a18')).toBe(true)
    expect(corHexValida('d63a18')).toBe(false)
    expect(corHexValida(null)).toBe(false)
  })

  it('contraste da WCAG: 21:1 entre preto e branco, 1:1 com a mesma cor', () => {
    expect(contraste('#000000', '#FFFFFF')).toBeCloseTo(21, 5)
    expect(contraste('#D63A18', '#D63A18')).toBeCloseTo(1, 5)
    expect(contraste('#D63A18', '#ffffff')).toBeGreaterThan(4.5) // o coral da marca leva texto branco
  })

  it('texto do botão: branco com contraste ≥ 4,5:1, senão #111827 (no limite: #767676 passa, #777777 não)', () => {
    expect(corTextoBotao('#D63A18')).toBe(TEXTO_CLARO_BOTAO)
    expect(corTextoBotao('#767676')).toBe(TEXTO_CLARO_BOTAO) // 4,54:1
    expect(corTextoBotao('#777777')).toBe(TEXTO_ESCURO_BOTAO) // 4,48:1
    expect(corTextoBotao('#FFD400')).toBe(TEXTO_ESCURO_BOTAO)
    expect(corTextoBotao('#ffffff')).toBe(TEXTO_ESCURO_BOTAO)
    expect(TEXTO_ESCURO_BOTAO).toBe('#111827')
    expect(textoDoBotaoEscuro('#FFD400')).toBe(true)
    expect(textoDoBotaoEscuro('#2563EB')).toBe(false)
    expect(textoDoBotaoEscuro(null)).toBe(false)
  })

  it('as 6 sugestões são válidas e todas levam texto branco', () => {
    expect(SUGESTOES_COR_EMAIL).toHaveLength(6)
    for (const s of SUGESTOES_COR_EMAIL) {
      expect(corHexValida(s.cor)).toBe(true)
      expect(corTextoBotao(s.cor)).toBe(TEXTO_CLARO_BOTAO)
    }
  })

  it('cor que vale: a da conta; sem ela, a do formulário; nenhuma válida, o coral #D63A18', () => {
    expect(corDestaque('#2563EB', '#E8501E')).toBe('#2563EB')
    expect(corDestaque(null, '#E8501E')).toBe('#E8501E')
    expect(corDestaque(undefined, 'vermelho')).toBe(COR_PADRAO_EMAIL)
    expect(corDestaque('ruim', null)).toBe(COR_PADRAO_EMAIL)
    expect(COR_PADRAO_EMAIL).toBe('#D63A18')
  })
})

describe('visual dos e-mails: conferência antes de salvar', () => {
  it('cor #RRGGBB ou nula; assinatura até 300 e rodapé até 500; só quebra de linha como controle', () => {
    expect(validarVisual({ email_cor: null, email_assinatura: 'Equipe Sol\n(11) 4000-0000', email_rodape: null })).toEqual({})
    expect(validarVisual({ email_cor: '#d63a18' })).toEqual({})
    expect(validarVisual({ email_cor: 'azul' }).email_cor).toBe('Use o formato #RRGGBB, por exemplo #D63A18.')
    expect(validarVisual({ email_assinatura: 'a'.repeat(300) })).toEqual({})
    expect(validarVisual({ email_assinatura: 'a'.repeat(301) }).email_assinatura).toBe('Use até 300 caracteres.')
    expect(validarVisual({ email_rodape: 'a'.repeat(501) }).email_rodape).toBe('Use até 500 caracteres.')
    expect(validarVisual({ email_rodape: 'Rua A\tnº 1' }).email_rodape).toMatch(/caracteres invisíveis/)
    expect(validarVisual({ email_rodape: 'Rua A\r\nnº 1' })).toEqual({})
    // API antiga (sem os campos do visual): passa
    expect(validarVisual({})).toEqual({})
  })

  it('validarConfig inclui o visual (mesmas chaves de `campos` da API)', () => {
    const base = {
      envios_ativos: false,
      envio_automatico: false,
      formulario_id: 1,
      intervalo_dias: 90,
      descanso_dias: 30,
      lembretes: 0,
      dias_lembretes: [],
      janela_inicio: '08:00',
      janela_fim: '18:00',
      so_dias_uteis: true,
      responder_para: null,
      remetente_nome: null,
      assunto_convite: 'Oi',
      texto_convite: 'Oi',
      assunto_lembrete: 'Oi',
      texto_lembrete: 'Oi',
      texto_whatsapp: 'Oi {link}',
      agradecimento_ativo: false,
      agradecimento: { promotor: '', neutro: '', detrator: '' },
    } satisfies Omit<ConfigEnvios, 'email_imagem_topo'>
    expect(validarConfig(base)).toEqual({})
    expect(Object.keys(validarConfig({ ...base, email_cor: '#12', email_assinatura: 'x'.repeat(301) }))).toEqual(['email_cor', 'email_assinatura'])
  })

  it('texto vazio vira null; dimensões e altura proporcional da imagem de topo (544 de largura)', () => {
    expect(textoOuNulo('  ')).toBeNull()
    expect(textoOuNulo(' Equipe ')).toBe('Equipe')
    expect(textoDimensoes(1200, 400)).toBe('1200 × 400 px')
    expect(textoDimensoes(null, 400)).toBeNull()
    expect(alturaImagemTopo(1200, 400)).toBe(181)
    expect(alturaImagemTopo(544, 100)).toBe(100)
    expect(alturaImagemTopo(null, null)).toBeNull()
    expect(alturaImagemTopo(1, 20000)).toBe(1088) // teto: o dobro da largura, como a API
    expect(alturaImagemTopo(20000, 1)).toBe(1)
  })
})

describe('prévia do e-mail com o visual (§2.2)', () => {
  const CONFIG: ConfigPrevia = {
    remetente_nome: null,
    responder_para: null,
    assunto_convite: 'Como foi com a {empresa}?',
    texto_convite: 'Olá, {nome}!\n\nConte como foi.',
    assunto_lembrete: 'Lembrete da {empresa}',
    texto_lembrete: 'Ainda dá tempo, {nome}.',
    agradecimento: { promotor: 'Obrigado pela nota {nota}, {nome}! Você disse: "{motivo}"', neutro: 'Valeu, {nome}.', detrator: 'Sentimos muito, {nome}.' },
    email_cor: null,
    email_mostrar_logo: true,
    email_imagem_topo: { id: 7, url: 'https://cdn.exemplo/topo.png', largura: 1200, altura: 400 },
    email_assinatura: 'Equipe Sol\n(11) 4000-0000\n\nAté logo!',
    email_rodape: 'Rua das Flores, 100\nSão Paulo (SP)',
  }
  const EXEMPLO = { nome: 'Maria Silva', empresa: 'Distribuidora Sol', empresa_cliente: 'Mercado Bom Preço' }

  it('convite: cor do formulário quando a conta não escolheu; logo, imagem de topo, assinatura e rodapé da conta', () => {
    const p = montarPreviaEmail(CONFIG, 'convite', 'nps', EXEMPLO, 'https://cdn.exemplo/logo.png', { temaCor: '#0E7490' })
    expect(p.cor).toBe('#0E7490')
    expect(p.corTextoBotao).toBe('#ffffff')
    expect(p.logo).toBe('https://cdn.exemplo/logo.png')
    expect(p.imagemTopo).toEqual({ url: 'https://cdn.exemplo/topo.png', largura: 1200, altura: 400 })
    expect(p.assunto).toBe('Como foi com a Distribuidora Sol?')
    expect(p.paragrafos).toEqual(['Olá, Maria!', 'Conte como foi.'])
    expect(p.bloco?.tipo).toBe('nps')
    // Assinatura: parágrafos (linha em branco), com as quebras simples dentro; texto puro, sem trocar variáveis
    expect(p.assinatura).toEqual(['Equipe Sol\n(11) 4000-0000', 'Até logo!'])
    expect(p.rodapeConta).toBe('Rua das Flores, 100\nSão Paulo (SP)')
    expect(p.rodape).toBe('Você recebeu esta pesquisa porque é cliente de Distribuidora Sol.')
    expect(p.descadastro).toBe('Não quero mais receber pesquisas')
  })

  it('a cor da conta vale mais que a do formulário; nenhuma válida → coral; cor clara → texto escuro no botão', () => {
    expect(montarPreviaEmail({ ...CONFIG, email_cor: '#2563EB' }, 'convite', 'nps', EXEMPLO, null, { temaCor: '#0E7490' }).cor).toBe('#2563EB')
    expect(montarPreviaEmail(CONFIG, 'convite', 'nps', EXEMPLO, null, { temaCor: 'ruim' }).cor).toBe('#D63A18')
    const clara = montarPreviaEmail({ ...CONFIG, email_cor: '#FFD400' }, 'convite', 'personalizado', EXEMPLO)
    expect(clara.bloco).toEqual({ tipo: 'botao', texto: 'Responder pesquisa' })
    expect(clara.corTextoBotao).toBe('#111827')
  })

  it('"Mostrar o logo" desligado tira o logo; sem imagem, assinatura e rodapé da conta, só as linhas fixas', () => {
    const p = montarPreviaEmail(
      { ...CONFIG, email_mostrar_logo: false, email_imagem_topo: null, email_assinatura: '   ', email_rodape: null },
      'lembrete',
      'csat',
      EXEMPLO,
      'https://cdn.exemplo/logo.png',
    )
    expect(p.logo).toBeNull()
    expect(p.imagemTopo).toBeNull()
    expect(p.assinatura).toEqual([])
    expect(p.rodapeConta).toBeNull()
    expect(p.rodape).toBe('Você recebeu esta pesquisa porque é cliente de Distribuidora Sol.')
    expect(p.descadastro).toBe('Não quero mais receber pesquisas')
    expect(p.assunto).toBe('Lembrete da Distribuidora Sol')
    expect(p.bloco?.tipo).toBe('csat')
  })

  it('a API antiga (sem os campos do visual) mostra o logo e a cor do formulário', () => {
    const visual = ['email_cor', 'email_mostrar_logo', 'email_imagem_topo', 'email_assinatura', 'email_rodape']
    const antiga = Object.fromEntries(Object.entries(CONFIG).filter(([k]) => !visual.includes(k))) as ConfigPrevia
    expect(Object.keys(antiga).some((k) => k.startsWith('email_'))).toBe(false)
    const p = montarPreviaEmail(antiga, 'convite', 'nps', EXEMPLO, 'https://cdn.exemplo/logo.png', { temaCor: '#047857' })
    expect([p.logo, p.cor, p.imagemTopo, p.assinatura, p.rodapeConta]).toEqual(['https://cdn.exemplo/logo.png', '#047857', null, [], null])
  })

  it('agradecimento: assunto fixo, {nota} e {motivo} de exemplo, sem bloco da nota, com o visual', () => {
    const p = montarPreviaEmail(CONFIG, 'agradecimento', 'nps', EXEMPLO, null, { temaCor: '#0E7490' })
    expect(p.assunto).toBe('Distribuidora Sol agradece a sua resposta')
    expect(p.paragrafos).toEqual(['Obrigado pela nota 10, Maria! Você disse: "O atendimento foi rápido e muito atencioso."'])
    expect(p.bloco).toBeNull()
    expect(p.cor).toBe('#0E7490')
    expect(p.assinatura).toHaveLength(2)
    expect(montarPreviaEmail(CONFIG, 'agradecimento', 'nps', EXEMPLO, null, { grupo: 'detrator' }).paragrafos).toEqual(['Sentimos muito, Maria.'])
    expect(montarPreviaEmail(CONFIG, 'agradecimento', 'nps', { empresa: '' }).assunto).toBe('Obrigado pela sua resposta')
  })

  it('{motivo}: o comentário numa linha, cortado em 200 caracteres; só no agradecimento', () => {
    expect(motivoEmUmaLinha('Entrega\n\natrasou   dois dias ')).toBe('Entrega atrasou dois dias')
    expect(motivoEmUmaLinha(null)).toBe('')
    expect(Array.from(motivoEmUmaLinha('😀'.repeat(250)))).toHaveLength(200)
    expect(renderizarMensagem('Você disse: {motivo}', { motivo: 'a'.repeat(300) })).toBe(`Você disse: ${'a'.repeat(200)}`)
    expect(VARIAVEIS_AGRADECIMENTO.map((v) => v.texto)).toEqual(['{nome}', '{empresa}', '{nota}', '{motivo}'])
  })

  it('um "$" no comentário não vira padrão de troca', () => {
    expect(renderizarMensagem('Você disse: {motivo}', { motivo: 'Paguei R$ 10 e $& e $1' })).toBe('Você disse: Paguei R$ 10 e $& e $1')
  })
})

describe('banco de imagens (§3 e §6.2)', () => {
  const imagem = { id: 3, url: 'https://api/publico/imagens/abc', nome: 'banner.png', tipo: 'image/png', tamanho: 250_000, largura: 1200, altura: 400, criada_em: '2026-10-01T12:00:00Z', em_uso: false }

  it('"X de 30 imagens", cheio no limite e a mesma mensagem da API', () => {
    expect(textoQuantidadeImagens(3, 30)).toBe('3 de 30 imagens')
    expect(bancoCheio(29, 30)).toBe(false)
    expect(bancoCheio(30, 30)).toBe(true)
    expect(mensagemLimiteBanco(30)).toBe('O banco de imagens tem até 30 imagens. Exclua uma para enviar outra.')
  })

  it('nome (ou a data), dimensões e tamanho', () => {
    expect(nomeImagem(imagem)).toBe('banner.png')
    expect(nomeImagem({ nome: null, criada_em: '2026-10-01T12:00:00Z' })).toBe('Imagem de 01/10/2026')
    expect(tamanhoArquivo(250_000)).toBe('244 KB')
    expect(tamanhoArquivo(1_048_576)).toBe('1,0 MB')
    expect(tamanhoArquivo(0)).toBeNull()
    expect(detalhesImagem(imagem)).toBe('1200 × 400 px · 244 KB')
    expect(detalhesImagem({ largura: null, altura: null, tamanho: 900 })).toBe('1 KB')
  })

  it('a escolhida vira a imagem de topo da configuração; ids comparados como texto', () => {
    expect(paraImagemTopo(imagem)).toEqual({ id: 3, url: 'https://api/publico/imagens/abc', largura: 1200, altura: 400 })
    expect(mesmaImagem({ id: 3 }, '3')).toBe(true)
    expect(mesmaImagem(null, 3)).toBe(false)
    expect(mesmaImagem({ id: 3 }, null)).toBe(false)
  })

  it('confere o arquivo antes de enviar: PNG/JPG pelos bytes, até 1 MB', async () => {
    const png = (n: number) => new File([new Uint8Array([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a, ...new Array(Math.max(0, n - 8)).fill(0)])], 'a.png', { type: 'image/png' })
    expect(await conferirImagemBanco(png(500_000))).toBeNull()
    expect(await conferirImagemBanco(png(LIMITE_IMAGEM_BANCO + 1))).toBe(MENSAGEM_IMAGEM_BANCO)
    expect(await conferirImagemBanco(new File(['GIF89a....'], 'a.png', { type: 'image/png' }))).toBe('Use uma imagem PNG ou JPG de até 1 MB.')
  })
})

describe('Auditoria › E-mails enviados (§5 e §6.3)', () => {
  const HOJE = '2026-10-02'

  it('abas: /auditoria/emails e ?aba=emails abrem os e-mails; o resto, as atividades', () => {
    expect(ABAS_AUDITORIA.map((a) => a.rotulo)).toEqual(['Atividades', 'E-mails enviados'])
    expect(abaAuditoriaDaRota('emails', undefined)).toBe('emails')
    expect(abaAuditoriaDaRota(undefined, 'emails')).toBe('emails')
    expect(abaAuditoriaDaRota('', ['emails'])).toBe('emails')
    expect(abaAuditoriaDaRota('atividades', undefined)).toBe('atividades')
    expect(abaAuditoriaDaRota(undefined, 'outra')).toBe('atividades')
  })

  it('período padrão: últimos 30 dias (com hoje); só manda os filtros preenchidos', () => {
    expect(filtrosEmailsParaApi(FILTROS_EMAILS_PADRAO, 1, HOJE)).toEqual({ de: '2026-09-03', ate: HOJE, pagina: 1 })
    expect(filtrosEmailsParaApi({ ...FILTROS_EMAILS_PADRAO, periodo: '90', tipo: 'convite', situacao: 'enviado', busca: '  maria ' }, 2, HOJE)).toEqual({
      de: '2026-07-05',
      ate: HOJE,
      tipo: 'convite',
      situacao: 'enviado',
      busca: 'maria',
      pagina: 2,
    })
    expect(filtrosEmailsParaApi({ ...FILTROS_EMAILS_PADRAO, periodo: 'personalizado', de: '2026-09-01', ate: '2026-09-10' }, 1, HOJE)).toMatchObject({
      de: '2026-09-01',
      ate: '2026-09-10',
    })
  })

  it('"Ver só as falhas": falhou nos últimos 7 dias, sem os outros filtros', () => {
    const f = filtrosSoFalhas()
    expect(filtrosEmailsParaApi(f, 1, HOJE)).toEqual({ de: '2026-09-26', ate: HOJE, situacao: 'falhou', pagina: 1 })
    expect(ehSoFalhas(f)).toBe(true)
    expect(ehSoFalhas({ ...f, tipo: 'convite' })).toBe(false)
    expect(temFiltroEmails(FILTROS_EMAILS_PADRAO)).toBe(false)
    expect(temFiltroEmails(f)).toBe(true)
  })

  it('datas escolhidas: as duas, a inicial antes da final, até hoje e dentro dos 90 dias guardados', () => {
    const p = (de: string, ate: string) => erroPeriodoEmails({ periodo: 'personalizado', de, ate }, HOJE)
    expect(primeiroDiaGuardado(HOJE)).toBe('2026-07-05')
    expect(p('2026-07-05', HOJE)).toBeNull()
    expect(p('2026-07-04', HOJE)).toBe('Guardamos só os últimos 90 dias. Escolha uma data inicial mais recente.')
    expect(p('2026-09-10', '2026-09-01')).toBe('A data inicial precisa ser antes da final.')
    expect(p('2026-09-10', '2026-10-03')).toBe('A data final não pode ser depois de hoje.')
    expect(p('', HOJE)).toBe('Escolha a data inicial.')
    expect(erroPeriodoEmails({ periodo: '30', de: '', ate: '' }, HOJE)).toBeNull()
  })

  it('textos: falhas, total, situação com etiqueta e o rótulo do tipo', () => {
    expect(textoFalhas(1)).toBe('1 e-mail falhou nos últimos 7 dias.')
    expect(textoFalhas(3)).toBe('3 e-mails falharam nos últimos 7 dias.')
    expect(textoTotalEmails(1)).toBe('1 e-mail')
    expect(textoTotalEmails(1234)).toBe('1.234 e-mails')
    expect(situacaoEmail('enviado')).toEqual({ rotulo: 'Enviado', tom: 'sucesso' })
    expect(situacaoEmail('falhou')).toEqual({ rotulo: 'Falhou', tom: 'erro' })
    expect(situacaoEmail('outra').tom).toBe('neutro')
    expect(rotuloTipoEmail({ tipo: 'teste', tipo_rotulo: 'E-mail de teste' })).toBe('E-mail de teste')
    expect(rotuloTipoEmail({ tipo: 'pico', tipo_rotulo: null })).toBe('Pico de reclamações')
    expect(rotuloTipoEmail({ tipo: 'novo_tipo' })).toBe('novo_tipo')
    // Boas-vindas e Cobrança ficam fora do filtro (nenhum e-mail sai com eles hoje); a linha que vier ainda tem rótulo
    expect(TIPOS_EMAIL).toHaveLength(12) // + retorno ao cliente (melhoria 4)
    expect(TIPOS_EMAIL.map((t) => t.valor)).not.toContain('boas_vindas')
    expect(rotuloTipoEmail({ tipo: 'cobranca', tipo_rotulo: 'Cobrança' })).toBe('Cobrança')
  })
})

describe('Política de privacidade (versão 3)', () => {
  const texto = JSON.stringify(PRIVACIDADE)

  it('versão 3, vigente desde 02/10/2026', () => {
    // Etapa 5f: a versão 4 veio por cima, vigente desde 03/10/2026 (ver etapa5fLogica.test.ts).
    expect(VERSAO_DOCUMENTOS).toBeGreaterThanOrEqual(3)
    expect(VIGENTE_DESDE >= '2026-10-02').toBe(true)
    expect(textoVersao(3, '2026-10-02')).toBe('Versão 3 · vigente desde 02/10/2026')
  })

  it('cita o registro de e-mails enviados: quem recebeu, assunto, situação, erro e 90 dias', () => {
    expect(texto).toContain('o endereço de quem recebeu, o assunto, a situação (enviado ou falhou), o erro')
    expect(texto).toContain('Auditoria › E-mails enviados')
    const retencao = JSON.stringify(PRIVACIDADE.secoes.find((s) => s.id === 'retencao'))
    expect(retencao).toContain('Registro de e-mails enviados (endereço de quem recebeu, assunto, situação e erro): 90 dias.')
  })
})

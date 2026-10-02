// Etapa 5c: regras puras do Crescimento (filtros ↔ endereço ↔ API, quem indicou, links, texto da oferta, edição de uma
// indicação), do cartão de indicação da pesquisa, de Configurações › Crescimento, do menu, do atalho e dos webhooks.
import { describe, expect, it } from 'vitest'
import type { Indicacao, Oportunidade } from '@/api/tipos'
import { atalhoPermitido } from '@/modulos/ajuda/atalhos'
import {
  aplicarMudancas,
  edicaoDaIndicacao,
  filtrosIndicacoesDaQuery,
  filtrosIndicacoesParaApi,
  filtrosOportunidadesDaQuery,
  filtrosOportunidadesParaApi,
  linhaVizinha,
  linkDaOferta,
  linkEmail,
  linkWhatsapp,
  mudancasIndicacao,
  queryDosFiltrosIndicacoes,
  queryDosFiltrosOportunidades,
  quemIndicou,
  semNomeDoIndicador,
  taxa,
  textoOferta,
  ultimaPaginaQueExiste,
  validarEdicaoIndicacao,
} from '@/modulos/crescimento/logica'
import { lerMoeda, partesEmail } from '@/utils/formatos'
import {
  PADRAO_CRESCIMENTO,
  normalizarConfigCrescimento,
  previaConvite,
  previaOferta,
  validarConfigCrescimento,
} from '@/modulos/configuracoes/configCrescimento'
import { VARIAVEIS_CONVITE_INDICACAO, VARIAVEIS_OFERTA } from '@/modulos/configuracoes/mensagens'
import { filtrarNavegacao, itemAtivo, navegacaoPrincipal } from '@/layouts/navegacao'
import {
  camposDoServidor,
  erroTelefoneIndicacao,
  lerConviteIndicacao,
  montarIndicacao,
  notaDaDireitoAIndicacao,
  validarIndicacao,
} from '@/pesquisa/indicacao'
import { EVENTOS_WEBHOOK, rotuloEventoWebhook } from '@/utils/rotulos'

const HOJE = '2026-10-02'

function indicacao(extra: Partial<Indicacao> = {}): Indicacao {
  return {
    id: 7,
    origem: 'pesquisa',
    nome: 'Juliana Prado',
    empresa: 'Empório Bela Vista',
    telefone: '5511987654321',
    email: 'juliana@bela.com.br',
    observacao: null,
    indicador: { contato: { id: 1, nome: 'Ana Souza' }, empresa: { id: 2, nome: 'Mercado Bom Preço' } },
    pode_identificar: true,
    responsavel: { id: 3, nome: 'Carla Ribeiro' },
    situacao: 'nova',
    valor_mensal: null,
    motivo: null,
    criada_em: '2026-10-01T10:00:00-03:00',
    atualizada_em: '2026-10-01T10:00:00-03:00',
    ...extra,
  }
}

describe('filtros de Indicações ↔ endereço ↔ API', () => {
  it('lê o endereço, ignora o que não vale e volta igual', () => {
    const f = filtrosIndicacoesDaQuery({ situacao: 'em_contato', responsavel_id: '3', periodo: '30', busca: '  Bela ', pagina: '2' })
    expect(f).toEqual({ situacao: 'em_contato', responsavel_id: '3', periodo: '30', de: '', ate: '', busca: 'Bela', pagina: 2 })
    expect(queryDosFiltrosIndicacoes(f)).toEqual({ situacao: 'em_contato', responsavel_id: '3', periodo: '30', busca: 'Bela', pagina: '2' })
    const ruim = filtrosIndicacoesDaQuery({ situacao: 'perdida', responsavel_id: '<script>', periodo: 'sempre', pagina: '-3' })
    expect(ruim).toMatchObject({ situacao: '', responsavel_id: '', periodo: 'tudo', pagina: 1 })
    expect(queryDosFiltrosIndicacoes(ruim)).toEqual({})
  })

  it('datas no endereço viram "escolher as datas"; para a API vão de/até (o preset vira intervalo)', () => {
    const f = filtrosIndicacoesDaQuery({ de: '2026-09-01', ate: '2026-09-30' })
    expect(f.periodo).toBe('personalizado')
    expect(filtrosIndicacoesParaApi(f, HOJE)).toEqual({ de: '2026-09-01', ate: '2026-09-30' })
    expect(filtrosIndicacoesParaApi({ ...f, periodo: '7', situacao: 'cliente', busca: 'x', pagina: 3 }, HOJE)).toEqual({
      situacao: 'cliente',
      de: '2026-09-26',
      ate: HOJE,
      busca: 'x',
      pagina: 3,
    })
  })

  it('Oportunidades: lista padrão "pode_crescer" fica fora do endereço; a API sempre recebe a lista', () => {
    const f = filtrosOportunidadesDaQuery({ lista: 'promotores', grupo_id: '2' })
    expect(queryDosFiltrosOportunidades(f)).toEqual({ lista: 'promotores', grupo_id: '2' })
    const padrao = filtrosOportunidadesDaQuery({ lista: 'qualquer' })
    expect(padrao.lista).toBe('pode_crescer')
    expect(queryDosFiltrosOportunidades(padrao)).toEqual({})
    expect(filtrosOportunidadesParaApi(padrao)).toEqual({ lista: 'pode_crescer' })
  })
})

describe('quem indicou, contato e oferta', () => {
  it('mostra a empresa e o nome, ou "Não quis se identificar"', () => {
    expect(quemIndicou(indicacao())).toBe('Mercado Bom Preço · Ana Souza')
    expect(quemIndicou(indicacao({ pode_identificar: false }))).toBe('Não quis se identificar')
    expect(quemIndicou(indicacao({ pode_identificar: false, indicador: { contato: null, empresa: null } }))).toBe('Não quis se identificar')
    expect(quemIndicou(indicacao({ origem: 'manual', indicador: { contato: null, empresa: null } }))).toBe('Não informado')
    expect(quemIndicou(indicacao({ origem: 'manual', pode_identificar: false, indicador: { contato: null, empresa: { id: 9, nome: 'Rede X' } } }))).toBe('Rede X')
    // Pela pesquisa, deixou dizer, mas o contato e a empresa de quem indicou foram apagados depois
    expect(quemIndicou(indicacao({ indicador: { contato: null, empresa: null } }))).toBe('Não informado (contato excluído)')
    expect(quemIndicou(indicacao({ indicador: { contato: null, empresa: { id: 2, nome: 'Mercado Bom Preço' } } }))).toBe('Mercado Bom Preço')
    // Sem o nome à vista, o texto da lista fica mais apagado
    expect(semNomeDoIndicador(indicacao())).toBe(false)
    expect(semNomeDoIndicador(indicacao({ pode_identificar: false }))).toBe(true)
    expect(semNomeDoIndicador(indicacao({ indicador: { contato: null, empresa: null } }))).toBe(true)
  })

  it('links: wa.me com o 55 e o texto codificado; mailto com assunto e corpo sem "+"', () => {
    expect(linkWhatsapp('11987654321')).toBe('https://wa.me/5511987654321')
    expect(linkWhatsapp('5511987654321', 'Olá, Ana! 50% & mais')).toBe('https://wa.me/5511987654321?text=Ol%C3%A1%2C%20Ana!%2050%25%20%26%20mais')
    expect(linkWhatsapp('123')).toBeNull()
    expect(linkWhatsapp(null)).toBeNull()
    expect(linkEmail('ana@x.com.br', 'Oi Ana', 'Linha 1\nLinha 2')).toBe('mailto:ana@x.com.br?subject=Oi%20Ana&body=Linha%201%0ALinha%202')
    expect(linkEmail('sem-arroba')).toBeNull()
  })

  it('texto da oferta troca as quatro variáveis (primeiro nome do contato e de quem oferece)', () => {
    const t = textoOferta(PADRAO_CRESCIMENTO.texto_oferta, {
      nome: 'Marcos Teixeira',
      empresa: 'Distribuidora Sol',
      empresa_cliente: 'Atacadão do Vale',
      representante: 'Ana Paula Ribeiro',
    })
    expect(t).toBe(
      'Olá, Marcos! Aqui é Ana, da Distribuidora Sol. Obrigado pela ótima avaliação! Preparei uma condição especial para a Atacadão do Vale. Posso te contar?',
    )
    expect(textoOferta('Oi, {nome}! {representante} aqui.', { nome: '', representante: 'Bia' })).toBe('Oi! Bia aqui.')
    expect(textoOferta('x'.repeat(2500), {})).toHaveLength(2000)
  })

  it('oferta sai pelo WhatsApp com telefone; só e-mail vira mailto; sem contato, nada', () => {
    const base: Oportunidade = {
      empresa: { id: 21, nome: 'Atacadão do Vale', valor_mensal: '3200.00' },
      grupo: null,
      responsavel: null,
      nps: { valor: 100, total: 4 },
      contato: { id: 201, nome: 'Marcos', telefone: '5511976543210', email: 'marcos@vale.com.br' },
      ultima_resposta: null,
      ultima_oferta: null,
    }
    expect(linkDaOferta(base, 'Oi')).toEqual({ canal: 'whatsapp', href: 'https://wa.me/5511976543210?text=Oi' })
    const soEmail = linkDaOferta({ ...base, contato: { ...base.contato!, telefone: null } }, 'Oi')
    expect(soEmail?.canal).toBe('email')
    expect(soEmail?.href).toBe('mailto:marcos@vale.com.br?subject=Uma%20condi%C3%A7%C3%A3o%20especial%20para%20a%20Atacad%C3%A3o%20do%20Vale&body=Oi')
    expect(linkDaOferta({ ...base, contato: null }, 'Oi')).toBeNull()
  })

  it('taxa em % inteiro calculada das contagens (meio para cima)', () => {
    expect(taxa(3, 12)).toBe(25)
    expect(taxa(1, 3)).toBe(33)
    expect(taxa(1, 8)).toBe(13)
    expect(taxa(0, 0)).toBeNull()
  })
})

describe('lista: página que ficou vazia e o foco quando uma linha sai', () => {
  it('volta para a última página que existe, sempre antes da atual', () => {
    expect(ultimaPaginaQueExiste(3, 100, 50)).toBe(2)
    expect(ultimaPaginaQueExiste(5, 53, 50)).toBe(2)
    expect(ultimaPaginaQueExiste(2, 0, 50)).toBe(1)
    // Total que não bate (a página atual "deveria" existir): mesmo assim volta uma, sem ficar indo e voltando
    expect(ultimaPaginaQueExiste(3, 500, 50)).toBe(2)
    expect(ultimaPaginaQueExiste(2, 10, 0)).toBe(1)
  })

  it('a linha seguinte que ficou; sem ela, a anterior; sem nenhuma, null (o título)', () => {
    const ordem = ['41', '40', '39']
    expect(linhaVizinha(ordem, '40', ['41', '39'])).toBe('39')
    expect(linhaVizinha(ordem, '39', ['41', '40'])).toBe('40')
    expect(linhaVizinha(ordem, '41', ['39'])).toBe('39')
    expect(linhaVizinha(ordem, '40', [])).toBeNull()
    // Nenhuma das antigas ficou (a página mudou): a primeira da lista nova
    expect(linhaVizinha(ordem, '40', ['12', '11'])).toBe('12')
  })
})

describe('valor digitado (lerMoeda): vírgula é decimal; ponto com 3 dígitos é milhar', () => {
  it('os casos comuns', () => {
    expect(lerMoeda('1.250')).toBe(1250)
    expect(lerMoeda('1.250,50')).toBe(1250.5)
    expect(lerMoeda('1250,5')).toBe(1250.5)
    expect(lerMoeda('12,5')).toBe(12.5)
    expect(lerMoeda('1.25')).toBe(1.25)
    expect(lerMoeda('1.250.000')).toBe(1250000)
    expect(lerMoeda('1.250.000,99')).toBe(1250000.99)
    expect(lerMoeda('R$ 1.250,00')).toBe(1250)
    expect(lerMoeda('R$ 30')).toBe(30)
    expect(lerMoeda('1250.5')).toBe(1250.5)
    expect(lerMoeda('1250')).toBe(1250)
    expect(lerMoeda('0,5')).toBe(0.5)
    expect(lerMoeda('-5')).toBe(-5)
  })

  it('ponto com 1, 2 ou mais de 3 dígitos é decimal; zero na frente não é milhar', () => {
    expect(lerMoeda('1.2')).toBe(1.2)
    expect(lerMoeda('12.50')).toBe(12.5)
    expect(lerMoeda('0.500')).toBe(0.5)
    expect(lerMoeda('1.2500')).toBe(1.25)
    expect(lerMoeda('10.000')).toBe(10000)
    expect(lerMoeda('999.999')).toBe(999999)
  })

  it('o que não dá para ler com certeza não vira número (a tela pede para conferir)', () => {
    expect(lerMoeda('')).toBeNull()
    expect(lerMoeda('abc')).toBeNull()
    expect(lerMoeda('1.2.3')).toBeNull()
    expect(lerMoeda('1.000.00')).toBeNull()
    expect(lerMoeda('1.25,50')).toBeNull()
    expect(lerMoeda('1,250.50')).toBeNull()
    expect(lerMoeda('1,2,3')).toBeNull()
  })

  it('o que formatarDecimal escreve volta igual (os campos se reformatam ao sair)', () => {
    for (const v of [0, 0.5, 12.5, 999.99, 1250, 1250.5, 1250000.99]) {
      expect(lerMoeda(new Intl.NumberFormat('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(v))).toBe(v)
    }
  })
})

describe('e-mail em partes (quebra depois do "@" e dos pontos)', () => {
  it('cada parte termina no "@" ou num ponto', () => {
    expect(partesEmail('sonia@padariaprado.com.br')).toEqual(['sonia@', 'padariaprado.', 'com.', 'br'])
    expect(partesEmail('ana.souza@x.io')).toEqual(['ana.', 'souza@', 'x.', 'io'])
    expect(partesEmail('semarroba')).toEqual(['semarroba'])
    expect(partesEmail(null)).toEqual([])
  })
})

describe('edição de uma indicação (PATCH só com o que mudou)', () => {
  it('virar cliente pede o valor mensal (pode ser 0) e manda a situação com o valor', () => {
    const i = indicacao()
    const e = { ...edicaoDaIndicacao(i), situacao: 'cliente' as const }
    expect(validarEdicaoIndicacao(e)).toEqual({ valor_mensal: 'Informe o valor mensal do novo cliente (pode ser 0).' })
    expect(validarEdicaoIndicacao({ ...e, valor_mensal: 'abc' }).valor_mensal).toBe('Digite um valor, ex.: 1.250,00.')
    expect(validarEdicaoIndicacao({ ...e, valor_mensal: '-5' }).valor_mensal).toBe('O valor não pode ser negativo.')
    expect(validarEdicaoIndicacao({ ...e, valor_mensal: '0' })).toEqual({})
    expect(mudancasIndicacao(i, { ...e, valor_mensal: '1.250,50' })).toEqual({ situacao: 'cliente', valor_mensal: 1250.5 })
    // Já cliente: mudar só o valor manda a situação junto
    const cliente = indicacao({ situacao: 'cliente', valor_mensal: '1250.50' })
    expect(edicaoDaIndicacao(cliente).valor_mensal).toBe('1.250,50')
    expect(mudancasIndicacao(cliente, edicaoDaIndicacao(cliente))).toEqual({})
    expect(mudancasIndicacao(cliente, { ...edicaoDaIndicacao(cliente), valor_mensal: '2.000,00' })).toEqual({ situacao: 'cliente', valor_mensal: 2000 })
  })

  it('não avançar manda o motivo (até 300); outras situações não mandam valor nem motivo; responsável vazio vira null', () => {
    const i = indicacao()
    const e = { ...edicaoDaIndicacao(i), situacao: 'nao_avancou' as const, motivo: '  Já tem fornecedor. ' }
    expect(mudancasIndicacao(i, e)).toEqual({ situacao: 'nao_avancou', motivo: 'Já tem fornecedor.' })
    expect(validarEdicaoIndicacao({ ...e, motivo: 'x'.repeat(301) })).toEqual({ motivo: 'Use até 300 caracteres.' })
    expect(mudancasIndicacao(indicacao({ situacao: 'cliente', valor_mensal: 10 }), { ...edicaoDaIndicacao(i), situacao: 'em_contato' })).toEqual({ situacao: 'em_contato' })
    expect(mudancasIndicacao(i, { ...edicaoDaIndicacao(i), responsavel_id: '' })).toEqual({ responsavel_id: null })
  })

  it('sem corpo na resposta, a lista aplica o que mudou (o valor some fora de "cliente")', () => {
    const cliente = indicacao({ situacao: 'cliente', valor_mensal: '900.00' })
    const r = aplicarMudancas(cliente, { situacao: 'em_contato', responsavel_id: 4 }, { id: 4, nome: 'Diego' })
    expect(r).toMatchObject({ situacao: 'em_contato', valor_mensal: null, responsavel: { id: 4, nome: 'Diego' } })
  })
})

describe('cartão de indicação da pesquisa (regras do contrato)', () => {
  const vazio = { nome: '', empresa: '', telefone: '', email: '', observacao: '' }

  it('nome de 2 a 120, telefone brasileiro ou e-mail (pelo menos um), observação até 500 e a confirmação', () => {
    expect(validarIndicacao(vazio, { confirmo: false })).toEqual({
      nome: 'Informe o nome de quem você indica.',
      telefone: 'Informe o WhatsApp ou o e-mail (pelo menos um dos dois).',
      confirmo: 'Marque a confirmação para enviar.',
    })
    expect(validarIndicacao({ ...vazio, nome: 'A', email: 'x@y' }).nome).toBe('O nome precisa ter pelo menos 2 letras.')
    expect(validarIndicacao({ ...vazio, nome: 'Ana', email: 'x@y' }).email).toBe('Confira o e-mail: parece que falta alguma parte.')
    expect(validarIndicacao({ ...vazio, nome: 'x'.repeat(121), telefone: '(11) 91234-5678' }).nome).toBe('Use até 120 caracteres.')
    expect(validarIndicacao({ ...vazio, nome: 'Ana', telefone: '(11) 91234-5678', observacao: 'x'.repeat(501) })).toEqual({ observacao: 'Use até 500 caracteres.' })
    expect(validarIndicacao({ ...vazio, nome: 'Ana', telefone: '(11) 91234-5678' }, { confirmo: true })).toEqual({})
    expect(erroTelefoneIndicacao('(01) 2345-6789')).toBe('Informe o DDD sem o zero da operadora.')
    expect(erroTelefoneIndicacao('12345')).toBe('Informe DDD e número, ex.: (11) 91234-5678.')
    expect(erroTelefoneIndicacao('+55 11 91234-5678')).toBeNull()
  })

  it('o corpo vai com textos limpos, telefone só com dígitos e vazios como null', () => {
    expect(montarIndicacao({ nome: '  Juliana\u0007 Prado ', empresa: ' ', telefone: '(11) 98765-4321', email: '', observacao: ' Linha 1\r\nLinha 2 ' }, false, true)).toEqual({
      nome: 'Juliana Prado',
      empresa: null,
      telefone: '11987654321',
      email: null,
      observacao: 'Linha 1\nLinha 2',
      pode_identificar: false,
      confirmo: true,
    })
  })

  it('só promotor (NPS 9–10) ou CSAT 5 dá direito; o convite da API só vale com texto', () => {
    expect([8, 9, 10].map((n) => notaDaDireitoAIndicacao('nps', n))).toEqual([false, true, true])
    expect([4, 5].map((n) => notaDaDireitoAIndicacao('csat', n))).toEqual([false, true])
    expect(notaDaDireitoAIndicacao('estrelas', 5)).toBe(true)
    expect(notaDaDireitoAIndicacao('escala', 10)).toBe(false)
    expect(lerConviteIndicacao(null)).toBeNull()
    expect(lerConviteIndicacao({ titulo: 1 })).toBeNull()
    expect(lerConviteIndicacao({ titulo: 'Oi', texto: 'Indique', recompensa: '  ' })).toEqual({ titulo: 'Oi', texto: 'Indique', recompensa: null })
  })

  it('erros do servidor por campo, com ou sem prefixo', () => {
    expect(camposDoServidor({ 'indicacao.telefone': 'Telefone inválido.', email: 'E-mail inválido.', outro: 'x' })).toEqual({
      telefone: 'Telefone inválido.',
      email: 'E-mail inválido.',
    })
  })
})

describe('Configurações › Crescimento', () => {
  it('título, texto e oferta obrigatórios com os limites; recompensa opcional (vazia vira null)', () => {
    expect(validarConfigCrescimento({ ...PADRAO_CRESCIMENTO, titulo_convite: ' ', texto_oferta: '' })).toEqual({
      titulo_convite: 'Escreva o título do convite.',
      texto_oferta: 'Escreva o texto da oferta.',
    })
    expect(
      validarConfigCrescimento({ ...PADRAO_CRESCIMENTO, titulo_convite: 'x'.repeat(121), texto_convite: 'x'.repeat(501), recompensa: 'x'.repeat(301), texto_oferta: 'x'.repeat(1001) }),
    ).toEqual({
      titulo_convite: 'Use até 120 caracteres.',
      texto_convite: 'Use até 500 caracteres.',
      recompensa: 'Use até 300 caracteres.',
      texto_oferta: 'Use até 1000 caracteres.',
    })
    expect(normalizarConfigCrescimento({ ...PADRAO_CRESCIMENTO, recompensa: '   ' }).recompensa).toBeNull()
  })

  it('prévias com as variáveis certas de cada texto', () => {
    expect(VARIAVEIS_CONVITE_INDICACAO.map((v) => v.texto)).toEqual(['{nome}', '{empresa}'])
    expect(VARIAVEIS_OFERTA.map((v) => v.texto)).toEqual(['{nome}', '{empresa}', '{empresa_cliente}', '{representante}'])
    expect(previaConvite({ ...PADRAO_CRESCIMENTO, recompensa: 'Ganhe 10%, {nome}!' }, { empresa: 'Sol', nome: 'Maria Souza' })).toEqual({
      titulo: 'Que bom que você gostou!',
      texto: 'Conhece outra empresa que ganharia com a Sol? Indique e a gente entra em contato com cuidado.',
      recompensa: 'Ganhe 10%, Maria!',
    })
    expect(previaOferta({ texto_oferta: '{representante} da {empresa} para {empresa_cliente}' }, { representante: 'Ana Paula', empresa: 'Sol', empresa_cliente: 'Vale' })).toBe('Ana da Sol para Vale')
  })
})

describe('menu, atalho e webhooks', () => {
  it('"Crescimento" vem depois de "Planos de ação" e só com crescimento.ver', () => {
    const rotulos = (permissoes: string[]) => filtrarNavegacao(navegacaoPrincipal, (p) => permissoes.includes(p), false).map((i) => i.rotulo)
    const todas = rotulos(['acoes.ver', 'crescimento.ver', 'relatorios.ver'])
    expect(todas.indexOf('Crescimento')).toBe(todas.indexOf('Planos de ação') + 1)
    expect(rotulos(['acoes.ver', 'relatorios.ver'])).not.toContain('Crescimento')
    const item = navegacaoPrincipal.find((i) => i.rotulo === 'Crescimento')!
    expect(item.para).toBe('/crescimento/indicacoes')
    expect(itemAtivo(item, '/crescimento/oportunidades', {}, false)).toBe(true)
  })

  it('atalho "crescimento" do assistente e da Ajuda', () => {
    const acesso = (p: string[]) => ({ pode: (x: string) => p.includes(x), admin: false })
    expect(atalhoPermitido('crescimento', acesso(['crescimento.ver']))).toEqual({
      chave: 'crescimento',
      rotulo: 'Crescimento',
      caminho: '/crescimento/indicacoes',
      permissao: 'crescimento.ver',
    })
    expect(atalhoPermitido('crescimento', acesso(['acoes.ver']))).toBeNull()
  })

  it('os eventos de indicação aparecem na escolha do webhook', () => {
    expect(Object.keys(EVENTOS_WEBHOOK)).toEqual(['resposta.criada', 'contato.descadastrado', 'indicacao.criada', 'indicacao.atualizada'])
    expect(rotuloEventoWebhook('indicacao.criada')).toBe('Nova indicação')
    expect(rotuloEventoWebhook('indicacao.atualizada')).toBe('Indicação mudou de situação')
    // A indicação nova também sai quando a equipe registra à mão (não só pela pesquisa)
    expect(EVENTOS_WEBHOOK['indicacao.criada'].descricao).toBe('Quando chega uma indicação nova, feita pela pesquisa ou registrada pela equipe.')
  })
})

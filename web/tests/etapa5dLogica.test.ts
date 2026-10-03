// Etapa 5d (docs/api-etapa-5d.md §6): regras puras da IA sob demanda: chave dos filtros, corpo do POST, contagem até
// gerar de novo, textos, erros da geração, leitura do que vem da API e os textos dos documentos legais.
import { describe, expect, it } from 'vitest'
import { ApiError, lerErroApi, MENSAGEM_MUITAS_TENTATIVAS } from '@/api/erros'
import { corpoGeracaoIa } from '@/api/etapa5d'
import {
  ESPERA_MAXIMA,
  chaveFiltros,
  descreverFiltrosIa,
  falarParecer,
  falarResumo,
  instante,
  lerCota,
  lerErroGeracao,
  listaDeTextos,
  normalizarItem,
  normalizarParecer,
  normalizarResumo,
  prazoLocal,
  rotuloBotaoGerar,
  rotuloOpcao,
  segundosAte,
  segundosDaMensagem,
  situacaoPassos,
  textoBotaoGerar,
  textoEscritaSalva,
  textoGerado,
  textoPassos,
} from '@/modulos/ia/logica'
import { textoAbertura, textoVersao } from '@/modulos/geral/legal/aceite'
import { PRIVACIDADE } from '@/modulos/geral/legal/privacidade'
import { TERMOS } from '@/modulos/geral/legal/termos'
import { VERSAO_DOCUMENTOS, VIGENTE_DESDE } from '@/modulos/geral/legal/versao'

describe('filtros', () => {
  it('chave canônica como a API: datas ou vazio, grupo ou vazio, só ativas 1/0 (vazio = 1)', () => {
    expect(chaveFiltros({ de: '2026-07-01', ate: '2026-09-30', so_ativos: true })).toBe('de=2026-07-01|ate=2026-09-30|grupo=|ativos=1')
    expect(chaveFiltros({})).toBe('de=|ate=|grupo=|ativos=1')
    expect(chaveFiltros({ grupo_id: 3, so_ativos: false })).toBe('de=|ate=|grupo=3|ativos=0')
    expect(chaveFiltros({ grupo_id: '' })).toBe(chaveFiltros({}))
    // Mesmos valores, mesma chave (a ordem e o tipo do grupo não importam).
    expect(chaveFiltros({ so_ativos: true, grupo_id: '7', ate: '2026-09-30' })).toBe(chaveFiltros({ ate: '2026-09-30', grupo_id: 7 }))
  })

  it('corpo do POST: os quatro campos, null no que não foi escolhido, grupo numérico', () => {
    expect(corpoGeracaoIa({})).toEqual({ de: null, ate: null, grupo_id: null, so_ativos: true })
    expect(corpoGeracaoIa({ de: '2026-07-01', ate: '2026-09-30', grupo_id: '12', so_ativos: false })).toEqual({
      de: '2026-07-01',
      ate: '2026-09-30',
      grupo_id: 12,
      so_ativos: false,
    })
    expect(corpoGeracaoIa({ grupo_id: 4, so_ativos: true }).grupo_id).toBe(4)
    expect(corpoGeracaoIa({ grupo_id: '' }).grupo_id).toBeNull()
  })

  it('descreve os filtros do parecer', () => {
    expect(descreverFiltrosIa('Últimos 90 dias', null, true)).toBe('Últimos 90 dias · Todos os grupos · Só empresas ativas')
    expect(descreverFiltrosIa('Últimos 30 dias', 'Varejo', false)).toBe('Últimos 30 dias · Grupo Varejo · Empresas ativas e inativas')
  })
})

describe('espera de 30 s', () => {
  const agora = Date.parse('2026-10-02T15:00:00Z')

  it('segundos até poder gerar: arredonda para cima, nunca negativo, nunca acima de 30', () => {
    expect(segundosAte(null, agora)).toBe(0)
    expect(segundosAte(agora - 5_000, agora)).toBe(0)
    expect(segundosAte(agora, agora)).toBe(0)
    expect(segundosAte(agora + 1, agora)).toBe(1)
    expect(segundosAte(agora + 24_200, agora)).toBe(25)
    expect(segundosAte(agora + 30_000, agora)).toBe(30)
    expect(segundosAte(agora + 95_000, agora)).toBe(ESPERA_MAXIMA)
  })

  it('pode_gerar_em em ms (null vazio ou inválido)', () => {
    expect(instante('2026-10-02T15:00:30Z')).toBe(agora + 30_000)
    expect(instante(null)).toBeNull()
    expect(instante('ontem')).toBeNull()
  })

  it('prazo no relógio do aparelho: o que falta na hora em que a resposta chega, de 0 a 30 s; a espera acaba em 30 s', () => {
    // Aparelho atrasado 1 min: o "daqui a 30 s" do servidor é, no relógio do aparelho, daqui a 90 s.
    const atrasado = prazoLocal(agora + 90_000, agora)
    expect(atrasado).toBe(agora + 30_000)
    expect(segundosAte(atrasado, agora)).toBe(30)
    expect(segundosAte(atrasado, agora + 29_500)).toBe(1)
    // A espera acaba 30 s depois, no relógio do aparelho (comparar com a hora do servidor daria 1 min e meio).
    expect(segundosAte(atrasado, agora + 30_000)).toBe(0)
    expect(segundosAte(agora + 90_000, agora + 30_000)).toBe(ESPERA_MAXIMA) // o jeito antigo: ainda 30 s
    // Aparelho adiantado 1 min: para ele, já passou (se a API ainda travar, o 429 diz quanto falta).
    expect(prazoLocal(agora - 30_000, agora)).toBe(agora)
    // Relógios certos: o que falta.
    expect(prazoLocal(agora + 12_000, agora)).toBe(agora + 12_000)
    expect(prazoLocal(null, agora)).toBeNull()
    expect(prazoLocal(Number.NaN, agora)).toBeNull()
  })

  it('texto do botão, com e sem contagem; o nome (para o leitor de tela) não muda com a contagem', () => {
    expect(textoBotaoGerar('Gerar resumo', false, 0)).toBe('Gerar resumo')
    expect(textoBotaoGerar('Gerar resumo', true, 0)).toBe('Gerar de novo')
    expect(textoBotaoGerar('Gerar resumo', true, 25)).toBe('Gerar de novo em 25 s')
    expect(textoBotaoGerar('Gerar parecer', false, 12)).toBe('Gerar parecer em 12 s')
    expect(rotuloBotaoGerar('Gerar resumo', false)).toBe('Gerar resumo')
    expect(rotuloBotaoGerar('Gerar parecer', false)).toBe('Gerar parecer')
    expect(rotuloBotaoGerar('Gerar parecer', true)).toBe('Gerar de novo')
  })
})

describe('rodapé', () => {
  it('"Gerado em dd/mm/aaaa às hh:mm por {nome} · {modelo}"', () => {
    const item = { gerado_em: '2026-10-02T17:30:00Z', gerado_por: 'Ana Paula', modelo_rotulo: 'Equilibrado' }
    expect(textoGerado(item)).toBe('Gerado em 02/10/2026 às 14:30 por Ana Paula · Equilibrado')
    expect(textoGerado({ ...item, gerado_por: null })).toBe('Gerado em 02/10/2026 às 14:30 · Equilibrado')
    expect(textoGerado({ ...item, modelo_rotulo: '' })).toBe('Gerado em 02/10/2026 às 14:30 por Ana Paula')
  })
})

describe('erros da geração', () => {
  const erro = (status: number, codigo: string, mensagem: string) => lerErroApi(status, { erro: { codigo, mensagem } })

  it('409 de cota esgotada e conta pausada mudam o estado (sem botão), com a mensagem da API', () => {
    expect(lerErroGeracao(erro(409, 'cota_esgotada', 'O limite mensal acabou.'))).toMatchObject({ bloqueio: 'cota_esgotada', mensagem: 'O limite mensal acabou.', repetir: false })
    expect(lerErroGeracao(erro(409, 'conta_pausada', 'A IA volta quando a assinatura estiver em dia.')).bloqueio).toBe('conta_pausada')
  })

  it('409 sem dados: aviso de informação, sem "Tentar de novo"', () => {
    expect(lerErroGeracao(erro(409, 'sem_dados', 'Não há respostas neste período para analisar.'))).toEqual({
      mensagem: 'Não há respostas neste período para analisar.',
      tom: 'info',
      repetir: false,
      bloqueio: null,
      esperar: null,
    })
  })

  it('429 aguarde: a mensagem da API (não a genérica) e os segundos para a contagem', () => {
    const e = erro(429, 'aguarde', 'Aguarde 12 s para gerar de novo.')
    expect(e.mensagem).toBe('Aguarde 12 s para gerar de novo.')
    expect(lerErroGeracao(e)).toMatchObject({ mensagem: 'Aguarde 12 s para gerar de novo.', tom: 'atencao', esperar: 12, repetir: false })
    const andamento = lerErroGeracao(erro(429, 'aguarde', 'Já tem um resumo sendo gerado. Aguarde alguns segundos.'))
    expect(andamento).toMatchObject({ mensagem: 'Já tem um resumo sendo gerado. Aguarde alguns segundos.', esperar: null })
    // Os outros 429 continuam com o texto padrão.
    expect(erro(429, 'muitas_tentativas', 'Rate limit').mensagem).toBe(MENSAGEM_MUITAS_TENTATIVAS)
  })

  it('503: "Tentar de novo"; o resto, só a mensagem; erro desconhecido, a padrão', () => {
    expect(lerErroGeracao(erro(503, 'ia_indisponivel', 'A IA não respondeu.'))).toMatchObject({ repetir: true, tom: 'erro' })
    expect(lerErroGeracao(erro(409, 'ia_indisponivel', 'A IA não está disponível no momento.'))).toMatchObject({ repetir: false, bloqueio: null })
    expect(lerErroGeracao(new Error('x'))).toMatchObject({ mensagem: expect.stringMatching(/Algo deu errado/), repetir: false })
    expect(lerErroGeracao(new ApiError(0, 'sem_conexao', 'Sem conexão.')).repetir).toBe(false)
  })

  it('segundos na mensagem do 429', () => {
    expect(segundosDaMensagem('Aguarde 1 s para gerar de novo.')).toBe(1)
    expect(segundosDaMensagem('Aguarde 0 s')).toBeNull()
    expect(segundosDaMensagem('Aguarde alguns segundos.')).toBeNull()
  })
})

describe('leitura do que vem da API', () => {
  it('resumo: as três frases como texto, numa linha', () => {
    expect(normalizarResumo({ melhorar: ' Prazo de entrega.\n', funciona: 'Atendimento.', proximo_passo: 'Ligar.' })).toEqual({
      melhorar: 'Prazo de entrega.',
      funciona: 'Atendimento.',
      proximo_passo: 'Ligar.',
    })
    expect(normalizarResumo({ melhorar: 3 })).toBeNull()
    expect(normalizarResumo(null)).toBeNull()
  })

  it('parecer: resumo e até 3 recomendações, sem vazias nem repetidas', () => {
    expect(normalizarParecer({ resumo: 'O NPS caiu.', recomendacoes: ['A', '', 'A', 'B', 'C', 'D', 7] })).toEqual({ resumo: 'O NPS caiu.', recomendacoes: ['A', 'B', 'C'] })
    expect(normalizarParecer({ resumo: '', recomendacoes: [] })).toBeNull()
    expect(normalizarParecer('texto')).toBeNull()
  })

  it('item: conteúdo lido, nome de quem gerou e o rótulo do modelo; conteúdo inválido = nada salvo', () => {
    const item = { conteudo: { resumo: 'Bom.', recomendacoes: [] }, gerado_em: '2026-10-02T17:30:00Z', gerado_por: { id: 1, nome: 'Ana' }, modelo: 'rapido', modelo_rotulo: 'Rápido e econômico', estilo: 'objetiva' }
    expect(normalizarItem(item, normalizarParecer)).toEqual({ conteudo: { resumo: 'Bom.', recomendacoes: [] }, gerado_em: '2026-10-02T17:30:00Z', gerado_por: 'Ana', modelo_rotulo: 'Rápido e econômico' })
    expect(normalizarItem({ ...item, gerado_por: null }, normalizarParecer)?.gerado_por).toBeNull()
    expect(normalizarItem({ ...item, conteudo: {} }, normalizarParecer)).toBeNull()
    expect(normalizarItem(null, normalizarParecer)).toBeNull()
  })

  it('cota só no formato certo', () => {
    expect(lerCota({ usadas: 13, limite: 500, restantes: 487, mes: '2026-10' })).toEqual({ usadas: 13, limite: 500, restantes: 487, mes: '2026-10' })
    expect(lerCota({ usadas: '13' })).toBeNull()
    expect(lerCota(undefined)).toBeNull()
  })

  it('texto para leitores de tela', () => {
    expect(falarResumo({ melhorar: 'A entrega.', funciona: 'O preço.', proximo_passo: 'Ligar.' })).toBe(
      'Precisa melhorar: A entrega. Está funcionando: O preço. Próximo passo: Ligar.',
    )
    expect(falarParecer({ resumo: 'Caiu.', recomendacoes: ['Ligar.', 'Visitar.'] })).toBe('Resumo: Caiu. Recomendações da semana: 1. Ligar. 2. Visitar.')
  })
})

describe('passos das ações', () => {
  it('situação conhecida ou nada; lista numerada para copiar', () => {
    expect(situacaoPassos('pendente')).toBe('pendente')
    expect(situacaoPassos('limite')).toBe('limite')
    expect(situacaoPassos(null)).toBeNull()
    expect(situacaoPassos('outra')).toBeNull()
    expect(listaDeTextos(['Ligar hoje.', ' ', 'Mandar e-mail.'])).toEqual(['Ligar hoje.', 'Mandar e-mail.'])
    expect(textoPassos(['Ligar hoje.', 'Mandar e-mail.', 'Agendar visita.'])).toBe('1. Ligar hoje.\n2. Mandar e-mail.\n3. Agendar visita.')
  })
})

describe('Configurações › IA: avisos ao salvar', () => {
  const lista = [
    { valor: 'rapido', rotulo: 'Rápido e econômico' },
    { valor: 'detalhado', rotulo: 'Mais detalhado' },
  ]
  it('com o rótulo da opção', () => {
    expect(rotuloOpcao(lista, 'detalhado')).toBe('Mais detalhado')
    expect(rotuloOpcao(lista, 'novo')).toBe('novo')
    expect(textoEscritaSalva('modelo', { modelo: 'rapido', modelos: lista })).toBe('Modelo salvo: Rápido e econômico.')
    expect(textoEscritaSalva('estilo', { estilo: 'criativa', estilos: [{ valor: 'criativa', rotulo: 'Criativa' }] })).toBe('Estilo salvo: Criativa.')
    expect(textoEscritaSalva('passos_acoes', { passos_acoes: true })).toMatch(/^Sugestão de passos ligada/)
    expect(textoEscritaSalva('passos_acoes', { passos_acoes: false })).toMatch(/^Sugestão de passos desligada/)
  })
})

describe('Termos de uso e Política de privacidade (versão 2)', () => {
  /** Os itens de uma lista, cada um como texto. */
  const itens = (blocos: (typeof PRIVACIDADE.secoes)[number]['blocos']) => {
    const lista = blocos.find((b) => b.tipo === 'lista')
    return lista && lista.tipo === 'lista' ? lista.itens.map((i) => (typeof i === 'string' ? i : i.map((p) => (typeof p === 'string' ? p : p.texto)).join(''))) : []
  }
  const RECURSOS = ['Análise de comentários', 'Passos das ações', 'Resumo do painel', 'Parecer dos relatórios', 'ToqqiAI']

  it('versão 2, vigente desde hoje (02/10/2026): a tela de aceite e o topo dos documentos mostram essa data', () => {
    // Etapa 5e: a versão 3 (registro de e-mails enviados) veio por cima, no mesmo dia (ver etapa5eLogica.test.ts).
    expect(VERSAO_DOCUMENTOS).toBeGreaterThanOrEqual(2)
    expect(VIGENTE_DESDE).toBe('2026-10-02')
    expect(textoVersao(2)).toBe('Versão 2 · vigente desde 02/10/2026')
    // Quem aceitou a versão 1 vê a tela de aceite de novo, com a data da versão 2.
    expect(textoAbertura({ versao_atual: 2, versao_aceita: 1, aceito_em: '2026-09-01T12:00:00Z', pendente: true })).toBe(
      'Atualizamos os Termos de uso e a Política de privacidade em 02/10/2026.',
    )
  })

  it('Política: a seção de IA com os cinco recursos, o que cada um envia e como desligar', () => {
    const ia = PRIVACIDADE.secoes.find((s) => s.id === 'inteligencia-artificial')!
    const texto = JSON.stringify(ia.blocos)
    expect(texto).toContain('em cinco recursos')
    const lista = itens(ia.blocos)
    expect(lista.map((i) => i.split(':')[0])).toEqual(RECURSOS)
    expect(texto).toContain('Como desligar: a análise de comentários e os passos das ações se desligam em Configurações › IA.')
    expect(texto).toContain('só quando alguém pede')
    // O resumo e o parecer também levam o nome da conta (nas instruções) e o do grupo filtrado.
    for (const recurso of [lista[2]!, lista[3]!]) {
      expect(recurso).toContain('o nome da conta (nas instruções para a IA)')
      expect(recurso).toContain('o nome do grupo de empresas filtrado, se houver')
    }
    const fornecedores = PRIVACIDADE.secoes.find((s) => s.id === 'compartilhamento')!
    expect(JSON.stringify(fornecedores.blocos)).toContain('passos das ações, resumo do painel, parecer dos relatórios e ToqqiAI')
  })

  it('Termos: os mesmos cinco recursos, o que vem ligado, o que só roda quando alguém pede e o que gasta a cota', () => {
    const servico = TERMOS.secoes.find((s) => s.id === 'o-servico')!
    expect(itens(servico.blocos).map((i) => i.split(':')[0])).toEqual(RECURSOS)
    const texto = JSON.stringify(servico.blocos)
    expect(texto).toContain('Também há cinco recursos de inteligência artificial (IA):')
    expect(texto).toContain('A análise de comentários e os passos das ações já vêm ligados, e a Empresa pode desligá-los em Configurações › IA.')
    expect(texto).toContain('O resumo do painel, o parecer dos relatórios e o ToqqiAI só rodam quando alguém da conta pede')
    expect(texto).toContain('cada resumo, parecer ou pergunta usa 1 análise da cota de IA do plano')
    expect(texto).toContain('/privacidade#inteligencia-artificial')
    // O texto antigo (só dois recursos) saiu.
    expect(texto).not.toContain('A análise de comentários já vem ligada')
  })
})

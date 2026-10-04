// Regras puras da etapa 5b: texto do assistente (sem HTML), histórico, cota, erros, atalhos por permissão, busca da
// Ajuda sem acento e a conversa guardada no navegador.
import { readFileSync } from 'node:fs'
import { afterEach, beforeEach, describe, expect, it } from 'vitest'
import { ApiError } from '@/api/erros'
import type { Permissao } from '@/api/tipos'
import { atalhoPermitido, atalhosDaResposta } from '@/modulos/ajuda/atalhos'
import { buscarNaAjuda, lerConteudo, palavrasDaBusca, paraBusca, raiz, semAcento } from '@/modulos/ajuda/logica'
import { apagarConversa, apagarConversas, chaveConversa, guardarConversa, lerConversa } from '@/modulos/assistente/historico'
import {
  blocosDoTexto,
  esperaDaTentativa,
  explicacaoIndisponivel,
  historicoParaApi,
  lerErroPergunta,
  MENSAGEM_LIMITE_PERGUNTAS,
  MIDIA_PAINEL,
  textoCota,
} from '@/modulos/assistente/logica'

/** A frase do 409 da API (desde 03/10 ela sugere o nível mais barato que cabe no que resta). */
const INSUFICIENTE = 'Resta 1 análise e o nível Mais detalhado gasta 2. Troque para o Equilibrado em Configurações › IA ou aguarde o próximo mês.'
/** A do site, quando a API não mandou a dela: sem citar nível (as análises de cada um mudam em Plataforma › Parâmetros). */
const INSUFICIENTE_SITE = 'O nível escolhido gasta 2 análises e resta 1. Troque o nível em Configurações › IA ou aguarde o próximo mês.'

const acesso = (permissoes: Permissao[], admin = false) => ({ pode: (p: Permissao) => permissoes.includes(p), admin })

describe('texto do assistente', () => {
  it('linhas "- " viram lista; as outras, parágrafos com as quebras de linha; linha em branco separa', () => {
    expect(blocosDoTexto('NPS de 42 (120 respostas).\nPeríodo: 02/09 a 01/10.\n\nDestaques:\n- subiu 5 pontos\n-  30 respostas a mais \nFim.')).toEqual([
      { tipo: 'paragrafo', linhas: ['NPS de 42 (120 respostas).', 'Período: 02/09 a 01/10.'] },
      { tipo: 'paragrafo', linhas: ['Destaques:'] },
      { tipo: 'lista', itens: ['subiu 5 pontos', '30 respostas a mais'] },
      { tipo: 'paragrafo', linhas: ['Fim.'] },
    ])
  })

  it('"-" sem espaço não é lista; HTML continua texto', () => {
    expect(blocosDoTexto('-5 pontos\r\n<b>oi</b>')).toEqual([{ tipo: 'paragrafo', linhas: ['-5 pontos', '<b>oi</b>'] }])
    expect(blocosDoTexto('')).toEqual([])
  })
})

describe('histórico e cota', () => {
  it('vão as últimas 8 mensagens que tiveram resposta, sem as perguntas que falharam', () => {
    const msgs = Array.from({ length: 12 }, (_, i) => ({ papel: i % 2 ? 'assistente' : 'usuario', texto: `m${i}` }) as const)
    const comFalha = [...msgs, { papel: 'usuario' as const, texto: 'falhou', falhou: true }]
    const h = historicoParaApi(comFalha)
    expect(h).toHaveLength(8)
    expect(h[0]).toEqual({ papel: 'usuario', texto: 'm4' })
    expect(h.at(-1)).toEqual({ papel: 'assistente', texto: 'm11' })
    expect(historicoParaApi([{ papel: 'assistente', texto: 'x'.repeat(5000) }])[0]!.texto).toHaveLength(4000)
  })

  it('"Restam X de Y análises este mês" (singular com 1)', () => {
    expect(textoCota({ usadas: 12, limite: 500, restantes: 488, mes: '2026-10' })).toBe('Restam 488 de 500 análises este mês')
    expect(textoCota({ usadas: 1999, limite: 2000, restantes: 1, mes: '2026-10' })).toBe('Resta 1 de 2.000 análises este mês')
    expect(textoCota({ usadas: 100, limite: 100, restantes: -3, mes: '2026-10' })).toBe('Restam 0 de 100 análises este mês')
  })
})

describe('erros da pergunta', () => {
  it('409 desliga a caixa; "Tentar de novo" só com 503 ia_indisponivel, 429 e sem conexão', () => {
    const cota = lerErroPergunta(new ApiError(409, 'cota_esgotada', 'O limite mensal de análises de IA do seu plano foi atingido. Ele renova no dia 1º.'))
    expect(cota).toEqual({ mensagem: 'O limite mensal de análises de IA do seu plano foi atingido. Ele renova no dia 1º.', repetir: false, bloqueio: 'cota_esgotada' })
    expect(lerErroPergunta(new ApiError(409, 'conta_pausada', 'O ToqqiAI volta quando a assinatura estiver em dia.')).bloqueio).toBe('conta_pausada')
    // O cliente troca o texto de todo 429; vale o do contrato.
    expect(lerErroPergunta(new ApiError(429, 'limite_perguntas', 'Muitas tentativas. Aguarde um minuto.'))).toEqual({ mensagem: MENSAGEM_LIMITE_PERGUNTAS, repetir: true, bloqueio: null })
    expect(lerErroPergunta(new ApiError(503, 'ia_indisponivel', 'Indisponível.'))).toEqual({ mensagem: 'Indisponível.', repetir: true, bloqueio: null })
    expect(lerErroPergunta(new ApiError(0, 'sem_conexao', 'Sem conexão.')).repetir).toBe(true)
    // Um 500 (ou um 503 que não é do assistente, um 502/504 do caminho) pode vir depois de a análise ser gasta: só a mensagem.
    expect(lerErroPergunta(new ApiError(500, 'erro_servidor', 'Algo deu errado.'))).toEqual({ mensagem: 'Algo deu errado.', repetir: false, bloqueio: null })
    expect(lerErroPergunta(new ApiError(503, 'erro_servidor', 'Fora do ar.')).repetir).toBe(false)
    expect(lerErroPergunta(new ApiError(504, 'erro_servidor', 'Demorou.')).repetir).toBe(false)
    expect(lerErroPergunta(new ApiError(422, 'validacao', 'Pergunta grande demais.')).repetir).toBe(false)
    expect(lerErroPergunta(new Error('x'))).toMatchObject({ repetir: false, bloqueio: null })
  })

  it('explica a caixa desligada pelo motivo', () => {
    expect(explicacaoIndisponivel(true, null)).toBeNull()
    expect(explicacaoIndisponivel(false, 'cota_esgotada')).toContain('renova no dia 1º')
    expect(explicacaoIndisponivel(false, 'conta_pausada')).toBe('O ToqqiAI volta quando a assinatura estiver em dia.')
    expect(explicacaoIndisponivel(false, 'outro')).toContain('indisponível')
  })

  it('cota insuficiente (03/10: resta menos que o custo do nível): 409 desliga a caixa; a explicação é a da API ou a mesma frase montada', () => {
    expect(lerErroPergunta(new ApiError(409, 'cota_insuficiente', INSUFICIENTE))).toEqual({ mensagem: INSUFICIENTE, repetir: false, bloqueio: 'cota_insuficiente' })
    expect(explicacaoIndisponivel(false, 'cota_insuficiente', { restantes: 1, custo: 2 })).toBe(INSUFICIENTE_SITE)
    expect(explicacaoIndisponivel(false, 'cota_insuficiente', { mensagem: 'A mensagem da API.', restantes: 1, custo: 2 })).toBe('A mensagem da API.')
    expect(explicacaoIndisponivel(false, 'cota_insuficiente', { restantes: 2, custo: 3 })).toBe(
      'O nível escolhido gasta 3 análises e restam 2. Troque o nível em Configurações › IA ou aguarde o próximo mês.',
    )
    expect(explicacaoIndisponivel(true, 'cota_insuficiente', { restantes: 1, custo: 2 })).toBeNull()
  })
})

describe('estado e tela do assistente', () => {
  it('sem o estado, tenta de novo depois de 5 s, 15 s e 60 s; depois, a cada 5 minutos', () => {
    expect([0, 1, 2, 3, 4, 50].map(esperaDaTentativa)).toEqual([5_000, 15_000, 60_000, 300_000, 300_000, 300_000])
    expect(esperaDaTentativa(-1)).toBe(5_000)
  })

  it('o painel preso ao canto exige largura e altura; a variante `painel:` do CSS usa a mesma consulta do script', () => {
    expect(MIDIA_PAINEL).toBe('(min-width: 640px) and (min-height: 560px)')
    const css = readFileSync('src/styles/main.css', 'utf8')
    expect(css).toContain(`@custom-variant painel (@media ${MIDIA_PAINEL});`)
  })
})

describe('atalhos (§5.4)', () => {
  it('só as telas que a pessoa pode abrir; Integrações só para administrador', () => {
    expect(atalhoPermitido('importar_contatos', acesso(['importacao.usar']))).toMatchObject({ rotulo: 'Importar contatos', caminho: '/contatos/importar' })
    expect(atalhoPermitido('importar_contatos', acesso(['contatos.ver']))).toBeNull()
    expect(atalhoPermitido('integracoes', acesso([], false))).toBeNull()
    expect(atalhoPermitido('integracoes', acesso([], true))).toMatchObject({ caminho: '/integracoes' })
    expect(atalhoPermitido('minha_conta', acesso([]))).toMatchObject({ caminho: '/minha-conta' })
    expect(atalhoPermitido('desconhecida', acesso([], true))).toBeNull()
    expect(atalhoPermitido('toString', acesso([], true))).toBeNull()
    expect(atalhoPermitido(null, acesso([], true))).toBeNull()
  })

  it('da resposta: sem repetir, sem desconhecidos, no máximo 2, com o caminho da tabela', () => {
    const lista = atalhosDaResposta(
      [
        { chave: 'relatorios', rotulo: 'Relatórios', caminho: 'javascript:alert(1)' },
        { chave: 'relatorios', rotulo: 'Relatórios', caminho: '/relatorios/empresas' },
        { chave: 'nova_tela', rotulo: 'Nova', caminho: '/nova' },
        { chave: 'equipe', rotulo: 'Equipe', caminho: '/equipe' },
        { chave: 'ajuda', rotulo: 'Ajuda', caminho: '/ajuda' },
        { chave: 'inicio', rotulo: 'Início', caminho: '/inicio' },
      ],
      acesso(['relatorios.ver']),
    )
    expect(lista.map((a) => [a.chave, a.caminho])).toEqual([
      ['relatorios', '/relatorios/empresas'],
      ['ajuda', '/ajuda'],
    ])
  })
})

const CONTEUDO = lerConteudo({
  versao: 1,
  topicos: [
    {
      id: 'contatos',
      titulo: 'Contatos',
      resumo: 'Quem recebe as pesquisas.',
      secoes: [
        { id: 'importar-planilha', titulo: 'Importar uma planilha', somente_admin: false, atalho: 'importar_contatos', palavras: ['importação', 'csv'], blocos: [{ tipo: 'passos', itens: ['Abra Contatos.', 'Clique em "Importar planilha".'] }] },
        { id: 'grupos', titulo: 'Grupos', somente_admin: false, atalho: null, palavras: [], blocos: [{ tipo: 'paragrafo', texto: 'Separe os contatos por região, como na importação.' }] },
      ],
    },
    {
      id: 'configuracoes',
      titulo: 'Configurações',
      resumo: '',
      secoes: [
        { id: 'notificacoes', titulo: 'Notificações', somente_admin: true, atalho: 'config_envios', palavras: ['e-mail'], blocos: [{ tipo: 'dica', texto: 'A IA avisa quando um detrator responde.' }, { tipo: 'video', url: 'x' }] },
        { id: 'sem-titulo', blocos: [] },
      ],
    },
    { id: 'contatos', titulo: 'Repetido', secoes: [] },
    { titulo: 'Sem id', secoes: [] },
  ],
})

describe('Ajuda: conteúdo e busca', () => {
  it('lê o conteúdo com cuidado: tira itens sem id, ids repetidos e blocos de tipo desconhecido', () => {
    expect(CONTEUDO.topicos.map((t) => t.id)).toEqual(['contatos', 'configuracoes'])
    expect(CONTEUDO.topicos[1]!.secoes.map((s) => s.id)).toEqual(['notificacoes'])
    expect(CONTEUDO.topicos[1]!.secoes[0]!.blocos).toEqual([{ tipo: 'dica', texto: 'A IA avisa quando um detrator responde.' }])
    // Jornadas (docs/ajuda-jornadas.md §3): depois de lerConteudo, `jornadas` é sempre uma lista (vazia sem jornadas).
    expect(lerConteudo(null)).toEqual({ versao: 1, jornadas: [], topicos: [] })
  })

  it('sem acento, sem diferenciar maiúsculas, com plural; título e palavras-chave pesam mais', () => {
    expect(semAcento('Importação ÇÃO')).toBe('importacao cao')
    expect(palavrasDaBusca('Como faço a importação de PLANILHAS?')).toEqual(['import', 'planilh'])
    expect(palavrasDaBusca('IA')).toEqual(['ia'])
    expect(['importar', 'importados', 'notificações', 'pagamento', 'detratores', 'mensagens', 'conta', 'envio', 'nps'].map((p) => raiz(paraBusca(p)))).toEqual([
      'import', 'importad', 'notific', 'paga', 'detrator', 'mensagem', 'conta', 'envio', 'nps',
    ])
    const r = buscarNaAjuda(CONTEUDO, 'IMPORTACAO')
    // A palavra-chave "importação" (peso 3) vem antes do texto de "Grupos" (peso 1).
    expect(r.map((x) => x.secao.id)).toEqual(['importar-planilha', 'grupos'])
    expect(r[1]!.trecho).toBe('Separe os contatos por região, como na importação.')
    expect(buscarNaAjuda(CONTEUDO, 'notificacao').map((x) => x.secao.id)).toEqual(['notificacoes'])
    expect(buscarNaAjuda(CONTEUDO, 'notificações').map((x) => x.secao.id)).toEqual(['notificacoes'])
    expect(buscarNaAjuda(CONTEUDO, 'planilhas').map((x) => x.secao.id)).toEqual(['importar-planilha'])
    // Verbo e substantivo se acham; "e-mail" e "email" também.
    expect(buscarNaAjuda(CONTEUDO, 'importar').map((x) => x.secao.id)).toEqual(['importar-planilha', 'grupos'])
    expect(buscarNaAjuda(CONTEUDO, 'email').map((x) => x.secao.id)).toEqual(['notificacoes'])
    // A raiz vale só no começo da palavra.
    expect(buscarNaAjuda(CONTEUDO, 'bra').map((x) => x.secao.id)).toEqual([])
    // Passos numerados no trecho.
    expect(buscarNaAjuda(CONTEUDO, 'csv')[0]!.trecho).toBe('1. Abra Contatos. 2. Clique em "Importar planilha".')
    // Palavra de 2 letras só como palavra inteira ("ia" não acha "região").
    expect(buscarNaAjuda(CONTEUDO, 'ia').map((x) => x.secao.id)).toEqual(['notificacoes'])
    expect(buscarNaAjuda(CONTEUDO, 'boleto')).toEqual([])
    expect(buscarNaAjuda(CONTEUDO, '  ')).toEqual([])
  })
})

describe('conversa guardada no navegador', () => {
  beforeEach(() => sessionStorage.clear())
  afterEach(() => sessionStorage.clear())

  it('uma por conta e usuário, até 20 mensagens; sair apaga todas', () => {
    const a = chaveConversa(1, 7)
    const b = chaveConversa(2, 7)
    expect(a).toBe('toqqi.assistente.1.7')
    const msgs = Array.from({ length: 25 }, (_, i) => ({ papel: i % 2 ? ('assistente' as const) : ('usuario' as const), texto: `m${i}` }))
    guardarConversa(a, msgs)
    guardarConversa(b, msgs.slice(0, 2))
    sessionStorage.setItem('toqqi.sessao', 'x')
    const lida = lerConversa(a)
    expect(lida).toHaveLength(20)
    expect(lida[0]).toEqual({ papel: 'assistente', texto: 'm5', sugestoes: [], atalhos: [] })
    apagarConversa(b)
    expect(lerConversa(b)).toEqual([])
    guardarConversa(b, msgs.slice(0, 2))
    apagarConversas()
    expect(lerConversa(a)).toEqual([])
    expect(lerConversa(b)).toEqual([])
    expect(sessionStorage.getItem('toqqi.sessao')).toBe('x')
  })

  it('dado corrompido ou estranho vira conversa vazia (ou só o que é válido)', () => {
    const k = chaveConversa(1, 1)
    sessionStorage.setItem(k, '{nao é json')
    expect(lerConversa(k)).toEqual([])
    sessionStorage.setItem(k, JSON.stringify([{ papel: 'sistema', texto: 'x' }, { papel: 'usuario', texto: '  ' }, { papel: 'usuario', texto: 'oi' }]))
    expect(lerConversa(k)).toEqual([{ papel: 'usuario', texto: 'oi' }])
  })
})

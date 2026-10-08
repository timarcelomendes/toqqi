// Etapa 5f, regras puras (docs/api-etapa-5f.md §10): textos das opções da Zona de risco com as contagens (plurais e
// milhar em pt-BR), o que sempre fica, a confirmação APAGAR, o resumo do que foi apagado, as mensagens de erro, o aviso
// do topo e o selo da Plataforma com `exclusao_em`, os filtros de Contatos e Empresas → consulta do CSV, a rota livre do
// aceite e a versão 4 dos Termos de uso e da Política de privacidade.
import { describe, expect, it } from 'vitest'
import { ApiError } from '@/api/erros'
import type { ZonaRisco } from '@/api/tipos'
import { ROTAS_LIVRES, redirecionarAceite, textoAbertura, textoVersao } from '@/modulos/geral/legal/aceite'
import { PRIVACIDADE } from '@/modulos/geral/legal/privacidade'
import { TERMOS } from '@/modulos/geral/legal/termos'
import type { Bloco, DocumentoLegal } from '@/modulos/geral/legal/tipos'
import { VERSAO_DOCUMENTOS, VIGENTE_DESDE } from '@/modulos/geral/legal/versao'
import {
  ROTULOS_OPCAO,
  TEXTO_EXPORTACAO,
  apagaAlgo,
  confirmacaoValida,
  contagensDaOpcao,
  juntar,
  mensagemErroExportacao,
  mensagemErroZona,
  mensagemExportacao,
  seloExclusao,
  textoAvisoExclusao,
  textoOpcao,
  textoResultado,
  textoSempreFica,
} from '@/modulos/configuracoes/dadosConta'
import { consultaContatos, consultaEmpresas, textoConsulta } from '@/modulos/contatos/exportacao'

const ZONA: ZonaRisco = {
  opcoes: {
    respostas: { respostas: 1234, acoes_sem_vinculo: 56 },
    contatos: { contatos: 5000, respostas: 1234, convites: 12000, envios: 30500, csat_sem_contato: 340 },
    tudo: { contatos: 5000, respostas: 1234, convites: 12000, envios: 30500, csat_sem_contato: 340, empresas: 300, acoes: 800, indicacoes: 40, ofertas: 25 },
  },
  mantidos: { csat: 412, descadastros: 12, usuarios: 4, formularios: 3 },
}
const VAZIA: ZonaRisco = {
  opcoes: {
    respostas: { respostas: 0, acoes_sem_vinculo: 0 },
    contatos: { contatos: 0, respostas: 0, convites: 0, envios: 0, csat_sem_contato: 0 },
    tudo: { contatos: 0, respostas: 0, convites: 0, envios: 0, csat_sem_contato: 0, empresas: 0, acoes: 0, indicacoes: 0, ofertas: 0 },
  },
  mantidos: { csat: 0, descadastros: 0, usuarios: 1, formularios: 2 },
}

describe('Zona de risco: textos das opções', () => {
  it('Respostas: o texto do contrato, com milhar e plural', () => {
    expect(textoOpcao('respostas', ZONA)).toBe(
      'Apaga 1.234 respostas NPS e de formulários personalizados, inclusive arquivadas. 56 planos de ação ficam sem o vínculo.',
    )
  })

  it('Respostas: singular, sem ações e sem nada', () => {
    const uma: ZonaRisco = { ...ZONA, opcoes: { ...ZONA.opcoes, respostas: { respostas: 1, acoes_sem_vinculo: 1 } } }
    expect(textoOpcao('respostas', uma)).toBe('Apaga 1 resposta NPS ou de formulário personalizado, inclusive arquivada. 1 plano de ação fica sem o vínculo.')
    const semAcoes: ZonaRisco = { ...ZONA, opcoes: { ...ZONA.opcoes, respostas: { respostas: 2, acoes_sem_vinculo: 0 } } }
    expect(textoOpcao('respostas', semAcoes)).toBe('Apaga 2 respostas NPS e de formulários personalizados, inclusive arquivadas.')
    expect(textoOpcao('respostas', VAZIA)).toBe('Não há respostas NPS nem de formulários personalizados para apagar.')
  })

  it('Contatos: o que apaga (só o que é maior que zero), as CSAT que ficam sem o contato e o que perde o contato', () => {
    expect(textoOpcao('contatos', ZONA)).toBe(
      'Apaga 5.000 contatos, 1.234 respostas NPS e de formulários personalizados, 12.000 convites e 30.500 envios, com o histórico de importações. ' +
        '340 respostas CSAT ficam, sem o contato. Planos de ação, indicações e ofertas ficam, sem o contato.',
    )
    const poucos: ZonaRisco = {
      ...ZONA,
      opcoes: { ...ZONA.opcoes, contatos: { contatos: 1, respostas: 0, convites: 0, envios: 1, csat_sem_contato: 1 } },
    }
    expect(textoOpcao('contatos', poucos)).toBe(
      'Apaga 1 contato e 1 envio, com o histórico de importações. 1 resposta CSAT fica, sem o contato. Planos de ação, indicações e ofertas ficam, sem o contato.',
    )
    expect(textoOpcao('contatos', VAZIA)).toBe('Não há contatos nem respostas para apagar.')
  })

  it('Recomeçar do zero: tudo, na ordem (empresas primeiro), e o que fica', () => {
    expect(textoOpcao('tudo', ZONA)).toBe(
      'Apaga 300 empresas, 5.000 contatos, 1.234 respostas NPS e de formulários personalizados, 12.000 convites, 30.500 envios, 800 planos de ação, 40 indicações e 25 ofertas, com o histórico de importações. ' +
        'As respostas CSAT ficam, sem o contato e sem a empresa. Responsáveis e cadastros (grupos, segmentos, perfis e cargos) também ficam.',
    )
    expect(textoOpcao('tudo', VAZIA)).toBe('Não há nada para apagar.')
  })

  it('rótulos dos rádios e títulos do diálogo', () => {
    expect(Object.values(ROTULOS_OPCAO).map((r) => r.rotulo)).toEqual(['Respostas', 'Contatos', 'Recomeçar do zero'])
    expect(ROTULOS_OPCAO.respostas.titulo).toBe('Apagar as respostas?')
    expect(ROTULOS_OPCAO.contatos.titulo).toBe('Apagar os contatos?')
    expect(ROTULOS_OPCAO.tudo.titulo).toBe('Apagar tudo?')
  })

  it('"Sempre fica": com as CSAT e a lista de descadastro; sem CSAT, sem o item', () => {
    expect(textoSempreFica(ZONA.mantidos)).toBe('Sempre fica: usuários, configurações, formulários, 412 respostas CSAT e a lista de descadastro (12).')
    expect(textoSempreFica({ ...ZONA.mantidos, csat: 1, descadastros: 1500 })).toBe(
      'Sempre fica: usuários, configurações, formulários, 1 resposta CSAT e a lista de descadastro (1.500).',
    )
    expect(textoSempreFica(VAZIA.mantidos)).toBe('Sempre fica: usuários, configurações, formulários e a lista de descadastro (0).')
  })

  it('apagaAlgo: só conta o que é apagado (ações sem vínculo e CSAT sem contato não contam)', () => {
    expect(apagaAlgo(contagensDaOpcao(ZONA, 'respostas'))).toBe(true)
    expect(apagaAlgo(contagensDaOpcao(VAZIA, 'tudo'))).toBe(false)
    expect(apagaAlgo({ respostas: 0, acoes_sem_vinculo: 3 })).toBe(false)
    expect(apagaAlgo({ contatos: 0, respostas: 0, convites: 0, envios: 0, csat_sem_contato: 9 })).toBe(false)
    expect(apagaAlgo({ ofertas: 1 })).toBe(true)
    expect(apagaAlgo(null)).toBe(false)
  })

  it('juntar: "a", "a e b", "a, b e c"', () => {
    expect(juntar([])).toBe('')
    expect(juntar(['a'])).toBe('a')
    expect(juntar(['a', 'b'])).toBe('a e b')
    expect(juntar(['a', 'b', 'c'])).toBe('a, b e c')
  })
})

describe('Zona de risco: confirmação, resultado e erros', () => {
  it('APAGAR em qualquer caixa e sem espaços nas pontas (a regra da API)', () => {
    for (const ok of ['APAGAR', 'apagar', 'Apagar', ' APAGAR ', '\tapagar\n']) expect(confirmacaoValida(ok)).toBe(true)
    for (const nao of ['', '  ', 'APAGA', 'APAGAR!', 'A PAGAR', 'apagar tudo', null, undefined]) expect(confirmacaoValida(nao)).toBe(false)
  })

  it('"Pronto: apagamos …" com o que foi apagado (milhar, plural, sem as ações que perderam o vínculo)', () => {
    expect(textoResultado({ respostas: 1234, acoes_sem_vinculo: 56 })).toBe('Pronto: apagamos 1.234 respostas.')
    expect(textoResultado(ZONA.opcoes.tudo as unknown as Record<string, number>)).toBe(
      'Pronto: apagamos 300 empresas, 5.000 contatos, 1.234 respostas, 12.000 convites, 30.500 envios, 800 planos de ação, 40 indicações e 25 ofertas.',
    )
    expect(textoResultado({ contatos: 1, envios: 1, csat_sem_contato: 2 })).toBe('Pronto: apagamos 1 contato e 1 envio.')
    expect(textoResultado({ respostas: 0 })).toBe('Pronto: não havia nada para apagar.')
    expect(textoResultado(null)).toBe('Pronto: não havia nada para apagar.')
  })

  it('erros do POST: a mensagem da API; 429 explica o limite de 5 por hora', () => {
    expect(mensagemErroZona(new ApiError(409, 'zona_em_andamento', 'Já tem uma exclusão em andamento nesta conta.'))).toBe(
      'Já tem uma exclusão em andamento nesta conta.',
    )
    const indisponivel = 'Não deu para apagar agora e nada foi apagado. Tente de novo em alguns minutos.'
    expect(mensagemErroZona(new ApiError(503, 'zona_indisponivel', indisponivel))).toBe(indisponivel)
    expect(mensagemErroZona(new ApiError(429, 'muitas_tentativas', 'Muitas tentativas. Aguarde um minuto.'))).toBe(
      'Você chegou ao limite de 5 tentativas por hora. Tente de novo mais tarde.',
    )
    expect(mensagemErroZona(new Error('x'))).toMatch(/nada foi apagado/)
  })
})

describe('Exportar todos os dados', () => {
  it('texto da seção e andamento (gerando, erro, pronto)', () => {
    expect(TEXTO_EXPORTACAO).toBe('Um arquivo .zip com uma planilha (CSV) por assunto. Senhas e chaves não vão.')
    expect(mensagemExportacao({ baixando: true, erro: null, pronta: false })).toEqual({ tom: 'info', texto: 'Gerando o arquivo… pode levar até um minuto.' })
    expect(mensagemExportacao({ baixando: false, erro: 'Falhou.', pronta: false })).toEqual({ tom: 'erro', texto: 'Falhou.' })
    expect(mensagemExportacao({ baixando: false, erro: null, pronta: true })?.tom).toBe('sucesso')
    expect(mensagemExportacao({ baixando: false, erro: null, pronta: false })).toBeNull()
  })

  it('409 com a mensagem da API; 429 com o limite de 5 por hora', () => {
    const emAndamento = 'Já tem uma exportação sendo gerada nesta conta. Aguarde terminar.'
    expect(mensagemErroExportacao(new ApiError(409, 'exportacao_em_andamento', emAndamento))).toBe(emAndamento)
    expect(mensagemErroExportacao(new ApiError(429, 'muitas_tentativas', 'Muitas tentativas. Aguarde um minuto.'))).toBe(
      'Você chegou ao limite de 5 exportações por hora. Tente de novo mais tarde.',
    )
    expect(mensagemErroExportacao(new ApiError(0, 'sem_conexao', 'Sem conexão.'))).toBe('Sem conexão.')
  })
})

describe('Exclusão automática: aviso do topo e selo da Plataforma', () => {
  it('administrador: baixar uma cópia ou assinar; os outros: falar com o administrador', () => {
    expect(textoAvisoExclusao('2027-01-15', true)).toEqual({
      texto: 'Os dados desta conta serão excluídos em 15/01/2027. Baixe uma cópia ou assine um plano.',
      admin: true,
    })
    expect(textoAvisoExclusao('2027-01-15', false)).toEqual({
      texto: 'Os dados desta conta serão excluídos em 15/01/2027. Fale com o administrador da conta.',
      admin: false,
    })
    expect(textoAvisoExclusao(null, true)).toBeNull()
    expect(textoAvisoExclusao(undefined, false)).toBeNull()
    expect(textoAvisoExclusao('não é data', true)).toBeNull()
  })

  it('selo: "Exclusão em dd/mm/aaaa"', () => {
    expect(seloExclusao('2027-01-15')).toBe('Exclusão em 15/01/2027')
    expect(seloExclusao(null)).toBeNull()
  })
})

describe('"Exportar CSV": filtros da aba → consulta', () => {
  it('Contatos: sem os vazios e sem a página; a empresa vai como empresa_id; a busca sem espaços nas pontas', () => {
    const c = consultaContatos({ busca: '  ana  ', empresa: { id: 14, nome: 'Mercado' }, grupo_id: 3, responsavel_id: '', perfil_id: '', ativo: 'todos' })
    expect(c).toEqual({ busca: 'ana', empresa_id: 14, grupo_id: 3, ativo: 'todos' })
    expect(textoConsulta(c)).toBe('busca=ana&empresa_id=14&grupo_id=3&ativo=todos')
    expect(consultaContatos({ busca: '', empresa: null, grupo_id: '', responsavel_id: '', perfil_id: '', ativo: 'true' })).toEqual({ ativo: 'true' })
    expect(textoConsulta(consultaContatos({ busca: 'joão & cia', empresa: null, grupo_id: '', responsavel_id: 7, perfil_id: 2, ativo: 'false' }))).toBe(
      'busca=jo%C3%A3o+%26+cia&responsavel_id=7&perfil_id=2&ativo=false',
    )
  })

  it('Empresas: os mesmos filtros da lista', () => {
    expect(consultaEmpresas({ busca: ' Bom ', grupo_id: '', segmento_id: 5, responsavel_id: 2, ativa: 'todas' })).toEqual({
      busca: 'Bom',
      segmento_id: 5,
      responsavel_id: 2,
      ativa: 'todas',
    })
    expect(textoConsulta(consultaEmpresas({ busca: '', grupo_id: 1, segmento_id: '', responsavel_id: '', ativa: 'true' }))).toBe('grupo_id=1&ativa=true')
  })
})

describe('Dados da conta livre com o aceite pendente', () => {
  const rota = (fullPath: string) => ({ path: fullPath, fullPath, meta: { logado: true } })
  const PENDENTE = { versao_atual: 4, versao_aceita: 3, aceito_em: '2026-10-02T12:00:00Z', pendente: true }

  it('/configuracoes/dados-da-conta está em ROTAS_LIVRES; as outras seções de Configurações, não', () => {
    expect(ROTAS_LIVRES).toContain('/configuracoes/dados-da-conta')
    expect(redirecionarAceite(rota('/configuracoes/dados-da-conta'), { logado: true, aceite: PENDENTE })).toBeNull()
    expect(redirecionarAceite(rota('/configuracoes/empresa'), { logado: true, aceite: PENDENTE })).toEqual({
      path: '/aceite',
      query: { de: '/configuracoes/empresa' },
    })
  })
})

describe('Termos de uso e Política de privacidade (versão 4)', () => {
  /** Todo o texto de um bloco (com os textos dos links), para procurar frases. */
  const textoDe = (t: string | Array<string | { texto: string }>) => (typeof t === 'string' ? t : t.map((p) => (typeof p === 'string' ? p : p.texto)).join(''))
  const textoBloco = (b: Bloco): string =>
    b.tipo === 'p' ? textoDe(b.texto) : b.tipo === 'lista' ? b.itens.map(textoDe).join('\n') : b.linhas.map((l) => l.map(textoDe).join(' | ')).join('\n')
  const secao = (d: DocumentoLegal, id: string) => {
    const s = d.secoes.find((x) => x.id === id)
    if (!s) throw new Error(`Sem a seção ${id}`)
    return s.blocos.map(textoBloco).join('\n')
  }

  it('versão 8 (5f, 5g, na 5k planos e cobrança e, em 08/10, o Entrar com o Google), vigente desde 08/10/2026 (a tela de aceite mostra essa data)', () => {
    expect(VERSAO_DOCUMENTOS).toBe(8)
    expect(VIGENTE_DESDE).toBe('2026-10-08')
    expect(textoVersao(VERSAO_DOCUMENTOS)).toBe('Versão 8 · vigente desde 08/10/2026')
    expect(textoAbertura({ versao_atual: 4, versao_aceita: 3, aceito_em: '2026-10-02T12:00:00Z', pendente: true })).toBe(
      'Atualizamos os Termos de uso e a Política de privacidade em 08/10/2026.',
    )
  })

  it('Política › Quais dados tratamos: o registro de acesso de usuários e de quem responde (data, hora e IP)', () => {
    const dados = secao(PRIVACIDADE, 'dados-que-tratamos')
    expect(dados).toContain('Usuários do Toqqi (registro de acesso)')
    expect(dados).toContain('cada entrada no Toqqi e de cada tentativa de entrar, do cadastro, do pedido de acesso e da troca de senha')
    expect(dados).toContain('data, hora e IP do envio da resposta ou de uma indicação')
  })

  it('Política › Por quanto tempo guardamos: sem "[a confirmar]" de cancelamento, teste e acesso; 90 dias, aviso 7 dias antes, 6 meses', () => {
    const retencao = secao(PRIVACIDADE, 'retencao')
    expect(retencao).toContain('guardamos os dados por 90 dias')
    expect(retencao).toContain('Avisamos os administradores por e-mail 7 dias antes da exclusão')
    expect(retencao).toContain('excluímos de forma definitiva e automática tudo o que é da conta, inclusive o registro de auditoria, o histórico de cobranças e os aceites dos termos')
    expect(retencao).toContain('por 6 meses (Marco Civil da Internet, art. 15), guardados à parte, mesmo depois de excluídos o usuário ou a conta')
    expect(retencao).toContain('Registro de auditoria e histórico de cobranças: enquanto a conta existir.')
    expect(retencao).toContain('enquanto a conta existir.')
    // Os três "[a confirmar]" de antes saíram (cancelamento, teste e registros de acesso).
    expect(retencao).not.toContain('[a confirmar: prazo, sugerido 90 dias]')
    expect(retencao).not.toContain('Contas de teste que não assinarem: [a confirmar')
    expect(retencao).not.toContain('[a confirmar: hoje eles são apagados junto com a conta ou o usuário]')
    expect(retencao).not.toContain('[a confirmar: como os dados são eliminados]')
    // O registro de e-mails enviados (etapa 5e) continua igual.
    expect(retencao).toContain('Registro de e-mails enviados (endereço de quem recebeu, assunto, situação e erro): 90 dias.')
  })

  it('Política › Como protegemos (registros fora das telas, só a equipe técnica, ordem judicial) e Seus direitos (portabilidade)', () => {
    expect(secao(PRIVACIDADE, 'seguranca')).toContain('nenhuma tela do Toqqi mostra esses registros. Só a equipe técnica consulta, e só para atender ordem judicial')
    expect(secao(PRIVACIDADE, 'seus-direitos')).toContain('portabilidade dos dados (o administrador da empresa baixa uma cópia de todos os dados da conta')
    expect(secao(PRIVACIDADE, 'seus-direitos')).toContain('Configurações › Dados da conta')
  })

  it('Termos: teste e "Fim do contrato" com as mesmas regras (90 dias, aviso 7 dias antes, exclusão automática, assinar cancela)', () => {
    const planos = secao(TERMOS, 'planos-e-pagamento')
    expect(planos).toContain('Se a Empresa não assinar, os dados ficam guardados por 90 dias depois do fim do teste e então são excluídos, como no fim do contrato')
    const tratamento = secao(TERMOS, 'tratamento-de-dados')
    expect(tratamento).toContain('a Empresa tem 90 dias para exportar os dados dela')
    expect(tratamento).toContain('Configurações › Dados da conta')
    expect(tratamento).toContain('Avisamos os administradores por e-mail 7 dias antes da exclusão.')
    expect(tratamento).toContain('excluímos de forma definitiva e automática todos os dados da conta')
    expect(tratamento).toContain('Assinar um plano antes disso cancela a exclusão.')
    expect(tratamento).not.toContain('[a confirmar: prazo, sugerido 90 dias]')
    expect(tratamento).not.toContain('[a confirmar: como os dados são eliminados]')
  })
})

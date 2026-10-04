// Etapa 5g (docs/api-etapa-5g.md): as regras puras de Plataforma › Parâmetros (catálogo, formato, leitura e validação
// dos campos, o que mudou, diálogo de confirmação e histórico), o valor contratado ao trocar de plano, a frase da cota
// em Configurações › IA, os dias do teste e os Termos v6.
import { describe, expect, it } from 'vitest'
import type { GrupoParametrosPlataforma, MudancaParametro, ValorParametro } from '@/api/tipos'
import { diasDoTeste, DIAS_TESTE_PADRAO } from '@/composables/planosPublicos'
import { textoContratado } from '@/modulos/assinatura/logica'
import { TERMOS } from '@/modulos/geral/legal/termos'
import { VERSAO_DOCUMENTOS, VIGENTE_DESDE } from '@/modulos/geral/legal/versao'
import { textoAnalisesPorNivel, textoGastoDaCota } from '@/modulos/ia/logica'
import {
  AVISO_DIMINUI,
  CAMPOS,
  LAYOUT_GRUPOS,
  abaPlataformaDaRota,
  aplicarPadrao,
  campoMudou,
  camposDoGrupo,
  casasDecimais,
  chavesAlteradas,
  difereDoPadrao,
  diminui,
  formDe,
  formatarValor,
  lerCampo,
  lerFormulario,
  lerInteiro,
  linhaMudanca,
  listaNomes,
  mesmoValor,
  rotuloGrupo,
  testaModelo,
  textoAlterado,
  textoConfirmacao,
  textoDoCampo,
  textoPadrao,
} from '@/modulos/plataforma/parametros'

/** Troca o espaço sem quebra do "R$ 149,00" (Intl) por espaço comum. */
const t = (s: string | null | undefined) => (s ?? '').replace(/ /g, ' ')

export const VALORES_PLANOS: Record<string, ValorParametro> = {
  'planos.essencial.preco': '149.00',
  'planos.profissional.preco': '349.00',
  'planos.empresa.preco': '799.00',
  'planos.essencial.contatos': 300,
  'planos.profissional.contatos': 1500,
  'planos.empresa.contatos': null,
}

function grupoPlanos(valores: Record<string, ValorParametro> = {}): GrupoParametrosPlataforma {
  return {
    grupo: 'planos',
    rotulo: 'Planos',
    versao: 0,
    alterado_em: null,
    alterado_por: null,
    valores: { ...VALORES_PLANOS, ...valores },
    padroes: { ...VALORES_PLANOS },
    origens: Object.fromEntries(Object.keys(VALORES_PLANOS).map((k) => [k, 'codigo'])),
  }
}

describe('catálogo e layout', () => {
  it('as 32 chaves do §2, cada uma num grupo, todas na tela (e só uma vez)', () => {
    expect(CAMPOS).toHaveLength(32)
    expect(camposDoGrupo('planos')).toHaveLength(6)
    expect(camposDoGrupo('ia')).toHaveLength(18)
    expect(camposDoGrupo('whatsapp')).toHaveLength(5)
    expect(camposDoGrupo('teste').map((c) => c.chave)).toEqual(['teste.dias', 'teste.plano', 'teste.exclusao_automatica'])
    for (const c of CAMPOS) expect(c.chave.startsWith(`${c.grupo}.`)).toBe(true)
    const naTela = Object.values(LAYOUT_GRUPOS).flatMap((l) => l.blocos.flatMap((b) => [...b.chaves, ...(b.blocos ?? []).flatMap((s) => s.chaves)]))
    expect([...naTela].sort()).toEqual(CAMPOS.map((c) => c.chave).sort())
    expect(rotuloGrupo('whatsapp')).toBe('WhatsApp automático')
    expect(rotuloGrupo('teste')).toBe('Teste e cortesia')
  })
  it('as notas de cada grupo', () => {
    expect(LAYOUT_GRUPOS.planos.nota).toBe('O preço novo vale para assinaturas novas e trocas de plano. Quem já assina continua com o valor contratado.')
    expect(LAYOUT_GRUPOS.ia.nota).toBe('Ao salvar um modelo ou esforço novo, o Toqqi faz uma chamada curta à OpenAI para conferir.')
    expect(LAYOUT_GRUPOS.teste.nota).toBe('Cota, teto e franquia da cortesia e do teste ficam em IA e WhatsApp automático.')
    expect(LAYOUT_GRUPOS.ia.blocos.map((b) => b.legenda)).toEqual([
      'Análises por mês (cota do plano)',
      'Níveis de modelo',
      'Teto de segurança por mês (análise dos comentários e passos das ações)',
    ])
  })
})

describe('formato dos valores', () => {
  it('dinheiro, contatos, inteiros, esforço, plano e exclusão', () => {
    expect(t(formatarValor('planos.essencial.preco', '149.9'))).toBe('R$ 149,90')
    expect(t(formatarValor('planos.empresa.preco', 1299))).toBe('R$ 1.299,00')
    expect(formatarValor('planos.profissional.contatos', 1500)).toBe('1.500')
    expect(formatarValor('planos.empresa.contatos', null)).toBe('sem limite')
    expect(formatarValor('ia.teto.empresa', 20000)).toBe('20.000')
    expect(formatarValor('ia.esforco.rapido', '')).toBe('sem raciocínio')
    expect(formatarValor('ia.esforco.rapido', 'minimal')).toBe('minimal')
    expect(formatarValor('ia.modelo.detalhado', 'gpt-5')).toBe('gpt-5')
    expect(formatarValor('teste.plano', 'profissional')).toBe('Profissional')
    expect(formatarValor('teste.exclusao_automatica', 'ligada')).toBe('Ligada')
    expect(formatarValor('teste.exclusao_automatica', 'simular')).toBe('Simular')
    expect(formatarValor('outra.chave', 3)).toBe('3')
  })
  it('texto do campo e comparação pelos centavos', () => {
    expect(textoDoCampo('planos.essencial.preco', '1250')).toBe('1.250,00')
    expect(textoDoCampo('planos.essencial.contatos', 300)).toBe('300')
    expect(textoDoCampo('planos.empresa.contatos', null)).toBe('')
    expect(mesmoValor('planos.essencial.preco', '149.9', '149.90')).toBe(true)
    expect(mesmoValor('planos.essencial.preco', 149.9, '149.90')).toBe(true)
    expect(mesmoValor('planos.essencial.preco', '149.91', '149.90')).toBe(false)
    expect(mesmoValor('planos.empresa.contatos', null, null)).toBe(true)
    expect(mesmoValor('planos.empresa.contatos', null, 0)).toBe(false)
  })
})

describe('leitura e validação dos campos (as regras da API)', () => {
  const ler = (chave: string, texto: string, semLimite = false) => lerCampo({ textos: { [chave]: texto }, semLimite: { [chave]: semLimite } }, chave)

  it('dinheiro aceita "1.250,00", "1250,5", "149" e "R$ 149,90"; vai com ponto e 2 casas', () => {
    expect(ler('planos.empresa.preco', '1.250,00')).toEqual({ valor: '1250.00' })
    expect(ler('planos.empresa.preco', '1250,5')).toEqual({ valor: '1250.50' })
    expect(ler('planos.essencial.preco', '149')).toEqual({ valor: '149.00' })
    expect(ler('planos.essencial.preco', 'R$ 149,90')).toEqual({ valor: '149.90' })
    expect(ler('planos.essencial.preco', '99.999,99')).toEqual({ valor: '99999.99' })
    expect(ler('planos.essencial.preco', '5')).toEqual({ valor: '5.00' })
  })
  it('dinheiro fora da faixa, com 3 casas, vazio ou ilegível dá a mensagem da API', () => {
    expect(ler('planos.essencial.preco', '4,99')).toEqual({ erro: 'Use um valor entre R$ 5,00 e R$ 99.999,99.' })
    expect(ler('planos.essencial.preco', '100.000,00')).toEqual({ erro: 'Use um valor entre R$ 5,00 e R$ 99.999,99.' })
    expect(ler('planos.essencial.preco', '149,999')).toEqual({ erro: 'Use no máximo 2 casas decimais.' })
    expect(ler('planos.essencial.preco', '1.25,50')).toEqual({ erro: 'Use um valor entre R$ 5,00 e R$ 99.999,99.' })
    expect(ler('planos.essencial.preco', '')).toEqual({ erro: 'Informe o preço.' })
    expect(ler('planos.essencial.preco', 'abc')).toEqual({ erro: 'Use um valor entre R$ 5,00 e R$ 99.999,99.' })
    expect(casasDecimais('149,999')).toBe(3)
    expect(casasDecimais('1.250')).toBe(0)
    expect(casasDecimais('149.9')).toBe(1)
  })
  it('inteiros com a faixa de cada chave; "1.500" vale; "Sem limite" vira null', () => {
    expect(lerInteiro('1.500')).toBe(1500)
    expect(lerInteiro(' 1500 ')).toBe(1500)
    expect(lerInteiro('1,5')).toBeNull()
    expect(lerInteiro('-3')).toBeNull()
    expect(lerInteiro('')).toBeNull()
    expect(ler('planos.essencial.contatos', '1.500')).toEqual({ valor: 1500 })
    expect(ler('planos.essencial.contatos', '0')).toEqual({ erro: 'Use um número inteiro de 1 a 1.000.000, ou marque “Sem limite”.' })
    expect(ler('planos.empresa.contatos', '', true)).toEqual({ valor: null })
    expect(ler('ia.cota.cortesia', '100001')).toEqual({ erro: 'Use um número inteiro de 0 a 100.000.' })
    expect(ler('ia.cota.cortesia', '0')).toEqual({ valor: 0 })
    expect(ler('ia.teto.teste', '1000001')).toEqual({ erro: 'Use um número inteiro de 0 a 1.000.000.' })
    expect(ler('ia.analises.detalhado', '11')).toEqual({ erro: 'Use um número inteiro de 1 a 10.' })
    expect(ler('whatsapp.franquia.teste', '2,5')).toEqual({ erro: 'Use um número inteiro de 0 a 100.000.' })
    expect(ler('teste.dias', '91')).toEqual({ erro: 'Use um número inteiro de 1 a 90.' })
    expect(ler('teste.dias', '7')).toEqual({ valor: 7 })
  })
  it('modelo (espaços das pontas saem), esforço, plano e exclusão', () => {
    expect(ler('ia.modelo.rapido', '  gpt-5-nano  ')).toEqual({ valor: 'gpt-5-nano' })
    expect(ler('ia.modelo.rapido', 'ft:gpt-4o:toqqi.v2_1')).toEqual({ valor: 'ft:gpt-4o:toqqi.v2_1' })
    expect(ler('ia.modelo.rapido', 'gpt 5')).toHaveProperty('erro')
    expect(ler('ia.modelo.rapido', '-gpt')).toHaveProperty('erro')
    expect(ler('ia.modelo.rapido', 'a'.repeat(101))).toHaveProperty('erro')
    expect(ler('ia.modelo.rapido', ' ')).toEqual({
      erro: 'Informe o nome do modelo (até 100 caracteres: letras, números, ponto, hífen, dois-pontos ou sublinhado).',
    })
    expect(ler('ia.esforco.rapido', '')).toEqual({ valor: '' })
    expect(ler('ia.esforco.rapido', 'xhigh')).toEqual({ valor: 'xhigh' })
    expect(ler('ia.esforco.rapido', 'max')).toEqual({ erro: 'Escolha um esforço da lista (ou “Sem raciocínio”).' })
    expect(ler('teste.plano', 'essencial')).toEqual({ valor: 'essencial' })
    expect(ler('teste.plano', 'cortesia')).toEqual({ erro: 'Escolha um dos planos: Essencial, Profissional ou Empresa.' })
    expect(ler('teste.exclusao_automatica', 'ligada')).toEqual({ valor: 'ligada' })
    expect(ler('teste.exclusao_automatica', 'sim')).toEqual({ erro: 'Escolha “ligada” ou “simular”.' })
  })
  it('a ordem dos planos: preços crescentes e limites que não diminuem (null é o maior)', () => {
    const dados = grupoPlanos()
    const form = formDe(dados)
    form.textos['planos.profissional.preco'] = '149,00'
    form.textos['planos.empresa.contatos'] = '1000'
    form.semLimite['planos.empresa.contatos'] = false
    expect(lerFormulario(dados, form).erros).toEqual({
      'planos.profissional.preco': 'O preço do Profissional precisa ser maior que o do Essencial.',
      'planos.empresa.contatos': 'O limite do Empresa não pode ser menor que o do Profissional.',
    })
    form.textos['planos.profissional.preco'] = '349,00'
    form.textos['planos.empresa.preco'] = '300'
    form.semLimite['planos.profissional.contatos'] = true
    expect(lerFormulario(dados, form).erros).toEqual({
      'planos.empresa.preco': 'O preço do Empresa precisa ser maior que o do Profissional.',
      'planos.empresa.contatos': 'O limite do Empresa não pode ser menor que o do Profissional.',
    })
    // Limites iguais valem; sem limite no Empresa também.
    const ok = formDe(dados)
    ok.textos['planos.profissional.contatos'] = '300'
    expect(lerFormulario(dados, ok)).toEqual({ valores: { ...VALORES_PLANOS, 'planos.profissional.contatos': 300 }, erros: {} })
  })
  it('o corpo leva todas as chaves do grupo (as que a tela não conhece, com o valor atual)', () => {
    const dados = { ...grupoPlanos(), valores: { ...VALORES_PLANOS, 'planos.extra.novo': 'x' } }
    expect(lerFormulario(dados, formDe(dados)).valores).toEqual({ ...VALORES_PLANOS, 'planos.extra.novo': 'x' })
  })
})

describe('o que mudou e "Usar o padrão"', () => {
  it('mesmo valor escrito de outro jeito não é mudança; texto ilegível é', () => {
    const dados = grupoPlanos()
    const form = formDe(dados)
    expect(chavesAlteradas(dados, form)).toEqual([])
    form.textos['planos.essencial.preco'] = '149'
    expect(campoMudou(dados, form, 'planos.essencial.preco')).toBe(false)
    form.textos['planos.essencial.preco'] = '159'
    form.textos['planos.essencial.contatos'] = 'abc'
    form.semLimite['planos.empresa.contatos'] = false
    form.textos['planos.empresa.contatos'] = '5000'
    expect(chavesAlteradas(dados, form)).toEqual(['planos.essencial.preco', 'planos.essencial.contatos', 'planos.empresa.contatos'])
  })
  it('difere do padrão e volta a ele', () => {
    const dados = grupoPlanos({ 'planos.essencial.preco': '159.00', 'planos.empresa.contatos': 9000 })
    const form = formDe(dados)
    expect(difereDoPadrao(form, 'planos.essencial.preco', '149.00')).toBe(true)
    expect(difereDoPadrao(form, 'planos.profissional.preco', '349.00')).toBe(false)
    aplicarPadrao(form, 'planos.essencial.preco', '149.00')
    expect(form.textos['planos.essencial.preco']).toBe('149,00')
    expect(difereDoPadrao(form, 'planos.empresa.contatos', null)).toBe(true)
    aplicarPadrao(form, 'planos.empresa.contatos', null)
    expect(form.semLimite['planos.empresa.contatos']).toBe(true)
    expect(difereDoPadrao(form, 'planos.empresa.contatos', null)).toBe(false)
  })
  it('modelo ou esforço mudado: o Toqqi testa na OpenAI', () => {
    expect(testaModelo(['ia.cota.essencial', 'ia.modelo.rapido'])).toBe(true)
    expect(testaModelo(['ia.esforco.detalhado'])).toBe(true)
    expect(testaModelo(['ia.analises.rapido', 'ia.teto.teste'])).toBe(false)
  })
})

describe('textos do cartão', () => {
  it('"Alterado em … por …" ou "Nunca alterado"', () => {
    expect(textoAlterado({ alterado_em: '2026-10-03T17:32:00Z', alterado_por: 'marcelo@toqqi.com' })).toBe('Alterado em 03/10/2026 às 14:32 por marcelo@toqqi.com')
    expect(textoAlterado({ alterado_em: null, alterado_por: null })).toBe('Nunca alterado: valem os padrões.')
  })
  it('"Padrão: …" com a origem', () => {
    expect(t(textoPadrao('planos.essencial.preco', '149.00', 'codigo'))).toBe('Padrão: R$ 149,00, do código.')
    expect(textoPadrao('ia.modelo.equilibrado', 'gpt-5-mini', 'ambiente')).toBe('Padrão: gpt-5-mini, da variável de ambiente.')
    expect(textoPadrao('planos.empresa.contatos', null, 'banco')).toBe('Padrão: sem limite. O valor em uso foi salvo aqui.')
    expect(textoPadrao('ia.esforco.rapido', '', undefined)).toBe('Padrão: sem raciocínio.')
  })
})

describe('diálogo de confirmação e histórico', () => {
  const m = (chave: string, de: MudancaParametro['de'], para: MudancaParametro['para']): MudancaParametro => ({ chave, de, para })

  it('linha do histórico', () => {
    expect(t(linhaMudanca(m('planos.essencial.preco', '149.00', '159.00')))).toBe('Preço do Essencial: R$ 149,00 → R$ 159,00')
    expect(linhaMudanca(m('planos.empresa.contatos', null, 5000))).toBe('Contatos do Empresa: sem limite → 5.000')
    expect(linhaMudanca(m('whatsapp.franquia.cortesia', 200, 150))).toBe('Franquia de WhatsApp da cortesia: 200 → 150')
    expect(linhaMudanca(m('ia.esforco.rapido', 'minimal', ''))).toBe('Esforço do nível Rápido: minimal → sem raciocínio')
    expect(linhaMudanca(m('teste.exclusao_automatica', 'simular', 'ligada'))).toBe('Exclusão automática: Simular → Ligada')
    expect(linhaMudanca(m('chave.nova', 1, 2))).toBe('chave.nova: 1 → 2')
  })
  it('nomes das contas: todas ("Alfa, Beta e Gama") ou com reticências quando há mais', () => {
    expect(listaNomes(['Alfa', 'Beta'], 12)).toBe('Alfa, Beta…')
    expect(listaNomes(['Alfa', 'Beta', 'Gama'], 3)).toBe('Alfa, Beta e Gama')
    expect(listaNomes(['Alfa'], 1)).toBe('Alfa')
    expect(listaNomes([], 4)).toBe('')
  })
  it('contatos que diminuem: quantas contas passam do limite, com exemplos, e o aviso de que vale na hora', () => {
    const c = textoConfirmacao('Planos', {
      mudancas: [m('planos.essencial.contatos', 300, 250), m('planos.essencial.preco', '149.00', '159.00'), m('planos.empresa.contatos', null, 20000)],
      impactos: [
        { chave: 'planos.essencial.contatos', contas: 12, exemplos: [{ id: 1, nome: 'Alfa', uso: 320 }, { id: 2, nome: 'Beta', uso: 310 }] },
        { chave: 'planos.empresa.contatos', contas: 1, exemplos: [{ id: 3, nome: 'Gama', uso: 25000 }] },
      ],
    })
    expect(c.titulo).toBe('Confirmar as mudanças em Planos?')
    expect(c.linhas.map((l) => t(l.texto))).toEqual([
      'Contatos do Essencial: 300 → 250. 12 contas têm mais de 250 contatos ativos (Alfa, Beta…): ficam com eles, mas não cadastram, importam nem reativam contatos.',
      'Preço do Essencial: R$ 149,00 → R$ 159,00. Vale para assinaturas novas e trocas de plano.',
      'Contatos do Empresa: sem limite → 20.000. 1 conta tem mais de 20.000 contatos ativos (Gama): fica com eles, mas não cadastra, importa nem reativa contatos.',
    ])
    expect(c.aviso).toBe('Vale na hora para todas as contas, inclusive quem já assina. Os Termos prometem aviso com antecedência razoável.')
    expect(c.aviso).toBe(AVISO_DIMINUI)
  })
  it('cota, teto e franquia que diminuem; análises que aumentam; exclusão ligada; nenhuma conta', () => {
    const c = textoConfirmacao('IA', {
      mudancas: [
        m('ia.cota.essencial', 500, 300),
        m('ia.teto.teste', 1000, 800),
        m('ia.analises.equilibrado', 1, 2),
        m('ia.cota.empresa', 2000, 1500),
        m('ia.analises.rapido', 1, 2),
      ],
      impactos: [
        { chave: 'ia.cota.essencial', contas: 3, exemplos: [] },
        { chave: 'ia.teto.teste', contas: 1, exemplos: [] },
        { chave: 'ia.analises.equilibrado', contas: 8, exemplos: [] },
        { chave: 'ia.cota.empresa', contas: 0, exemplos: [] },
        { chave: 'ia.analises.rapido', contas: 1, exemplos: [] },
      ],
    })
    expect(c.linhas.map((l) => l.texto)).toEqual([
      'Cota de IA do Essencial: 500 → 300. 3 contas já usaram 300 ou mais neste mês.',
      'Teto de IA do teste: 1.000 → 800. 1 conta já usou 800 ou mais neste mês.',
      'Análises por uso do nível Equilibrado: 1 → 2. 8 contas usam este nível.',
      'Cota de IA do Empresa: 2.000 → 1.500. Nenhuma conta usou 1.500 ou mais neste mês.',
      'Análises por uso do nível Rápido: 1 → 2. 1 conta usa este nível.',
    ])
    expect(c.aviso).toBe(AVISO_DIMINUI)
    const e = textoConfirmacao('Teste e cortesia', { mudancas: [m('teste.exclusao_automatica', 'simular', 'ligada'), m('teste.dias', 14, 7)], impactos: [] })
    expect(e.linhas.map((l) => l.texto)).toEqual([
      'Exclusão automática: Simular → Ligada. Na próxima rodada (9h), contas encerradas há 90 dias passam a ser avisadas e excluídas de vez.',
      'Dias de teste: 14 → 7.',
    ])
    // Ligar a exclusão e mudar os dias não diminuem limites: sem o aviso.
    expect(e.aviso).toBeNull()
  })
  it('subir limites não diminui nada', () => {
    expect(diminui(m('ia.cota.essencial', 100, 150))).toBe(false)
    expect(diminui(m('planos.empresa.contatos', 5000, null))).toBe(false)
    expect(diminui(m('planos.empresa.contatos', null, 5000))).toBe(true)
    expect(diminui(m('ia.analises.detalhado', 2, 1))).toBe(false)
    expect(diminui(m('planos.essencial.preco', '149.00', '99.00'))).toBe(false)
    expect(textoConfirmacao('WhatsApp automático', { mudancas: [m('whatsapp.franquia.teste', 20, 40)], impactos: [] }).aviso).toBeNull()
  })
})

describe('abas da Plataforma', () => {
  it('/plataforma/parametros abre Parâmetros; o resto, Contas', () => {
    expect(abaPlataformaDaRota('parametros')).toBe('parametros')
    expect(abaPlataformaDaRota(['parametros'])).toBe('parametros')
    expect(abaPlataformaDaRota('contas')).toBe('contas')
    expect(abaPlataformaDaRota(undefined)).toBe('contas')
  })
})

describe('assinatura: o valor contratado no cartão do plano atual', () => {
  it('só quando difere do preço de hoje', () => {
    expect(t(textoContratado('349.00', '399.00'))).toBe('Você paga R$ 349,00; hoje o plano custa R$ 399,00.')
    expect(textoContratado('349.00', 349)).toBeNull()
    expect(textoContratado(null, '399.00')).toBeNull()
  })
})

describe('Configurações › IA: análises por nível vindas da API', () => {
  it('lista os níveis com as análises; sem elas, a frase não cita números', () => {
    const modelos = [
      { rotulo: 'Rápido', analises: 1 },
      { rotulo: 'Equilibrado', analises: 1 },
      { rotulo: 'Mais detalhado', analises: 3 },
    ]
    expect(textoAnalisesPorNivel(modelos)).toBe('Rápido 1, Equilibrado 1 e Mais detalhado 3')
    expect(textoAnalisesPorNivel([{ rotulo: 'Rápido' }])).toBeNull()
    expect(textoGastoDaCota(modelos)).toBe(
      'Cada pergunta ao ToqqiAI, cada resumo do painel e cada parecer dos relatórios usam análises da cota conforme o nível do modelo: Rápido 1, Equilibrado 1 e Mais detalhado 3. A análise de cada resposta e os passos das ações não entram nesta conta.',
    )
    expect(textoGastoDaCota(undefined)).toContain('conforme o nível do modelo. A análise')
  })
})

describe('dias do teste (GET /publico/planos)', () => {
  it('teste.dias inteiro e positivo; senão, null (a tela fica com 14)', () => {
    expect(DIAS_TESTE_PADRAO).toBe(14)
    expect(diasDoTeste({ teste: { dias: 7, plano: 'essencial', whatsapp: 20, ia_teto: 1000 } })).toBe(7)
    expect(diasDoTeste({ teste: { dias: 0 } as never })).toBeNull()
    expect(diasDoTeste({ teste: { dias: '7' } as never })).toBeNull()
    expect(diasDoTeste(null)).toBeNull()
  })
})

describe('Termos de uso v6 (etapa 5g)', () => {
  const texto = JSON.stringify(TERMOS)
  it('versão 6, vigente desde 03/10/2026', () => {
    expect([VERSAO_DOCUMENTOS, VIGENTE_DESDE]).toEqual([6, '2026-10-03'])
  })
  it('o preço é o da contratação; limites e cotas podem mudar, com aviso se diminuírem', () => {
    expect(texto).toContain(
      'O preço é o mostrado na contratação e só muda por reajuste, como abaixo. Limites e cotas dos planos podem mudar; se diminuírem, avisamos com antecedência razoável.',
    )
    expect(texto).not.toContain('Os preços e limites vigentes são os que aparecem lá no momento da contratação.')
  })
  it('na IA, as análises dependem do nível (a tela mostra quantas)', () => {
    expect(texto).toContain('usa análises da cota de IA do plano, conforme o nível de modelo escolhido em Configurações › IA (a tela mostra quantas).')
    expect(texto).not.toContain('2 no nível Mais detalhado')
  })
})

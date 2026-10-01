import { describe, expect, it } from 'vitest'
import type { FranquiaWhatsapp, WhatsappIntegracao } from '@/api/tipos'
import {
  CHAVE_EXEMPLO,
  EXEMPLO_PESQUISA,
  aspasShell,
  avisoCanal,
  canalUsaWhatsapp,
  confirmarGuardado,
  disponibilidadeCanais,
  estadoFranquia,
  exemploCurl,
  exemploCurlTeste,
  explicacaoFranquia,
  fecharSegredo,
  lerPaginaEntregas,
  modeloSugerido,
  mostrarSegredo,
  podeFecharSegredo,
  prefixoMascarado,
  situacaoWebhook,
  urlApi,
  validarUrlWebhook,
} from '@/modulos/integracoes/logica'
import { ORIGENS_DESCADASTRO, SITUACOES_ENVIO, rotuloDe, situacaoEnvio } from '@/modulos/envios/logica'
import { CANAIS_CONFIG, rotuloEventoWebhook } from '@/utils/rotulos'
import { filtrarNavegacao, navegacaoAdministracao } from '@/layouts/navegacao'

const franquia = (usadas_mes: number, limite = 100, extra: Partial<FranquiaWhatsapp> = {}): FranquiaWhatsapp => ({
  plano: 'profissional',
  limite,
  usadas_mes,
  excedente_ativo: false,
  excedentes_mes: 0,
  valor_excedente: 1.5,
  ...extra,
})

const whats = (extra: Partial<WhatsappIntegracao> = {}): WhatsappIntegracao => ({
  conectado: true,
  numero_exibicao: '+55 11 91234-5678',
  nome_verificado: 'Distribuidora Exemplo',
  phone_number_id: '1065',
  waba_id: '1022',
  modelo: { nome: 'pesquisa_satisfacao', idioma: 'pt_BR' },
  ativo: true,
  franquia: franquia(10),
  ultimo_erro: null,
  webhook_url: 'https://api.toqqi.com.br/publico/whatsapp/webhook',
  webhook_verificacao: 'abc',
  ...extra,
})

describe('franquia do WhatsApp', () => {
  it('abaixo de 80% está ok (verde)', () => {
    const e = estadoFranquia(franquia(32, 90))
    expect(e.nivel).toBe('ok')
    expect(e.tom).toBe('sucesso')
    expect(e.percentual).toBe(35)
    expect(e.restantes).toBe(58)
    expect(e.resumo).toBe('32 de 90 no mês')
  })

  it('a partir de 80% muda para atenção', () => {
    expect(estadoFranquia(franquia(79)).nivel).toBe('ok')
    expect(estadoFranquia(franquia(80)).nivel).toBe('atencao')
    expect(estadoFranquia(franquia(32, 40)).tom).toBe('atencao')
  })

  it('só mostra 100% quando acabou de verdade', () => {
    expect(estadoFranquia(franquia(199, 200)).percentual).toBe(99)
    expect(estadoFranquia(franquia(199, 200)).nivel).toBe('atencao')
    const fim = estadoFranquia(franquia(200, 200))
    expect(fim).toMatchObject({ nivel: 'esgotada', tom: 'erro', percentual: 100, restantes: 0 })
  })

  it('passou do limite (excedentes) continua em 100%, sem restantes negativos', () => {
    const e = estadoFranquia(franquia(230, 200))
    expect(e.percentual).toBe(100)
    expect(e.restantes).toBe(0)
  })

  it('dados ausentes ou limite zero contam como esgotada', () => {
    expect(estadoFranquia(null).nivel).toBe('esgotada')
    expect(estadoFranquia(franquia(0, 0)).nivel).toBe('esgotada')
  })

  it('explica o que acontece em cada estado', () => {
    expect(explicacaoFranquia(franquia(10, 100))).toContain('Restam 90 mensagens')
    expect(explicacaoFranquia(franquia(99, 100))).toContain('Restam 1 mensagem neste mês')
    expect(explicacaoFranquia(franquia(85, 100))).toContain('por e-mail')
    expect(explicacaoFranquia(franquia(100, 100))).toContain('vão por e-mail')
    const extra = explicacaoFranquia(franquia(103, 100, { excedente_ativo: true, excedentes_mes: 3 }))
    expect(extra).toMatch(/R\$\s1,50/)
    expect(extra).toContain('3 extras')
  })
})

describe('exemplos prontos (cURL)', () => {
  it('junta a base com o caminho sem barra dobrada', () => {
    expect(urlApi('https://api.toqqi.com.br/', '/integracao/teste')).toBe('https://api.toqqi.com.br/integracao/teste')
    expect(urlApi('/api', 'integracao/pesquisas')).toBe('/api/integracao/pesquisas')
  })

  it('protege aspas simples para o shell', () => {
    expect(aspasShell("Pão d'Ouro")).toBe(`'Pão d'\\''Ouro'`)
  })

  it('monta o POST de pesquisas com a chave e um corpo JSON válido', () => {
    const c = exemploCurl('https://api.toqqi.com.br/')
    const linhas = c.split('\n')
    expect(linhas[0]).toBe('curl -X POST "https://api.toqqi.com.br/integracao/pesquisas" \\')
    expect(c).toContain(`-H "X-Api-Key: ${CHAVE_EXEMPLO}"`)
    expect(c).toContain('-H "Content-Type: application/json"')
    const corpo = c.slice(c.indexOf("-d '") + 4, c.lastIndexOf("'"))
    expect(JSON.parse(corpo)).toEqual(EXEMPLO_PESQUISA)
    expect(EXEMPLO_PESQUISA.contexto).toMatchObject({ pedido: expect.any(String), motorista: expect.any(String), rota: expect.any(String) })
  })

  it('usa a chave informada e escapa aspas do corpo', () => {
    const c = exemploCurl('https://x.com', 'tq_live_abc', { nome: "D'Ávila" })
    expect(c).toContain('X-Api-Key: tq_live_abc')
    expect(c).toContain(`D'\\''Ávila`)
  })

  it('monta o GET de teste da chave', () => {
    expect(exemploCurlTeste('https://api.toqqi.com.br')).toBe(
      `curl "https://api.toqqi.com.br/integracao/teste" \\\n  -H "X-Api-Key: ${CHAVE_EXEMPLO}"`,
    )
  })
})

describe('canais de envio', () => {
  it('e-mail sempre disponível; WhatsApp só conectado', () => {
    const sem = disponibilidadeCanais(whats({ conectado: false }))
    expect(sem.email.disponivel).toBe(true)
    expect(sem.whatsapp.disponivel).toBe(false)
    expect(sem.whatsapp_e_email.disponivel).toBe(false)
    expect(sem.whatsapp.motivo).toContain('Integrações')

    const com = disponibilidadeCanais(whats())
    expect(com.whatsapp).toEqual({ disponivel: true, motivo: null })
    expect(com.whatsapp_e_email.disponivel).toBe(true)
  })

  it('sem conseguir consultar, WhatsApp fica indisponível', () => {
    const r = disponibilidadeCanais(null)
    expect(r.email.disponivel).toBe(true)
    expect(r.whatsapp.disponivel).toBe(false)
  })

  it('sabe quais canais usam WhatsApp', () => {
    expect(canalUsaWhatsapp('email')).toBe(false)
    expect(canalUsaWhatsapp('whatsapp')).toBe(true)
    expect(canalUsaWhatsapp('whatsapp_e_email')).toBe(true)
    expect(canalUsaWhatsapp(undefined)).toBe(false)
  })

  it('avisa quando o canal escolhido não vai sair pelo WhatsApp', () => {
    expect(avisoCanal('email', whats({ conectado: false }))).toBeNull()
    expect(avisoCanal('whatsapp', whats())).toBeNull()
    expect(avisoCanal('whatsapp', whats({ conectado: false }))).toContain('não está conectado')
    expect(avisoCanal('whatsapp_e_email', whats({ ativo: false }))).toContain('desligado')
    expect(avisoCanal('whatsapp', whats({ franquia: franquia(100, 100) }))).toContain('franquia')
    expect(avisoCanal('whatsapp', whats({ franquia: franquia(100, 100, { excedente_ativo: true }) }))).toBeNull()
  })

  it('tem rótulo e explicação para os três canais', () => {
    expect(Object.keys(CANAIS_CONFIG)).toEqual(['email', 'whatsapp', 'whatsapp_e_email'])
    for (const c of Object.values(CANAIS_CONFIG)) expect(c.descricao.length).toBeGreaterThan(20)
  })
})

describe('segredo mostrado uma vez', () => {
  it('só fecha depois de confirmar que guardou, e apaga o valor', () => {
    let e = mostrarSegredo('tq_live_x')
    expect(podeFecharSegredo(e)).toBe(false)
    expect(fecharSegredo(e).valor).toBe('tq_live_x')
    e = confirmarGuardado(e)
    expect(podeFecharSegredo(e)).toBe(true)
    expect(fecharSegredo(e)).toEqual({ valor: null, guardado: false })
  })

  it('mascara o prefixo com reticências únicas', () => {
    expect(prefixoMascarado('tq_live_ab12')).toBe('tq_live_ab12…')
    expect(prefixoMascarado('tq_live_ab12…')).toBe('tq_live_ab12…')
    expect(prefixoMascarado(null)).toBe('—')
  })
})

describe('webhooks', () => {
  it('aceita só https público', () => {
    expect(validarUrlWebhook('https://erp.empresa.com.br/toqqi')).toBeNull()
    expect(validarUrlWebhook('')).toContain('Informe')
    expect(validarUrlWebhook('http://erp.empresa.com.br')).toContain('https://')
    expect(validarUrlWebhook('não é url')).toContain('Confira')
    for (const u of ['https://localhost/x', 'https://127.0.0.1/x', 'https://10.0.0.5', 'https://192.168.1.10', 'https://172.20.0.1', 'https://[::1]/x']) {
      expect(validarUrlWebhook(u)).toContain('público')
    }
  })

  it('resume a situação do aviso', () => {
    expect(situacaoWebhook({ ativo: true, ultima_entrega: null, falhas_seguidas: 0 }).rotulo).toBe('Sem avisos ainda')
    expect(situacaoWebhook({ ativo: true, ultima_entrega: { quando: '', status_http: 200, ok: true }, falhas_seguidas: 0 }).tom).toBe('sucesso')
    expect(situacaoWebhook({ ativo: true, ultima_entrega: { quando: '', status_http: 500, ok: false }, falhas_seguidas: 2 }).tom).toBe('erro')
    expect(situacaoWebhook({ ativo: false, ultima_entrega: null, falhas_seguidas: 10 }).rotulo).toBe('Desligado por falhas')
    expect(situacaoWebhook({ ativo: false, ultima_entrega: null, falhas_seguidas: 0 }).rotulo).toBe('Desligado')
  })

  it('lê a página de entregas em lista simples ou paginada', () => {
    const item = (id: number) => ({ id, evento: 'resposta.criada', criado_em: '', tentativas: 1, status_http: 200, ok: true, erro: null })
    const cheia = Array.from({ length: 20 }, (_, i) => item(i))
    expect(lerPaginaEntregas(cheia, 1, 0)).toMatchObject({ temMais: true, tamanho: 20 })
    expect(lerPaginaEntregas(cheia.slice(0, 5), 1, 0).temMais).toBe(false)
    expect(lerPaginaEntregas(cheia.slice(0, 5), 2, 20).temMais).toBe(false)
    expect(lerPaginaEntregas({ itens: cheia, total: 45, pagina: 1, por_pagina: 20 }, 2, 20).temMais).toBe(true)
    expect(lerPaginaEntregas({ itens: cheia.slice(0, 5), total: 45, pagina: 3, por_pagina: 20 }, 3, 20).temMais).toBe(false)
    expect(lerPaginaEntregas(null, 1, 0).itens).toEqual([])
  })

  it('traduz os eventos', () => {
    expect(rotuloEventoWebhook('resposta.criada')).toBe('Nova resposta')
    expect(rotuloEventoWebhook('contato.descadastrado')).toBe('Cliente saiu da lista')
    expect(rotuloEventoWebhook('outro')).toBe('outro')
  })
})

describe('modelo de mensagem sugerido', () => {
  it('tem as três variáveis e o botão de URL dinâmica', () => {
    const m = modeloSugerido('https://app.toqqi.com.br/')
    expect(m.corpo).toContain('{{1}}')
    expect(m.corpo).toContain('{{2}}')
    expect(m.corpo).toContain('{{3}}')
    expect(m.categoria).toBe('Utilidade')
    expect(m.botaoUrl).toBe('https://app.toqqi.com.br/r/{{1}}')
  })
})

describe('envios com WhatsApp automático', () => {
  it('tem as situações novas em português', () => {
    expect(situacaoEnvio('enviado').rotulo).toBe('Enviado')
    expect(situacaoEnvio('entregue').rotulo).toBe('Entregue')
    expect(situacaoEnvio('lido').rotulo).toBe('Lido')
    expect(situacaoEnvio('erro').rotulo).toBe('Não saiu')
    expect(Object.keys(SITUACOES_ENVIO)).toContain('lido')
  })

  it('descadastro pelo WhatsApp', () => {
    expect(rotuloDe(ORIGENS_DESCADASTRO, 'whatsapp')).toBe('Pediu pelo WhatsApp (SAIR)')
  })
})

describe('menu Integrações', () => {
  it('aparece só para o perfil administrador', () => {
    const pode = () => true
    const rotulos = (admin: boolean) => filtrarNavegacao(navegacaoAdministracao, pode, false, admin).map((i) => i.rotulo)
    expect(rotulos(true)).toContain('Integrações')
    expect(rotulos(false)).not.toContain('Integrações')
  })
})

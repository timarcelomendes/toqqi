import { describe, expect, it, vi } from 'vitest'
import type { DadosEmpresaConta } from '@/api/tipos'
import {
  MENSAGENS,
  TEMPO_LIMITE_CEP,
  UFS,
  buscarCep,
  cnpjValido,
  documentoValido,
  corpoDoForm,
  cpfValido,
  formDosDados,
  formatarCep,
  mascaraDocumento,
  mascaraTelefone,
  mesmosDados,
  preencherEndereco,
  siteValido,
  telefoneDoCampo,
  validarEmpresa,
  type FormEmpresa,
} from '@/modulos/configuracoes/empresa'
import { ACEITA_LOGO, LIMITE_LOGO, MENSAGEM_LOGO, conferirLogo, ehImagemDaPlataforma, logoParaCliente } from '@/utils/imagens'

const DADOS: DadosEmpresaConta = {
  nome: 'Transportes Rápidos',
  razao_social: null,
  documento: '11222333000181',
  telefone: '5511912345678',
  email_contato: 'contato@rapidos.com.br',
  site: 'https://www.rapidos.com.br',
  cep: '01310100',
  logradouro: 'Avenida Paulista',
  numero: '1000',
  complemento: null,
  bairro: 'Bela Vista',
  cidade: 'São Paulo',
  uf: 'SP',
  logo_url: null,
  atualizado_em: null,
}

const vazio = (extra: Partial<FormEmpresa> = {}): FormEmpresa => ({ ...formDosDados(null), nome: 'Transportes Rápidos', ...extra })

describe('máscaras', () => {
  it('CEP: 00000-000, só dígitos, no máximo 8', () => {
    expect(formatarCep('01310100')).toBe('01310-100')
    expect(formatarCep('01310')).toBe('01310')
    expect(formatarCep('013101')).toBe('01310-1')
    expect(formatarCep('01310-1009999')).toBe('01310-100')
    expect(formatarCep('ab')).toBe('')
    expect(formatarCep(null)).toBe('')
  })

  it('CNPJ com máscara; com 11 dígitos, vira CPF', () => {
    expect(mascaraDocumento('11222333000181')).toBe('11.222.333/0001-81')
    expect(mascaraDocumento('11.222.333/0001-81')).toBe('11.222.333/0001-81')
    expect(mascaraDocumento('52998224725')).toBe('529.982.247-25')
    expect(mascaraDocumento('1122233300018199')).toBe('11.222.333/0001-81')
  })

  it('telefone brasileiro com máscara; com "+", fica com o código do país e sem cortar', () => {
    expect(mascaraTelefone('11912345678')).toBe('(11) 91234-5678')
    // colado com +55 e máscara: nada se perde (o campo não tem maxlength que corte antes da máscara)
    expect(mascaraTelefone('+55 11 98765-4321')).toBe('(11) 98765-4321')
    expect(mascaraTelefone('1132345678')).toBe('(11) 3234-5678')
    expect(mascaraTelefone('+351 912 345 678')).toBe('+351912345678')
    expect(mascaraTelefone('+')).toBe('+')
  })

  it('telefone salvo (com 55) volta para o campo sem o 55; de outro país, com "+"', () => {
    expect(telefoneDoCampo('5511912345678')).toBe('(11) 91234-5678')
    expect(telefoneDoCampo('551132345678')).toBe('(11) 3234-5678')
    expect(telefoneDoCampo('351912345678')).toBe('+351912345678')
    expect(telefoneDoCampo(null)).toBe('')
  })
})

describe('dados ↔ tela', () => {
  it('a tela mostra com máscaras e null vira vazio', () => {
    const f = formDosDados(DADOS)
    expect(f).toMatchObject({ documento: '11.222.333/0001-81', telefone: '(11) 91234-5678', cep: '01310-100', razao_social: '', complemento: '' })
  })

  it('para a API vão só os dígitos, vazios como null e sem espaços nas pontas', () => {
    const f = { ...formDosDados(DADOS), nome: '  Transportes Rápidos  ', razao_social: '   ', uf: 'sp' }
    expect(corpoDoForm(f)).toEqual({
      nome: 'Transportes Rápidos',
      razao_social: null,
      documento: '11222333000181',
      telefone: '11912345678',
      email_contato: 'contato@rapidos.com.br',
      site: 'https://www.rapidos.com.br',
      cep: '01310100',
      logradouro: 'Avenida Paulista',
      numero: '1000',
      complemento: null,
      bairro: 'Bela Vista',
      cidade: 'São Paulo',
      uf: 'SP',
    })
    expect(corpoDoForm(formDosDados(null))).toMatchObject({ documento: null, telefone: null, cep: null, uf: null })
  })

  it('máscara, espaço a mais ou o 55 no telefone não contam como alteração', () => {
    const original = formDosDados(DADOS)
    expect(mesmosDados({ ...original, nome: 'Transportes Rápidos ', documento: '11222333000181', telefone: '+5511912345678' }, original)).toBe(true)
    expect(mesmosDados({ ...original, numero: '1001' }, original)).toBe(false)
    expect(mesmosDados({ ...original, telefone: '' }, original)).toBe(false)
  })
})

describe('validação (as mesmas regras e mensagens do servidor)', () => {
  it('CPF e CNPJ pelos dígitos verificadores', () => {
    expect(cpfValido('52998224725')).toBe(true)
    expect(cpfValido('52998224724')).toBe(false)
    expect(cpfValido('11111111111')).toBe(false)
    expect(cnpjValido('11222333000181')).toBe(true)
    expect(cnpjValido('45997418000153')).toBe(true)
    expect(cnpjValido('11222333000180')).toBe(false)
    expect(cnpjValido('00000000000000')).toBe(false)
  })

  it('só o nome é obrigatório', () => {
    expect(validarEmpresa(vazio())).toEqual({})
    expect(validarEmpresa(vazio({ nome: ' ' })).nome).toBe(MENSAGENS.nome)
    expect(validarEmpresa(vazio({ nome: 'A' })).nome).toBe(MENSAGENS.nome)
    expect(validarEmpresa(vazio({ nome: 'x'.repeat(121) })).nome).toBe('Use no máximo 120 caracteres.')
  })

  it('documento: CNPJ ou CPF válidos (com ou sem máscara)', () => {
    expect(validarEmpresa(vazio({ documento: '11.222.333/0001-81' }))).toEqual({})
    expect(validarEmpresa(vazio({ documento: '529.982.247-25' }))).toEqual({})
    expect(validarEmpresa(vazio({ documento: '11.222.333/0001-80' })).documento).toBe(MENSAGENS.documento)
    expect(validarEmpresa(vazio({ documento: '123.456' })).documento).toBe(MENSAGENS.documento)
  })

  it('telefone com DDD, sem o zero da operadora; com código do país, 12 ou 13 dígitos', () => {
    expect(validarEmpresa(vazio({ telefone: '(11) 91234-5678' }))).toEqual({})
    expect(validarEmpresa(vazio({ telefone: '+351912345678' }))).toEqual({})
    expect(validarEmpresa(vazio({ telefone: '(01) 2345-6789' })).telefone).toBe(MENSAGENS.telefoneZero)
    expect(validarEmpresa(vazio({ telefone: '(11) 1234' })).telefone).toBe(MENSAGENS.telefone)
  })

  it('e-mail, site, CEP e UF', () => {
    expect(validarEmpresa(vazio({ email_contato: 'contato@' })).email_contato).toBe(MENSAGENS.email_contato)
    expect(validarEmpresa(vazio({ site: 'rapidos' })).site).toBe(MENSAGENS.site)
    expect(validarEmpresa(vazio({ cep: '0131' })).cep).toBe(MENSAGENS.cep)
    expect(validarEmpresa(vazio({ uf: 'XX' })).uf).toBe(MENSAGENS.uf)
    expect(validarEmpresa(vazio({ uf: 'sp', cep: '01310-100', site: 'www.rapidos.com.br', email_contato: 'oi@rapidos.com.br' }))).toEqual({})
    expect(UFS).toHaveLength(27)
  })

  it('site: sem https:// vale; só http/https, com ponto, sem usuário e senha, até 200 caracteres', () => {
    expect(siteValido('www.rapidos.com.br')).toBe(true)
    expect(siteValido('http://rapidos.com.br/contato')).toBe(true)
    expect(siteValido('açaí.com.br')).toBe(true)
    expect(siteValido('rapidos')).toBe(false)
    expect(siteValido('ftp://rapidos.com.br')).toBe(false)
    expect(siteValido('https://ana:senha@rapidos.com.br')).toBe(false)
    expect(siteValido('https://192.168.0.1')).toBe(false)
    expect(siteValido('rapidos .com.br')).toBe(false)
    expect(siteValido(`rapidos.com.br/${'a'.repeat(190)}`)).toBe(false)
  })

  it('limites de tamanho dos textos', () => {
    expect(validarEmpresa(vazio({ numero: '1'.repeat(21) })).numero).toBe('Use no máximo 20 caracteres.')
    expect(validarEmpresa(vazio({ logradouro: 'R'.repeat(151) })).logradouro).toBe('Use no máximo 150 caracteres.')
  })
})

describe('endereço pelo CEP (ViaCEP)', () => {
  const json = (corpo: unknown, status = 200) => new Response(JSON.stringify(corpo), { status })
  const PAULISTA = { cep: '01310-100', logradouro: 'Avenida Paulista', complemento: 'de 612 a 1510 - lado par', bairro: 'Bela Vista', localidade: 'São Paulo', uf: 'SP' }

  it('busca https://viacep.com.br/ws/{cep}/json/ e devolve o endereço', async () => {
    const buscar = vi.fn(async () => json(PAULISTA))
    expect(await buscarCep('01310-100', { fetch: buscar as unknown as typeof fetch })).toEqual({
      logradouro: 'Avenida Paulista',
      bairro: 'Bela Vista',
      cidade: 'São Paulo',
      uf: 'SP',
    })
    expect(buscar).toHaveBeenCalledWith('https://viacep.com.br/ws/01310100/json/', expect.objectContaining({ signal: expect.anything() }))
  })

  it('CEP incompleto nem busca', async () => {
    const buscar = vi.fn(async () => json(PAULISTA))
    expect(await buscarCep('01310-10', { fetch: buscar as unknown as typeof fetch })).toBeNull()
    expect(buscar).not.toHaveBeenCalled()
  })

  it('CEP que não existe, erro do serviço ou sem internet: null, sem aviso', async () => {
    for (const resposta of [async () => json({ erro: true }), async () => json({ erro: 'true' }), async () => json({}, 400), async () => json(null)]) {
      expect(await buscarCep('99999999', { fetch: vi.fn(resposta) as unknown as typeof fetch })).toBeNull()
    }
    const semRede = vi.fn(async () => {
      throw new TypeError('Failed to fetch')
    })
    expect(await buscarCep('01310100', { fetch: semRede as unknown as typeof fetch })).toBeNull()
  })

  it('demorou mais que o tempo limite (~4 s): desiste e devolve null', async () => {
    expect(TEMPO_LIMITE_CEP).toBe(4000)
    const lento = vi.fn(
      (_url: string, init: RequestInit) =>
        new Promise<Response>((_ok, falhar) => init.signal?.addEventListener('abort', () => falhar(new DOMException('cancelado', 'AbortError')))),
    )
    expect(await buscarCep('01310100', { fetch: lento as unknown as typeof fetch, tempoLimite: 20 })).toBeNull()
  })

  it('UF fora da lista não entra', async () => {
    const buscar = vi.fn(async () => json({ ...PAULISTA, uf: 'ZZ' }))
    expect((await buscarCep('01310100', { fetch: buscar as unknown as typeof fetch }))?.uf).toBe('')
  })

  it('preenche só os campos vazios (o que a pessoa escreveu fica)', () => {
    const f = vazio({ logradouro: 'Av. Paulista (escrita à mão)', bairro: '  ' })
    const preenchidos = preencherEndereco(f, { logradouro: 'Avenida Paulista', bairro: 'Bela Vista', cidade: 'São Paulo', uf: 'SP' })
    expect(preenchidos).toEqual(['bairro', 'cidade', 'uf'])
    expect(f).toMatchObject({ logradouro: 'Av. Paulista (escrita à mão)', bairro: 'Bela Vista', cidade: 'São Paulo', uf: 'SP' })
    // Endereço sem logradouro (CEP de cidade pequena): o campo fica vazio para preencher à mão.
    const g = vazio()
    expect(preencherEndereco(g, { logradouro: '', bairro: '', cidade: 'Itu', uf: 'SP' })).toEqual(['cidade', 'uf'])
    expect(g.logradouro).toBe('')
  })
})

describe('logo: conferência antes de enviar', () => {
  const PNG = [0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a, 0, 0, 0, 0x0d]
  const JPEG = [0xff, 0xd8, 0xff, 0xe0, 0, 0x10]
  const GIF = [0x47, 0x49, 0x46, 0x38, 0x39, 0x61, 1, 0]
  const arquivo = (bytes: number[], nome: string, tipo: string, tamanho = bytes.length) => {
    const corpo = new Uint8Array(tamanho)
    corpo.set(bytes)
    return new File([corpo], nome, { type: tipo })
  }

  it('PNG e JPG (pelos primeiros bytes) de até 300 KB passam', async () => {
    expect(await conferirLogo(arquivo(PNG, 'logo.png', 'image/png'))).toBeNull()
    expect(await conferirLogo(arquivo(JPEG, 'logo.jpg', 'image/jpeg'))).toBeNull()
    expect(await conferirLogo(arquivo(PNG, 'logo.png', 'image/png', LIMITE_LOGO))).toBeNull()
    expect(ACEITA_LOGO).toBe('image/png,image/jpeg')
  })

  it('outro formato (mesmo com extensão .png), vazio ou maior que 300 KB: a mesma mensagem da API', async () => {
    expect(MENSAGEM_LOGO).toBe('Use uma imagem PNG ou JPG de até 300 KB.')
    expect(await conferirLogo(arquivo(GIF, 'logo.png', 'image/png'))).toBe(MENSAGEM_LOGO)
    expect(await conferirLogo(new File(['<svg xmlns="http://www.w3.org/2000/svg"/>'], 'logo.svg', { type: 'image/svg+xml' }))).toBe(MENSAGEM_LOGO)
    expect(await conferirLogo(arquivo(PNG, 'grande.png', 'image/png', LIMITE_LOGO + 1))).toBe(MENSAGEM_LOGO)
    expect(await conferirLogo(new File([], 'vazio.png', { type: 'image/png' }))).toBe(MENSAGEM_LOGO)
  })

  it('reconhece a imagem guardada pela plataforma', () => {
    expect(ehImagemDaPlataforma('http://localhost:8000/api/v1/publico/imagens/Ab_cD-123456789012345678901234567890')).toBe(true)
    expect(ehImagemDaPlataforma('https://suaempresa.com.br/logo.png')).toBe(false)
    expect(ehImagemDaPlataforma('data:image/png;base64,iVBORw0KGgo=')).toBe(false)
    expect(ehImagemDaPlataforma(null)).toBe(false)
  })

  it('o cliente vê o logo do formulário; sem ele, o da empresa', () => {
    expect(logoParaCliente('https://x.com.br/f.png', 'https://x.com.br/e.png')).toEqual({ url: 'https://x.com.br/f.png', daEmpresa: false })
    expect(logoParaCliente(null, 'https://x.com.br/e.png')).toEqual({ url: 'https://x.com.br/e.png', daEmpresa: true })
    expect(logoParaCliente('  ', 'https://x.com.br/e.png')).toEqual({ url: 'https://x.com.br/e.png', daEmpresa: true })
    expect(logoParaCliente(null, null)).toEqual({ url: null, daEmpresa: false })
  })
})

describe('CNPJ alfanumérico (Receita Federal, desde 31/07/2026)', () => {
  it('aceita o exemplo oficial, com máscara e minúsculas; recusa DV errado e letra no DV', () => {
    expect(cnpjValido('12ABC34501DE35')).toBe(true)
    expect(documentoValido('12.abc.345/01de-35')).toBe(true)
    expect(cnpjValido('12ABC34501DE36')).toBe(false)
    expect(cnpjValido('12ABC34501DE3A')).toBe(false)
    expect(documentoValido('12.ABC.345/01DE-3')).toBe(false)
    expect(documentoValido('11.222.333/0001-81')).toBe(true) // o numérico continua valendo
  })
})

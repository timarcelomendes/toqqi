// Situação do número na Meta e o registro pelo Toqqi (docs/api-whatsapp-registro.md): a linha "Situação na Meta",
// o cartão "Falta registrar o número na Meta" com o PIN de 6 números, as recusas e o aviso no guia de conexão.
import { afterEach, describe, expect, it } from 'vitest'
import { enableAutoUnmount, flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createMemoryHistory, createRouter } from 'vue-router'
import { h, type Component } from 'vue'
import PainelWhatsapp from '@/modulos/integracoes/PainelWhatsapp.vue'
import GuiaWhatsapp from '@/modulos/integracoes/GuiaWhatsapp.vue'
import { gerarPin, pinFraco, situacaoNumero, soPin } from '@/modulos/integracoes/logica'
import type { NumeroWhatsapp, WhatsappIntegracao } from '@/api'
import { useSessaoStore } from '@/stores/sessao'
import { apiFalsa, type Chamada } from './apiFalsa'

enableAutoUnmount(afterEach)
afterEach(() => {
  document.body.innerHTML = ''
})

const t = (s: string) => s.replace(/\s+/g, ' ').trim()
const MSG_OK = 'Pronto! O número foi registrado na Meta. Em alguns minutos ele aparece como Conectado no WhatsApp Manager.'

function dados(extra: Partial<WhatsappIntegracao> = {}): WhatsappIntegracao {
  return {
    conectado: true,
    numero_exibicao: '+55 11 93220-0234',
    nome_verificado: 'Alfa Distribuidora',
    phone_number_id: '1234567890',
    waba_id: '9876543210',
    modelo: { nome: 'pesquisa_toqqi', idioma: 'pt_BR' },
    ativo: true,
    franquia: { plano: 'profissional', limite: null, usadas_mes: 0, excedente_ativo: false, excedentes_mes: 0, valor_excedente: null },
    ultimo_erro: null,
    webhook_url: 'https://api.toqqi.com/api/v1/publico/whatsapp/webhook',
    webhook_verificacao: 'abc',
    ...extra,
  } as WhatsappIntegracao
}

async function montar(componente: Component, props: Record<string, unknown>): Promise<VueWrapper> {
  setActivePinia(createPinia())
  useSessaoStore().definirSessao(
    {
      token: 't',
      expira_em: '2099-01-01T00:00:00Z',
      usuario: { id: 1, nome: 'Ana', email: 'ana@alfa.com.br', cargo: null, perfil: 'admin', situacao: 'ativo', email_confirmado: true, ultimo_acesso: null, superadmin: false },
      conta: { id: 1, nome: 'Alfa', plano: null, situacao: 'ativa', teste_ate: null },
      permissoes: ['envios.ver', 'configuracoes.gerenciar'],
    } as never,
    false,
  )
  const router = createRouter({ history: createMemoryHistory(), routes: [{ path: '/:qualquer(.*)*', component: { render: () => h('div') } }] })
  await router.push('/integracoes')
  await router.isReady()
  const w = mount(componente, { props, global: { plugins: [router] }, attachTo: document.body })
  await flushPromises()
  return w
}

const pendente: NumeroWhatsapp = { situacao: 'falta_registrar', status: 'PENDING', codigo_confirmado: true }

describe('regras', () => {
  it('a situação em palavras, com o tom', () => {
    expect(situacaoNumero({ situacao: 'registrado', status: 'CONNECTED', codigo_confirmado: true })).toEqual({ rotulo: 'Registrado e pronto para enviar', tom: 'sucesso' })
    expect(situacaoNumero(pendente)).toEqual({ rotulo: 'Pendente: falta registrar o número', tom: 'atencao' })
    expect(situacaoNumero({ situacao: 'atencao', status: 'FLAGGED', codigo_confirmado: true }).rotulo).toBe('Registrado, mas a Meta marcou como "Sinalizado"')
    expect(situacaoNumero({ situacao: 'problema', status: 'BANNED', codigo_confirmado: null })).toEqual({ rotulo: 'A Meta marcou como "Banido"', tom: 'erro' })
    expect(situacaoNumero({ situacao: 'problema', status: 'NOVO_STATUS', codigo_confirmado: null }).rotulo).toBe('A Meta marcou como "NOVO_STATUS"')
    expect(situacaoNumero({ situacao: 'desconhecida', status: null, codigo_confirmado: null })).toEqual({ rotulo: 'A Meta não informou', tom: 'neutro' })
  })

  it('o PIN fica só com 6 números', () => {
    expect(soPin('12a3 45-678')).toBe('123456')
    expect(soPin('４８２９１５')).toBe('')
  })

  it('PIN fácil de adivinhar: repetido ou em sequência', () => {
    for (const p of ['111111', '000000', '123456', '890123', '654321', '210987']) expect(pinFraco(p), p).toBe(true)
    for (const p of ['482915', '112233', '121212', '12345', '']) expect(pinFraco(p), p).toBe(false)
  })

  it('gera 6 números, sorteando de novo enquanto sair um PIN fácil', () => {
    const fila = [1, 2, 3, 4, 5, 6, 4, 8, 2, 9, 1, 5]
    expect(gerarPin(() => fila.shift()!)).toBe('482915')
    for (let i = 0; i < 50; i++) {
      const pin = gerarPin()
      expect(pin).toMatch(/^\d{6}$/)
      expect(pinFraco(pin)).toBe(false)
    }
  })
})

describe('Integrações › WhatsApp: situação do número', () => {
  it('registrado: só a linha "Situação na Meta", sem o cartão do PIN', async () => {
    apiFalsa({ 'GET /integracoes/whatsapp/numero': () => ({ situacao: 'registrado', status: 'CONNECTED', codigo_confirmado: true }) })
    const w = await montar(PainelWhatsapp, { dados: dados() })
    expect(t(w.get('[data-situacao-numero]').text())).toBe('Registrado e pronto para enviar')
    expect(w.find('[data-registro-numero]').exists()).toBe(false)
    expect(w.find('[data-aviso-numero]').exists()).toBe(false)
  })

  it('pendente: registra com o PIN, mostra o aviso e recarrega a conexão', async () => {
    const pins: unknown[] = []
    const { chamadas } = apiFalsa({
      'GET /integracoes/whatsapp/numero': () => pendente,
      'POST /integracoes/whatsapp/registrar': (c: Chamada) => {
        pins.push(c.corpo)
        return { mensagem: MSG_OK, numero: { situacao: 'registrado', status: null, codigo_confirmado: true } }
      },
      'GET /integracoes/whatsapp': () => dados({ ultimo_erro: null }),
    })
    const w = await montar(PainelWhatsapp, { dados: dados({ ultimo_erro: 'A conta do WhatsApp está bloqueada, restrita ou sem número registrado na Meta.' }) })
    expect(t(w.get('[data-situacao-numero]').text())).toBe('Pendente: falta registrar o número')
    const cartao = w.get('[data-registro-numero]')
    expect(t(cartao.text())).toContain('Falta registrar o número na Meta')
    expect(t(cartao.text())).toContain('O Toqqi não guarda o PIN.')
    expect(t(cartao.text())).toContain('A Meta aceita até 10 tentativas a cada 3 dias.')
    expect(cartao.find('[data-falta-codigo]').exists()).toBe(false)
    // PIN curto: nem chega à API
    await cartao.get('input[data-pin]').setValue('4829')
    await cartao.get('form').trigger('submit')
    expect(t(cartao.text())).toContain('O PIN tem 6 números.')
    expect(pins).toHaveLength(0)
    await cartao.get('input[data-pin]').setValue('48-29 15')
    expect((cartao.get('input[data-pin]').element as HTMLInputElement).value).toBe('482915')
    await cartao.get('form').trigger('submit')
    await flushPromises()
    expect(pins).toEqual([{ pin: '482915' }])
    expect(t(w.get('[data-registrado]').text())).toContain(MSG_OK)
    expect(w.find('[data-registro-numero]').exists()).toBe(false)
    expect(t(w.get('[data-situacao-numero]').text())).toBe('Registrado e pronto para enviar')
    expect(chamadas.filter((c) => c.metodo === 'GET' && c.caminho === '/integracoes/whatsapp')).toHaveLength(1)
    expect(w.emitted('atualizado')![0]![0]).toMatchObject({ ultimo_erro: null })
  })

  it('"Gerar PIN" preenche o campo, oferece copiar e registra com ele; PIN fácil digitado ganha o aviso', async () => {
    const pins: unknown[] = []
    apiFalsa({
      'GET /integracoes/whatsapp/numero': () => pendente,
      'POST /integracoes/whatsapp/registrar': (c: Chamada) => {
        pins.push(c.corpo)
        return { mensagem: MSG_OK, numero: { situacao: 'registrado', status: null, codigo_confirmado: true } }
      },
      'GET /integracoes/whatsapp': () => dados(),
    })
    const w = await montar(PainelWhatsapp, { dados: dados() })
    const entrada = () => w.get('input[data-pin]').element as HTMLInputElement
    expect(t(w.get('[data-registro-numero]').text())).toContain('Digite um PIN seu ou gere um.')
    await w.get('input[data-pin]').setValue('123456')
    expect(w.find('[data-pin-fraco]').exists()).toBe(true)
    await w.get('[data-gerar-pin]').trigger('click')
    expect(entrada().value).toMatch(/^\d{6}$/)
    expect(pinFraco(entrada().value)).toBe(false)
    expect(document.activeElement).toBe(entrada())
    const gerado = w.get('[data-pin-gerado]')
    expect(t(gerado.text())).toContain('PIN gerado: anote ou copie antes de registrar.')
    expect(t(gerado.text())).toContain('Copiar PIN')
    const pin = entrada().value
    // mudou um número: passa a ser o digitado
    await w.get('input[data-pin]').setValue(pin.slice(0, 5) + String((Number(pin[5]) + 1) % 10))
    expect(w.find('[data-pin-gerado]').exists()).toBe(false)
    await w.get('[data-gerar-pin]').trigger('click')
    const outro = entrada().value
    await w.get('[data-registro-numero] form').trigger('submit')
    await flushPromises()
    expect(pins).toEqual([{ pin: outro }])
  })

  it('pendente sem o código confirmado: a dica; recusa da Meta em texto simples', async () => {
    const recusa = 'O PIN não confere. Este número já tem verificação em duas etapas: use o PIN dela ou troque o PIN no WhatsApp Manager (no número, em Configurações › Verificação em duas etapas).'
    apiFalsa({
      'GET /integracoes/whatsapp/numero': () => ({ ...pendente, codigo_confirmado: false }),
      'POST /integracoes/whatsapp/registrar': () => new Response(JSON.stringify({ erro: { codigo: 'registro_recusado', mensagem: recusa } }), { status: 409 }),
    })
    const w = await montar(PainelWhatsapp, { dados: dados() })
    expect(w.find('[data-falta-codigo]').exists()).toBe(true)
    await w.get('input[data-pin]').setValue('111111')
    await w.get('[data-registro-numero] form').trigger('submit')
    await flushPromises()
    expect(t(w.get('[data-erro-registro]').text())).toBe(recusa)
    expect(w.find('[data-registro-numero]').exists()).toBe(true)
    expect(w.find('[data-registrado]').exists()).toBe(false)
  })

  it('sinalizado ou banido: o aviso com o caminho do WhatsApp Manager', async () => {
    apiFalsa({ 'GET /integracoes/whatsapp/numero': () => ({ situacao: 'problema', status: 'BANNED', codigo_confirmado: null }) })
    const w = await montar(PainelWhatsapp, { dados: dados() })
    const aviso = w.get('[data-aviso-numero]')
    expect(t(aviso.text())).toContain('A Meta marcou como "Banido"')
    expect(t(aviso.text())).toContain('as pesquisas não saem por este número')
    expect(aviso.get('a').attributes('href')).toBe('https://business.facebook.com/wa/manage/phone-numbers/')
    expect(w.find('[data-registro-numero]').exists()).toBe(false)
  })

  it('a Meta não respondeu: diz e deixa tentar de novo', async () => {
    let falhar = true
    apiFalsa({
      'GET /integracoes/whatsapp/numero': () =>
        falhar
          ? new Response(JSON.stringify({ erro: { codigo: 'falha_meta', mensagem: 'A Meta recusou o token do WhatsApp. Reconecte o WhatsApp em Integrações.' } }), { status: 409 })
          : pendente,
    })
    const w = await montar(PainelWhatsapp, { dados: dados() })
    expect(t(w.get('[data-situacao-numero]').text())).toContain('Não deu para conferir agora: A Meta recusou o token do WhatsApp.')
    falhar = false
    await w.get('[data-situacao-numero] button').trigger('click')
    await flushPromises()
    expect(w.find('[data-registro-numero]').exists()).toBe(true)
  })
})

describe('Guia de conexão', () => {
  it('avisa que o número fica Pendente e que o Toqqi registra depois de conectar', async () => {
    apiFalsa({})
    const w = await montar(GuiaWhatsapp, { dados: dados({ conectado: false }) })
    expect(t(w.get('[data-nota-registro]').text())).toBe(
      'O número vai aparecer como Pendente no WhatsApp Manager até ser registrado. Não precisa fazer nada lá: depois de conectar aqui, o Toqqi registra para você, com um PIN de 6 números que você digita ou gera na hora.',
    )
  })
})

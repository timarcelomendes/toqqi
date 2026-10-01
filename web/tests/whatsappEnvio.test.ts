import { afterEach, describe, expect, it, vi } from 'vitest'
import { avisos } from '@/composables/avisos'
import { AVISO_WHATSAPP, useWhatsapp } from '@/composables/whatsapp'

afterEach(() => {
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
  avisos.splice(0)
})

describe('abrir convite no WhatsApp', () => {
  it('abre a aba no clique, chama a API e leva para o wa.me, explicando que falta apertar Enviar', async () => {
    const aba = { closed: false, opener: {}, location: { href: '' }, close: vi.fn() }
    vi.spyOn(window, 'open').mockReturnValue(aba as unknown as Window)
    const fetch = vi.fn(async () => new Response(JSON.stringify({ url: 'https://wa.me/5511999999999?text=Oi', mensagem: 'Oi', link: 'x' }), { status: 201 }))
    vi.stubGlobal('fetch', fetch)

    const { abrir } = useWhatsapp()
    expect(await abrir({ id: 42, nome: 'Ana' })).toBe(true)
    expect(String((fetch.mock.calls[0] as unknown as [string])[0])).toContain('/contatos/42/whatsapp')
    expect(aba.location.href).toBe('https://wa.me/5511999999999?text=Oi')
    expect(aba.opener).toBeNull()
    expect(avisos.some((a) => a.mensagem === AVISO_WHATSAPP)).toBe(true)
  })

  it('se a API recusar (ex.: sem telefone), fecha a aba e mostra o motivo', async () => {
    const aba = { closed: false, opener: {}, location: { href: '' }, close: vi.fn() }
    vi.spyOn(window, 'open').mockReturnValue(aba as unknown as Window)
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => new Response(JSON.stringify({ erro: { codigo: 'sem_telefone', mensagem: 'Este contato não tem telefone.' } }), { status: 422 })),
    )
    const { abrir } = useWhatsapp()
    expect(await abrir({ id: 1, nome: 'Bia' })).toBe(false)
    expect(aba.close).toHaveBeenCalled()
    expect(avisos.some((a) => a.mensagem === 'Este contato não tem telefone.')).toBe(true)
  })
})

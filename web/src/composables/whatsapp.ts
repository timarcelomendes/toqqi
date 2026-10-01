import { ref } from 'vue'
import { ApiError, mensagemDoErro, whatsappApi, type Id } from '@/api'
import { avisar } from './avisos'

export const AVISO_WHATSAPP =
  'A mensagem abriu no WhatsApp. Ela só sai quando você apertar Enviar lá: o Toqqi não consegue confirmar a entrega por esse caminho.'

/**
 * Abre o convite no WhatsApp (POST /contatos/{id}/whatsapp).
 * A janela é aberta ANTES da chamada (no clique), senão o navegador bloqueia como pop-up.
 */
export function useWhatsapp() {
  const abrindo = ref<Id | null>(null)

  async function abrir(contato: { id: Id; nome: string }, formularioId?: Id): Promise<boolean> {
    if (abrindo.value !== null) return false
    abrindo.value = contato.id
    let janela: Window | null = null
    try {
      janela = window.open('', '_blank')
      if (janela) janela.opener = null
    } catch {
      janela = null
    }
    try {
      const r = await whatsappApi.criar(contato.id, formularioId)
      if (janela && !janela.closed) janela.location.href = r.url
      else {
        // Sem "noopener" nas opções: com ele, window.open sempre devolve null e não daria para saber se abriu.
        const nova = window.open(r.url, '_blank')
        if (!nova) {
          avisar.atencao('Seu navegador bloqueou a nova aba. Libere as janelas do Toqqi e tente de novo.')
          return false
        }
        nova.opener = null
      }
      avisar({ tipo: 'sucesso', titulo: `Convite para ${contato.nome} pronto`, mensagem: AVISO_WHATSAPP, duracao: 9000 })
      return true
    } catch (e) {
      janela?.close()
      avisar.erro(e instanceof ApiError ? e.mensagem : mensagemDoErro(e))
      return false
    } finally {
      abrindo.value = null
    }
  }

  return { abrindo, abrir }
}

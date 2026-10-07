// Feedback (docs/api-feedback.md): a janela "Enviar feedback" (uma só, montada no AppLayout e aberta pelo menu ou por
// qualquer tela) e os números do menu: as respostas novas da equipe para quem usa (GET /feedback/novidades) e, para a
// equipe Toqqi, os feedbacks que precisam de atenção (GET /plataforma/feedback/contagem). O menu relê a cada troca de
// página, no máximo a cada 60 s; as telas de feedback acertam o número na hora, pelo que acabaram de ler.
import { reactive, ref } from 'vue'
import { feedbackApi, plataformaFeedbackApi, type TipoFeedback } from '@/api'

export const INTERVALO_FEEDBACK_MS = 60_000

const janela = reactive<{ aberta: boolean; tipo: TipoFeedback | null }>({ aberta: false, tipo: null })
const novidades = ref(0)
const atencao = ref(0)
const lidos = { novidades: 0, atencao: 0 }
const lendo: { novidades: Promise<void> | null; atencao: Promise<void> | null } = { novidades: null, atencao: null }

function reler(qual: 'novidades' | 'atencao', buscar: () => Promise<number>, forcar: boolean): Promise<void> {
  const atual = lendo[qual]
  if (atual) return atual
  if (!forcar && lidos[qual] && Date.now() - lidos[qual] < INTERVALO_FEEDBACK_MS) return Promise.resolve()
  const p = buscar()
    .then((n) => {
      ;(qual === 'novidades' ? novidades : atencao).value = Math.max(0, n)
      lidos[qual] = Date.now()
    })
    .catch(() => {
      /* sem o número novo, fica o último */
    })
    .finally(() => {
      lendo[qual] = null
    })
  lendo[qual] = p
  return p
}

export function usarFeedback() {
  /** Abre a janela (com o tipo já escolhido, se vier). */
  function abrir(tipo: TipoFeedback | null = null) {
    janela.tipo = tipo
    janela.aberta = true
  }

  function atualizarNovidades(forcar = false): Promise<void> {
    return reler('novidades', () => feedbackApi.novidades().then((r) => r.novidades), forcar)
  }

  /** Só para a equipe Toqqi; para os outros, zera. */
  function atualizarAtencao(superadmin: boolean, forcar = false): Promise<void> {
    if (!superadmin) {
      atencao.value = 0
      return Promise.resolve()
    }
    return reler('atencao', () => plataformaFeedbackApi.contagem().then((r) => r.atencao), forcar)
  }

  function definirNovidades(n: number) {
    novidades.value = Math.max(0, n)
    lidos.novidades = Date.now()
  }

  function definirAtencao(n: number) {
    atencao.value = Math.max(0, n)
    lidos.atencao = Date.now()
  }

  return { janela, novidades, atencao, abrir, atualizarNovidades, atualizarAtencao, definirNovidades, definirAtencao }
}

/** Só para os testes. */
export function limparFeedback() {
  janela.aberta = false
  janela.tipo = null
  novidades.value = 0
  atencao.value = 0
  lidos.novidades = 0
  lidos.atencao = 0
  lendo.novidades = null
  lendo.atencao = null
}

// Modo exemplo do Início (etapa 5h, docs/api-etapa-5h.md §1): ligado pelo "Comece por aqui" (ou por ?exemplo=1 no
// endereço), mostra o painel com dados de exemplo e a faixa no topo. Não fica salvo: vale enquanto a pessoa está no
// Início (sair da tela ou recarregar volta ao normal). O estado é compartilhado entre o Início (a faixa, acima de tudo)
// e o painel (os dados).
import { readonly, ref } from 'vue'

const ativo = ref(false)

export function usarModoExemplo() {
  return {
    ativo: readonly(ativo),
    ligar: () => {
      ativo.value = true
    },
    desligar: () => {
      ativo.value = false
    },
  }
}

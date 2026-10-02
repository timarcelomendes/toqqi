<script setup lang="ts">
// Cartão "Privacidade" em Minha conta (docs/api-aceite-lgpd.md §3 e §5): quando a pessoa aceitou os documentos, os
// links e o botão "Retirar meu aceite" (diálogo de confirmação; ao confirmar, sai do Toqqi e vai para Entrar).
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ApiError, euApi, mensagemDoErro } from '@/api'
import { avisar } from '@/composables/avisos'
import { confirmar } from '@/composables/confirmacao'
import { useSessaoStore } from '@/stores/sessao'
import { formatarDataHora } from '@/utils/datas'
import Alerta from '@/components/ui/Alerta.vue'
import Botao from '@/components/ui/Botao.vue'
import {
  complementoRetirarAceite,
  temAceiteEmVigor,
  textoAceiteRegistrado,
  TEXTO_RETIRAR_ACEITE,
} from '@/modulos/geral/legal/aceite'
import SecaoCartao from './SecaoCartao.vue'

const sessao = useSessaoStore()
const router = useRouter()
const texto = computed(() => textoAceiteRegistrado(sessao.usuario?.aceite, (v) => formatarDataHora(v)))
const podeRetirar = computed(() => temAceiteEmVigor(sessao.usuario?.aceite))

const retirando = ref(false)
const erro = ref<string | null>(null)

const MENSAGEM_PADRAO = 'Aceite retirado. Para voltar a usar o Toqqi, entre de novo e aceite os termos.'

async function retirar() {
  if (retirando.value) return
  erro.value = null
  const ok = await confirmar({
    titulo: 'Retirar o aceite?',
    mensagem: TEXTO_RETIRAR_ACEITE,
    complemento: complementoRetirarAceite(sessao.admin, sessao.pode('assinatura.gerenciar')) ?? undefined,
    confirmar: 'Retirar e sair',
    cancelar: 'Cancelar',
    perigo: true,
  })
  if (!ok) return
  retirando.value = true
  try {
    const r = await euApi.revogarAceite()
    // A API já encerrou todas as sessões, inclusive esta: limpa a sessão local como o "Sair" (sem chamar /auth/sair,
    // que daria 401) e vai para Entrar com o aviso de sucesso.
    sessao.limpar(null)
    // Aviso global (Avisos.vue, no App): continua visível depois da troca de rota; um pouco mais longo que o padrão.
    avisar({ tipo: 'sucesso', mensagem: r?.mensagem || MENSAGEM_PADRAO, duracao: 8000 })
    await router.push({ name: 'entrar' })
  } catch (e) {
    if (e instanceof ApiError && e.status === 409) {
      // Não há aceite em vigor (ex.: retirado noutro aparelho): mostra a mensagem e busca a situação nova.
      erro.value = e.mensagem || 'Você não tem um aceite em vigor para retirar.'
      try {
        await sessao.recarregar()
        // Sem aceite em vigor, o Toqqi não pode ser usado: vai direto para a tela de aceite.
        if (sessao.usuario?.aceite?.pendente) await router.push({ name: 'aceite', query: { de: '/minha-conta' } })
      } catch {
        /* sem conexão: fica a mensagem */
      }
    } else {
      erro.value = mensagemDoErro(e)
    }
  } finally {
    retirando.value = false
  }
}
</script>

<template>
  <SecaoCartao titulo="Privacidade" descricao="Como o Toqqi trata os seus dados e os dos seus clientes.">
    <p class="text-sm leading-relaxed text-texto-suave" data-teste="aceite">{{ texto }}</p>
    <Alerta v-if="erro" tom="erro" class="mt-4" data-teste="erro-retirar">{{ erro }}</Alerta>
    <div v-if="podeRetirar" class="mt-4">
      <Botao variante="perigo-suave" :carregando="retirando" class="border border-erro/30" data-teste="retirar-aceite" @click="retirar">
        Retirar meu aceite
      </Botao>
    </div>
    <ul class="mt-4 flex flex-col gap-2 text-sm sm:flex-row sm:gap-6">
      <li><RouterLink to="/termos" target="_blank" class="link">Termos de uso</RouterLink></li>
      <li><RouterLink to="/privacidade" target="_blank" class="link">Política de privacidade</RouterLink></li>
    </ul>
    <p class="mt-4 text-sm text-texto-fraco">
      Dúvidas ou pedidos sobre os seus dados:
      <a class="link break-all" href="mailto:privacidade@toqqi.com">privacidade@toqqi.com</a>.
    </p>
  </SecaoCartao>
</template>

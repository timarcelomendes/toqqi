<script setup lang="ts">
// Aviso do topo de todas as telas logadas, a partir de `conta.cobranca.aviso` (etapa 5a): teste acabando, teste
// encerrado, fatura atrasada, envios pausados, assinatura cancelada, aguardando o pagamento. Quem cuida da assinatura
// (`assinatura.gerenciar`) vê "Escolher plano" ou "Pagar agora"; os outros leem "Fale com o administrador da conta.".
// Na própria tela de Assinatura o aviso não aparece (a página já mostra tudo, com os dados de agora). Os
// informativos podem ser fechados (o foco vai para o conteúdo): voltam na próxima sessão do navegador ou quando o aviso
// muda.
// Etapa 5f: conta encerrada com dia marcado para a exclusão (`cobranca.exclusao_em`): este aviso fica no lugar do de
// cobrança, em todas as telas (inclusive Assinatura) e sem fechar. O administrador vê "Baixar os dados" e "Escolher
// plano" (o botão da própria tela em que ele está some); os outros, "Fale com o administrador da conta.".
import { computed, ref } from 'vue'
import { useRoute } from 'vue-router'
import { AlertTriangle, CalendarX, Info, X, XCircle } from 'lucide-vue-next'
import { useSessaoStore } from '@/stores/sessao'
import Botao from '@/components/ui/Botao.vue'
import { FALE_COM_ADMIN, ROTULOS_ACAO_AVISO, chaveDoAviso, textoDoAviso } from '@/modulos/assinatura/logica'
import { ROTA_DADOS_CONTA, textoAvisoExclusao } from '@/modulos/configuracoes/dadosConta'

const CHAVE_FECHADOS = 'toqqi.avisos-fechados'

const sessao = useSessaoStore()
const rota = useRoute()

function lerFechados(): string[] {
  try {
    const v: unknown = JSON.parse(sessionStorage.getItem(CHAVE_FECHADOS) ?? '[]')
    return Array.isArray(v) ? v.filter((x): x is string => typeof x === 'string') : []
  } catch {
    return []
  }
}
const fechados = ref<string[]>(lerFechados())

const aviso = computed(() => sessao.conta?.cobranca?.aviso ?? null)
const texto = computed(() => textoDoAviso(aviso.value, sessao.conta?.cobranca))
const chave = computed(() => (aviso.value ? chaveDoAviso(aviso.value) : ''))
const visivel = computed(
  () => !!texto.value && rota.path !== '/assinatura' && !(texto.value.dispensavel && fechados.value.includes(chave.value)),
)
const podeGerenciar = computed(() => sessao.pode('assinatura.gerenciar'))

const exclusao = computed(() => textoAvisoExclusao(sessao.conta?.cobranca?.exclusao_em, sessao.admin))
const botaoBaixar = computed(() => !!exclusao.value?.admin && rota.path !== ROTA_DADOS_CONTA)
const botaoPlano = computed(() => !!exclusao.value?.admin && podeGerenciar.value && rota.path !== '/assinatura')

function fechar() {
  fechados.value = [...fechados.value.filter((c) => c !== chave.value), chave.value].slice(-20)
  try {
    sessionStorage.setItem(CHAVE_FECHADOS, JSON.stringify(fechados.value))
  } catch {
    /* sem armazenamento: fica fechado só nesta tela */
  }
  // O botão sumiu junto com o aviso: o foco não fica perdido no topo da página.
  document.getElementById('conteudo')?.focus()
}

const ICONES = { info: Info, atencao: AlertTriangle, erro: XCircle }
const FUNDOS = { info: 'border-info/25 bg-info-suave', atencao: 'border-atencao/25 bg-atencao-suave', erro: 'border-erro/25 bg-erro-suave' }
const CORES_ICONE = { info: 'text-info', atencao: 'text-atencao', erro: 'text-erro' }
</script>

<template>
  <section v-if="exclusao" class="border-b border-erro/25 bg-erro-suave" aria-label="Aviso sobre a exclusão da conta" data-aviso-exclusao>
    <div class="mx-auto flex w-full max-w-6xl flex-col gap-2.5 px-4 py-3 sm:flex-row sm:items-center sm:gap-4 sm:px-6 lg:px-10">
      <p class="flex min-w-0 flex-1 items-start gap-2.5 text-sm text-texto" role="status">
        <CalendarX class="mt-0.5 size-5 shrink-0 text-erro" aria-hidden="true" />
        <span class="min-w-0">{{ exclusao.texto }}</span>
      </p>
      <div v-if="botaoBaixar || botaoPlano" class="ml-[1.875rem] flex flex-wrap gap-2 sm:ml-0">
        <Botao v-if="botaoBaixar" variante="secundario" tamanho="sm" :para="ROTA_DADOS_CONTA" data-acao-exclusao="baixar">Baixar os dados</Botao>
        <Botao v-if="botaoPlano" variante="secundario" tamanho="sm" para="/assinatura" data-acao-exclusao="plano">Escolher plano</Botao>
      </div>
    </div>
  </section>
  <section v-else-if="visivel && texto" class="border-b" :class="FUNDOS[texto.tom]" aria-label="Aviso sobre a assinatura" data-aviso-cobranca :data-tipo="aviso?.tipo">
    <!-- O X fica sempre na mesma linha do texto; o botão de ação desce para baixo do texto só no celular. -->
    <div class="mx-auto flex w-full max-w-6xl items-start gap-2 px-4 py-3 sm:items-center sm:px-6 lg:px-10">
      <div class="flex min-w-0 flex-1 flex-col gap-2.5 sm:flex-row sm:items-center sm:gap-4">
        <p class="flex min-w-0 flex-1 items-start gap-2.5 text-sm text-texto" role="status">
          <component :is="ICONES[texto.tom]" class="mt-0.5 size-5 shrink-0" :class="CORES_ICONE[texto.tom]" aria-hidden="true" />
          <span class="min-w-0">
            {{ texto.texto }}
            <span v-if="!podeGerenciar" class="text-texto-suave">{{ FALE_COM_ADMIN }}</span>
          </span>
        </p>
        <Botao
          v-if="podeGerenciar"
          :variante="texto.acao === 'pagar' ? 'primario' : 'secundario'"
          tamanho="sm"
          para="/assinatura"
          class="ml-[1.875rem] self-start sm:ml-0 sm:self-auto"
          data-acao-aviso
        >
          {{ ROTULOS_ACAO_AVISO[texto.acao] }}
        </Botao>
      </div>
      <button
        v-if="texto.dispensavel"
        type="button"
        class="-my-1 flex size-8 shrink-0 items-center justify-center rounded-lg text-texto-suave hover:bg-superficie/70 hover:text-texto"
        aria-label="Fechar aviso"
        @click="fechar"
      >
        <X class="size-4" aria-hidden="true" />
      </button>
    </div>
  </section>
</template>

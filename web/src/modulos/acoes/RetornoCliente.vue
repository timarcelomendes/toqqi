<script setup lang="ts">
// Melhoria 4: retorno ao cliente ("você falou, nós fizemos"). Com o plano concluído e um contato com e-mail, quem trata
// a ação escreve (ou ajusta) uma mensagem curta e o Toqqi manda ao cliente, uma vez. Fechar o ciclo aumenta a resposta
// da próxima pesquisa e ajuda a reverter detratores.
import { computed, ref, watch } from 'vue'
import { MailCheck } from 'lucide-vue-next'
import { acoesApi, mensagemDoErro, type Acao } from '@/api'
import { avisar } from '@/composables/avisos'
import { useSessaoStore } from '@/stores/sessao'
import { formatarDataHora } from '@/utils/datas'
import AreaTexto from '@/components/ui/AreaTexto.vue'
import Botao from '@/components/ui/Botao.vue'

const props = defineProps<{ acao: Acao }>()
const emit = defineEmits<{ enviado: [Acao] }>()
const sessao = useSessaoStore()
const aberto = ref(false)
const texto = ref('')
const enviando = ref(false)
const erro = ref<string | null>(null)

/** O comentário do cliente em uma linha (até 120 letras), para a mensagem começar pelo que ele disse. */
const disse = computed(() => {
  const c = (props.acao.resposta?.comentario ?? '').replace(/\s+/g, ' ').trim()
  return c.length > 120 ? `${c.slice(0, 117)}…` : c
})
function rascunho(): string {
  const inicio = disse.value ? `Você nos contou: “${disse.value}”.` : 'Obrigado por responder a nossa pesquisa.'
  const feito = (props.acao.resolucao ?? '').trim()
  return `Olá, {nome}!\n\n${inicio}\n\n${feito ? `O que fizemos: ${feito}` : 'Queremos contar o que fizemos com a sua opinião.'}\n\nObrigado por nos ajudar a melhorar.`
}
watch(
  () => props.acao.id,
  () => {
    aberto.value = false
    erro.value = null
  },
)
function abrir() {
  texto.value = rascunho()
  erro.value = null
  aberto.value = true
}
async function enviar() {
  if (texto.value.trim().length < 10) {
    erro.value = 'Escreva o que foi feito (pelo menos uma frase).'
    return
  }
  enviando.value = true
  try {
    const a = await acoesApi.avisarCliente(props.acao.id, texto.value)
    aberto.value = false
    avisar.sucesso('Pronto: o cliente vai receber a mensagem por e-mail.')
    emit('enviado', a)
  } catch (e) {
    erro.value = mensagemDoErro(e)
  } finally {
    enviando.value = false
  }
}
const visivel = computed(() => props.acao.situacao === 'concluida' && !!props.acao.contato)
</script>

<template>
  <section v-if="visivel" class="flex flex-col gap-3 rounded-xl border border-borda p-4" aria-labelledby="t-retorno" data-retorno-cliente>
    <h3 id="t-retorno" class="flex items-center gap-2 text-sm font-bold text-texto">
      <MailCheck class="size-4 text-marca-texto" aria-hidden="true" /> Avisar o cliente
    </h3>
    <template v-if="acao.retorno_em">
      <p class="text-sm text-texto-suave">Avisado em {{ formatarDataHora(acao.retorno_em) }}.</p>
      <p class="whitespace-pre-line rounded-lg bg-superficie-2 p-3 text-sm text-texto">{{ acao.retorno_texto }}</p>
    </template>
    <template v-else-if="!aberto">
      <p class="text-sm text-texto-suave">Conte a {{ acao.contato!.nome }} o que foi feito com a opinião dele. Quem vê o problema resolvido responde mais à próxima pesquisa.</p>
      <Botao v-if="sessao.pode('acoes.tratar')" variante="secundario" class="self-start" data-abrir-retorno @click="abrir">Escrever a mensagem</Botao>
    </template>
    <template v-else>
      <AreaTexto v-model="texto" rotulo="Mensagem" :linhas="7" :maximo="1000" contador :erro="erro" dica="Vai por e-mail, com o visual dos e-mails da sua empresa. {nome} vira o primeiro nome do contato." />
      <div class="flex flex-wrap gap-2">
        <Botao :carregando="enviando" data-enviar-retorno @click="enviar">Enviar ao cliente</Botao>
        <Botao variante="fantasma" :desabilitado="enviando" @click="aberto = false">Cancelar</Botao>
      </div>
    </template>
  </section>
</template>

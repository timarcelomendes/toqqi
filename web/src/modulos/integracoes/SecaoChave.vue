<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { KeyRound, RefreshCw, Trash2 } from 'lucide-vue-next'
import { chaveIntegracaoApi, mensagemDoErro, type ChaveIntegracao } from '@/api'
import { avisar } from '@/composables/avisos'
import { confirmar } from '@/composables/confirmacao'
import { formatarDataHora } from '@/utils/datas'
import Alerta from '@/components/ui/Alerta.vue'
import Botao from '@/components/ui/Botao.vue'
import Carregando from '@/components/ui/Carregando.vue'
import Etiqueta from '@/components/ui/Etiqueta.vue'
import ModalSegredo from './ModalSegredo.vue'
import { prefixoMascarado } from './logica'

const emit = defineEmits<{ irPara: [aba: 'conectar'] }>()

const chave = ref<ChaveIntegracao | null>(null)
const carregando = ref(true)
const erro = ref<string | null>(null)
const ocupado = ref<'gerar' | 'revogar' | null>(null)
const nova = ref<string | null>(null)

async function carregar() {
  carregando.value = true
  erro.value = null
  try {
    chave.value = await chaveIntegracaoApi.obter()
  } catch (e) {
    erro.value = mensagemDoErro(e)
  } finally {
    carregando.value = false
  }
}

async function gerar() {
  if (chave.value?.existe) {
    const ok = await confirmar({
      titulo: 'Gerar uma nova chave?',
      mensagem:
        'A chave atual para de funcionar na hora. Tudo o que usa a chave antiga (seu sistema, Zapier, Make, n8n) deixa de enviar pesquisas até receber a nova.',
      confirmar: 'Gerar nova chave',
      perigo: true,
    })
    if (!ok) return
  }
  ocupado.value = 'gerar'
  try {
    const r = await chaveIntegracaoApi.gerar()
    chave.value = { existe: true, prefixo: r.prefixo, criada_em: r.criada_em, ultimo_uso: null }
    nova.value = r.chave
  } catch (e) {
    avisar.erro(mensagemDoErro(e))
  } finally {
    ocupado.value = null
  }
}

async function revogar() {
  const ok = await confirmar({
    titulo: 'Revogar a chave de integração?',
    mensagem: 'Ela para de funcionar na hora e os sistemas que usam essa chave deixam de enviar pesquisas. Você pode gerar outra depois.',
    confirmar: 'Revogar chave',
    perigo: true,
  })
  if (!ok) return
  ocupado.value = 'revogar'
  try {
    await chaveIntegracaoApi.revogar()
    chave.value = { existe: false, prefixo: null, criada_em: null, ultimo_uso: null }
    avisar.sucesso('Chave revogada. Ela não funciona mais.')
  } catch (e) {
    avisar.erro(mensagemDoErro(e))
  } finally {
    ocupado.value = null
  }
}

onMounted(carregar)
</script>

<template>
  <section class="cartao grid gap-6 p-5 sm:p-6 md:grid-cols-3" aria-labelledby="t-chave">
    <div>
      <div class="mb-3 flex size-10 items-center justify-center rounded-xl bg-marca-suave text-marca-texto"><KeyRound class="size-5" aria-hidden="true" /></div>
      <h2 id="t-chave" class="text-base font-bold text-texto">Chave de integração</h2>
      <p class="mt-1 text-sm text-texto-suave">
        É a "senha" que o sistema da sua empresa (ou o Zapier, Make, n8n) usa para pedir ao Toqqi que envie uma pesquisa. Trate como uma senha: não mande por e-mail nem em grupos.
      </p>
    </div>
    <div class="md:col-span-2">
      <Carregando v-if="carregando" :linhas="2" />
      <Alerta v-else-if="erro" tom="erro">
        {{ erro }} <button type="button" class="link ml-1" @click="carregar">Tentar de novo</button>
      </Alerta>
      <div v-else-if="chave" class="flex flex-col gap-5">
        <dl v-if="chave.existe" class="grid gap-4 rounded-xl border border-borda bg-superficie-2/50 p-4 sm:grid-cols-3">
          <div class="min-w-0">
            <dt class="text-xs font-semibold uppercase tracking-wide text-texto-fraco">Chave</dt>
            <dd class="mt-1 truncate font-mono text-sm text-texto">{{ prefixoMascarado(chave.prefixo) }}</dd>
          </div>
          <div>
            <dt class="text-xs font-semibold uppercase tracking-wide text-texto-fraco">Criada em</dt>
            <dd class="mt-1 text-sm text-texto">{{ formatarDataHora(chave.criada_em) }}</dd>
          </div>
          <div>
            <dt class="text-xs font-semibold uppercase tracking-wide text-texto-fraco">Último uso</dt>
            <dd class="mt-1 text-sm text-texto">{{ chave.ultimo_uso ? formatarDataHora(chave.ultimo_uso) : 'Ainda não foi usada' }}</dd>
          </div>
        </dl>
        <div v-else class="flex flex-col items-start gap-2">
          <Etiqueta tom="neutro" ponto>Nenhuma chave ativa</Etiqueta>
          <p class="text-sm text-texto-suave">Gere uma chave quando for ligar o sistema da sua empresa ao Toqqi. Ela aparece completa uma única vez.</p>
        </div>

        <div class="flex flex-wrap gap-2">
          <Botao :carregando="ocupado === 'gerar'" :desabilitado="ocupado !== null" :variante="chave.existe ? 'secundario' : 'primario'" @click="gerar">
            <RefreshCw v-if="chave.existe && ocupado !== 'gerar'" class="size-4" aria-hidden="true" />
            <KeyRound v-else-if="ocupado !== 'gerar'" class="size-4" aria-hidden="true" />
            {{ chave.existe ? 'Gerar nova chave' : 'Gerar chave' }}
          </Botao>
          <Botao v-if="chave.existe" variante="perigo-suave" :carregando="ocupado === 'revogar'" :desabilitado="ocupado !== null" @click="revogar">
            <Trash2 v-if="ocupado !== 'revogar'" class="size-4" aria-hidden="true" /> Revogar
          </Botao>
        </div>
        <p class="text-sm text-texto-fraco">
          Perdeu a chave? Não tem como ver de novo: gere uma nova e atualize onde ela é usada.
          <button type="button" class="link" @click="emit('irPara', 'conectar')">Ver como conectar seu sistema</button>
        </p>
      </div>
    </div>

    <ModalSegredo
      :segredo="nova"
      titulo="Sua chave de integração"
      descricao="Entregue esta chave para quem cuida do sistema da sua empresa."
      rotulo-campo="Chave"
      @fechado="nova = null"
    />
  </section>
</template>

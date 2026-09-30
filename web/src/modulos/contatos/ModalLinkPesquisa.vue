<script setup lang="ts">
// Gera um convite individual (sem e-mail) para mandar à mão, por WhatsApp ou onde quiser.
import { computed, reactive, ref, watch } from 'vue'
import { ExternalLink, MessageCircle } from 'lucide-vue-next'
import { contatosApi, formulariosApi, type Contato, type FormularioResumo, type Id, type LinkPesquisa } from '@/api'
import { useFormulario } from '@/composables/formulario'
import { useSessaoStore } from '@/stores/sessao'
import { telefoneWhatsapp } from '@/utils/formatos'
import { CAMPOS_CONTEXTO, ROTULOS_CONTEXTO, type Contexto } from '@/pesquisa/tipos'
import Alerta from '@/components/ui/Alerta.vue'
import Botao from '@/components/ui/Botao.vue'
import BotaoCopiar from '@/components/ui/BotaoCopiar.vue'
import Campo from '@/components/ui/Campo.vue'
import Modal from '@/components/ui/Modal.vue'
import Selecao from '@/components/ui/Selecao.vue'

const props = defineProps<{ contato: Contato | null }>()
const aberto = defineModel<boolean>('aberto', { default: false })

const sessao = useSessaoStore()
const { enviando, erroGeral, executar, limpar } = useFormulario()
const formularios = ref<FormularioResumo[]>([])
const formularioId = ref<Id | ''>('')
const assunto = ref('')
const contexto = reactive<Contexto>({})
const comContexto = ref(false)
const resultado = ref<LinkPesquisa | null>(null)

const opcoesFormularios = computed(() =>
  formularios.value
    .filter((f) => f.ativo)
    .map((f) => ({ valor: f.id, rotulo: f.nome + (f.padrao_nps ? ' (padrão NPS)' : f.padrao_csat ? ' (padrão CSAT)' : '') })),
)

watch(aberto, async (v) => {
  if (!v) return
  limpar()
  resultado.value = null
  assunto.value = ''
  comContexto.value = false
  for (const c of CAMPOS_CONTEXTO) delete contexto[c]
  formularioId.value = ''
  if (!formularios.value.length && sessao.pode('formularios.ver')) {
    try {
      formularios.value = await formulariosApi.listar()
    } catch {
      /* sem a lista, usa o formulário padrão da conta */
    }
  }
})

const whatsapp = computed(() => {
  const numero = telefoneWhatsapp(props.contato?.telefone)
  if (!numero || !resultado.value) return null
  const nome = props.contato?.nome.split(' ')[0] ?? ''
  const msg = `Olá${nome ? `, ${nome}` : ''}! Pode responder nossa pesquisa rapidinho? Leva menos de um minuto: ${resultado.value.link}`
  return `https://wa.me/${numero}?text=${encodeURIComponent(msg)}`
})

async function gerar() {
  if (!props.contato) return
  const ctx: Contexto = {}
  for (const c of CAMPOS_CONTEXTO) {
    const v = contexto[c]?.trim()
    if (v) ctx[c] = v
  }
  const r = await executar(() =>
    contatosApi.linkPesquisa(props.contato!.id, {
      ...(formularioId.value !== '' ? { formulario_id: formularioId.value } : {}),
      ...(Object.keys(ctx).length ? { contexto: ctx } : {}),
      ...(assunto.value.trim() ? { assunto: assunto.value.trim() } : {}),
    }),
  )
  if (r) resultado.value = r
}
</script>

<template>
  <Modal v-model:aberto="aberto" titulo="Gerar link de pesquisa" :descricao="contato ? `Um link só para ${contato.nome} responder.` : undefined" :bloqueado="enviando">
    <div v-if="resultado" class="flex flex-col gap-4">
      <Alerta tom="sucesso" titulo="Link pronto!">Mande para a pessoa pelo canal que preferir. Ele vale para uma resposta.</Alerta>
      <div class="flex flex-col gap-1.5">
        <label for="link-gerado" class="text-sm font-semibold text-texto">Link da pesquisa</label>
        <input
          id="link-gerado"
          :value="resultado.link"
          readonly
          class="h-11 w-full rounded-xl border border-borda-forte bg-superficie-2 px-3.5 text-sm text-texto"
          @focus="($event.target as HTMLInputElement).select()"
        />
      </div>
      <div class="flex flex-wrap gap-2">
        <BotaoCopiar :texto="resultado.link" rotulo="Copiar link" variante="primario" />
        <a
          v-if="whatsapp"
          :href="whatsapp"
          target="_blank"
          rel="noopener"
          class="inline-flex h-10 items-center gap-2 rounded-xl border border-borda-forte bg-superficie px-4 text-sm font-semibold text-texto hover:bg-superficie-2"
        >
          <MessageCircle class="size-4 text-[#128C7E]" aria-hidden="true" /> Abrir no WhatsApp
        </a>
        <a :href="resultado.link" target="_blank" rel="noopener" class="inline-flex h-10 items-center gap-2 rounded-xl px-4 text-sm font-semibold text-texto-suave hover:bg-superficie-2">
          <ExternalLink class="size-4" aria-hidden="true" /> Ver a pesquisa
        </a>
      </div>
      <p v-if="!whatsapp" class="text-sm text-texto-fraco">Cadastre um telefone no contato para abrir direto no WhatsApp.</p>
    </div>

    <form v-else id="form-link" class="flex flex-col gap-4" novalidate @submit.prevent="gerar">
      <Alerta v-if="erroGeral" tom="erro">{{ erroGeral }}</Alerta>
      <Selecao
        v-if="opcoesFormularios.length"
        v-model="formularioId"
        rotulo="Formulário"
        :opcoes="opcoesFormularios"
        vazio="O padrão da conta"
        dica="Se não escolher, vai o formulário padrão de NPS."
      />
      <Campo v-model="assunto" rotulo="Assunto" opcional placeholder="o nosso atendimento" dica="Aparece no lugar de {assunto} nas perguntas." maxlength="120" />
      <button v-if="!comContexto" type="button" class="link w-fit text-sm" @click="comContexto = true">Adicionar informações do pedido ou da entrega</button>
      <fieldset v-else class="rounded-xl border border-borda p-4">
        <legend class="px-1 text-sm font-semibold text-texto">Informações do pedido ou da entrega <span class="font-normal text-texto-fraco">(opcional)</span></legend>
        <p class="mb-3 text-sm text-texto-fraco">Ficam guardadas junto da resposta, para você saber de qual entrega a pessoa está falando.</p>
        <div class="grid gap-3 sm:grid-cols-2">
          <Campo v-for="c in CAMPOS_CONTEXTO" :key="c" v-model="contexto[c]" :rotulo="ROTULOS_CONTEXTO[c]" maxlength="120" autocomplete="off" />
        </div>
      </fieldset>
    </form>

    <template #rodape>
      <template v-if="resultado">
        <Botao variante="secundario" @click="resultado = null">Gerar outro</Botao>
        <Botao @click="aberto = false">Concluir</Botao>
      </template>
      <template v-else>
        <Botao variante="secundario" :desabilitado="enviando" @click="aberto = false">Cancelar</Botao>
        <Botao tipo="submit" form="form-link" :carregando="enviando">Gerar link</Botao>
      </template>
    </template>
  </Modal>
</template>

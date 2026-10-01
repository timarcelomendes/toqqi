<script setup lang="ts">
// Logo da empresa: prévia em fundo claro e escuro, enviar/trocar (PUT /conta/logo) e remover (DELETE /conta/logo).
// Vale na hora (não depende do "Salvar alterações" dos dados): aparece nas pesquisas e nos e-mails
// quando o formulário não tem logo próprio.
import { ref } from 'vue'
import { ImageIcon, ImagePlus, Trash2 } from 'lucide-vue-next'
import { ApiError, empresaApi, mensagemDoErro } from '@/api'
import { avisar } from '@/composables/avisos'
import { confirmar } from '@/composables/confirmacao'
import { ACEITA_LOGO, conferirLogo } from '@/utils/imagens'
import Botao from '@/components/ui/Botao.vue'

const props = defineProps<{ logoUrl: string | null; nome: string }>()
// `atualizadoEm`: a data que o servidor gravou (o envio devolve; na remoção, 204, vale a hora local).
const emit = defineEmits<{ trocado: [url: string | null, atualizadoEm: string | null] }>()

const enviando = ref(false)
const removendo = ref(false)
const erro = ref<string | null>(null)
const entrada = ref<HTMLInputElement | null>(null)

async function escolher(f: File | undefined) {
  erro.value = null
  if (!f) return
  const problema = await conferirLogo(f)
  if (problema) {
    erro.value = problema
    return
  }
  enviando.value = true
  const tinha = !!props.logoUrl
  try {
    const r = await empresaApi.enviarLogo(f)
    emit('trocado', r.logo_url, r.atualizado_em)
    avisar.sucesso(tinha ? 'Logo trocado.' : 'Logo enviado.')
  } catch (e) {
    erro.value = e instanceof ApiError ? (e.campo('arquivo') ?? e.mensagem) : mensagemDoErro(e)
  } finally {
    enviando.value = false
  }
}

async function remover() {
  const ok = await confirmar({
    titulo: 'Remover o logo da empresa?',
    mensagem:
      'As pesquisas e os e-mails ficam sem o logo da empresa (os formulários que têm logo próprio continuam com o deles). Você pode enviar outro quando quiser.',
    confirmar: 'Remover logo',
    perigo: true,
  })
  if (!ok) return
  removendo.value = true
  erro.value = null
  try {
    await empresaApi.removerLogo()
    emit('trocado', null, new Date().toISOString())
    avisar.sucesso('Logo removido.')
  } catch (e) {
    avisar.erro(mensagemDoErro(e))
  } finally {
    removendo.value = false
  }
}
</script>

<template>
  <div class="flex flex-col gap-4">
    <!-- Prévia nos dois fundos: o logo precisa ficar legível nos dois (e-mails e pesquisas podem ser claros ou escuros). -->
    <div v-if="logoUrl" class="grid grid-cols-1 gap-3 sm:grid-cols-2">
      <figure class="flex flex-col gap-1.5">
        <div class="flex h-28 items-center justify-center rounded-xl border border-slate-200 bg-white p-4">
          <img :src="logoUrl" :alt="`Logo de ${nome} em fundo claro`" class="max-h-16 max-w-full object-contain" />
        </div>
        <figcaption class="text-xs text-texto-fraco">Em fundo claro</figcaption>
      </figure>
      <figure class="flex flex-col gap-1.5">
        <div class="flex h-28 items-center justify-center rounded-xl border border-slate-700 bg-slate-900 p-4">
          <img :src="logoUrl" :alt="`Logo de ${nome} em fundo escuro`" class="max-h-16 max-w-full object-contain" />
        </div>
        <figcaption class="text-xs text-texto-fraco">Em fundo escuro</figcaption>
      </figure>
    </div>
    <div v-else class="flex min-h-28 flex-col items-center justify-center gap-1.5 rounded-xl border border-dashed border-borda-forte p-4 text-center">
      <ImageIcon class="size-6 text-texto-fraco" aria-hidden="true" />
      <p class="text-sm font-semibold text-texto">Sua empresa ainda não tem logo.</p>
      <p class="text-sm text-texto-suave">Depois de enviar, você vê aqui como ele fica em fundo claro e escuro.</p>
    </div>

    <div class="flex flex-wrap gap-2">
      <Botao variante="secundario" :carregando="enviando" :desabilitado="removendo" @click="entrada?.click()">
        <ImagePlus v-if="!enviando" class="size-4" aria-hidden="true" /> {{ logoUrl ? 'Trocar logo' : 'Enviar logo' }}
      </Botao>
      <Botao v-if="logoUrl" variante="perigo-suave" :carregando="removendo" :desabilitado="enviando" @click="remover">
        <Trash2 v-if="!removendo" class="size-4" aria-hidden="true" /> Remover
      </Botao>
      <input
        ref="entrada"
        type="file"
        :accept="ACEITA_LOGO"
        class="sr-only"
        tabindex="-1"
        aria-hidden="true"
        @change="escolher(($event.target as HTMLInputElement).files?.[0]); ($event.target as HTMLInputElement).value = ''"
      />
    </div>
    <p class="text-sm text-texto-fraco">PNG ou JPG de até 300 KB. Fundo transparente fica melhor; nos e-mails, o logo aparece com até 48 px de altura.</p>
    <p v-if="erro" class="text-sm font-medium text-erro" role="alert">{{ erro }}</p>
  </div>
</template>

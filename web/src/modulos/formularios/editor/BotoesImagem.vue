<script setup lang="ts">
// Imagem no conteúdo (docs/api-etapa-5l.md §4.6 e §5.3): "Enviar imagem" (PNG ou JPG de até 1 MB, guardada para este
// formulário) ou, para quem cuida do banco de imagens, "Escolher do banco". Só imagens da plataforma entram no HTML.
import { computed, ref } from 'vue'
import { ImagePlus, Images } from 'lucide-vue-next'
import { ApiError, formulariosApi, mensagemDoErro, type Id, type ImagemBanco } from '@/api'
import { useSessaoStore } from '@/stores/sessao'
import { ACEITA_LOGO, conferirImagemBanco } from '@/utils/imagens'
import Botao from '@/components/ui/Botao.vue'
import BancoImagens from '@/modulos/configuracoes/BancoImagens.vue'

const props = defineProps<{ formularioId: Id; desabilitado?: boolean }>()
const emit = defineEmits<{ imagem: [img: { src: string; alt: string; width?: number | null; height?: number | null }] }>()
const sessao = useSessaoStore()
const podeBanco = computed(() => sessao.pode('configuracoes.gerenciar'))
const entrada = ref<HTMLInputElement | null>(null)
const enviando = ref(false)
const erro = ref<string | null>(null)
const bancoAberto = ref(false)

async function enviar(f: File | undefined) {
  erro.value = null
  if (!f || enviando.value) return
  const problema = await conferirImagemBanco(f)
  if (problema) {
    erro.value = problema
    return
  }
  enviando.value = true
  try {
    const r = await formulariosApi.enviarImagem(props.formularioId, f)
    emit('imagem', { src: r.url, alt: '', width: r.largura ?? null, height: r.altura ?? null })
  } catch (e) {
    erro.value = e instanceof ApiError ? (e.campo('arquivo') ?? e.mensagem) : mensagemDoErro(e)
  } finally {
    enviando.value = false
  }
}

function doBanco(i: ImagemBanco) {
  emit('imagem', { src: i.url, alt: '', width: i.largura ?? null, height: i.altura ?? null })
}

/** Abre a escolha de arquivo (a barra do editor visual também chama). */
function escolherArquivo() {
  entrada.value?.click()
}
defineExpose({ escolherArquivo })
</script>

<template>
  <div class="flex flex-col gap-1.5" data-botoes-imagem>
    <div class="flex flex-wrap gap-2">
      <Botao variante="secundario" tamanho="sm" :carregando="enviando" :desabilitado="desabilitado" data-enviar-imagem-conteudo @click="escolherArquivo">
        <ImagePlus v-if="!enviando" class="size-4" aria-hidden="true" /> Enviar imagem
      </Botao>
      <Botao v-if="podeBanco" variante="secundario" tamanho="sm" :desabilitado="desabilitado" data-escolher-do-banco @click="bancoAberto = true">
        <Images class="size-4" aria-hidden="true" /> Escolher do banco
      </Botao>
      <input
        ref="entrada"
        type="file"
        :accept="ACEITA_LOGO"
        class="sr-only"
        tabindex="-1"
        aria-hidden="true"
        @change="enviar(($event.target as HTMLInputElement).files?.[0]); ($event.target as HTMLInputElement).value = ''"
      />
    </div>
    <p v-if="erro" class="text-sm font-medium text-erro" role="alert">{{ erro }}</p>
    <BancoImagens v-if="podeBanco" v-model:aberto="bancoAberto" descricao="Escolha uma imagem para o conteúdo ou envie uma nova." @escolher="doBanco" />
  </div>
</template>

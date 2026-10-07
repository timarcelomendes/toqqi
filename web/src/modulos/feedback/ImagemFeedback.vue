<script setup lang="ts">
// Uma imagem privada do feedback: busca como blob (com o token; não há URL pública), mostra a miniatura e abre maior
// numa janela por cima. Não carregou: "Tentar de novo".
import { onBeforeUnmount, onMounted, ref } from 'vue'
import { ImageOff, RefreshCw } from 'lucide-vue-next'
import Modal from '@/components/ui/Modal.vue'

const props = defineProps<{ carregar: (sinal: AbortSignal) => Promise<Blob>; nome: string | null }>()

const url = ref<string | null>(null)
const falhou = ref(false)
const aberta = ref(false)
let controlador: AbortController | null = null

async function buscar() {
  controlador?.abort()
  controlador = new AbortController()
  falhou.value = false
  try {
    const blob = await props.carregar(controlador.signal)
    if (url.value) URL.revokeObjectURL(url.value)
    url.value = URL.createObjectURL(blob)
  } catch (e) {
    if (e instanceof DOMException && e.name === 'AbortError') return
    falhou.value = true
  }
}

onMounted(buscar)
onBeforeUnmount(() => {
  controlador?.abort()
  if (url.value) URL.revokeObjectURL(url.value)
})

const descricao = () => (props.nome ? `Imagem ${props.nome}` : 'Imagem anexada')
</script>

<template>
  <div class="relative aspect-[4/3] overflow-hidden rounded-xl border border-borda bg-superficie" data-imagem-feedback>
    <button
      v-if="url"
      type="button"
      class="block size-full focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-foco"
      :aria-label="`Ver maior: ${descricao()}`"
      @click="aberta = true"
    >
      <img :src="url" :alt="descricao()" class="size-full object-cover" />
    </button>
    <button
      v-else-if="falhou"
      type="button"
      class="flex size-full flex-col items-center justify-center gap-1 text-xs font-semibold text-texto-suave hover:bg-superficie-2"
      data-tentar-imagem
      @click="buscar"
    >
      <ImageOff class="size-5" aria-hidden="true" />
      <span>A imagem não carregou</span>
      <span class="inline-flex items-center gap-1 text-marca-texto"><RefreshCw class="size-3.5" aria-hidden="true" /> Tentar de novo</span>
    </button>
    <div v-else class="size-full animate-pulse bg-superficie-2" role="status"><span class="sr-only">Carregando a imagem…</span></div>

    <Modal v-model:aberto="aberta" :titulo="nome || 'Imagem'" tamanho="lg" elevado>
      <img v-if="url" :src="url" :alt="descricao()" class="mx-auto max-h-[75dvh] w-auto max-w-full rounded-lg" />
    </Modal>
  </div>
</template>

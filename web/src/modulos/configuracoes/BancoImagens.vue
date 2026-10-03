<script setup lang="ts">
// Banco de imagens da conta (docs/api-etapa-5e.md §3 e §6.2), numa janela: grade de miniaturas (nome, dimensões,
// "Em uso"), "Enviar imagem" (PNG ou JPG de até 1 MB), escolher a imagem de topo dos e-mails e excluir (com
// confirmação; a imagem em uso não sai, e a mensagem da API explica). As miniaturas são botões; ao fechar, o foco volta
// a quem abriu a janela (o Modal cuida disso).
import { computed, nextTick, onBeforeUnmount, ref, useId, watch } from 'vue'
import { Check, ImageIcon, ImagePlus, Trash2 } from 'lucide-vue-next'
import { ApiError, imagensApi, mensagemDoErro, type Id, type ImagemBanco } from '@/api'
import { confirmar } from '@/composables/confirmacao'
import { ACEITA_LOGO, conferirImagemBanco } from '@/utils/imagens'
import Alerta from '@/components/ui/Alerta.vue'
import Botao from '@/components/ui/Botao.vue'
import Carregando from '@/components/ui/Carregando.vue'
import EstadoVazio from '@/components/ui/EstadoVazio.vue'
import Etiqueta from '@/components/ui/Etiqueta.vue'
import Modal from '@/components/ui/Modal.vue'
import {
  DICA_TAMANHO_TOPO,
  LIMITE_BANCO_PADRAO,
  bancoCheio,
  detalhesImagem,
  mensagemLimiteBanco,
  mesmaImagem,
  nomeImagem,
  textoQuantidadeImagens,
} from './bancoImagens'

const props = defineProps<{ escolhidaId?: Id | null }>()
const aberto = defineModel<boolean>('aberto', { default: false })
const emit = defineEmits<{ escolher: [imagem: ImagemBanco]; excluida: [id: Id] }>()

const uid = useId()
const itens = ref<ImagemBanco[]>([])
const limite = ref(LIMITE_BANCO_PADRAO)
const carregou = ref(false)
const carregando = ref(false)
const erroCarga = ref<string | null>(null)
/** Erro de uma ação (enviar ou excluir): fica na janela, perto da grade. */
const erro = ref<string | null>(null)
/** O que acabou de acontecer, para quem usa leitor de tela (e à vista, em verde). */
const anuncio = ref('')
const enviando = ref(false)
const excluindo = ref<Id | null>(null)
const entrada = ref<HTMLInputElement | null>(null)
const corpo = ref<HTMLElement | null>(null)
let controle: AbortController | null = null

const cheio = computed(() => carregou.value && bancoCheio(itens.value.length, limite.value))
const escolhida = (i: ImagemBanco) => mesmaImagem(i, props.escolhidaId)

async function carregar() {
  controle?.abort()
  controle = new AbortController()
  carregando.value = true
  erroCarga.value = null
  try {
    const r = await imagensApi.listar(controle.signal)
    itens.value = r.itens ?? []
    limite.value = r.limite || LIMITE_BANCO_PADRAO
    carregou.value = true
  } catch (e) {
    if (e instanceof DOMException && e.name === 'AbortError') return
    erroCarga.value = mensagemDoErro(e)
  } finally {
    carregando.value = false
  }
}

// Busca a cada abertura: "Em uso" segue a configuração salva, que pode ter mudado.
watch(
  aberto,
  (v) => {
    if (v) {
      erro.value = null
      anuncio.value = ''
      void carregar()
    } else controle?.abort()
  },
  { immediate: true },
)
onBeforeUnmount(() => controle?.abort())

/** No limite, o botão fica inativo (mas focável, para o leitor de tela ler o porquê, que está logo abaixo dele). */
function abrirArquivos() {
  if (enviando.value || cheio.value) return
  entrada.value?.click()
}

async function enviar(f: File | undefined) {
  erro.value = null
  anuncio.value = ''
  if (!f || enviando.value) return
  const problema = await conferirImagemBanco(f)
  if (problema) {
    erro.value = problema
    return
  }
  enviando.value = true
  try {
    const nova = await imagensApi.enviar(f)
    itens.value = [nova, ...itens.value.filter((i) => !mesmaImagem(i, nova.id))]
    anuncio.value = `Imagem enviada: ${nomeImagem(nova)}. Para usar, escolha a imagem na lista.`
  } catch (e) {
    erro.value = e instanceof ApiError ? (e.campo('arquivo') ?? e.mensagem) : mensagemDoErro(e)
    // Outra pessoa encheu o banco enquanto a janela estava aberta: a contagem acompanha.
    if (e instanceof ApiError && e.codigo === 'limite_imagens') void carregar()
  } finally {
    enviando.value = false
  }
}

function escolher(i: ImagemBanco) {
  emit('escolher', i)
  aberto.value = false
}

/** Depois de excluir, o foco vai para a miniatura que ficou no lugar (ou a anterior); sem nenhuma, para "Enviar imagem". */
async function focarDepoisDeExcluir(posicao: number) {
  await nextTick()
  const botoes = corpo.value?.querySelectorAll<HTMLElement>('[data-escolher]') ?? []
  const alvo = botoes[Math.min(posicao, botoes.length - 1)] ?? corpo.value?.querySelector<HTMLElement>('[data-enviar-imagem]')
  alvo?.focus()
}

async function excluir(i: ImagemBanco) {
  erro.value = null
  anuncio.value = ''
  const nome = nomeImagem(i)
  const ok = await confirmar({
    titulo: 'Excluir esta imagem?',
    mensagem: `“${nome}” sai do banco de imagens. Não dá para desfazer.`,
    confirmar: 'Excluir imagem',
    perigo: true,
  })
  if (!ok) return
  const posicao = itens.value.findIndex((x) => mesmaImagem(x, i.id))
  excluindo.value = i.id
  try {
    await imagensApi.excluir(i.id)
    itens.value = itens.value.filter((x) => !mesmaImagem(x, i.id))
    anuncio.value = `Imagem excluída: ${nome}.`
    emit('excluida', i.id)
    void focarDepoisDeExcluir(posicao)
  } catch (e) {
    if (e instanceof ApiError && e.status === 404) {
      // Já não existe (outra pessoa excluiu): some da lista também.
      itens.value = itens.value.filter((x) => !mesmaImagem(x, i.id))
      anuncio.value = `A imagem ${nome} já tinha sido excluída.`
      emit('excluida', i.id)
      void focarDepoisDeExcluir(posicao)
    } else {
      // Em uso (409 imagem_em_uso) e os outros erros: a mensagem da API.
      erro.value = mensagemDoErro(e)
    }
  } finally {
    excluindo.value = null
  }
}
</script>

<template>
  <Modal v-model:aberto="aberto" titulo="Banco de imagens" descricao="Escolha a imagem do topo dos e-mails ou envie uma nova." tamanho="lg">
    <div ref="corpo" class="flex flex-col gap-4" data-banco-imagens>
      <div class="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div class="flex flex-col gap-1">
          <Botao
            variante="secundario"
            focavel
            :carregando="enviando"
            :desabilitado="cheio"
            :aria-describedby="`${uid}-dica${cheio ? ` ${uid}-cheio` : ''}`"
            data-autofoco
            data-enviar-imagem
            @click="abrirArquivos"
          >
            <ImagePlus v-if="!enviando" class="size-4" aria-hidden="true" /> Enviar imagem
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
        <p v-if="carregou" class="text-sm font-semibold text-texto-suave tabular-nums" data-quantidade>{{ textoQuantidadeImagens(itens.length, limite) }}</p>
      </div>
      <p :id="`${uid}-dica`" class="text-sm text-texto-fraco">PNG ou JPG de até 1 MB. {{ DICA_TAMANHO_TOPO }}</p>
      <p v-if="cheio" :id="`${uid}-cheio`" class="text-sm font-medium text-atencao" data-banco-cheio>{{ mensagemLimiteBanco(limite) }}</p>

      <Alerta v-if="erro" tom="erro" data-erro-banco>{{ erro }}</Alerta>
      <!-- Sempre presente (vazia quando não há o que dizer): quem vê percebe pela grade; quem ouve, por aqui -->
      <p class="sr-only" role="status" aria-live="polite" data-anuncio-banco>{{ anuncio }}</p>

      <Carregando v-if="carregando && !carregou" :linhas="3" rotulo="Carregando as imagens" />
      <Alerta v-else-if="erroCarga && !carregou" tom="erro">
        {{ erroCarga }} <button type="button" class="link ml-1" @click="carregar">Tentar de novo</button>
      </Alerta>
      <EstadoVazio
        v-else-if="carregou && !itens.length"
        :icone="ImageIcon"
        titulo="Nenhuma imagem ainda"
        descricao="Envie a primeira: um banner com a cara da sua empresa, por exemplo."
      />
      <ul v-else-if="itens.length" class="grid grid-cols-1 gap-3 min-[420px]:grid-cols-2 sm:grid-cols-3" aria-label="Imagens do banco" data-grade-imagens>
        <li
          v-for="i in itens"
          :key="String(i.id)"
          class="flex min-w-0 flex-col overflow-hidden rounded-xl border bg-superficie"
          :class="escolhida(i) ? 'border-marca ring-2 ring-marca/30' : 'border-borda'"
          :data-imagem="String(i.id)"
        >
          <button
            type="button"
            class="relative block border-b border-slate-200 bg-white focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-foco"
            :aria-label="`Escolher ${nomeImagem(i)}`"
            :aria-describedby="`${uid}-${i.id}-detalhes`"
            data-escolher
            @click="escolher(i)"
          >
            <img :src="i.url" alt="" class="aspect-[3/1] w-full object-contain" loading="lazy" />
            <span v-if="escolhida(i)" class="absolute right-1.5 top-1.5 inline-flex items-center gap-1 rounded-full bg-marca-forte px-2 py-0.5 text-xs font-semibold text-white">
              <Check class="size-3.5" aria-hidden="true" /> Escolhida
            </span>
          </button>
          <div class="flex items-start gap-2 p-2.5">
            <div class="min-w-0 flex-1">
              <p class="truncate text-sm font-semibold text-texto" :title="nomeImagem(i)">{{ nomeImagem(i) }}</p>
              <p :id="`${uid}-${i.id}-detalhes`" class="flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-texto-fraco">
                <span>{{ detalhesImagem(i) || 'Tamanho desconhecido' }}</span>
                <Etiqueta v-if="i.em_uso" tom="sucesso" data-em-uso>Em uso</Etiqueta>
                <span v-if="escolhida(i)" class="sr-only">Escolhida agora.</span>
              </p>
            </div>
            <Botao
              variante="perigo-suave"
              tamanho="sm"
              :somente-icone="`Excluir ${nomeImagem(i)}`"
              :carregando="excluindo !== null && String(excluindo) === String(i.id)"
              :desabilitado="excluindo !== null"
              data-excluir
              @click="excluir(i)"
            >
              <Trash2 v-if="excluindo === null || String(excluindo) !== String(i.id)" class="size-4" aria-hidden="true" />
            </Botao>
          </div>
        </li>
      </ul>
    </div>
    <template #rodape>
      <Botao variante="secundario" @click="aberto = false">Fechar</Botao>
    </template>
  </Modal>
</template>

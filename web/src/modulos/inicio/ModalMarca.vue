<script setup lang="ts">
// Modal "Sua marca nas pesquisas" (etapa 5h, docs/api-etapa-5h.md §1): o logo (o mesmo envio de Configurações › Empresa,
// PUT /conta/logo, que vale na hora) e a cor (paleta com 8 sugestões + campo #RRGGBB, com a prévia da pesquisa) →
// PUT /conta/marca. A cor vale para os e-mails e para os formulários que ainda estão na cor dos modelos.
import { computed, ref, watch } from 'vue'
import { Check } from 'lucide-vue-next'
import { ApiError, marcaApi, mensagemDoErro } from '@/api'
import { avisar } from '@/composables/avisos'
import Botao from '@/components/ui/Botao.vue'
import Campo from '@/components/ui/Campo.vue'
import Modal from '@/components/ui/Modal.vue'
import LogoEmpresa from '@/modulos/configuracoes/LogoEmpresa.vue'
import { COR_DOS_MODELOS, CORES_MARCA, MENSAGEM_COR, corDoTexto, normalizarCor, textoCorSalva } from './logica'

const props = defineProps<{ cor: string | null; logoUrl: string | null; empresa: string }>()
const emit = defineEmits<{ corSalva: [cor: string]; logoTrocado: [url: string | null] }>()
const aberto = defineModel<boolean>('aberto', { default: false })

const texto = ref('')
const erro = ref<string | null>(null)
const salvando = ref(false)

// Ao abrir, começa pela cor da conta (ou vazio, com a prévia na cor dos modelos).
watch(aberto, (v) => {
  if (!v) return
  texto.value = props.cor ?? ''
  erro.value = null
})

const escolhida = computed(() => normalizarCor(texto.value))
const previa = computed(() => escolhida.value ?? props.cor ?? COR_DOS_MODELOS)
const textoPrevia = computed(() => corDoTexto(previa.value))
/** Algo digitado e diferente da cor salva (o clique confere o formato e mostra o erro). */
const podeSalvar = computed(() => !!texto.value.trim() && (escolhida.value === null || escolhida.value !== props.cor))

function escolher(cor: string) {
  texto.value = cor
  erro.value = null
}

async function salvar() {
  if (!escolhida.value) {
    erro.value = MENSAGEM_COR
    return
  }
  salvando.value = true
  erro.value = null
  try {
    const r = await marcaApi.salvar(escolhida.value)
    avisar.sucesso(textoCorSalva(r.formularios_atualizados))
    emit('corSalva', r.cor)
    aberto.value = false
  } catch (e) {
    if (e instanceof ApiError && e.status === 422) erro.value = e.campo('cor') ?? e.mensagem
    else avisar.erro(mensagemDoErro(e))
  } finally {
    salvando.value = false
  }
}
</script>

<template>
  <Modal
    v-model:aberto="aberto"
    titulo="Sua marca nas pesquisas"
    descricao="O logo e a cor aparecem na página da pesquisa e nos e-mails que seus clientes recebem."
    tamanho="lg"
    :bloqueado="salvando"
  >
    <div class="flex flex-col gap-7">
      <section class="flex flex-col gap-3" aria-labelledby="t-marca-logo">
        <h3 id="t-marca-logo" class="text-sm font-bold text-texto">Logo</h3>
        <LogoEmpresa :logo-url="logoUrl" :nome="empresa" @trocado="(url) => emit('logoTrocado', url)" />
      </section>

      <section class="flex flex-col gap-3 border-t border-borda pt-6" aria-labelledby="t-marca-cor">
        <div>
          <h3 id="t-marca-cor" class="text-sm font-bold text-texto">Cor</h3>
          <p class="mt-0.5 text-sm text-texto-suave">Vai nos botões da pesquisa e no destaque dos e-mails. Escolha uma sugestão ou digite a da sua marca.</p>
        </div>
        <fieldset>
          <legend class="sr-only">Sugestões de cor</legend>
          <div class="grid grid-cols-4 gap-2 sm:grid-cols-8" data-paleta>
            <label
              v-for="c in CORES_MARCA"
              :key="c.cor"
              class="group relative flex cursor-pointer flex-col items-center gap-1 rounded-xl p-1 has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-offset-2 has-[:focus-visible]:outline-foco"
              :title="`${c.nome} (${c.cor})`"
            >
              <input type="radio" name="cor-marca" class="sr-only" :value="c.cor" :checked="escolhida === c.cor" @change="escolher(c.cor)" />
              <span
                class="flex h-11 w-full items-center justify-center rounded-lg ring-1 ring-inset ring-black/10 transition-transform group-hover:scale-105 dark:ring-white/20"
                :class="escolhida === c.cor ? 'outline-2 outline-offset-2 outline-texto' : ''"
                :style="{ backgroundColor: c.cor, color: corDoTexto(c.cor) }"
                aria-hidden="true"
              >
                <Check v-if="escolhida === c.cor" class="size-5" stroke-width="3" />
              </span>
              <span class="text-xs text-texto-suave">{{ c.nome }}<span class="sr-only"> ({{ c.cor }})</span></span>
            </label>
          </div>
        </fieldset>
        <div class="grid grid-cols-1 items-start gap-4 sm:grid-cols-[minmax(0,14rem)_minmax(0,1fr)]">
          <Campo
            v-model="texto"
            rotulo="Código da cor"
            dica="No formato #RRGGBB, como #D63A18."
            :erro="erro"
            autocomplete="off"
            spellcheck="false"
            maxlength="9"
            @update:model-value="erro = null"
          >
            <template #antes>
              <span class="size-4 rounded ring-1 ring-inset ring-black/10 dark:ring-white/20" :style="{ backgroundColor: previa }" />
            </template>
          </Campo>
          <!-- Prévia: a pesquisa como o cliente vê (fundo claro, como a página pública) -->
          <figure class="flex flex-col gap-1.5" data-previa-marca>
            <div class="overflow-hidden rounded-xl bg-white text-slate-900 shadow-cartao ring-1 ring-slate-200">
              <div class="h-1.5" :style="{ backgroundColor: previa }" />
              <div class="flex flex-col gap-3 p-4">
                <img v-if="logoUrl" :src="logoUrl" alt="" class="max-h-7 max-w-32 self-start object-contain" />
                <p class="text-sm font-semibold leading-snug">De 0 a 10, quanto você recomendaria a {{ empresa }}?</p>
                <div class="grid grid-cols-11 gap-0.5" aria-hidden="true">
                  <span
                    v-for="n in 11"
                    :key="n"
                    class="flex h-6 items-center justify-center rounded border text-[10px] font-bold"
                    :class="n - 1 === 9 ? 'border-transparent' : 'border-slate-200 text-slate-600'"
                    :style="n - 1 === 9 ? { backgroundColor: previa, color: textoPrevia } : undefined"
                    >{{ n - 1 }}</span
                  >
                </div>
                <span
                  class="inline-flex h-10 items-center justify-center self-end rounded-xl px-5 text-sm font-bold shadow-sm"
                  :style="{ backgroundColor: previa, color: textoPrevia }"
                  data-botao-previa
                  >Continuar</span
                >
              </div>
            </div>
            <figcaption class="text-xs text-texto-fraco">
              Prévia com a cor {{ previa }}<template v-if="!escolhida && !cor"> (a dos modelos)</template>.
            </figcaption>
          </figure>
        </div>
      </section>
    </div>

    <template #rodape>
      <Botao variante="secundario" :desabilitado="salvando" @click="aberto = false">Fechar</Botao>
      <Botao :carregando="salvando" :desabilitado="!podeSalvar" data-salvar-cor @click="salvar">Salvar cor</Botao>
    </template>
  </Modal>
</template>

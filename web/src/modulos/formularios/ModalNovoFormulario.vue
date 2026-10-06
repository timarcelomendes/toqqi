<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { GitBranch } from 'lucide-vue-next'
import { formulariosApi, mensagemDoErro, type ModeloFormulario } from '@/api'
import { avisar } from '@/composables/avisos'
import { useFormulario } from '@/composables/formulario'
import { useSessaoStore } from '@/stores/sessao'
import { tipoPrincipal } from '@/pesquisa/logica'
import { logoParaCliente } from '@/utils/imagens'
import { TIPOS_FORMULARIO } from '@/utils/rotulos'
import Pesquisa from '@/pesquisa/Pesquisa.vue'
import Alerta from '@/components/ui/Alerta.vue'
import Botao from '@/components/ui/Botao.vue'
import Campo from '@/components/ui/Campo.vue'
import Carregando from '@/components/ui/Carregando.vue'
import Etiqueta from '@/components/ui/Etiqueta.vue'
import Modal from '@/components/ui/Modal.vue'

const aberto = defineModel<boolean>('aberto', { default: false })
const router = useRouter()
const sessao = useSessaoStore()
const { enviando, erroGeral, erros, executar, limpar } = useFormulario()

const modelos = ref<ModeloFormulario[]>([])
const carregando = ref(false)
const erroModelos = ref<string | null>(null)
const escolhido = ref<string>('')
const nome = ref('')
const nomeEditado = ref(false)
const erroNome = ref<string | null>(null)

const modelo = computed(() => modelos.value.find((m) => m.chave === escolhido.value) ?? null)
/** Etapa 5l: o modelo tem lógica (mostrar se, pular) ou finais por condição. */
const comLogica = (m: ModeloFormulario) =>
  !!m.finais?.length || (m.perguntas ?? []).some((p) => !!p.logica?.mostrar_se?.condicoes?.length || !!p.logica?.pular?.length || !!p.condicao)

async function carregar() {
  carregando.value = true
  erroModelos.value = null
  try {
    modelos.value = await formulariosApi.modelos()
    if (!escolhido.value && modelos.value[0]) escolhido.value = modelos.value[0].chave
  } catch (e) {
    erroModelos.value = mensagemDoErro(e)
  } finally {
    carregando.value = false
  }
}

watch(aberto, (v) => {
  if (!v) return
  limpar()
  erroNome.value = null
  nome.value = ''
  nomeEditado.value = false
  if (!modelos.value.length) carregar()
})
// Sugere o nome do modelo enquanto a pessoa não escreve o dela.
watch(modelo, (m) => {
  if (m && !nomeEditado.value) nome.value = m.chave === 'em_branco' ? '' : m.nome
})

async function criar() {
  erroNome.value = nome.value.trim() ? null : 'Dê um nome para o formulário.'
  if (erroNome.value) return
  const f = await executar(() => formulariosApi.criar({ nome: nome.value.trim(), ...(escolhido.value ? { modelo: escolhido.value } : {}) }))
  if (!f) return
  avisar.sucesso('Formulário criado. Agora é só ajustar do seu jeito.')
  aberto.value = false
  router.push(`/formularios/${f.id}`)
}
</script>

<template>
  <Modal v-model:aberto="aberto" titulo="Novo formulário" descricao="Comece por um modelo pronto. Dá para mudar tudo depois." tamanho="lg" :bloqueado="enviando">
    <form id="form-novo" class="flex flex-col gap-5" novalidate @submit.prevent="criar">
      <Alerta v-if="erroGeral && !erros.nome" tom="erro">{{ erroGeral }}</Alerta>
      <Campo
        v-model="nome"
        rotulo="Nome do formulário"
        obrigatorio
        data-autofoco
        maxlength="120"
        placeholder="Ex.: Pesquisa pós-entrega"
        :erro="erroNome ?? erros.nome"
        dica="Só a sua equipe vê este nome."
        @input="nomeEditado = true"
      />
      <Carregando v-if="carregando" :linhas="3" />
      <Alerta v-else-if="erroModelos" tom="erro">
        {{ erroModelos }} <button type="button" class="link ml-1" @click="carregar">Tentar de novo</button>
      </Alerta>
      <div v-else class="grid gap-4 md:grid-cols-2">
        <fieldset>
          <legend class="mb-2 text-sm font-semibold text-texto">Modelo</legend>
          <div class="flex max-h-[26rem] flex-col gap-2 overflow-y-auto pr-1">
            <label
              v-for="m in modelos"
              :key="m.chave"
              class="flex cursor-pointer flex-col gap-1 rounded-xl border p-3 transition-colors has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-offset-2 has-[:focus-visible]:outline-foco"
              :class="escolhido === m.chave ? 'border-marca bg-marca-suave' : 'border-borda-forte hover:bg-superficie-2'"
            >
              <input v-model="escolhido" type="radio" name="modelo" :value="m.chave" class="sr-only" />
              <span class="flex items-start justify-between gap-2">
                <span class="text-sm font-bold text-texto">{{ m.nome }}</span>
                <span class="flex shrink-0 flex-wrap justify-end gap-1">
                  <Etiqueta v-if="comLogica(m)" tom="info" data-com-logica><GitBranch class="size-3" aria-hidden="true" /> Com lógica</Etiqueta>
                  <Etiqueta :tom="TIPOS_FORMULARIO[tipoPrincipal(m.perguntas ?? [])].tom">{{ TIPOS_FORMULARIO[tipoPrincipal(m.perguntas ?? [])].rotulo }}</Etiqueta>
                </span>
              </span>
              <span class="text-xs text-texto-suave">{{ m.descricao }}</span>
            </label>
          </div>
        </fieldset>
        <div class="flex flex-col gap-2">
          <p class="text-sm font-semibold text-texto" id="titulo-previa-modelo">Como fica</p>
          <div class="max-h-[26rem] overflow-y-auto rounded-xl bg-slate-100 p-2" aria-labelledby="titulo-previa-modelo" role="region">
            <Pesquisa
              v-if="modelo"
              :key="modelo.chave"
              :formulario="{ nome: modelo.nome, perguntas: modelo.perguntas ?? [], tema: { ...modelo.tema, logo_url: logoParaCliente(modelo.tema?.logo_url, sessao.conta?.logo_url).url } }"
              :finais="modelo.finais ?? []"
              :variaveis="{ empresa: sessao.conta?.nome ?? 'Sua empresa', nome: 'Maria', assunto: '', referencia: '' }"
              previa
              compacto
            />
          </div>
        </div>
      </div>
    </form>
    <template #rodape>
      <Botao variante="secundario" :desabilitado="enviando" @click="aberto = false">Cancelar</Botao>
      <Botao tipo="submit" form="form-novo" :carregando="enviando" :desabilitado="carregando">Criar formulário</Botao>
    </template>
  </Modal>
</template>

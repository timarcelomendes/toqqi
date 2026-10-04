<script setup lang="ts">
// Um grupo de Plataforma › Parâmetros (etapa 5g, §7): um formulário com "Descartar" e "Salvar alterações" (desligados
// sem mudança) e "Alterado em … por …". Salvar confere os campos (as regras da API), pede a prévia e, se ela pedir
// confirmação, abre o diálogo com as contas atingidas; "Confirmar e salvar" manda o PUT com `confirmar`. No grupo IA, um
// modelo ou esforço novo é testado na OpenAI antes de salvar ("Testando o modelo…"). 409 de versão: alerta com
// "Recarregar"; 422: nos campos; 503 e outros: alerta. O foco volta ao botão de salvar (ou vai ao primeiro erro).
import { computed, nextTick, reactive, ref, useId, watch } from 'vue'
import { ApiError, mensagemDoErro, parametrosApi, type GrupoParametros, type GrupoParametrosPlataforma, type ValorParametro } from '@/api'
import Alerta from '@/components/ui/Alerta.vue'
import Botao from '@/components/ui/Botao.vue'
import Modal from '@/components/ui/Modal.vue'
import CampoParametro from './CampoParametro.vue'
import {
  LAYOUT_GRUPOS,
  aplicarPadrao,
  campoDaChave,
  camposDoGrupo,
  chavesAlteradas,
  formDe,
  lerFormulario,
  testaModelo,
  textoAlterado,
  textoConfirmacao,
  type Confirmacao,
  type FormParametros,
} from './parametros'

const props = defineProps<{ dados: GrupoParametrosPlataforma }>()
const emit = defineEmits<{ salvo: [GrupoParametrosPlataforma]; recarregar: [] }>()

const STATUS_SALVO = 'Parâmetros salvos.'
const idTitulo = `t-param-${useId()}`
const grupo = computed(() => props.dados.grupo as GrupoParametros)
const layout = computed(() => LAYOUT_GRUPOS[grupo.value])

const form = reactive<FormParametros>(formDe(props.dados))
const erros = reactive<Record<string, string>>({})
const alerta = ref<{ tom: 'erro' | 'atencao'; texto: string; recarregar?: boolean } | null>(null)
/** O que o leitor de tela ouve: "Conferindo as mudanças…", "Salvando…", "Testando o modelo…", "Parâmetros salvos.". */
const status = ref('')
const ocupado = ref<'previa' | 'salvando' | null>(null)
const confirmacao = ref<Confirmacao | null>(null)
const dialogoAberto = ref(false)
const raiz = ref<HTMLElement | null>(null)
/** Os valores conferidos na prévia, que vão no PUT. */
let pendentes: Record<string, ValorParametro> | null = null

const alteradas = computed(() => chavesAlteradas(props.dados, form))
const alterado = computed(() => alteradas.value.length > 0)
const testando = ref(false)
const textoSalvando = computed(() => (testando.value ? 'Testando o modelo…' : 'Salvando…'))

function limparErros() {
  for (const k of Object.keys(erros)) delete erros[k]
}

function reiniciar(d: GrupoParametrosPlataforma) {
  const novo = formDe(d)
  form.textos = novo.textos
  form.semLimite = novo.semLimite
  limparErros()
  alerta.value = null
}

// Dados novos (salvou, recarregou): os campos voltam ao que está em uso.
watch(
  () => props.dados,
  (d) => reiniciar(d),
)
// Mexeu de novo depois de salvar: o "Parâmetros salvos." sai.
watch(alterado, (v) => {
  if (v && status.value === STATUS_SALVO) status.value = ''
})

function descartar() {
  reiniciar(props.dados)
  status.value = ''
}

function aoDigitar(chave: string) {
  delete erros[chave]
}

function usarPadrao(chave: string) {
  aplicarPadrao(form, chave, props.dados.padroes[chave])
  delete erros[chave]
}

/** O "Salvar alterações" deste cartão (fora do fieldset: não desliga durante a prévia nem ao salvar). */
const botaoSalvar = () => raiz.value?.querySelector<HTMLElement>('[data-salvar]') ?? null

async function focarBotao() {
  await nextTick()
  botaoSalvar()?.focus()
}

/** Foca o primeiro campo com erro; sem nenhum, o botão de salvar. */
async function focarPrimeiroErro() {
  await nextTick()
  const el = raiz.value?.querySelector<HTMLElement>('[aria-invalid="true"]')
  if (el) el.focus()
  else await focarBotao()
}

/** Erro da API: campos do grupo vão para os campos; o resto, para o alerta do cartão. */
function tratarErro(e: unknown): 'campos' | 'alerta' {
  status.value = ''
  if (!(e instanceof ApiError)) {
    alerta.value = { tom: 'erro', texto: mensagemDoErro(e) }
    return 'alerta'
  }
  if (e.status === 409 && e.codigo === 'parametros_alterados') {
    alerta.value = { tom: 'atencao', texto: e.mensagem, recarregar: true }
    return 'alerta'
  }
  if (e.status === 422) {
    const chaves = new Set(camposDoGrupo(grupo.value).map((c) => c.chave))
    const soltas: string[] = []
    for (const [k, msg] of Object.entries(e.campos)) {
      if (chaves.has(k)) erros[k] = msg
      else soltas.push(msg)
    }
    if (soltas.length || !Object.keys(e.campos).length) alerta.value = { tom: 'erro', texto: soltas.length ? soltas.join(' ') : e.mensagem }
    return Object.keys(erros).length ? 'campos' : 'alerta'
  }
  alerta.value = { tom: 'erro', texto: e.mensagem }
  return 'alerta'
}

/** Pede a prévia dos valores; com confirmação, abre o diálogo; sem, salva direto. */
async function conferir(valores: Record<string, ValorParametro>) {
  ocupado.value = 'previa'
  status.value = 'Conferindo as mudanças…'
  try {
    const previa = await parametrosApi.previa(grupo.value, valores)
    pendentes = valores
    if (previa.precisa_confirmar) {
      ocupado.value = null
      status.value = ''
      confirmacao.value = textoConfirmacao(props.dados.rotulo, previa)
      dialogoAberto.value = true
      return
    }
    await gravar(false)
  } catch (e) {
    ocupado.value = null
    if (tratarErro(e) === 'campos') await focarPrimeiroErro()
    else await focarBotao()
  }
}

async function salvar() {
  if (!alterado.value || ocupado.value) return
  limparErros()
  alerta.value = null
  status.value = ''
  const { valores, erros: locais } = lerFormulario(props.dados, form)
  if (Object.keys(locais).length) {
    Object.assign(erros, locais)
    await focarPrimeiroErro()
    return
  }
  testando.value = testaModelo(alteradas.value)
  // Enviado com Enter num campo: o fieldset desliga durante a prévia e o navegador tiraria o foco do campo (para o body,
  // de onde o diálogo não teria para onde devolvê-lo). O foco passa já ao botão de salvar, como quando se clica nele.
  botaoSalvar()?.focus()
  await conferir(valores)
}

/** "Confirmar e salvar" fechou o diálogo: quem gravou cuida do foco (o botão, o campo com erro ou o diálogo de novo). */
let fechouAoGravar = false

function fecharDialogoAoGravar() {
  if (!dialogoAberto.value) return
  fechouAoGravar = true
  dialogoAberto.value = false
}

async function gravar(confirmar: boolean) {
  if (!pendentes) return
  ocupado.value = 'salvando'
  status.value = textoSalvando.value
  let destino: 'botao' | 'campos' = 'botao'
  try {
    const r = await parametrosApi.salvar(grupo.value, { versao: props.dados.versao, valores: pendentes, confirmar })
    pendentes = null
    fecharDialogoAoGravar()
    status.value = STATUS_SALVO
    emit('salvo', r)
  } catch (e) {
    fecharDialogoAoGravar()
    if (e instanceof ApiError && e.status === 409 && e.codigo === 'confirmacao_necessaria' && pendentes) {
      // Algo mudou desde a prévia: confere de novo e mostra o diálogo com os números de agora.
      ocupado.value = null
      await conferir(pendentes)
      return
    }
    destino = tratarErro(e) === 'campos' ? 'campos' : 'botao'
  } finally {
    if (ocupado.value === 'salvando') ocupado.value = null
  }
  if (destino === 'campos') await focarPrimeiroErro()
  else await focarBotao()
}

function cancelar() {
  if (ocupado.value === 'salvando') return
  dialogoAberto.value = false
}

// Fechou o diálogo sem salvar (Cancelar, Esc, X ou fora): nada foi salvo e o foco volta ao "Salvar alterações" deste
// cartão, por qualquer caminho e também quando o diálogo veio do Enter num campo (o Modal devolveria ao que tinha o foco
// ao abrir). Fechado por "Confirmar e salvar", o foco fica com quem gravou.
function aoFecharDialogo() {
  if (fechouAoGravar) {
    fechouAoGravar = false
    return
  }
  if (ocupado.value !== 'salvando' && status.value !== STATUS_SALVO) status.value = ''
  void focarBotao()
}

const valor = (chave: string) => props.dados.padroes[chave]
const origem = (chave: string) => props.dados.origens[chave]
const largo = (chave: string) => campoDaChave(chave)?.tipo === 'exclusao'
</script>

<template>
  <section ref="raiz" class="cartao" :aria-labelledby="idTitulo" :data-grupo="dados.grupo">
    <form novalidate @submit.prevent="salvar">
      <div class="flex flex-col gap-1 border-b border-borda px-5 py-4 sm:px-6">
        <h2 :id="idTitulo" class="text-base font-bold text-texto">{{ dados.rotulo }}</h2>
        <p v-if="layout" class="text-sm text-texto-suave">{{ layout.descricao }}</p>
        <p class="text-xs text-texto-fraco [overflow-wrap:anywhere]" data-alterado>{{ textoAlterado(dados) }}</p>
      </div>

      <fieldset v-if="layout" class="m-0 flex min-w-0 flex-col gap-6 border-0 p-5 sm:p-6" :disabled="ocupado !== null">
        <legend class="sr-only">{{ dados.rotulo }}</legend>
        <Alerta v-if="alerta" :tom="alerta.tom" data-alerta-cartao>
          {{ alerta.texto }}
          <button v-if="alerta.recarregar" type="button" class="link ml-1" data-recarregar @click="emit('recarregar')">Recarregar</button>
        </Alerta>

        <div :class="layout.ladoALado ? 'grid gap-6 lg:grid-cols-3' : 'flex flex-col gap-6'">
          <fieldset v-for="b in layout.blocos" :key="b.legenda" class="m-0 min-w-0 border-0 p-0" :data-bloco="b.legenda">
            <legend class="mb-3 text-sm font-bold text-texto">{{ b.legenda }}</legend>
            <div v-if="b.chaves.length" :class="layout.ladoALado ? 'flex flex-col gap-4' : 'grid gap-4 sm:grid-cols-2 lg:grid-cols-3'">
              <CampoParametro
                v-for="k in b.chaves"
                :key="k"
                v-model:texto="form.textos[k]"
                v-model:sem-limite="form.semLimite[k]"
                :class="largo(k) ? 'sm:col-span-full' : ''"
                :chave="k"
                :padrao="valor(k)"
                :origem="origem(k)"
                :erro="erros[k]"
                @update:texto="aoDigitar(k)"
                @update:sem-limite="aoDigitar(k)"
                @usar-padrao="usarPadrao(k)"
              />
            </div>
            <div v-if="b.blocos?.length" class="grid gap-6 lg:grid-cols-3">
              <fieldset v-for="sb in b.blocos" :key="sb.legenda" class="m-0 min-w-0 rounded-xl border border-borda p-4" :data-bloco="sb.legenda">
                <legend class="px-1 text-sm font-semibold text-texto">{{ sb.legenda }}</legend>
                <div class="flex flex-col gap-4">
                  <CampoParametro
                    v-for="k in sb.chaves"
                    :key="k"
                    v-model:texto="form.textos[k]"
                    v-model:sem-limite="form.semLimite[k]"
                    :chave="k"
                    :padrao="valor(k)"
                    :origem="origem(k)"
                    :erro="erros[k]"
                    @update:texto="aoDigitar(k)"
                    @usar-padrao="usarPadrao(k)"
                  />
                </div>
              </fieldset>
            </div>
          </fieldset>
        </div>

        <p v-if="layout.nota" class="text-sm text-texto-suave" data-nota>{{ layout.nota }}</p>
      </fieldset>

      <div class="flex flex-col-reverse gap-2 border-t border-borda px-5 py-4 sm:flex-row sm:items-center sm:justify-end sm:px-6">
        <p class="min-h-5 text-sm text-texto-suave sm:mr-auto" aria-live="polite" data-status>{{ dialogoAberto ? '' : status }}</p>
        <Botao variante="secundario" :desabilitado="!alterado || ocupado !== null" data-descartar @click="descartar">Descartar</Botao>
        <Botao tipo="submit" :carregando="ocupado !== null && !dialogoAberto" :desabilitado="!alterado" focavel data-salvar>Salvar alterações</Botao>
      </div>
    </form>

    <Modal
      v-if="confirmacao"
      v-model:aberto="dialogoAberto"
      :titulo="confirmacao.titulo"
      papel="alertdialog"
      tamanho="lg"
      :bloqueado="ocupado === 'salvando'"
      @fechado="aoFecharDialogo"
    >
      <div class="flex flex-col gap-4" data-dialogo-parametros>
        <ul class="flex list-disc flex-col gap-2 pl-5 text-[0.95rem] leading-relaxed text-texto-suave">
          <li v-for="l in confirmacao.linhas" :key="l.chave" :data-linha="l.chave">{{ l.texto }}</li>
        </ul>
        <Alerta v-if="confirmacao.aviso" tom="atencao" data-aviso-diminui>{{ confirmacao.aviso }}</Alerta>
        <p class="sr-only" aria-live="polite">{{ dialogoAberto ? status : '' }}</p>
      </div>
      <template #rodape>
        <Botao variante="secundario" :desabilitado="ocupado === 'salvando'" @click="cancelar">Cancelar</Botao>
        <Botao data-autofoco :carregando="ocupado === 'salvando'" focavel data-confirmar-salvar @click="ocupado ? undefined : gravar(true)">
          {{ ocupado === 'salvando' ? textoSalvando : 'Confirmar e salvar' }}
        </Botao>
      </template>
    </Modal>
  </section>
</template>

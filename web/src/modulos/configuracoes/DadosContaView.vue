<script setup lang="ts">
// Configurações › Dados da conta (etapa 5f, docs/api-etapa-5f.md §10): só o administrador, também com o aceite dos
// termos pendente (ROTAS_LIVRES) e com a conta encerrada. "Exportar todos os dados": o .zip com uma planilha (CSV) por
// assunto. "Zona de risco": apagar de vez as respostas, os contatos ou tudo (Recomeçar do zero), com as contagens de
// GET /conta/zona-de-risco e a confirmação APAGAR; depois de apagar, o resumo e as contagens de novo.
import { computed, onBeforeUnmount, onMounted, ref, useId } from 'vue'
import { CheckCircle2, Circle, CircleCheck, DatabaseBackup, Download, Trash2, TriangleAlert } from 'lucide-vue-next'
import { dadosContaApi, mensagemDoErro, type OpcaoZonaRisco, type ResultadoZonaRisco, type ZonaRisco } from '@/api'
import CabecalhoPagina from '@/components/app/CabecalhoPagina.vue'
import Alerta from '@/components/ui/Alerta.vue'
import Botao from '@/components/ui/Botao.vue'
import Carregando from '@/components/ui/Carregando.vue'
import ModalZonaRisco from './ModalZonaRisco.vue'
import NavConfiguracoes from './NavConfiguracoes.vue'
import {
  OPCOES_ZONA,
  ROTULOS_OPCAO,
  TEXTO_EXPORTACAO,
  apagaAlgo,
  contagensDaOpcao,
  mensagemErroExportacao,
  mensagemExportacao,
  textoOpcao,
  textoResultado,
  textoSempreFica,
} from './dadosConta'

const id = useId()

// ── Exportar todos os dados ─────────────────────────────────────────────────
const baixando = ref(false)
const erroExportacao = ref<string | null>(null)
const exportacaoPronta = ref(false)
const andamento = computed(() => mensagemExportacao({ baixando: baixando.value, erro: erroExportacao.value, pronta: exportacaoPronta.value }))

async function baixarTudo() {
  if (baixando.value) return
  baixando.value = true
  erroExportacao.value = null
  exportacaoPronta.value = false
  try {
    await dadosContaApi.baixarTudo()
    exportacaoPronta.value = true
  } catch (e) {
    erroExportacao.value = mensagemErroExportacao(e)
  } finally {
    baixando.value = false
  }
}

// ── Zona de risco ───────────────────────────────────────────────────────────
const zona = ref<ZonaRisco | null>(null)
const carregandoZona = ref(true)
const erroZona = ref<string | null>(null)
const opcao = ref<OpcaoZonaRisco>('respostas')
const modalAberto = ref(false)
const resultado = ref<string | null>(null)
let controle: AbortController | null = null

const podeApagar = computed(() => !!zona.value && apagaAlgo(contagensDaOpcao(zona.value, opcao.value)))

/** Lê as contagens. Na releitura (depois de apagar), o conteúdo fica na tela: o botão que abriu o diálogo não some. */
async function carregarZona() {
  controle?.abort()
  controle = new AbortController()
  carregandoZona.value = true
  erroZona.value = null
  try {
    zona.value = await dadosContaApi.zonaDeRisco(controle.signal)
  } catch (e) {
    if (e instanceof DOMException && e.name === 'AbortError') return
    erroZona.value = mensagemDoErro(e)
  } finally {
    carregandoZona.value = false
  }
}

function abrirConfirmacao() {
  if (!podeApagar.value) return
  resultado.value = null
  modalAberto.value = true
}

function aoApagar(r: ResultadoZonaRisco) {
  resultado.value = textoResultado(r.apagados)
  void carregarZona()
}

onMounted(carregarZona)
onBeforeUnmount(() => controle?.abort())
</script>

<template>
  <NavConfiguracoes />
  <CabecalhoPagina titulo="Dados da conta" descricao="Baixe uma cópia de tudo o que a sua empresa guarda no Toqqi ou apague dados de vez." />

  <div class="flex flex-col gap-6">
    <section class="cartao grid gap-6 p-5 sm:p-6 md:grid-cols-3" aria-labelledby="titulo-exportar" data-exportar-tudo>
      <div>
        <div class="mb-3 flex size-10 items-center justify-center rounded-xl bg-marca-suave text-marca-texto">
          <DatabaseBackup class="size-5" aria-hidden="true" />
        </div>
        <h2 id="titulo-exportar" class="text-base font-bold text-texto">Exportar todos os dados</h2>
        <p class="mt-1 text-sm text-texto-suave">{{ TEXTO_EXPORTACAO }}</p>
      </div>
      <div class="flex flex-col items-start gap-3 md:col-span-2">
        <Botao :carregando="baixando" focavel data-baixar-tudo @click="baixarTudo">
          <Download v-if="!baixando" class="size-4" aria-hidden="true" /> Baixar todos os dados
        </Botao>
        <!-- Sempre no lugar, para o leitor de tela anunciar o andamento ("Gerando o arquivo…") e o fim. -->
        <p aria-live="polite" class="text-sm text-texto-suave" data-status-exportacao>{{ andamento && andamento.tom !== 'erro' ? andamento.texto : '' }}</p>
        <Alerta v-if="erroExportacao" tom="erro" class="w-full" data-erro-exportacao>{{ erroExportacao }}</Alerta>
      </div>
    </section>

    <section class="cartao grid gap-6 border-erro/40 p-5 sm:p-6 md:grid-cols-3" aria-labelledby="titulo-zona" data-zona-risco>
      <div>
        <div class="mb-3 flex size-10 items-center justify-center rounded-xl bg-erro-suave text-erro">
          <TriangleAlert class="size-5" aria-hidden="true" />
        </div>
        <h2 id="titulo-zona" class="text-base font-bold text-texto">Zona de risco</h2>
        <p class="mt-1 text-sm text-texto-suave">Apaga dados da conta de uma vez. Não tem volta: baixe todos os dados antes.</p>
      </div>

      <div class="flex min-w-0 flex-col gap-4 md:col-span-2">
        <!-- O resumo do que foi apagado (região sempre no lugar, para ser anunciada). -->
        <div aria-live="polite" data-resultado-zona>
          <p v-if="resultado" class="flex gap-3 rounded-xl border border-sucesso/25 bg-sucesso-suave p-3.5 text-sm text-texto">
            <CheckCircle2 class="mt-0.5 size-5 shrink-0 text-sucesso" aria-hidden="true" />
            <span class="min-w-0">{{ resultado }}</span>
          </p>
        </div>

        <Carregando v-if="!zona && carregandoZona" :linhas="3" rotulo="Carregando as contagens…" />
        <Alerta v-if="erroZona" tom="erro" data-erro-zona>
          {{ erroZona }} <button type="button" class="link ml-1" @click="carregarZona">Tentar de novo</button>
        </Alerta>

        <template v-if="zona">
          <fieldset class="m-0 min-w-0 border-0 p-0" :aria-busy="carregandoZona || undefined">
            <legend class="mb-2 text-sm font-semibold text-texto">O que apagar</legend>
            <div class="flex flex-col gap-2">
              <label
                v-for="o in OPCOES_ZONA"
                :key="o"
                class="relative flex min-w-0 cursor-pointer gap-2.5 rounded-xl border p-3.5 transition-colors has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-offset-2 has-[:focus-visible]:outline-foco"
                :class="opcao === o ? 'border-erro bg-erro-suave' : 'border-borda-forte hover:bg-superficie-2'"
                :data-opcao="o"
              >
                <input
                  v-model="opcao"
                  type="radio"
                  :name="`zona-${id}`"
                  :value="o"
                  class="sr-only"
                  :aria-labelledby="`${id}-${o}-rotulo`"
                  :aria-describedby="`${id}-${o}-texto`"
                />
                <CircleCheck v-if="opcao === o" class="mt-0.5 size-4 shrink-0 text-erro" aria-hidden="true" />
                <Circle v-else class="mt-0.5 size-4 shrink-0 text-texto-fraco" aria-hidden="true" />
                <span class="flex min-w-0 flex-col gap-0.5">
                  <span :id="`${id}-${o}-rotulo`" class="text-sm font-bold text-texto">{{ ROTULOS_OPCAO[o].rotulo }}</span>
                  <span :id="`${id}-${o}-texto`" class="text-sm text-texto-suave" data-texto-opcao>{{ textoOpcao(o, zona) }}</span>
                </span>
              </label>
            </div>
          </fieldset>

          <p class="text-sm text-texto-suave" data-sempre-fica>{{ textoSempreFica(zona.mantidos) }}</p>

          <div class="flex flex-col items-start gap-2 sm:flex-row sm:items-center">
            <Botao
              variante="perigo"
              :desabilitado="!podeApagar"
              focavel
              :aria-describedby="podeApagar ? undefined : `${id}-nada`"
              data-abrir-zona
              @click="abrirConfirmacao"
            >
              <Trash2 class="size-4" aria-hidden="true" /> Apagar…
            </Botao>
            <p v-if="!podeApagar" :id="`${id}-nada`" class="text-sm text-texto-fraco">Esta opção não tem nada para apagar.</p>
          </div>
        </template>
      </div>
    </section>
  </div>

  <ModalZonaRisco
    v-model:aberto="modalAberto"
    :opcao="opcao"
    :zona="zona"
    :baixando="baixando"
    :mensagem-exportacao="andamento"
    @baixar="baixarTudo"
    @apagado="aoApagar"
  />
</template>

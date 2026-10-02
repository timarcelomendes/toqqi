<script setup lang="ts">
// Configurações › Planos de ação: prazo de cada grupo (1 a 90 dias) e se promotor também ganha ação.
import { computed, onMounted, reactive, ref } from 'vue'
import { onBeforeRouteLeave } from 'vue-router'
import { CalendarClock, ThumbsUp } from 'lucide-vue-next'
import { acoesApi, mensagemDoErro, type ConfigAcoes } from '@/api'
import { avisar } from '@/composables/avisos'
import { confirmar } from '@/composables/confirmacao'
import { useFormulario } from '@/composables/formulario'
import { useSessaoStore } from '@/stores/sessao'
import CabecalhoPagina from '@/components/app/CabecalhoPagina.vue'
import Alerta from '@/components/ui/Alerta.vue'
import Botao from '@/components/ui/Botao.vue'
import Carregando from '@/components/ui/Carregando.vue'
import Interruptor from '@/components/ui/Interruptor.vue'
import NavConfiguracoes from './NavConfiguracoes.vue'
import { PRAZOS_ACOES, montarConfigAcoes, validarConfigAcoes } from './configAcoes'

const sessao = useSessaoStore()
const podeSalvar = computed(() => sessao.pode('configuracoes.gerenciar'))
const carregando = ref(true)
const erroCarga = ref<string | null>(null)
const original = ref<ConfigAcoes | null>(null)
const { enviando, erroGeral, erros, executar, limpar } = useFormulario()
const locais = reactive<Record<string, string>>({})
// Números editados como texto: o campo pode ficar vazio enquanto a pessoa digita.
const texto = reactive({ prazo_detrator: '2', prazo_neutro: '5', prazo_promotor: '7' })
const acaoPromotor = ref(false)

function aplicar(c: ConfigAcoes) {
  original.value = { ...c }
  texto.prazo_detrator = String(c.prazo_detrator)
  texto.prazo_neutro = String(c.prazo_neutro)
  texto.prazo_promotor = String(c.prazo_promotor)
  acaoPromotor.value = !!c.acao_promotor
}

const atual = computed(() => montarConfigAcoes(texto, acaoPromotor.value))
const alterado = computed(() => !!original.value && JSON.stringify(atual.value) !== JSON.stringify(original.value))
const erro = (c: string) => locais[c] ?? erros[c] ?? null

async function carregar() {
  carregando.value = true
  erroCarga.value = null
  try {
    aplicar(await acoesApi.configuracao())
  } catch (e) {
    erroCarga.value = mensagemDoErro(e)
  } finally {
    carregando.value = false
  }
}

async function salvar(): Promise<boolean> {
  limpar()
  for (const k of Object.keys(locais)) delete locais[k]
  const v = validarConfigAcoes(texto)
  if (Object.keys(v).length) {
    Object.assign(locais, v)
    erroGeral.value = 'Confira os prazos destacados.'
    return false
  }
  const r = await executar(() => acoesApi.salvarConfiguracao(atual.value))
  if (!r) return false
  aplicar(r)
  avisar.sucesso('Configurações dos planos de ação salvas. Valem para as próximas respostas.')
  return true
}

function descartar() {
  if (original.value) aplicar(original.value)
  limpar()
  for (const k of Object.keys(locais)) delete locais[k]
}

onBeforeRouteLeave(async () => {
  if (!alterado.value || enviando.value) return true
  return confirmar({
    titulo: 'Sair sem salvar?',
    mensagem: 'Você mudou os prazos e ainda não salvou. Se sair agora, as mudanças se perdem.',
    confirmar: 'Sair sem salvar',
    cancelar: 'Continuar editando',
    perigo: true,
  })
})

onMounted(carregar)
</script>

<template>
  <NavConfiguracoes />
  <CabecalhoPagina titulo="Planos de ação" descricao="Quando uma resposta vira ação sozinha e quantos dias a equipe tem para cuidar de cada cliente." />

  <Carregando v-if="carregando" :linhas="3" />
  <Alerta v-else-if="erroCarga" tom="erro">
    {{ erroCarga }} <button type="button" class="link ml-1" @click="carregar">Tentar de novo</button>
  </Alerta>

  <form v-else class="flex flex-col gap-6" novalidate @submit.prevent="salvar">
    <Alerta v-if="!podeSalvar" tom="info">Você pode ver estas configurações, mas só um administrador consegue mudar.</Alerta>
    <Alerta v-if="erroGeral" tom="erro">{{ erroGeral }}</Alerta>

    <fieldset :disabled="!podeSalvar" class="flex min-w-0 flex-col gap-6">
      <legend class="sr-only">Configurações dos planos de ação</legend>

      <section class="cartao grid grid-cols-1 gap-6 p-5 sm:p-6 md:grid-cols-3" aria-labelledby="t-prazos">
        <div>
          <div class="mb-3 flex size-10 items-center justify-center rounded-xl bg-marca-suave text-marca-texto"><CalendarClock class="size-5" aria-hidden="true" /></div>
          <h2 id="t-prazos" class="text-base font-bold text-texto">Prazo para tratar</h2>
          <p class="mt-1 text-sm text-texto-suave">
            Quantos dias a equipe tem, contados a partir do dia em que a resposta é registrada. A ação nasce com o responsável da empresa do cliente.
          </p>
        </div>
        <div class="flex flex-col gap-4 md:col-span-2">
          <div v-for="p in PRAZOS_ACOES" :key="p.chave" class="flex flex-col gap-1.5" :class="p.chave === 'prazo_promotor' && !acaoPromotor ? 'opacity-70' : ''">
            <label :for="`prazo-${p.chave}`" class="text-sm font-semibold text-texto">{{ p.rotulo }}</label>
            <p :id="`dica-${p.chave}`" class="text-sm text-texto-fraco">{{ p.descricao }}</p>
            <div class="flex items-center gap-2">
              <input
                :id="`prazo-${p.chave}`"
                v-model="texto[p.chave]"
                type="number"
                inputmode="numeric"
                min="1"
                max="90"
                :aria-invalid="erro(p.chave) ? 'true' : undefined"
                :aria-describedby="[`dica-${p.chave}`, erro(p.chave) ? `erro-${p.chave}` : ''].join(' ').trim()"
                class="h-11 w-24 rounded-xl border bg-superficie px-3 text-center text-[0.95rem] text-texto focus:outline-none focus:ring-3 disabled:bg-superficie-2 disabled:text-texto-fraco"
                :class="erro(p.chave) ? 'border-erro focus:ring-erro/20' : 'border-borda-forte focus:border-marca focus:ring-marca/20'"
              />
              <span class="text-sm text-texto-suave">dias</span>
            </div>
            <p v-if="erro(p.chave)" :id="`erro-${p.chave}`" class="text-sm font-medium text-erro">{{ erro(p.chave) }}</p>
          </div>
          <p class="text-sm text-texto-fraco">De 1 a 90 dias. No CSAT (notas de 1 a 5), nota 1 ou 2 vira ação com o prazo do detrator.</p>
        </div>
      </section>

      <section class="cartao grid grid-cols-1 gap-6 p-5 sm:p-6 md:grid-cols-3" aria-labelledby="t-promotores">
        <div>
          <div class="mb-3 flex size-10 items-center justify-center rounded-xl bg-marca-suave text-marca-texto"><ThumbsUp class="size-5" aria-hidden="true" /></div>
          <h2 id="t-promotores" class="text-base font-bold text-texto">Promotores</h2>
          <p class="mt-1 text-sm text-texto-suave">Quem deu 9 ou 10. Já está satisfeito, então não precisa de ação, mas dá para agradecer ou pedir uma indicação.</p>
        </div>
        <div class="md:col-span-2">
          <Interruptor
            v-model="acaoPromotor"
            rotulo="Criar ação também para promotores"
            descricao="Desligado, só detratores e neutros viram ação (é o mais comum). Ligado, todo promotor também ganha uma ação, de prioridade baixa, e o quadro fica mais cheio."
            :desabilitado="!podeSalvar"
          />
        </div>
      </section>
    </fieldset>

    <div v-if="podeSalvar" data-barra-fixa class="sticky bottom-0 z-10 -mx-4 flex flex-col-reverse gap-2 border-t border-borda bg-fundo/90 px-4 py-3 backdrop-blur sm:-mx-6 sm:flex-row sm:justify-end sm:px-6 lg:-mx-10 lg:px-10">
      <p v-if="alterado" class="text-sm text-texto-fraco sm:mr-auto sm:self-center">Você tem alterações não salvas.</p>
      <Botao v-if="alterado" variante="secundario" :desabilitado="enviando" @click="descartar">Descartar</Botao>
      <Botao tipo="submit" :carregando="enviando" :desabilitado="!alterado">Salvar alterações</Botao>
    </div>
  </form>
</template>

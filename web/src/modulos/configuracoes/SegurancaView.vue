<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { Clock, Globe } from 'lucide-vue-next'
import { contaApi, mensagemDoErro, type Seguranca } from '@/api'
import { avisar } from '@/composables/avisos'
import { useFormulario } from '@/composables/formulario'
import CabecalhoPagina from '@/components/app/CabecalhoPagina.vue'
import Alerta from '@/components/ui/Alerta.vue'
import Botao from '@/components/ui/Botao.vue'
import CampoChips from '@/components/ui/CampoChips.vue'
import Carregando from '@/components/ui/Carregando.vue'
import Selecao from '@/components/ui/Selecao.vue'
import NavConfiguracoes from './NavConfiguracoes.vue'

const OPCOES_BASE = [
  { valor: 30, rotulo: '30 minutos' },
  { valor: 60, rotulo: '1 hora' },
  { valor: 120, rotulo: '2 horas' },
  { valor: 240, rotulo: '4 horas' },
  { valor: 480, rotulo: '8 horas' },
  { valor: 1440, rotulo: '24 horas' },
]

const carregando = ref(true)
const erroCarga = ref<string | null>(null)
const original = ref<Seguranca | null>(null)
const dados = reactive<Seguranca>({ sessao_minutos: 60, dominios: [] })
const { enviando, erroGeral, erros, executar } = useFormulario()
const chips = ref<InstanceType<typeof CampoChips> | null>(null)

// Se a API devolver um tempo fora da lista, mostramos também para não perder o valor.
const opcoesTempo = computed(() => {
  const v = original.value?.sessao_minutos
  if (!v || OPCOES_BASE.some((o) => o.valor === v)) return OPCOES_BASE
  const rotulo = v % 60 === 0 ? `${v / 60} horas` : `${v} minutos`
  return [...OPCOES_BASE, { valor: v, rotulo }].sort((a, b) => a.valor - b.valor)
})

const alterado = computed(
  () =>
    !!original.value &&
    (original.value.sessao_minutos !== dados.sessao_minutos ||
      original.value.dominios.length !== dados.dominios.length ||
      original.value.dominios.some((d, i) => d !== dados.dominios[i])),
)

/** Erros por item: aceita tanto "dominios.0" quanto "dominios[0]" vindos da API. */
const errosDominios = computed(() => {
  const mapa: Record<number, string> = {}
  for (const [chave, msg] of Object.entries(erros)) {
    const m = /^dominios(?:\.|\[)(\d+)\]?$/.exec(chave)
    if (m) mapa[Number(m[1])] = msg
  }
  return mapa
})

function normalizarDominio(v: string): string {
  let d = v.trim().toLowerCase()
  d = d.replace(/^https?:\/\//, '').replace(/\/.*$/, '')
  if (d.includes('@')) d = d.slice(d.lastIndexOf('@') + 1) // colou um e-mail inteiro
  return d.replace(/^www\./, '')
}

function validarDominio(d: string): string | null {
  return /^(?=.{3,253}$)([a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,}$/.test(d)
    ? null
    : `"${d}" não parece um domínio. Use só a parte depois do @, por exemplo: suaempresa.com.br`
}

function aplicar(s: Seguranca) {
  original.value = { sessao_minutos: s.sessao_minutos, dominios: [...s.dominios] }
  dados.sessao_minutos = s.sessao_minutos
  dados.dominios = [...s.dominios]
}

async function carregar() {
  carregando.value = true
  erroCarga.value = null
  try {
    aplicar(await contaApi.seguranca())
  } catch (e) {
    erroCarga.value = mensagemDoErro(e)
  } finally {
    carregando.value = false
  }
}

async function salvar() {
  // Se ficou algo digitado no campo de domínios, adiciona antes de salvar.
  if (chips.value?.pendente() && !chips.value.adicionar()) return
  const r = await executar(() => contaApi.salvarSeguranca({ sessao_minutos: Number(dados.sessao_minutos), dominios: dados.dominios }))
  if (r) {
    aplicar(r)
    avisar.sucesso('Configurações de segurança salvas.')
  }
}

function descartar() {
  if (original.value) aplicar(original.value)
}

onMounted(carregar)
</script>

<template>
  <NavConfiguracoes />
  <CabecalhoPagina titulo="Segurança" descricao="Regras de acesso que valem para todas as pessoas da sua empresa." />

  <Carregando v-if="carregando" :linhas="3" />
  <Alerta v-else-if="erroCarga" tom="erro">
    {{ erroCarga }} <button type="button" class="link ml-1" @click="carregar">Tentar de novo</button>
  </Alerta>

  <form v-else class="flex flex-col gap-6" novalidate @submit.prevent="salvar">
    <Alerta v-if="erroGeral" tom="erro">{{ erroGeral }}</Alerta>

    <section class="cartao grid gap-6 p-5 sm:p-6 md:grid-cols-3" aria-labelledby="titulo-tempo">
      <div>
        <div class="mb-3 flex size-10 items-center justify-center rounded-xl bg-marca-suave text-marca-texto">
          <Clock class="size-5" aria-hidden="true" />
        </div>
        <h2 id="titulo-tempo" class="text-base font-bold text-texto">Tempo de sessão</h2>
        <p class="mt-1 text-sm text-texto-suave">
          Quanto tempo cada pessoa fica conectada antes de precisar entrar de novo. Tempos menores são mais seguros.
        </p>
      </div>
      <div class="md:col-span-2 md:max-w-xs">
        <Selecao v-model="dados.sessao_minutos" rotulo="Encerrar a sessão após" :opcoes="opcoesTempo" :erro="erros.sessao_minutos" />
      </div>
    </section>

    <section class="cartao grid gap-6 p-5 sm:p-6 md:grid-cols-3" aria-labelledby="titulo-dominios">
      <div>
        <div class="mb-3 flex size-10 items-center justify-center rounded-xl bg-marca-suave text-marca-texto">
          <Globe class="size-5" aria-hidden="true" />
        </div>
        <h2 id="titulo-dominios" class="text-base font-bold text-texto">Domínios liberados</h2>
        <p class="mt-1 text-sm text-texto-suave">
          Pessoas com e-mail destes domínios podem pedir acesso; você aprova em
          <RouterLink to="/equipe" class="link">Equipe</RouterLink>.
        </p>
      </div>
      <div class="md:col-span-2">
        <CampoChips
          ref="chips"
          v-model="dados.dominios"
          rotulo="Domínios de e-mail da empresa"
          placeholder="suaempresa.com.br"
          dica="Digite o domínio e aperte Enter. E-mails gratuitos (Gmail, Hotmail…) não são aceitos."
          :normalizar="normalizarDominio"
          :validar="validarDominio"
          :erro="erros.dominios"
          :erros-itens="errosDominios"
        />
        <p v-if="!dados.dominios.length" class="mt-3 text-sm text-texto-fraco">
          Nenhum domínio liberado: só entra quem você cadastrar em Equipe.
        </p>
      </div>
    </section>

    <div class="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
      <Botao v-if="alterado" variante="secundario" :desabilitado="enviando" @click="descartar">Descartar</Botao>
      <Botao tipo="submit" :carregando="enviando" :desabilitado="!alterado">Salvar alterações</Botao>
    </div>
  </form>
</template>

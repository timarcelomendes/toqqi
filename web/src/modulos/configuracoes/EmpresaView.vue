<script setup lang="ts">
// Configurações › Empresa: identificação, contato, endereço (com o CEP preenchendo o resto) e logo.
// O nome e o logo aparecem para os clientes nas pesquisas e nos e-mails.
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { onBeforeRouteLeave } from 'vue-router'
import { Building2, ImageIcon, MapPin, Phone } from 'lucide-vue-next'
import { empresaApi, mensagemDoErro, type DadosEmpresaConta } from '@/api'
import { avisar } from '@/composables/avisos'
import { confirmar } from '@/composables/confirmacao'
import { useFormulario } from '@/composables/formulario'
import { useSessaoStore } from '@/stores/sessao'
import { formatarDataHora } from '@/utils/datas'
import { apenasDigitos } from '@/utils/validacao'
import CabecalhoPagina from '@/components/app/CabecalhoPagina.vue'
import Alerta from '@/components/ui/Alerta.vue'
import Botao from '@/components/ui/Botao.vue'
import Campo from '@/components/ui/Campo.vue'
import Carregando from '@/components/ui/Carregando.vue'
import Selecao from '@/components/ui/Selecao.vue'
import LogoEmpresa from './LogoEmpresa.vue'
import NavConfiguracoes from './NavConfiguracoes.vue'
import {
  LIMITES,
  UFS,
  buscarCep,
  corpoDoForm,
  formDosDados,
  formatarCep,
  mascaraDocumento,
  mascaraTelefone,
  mesmosDados,
  preencherEndereco,
  validarEmpresa,
  type FormEmpresa,
} from './empresa'

const sessao = useSessaoStore()
const carregando = ref(true)
const erroCarga = ref<string | null>(null)
const dados = ref<DadosEmpresaConta | null>(null)
const original = ref<FormEmpresa>(formDosDados(null))
const form = reactive<FormEmpresa>(formDosDados(null))
const { enviando, erroGeral, erros, executar, limpar } = useFormulario()
const locais = reactive<Record<string, string>>({})
const raiz = ref<HTMLElement | null>(null)

const alterado = computed(() => !!dados.value && !mesmosDados(form, original.value))
const erro = (c: keyof FormEmpresa) => locais[c] ?? erros[c] ?? null
const opcoesUf = UFS.map((u) => ({ valor: u, rotulo: u }))

function aplicar(d: DadosEmpresaConta) {
  dados.value = d
  const f = formDosDados(d)
  original.value = f
  Object.assign(form, f)
}

function limparErros() {
  limpar()
  for (const k of Object.keys(locais)) delete locais[k]
}

async function carregar() {
  carregando.value = true
  erroCarga.value = null
  try {
    aplicar(await empresaApi.obter())
  } catch (e) {
    erroCarga.value = mensagemDoErro(e)
  } finally {
    carregando.value = false
  }
}

// Máscaras: o campo (`mascara`) mostra o valor formatado; para a API vão só os dígitos (e as letras do CNPJ).

// ── CEP → endereço (ViaCEP): só os campos vazios; se falhar, segue à mão sem aviso ──
const buscandoCep = ref(false)
const avisoCep = ref<string | null>(null)
let ultimoCep = ''
let controleCep: AbortController | null = null

async function aoDigitarCep(v: string) {
  form.cep = formatarCep(v)
  const cep = apenasDigitos(form.cep)
  if (cep === ultimoCep) return
  // Mudou o CEP: a busca anterior (se ainda corre) não serve mais.
  controleCep?.abort()
  controleCep = null
  buscandoCep.value = false
  avisoCep.value = null
  ultimoCep = cep.length === 8 ? cep : ''
  if (cep.length !== 8) return
  const controle = (controleCep = new AbortController())
  buscandoCep.value = true
  const endereco = await buscarCep(cep, { sinal: controle.signal })
  if (controle !== controleCep) return // o CEP mudou durante a busca
  controleCep = null
  buscandoCep.value = false
  if (endereco && preencherEndereco(form, endereco).length) avisoCep.value = 'Endereço preenchido pelo CEP. Confira e complete o número.'
}

// ── Salvar ───────────────────────────────────────────────────────────────────
async function focarPrimeiroErro() {
  await nextTick()
  raiz.value?.querySelector<HTMLElement>('[aria-invalid="true"]')?.focus()
}

async function salvar() {
  if (!dados.value || enviando.value) return
  limparErros()
  const v = validarEmpresa(form)
  if (Object.keys(v).length) {
    Object.assign(locais, v)
    erroGeral.value = 'Confira os campos destacados.'
    focarPrimeiroErro()
    return
  }
  const r = await executar(() => empresaApi.salvar(corpoDoForm(form)))
  if (!r) {
    focarPrimeiroErro()
    return
  }
  aplicar(r)
  // O nome (e o logo) no topo do app mudam na hora.
  sessao.atualizarConta({ nome: r.nome, logo_url: r.logo_url })
  avisar.sucesso('Dados da empresa salvos.')
}

function descartar() {
  controleCep?.abort()
  controleCep = null
  buscandoCep.value = false
  ultimoCep = ''
  avisoCep.value = null
  Object.assign(form, original.value)
  limparErros()
}

// O logo vale na hora (não espera o "Salvar alterações"); os campos de texto em edição ficam como estão.
function aoTrocarLogo(url: string | null, atualizadoEm: string | null) {
  if (dados.value) dados.value = { ...dados.value, logo_url: url, atualizado_em: atualizadoEm ?? dados.value.atualizado_em }
  sessao.atualizarConta({ logo_url: url })
}

// ── Sair com alterações não salvas ──────────────────────────────────────────
onBeforeRouteLeave(async () => {
  if (!alterado.value || enviando.value) return true
  return confirmar({
    titulo: 'Sair sem salvar?',
    mensagem: 'Você mudou os dados da empresa e ainda não salvou. Se sair agora, as mudanças se perdem.',
    confirmar: 'Sair sem salvar',
    cancelar: 'Continuar editando',
    perigo: true,
  })
})
function antesDeFecharAba(e: BeforeUnloadEvent) {
  if (!alterado.value) return
  e.preventDefault()
  e.returnValue = ''
}

onMounted(() => {
  carregar()
  window.addEventListener('beforeunload', antesDeFecharAba)
})
onBeforeUnmount(() => {
  window.removeEventListener('beforeunload', antesDeFecharAba)
  controleCep?.abort()
})
</script>

<template>
  <NavConfiguracoes />
  <CabecalhoPagina titulo="Empresa" descricao="Os dados da sua empresa. O nome e o logo aparecem para os seus clientes nas pesquisas e nos e-mails." />

  <Carregando v-if="carregando" :linhas="4" />
  <Alerta v-else-if="erroCarga" tom="erro">
    {{ erroCarga }} <button type="button" class="link ml-1" @click="carregar">Tentar de novo</button>
  </Alerta>

  <form v-else-if="dados" ref="raiz" class="flex flex-col gap-6" novalidate @submit.prevent="salvar">
    <Alerta v-if="erroGeral" tom="erro">{{ erroGeral }}</Alerta>

    <!-- Identificação -->
    <section class="cartao grid grid-cols-1 gap-6 p-5 sm:p-6 md:grid-cols-3" aria-labelledby="t-identificacao">
      <div>
        <div class="mb-3 flex size-10 items-center justify-center rounded-xl bg-marca-suave text-marca-texto"><Building2 class="size-5" aria-hidden="true" /></div>
        <h2 id="t-identificacao" class="text-base font-bold text-texto">Identificação</h2>
        <p class="mt-1 text-sm text-texto-suave">Como a sua empresa se apresenta para os clientes.</p>
      </div>
      <div class="flex min-w-0 flex-col gap-4 md:col-span-2">
        <Campo
          v-model="form.nome"
          rotulo="Nome da empresa"
          obrigatorio
          :maxlength="LIMITES.nome"
          autocomplete="organization"
          :erro="erro('nome')"
          dica="É assim que a empresa aparece nas pesquisas e nos e-mails (no lugar de {empresa})."
        />
        <Campo v-model="form.razao_social" rotulo="Razão social" opcional :maxlength="LIMITES.razao_social" :erro="erro('razao_social')" />
        <Campo
          v-model="form.documento"
          rotulo="CNPJ"
          opcional
          autocapitalize="characters"
          autocomplete="off"
          spellcheck="false"
          placeholder="00.000.000/0000-00"
          :mascara="mascaraDocumento"
          :erro="erro('documento')"
          dica="Também aceita CPF. O CNPJ pode ter letras (CNPJ alfanumérico)."
          class="sm:max-w-xs"
        />
      </div>
    </section>

    <!-- Contato -->
    <section class="cartao grid grid-cols-1 gap-6 p-5 sm:p-6 md:grid-cols-3" aria-labelledby="t-contato">
      <div>
        <div class="mb-3 flex size-10 items-center justify-center rounded-xl bg-marca-suave text-marca-texto"><Phone class="size-5" aria-hidden="true" /></div>
        <h2 id="t-contato" class="text-base font-bold text-texto">Contato</h2>
        <p class="mt-1 text-sm text-texto-suave">Para os clientes acharem a empresa.</p>
      </div>
      <div class="grid min-w-0 grid-cols-1 gap-4 sm:grid-cols-2 md:col-span-2">
        <Campo
          v-model="form.telefone"
          rotulo="Telefone ou WhatsApp"
          opcional
          tipo="tel"
          inputmode="tel"
          autocomplete="tel-national"
          placeholder="(11) 91234-5678"
          :mascara="mascaraTelefone"
          :erro="erro('telefone')"
        />
        <Campo
          v-model="form.email_contato"
          rotulo="E-mail"
          opcional
          tipo="email"
          autocomplete="email"
          :maxlength="LIMITES.email_contato"
          placeholder="contato@suaempresa.com.br"
          :erro="erro('email_contato')"
        />
        <Campo
          v-model="form.site"
          rotulo="Site"
          opcional
          inputmode="url"
          autocomplete="url"
          :maxlength="LIMITES.site"
          placeholder="www.suaempresa.com.br"
          spellcheck="false"
          :erro="erro('site')"
          class="sm:col-span-2"
        />
      </div>
    </section>

    <!-- Endereço -->
    <section class="cartao grid grid-cols-1 gap-6 p-5 sm:p-6 md:grid-cols-3" aria-labelledby="t-endereco">
      <div>
        <div class="mb-3 flex size-10 items-center justify-center rounded-xl bg-marca-suave text-marca-texto"><MapPin class="size-5" aria-hidden="true" /></div>
        <h2 id="t-endereco" class="text-base font-bold text-texto">Endereço</h2>
        <p class="mt-1 text-sm text-texto-suave">Comece pelo CEP: a rua, o bairro e a cidade se preenchem sozinhos.</p>
      </div>
      <div class="grid min-w-0 grid-cols-1 gap-4 sm:grid-cols-6 md:col-span-2">
        <Campo
          :model-value="form.cep"
          rotulo="CEP"
          opcional
          inputmode="numeric"
          autocomplete="postal-code"
          placeholder="00000-000"
          :mascara="formatarCep"
          :erro="erro('cep')"
          class="sm:col-span-3"
          @update:model-value="aoDigitarCep"
        >
          <template v-if="buscandoCep || avisoCep" #dica>{{ buscandoCep ? 'Buscando o endereço…' : avisoCep }}</template>
        </Campo>
        <!-- Sempre na página, para o leitor de tela anunciar quando o endereço chega. -->
        <p class="sr-only" aria-live="polite">{{ avisoCep }}</p>
        <div class="hidden sm:col-span-3 sm:block" aria-hidden="true" />
        <Campo
          v-model="form.logradouro"
          rotulo="Logradouro"
          opcional
          autocomplete="address-line1"
          :maxlength="LIMITES.logradouro"
          placeholder="Rua, avenida…"
          :erro="erro('logradouro')"
          class="sm:col-span-4"
        />
        <Campo v-model="form.numero" rotulo="Número" opcional :maxlength="LIMITES.numero" :erro="erro('numero')" class="sm:col-span-2" />
        <Campo
          v-model="form.complemento"
          rotulo="Complemento"
          opcional
          autocomplete="address-line2"
          :maxlength="LIMITES.complemento"
          placeholder="Sala, andar…"
          :erro="erro('complemento')"
          class="sm:col-span-3"
        />
        <Campo v-model="form.bairro" rotulo="Bairro" opcional :maxlength="LIMITES.bairro" :erro="erro('bairro')" class="sm:col-span-3" />
        <Campo
          v-model="form.cidade"
          rotulo="Cidade"
          opcional
          autocomplete="address-level2"
          :maxlength="LIMITES.cidade"
          :erro="erro('cidade')"
          class="sm:col-span-4"
        />
        <Selecao v-model="form.uf" rotulo="UF" :opcoes="opcoesUf" vazio="Escolha" :erro="erro('uf')" class="sm:col-span-2" />
      </div>
    </section>

    <!-- Logo (vale na hora, não depende do "Salvar alterações") -->
    <section class="cartao grid grid-cols-1 gap-6 p-5 sm:p-6 md:grid-cols-3" aria-labelledby="t-logo">
      <div>
        <div class="mb-3 flex size-10 items-center justify-center rounded-xl bg-marca-suave text-marca-texto"><ImageIcon class="size-5" aria-hidden="true" /></div>
        <h2 id="t-logo" class="text-base font-bold text-texto">Logo</h2>
        <p class="mt-1 text-sm text-texto-suave">Aparece no topo das pesquisas e dos e-mails quando o formulário não tem logo próprio. Enviar ou remover vale na hora.</p>
      </div>
      <div class="min-w-0 md:col-span-2">
        <LogoEmpresa :logo-url="dados.logo_url" :nome="original.nome || 'sua empresa'" @trocado="aoTrocarLogo" />
      </div>
    </section>

    <p v-if="dados.atualizado_em" class="text-sm text-texto-fraco">Última alteração em {{ formatarDataHora(dados.atualizado_em) }}.</p>

    <div class="sticky bottom-0 z-10 -mx-4 flex flex-col-reverse gap-2 border-t border-borda bg-fundo/90 px-4 py-3 backdrop-blur sm:-mx-6 sm:flex-row sm:justify-end sm:px-6 lg:-mx-10 lg:px-10">
      <p v-if="alterado" class="text-sm text-texto-fraco sm:mr-auto sm:self-center">Você tem alterações não salvas.</p>
      <Botao v-if="alterado" variante="secundario" :desabilitado="enviando" @click="descartar">Descartar</Botao>
      <Botao tipo="submit" :carregando="enviando" :desabilitado="!alterado">Salvar alterações</Botao>
    </div>
  </form>
</template>

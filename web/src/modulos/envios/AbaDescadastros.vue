<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { Search, UserX } from 'lucide-vue-next'
import { enviosApi, mensagemDoErro, type Descadastro } from '@/api'
import { useSessaoStore } from '@/stores/sessao'
import { formatarDataHora } from '@/utils/datas'
import Alerta from '@/components/ui/Alerta.vue'
import Botao from '@/components/ui/Botao.vue'
import Campo from '@/components/ui/Campo.vue'
import EstadoVazio from '@/components/ui/EstadoVazio.vue'
import Paginacao from '@/components/ui/Paginacao.vue'
import Tabela, { type Coluna } from '@/components/ui/Tabela.vue'
import ModalDescadastro from './ModalDescadastro.vue'
import { ORIGENS_DESCADASTRO, rotuloDe } from './logica'

const sessao = useSessaoStore()
const linhas = ref<Descadastro[]>([])
const total = ref(0)
const porPagina = ref(50)
const pagina = ref(1)
const carregando = ref(true)
const erro = ref<string | null>(null)
const busca = ref('')
const modalAberto = ref(false)

const colunas: Coluna[] = [
  { chave: 'email', rotulo: 'E-mail' },
  { chave: 'motivo', rotulo: 'Motivo', classe: 'hidden md:table-cell' },
  { chave: 'origem', rotulo: 'Como saiu', classe: 'hidden lg:table-cell' },
  { chave: 'criado_em', rotulo: 'Quando', classe: 'hidden sm:table-cell' },
]

let controle: AbortController | null = null
async function carregar() {
  controle?.abort()
  controle = new AbortController()
  carregando.value = true
  erro.value = null
  try {
    const r = await enviosApi.descadastros({ busca: busca.value.trim(), pagina: pagina.value }, controle.signal)
    linhas.value = r.itens
    total.value = r.total
    porPagina.value = r.por_pagina || 50
  } catch (e) {
    if (e instanceof DOMException) return
    erro.value = mensagemDoErro(e)
  } finally {
    carregando.value = false
  }
}

let atraso: ReturnType<typeof setTimeout> | null = null
watch(busca, () => {
  if (atraso) clearTimeout(atraso)
  atraso = setTimeout(() => {
    pagina.value = 1
    carregar()
  }, 300)
})
watch(pagina, carregar)
onMounted(carregar)
onBeforeUnmount(() => {
  controle?.abort()
  if (atraso) clearTimeout(atraso)
})
</script>

<template>
  <div class="flex flex-col gap-4">
    <Alerta tom="info" titulo="Quem sai da lista não recebe mais nenhuma pesquisa da sua empresa">
      Nem por e-mail, nem pelo WhatsApp, mesmo que o contato seja importado de novo. Só a própria pessoa pode voltar a receber,
      pelo link "Não quero mais receber pesquisas" de um e-mail que recebeu.
    </Alerta>

    <div class="cartao">
      <div class="flex flex-col gap-3 border-b border-borda p-4 sm:flex-row sm:items-center sm:px-5">
        <Campo v-model="busca" rotulo="Buscar descadastros" rotulo-oculto tipo="search" placeholder="Buscar por e-mail ou nome" class="sm:max-w-sm sm:flex-1">
          <template #antes><Search class="size-4" aria-hidden="true" /></template>
        </Campo>
        <Botao v-if="sessao.pode('contatos.editar')" variante="secundario" class="sm:ml-auto" @click="modalAberto = true">
          <UserX class="size-4" aria-hidden="true" /> Registrar descadastro
        </Botao>
      </div>

      <Alerta v-if="erro" tom="erro" class="m-4">
        {{ erro }} <button type="button" class="link ml-1" @click="carregar">Tentar de novo</button>
      </Alerta>
      <Tabela v-else :colunas="colunas" :linhas="linhas" :chave="(d) => `${d.email}-${d.criado_em}`" :carregando="carregando" legenda="Pessoas que saíram da lista">
        <template #cel-email="{ linha: d }">
          <div class="min-w-0">
            <p class="break-all font-semibold text-texto">{{ d.email }}</p>
            <RouterLink v-if="d.contato" :to="`/contatos/${d.contato.id}`" class="text-sm text-texto-suave hover:underline">{{ d.contato.nome }}</RouterLink>
            <p v-if="d.motivo" class="mt-0.5 text-xs text-texto-fraco md:hidden">"{{ d.motivo }}"</p>
            <p class="text-xs text-texto-fraco sm:hidden">{{ formatarDataHora(d.criado_em) }}</p>
          </div>
        </template>
        <template #cel-motivo="{ linha: d }">
          <span :class="d.motivo ? 'text-texto-suave' : 'text-texto-fraco'">{{ d.motivo || 'Não informou' }}</span>
        </template>
        <template #cel-origem="{ linha: d }">
          <span class="text-texto-suave">{{ rotuloDe(ORIGENS_DESCADASTRO, d.origem) }}</span>
        </template>
        <template #cel-criado_em="{ linha: d }">
          <span class="whitespace-nowrap text-texto-suave">{{ formatarDataHora(d.criado_em) }}</span>
        </template>
        <template #vazio>
          <EstadoVazio v-if="busca" :icone="Search" titulo="Ninguém encontrado" descricao="Tente outra busca." />
          <EstadoVazio v-else :icone="UserX" titulo="Ninguém saiu da lista" descricao="Quando alguém pedir para não receber mais pesquisas, aparece aqui." />
        </template>
      </Tabela>
      <Paginacao v-if="!erro" v-model="pagina" :total="total" :por-pagina="porPagina" :carregando="carregando" :nome-itens="total === 1 ? 'pessoa' : 'pessoas'" />
    </div>

    <ModalDescadastro v-model:aberto="modalAberto" @registrado="carregar" />
  </div>
</template>

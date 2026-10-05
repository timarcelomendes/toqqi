<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { Building2, Download, History, MoreHorizontal, Pencil, RotateCcw, Search, Trash2, UserX } from 'lucide-vue-next'
import { empresasApi, exportacaoListasApi, mensagemDoErro, type Empresa, type Id } from '@/api'
import { avisar } from '@/composables/avisos'
import { confirmar } from '@/composables/confirmacao'
import { useCadastrosStore } from '@/stores/cadastros'
import { useSessaoStore } from '@/stores/sessao'
import { formatarData } from '@/utils/datas'
import { formatarDocumento, formatarMoeda, formatarNumero } from '@/utils/formatos'
import ItemMenu from '@/components/app/ItemMenu.vue'
import Alerta from '@/components/ui/Alerta.vue'
import Botao from '@/components/ui/Botao.vue'
import Campo from '@/components/ui/Campo.vue'
import EstadoVazio from '@/components/ui/EstadoVazio.vue'
import Etiqueta from '@/components/ui/Etiqueta.vue'
import MenuSuspenso from '@/components/ui/MenuSuspenso.vue'
import Paginacao from '@/components/ui/Paginacao.vue'
import Selecao from '@/components/ui/Selecao.vue'
import Tabela, { type Coluna } from '@/components/ui/Tabela.vue'
import ModalDesfecho from './ModalDesfecho.vue'
import ModalEmpresa from './ModalEmpresa.vue'
import { seloSituacao, situacaoEmpresa } from './desfecho'
import { consultaEmpresas, type FiltrosEmpresasTela } from './exportacao'

const sessao = useSessaoStore()
const cadastros = useCadastrosStore()
const empresas = ref<Empresa[]>([])
const total = ref(0)
const porPagina = ref(50)
const pagina = ref(1)
const carregando = ref(true)
const erro = ref<string | null>(null)
const ocupado = ref<Id | null>(null)
const filtros = reactive<FiltrosEmpresasTela>({
  busca: '',
  grupo_id: '',
  segmento_id: '',
  responsavel_id: '',
  ativa: 'true',
})
const modalAberto = ref(false)
const emEdicao = ref<Empresa | null>(null)

const podeEditar = computed(() => sessao.pode('contatos.editar'))
// A API exige contatos.excluir E perfil admin para excluir empresa.
const podeExcluir = computed(() => sessao.pode('contatos.excluir') && sessao.usuario?.perfil === 'admin')
// Etapa 4b: atalho para o histórico da empresa em Relatórios.
const podeVerHistorico = computed(() => sessao.pode('relatorios.ver'))
// Etapa 5f: "Exportar CSV" com os filtros da aba (como os outros CSV, pede também painel.exportar).
const podeExportar = computed(() => sessao.pode('contatos.ver') && sessao.pode('painel.exportar'))
const baixando = ref(false)

async function exportar() {
  if (baixando.value) return
  baixando.value = true
  try {
    await exportacaoListasApi.baixarEmpresas(consultaEmpresas(filtros))
  } catch (e) {
    avisar.erro(mensagemDoErro(e))
  } finally {
    baixando.value = false
  }
}

const colunas: Coluna[] = [
  { chave: 'nome', rotulo: 'Empresa' },
  { chave: 'grupo', rotulo: 'Grupo e segmento', classe: 'hidden lg:table-cell' },
  { chave: 'responsavel', rotulo: 'Responsável', classe: 'hidden md:table-cell' },
  { chave: 'valor_mensal', rotulo: 'Valor mensal', alinhar: 'direita', classe: 'hidden xl:table-cell' },
  { chave: 'cliente_desde', rotulo: 'Cliente desde', classe: 'hidden xl:table-cell' },
  { chave: 'contatos', rotulo: 'Contatos', alinhar: 'centro', classe: 'hidden sm:table-cell' },
  { chave: 'ativa', rotulo: 'Situação', classe: 'hidden md:table-cell' },
  { chave: 'acoes', rotulo: 'Ações', rotuloOculto: true, alinhar: 'direita' },
]
const opcoesAtiva = [
  { valor: 'true' as const, rotulo: 'Ativas' },
  { valor: 'false' as const, rotulo: 'Inativas' },
  { valor: 'todas' as const, rotulo: 'Todas' },
]

let controle: AbortController | null = null
async function carregar() {
  controle?.abort()
  controle = new AbortController()
  carregando.value = true
  erro.value = null
  try {
    const r = await empresasApi.listar({ ...consultaEmpresas(filtros), pagina: pagina.value }, controle.signal)
    empresas.value = r.itens
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
watch(
  () => filtros.busca,
  () => {
    if (atraso) clearTimeout(atraso)
    atraso = setTimeout(() => {
      pagina.value = 1
      carregar()
    }, 300)
  },
)
watch(
  () => [filtros.grupo_id, filtros.segmento_id, filtros.responsavel_id, filtros.ativa],
  () => {
    pagina.value = 1
    carregar()
  },
)
watch(pagina, carregar)

function novo() {
  emEdicao.value = null
  modalAberto.value = true
}
function editar(e: Empresa) {
  emEdicao.value = e
  modalAberto.value = true
}
// Etapa 5i: desfecho ("Marcar como perdida" / "Voltou a ser cliente").
const desfecho = reactive<{ aberto: boolean; modo: 'perda' | 'retorno'; empresa: Empresa | null }>({ aberto: false, modo: 'perda', empresa: null })
function abrirDesfecho(e: Empresa, modo: 'perda' | 'retorno') {
  Object.assign(desfecho, { aberto: true, modo, empresa: e })
}
function aoSalvar(e: Empresa) {
  const i = empresas.value.findIndex((x) => String(x.id) === String(e.id))
  if (i >= 0) empresas.value.splice(i, 1, e)
  else {
    empresas.value.unshift(e)
    total.value++
  }
}

async function excluir(e: Empresa) {
  const ok = await confirmar({
    titulo: `Excluir ${e.nome}?`,
    mensagem:
      e.contatos > 0
        ? `Os ${formatarNumero(e.contatos)} contatos desta empresa continuam cadastrados, só que sem empresa. As respostas deles também continuam. Não dá para desfazer.`
        : 'A empresa sai da lista. Não dá para desfazer.',
    confirmar: 'Excluir empresa',
    perigo: true,
  })
  if (!ok) return
  ocupado.value = e.id
  try {
    await empresasApi.excluir(e.id)
    empresas.value = empresas.value.filter((x) => String(x.id) !== String(e.id))
    total.value = Math.max(0, total.value - 1)
    avisar.sucesso(`${e.nome} foi excluída.`)
  } catch (err) {
    avisar.erro(mensagemDoErro(err))
  } finally {
    ocupado.value = null
  }
}

onMounted(() => {
  carregar()
  cadastros.garantir(['grupos', 'segmentos', 'responsaveis'])
})
onBeforeUnmount(() => {
  controle?.abort()
  if (atraso) clearTimeout(atraso)
})
defineExpose({ novo })
</script>

<template>
  <div class="cartao">
    <div class="flex flex-col gap-3 border-b border-borda p-4 sm:px-5">
      <div class="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
        <Campo v-model="filtros.busca" rotulo="Buscar empresas" rotulo-oculto tipo="search" placeholder="Buscar por nome, CNPJ ou código" class="sm:col-span-2">
          <template #antes><Search class="size-4" aria-hidden="true" /></template>
        </Campo>
        <Selecao v-model="filtros.grupo_id" rotulo="Grupo" rotulo-oculto :opcoes="cadastros.listas.grupos.map((g) => ({ valor: g.id, rotulo: g.nome }))" vazio="Todos os grupos" />
        <Selecao v-model="filtros.segmento_id" rotulo="Segmento" rotulo-oculto :opcoes="cadastros.listas.segmentos.map((g) => ({ valor: g.id, rotulo: g.nome }))" vazio="Todos os segmentos" />
        <Selecao v-model="filtros.responsavel_id" rotulo="Responsável" rotulo-oculto :opcoes="cadastros.listas.responsaveis.map((r) => ({ valor: r.id, rotulo: r.nome }))" vazio="Todos os responsáveis" />
      </div>
      <div class="flex items-center justify-between gap-2">
        <div class="inline-flex w-fit rounded-xl border border-borda-forte p-0.5" role="radiogroup" aria-label="Mostrar empresas">
          <button
            v-for="o in opcoesAtiva"
            :key="o.valor"
            type="button"
            role="radio"
            :aria-checked="filtros.ativa === o.valor"
            class="h-9 rounded-[0.6rem] px-3 text-sm font-semibold transition-colors"
            :class="filtros.ativa === o.valor ? 'bg-marca-suave text-marca-texto' : 'text-texto-fraco hover:text-texto'"
            @click="filtros.ativa = o.valor"
          >
            {{ o.rotulo }}
          </button>
        </div>
        <!-- No celular, só o ícone (o nome fica no aria-label, igual ao texto que aparece nas telas maiores). -->
        <Botao
          v-if="podeExportar"
          variante="secundario"
          aria-label="Exportar CSV"
          :carregando="baixando"
          focavel
          data-exportar-csv
          @click="exportar"
        >
          <Download v-if="!baixando" class="size-4" aria-hidden="true" />
          <span class="hidden sm:inline">Exportar CSV</span>
        </Botao>
      </div>
    </div>

    <Alerta v-if="erro" tom="erro" class="m-4">
      {{ erro }} <button type="button" class="link ml-1" @click="carregar">Tentar de novo</button>
    </Alerta>

    <Tabela v-else :colunas="colunas" :linhas="empresas" :chave="(e) => e.id" :carregando="carregando" legenda="Empresas">
      <template #cel-nome="{ linha: e }">
        <p class="font-semibold text-texto">{{ e.nome }}</p>
        <p v-if="e.documento" class="text-xs text-texto-fraco">{{ formatarDocumento(e.documento) }}</p>
        <p v-if="e.responsavel" class="text-xs text-texto-suave md:hidden">{{ e.responsavel.nome }}</p>
      </template>
      <template #cel-grupo="{ linha: e }">
        <p class="text-texto-suave">{{ e.grupo?.nome ?? '—' }}</p>
        <p v-if="e.segmento" class="text-xs text-texto-fraco">{{ e.segmento.nome }}</p>
      </template>
      <template #cel-responsavel="{ linha: e }">
        <span class="text-texto-suave">{{ e.responsavel?.nome ?? '—' }}</span>
      </template>
      <template #cel-valor_mensal="{ linha: e }">
        <span class="whitespace-nowrap tabular-nums text-texto-suave">{{ formatarMoeda(e.valor_mensal) }}</span>
      </template>
      <template #cel-cliente_desde="{ linha: e }">
        <span class="text-texto-suave">{{ formatarData(e.cliente_desde) }}</span>
      </template>
      <template #cel-contatos="{ linha: e }">
        <span class="tabular-nums text-texto-suave">{{ formatarNumero(e.contatos) }}</span>
      </template>
      <template #cel-ativa="{ linha: e }">
        <Etiqueta :tom="seloSituacao(e).tom" ponto>{{ seloSituacao(e).texto }}</Etiqueta>
      </template>
      <template #cel-acoes="{ linha: e }">
        <MenuSuspenso v-if="podeEditar || podeExcluir || podeVerHistorico" :rotulo="`Ações para ${e.nome}`" fixo>
          <template #gatilho="{ props }">
            <button v-bind="props" type="button" class="flex size-9 items-center justify-center rounded-lg text-texto-fraco hover:bg-superficie-2 hover:text-texto disabled:opacity-50" :disabled="ocupado === e.id">
              <MoreHorizontal class="size-5" aria-hidden="true" />
            </button>
          </template>
          <ItemMenu v-if="podeVerHistorico" :icone="History" :para="{ path: '/relatorios/historico', query: { empresa_id: String(e.id) } }">Ver histórico</ItemMenu>
          <ItemMenu v-if="podeEditar" :icone="Pencil" @click="editar(e)">Editar</ItemMenu>
          <ItemMenu v-if="podeEditar && situacaoEmpresa(e) === 'perdida'" :icone="RotateCcw" @click="abrirDesfecho(e, 'retorno')">Voltou a ser cliente</ItemMenu>
          <ItemMenu v-else-if="podeEditar" :icone="UserX" @click="abrirDesfecho(e, 'perda')">Marcar como perdida</ItemMenu>
          <ItemMenu v-if="podeExcluir" :icone="Trash2" perigo @click="excluir(e)">Excluir</ItemMenu>
        </MenuSuspenso>
      </template>
      <template #vazio>
        <EstadoVazio v-if="filtros.busca || filtros.grupo_id || filtros.segmento_id || filtros.responsavel_id" :icone="Search" titulo="Nenhuma empresa encontrada" descricao="Tente outra busca ou mude os filtros." />
        <EstadoVazio v-else :icone="Building2" titulo="Nenhuma empresa ainda" descricao="Empresas agrupam seus contatos e ajudam a ver a satisfação por cliente.">
          <Botao v-if="podeEditar" @click="novo">Nova empresa</Botao>
        </EstadoVazio>
      </template>
    </Tabela>
    <Paginacao v-if="!erro" v-model="pagina" :total="total" :por-pagina="porPagina" :carregando="carregando" :nome-itens="total === 1 ? 'empresa' : 'empresas'" />
    <ModalEmpresa v-model:aberto="modalAberto" :empresa="emEdicao" @salvo="aoSalvar" />
    <ModalDesfecho v-model:aberto="desfecho.aberto" :empresa="desfecho.empresa" :modo="desfecho.modo" @salvo="aoSalvar" />
  </div>
</template>

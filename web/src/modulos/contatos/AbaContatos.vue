<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { Download, Eye, Link2, MessageCircle, MoreHorizontal, Pencil, Search, SlidersHorizontal, Trash2, Upload, UserPlus, UsersRound } from 'lucide-vue-next'
import { contatosApi, exportacaoListasApi, mensagemDoErro, type Contato, type Id } from '@/api'
import { avisar } from '@/composables/avisos'
import { confirmar } from '@/composables/confirmacao'
import { useWhatsapp } from '@/composables/whatsapp'
import { useCadastrosStore } from '@/stores/cadastros'
import { useSessaoStore } from '@/stores/sessao'
import { exibirTelefone } from '@/utils/formatos'
import { iniciais, situacaoContato, tomNotaNps } from '@/utils/rotulos'
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
import CampoEmpresa from './CampoEmpresa.vue'
import ModalContato from './ModalContato.vue'
import ModalLinkPesquisa from './ModalLinkPesquisa.vue'
import { consultaContatos, type FiltrosContatosTela } from './exportacao'

const sessao = useSessaoStore()
const cadastros = useCadastrosStore()
const router = useRouter()

const contatos = ref<Contato[]>([])
const total = ref(0)
const porPagina = ref(50)
const pagina = ref(1)
const carregando = ref(true)
const erro = ref<string | null>(null)
const ocupado = ref<Id | null>(null)
const filtrosAbertos = ref(false)

const filtros = reactive<FiltrosContatosTela>({
  busca: '',
  empresa: null,
  grupo_id: '',
  responsavel_id: '',
  perfil_id: '',
  ativo: 'true',
})

const modalAberto = ref(false)
const emEdicao = ref<Contato | null>(null)
const linkAberto = ref(false)
const paraLink = ref<Contato | null>(null)

const podeEditar = computed(() => sessao.pode('contatos.editar'))
const podeExcluir = computed(() => sessao.pode('contatos.excluir'))
const podeLink = computed(() => sessao.pode('envios.disparar'))
// Etapa 5f: "Exportar CSV" com os filtros da aba (como os outros CSV, pede também painel.exportar).
const podeExportar = computed(() => sessao.pode('contatos.ver') && sessao.pode('painel.exportar'))
const baixando = ref(false)

async function exportar() {
  if (baixando.value) return
  baixando.value = true
  try {
    await exportacaoListasApi.baixarContatos(consultaContatos(filtros))
  } catch (e) {
    avisar.erro(mensagemDoErro(e))
  } finally {
    baixando.value = false
  }
}
const whatsapp = useWhatsapp()
const podeWhatsapp = (c: Contato) => podeLink.value && c.ativo && !!c.telefone && c.situacao !== 'saiu_da_lista'

async function abrirWhatsapp(c: Contato) {
  if (await whatsapp.abrir(c)) carregar()
}

const colunas: Coluna[] = [
  { chave: 'nome', rotulo: 'Contato' },
  { chave: 'empresa', rotulo: 'Empresa', classe: 'hidden md:table-cell' },
  { chave: 'perfil', rotulo: 'Perfil', classe: 'hidden xl:table-cell' },
  { chave: 'situacao', rotulo: 'Situação', classe: 'hidden lg:table-cell' },
  { chave: 'ultima_nota', rotulo: 'Última nota', alinhar: 'centro', classe: 'hidden sm:table-cell' },
  { chave: 'acoes', rotulo: 'Ações', rotuloOculto: true, alinhar: 'direita' },
]

const filtrosAtivos = computed(
  () => [filtros.empresa, filtros.grupo_id, filtros.responsavel_id, filtros.perfil_id].filter((v) => v !== null && v !== '').length + (filtros.ativo !== 'true' ? 1 : 0),
)
const opcoesSituacao = [
  { valor: 'true' as const, rotulo: 'Ativos' },
  { valor: 'false' as const, rotulo: 'Inativos' },
  { valor: 'todos' as const, rotulo: 'Todos' },
]

let controle: AbortController | null = null
async function carregar() {
  controle?.abort()
  controle = new AbortController()
  carregando.value = true
  erro.value = null
  try {
    const r = await contatosApi.listar({ ...consultaContatos(filtros), pagina: pagina.value }, controle.signal)
    contatos.value = r.itens
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
  () => [filtros.empresa?.id, filtros.grupo_id, filtros.responsavel_id, filtros.perfil_id, filtros.ativo],
  () => {
    pagina.value = 1
    carregar()
  },
)
watch(pagina, carregar)

function limparFiltros() {
  Object.assign(filtros, { empresa: null, grupo_id: '', responsavel_id: '', perfil_id: '', ativo: 'true' })
}

function novo() {
  emEdicao.value = null
  modalAberto.value = true
}
function editar(c: Contato) {
  emEdicao.value = c
  modalAberto.value = true
}
function gerarLink(c: Contato) {
  paraLink.value = c
  linkAberto.value = true
}

function aoSalvar(c: Contato) {
  const i = contatos.value.findIndex((x) => String(x.id) === String(c.id))
  if (i >= 0) contatos.value.splice(i, 1, c)
  else {
    contatos.value.unshift(c)
    total.value++
  }
}

async function excluir(c: Contato) {
  const ok = await confirmar({
    titulo: `Excluir ${c.nome}?`,
    mensagem: 'O contato sai da lista e as respostas dele também são apagadas. Não dá para desfazer. Se só quer parar de enviar pesquisas, é melhor desativar.',
    confirmar: 'Excluir contato',
    perigo: true,
  })
  if (!ok) return
  ocupado.value = c.id
  try {
    await contatosApi.excluir(c.id)
    contatos.value = contatos.value.filter((x) => String(x.id) !== String(c.id))
    total.value = Math.max(0, total.value - 1)
    avisar.sucesso(`${c.nome} foi excluído(a).`)
  } catch (e) {
    avisar.erro(mensagemDoErro(e))
  } finally {
    ocupado.value = null
  }
}

onMounted(() => {
  carregar()
  cadastros.garantir(['grupos', 'perfis', 'responsaveis'])
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
      <!--
        No celular: a busca e o "Exportar CSV" (só o ícone) na primeira linha; Ativos/Inativos/Todos e "Filtros" na de
        baixo ("Filtros" desce mais uma quando não cabe, sem vazar do cartão). Da tela pequena (sm) para cima, tudo numa
        linha, na ordem do código (a mesma do teclado): busca, situação, "Filtros" e "Exportar CSV".
      -->
      <div class="flex flex-wrap items-center gap-x-2 gap-y-3 sm:flex-nowrap">
        <Campo
          v-model="filtros.busca"
          rotulo="Buscar contatos"
          rotulo-oculto
          tipo="search"
          placeholder="Buscar por nome, e-mail, telefone ou código"
          class="min-w-0 flex-1 sm:mr-1 sm:max-w-md"
        >
          <template #antes><Search class="size-4" aria-hidden="true" /></template>
        </Campo>
        <div class="order-last flex w-full flex-wrap items-center gap-2 sm:order-none sm:ml-auto sm:w-auto sm:flex-nowrap">
          <div class="inline-flex rounded-xl border border-borda-forte p-0.5" role="radiogroup" aria-label="Mostrar contatos">
            <button
              v-for="o in opcoesSituacao"
              :key="o.valor"
              type="button"
              role="radio"
              :aria-checked="filtros.ativo === o.valor"
              class="h-9 rounded-[0.6rem] px-3 text-sm font-semibold transition-colors"
              :class="filtros.ativo === o.valor ? 'bg-marca-suave text-marca-texto' : 'text-texto-fraco hover:text-texto'"
              @click="filtros.ativo = o.valor"
            >
              {{ o.rotulo }}
            </button>
          </div>
          <Botao variante="secundario" :aria-expanded="filtrosAbertos" aria-controls="filtros-contatos" @click="filtrosAbertos = !filtrosAbertos">
            <SlidersHorizontal class="size-4" aria-hidden="true" /> Filtros
            <span v-if="filtrosAtivos" class="rounded-full bg-marca-forte px-1.5 text-xs text-white">{{ filtrosAtivos }}</span>
          </Botao>
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
      <div v-show="filtrosAbertos" id="filtros-contatos" class="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <CampoEmpresa v-model="filtros.empresa" rotulo="Empresa" placeholder="Todas" />
        <Selecao v-model="filtros.grupo_id" rotulo="Grupo" :opcoes="cadastros.listas.grupos.map((g) => ({ valor: g.id, rotulo: g.nome }))" vazio="Todos" />
        <Selecao v-model="filtros.responsavel_id" rotulo="Responsável" :opcoes="cadastros.listas.responsaveis.map((r) => ({ valor: r.id, rotulo: r.nome }))" vazio="Todos" />
        <Selecao v-model="filtros.perfil_id" rotulo="Perfil" :opcoes="cadastros.listas.perfis.map((p) => ({ valor: p.id, rotulo: p.nome }))" vazio="Todos" />
        <div v-if="filtrosAtivos" class="sm:col-span-2 lg:col-span-4">
          <Botao variante="fantasma" tamanho="sm" @click="limparFiltros">Limpar filtros</Botao>
        </div>
      </div>
    </div>

    <Alerta v-if="erro" tom="erro" class="m-4">
      {{ erro }} <button type="button" class="link ml-1" @click="carregar">Tentar de novo</button>
    </Alerta>

    <Tabela v-else :colunas="colunas" :linhas="contatos" :chave="(c) => c.id" :carregando="carregando" legenda="Contatos">
      <template #cel-nome="{ linha: c }">
        <div class="flex items-center gap-3">
          <span class="flex size-9 shrink-0 items-center justify-center rounded-full bg-superficie-2 text-xs font-bold text-texto-suave" aria-hidden="true">{{ iniciais(c.nome) }}</span>
          <div class="min-w-0">
            <RouterLink :to="`/contatos/${c.id}`" class="block truncate font-semibold text-texto hover:underline">{{ c.nome }}</RouterLink>
            <p class="truncate text-texto-fraco">{{ c.email || exibirTelefone(c.telefone) || '—' }}</p>
            <p v-if="c.email && c.telefone" class="truncate text-xs text-texto-fraco">{{ exibirTelefone(c.telefone) }}</p>
            <p v-if="c.empresa" class="truncate text-xs text-texto-suave md:hidden">{{ c.empresa.nome }}</p>
            <div class="mt-1 flex flex-wrap gap-1.5 lg:hidden">
              <Etiqueta :tom="situacaoContato(c.situacao, c).tom" ponto>{{ situacaoContato(c.situacao, c).rotulo }}</Etiqueta>
            </div>
          </div>
        </div>
      </template>
      <template #cel-empresa="{ linha: c }">
        <span class="text-texto-suave">{{ c.empresa?.nome ?? '—' }}</span>
      </template>
      <template #cel-perfil="{ linha: c }">
        <span class="text-texto-suave">{{ c.perfil?.nome ?? '—' }}</span>
      </template>
      <template #cel-situacao="{ linha: c }">
        <Etiqueta :tom="situacaoContato(c.situacao, c).tom" ponto>{{ situacaoContato(c.situacao, c).rotulo }}</Etiqueta>
      </template>
      <template #cel-ultima_nota="{ linha: c }">
        <Etiqueta v-if="c.ultima_nota !== null && c.ultima_nota !== undefined" :tom="tomNotaNps(c.ultima_nota)">
          <span class="sr-only">Nota </span>{{ c.ultima_nota }}
        </Etiqueta>
        <span v-else class="text-texto-fraco" aria-label="Sem nota">—</span>
      </template>
      <template #cel-acoes="{ linha: c }">
        <MenuSuspenso :rotulo="`Ações para ${c.nome}`" fixo>
          <template #gatilho="{ props }">
            <button
              v-bind="props"
              type="button"
              class="flex size-9 items-center justify-center rounded-lg text-texto-fraco hover:bg-superficie-2 hover:text-texto disabled:opacity-50"
              :disabled="ocupado === c.id"
            >
              <MoreHorizontal class="size-5" aria-hidden="true" />
            </button>
          </template>
          <ItemMenu :icone="Eye" :para="`/contatos/${c.id}`">Ver detalhes</ItemMenu>
          <ItemMenu v-if="podeEditar" :icone="Pencil" @click="editar(c)">Editar</ItemMenu>
          <ItemMenu v-if="podeWhatsapp(c)" :icone="MessageCircle" @click="abrirWhatsapp(c)">Enviar pelo WhatsApp</ItemMenu>
          <ItemMenu v-if="podeLink && c.ativo" :icone="Link2" @click="gerarLink(c)">Gerar link de pesquisa</ItemMenu>
          <ItemMenu v-if="podeExcluir" :icone="Trash2" perigo @click="excluir(c)">Excluir</ItemMenu>
        </MenuSuspenso>
      </template>
      <template #vazio>
        <EstadoVazio v-if="filtros.busca || filtrosAtivos" :icone="Search" titulo="Nenhum contato encontrado" descricao="Tente outra busca ou limpe os filtros.">
          <Botao variante="secundario" @click="() => { filtros.busca = ''; limparFiltros() }">Limpar busca e filtros</Botao>
        </EstadoVazio>
        <EstadoVazio v-else :icone="UsersRound" titulo="Seus clientes vão aparecer aqui" descricao="Cadastre um por um ou traga todos de uma vez com uma planilha.">
          <div class="flex flex-wrap justify-center gap-2">
            <Botao v-if="sessao.pode('importacao.usar')" @click="router.push('/contatos/importar')"><Upload class="size-4" aria-hidden="true" /> Importar planilha</Botao>
            <Botao v-if="podeEditar" variante="secundario" @click="novo"><UserPlus class="size-4" aria-hidden="true" /> Novo contato</Botao>
          </div>
        </EstadoVazio>
      </template>
    </Tabela>
    <Paginacao v-if="!erro" v-model="pagina" :total="total" :por-pagina="porPagina" :carregando="carregando" :nome-itens="total === 1 ? 'contato' : 'contatos'" />

    <ModalContato v-model:aberto="modalAberto" :contato="emEdicao" @salvo="aoSalvar" />
    <ModalLinkPesquisa v-model:aberto="linkAberto" :contato="paraLink" />
  </div>
</template>

<script setup lang="ts">
// Etapa 5i: a tela da empresa — dados, saúde, contatos e a linha do tempo (entrada, valor, perda e retorno).
import { computed, onMounted, ref, watch } from 'vue'
import { RouterLink, useRoute } from 'vue-router'
import { ArrowLeft, Building2, History, Pencil, RotateCcw, UserX, Users } from 'lucide-vue-next'
import {
  ApiError,
  contatosApi,
  empresasApi,
  mensagemDoErro,
  saudeApi,
  type Contato,
  type Empresa,
  type MarcoEmpresa,
  type SaudeEmpresa,
} from '@/api'
import { useSessaoStore } from '@/stores/sessao'
import { formatarData } from '@/utils/datas'
import { formatarDocumento, formatarMoeda } from '@/utils/formatos'
import { situacaoContato } from '@/utils/rotulos'
import Alerta from '@/components/ui/Alerta.vue'
import Botao from '@/components/ui/Botao.vue'
import Carregando from '@/components/ui/Carregando.vue'
import EstadoVazio from '@/components/ui/EstadoVazio.vue'
import Etiqueta from '@/components/ui/Etiqueta.vue'
import SeloSaude from '@/modulos/saude/SeloSaude.vue'
import { textoRenova } from '@/modulos/saude/logica'
import ModalDesfecho from './ModalDesfecho.vue'
import ModalEmpresa from './ModalEmpresa.vue'
import { seloSituacao, situacaoEmpresa, textoMarco } from './desfecho'

const rota = useRoute()
const sessao = useSessaoStore()
const id = computed(() => String(rota.params.id))
const empresa = ref<Empresa | null>(null)
const contatos = ref<Contato[]>([])
const totalContatos = ref(0)
const marcos = ref<MarcoEmpresa[]>([])
const saude = ref<SaudeEmpresa | null>(null)
const carregando = ref(true)
const erro = ref<string | null>(null)
const naoExiste = ref(false)
const editarAberto = ref(false)
const desfecho = ref<{ aberto: boolean; modo: 'perda' | 'retorno' | 'corrigir' }>({ aberto: false, modo: 'perda' })

const podeEditar = computed(() => sessao.pode('contatos.editar'))
const podeNumeros = computed(() => sessao.pode('painel.ver') || sessao.pode('relatorios.ver'))
const perdida = computed(() => !!empresa.value && situacaoEmpresa(empresa.value) === 'perdida')

async function carregar() {
  carregando.value = true
  erro.value = null
  naoExiste.value = false
  try {
    const [e, c, h] = await Promise.all([
      empresasApi.obter(id.value),
      contatosApi.listar({ empresa_id: id.value, ativo: 'todos', por_pagina: 100 }),
      empresasApi.historico(id.value),
    ])
    empresa.value = e
    contatos.value = c.itens
    totalContatos.value = c.total
    marcos.value = h.itens
    document.title = `${e.nome} · Toqqi`
    saude.value = podeNumeros.value ? (await saudeApi.empresa(id.value).catch(() => null))?.saude ?? null : null
  } catch (e) {
    if (e instanceof ApiError && e.status === 404) naoExiste.value = true
    else erro.value = mensagemDoErro(e)
  } finally {
    carregando.value = false
  }
}

function abrirDesfecho(modo: 'perda' | 'retorno' | 'corrigir') {
  desfecho.value = { aberto: true, modo }
}

watch(id, carregar)
onMounted(carregar)
</script>

<template>
  <div>
    <RouterLink :to="{ path: '/contatos', query: { aba: 'empresas' } }" class="mb-4 inline-flex items-center gap-1.5 rounded-lg text-sm font-semibold text-texto-suave hover:text-texto">
      <ArrowLeft class="size-4" aria-hidden="true" /> Empresas
    </RouterLink>

    <Carregando v-if="carregando && !empresa" :linhas="4" />
    <div v-else-if="naoExiste" class="cartao">
      <EstadoVazio :icone="Building2" titulo="Empresa não encontrada" descricao="Ela pode ter sido excluída.">
        <Botao :para="{ path: '/contatos', query: { aba: 'empresas' } }" variante="secundario">Ver todas as empresas</Botao>
      </EstadoVazio>
    </div>
    <Alerta v-else-if="erro" tom="erro">
      {{ erro }} <button type="button" class="link ml-1" @click="carregar">Tentar de novo</button>
    </Alerta>

    <template v-else-if="empresa">
      <header class="mb-6 flex flex-col gap-4 sm:flex-row sm:items-center" data-empresa-cabecalho>
        <span class="flex size-14 shrink-0 items-center justify-center rounded-full bg-marca-suave text-marca-texto" aria-hidden="true">
          <Building2 class="size-6" />
        </span>
        <div class="min-w-0 flex-1">
          <h1 class="titulo-pagina truncate">{{ empresa.nome }}</h1>
          <div class="mt-1 flex flex-wrap items-center gap-2 text-sm text-texto-suave">
            <span v-if="empresa.documento">{{ formatarDocumento(empresa.documento) }}</span>
            <Etiqueta :tom="seloSituacao(empresa).tom" ponto>{{ seloSituacao(empresa).texto }}</Etiqueta>
            <SeloSaude v-if="saude" :faixa="saude.faixa" :nota="saude.nota" />
          </div>
        </div>
        <div class="flex flex-wrap gap-2">
          <Botao v-if="sessao.pode('relatorios.ver')" variante="secundario" :para="{ path: '/relatorios/historico', query: { empresa_id: String(empresa.id) } }">
            <History class="size-4" aria-hidden="true" /> Histórico de respostas
          </Botao>
          <Botao v-if="podeEditar" variante="secundario" @click="editarAberto = true"><Pencil class="size-4" aria-hidden="true" /> Editar</Botao>
          <Botao v-if="podeEditar && perdida" variante="secundario" @click="abrirDesfecho('retorno')"><RotateCcw class="size-4" aria-hidden="true" /> Voltou a ser cliente</Botao>
          <Botao v-if="podeEditar && perdida" variante="secundario" @click="abrirDesfecho('corrigir')"><Pencil class="size-4" aria-hidden="true" /> Corrigir a perda</Botao>
          <Botao v-else-if="podeEditar" variante="perigo-suave" @click="abrirDesfecho('perda')"><UserX class="size-4" aria-hidden="true" /> Marcar como perdida</Botao>
        </div>
      </header>

      <div class="grid gap-6 lg:grid-cols-3">
        <div class="flex flex-col gap-6 lg:col-span-1">
          <section class="cartao p-5" aria-labelledby="titulo-dados-empresa">
            <h2 id="titulo-dados-empresa" class="font-bold text-texto">Dados</h2>
            <dl class="mt-3 grid grid-cols-[auto_1fr] gap-x-4 gap-y-2.5 text-sm">
              <dt class="text-texto-fraco">Valor mensal</dt>
              <dd class="tabular-nums text-texto">{{ formatarMoeda(empresa.valor_mensal) }}</dd>
              <dt class="text-texto-fraco">Cliente desde</dt>
              <dd class="text-texto">{{ formatarData(empresa.cliente_desde) }}</dd>
              <dt class="text-texto-fraco">Renovação</dt>
              <dd class="text-texto">{{ formatarData(empresa.renovacao_em) }}</dd>
              <dt class="text-texto-fraco">Grupo</dt>
              <dd class="text-texto">{{ empresa.grupo?.nome ?? '—' }}</dd>
              <dt class="text-texto-fraco">Segmento</dt>
              <dd class="text-texto">{{ empresa.segmento?.nome ?? '—' }}</dd>
              <dt class="text-texto-fraco">Responsável</dt>
              <dd class="text-texto">{{ empresa.responsavel?.nome ?? '—' }}</dd>
              <template v-if="empresa.codigo_externo">
                <dt class="text-texto-fraco">No seu sistema</dt>
                <dd class="font-mono text-texto">{{ empresa.codigo_externo }}</dd>
              </template>
              <template v-if="perdida">
                <dt class="text-texto-fraco">Motivo da perda</dt>
                <dd class="text-texto">{{ [empresa.motivo_perda_rotulo, empresa.motivo_detalhe].filter(Boolean).join(': ') || '—' }}</dd>
              </template>
            </dl>
          </section>

          <section v-if="saude" class="cartao p-5" aria-labelledby="titulo-saude-empresa" data-empresa-saude>
            <h2 id="titulo-saude-empresa" class="font-bold text-texto">Saúde da conta</h2>
            <p v-if="saude.renovacao && saude.destaque" class="mt-2 text-sm font-semibold text-erro">{{ textoRenova(saude.renovacao.dias) }}, com a saúde em risco</p>
            <ul v-if="saude.porques.length" class="mt-3 flex flex-col gap-2 text-sm">
              <li v-for="(p, i) in saude.porques" :key="i" class="flex gap-2">
                <span
                  class="mt-1.5 size-2 shrink-0 rounded-full"
                  :class="{ 'bg-erro': p.tom === 'negativo', 'bg-sucesso': p.tom === 'positivo', 'bg-texto-fraco': p.tom === 'neutro' }"
                  aria-hidden="true"
                />
                <span class="text-texto-suave">{{ p.texto }}</span>
              </li>
            </ul>
            <p v-else class="mt-2 text-sm text-texto-suave">Ainda sem respostas suficientes para dizer.</p>
          </section>
        </div>

        <div class="flex flex-col gap-6 lg:col-span-2">
          <section class="cartao" aria-labelledby="titulo-contatos-empresa">
            <div class="flex items-center justify-between gap-3 border-b border-borda px-5 py-4">
              <h2 id="titulo-contatos-empresa" class="font-bold text-texto">Contatos ({{ totalContatos }})</h2>
            </div>
            <EstadoVazio v-if="!contatos.length" :icone="Users" titulo="Nenhum contato" descricao="Cadastre ou importe as pessoas desta empresa para mandar as pesquisas." />
            <ul v-else class="divide-y divide-borda">
              <li v-for="c in contatos" :key="c.id" class="flex flex-wrap items-center gap-x-3 gap-y-1 px-5 py-3">
                <RouterLink :to="`/contatos/${c.id}`" class="link font-semibold">{{ c.nome }}</RouterLink>
                <span class="min-w-0 truncate text-sm text-texto-fraco">{{ c.email ?? '' }}</span>
                <Etiqueta v-if="!c.ativo" tom="neutro" class="ml-auto">Inativo</Etiqueta>
                <Etiqueta v-else :tom="situacaoContato(c.situacao, c).tom" ponto class="ml-auto">{{ situacaoContato(c.situacao, c).rotulo }}</Etiqueta>
              </li>
            </ul>
            <p v-if="totalContatos > contatos.length" class="border-t border-borda px-5 py-3 text-sm text-texto-suave">
              Mostrando {{ contatos.length }} de {{ totalContatos }}. Para ver todos, busque pelo nome da empresa em Contatos.
            </p>
          </section>

          <section class="cartao" aria-labelledby="titulo-linha-tempo" data-linha-do-tempo>
            <h2 id="titulo-linha-tempo" class="border-b border-borda px-5 py-4 font-bold text-texto">Linha do tempo</h2>
            <EstadoVazio v-if="!marcos.length" :icone="History" titulo="Sem registros ainda" descricao="A entrada, as mudanças de valor, a perda e o retorno aparecem aqui." />
            <ol v-else class="flex flex-col gap-0 px-5 py-4">
              <li v-for="m in marcos" :key="m.id" class="relative flex gap-3 pb-4 last:pb-0">
                <span
                  class="mt-1.5 size-2.5 shrink-0 rounded-full"
                  :class="{
                    'bg-sucesso': textoMarco(m).tom === 'sucesso',
                    'bg-erro': textoMarco(m).tom === 'erro',
                    'bg-atencao': textoMarco(m).tom === 'atencao',
                    'bg-texto-fraco': textoMarco(m).tom === 'neutro',
                  }"
                  aria-hidden="true"
                />
                <div class="min-w-0">
                  <p class="text-sm font-semibold text-texto">{{ textoMarco(m).titulo }}</p>
                  <p class="text-xs text-texto-fraco">{{ [formatarData(m.data), textoMarco(m).detalhe].filter(Boolean).join(' · ') }}</p>
                </div>
              </li>
            </ol>
          </section>
        </div>
      </div>

      <ModalEmpresa v-model:aberto="editarAberto" :empresa="empresa" @salvo="carregar" />
      <ModalDesfecho v-model:aberto="desfecho.aberto" :empresa="empresa" :modo="desfecho.modo" @salvo="carregar" />
    </template>
  </div>
</template>

<script setup lang="ts">
// Crescimento › Oportunidades: as listas "Pode crescer" e "Promotores recentes" (com o critério de cada uma e a regra
// de ouro), filtros de grupo e responsável e as empresas com NPS, valor, contato e última oferta. "Oferecer pelo
// WhatsApp" abre wa.me com o texto da oferta pronto (sem telefone, o e-mail) e registra a oferta; depois, "Registrar
// resultado". Tabela a partir de 1280 px (muitas colunas), cartões abaixo.
import { computed, onBeforeUnmount, reactive, ref } from 'vue'
import { Building2, Mail, MessageCircle, Search, ShieldCheck } from 'lucide-vue-next'
import {
  ApiError,
  crescimentoApi,
  mensagemDoErro,
  type ConfigCrescimento,
  type Id,
  type Oportunidade,
  type Pagina,
  type UltimaOferta,
} from '@/api'
import { avisar } from '@/composables/avisos'
import { useCadastrosStore } from '@/stores/cadastros'
import { useSessaoStore } from '@/stores/sessao'
import { formatarData } from '@/utils/datas'
import { exibirTelefone, formatarMoeda, plural } from '@/utils/formatos'
import Alerta from '@/components/ui/Alerta.vue'
import Botao from '@/components/ui/Botao.vue'
import BotoesSegmentados from '@/components/ui/BotoesSegmentados.vue'
import EstadoVazio from '@/components/ui/EstadoVazio.vue'
import Etiqueta from '@/components/ui/Etiqueta.vue'
import Paginacao from '@/components/ui/Paginacao.vue'
import Selecao from '@/components/ui/Selecao.vue'
import Tabela, { type Coluna } from '@/components/ui/Tabela.vue'
import TextoEmail from '@/components/ui/TextoEmail.vue'
import { PADRAO_CRESCIMENTO } from '@/modulos/configuracoes/configCrescimento'
import SeloNps from '@/modulos/relatorios/SeloNps.vue'
import { usarRelatorio } from '@/modulos/relatorios/usarRelatorio'
import ModalResultadoOferta from './ModalResultadoOferta.vue'
import {
  LISTAS_OPORTUNIDADE,
  ORDEM_LISTAS,
  REGRA_DE_OURO,
  filtrosOportunidadesParaApi,
  linkDaOferta,
  numeroDecimal,
  resultadoOferta,
  textoOferta,
  type FiltrosOportunidadesTela,
} from './logica'

const props = defineProps<{
  /** O texto da oferta vem daqui: null enquanto carrega ou se falhou (aí "Oferecer" fica desligado). */
  config: ConfigCrescimento | null
  erroConfig: string | null
}>()
const filtros = defineModel<FiltrosOportunidadesTela>('filtros', { required: true })
const emit = defineEmits<{ mudou: []; recarregarConfig: [] }>()
const sessao = useSessaoStore()
const cadastros = useCadastrosStore()
const podeTratar = computed(() => sessao.pode('crescimento.tratar'))
const podeVerCadastros = computed(() => sessao.pode('contatos.ver'))

const consulta = computed(() => filtrosOportunidadesParaApi(filtros.value))
const { dados, carregando, atualizando, erro, carregar } = usarRelatorio<Pagina<Oportunidade>>(
  (sinal) => crescimentoApi.oportunidades(consulta.value, sinal),
  () => JSON.stringify(consulta.value),
)
defineExpose({ recarregar: () => carregar() })

const opcoesLista = ORDEM_LISTAS.map((l) => ({ valor: l, rotulo: LISTAS_OPORTUNIDADE[l].rotulo }))
/** Opções de uma lista dos cadastros (com "Sem responsável" = 0 quando pedido) e o valor do endereço, se faltar. */
function opcoesCom(lista: { id: Id; nome: string }[], atual: Id | '', sem?: string) {
  const opcoes: { valor: Id; rotulo: string }[] = [...(sem ? [{ valor: '0' as Id, rotulo: sem }] : []), ...lista.map((x) => ({ valor: x.id, rotulo: x.nome }))]
  if (atual !== '' && !opcoes.some((o) => String(o.valor) === String(atual))) opcoes.push({ valor: atual, rotulo: 'Escolhido no link' })
  return opcoes
}
const temFiltro = computed(() => filtros.value.grupo_id !== '' || filtros.value.responsavel_id !== '')
function limparFiltros() {
  Object.assign(filtros.value, { grupo_id: '', responsavel_id: '' })
}

const pagina = computed({ get: () => filtros.value.pagina, set: (p: number) => (filtros.value.pagina = p) })
const itens = computed(() => dados.value?.itens ?? [])

// ── Oferta ──────────────────────────────────────────────────────────────────
// Sem a configuração (ainda carregando ou com erro), "Oferecer" fica desligado: a oferta não sai com o texto padrão
// no lugar do texto da empresa sem ninguém saber.
const ofertaPronta = computed(() => props.config !== null)
const modelo = computed(() => props.config?.texto_oferta?.trim() || PADRAO_CRESCIMENTO.texto_oferta)
function texto(o: Oportunidade): string {
  return textoOferta(modelo.value, {
    nome: o.contato?.nome,
    empresa: sessao.conta?.nome,
    empresa_cliente: o.empresa.nome,
    representante: sessao.usuario?.nome,
  })
}
const links = computed(() => new Map(itens.value.map((o) => [String(o.empresa.id), linkDaOferta(o, texto(o))])))
const linkDe = (o: Oportunidade) => links.value.get(String(o.empresa.id)) ?? null

/**
 * Empresas travadas: enquanto a oferta é registrada e por alguns segundos depois. Um clique a mais (o segundo de um
 * clique duplo, ou outro logo em seguida) não abre outra conversa nem registra outra oferta.
 */
const TRAVA_DEPOIS_DA_OFERTA_MS = 5000
const travadas = reactive(new Set<string>())
const destravar = new Map<string, ReturnType<typeof setTimeout>>()
onBeforeUnmount(() => destravar.forEach((t) => clearTimeout(t)))
const travada = (o: Oportunidade) => travadas.has(String(o.empresa.id))
const anuncio = ref('')

/** O botão de oferecer: link de verdade com o texto pronto ou, sem a configuração, um botão desligado. */
function atributosOferta(o: Oportunidade): Record<string, string | boolean | undefined> {
  const l = linkDe(o)
  if (!l || !ofertaPronta.value) {
    return { type: 'button', disabled: true, title: props.erroConfig ? 'Não deu para carregar o texto da oferta.' : 'Carregando o texto da oferta…' }
  }
  return {
    href: l.href,
    target: l.canal === 'whatsapp' ? '_blank' : undefined,
    rel: 'noopener noreferrer',
    'aria-disabled': travada(o) ? 'true' : undefined,
  }
}

function trocarOferta(empresaId: Id, ultima: UltimaOferta) {
  if (!dados.value) return
  dados.value = {
    ...dados.value,
    itens: dados.value.itens.map((x) => (String(x.empresa.id) === String(empresaId) ? { ...x, ultima_oferta: ultima } : x)),
  }
}

/** O link abre sozinho (é um link de verdade: o navegador não bloqueia); aqui a oferta é registrada. */
async function aoOferecer(o: Oportunidade, e: MouseEvent) {
  const chave = String(o.empresa.id)
  const link = linkDe(o)
  // O segundo clique de um clique duplo (detail 2) ou a empresa travada: nem abre outra conversa.
  if (e.detail > 1 || travadas.has(chave) || !link || !ofertaPronta.value || !podeTratar.value) {
    e.preventDefault()
    return
  }
  travadas.add(chave)
  let registrou = false
  try {
    const r = await crescimentoApi.registrarOferta({
      empresa_id: o.empresa.id,
      contato_id: o.contato?.id ?? null,
      lista: filtros.value.lista,
      canal: link.canal,
      texto: texto(o),
    })
    registrou = true
    if (r && r.id !== undefined) {
      trocarOferta(o.empresa.id, { id: r.id, criada_em: r.criada_em || new Date().toISOString(), resultado: r.resultado ?? null, valor: r.valor ?? null })
    }
    anuncio.value = `Oferta para ${o.empresa.nome} registrada. Quando souber a resposta, use “Registrar resultado”.`
    emit('mudou')
  } catch (erro) {
    // Um 422 traz o motivo no campo (ex.: o contato saiu da lista); a mensagem geral seria só "confira os campos".
    const motivo = erro instanceof ApiError ? (Object.values(erro.campos)[0] ?? erro.mensagem) : mensagemDoErro(erro)
    if (erro instanceof ApiError && erro.status === 422) {
      // A regra de ouro, conferida na hora: a empresa saiu das oportunidades (detrator, plano de ação aberto…) ou o
      // contato saiu da lista depois que a lista abriu. A conversa já abriu: não é para mandar. A lista atualiza.
      avisar.erro(`${motivo} A oferta não foi registrada: não mande a mensagem que abriu.`)
      void carregar()
    } else avisar.erro(`A conversa abriu, mas a oferta não foi registrada: ${motivo}`)
  } finally {
    if (registrou) {
      destravar.set(
        chave,
        setTimeout(() => {
          travadas.delete(chave)
          destravar.delete(chave)
        }, TRAVA_DEPOIS_DA_OFERTA_MS),
      )
    } else travadas.delete(chave)
  }
}

const resultadoDe = ref<Oportunidade | null>(null)
const modalResultado = ref(false)
function abrirResultado(o: Oportunidade) {
  resultadoDe.value = o
  modalResultado.value = true
}
function aoSalvarResultado(empresaId: Id, ultima: UltimaOferta) {
  trocarOferta(empresaId, ultima)
  anuncio.value = `Resultado da oferta registrado: ${resultadoOferta(ultima.resultado)?.rotulo ?? ''}.`
  emit('mudou')
}

// A oferta sai pelo contato (o botão fica com ele) e o resultado fica com a última oferta.
const colunas: Coluna[] = [
  { chave: 'empresa', rotulo: 'Empresa', classe: 'w-[22%]' },
  { chave: 'nps', rotulo: 'NPS' },
  { chave: 'valor', rotulo: 'Valor mensal', alinhar: 'direita' },
  { chave: 'contato', rotulo: 'Contato' },
  { chave: 'oferta', rotulo: 'Última oferta' },
]
</script>

<template>
  <div class="flex flex-col gap-4">
    <section class="cartao flex flex-col gap-3 p-4 sm:p-5" aria-labelledby="t-qual-lista">
      <h2 id="t-qual-lista" class="sr-only">Qual lista ver</h2>
      <BotoesSegmentados v-model="filtros.lista" :opcoes="opcoesLista" rotulo="Lista de oportunidades" bloco />
      <p class="text-sm text-texto-suave" aria-live="polite" data-criterio>{{ LISTAS_OPORTUNIDADE[filtros.lista].criterio }}</p>
      <p class="flex items-start gap-2 text-sm text-texto-fraco" data-regra-de-ouro>
        <ShieldCheck class="mt-0.5 size-4 shrink-0 text-sucesso" aria-hidden="true" /> {{ REGRA_DE_OURO }}
      </p>
      <div v-if="podeVerCadastros || temFiltro" class="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <Selecao
          v-if="podeVerCadastros || filtros.grupo_id !== ''"
          v-model="filtros.grupo_id"
          rotulo="Grupo de empresas"
          :opcoes="opcoesCom(cadastros.listas.grupos, filtros.grupo_id)"
          vazio="Todos os grupos"
        />
        <Selecao
          v-if="podeVerCadastros || filtros.responsavel_id !== ''"
          v-model="filtros.responsavel_id"
          rotulo="Responsável"
          :opcoes="opcoesCom(cadastros.listas.responsaveis, filtros.responsavel_id, 'Sem responsável')"
          vazio="Todos"
        />
        <div v-if="temFiltro" class="flex items-end">
          <Botao variante="fantasma" tamanho="sm" class="!h-11" @click="limparFiltros">Limpar filtros</Botao>
        </div>
      </div>
      <p v-if="!podeTratar" class="text-sm text-texto-fraco">Seu perfil pode ver as oportunidades, mas não registrar ofertas.</p>
      <Alerta v-else-if="!config && erroConfig" tom="erro" data-erro-config>
        Não deu para carregar o texto da oferta: {{ erroConfig }} Enquanto isso, “Oferecer” fica desligado.
        <button type="button" class="link ml-1" @click="emit('recarregarConfig')">Tentar de novo</button>
      </Alerta>
    </section>

    <section class="cartao" aria-labelledby="t-lista-oportunidades">
      <h2 id="t-lista-oportunidades" class="sr-only">{{ LISTAS_OPORTUNIDADE[filtros.lista].rotulo }}</h2>

      <div v-if="carregando && !dados" class="flex flex-col gap-3 p-5" role="status" aria-label="Carregando as oportunidades">
        <div v-for="i in 4" :key="i" class="h-14 animate-pulse rounded-xl bg-superficie-2" />
      </div>

      <Alerta v-else-if="erro && !dados" tom="erro" class="m-4">
        {{ erro }} <button type="button" class="link ml-1" @click="carregar">Tentar de novo</button>
      </Alerta>

      <div v-else-if="dados" class="transition-opacity" :class="atualizando ? 'opacity-60' : ''" :aria-busy="atualizando || undefined">
        <Alerta v-if="erro" tom="erro" class="m-4">
          Não deu para atualizar a lista: {{ erro }} <button type="button" class="link ml-1" @click="carregar">Tentar de novo</button>
        </Alerta>

        <!-- Computador: tabela -->
        <div v-if="itens.length" class="hidden xl:block">
          <Tabela densa :colunas="colunas" :linhas="itens" :chave="(x) => x.empresa.id" :legenda="LISTAS_OPORTUNIDADE[filtros.lista].rotulo">
            <template #cel-empresa="{ linha: x }">
              <p class="break-words font-semibold text-texto">{{ x.empresa.nome }}</p>
              <p class="text-xs text-texto-fraco">{{ [x.grupo?.nome, x.responsavel?.nome ?? 'Sem responsável'].filter(Boolean).join(' · ') }}</p>
            </template>
            <template #cel-nps="{ linha: x }">
              <SeloNps :nps="x.nps" compacto />
              <p class="text-xs text-texto-fraco">{{ plural(x.nps.total, 'resposta', 'respostas') }}</p>
              <p v-if="x.ultima_resposta" class="text-xs text-texto-fraco">
                Última: <template v-if="typeof x.ultima_resposta.nota === 'number'">nota {{ x.ultima_resposta.nota }}{{ x.ultima_resposta.tipo_nota === 'csat' ? ' (CSAT)' : '' }} em </template>{{ formatarData(x.ultima_resposta.data) }}
              </p>
            </template>
            <template #cel-valor="{ linha: x }">
              <span v-if="numeroDecimal(x.empresa.valor_mensal) !== null" class="whitespace-nowrap tabular-nums text-texto-suave">{{ formatarMoeda(x.empresa.valor_mensal) }}</span>
              <span v-else class="text-texto-fraco">Sem valor</span>
            </template>
            <template #cel-contato="{ linha: x }">
              <template v-if="x.contato">
                <p class="font-medium text-texto">{{ x.contato.nome }}</p>
                <p v-if="x.contato.telefone" class="whitespace-nowrap text-xs text-texto-fraco">{{ exibirTelefone(x.contato.telefone) }}</p>
                <p v-else-if="x.contato.email" class="text-xs text-texto-fraco"><TextoEmail :email="x.contato.email" /></p>
                <component
                  :is="ofertaPronta ? 'a' : 'button'"
                  v-if="podeTratar && linkDe(x)"
                  v-bind="atributosOferta(x)"
                  class="mt-2 inline-flex h-9 items-center gap-1.5 whitespace-nowrap rounded-xl border border-borda-forte bg-superficie px-3 text-sm font-semibold text-texto transition-colors hover:bg-superficie-2 disabled:cursor-not-allowed disabled:opacity-55 disabled:hover:bg-superficie aria-disabled:cursor-not-allowed aria-disabled:opacity-55"
                  :data-oferecer="String(x.empresa.id)"
                  @click="aoOferecer(x, $event)"
                >
                  <MessageCircle v-if="linkDe(x)!.canal === 'whatsapp'" class="size-4 text-sucesso" aria-hidden="true" />
                  <Mail v-else class="size-4 text-texto-fraco" aria-hidden="true" />
                  {{ linkDe(x)!.canal === 'whatsapp' ? 'Oferecer pelo WhatsApp' : 'Oferecer por e-mail' }}
                  <span class="sr-only"> para {{ x.empresa.nome }}{{ ofertaPronta && linkDe(x)!.canal === 'whatsapp' ? ' (abre em nova aba)' : '' }}</span>
                </component>
              </template>
              <span v-else class="text-texto-fraco">Sem contato disponível</span>
            </template>
            <template #cel-oferta="{ linha: x }">
              <template v-if="x.ultima_oferta">
                <p class="whitespace-nowrap text-texto-suave">{{ formatarData(x.ultima_oferta.criada_em) }}</p>
                <Etiqueta v-if="resultadoOferta(x.ultima_oferta.resultado)" :tom="resultadoOferta(x.ultima_oferta.resultado)!.tom" class="mt-1">
                  {{ resultadoOferta(x.ultima_oferta.resultado)!.rotulo }}
                </Etiqueta>
                <p v-else class="text-xs text-texto-fraco">Sem resultado ainda</p>
                <button
                  v-if="podeTratar"
                  type="button"
                  class="link mt-1 flex min-h-9 items-center text-left text-sm"
                  :data-resultado="String(x.empresa.id)"
                  @click="abrirResultado(x)"
                >
                  {{ x.ultima_oferta.resultado ? 'Mudar resultado' : 'Registrar resultado' }}<span class="sr-only"> da oferta para {{ x.empresa.nome }}</span>
                </button>
              </template>
              <span v-else class="text-texto-fraco">Nenhuma</span>
            </template>
          </Tabela>
        </div>

        <!-- Celular e tablet: cartões -->
        <ul v-if="itens.length" class="flex flex-col divide-y divide-borda xl:hidden" :aria-label="LISTAS_OPORTUNIDADE[filtros.lista].rotulo">
          <li v-for="x in itens" :key="String(x.empresa.id)" class="flex flex-col gap-3 px-4 py-4">
            <div class="flex items-start justify-between gap-3">
              <div class="min-w-0">
                <h3 class="break-words font-semibold text-texto">{{ x.empresa.nome }}</h3>
                <p class="text-sm text-texto-fraco">
                  {{ [x.grupo?.nome, x.responsavel?.nome ?? 'Sem responsável'].filter(Boolean).join(' · ') }}
                  · {{ numeroDecimal(x.empresa.valor_mensal) !== null ? `${formatarMoeda(x.empresa.valor_mensal)}/mês` : 'sem valor' }}
                </p>
              </div>
              <SeloNps :nps="x.nps" compacto />
            </div>
            <dl class="grid grid-cols-1 gap-x-4 gap-y-1.5 text-sm sm:grid-cols-2">
              <div class="min-w-0">
                <dt class="text-texto-fraco">Contato</dt>
                <dd class="break-words text-texto">
                  <template v-if="x.contato">
                    {{ x.contato.nome }} ·
                    <span v-if="exibirTelefone(x.contato.telefone)" class="whitespace-nowrap">{{ exibirTelefone(x.contato.telefone) }}</span>
                    <TextoEmail v-else-if="x.contato.email" :email="x.contato.email" />
                  </template>
                  <template v-else>Sem contato disponível</template>
                </dd>
              </div>
              <div>
                <dt class="text-texto-fraco">Respostas</dt>
                <dd class="text-texto">
                  {{ plural(x.nps.total, 'resposta', 'respostas') }}<template v-if="x.ultima_resposta"> · última {{ formatarData(x.ultima_resposta.data) }}<template v-if="typeof x.ultima_resposta.nota === 'number'"> (nota {{ x.ultima_resposta.nota }})</template></template>
                </dd>
              </div>
              <div class="sm:col-span-2">
                <dt class="text-texto-fraco">Última oferta</dt>
                <dd class="flex flex-wrap items-center gap-2 text-texto">
                  <template v-if="x.ultima_oferta">
                    {{ formatarData(x.ultima_oferta.criada_em) }}
                    <Etiqueta v-if="resultadoOferta(x.ultima_oferta.resultado)" :tom="resultadoOferta(x.ultima_oferta.resultado)!.tom">
                      {{ resultadoOferta(x.ultima_oferta.resultado)!.rotulo }}
                    </Etiqueta>
                    <span v-else class="text-texto-fraco">· sem resultado ainda</span>
                  </template>
                  <template v-else>Nenhuma</template>
                </dd>
              </div>
            </dl>
            <div v-if="podeTratar && (linkDe(x) || x.ultima_oferta)" class="flex flex-wrap gap-2">
              <component
                :is="ofertaPronta ? 'a' : 'button'"
                v-if="linkDe(x)"
                v-bind="atributosOferta(x)"
                class="inline-flex h-10 items-center gap-1.5 rounded-xl border border-borda-forte bg-superficie px-3.5 text-sm font-semibold text-texto transition-colors hover:bg-superficie-2 disabled:cursor-not-allowed disabled:opacity-55 disabled:hover:bg-superficie aria-disabled:cursor-not-allowed aria-disabled:opacity-55"
                :data-oferecer-cartao="String(x.empresa.id)"
                @click="aoOferecer(x, $event)"
              >
                <MessageCircle v-if="linkDe(x)!.canal === 'whatsapp'" class="size-4 text-sucesso" aria-hidden="true" />
                <Mail v-else class="size-4 text-texto-fraco" aria-hidden="true" />
                {{ linkDe(x)!.canal === 'whatsapp' ? 'Oferecer pelo WhatsApp' : 'Oferecer por e-mail' }}
                <span class="sr-only"> para {{ x.empresa.nome }}{{ ofertaPronta && linkDe(x)!.canal === 'whatsapp' ? ' (abre em nova aba)' : '' }}</span>
              </component>
              <Botao v-if="x.ultima_oferta" variante="fantasma" class="!h-10" @click="abrirResultado(x)">
                {{ x.ultima_oferta.resultado ? 'Mudar resultado' : 'Registrar resultado' }}<span class="sr-only"> da oferta para {{ x.empresa.nome }}</span>
              </Botao>
            </div>
          </li>
        </ul>

        <template v-if="!itens.length">
          <EstadoVazio v-if="temFiltro" :icone="Search" titulo="Nenhuma empresa com esses filtros" descricao="Tente outro grupo ou responsável.">
            <Botao variante="secundario" @click="limparFiltros">Limpar filtros</Botao>
          </EstadoVazio>
          <EstadoVazio
            v-else
            :icone="Building2"
            titulo="Nenhuma empresa nesta lista agora"
            :descricao="
              filtros.lista === 'pode_crescer'
                ? 'Aparecem aqui as empresas com NPS de 0 para cima e valor mensal abaixo da mediana. Sem valor mensal cadastrado, a empresa não entra na conta: cadastre em Contatos › Empresas.'
                : 'Aparecem aqui as empresas com nota 9 ou 10 nos últimos 30 dias. Elas entram sozinhas conforme os clientes respondem.'
            "
          />
        </template>

        <Paginacao
          v-model="pagina"
          :total="dados.total"
          :por-pagina="dados.por_pagina || 50"
          :carregando="atualizando"
          :nome-itens="dados.total === 1 ? 'empresa' : 'empresas'"
        />
      </div>
    </section>
    <p class="sr-only" aria-live="polite">{{ anuncio }}</p>

    <ModalResultadoOferta v-model:aberto="modalResultado" :oportunidade="resultadoDe" @salvo="aoSalvarResultado" />
  </div>
</template>

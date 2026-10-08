<script setup lang="ts">
// Plataforma › Contas: as contas de clientes do Toqqi (a tela de antes da etapa 5g). Etapa 5g: os dias do "+N dias" (no
// botão, no diálogo e no pedido) e da "Nova conta" vêm de `teste.dias`: o gravado no banco, quando a aba Parâmetros já o
// leu, salvou ou releu nesta página (`diasGravados`); antes disso, o de GET /publico/planos (carregando ou com falha, 14).
// A leitura pública tem cache (até 60 s no navegador e 30 s na API): sem o gravado, o número ficaria o de antes de salvar.
// Risco (docs/api-plataforma-risco.md): coluna com o nível, a nota e os motivos; "Suspeitas" mostra só as de risco médio
// ou alto, da maior nota para a menor. No celular, o risco médio ou alto aparece embaixo do nome.
import { computed, onMounted, ref } from 'vue'
import { Building2, CalendarPlus, Gift, Plus, Search, ShieldAlert, Trash2 } from 'lucide-vue-next'
import { mensagemDoErro, plataformaApi, type ContaPlataforma } from '@/api'
import { avisar } from '@/composables/avisos'
import { confirmar } from '@/composables/confirmacao'
import { usarDiasTeste } from '@/composables/planosPublicos'
import { useSessaoStore } from '@/stores/sessao'
import { diasAte, formatarData } from '@/utils/datas'
import { formatarMoeda, plural } from '@/utils/formatos'
import { situacaoConta } from '@/utils/rotulos'
import { nomeDoPlano } from '@/modulos/assinatura/logica'
import { seloExclusao } from '@/modulos/configuracoes/dadosConta'
import Alerta from '@/components/ui/Alerta.vue'
import Botao from '@/components/ui/Botao.vue'
import Campo from '@/components/ui/Campo.vue'
import EstadoVazio from '@/components/ui/EstadoVazio.vue'
import Etiqueta from '@/components/ui/Etiqueta.vue'
import Tabela, { type Coluna } from '@/components/ui/Tabela.vue'
import ModalExcluirConta from './ModalExcluirConta.vue'
import ModalNovaConta from './ModalNovaConta.vue'
import { NIVEIS, detalheSinal, suspeita, suspeitas, textoSinal } from './risco'

const props = defineProps<{ diasGravados?: number | null }>()

const contas = ref<ContaPlataforma[]>([])
const carregando = ref(true)
const erro = ref<string | null>(null)
const busca = ref('')
const soSuspeitas = ref(false)
const ocupado = ref<string | null>(null)
const modalAberto = ref(false)
const sessao = useSessaoStore()
const excluirAberto = ref(false)
const paraExcluir = ref<ContaPlataforma | null>(null)
const diasPublicos = usarDiasTeste()
const diasTeste = computed(() => props.diasGravados ?? diasPublicos.value)

/** A conta do próprio superadmin não pode ser excluída por aqui. */
const propria = (c: ContaPlataforma) => !!sessao.conta && String(sessao.conta.id) === String(c.id)

function pedirExclusao(c: ContaPlataforma) {
  paraExcluir.value = c
  excluirAberto.value = true
}

function aoExcluir(c: ContaPlataforma) {
  contas.value = contas.value.filter((x) => String(x.id) !== String(c.id))
}

// Usuários e "criada em" ganham coluna só em telas bem largas; antes disso, ficam embaixo do nome. As datas (teste e pago
// até) ficam embaixo da situação (no celular, embaixo do nome): a coluna Datas saiu para a coluna Risco caber.
// Risco: coluna a partir de xl; antes disso, o risco médio ou alto fica embaixo do nome.
const colunas: Coluna[] = [
  { chave: 'nome', rotulo: 'Empresa' },
  { chave: 'risco', rotulo: 'Risco', classe: 'hidden xl:table-cell' },
  { chave: 'situacao', rotulo: 'Situação', classe: 'hidden sm:table-cell' },
  { chave: 'assinatura', rotulo: 'Assinatura', classe: 'hidden md:table-cell' },
  { chave: 'usuarios', rotulo: 'Usuários', classe: 'hidden 2xl:table-cell', alinhar: 'direita' },
  { chave: 'criada_em', rotulo: 'Criada em', classe: 'hidden 2xl:table-cell' },
  { chave: 'acoes', rotulo: 'Ações', rotuloOculto: true, alinhar: 'direita' },
]

/** "Profissional · R$ 349,00/mês" (etapa 5a); sem assinatura, o plano da conta (o do teste). */
function textoAssinatura(c: ContaPlataforma): string {
  if (c.assinatura) return `${nomeDoPlano(c.assinatura.plano)} · ${formatarMoeda(c.assinatura.valor)}/mês`
  return c.plano ? `Sem assinatura (plano ${nomeDoPlano(c.plano)})` : 'Sem assinatura'
}

/** "Teste até 15/10/2026 · Pago até 29/10/2026" (celular e telas médias, onde não há a coluna de datas). */
function textoDatas(c: ContaPlataforma): string {
  return [c.teste_ate ? `Teste até ${formatarData(c.teste_ate)}` : '', c.pago_ate ? `Pago até ${formatarData(c.pago_ate)}` : ''].filter(Boolean).join(' · ')
}

/** "+N dias" não vale para conta com assinatura ativa nem cortesia (a API devolve 409). */
function semEstender(c: ContaPlataforma): string | null {
  if (c.situacao === 'cortesia') return 'Conta cortesia não tem teste para estender.'
  if (c.assinatura) return 'Conta com assinatura ativa: o teste não pode ser estendido.'
  return null
}

/** O administrador mais antigo da conta e quantos outros há ("ana@alfa.com.br e mais 1 administrador"). */
function adminDe(c: ContaPlataforma): { email: string; confirmado: boolean; mais: string } | null {
  const [primeiro, ...outros] = c.admins ?? []
  if (!primeiro) return null
  const mais = outros.length ? ` e mais ${plural(outros.length, 'administrador', 'administradores')}` : ''
  return { email: primeiro.email, confirmado: primeiro.email_confirmado, mais }
}

const totalSuspeitas = computed(() => contas.value.filter(suspeita).length)

/** Busca pelo nome da empresa ou pelo e-mail de um administrador; com "Suspeitas", só elas, da maior nota para a menor. */
const filtradas = computed(() => {
  const base = soSuspeitas.value ? suspeitas(contas.value) : contas.value
  const t = busca.value.trim().toLowerCase()
  if (!t) return base
  return base.filter((c) => c.nome.toLowerCase().includes(t) || (c.admins ?? []).some((a) => a.email.toLowerCase().includes(t)))
})

async function carregar() {
  carregando.value = true
  erro.value = null
  try {
    contas.value = await plataformaApi.contas()
  } catch (e) {
    erro.value = mensagemDoErro(e)
  } finally {
    carregando.value = false
  }
}

function substituir(c: ContaPlataforma) {
  const i = contas.value.findIndex((x) => String(x.id) === String(c.id))
  // A resposta pode não trazer todos os campos da listagem (ex.: usuarios): mescla.
  if (i >= 0) contas.value.splice(i, 1, { ...contas.value[i]!, ...c })
}

async function estender(c: ContaPlataforma) {
  if (semEstender(c)) return
  const dias = diasAte(c.teste_ate)
  // O número que a pessoa viu no botão e confirmou é o que vai no pedido.
  const n = diasTeste.value
  const ok = await confirmar({
    titulo: `Dar mais ${n} dias para ${c.nome}?`,
    mensagem:
      c.teste_ate && dias !== null && dias >= 0
        ? `O teste vai até ${formatarData(c.teste_ate)}. Os ${n} dias contam a partir dessa data.`
        : c.teste_ate
          ? `O teste acabou em ${formatarData(c.teste_ate)}. Os ${n} dias contam a partir de hoje.`
          : `Os ${n} dias contam a partir de hoje.`,
    confirmar: `+${n} dias`,
  })
  if (!ok) return
  ocupado.value = `estender-${c.id}`
  try {
    const r = await plataformaApi.estenderTeste(c.id, n)
    substituir(r)
    avisar.sucesso(r?.teste_ate ? `Teste de ${c.nome} vai até ${formatarData(r.teste_ate)}.` : 'Teste estendido.')
  } catch (e) {
    avisar.erro(mensagemDoErro(e))
  } finally {
    ocupado.value = null
  }
}

async function cortesia(c: ContaPlataforma) {
  const ok = await confirmar({
    titulo: `Dar cortesia para ${c.nome}?`,
    mensagem: c.assinatura
      ? `A conta passa a usar o Toqqi sem cobrança, sem data para acabar. A assinatura no Asaas (${textoAssinatura(c)}) será cancelada, com as faturas em aberto.`
      : 'A conta passa a usar o Toqqi sem cobrança, sem data para acabar.',
    confirmar: c.assinatura ? 'Cancelar a assinatura e dar cortesia' : 'Dar cortesia',
    perigo: !!c.assinatura,
    cancelar: 'Voltar',
  })
  if (!ok) return
  ocupado.value = `cortesia-${c.id}`
  try {
    substituir(await plataformaApi.cortesia(c.id))
    avisar.sucesso(`${c.nome} agora é cortesia.`)
  } catch (e) {
    avisar.erro(mensagemDoErro(e))
  } finally {
    ocupado.value = null
  }
}

onMounted(carregar)
</script>

<template>
  <!-- Uma raiz só: a Plataforma esconde a aba com v-show (as janelas vão para o body pelo Teleport do Modal) -->
  <div data-aba-contas>
    <div class="cartao">
      <div class="flex flex-col gap-3 border-b border-borda p-4 sm:flex-row sm:items-center sm:px-5">
        <Campo v-model="busca" rotulo="Buscar conta" rotulo-oculto tipo="search" placeholder="Buscar por empresa ou e-mail" class="sm:max-w-sm sm:flex-1">
          <template #antes><Search class="size-4" aria-hidden="true" /></template>
        </Campo>
        <button
          type="button"
          class="inline-flex min-h-11 items-center gap-2 self-start rounded-xl border px-3.5 text-sm font-semibold transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-foco sm:self-auto"
          :class="soSuspeitas ? 'border-marca bg-marca-suave text-marca-texto' : 'border-borda-forte bg-superficie text-texto hover:bg-superficie-2'"
          :aria-pressed="soSuspeitas"
          title="Só as contas com risco médio ou alto, da maior nota para a menor"
          data-filtro-suspeitas
          @click="soSuspeitas = !soSuspeitas"
        >
          <ShieldAlert class="size-4" aria-hidden="true" /> Suspeitas
          <span class="tabular-nums" :class="soSuspeitas ? '' : totalSuspeitas ? 'text-erro' : 'text-texto-fraco'">{{ totalSuspeitas }}</span>
        </button>
        <p class="text-sm text-texto-fraco sm:ml-auto">{{ filtradas.length }} {{ filtradas.length === 1 ? 'conta' : 'contas' }}</p>
        <Botao class="self-start sm:self-auto" @click="modalAberto = true"><Plus class="size-4" aria-hidden="true" /> Nova conta</Botao>
      </div>

      <Alerta v-if="erro" tom="erro" class="m-4">
        {{ erro }} <button type="button" class="link ml-1" @click="carregar">Tentar de novo</button>
      </Alerta>
      <Tabela v-else :colunas="colunas" :linhas="filtradas" :chave="(c) => c.id" :carregando="carregando" legenda="Contas da plataforma" densa>
        <template #cel-nome="{ linha: c }">
          <div class="flex min-w-48 flex-wrap items-center gap-x-2 gap-y-1">
            <p class="font-semibold text-texto">{{ c.nome }}</p>
            <Etiqueta v-if="propria(c)" tom="marca" data-sua-conta>Sua conta</Etiqueta>
          </div>
          <p v-if="adminDe(c)" class="text-texto-suave [overflow-wrap:anywhere]" data-admin>
            {{ adminDe(c)!.email }}<span v-if="!adminDe(c)!.confirmado" class="text-atencao"> (não confirmado)</span>{{ adminDe(c)!.mais }}
          </p>
          <p class="text-xs text-texto-fraco 2xl:hidden">{{ plural(c.usuarios ?? 0, 'usuário', 'usuários') }} · criada em {{ formatarData(c.criada_em) }}</p>
          <p class="mt-1 text-texto-suave md:hidden">{{ textoAssinatura(c) }}</p>
          <div class="mt-1 flex flex-wrap gap-1.5 sm:hidden">
            <Etiqueta :tom="situacaoConta(c.situacao).tom">{{ situacaoConta(c.situacao).rotulo }}</Etiqueta>
            <Etiqueta v-if="seloExclusao(c.exclusao_em)" tom="erro" data-selo-exclusao>{{ seloExclusao(c.exclusao_em) }}</Etiqueta>
          </div>
          <p v-if="c.teste_ate || c.pago_ate" class="mt-1 text-xs text-texto-fraco sm:hidden">{{ textoDatas(c) }}</p>
          <!-- Até xl (sem a coluna Risco): o risco médio ou alto embaixo do nome (o baixo só na coluna) -->
          <div v-if="c.risco && suspeita(c)" class="mt-2 xl:hidden" data-risco-celular>
            <Etiqueta :tom="NIVEIS[c.risco.nivel].tom">Risco {{ NIVEIS[c.risco.nivel].rotulo.toLowerCase() }} <span class="tabular-nums">{{ c.risco.pontos }}</span></Etiqueta>
            <ul class="mt-1 space-y-0.5 text-xs text-texto-suave">
              <li v-for="(sinal, i) in c.risco.sinais" :key="i">
                {{ textoSinal(sinal) }}<span v-if="detalheSinal(sinal)" class="block text-texto-fraco [overflow-wrap:anywhere]">{{ detalheSinal(sinal) }}</span>
              </li>
            </ul>
          </div>
        </template>
        <template #cel-risco="{ linha: c }">
          <div v-if="c.risco" class="min-w-52 max-w-64" data-risco>
            <Etiqueta v-if="suspeita(c)" :tom="NIVEIS[c.risco.nivel].tom" data-nivel
              >{{ NIVEIS[c.risco.nivel].rotulo }} <span class="tabular-nums">{{ c.risco.pontos }}</span><span class="sr-only"> de 100 pontos</span></Etiqueta
            >
            <p v-else class="text-texto-fraco tabular-nums" data-nivel>
              {{ c.risco.sinais.length ? `Baixo ${c.risco.pontos}` : 'Nenhum sinal' }}<span v-if="c.risco.sinais.length" class="sr-only"> de 100 pontos</span>
            </p>
            <ul v-if="c.risco.sinais.length" class="mt-1.5 space-y-1 text-xs leading-snug" :class="suspeita(c) ? 'text-texto-suave' : 'text-texto-fraco'">
              <li v-for="(sinal, i) in c.risco.sinais" :key="i" class="flex gap-1.5" data-sinal>
                <span class="w-6 shrink-0 text-right font-semibold tabular-nums text-texto-fraco" aria-hidden="true">+{{ sinal.pontos }}</span>
                <span class="min-w-0 [overflow-wrap:anywhere]"
                  >{{ textoSinal(sinal) }}<span class="sr-only"> ({{ sinal.pontos }} pontos)</span
                  ><span v-if="detalheSinal(sinal)" class="mt-0.5 block text-texto-fraco">{{ detalheSinal(sinal) }}</span></span
                >
              </li>
            </ul>
          </div>
          <span v-else class="text-texto-fraco" title="Conta da equipe Toqqi: sem nota">—<span class="sr-only">Conta da equipe, sem nota</span></span>
        </template>
        <template #cel-situacao="{ linha: c }">
          <div class="flex flex-col items-start gap-1">
            <Etiqueta :tom="situacaoConta(c.situacao).tom">{{ situacaoConta(c.situacao).rotulo }}</Etiqueta>
            <!-- Etapa 5f: conta encerrada com a exclusão automática já avisada -->
            <Etiqueta v-if="seloExclusao(c.exclusao_em)" tom="erro" data-selo-exclusao>{{ seloExclusao(c.exclusao_em) }}</Etiqueta>
          </div>
          <p v-if="c.atrasada_desde" class="mt-1 whitespace-nowrap text-xs text-texto-fraco">Vencida em {{ formatarData(c.atrasada_desde) }}</p>
          <p v-if="c.teste_ate" class="mt-1 whitespace-nowrap text-xs text-texto-fraco" data-teste-ate>Teste até {{ formatarData(c.teste_ate) }}</p>
          <p v-if="c.pago_ate" class="mt-0.5 whitespace-nowrap text-xs text-texto-fraco" data-pago-ate>Pago até {{ formatarData(c.pago_ate) }}</p>
        </template>
        <template #cel-assinatura="{ linha: c }">
          <template v-if="c.assinatura">
            <p class="text-texto">{{ nomeDoPlano(c.assinatura.plano) }}</p>
            <p class="whitespace-nowrap text-xs text-texto-fraco">{{ formatarMoeda(c.assinatura.valor) }}/mês</p>
          </template>
          <template v-else>
            <p class="text-texto-fraco">Sem assinatura</p>
            <p v-if="c.plano" class="whitespace-nowrap text-xs text-texto-fraco">Plano {{ nomeDoPlano(c.plano) }}</p>
          </template>
        </template>
        <template #cel-usuarios="{ linha: c }">
          <span class="tabular-nums text-texto-suave">{{ c.usuarios ?? '—' }}</span>
        </template>
        <template #cel-criada_em="{ linha: c }">
          <span class="whitespace-nowrap text-texto-suave">{{ formatarData(c.criada_em) }}</span>
        </template>
        <template #cel-acoes="{ linha: c }">
          <div class="flex flex-wrap justify-end gap-1.5">
            <Botao
              variante="secundario"
              tamanho="sm"
              :carregando="ocupado === `estender-${c.id}`"
              :desabilitado="!!ocupado || !!semEstender(c)"
              :title="semEstender(c) ?? undefined"
              @click="estender(c)"
            >
              <CalendarPlus class="size-4" aria-hidden="true" /> +{{ diasTeste }} dias<span class="sr-only"> para {{ c.nome }}{{ semEstender(c) ? ` (indisponível: ${semEstender(c)})` : '' }}</span>
            </Botao>
            <Botao
              v-if="c.situacao !== 'cortesia'"
              variante="fantasma"
              tamanho="sm"
              :carregando="ocupado === `cortesia-${c.id}`"
              :desabilitado="!!ocupado"
              @click="cortesia(c)"
            >
              <Gift class="size-4" aria-hidden="true" /> Cortesia<span class="sr-only"> para {{ c.nome }}</span>
            </Botao>
            <Botao v-if="!propria(c)" variante="perigo-suave" tamanho="sm" :desabilitado="!!ocupado" @click="pedirExclusao(c)">
              <Trash2 class="size-4" aria-hidden="true" /> Excluir<span class="sr-only"> a conta {{ c.nome }}</span>
            </Botao>
          </div>
        </template>
        <template #vazio>
          <EstadoVazio
            :icone="Building2"
            :titulo="soSuspeitas && !busca ? 'Nenhuma conta suspeita' : busca ? 'Nenhuma conta encontrada' : 'Nenhuma conta ainda'"
            :descricao="soSuspeitas && !busca ? 'Nenhuma conta tem risco médio ou alto agora.' : undefined"
          />
        </template>
      </Tabela>
    </div>

    <ModalNovaConta v-model:aberto="modalAberto" :dias-teste="diasTeste" @criada="carregar" />
    <ModalExcluirConta v-model:aberto="excluirAberto" :conta="paraExcluir" @excluida="aoExcluir" />
  </div>
</template>

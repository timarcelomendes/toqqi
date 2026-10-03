<script setup lang="ts">
// Configurações › IA (etapa 4b): se a IA está ligada na plataforma, a chave da conta ("Analisar comentários com
// IA"), o uso do mês contra o teto de segurança, a fila, o "analisar os últimos 90 dias" e o que vai para a IA.
// Etapa 5b: a cota de IA do plano (cada pergunta ao assistente usa 1 análise).
// Etapa 5d: "Como a IA escreve" (modelo, estilo e os passos sugeridos nas ações); o resumo do painel e o parecer dos
// relatórios também gastam a cota. Desde 03/10, o nível Mais detalhado gasta 2 análises por pergunta, resumo ou parecer.
import { computed, onMounted, ref, watch } from 'vue'
import { Gauge, History, ShieldCheck, Sparkles } from 'lucide-vue-next'
import { ApiError, iaApi, mensagemDoErro, type ConfigIa, type CotaIa } from '@/api'
import { avisar } from '@/composables/avisos'
import { confirmar } from '@/composables/confirmacao'
import { useAssistenteStore } from '@/stores/assistente'
import { useSessaoStore } from '@/stores/sessao'
import { formatarNumero, plural } from '@/utils/formatos'
import CabecalhoPagina from '@/components/app/CabecalhoPagina.vue'
import IconeToqqiAI from '@/components/app/IconeToqqiAI.vue'
import Alerta from '@/components/ui/Alerta.vue'
import Botao from '@/components/ui/Botao.vue'
import Carregando from '@/components/ui/Carregando.vue'
import Etiqueta from '@/components/ui/Etiqueta.vue'
import Interruptor from '@/components/ui/Interruptor.vue'
import Medidor from '@/components/ui/Medidor.vue'
import { formatarMes } from '@/modulos/painel/logica'
import { TEMAS_PADRAO } from '@/modulos/respostas/logica'
import ComoIaEscreve from './ComoIaEscreve.vue'
import NavConfiguracoes from './NavConfiguracoes.vue'

const sessao = useSessaoStore()
const assistente = useAssistenteStore()
const dados = ref<ConfigIa | null>(null)
const carregando = ref(true)
const erroCarga = ref<string | null>(null)
const salvando = ref(false)
const analisando = ref(false)

/**
 * A cota do mesmo mês que o assistente recebeu depois da última leitura desta tela (cada resposta traz a sua): mais nova
 * que a de `dados`. Volta a null a cada leitura da tela.
 */
const cotaDoAssistente = ref<CotaIa | null>(null)
watch(
  () => assistente.cota,
  (c) => {
    if (c && c.mes === dados.value?.cota?.mes) cotaDoAssistente.value = c
  },
)

function receber(d: ConfigIa) {
  dados.value = d
  cotaDoAssistente.value = null
}

async function carregar() {
  carregando.value = true
  erroCarga.value = null
  try {
    receber(await iaApi.obter())
  } catch (e) {
    erroCarga.value = mensagemDoErro(e)
  } finally {
    carregando.value = false
  }
}

/** Busca os números de novo depois de uma ação, sem trocar a tela pelo esqueleto (se falhar, fica o que está na tela). */
async function atualizarNumeros() {
  try {
    receber(await iaApi.obter())
  } catch {
    /* os números antigos continuam */
  }
}

/** A sessão guarda `conta.ia_ativa` (filtros e caixas de IA nas outras telas): busca de novo depois de mudar. */
function atualizarSessao() {
  sessao.recarregar().catch(() => undefined)
}

async function mudarAnalise(ligar: boolean) {
  const d = dados.value
  if (!d || salvando.value) return
  if (!ligar && d.pendentes > 0) {
    const ok = await confirmar({
      titulo: 'Desligar a análise com IA?',
      mensagem: `${plural(d.pendentes, 'comentário está', 'comentários estão')} na fila e não ${d.pendentes === 1 ? 'vai ser analisado' : 'vão ser analisados'}: ${d.pendentes === 1 ? 'fica' : 'ficam'} com os temas pelas palavras-chave. As análises já feitas continuam.`,
      confirmar: 'Desligar',
      perigo: true,
    })
    if (!ok) return
  }
  salvando.value = true
  try {
    receber(await iaApi.salvar(ligar))
    avisar.sucesso(ligar ? 'Análise com IA ligada: os próximos comentários já passam por ela.' : 'Análise com IA desligada. Os temas voltam a sair pelas palavras-chave.')
    atualizarSessao()
  } catch (e) {
    avisar.erro(mensagemDoErro(e))
  } finally {
    salvando.value = false
  }
}

const mes = computed(() => (dados.value ? formatarMes(dados.value.mes, 'longo') : ''))
/**
 * Etapa 5b: cota do plano (gasta pelo ToqqiAI, pelo resumo do painel e pelo parecer dos relatórios). Se o assistente
 * recebeu uma cota do mesmo mês depois da leitura desta tela, vale a dele (a mais recente).
 */
const cota = computed(() => {
  const daTela = dados.value?.cota ?? null
  const doAssistente = cotaDoAssistente.value
  return daTela && doAssistente && doAssistente.mes === daTela.mes ? doAssistente : daTela
})
const textoCota = computed(() =>
  cota.value ? `${formatarNumero(cota.value.usadas)} de ${formatarNumero(cota.value.limite)} análises usadas em ${formatarMes(cota.value.mes, 'longo')}` : '',
)
const restantes = computed(() => (dados.value ? Math.max(0, dados.value.limite - dados.value.analises - dados.value.pendentes) : 0))
const noLimite = computed(() => !!dados.value && dados.value.limite > 0 && dados.value.analises >= dados.value.limite)
const podeAnalisarRecentes = computed(() => !!dados.value?.disponivel && !!dados.value?.analise_respostas)
/** Etapa 5d: a API manda o modelo, o estilo e os passos (a anterior não manda: a seção não aparece). */
const temEscrita = computed(
  () => !!dados.value && (Array.isArray(dados.value.modelos) || Array.isArray(dados.value.estilos) || typeof dados.value.passos_acoes === 'boolean'),
)

async function analisarRecentes() {
  if (!podeAnalisarRecentes.value || analisando.value) return
  const ok = await confirmar({
    titulo: 'Analisar os comentários dos últimos 90 dias?',
    mensagem: `Os comentários dos últimos 90 dias que ainda não têm análise (inclusive os importados) vão para a fila da IA, dos mais recentes para os mais antigos, até o limite do mês. Restam ${plural(restantes.value, 'análise', 'análises')} em ${mes.value}.`,
    confirmar: 'Analisar comentários',
  })
  if (!ok) return
  analisando.value = true
  try {
    const r = await iaApi.analisarRecentes()
    if (r.marcadas > 0) {
      avisar.sucesso(`${plural(r.marcadas, 'comentário foi', 'comentários foram')} para a fila. Restam ${plural(r.restantes_no_mes, 'análise', 'análises')} neste mês.`)
    } else {
      avisar.info(r.restantes_no_mes > 0 ? 'Nenhum comentário dos últimos 90 dias está sem análise.' : 'O limite deste mês já foi usado. Tente de novo quando o mês virar.')
    }
    atualizarNumeros()
  } catch (e) {
    avisar.erro(e instanceof ApiError ? e.mensagem : mensagemDoErro(e))
  } finally {
    analisando.value = false
  }
}

onMounted(carregar)
</script>

<template>
  <NavConfiguracoes />
  <CabecalhoPagina
    titulo="Inteligência artificial"
    descricao="A IA lê o comentário de cada cliente, resume o painel e os relatórios quando alguém pede, sugere passos nas ações e responde no ToqqiAI."
  />

  <Carregando v-if="carregando" :linhas="4" />
  <Alerta v-else-if="erroCarga" tom="erro">
    {{ erroCarga }} <button type="button" class="link ml-1" @click="carregar">Tentar de novo</button>
  </Alerta>

  <div v-else-if="dados" class="flex flex-col gap-6">
    <!-- Cota de IA do plano (etapa 5b) -->
    <section v-if="cota" class="cartao grid grid-cols-1 gap-6 p-5 sm:p-6 md:grid-cols-3" aria-labelledby="t-ia-cota" data-cota-plano>
      <div>
        <div class="mb-3 flex size-10 items-center justify-center rounded-xl bg-marca-suave text-marca-texto"><IconeToqqiAI class="size-5" /></div>
        <h2 id="t-ia-cota" class="text-base font-bold text-texto">Cota de IA do plano</h2>
        <p class="mt-1 text-sm text-texto-suave">Renova no dia 1º de cada mês.</p>
      </div>
      <div class="flex min-w-0 flex-col gap-3 md:col-span-2">
        <p class="text-sm text-texto-suave" data-cota-texto>
          <strong class="text-base font-bold text-texto">{{ formatarNumero(cota.usadas) }}</strong> de {{ formatarNumero(cota.limite) }} análises usadas em
          {{ formatarMes(cota.mes, 'longo') }}
        </p>
        <Medidor :valor="cota.usadas" :maximo="cota.limite" rotulo="Análises da cota do plano usadas neste mês" :texto="textoCota" />
        <p class="text-sm text-texto-suave">
          Cada pergunta ao ToqqiAI, cada resumo do painel e cada parecer dos relatórios usam 1 análise, ou 2 no modelo Mais detalhado. A
          análise de cada resposta e os passos das ações não entram nesta conta.
        </p>
        <Alerta v-if="cota.limite > 0 && cota.restantes <= 0" tom="atencao">
          A cota deste mês acabou: o ToqqiAI, o resumo do painel e o parecer dos relatórios voltam no dia 1º.
        </Alerta>
      </div>
    </section>

    <!-- Como a IA escreve (etapa 5d) -->
    <ComoIaEscreve v-if="temEscrita" :dados="dados" @salvo="receber" />

    <!-- Situação e a chave da conta -->
    <section class="cartao grid grid-cols-1 gap-6 p-5 sm:p-6 md:grid-cols-3" aria-labelledby="t-ia-situacao">
      <div>
        <div class="mb-3 flex size-10 items-center justify-center rounded-xl bg-marca-suave text-marca-texto"><Sparkles class="size-5" aria-hidden="true" /></div>
        <h2 id="t-ia-situacao" class="text-base font-bold text-texto">Análise dos comentários</h2>
        <p class="mt-1 text-sm text-texto-suave">Os temas da IA substituem os das palavras-chave. Os temas escolhidos à mão por alguém da equipe continuam.</p>
      </div>
      <div class="flex min-w-0 flex-col gap-4 md:col-span-2">
        <div class="flex flex-wrap items-center gap-2 text-sm">
          <span class="text-texto-suave">Na plataforma:</span>
          <Etiqueta v-if="dados.disponivel" tom="sucesso" ponto data-situacao-ia>Ligada{{ dados.provedor ? ` (${dados.provedor})` : '' }}</Etiqueta>
          <Etiqueta v-else tom="neutro" ponto data-situacao-ia>Não está ligada</Etiqueta>
        </div>
        <Alerta v-if="!dados.disponivel" tom="info">
          A plataforma ainda não tem a IA configurada. Enquanto isso, os temas continuam saindo pelas palavras-chave dos comentários.
        </Alerta>
        <Interruptor
          :model-value="dados.analise_respostas"
          rotulo="Analisar comentários com IA"
          descricao="Cada comentário novo ganha um resumo, o sentimento geral (positivo, neutro, negativo ou misto) e os temas com o sentimento do cliente sobre cada um."
          :desabilitado="salvando || !dados.disponivel"
          @update:model-value="mudarAnalise"
        />
        <p v-if="dados.disponivel && !dados.analise_respostas" class="text-sm text-texto-fraco">Desligada nesta conta: os temas saem pelas palavras-chave.</p>
      </div>
    </section>

    <!-- Uso do mês -->
    <section class="cartao grid grid-cols-1 gap-6 p-5 sm:p-6 md:grid-cols-3" aria-labelledby="t-ia-uso">
      <div>
        <div class="mb-3 flex size-10 items-center justify-center rounded-xl bg-marca-suave text-marca-texto"><Gauge class="size-5" aria-hidden="true" /></div>
        <h2 id="t-ia-uso" class="text-base font-bold text-texto">Uso do mês</h2>
        <p class="mt-1 text-sm text-texto-suave">
          A análise de cada resposta e os passos sugeridos nas ações não gastam a cota de IA do plano. Este limite de segurança protege a conta de um
          uso fora do normal.
        </p>
      </div>
      <div class="flex min-w-0 flex-col gap-4 md:col-span-2">
        <div class="flex flex-col gap-2">
          <p class="flex flex-wrap items-baseline justify-between gap-x-3 text-sm">
            <span class="font-semibold text-texto first-letter:uppercase">{{ mes }}</span>
            <span class="text-texto-suave">
              <strong class="text-base font-bold text-texto">{{ formatarNumero(dados.analises) }}</strong> de {{ formatarNumero(dados.limite) }} análises
            </span>
          </p>
          <Medidor :valor="dados.analises" :maximo="dados.limite" rotulo="Análises usadas neste mês" :texto="`${formatarNumero(dados.analises)} de ${formatarNumero(dados.limite)} análises`" />
        </div>
        <Alerta v-if="noLimite" tom="atencao">
          Limite do mês atingido: até o mês virar, as respostas novas ficam com os temas pelas palavras-chave e as ações novas, sem passos sugeridos.
        </Alerta>
        <dl class="grid grid-cols-2 gap-3 text-sm sm:grid-cols-3">
          <div class="rounded-xl bg-superficie-2 p-3">
            <dt class="text-texto-fraco">Na fila</dt>
            <dd class="text-lg font-bold text-texto">{{ formatarNumero(dados.pendentes) }}</dd>
          </div>
          <div class="rounded-xl bg-superficie-2 p-3">
            <dt class="text-texto-fraco">Não deu certo no mês</dt>
            <dd class="text-lg font-bold text-texto">{{ formatarNumero(dados.falharam_no_mes) }}</dd>
          </div>
          <div class="rounded-xl bg-superficie-2 p-3">
            <dt class="text-texto-fraco">Ainda dá para analisar</dt>
            <dd class="text-lg font-bold text-texto">{{ formatarNumero(restantes) }}</dd>
          </div>
        </dl>
      </div>
    </section>

    <!-- Comentários antigos -->
    <section class="cartao grid grid-cols-1 gap-6 p-5 sm:p-6 md:grid-cols-3" aria-labelledby="t-ia-antigos">
      <div>
        <div class="mb-3 flex size-10 items-center justify-center rounded-xl bg-marca-suave text-marca-texto"><History class="size-5" aria-hidden="true" /></div>
        <h2 id="t-ia-antigos" class="text-base font-bold text-texto">Comentários antigos</h2>
        <p class="mt-1 text-sm text-texto-suave">As respostas importadas e as que chegaram antes de ligar a IA ficam sem análise. Dá para mandar as dos últimos 90 dias.</p>
      </div>
      <div class="flex min-w-0 flex-col items-start gap-3 md:col-span-2">
        <p class="text-sm text-texto-suave">
          Vão para a fila os comentários dos últimos 90 dias que ainda não têm análise (inclusive os importados), dos mais recentes para os mais
          antigos, até o limite do mês.
        </p>
        <!-- No celular, ocupa a largura toda e quebra linha (o texto é longo para uma linha só). -->
        <Botao
          variante="secundario"
          class="!h-auto min-h-10 w-full !whitespace-normal py-2 text-center sm:w-auto"
          :carregando="analisando"
          :desabilitado="!podeAnalisarRecentes || restantes === 0"
          @click="analisarRecentes"
        >
          <History v-if="!analisando" class="size-4 shrink-0" aria-hidden="true" /> Analisar comentários dos últimos 90 dias
        </Botao>
        <p v-if="!podeAnalisarRecentes" class="text-sm text-texto-fraco">
          {{ dados.disponivel ? 'Ligue "Analisar comentários com IA" para usar.' : 'Disponível quando a IA estiver ligada na plataforma.' }}
        </p>
        <p v-else-if="restantes === 0" class="text-sm text-texto-fraco">O limite deste mês já foi usado (contando a fila).</p>
      </div>
    </section>

    <!-- O que é enviado: na análise de cada comentário, nos passos das ações, no resumo e no parecer e no assistente -->
    <section class="cartao grid grid-cols-1 gap-6 p-5 sm:p-6 md:grid-cols-3" aria-labelledby="t-ia-privacidade" data-ia-privacidade>
      <div>
        <div class="mb-3 flex size-10 items-center justify-center rounded-xl bg-marca-suave text-marca-texto"><ShieldCheck class="size-5" aria-hidden="true" /></div>
        <h2 id="t-ia-privacidade" class="text-base font-bold text-texto">O que é enviado à IA</h2>
        <p class="mt-1 text-sm text-texto-suave">Só o necessário para cada recurso.</p>
      </div>
      <div class="flex min-w-0 flex-col gap-5 md:col-span-2">
        <div class="flex flex-col gap-2" data-envio-analise>
          <h3 class="text-sm font-bold text-texto">Na análise dos comentários</h3>
          <ul class="flex list-disc flex-col gap-2 pl-5 text-sm text-texto">
            <li>O texto que o cliente escreveu (até 500 caracteres), as opções que ele marcou e a nota.</li>
            <li><strong class="font-semibold">Nunca</strong> o nome, o e-mail, o telefone, a empresa do cliente ou os dados do pedido.</li>
            <li>O provedor{{ dados.provedor ? ` (${dados.provedor})` : '' }} não guarda a conversa.</li>
            <li>Os temas saem só desta lista: {{ TEMAS_PADRAO.map((t) => t.rotulo).join(', ') }}.</li>
          </ul>
        </div>
        <div class="flex flex-col gap-2" data-envio-passos>
          <h3 class="text-sm font-bold text-texto">Nos passos das ações</h3>
          <ul class="flex list-disc flex-col gap-2 pl-5 text-sm text-texto">
            <li>O tipo, a nota e o grupo da resposta, o comentário do cliente (até 500 caracteres) e as opções que ele marcou.</li>
            <li>As últimas 5 respostas da mesma empresa: data, tipo, nota e comentário (até 300 caracteres).</li>
            <li><strong class="font-semibold">Nunca</strong> o nome da empresa ou do contato, o e-mail, o telefone ou os dados do pedido.</li>
          </ul>
        </div>
        <div class="flex flex-col gap-2" data-envio-resumo>
          <h3 class="text-sm font-bold text-texto">No resumo do painel e no parecer dos relatórios</h3>
          <ul class="flex list-disc flex-col gap-2 pl-5 text-sm text-texto">
            <li>
              Só quando alguém pede: o nome da sua conta, os números do período e dos filtros da tela (com o nome do grupo escolhido) e nomes de
              empresas e de responsáveis.
            </li>
            <li>No resumo, até 8 comentários do período (até 300 caracteres), sem o nome, o e-mail ou o telefone de quem respondeu.</li>
            <li>O texto gerado fica guardado na conta até alguém gerar de novo com os mesmos filtros.</li>
          </ul>
        </div>
        <div class="flex flex-col gap-2" data-envio-assistente>
          <h3 class="text-sm font-bold text-texto">No ToqqiAI</h3>
          <ul class="flex list-disc flex-col gap-2 pl-5 text-sm text-texto">
            <li>A pergunta, as últimas mensagens da conversa e o nome da sua conta.</li>
            <li>Os dados que ele consulta para responder: números, nomes de empresas e de contatos e comentários dos clientes.</li>
            <li>O provedor{{ dados.provedor ? ` (${dados.provedor})` : '' }} não guarda a conversa.</li>
          </ul>
        </div>
      </div>
    </section>
  </div>
</template>

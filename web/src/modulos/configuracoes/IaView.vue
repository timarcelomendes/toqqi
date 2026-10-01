<script setup lang="ts">
// Configurações › IA (etapa 4b): se a IA está ligada na plataforma, a chave da conta ("Analisar comentários com
// IA"), o uso do mês contra o teto de segurança, a fila, o "analisar os últimos 90 dias" e o que vai para a IA.
import { computed, onMounted, ref } from 'vue'
import { Gauge, History, ShieldCheck, Sparkles } from 'lucide-vue-next'
import { ApiError, iaApi, mensagemDoErro, type ConfigIa } from '@/api'
import { avisar } from '@/composables/avisos'
import { confirmar } from '@/composables/confirmacao'
import { useSessaoStore } from '@/stores/sessao'
import { formatarNumero, plural } from '@/utils/formatos'
import CabecalhoPagina from '@/components/app/CabecalhoPagina.vue'
import Alerta from '@/components/ui/Alerta.vue'
import Botao from '@/components/ui/Botao.vue'
import Carregando from '@/components/ui/Carregando.vue'
import Etiqueta from '@/components/ui/Etiqueta.vue'
import Interruptor from '@/components/ui/Interruptor.vue'
import Medidor from '@/components/ui/Medidor.vue'
import { formatarMes } from '@/modulos/painel/logica'
import { TEMAS_PADRAO } from '@/modulos/respostas/logica'
import NavConfiguracoes from './NavConfiguracoes.vue'

const sessao = useSessaoStore()
const dados = ref<ConfigIa | null>(null)
const carregando = ref(true)
const erroCarga = ref<string | null>(null)
const salvando = ref(false)
const analisando = ref(false)

async function carregar() {
  carregando.value = true
  erroCarga.value = null
  try {
    dados.value = await iaApi.obter()
  } catch (e) {
    erroCarga.value = mensagemDoErro(e)
  } finally {
    carregando.value = false
  }
}

/** Busca os números de novo depois de uma ação, sem trocar a tela pelo esqueleto (se falhar, fica o que está na tela). */
async function atualizarNumeros() {
  try {
    dados.value = await iaApi.obter()
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
    dados.value = await iaApi.salvar(ligar)
    avisar.sucesso(ligar ? 'Análise com IA ligada: os próximos comentários já passam por ela.' : 'Análise com IA desligada. Os temas voltam a sair pelas palavras-chave.')
    atualizarSessao()
  } catch (e) {
    avisar.erro(mensagemDoErro(e))
  } finally {
    salvando.value = false
  }
}

const mes = computed(() => (dados.value ? formatarMes(dados.value.mes, 'longo') : ''))
const restantes = computed(() => (dados.value ? Math.max(0, dados.value.limite - dados.value.analises - dados.value.pendentes) : 0))
const noLimite = computed(() => !!dados.value && dados.value.limite > 0 && dados.value.analises >= dados.value.limite)
const podeAnalisarRecentes = computed(() => !!dados.value?.disponivel && !!dados.value?.analise_respostas)

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
    descricao="A IA lê o comentário de cada cliente, resume numa frase e diz o sentimento geral e os temas citados, com o sentimento sobre cada um."
  />

  <Carregando v-if="carregando" :linhas="4" />
  <Alerta v-else-if="erroCarga" tom="erro">
    {{ erroCarga }} <button type="button" class="link ml-1" @click="carregar">Tentar de novo</button>
  </Alerta>

  <div v-else-if="dados" class="flex flex-col gap-6">
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
        <p class="mt-1 text-sm text-texto-suave">A análise de cada resposta não gasta a cota de IA do plano. O limite de segurança protege a conta de um uso fora do normal.</p>
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
        <Alerta v-if="noLimite" tom="atencao">Limite do mês atingido: as respostas novas ficam com os temas pelas palavras-chave até o mês virar.</Alerta>
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

    <!-- O que é enviado -->
    <section class="cartao grid grid-cols-1 gap-6 p-5 sm:p-6 md:grid-cols-3" aria-labelledby="t-ia-privacidade">
      <div>
        <div class="mb-3 flex size-10 items-center justify-center rounded-xl bg-marca-suave text-marca-texto"><ShieldCheck class="size-5" aria-hidden="true" /></div>
        <h2 id="t-ia-privacidade" class="text-base font-bold text-texto">O que é enviado à IA</h2>
        <p class="mt-1 text-sm text-texto-suave">Só o necessário para entender o comentário.</p>
      </div>
      <div class="min-w-0 md:col-span-2">
        <ul class="flex list-disc flex-col gap-2 pl-5 text-sm text-texto">
          <li>O texto que o cliente escreveu (até 500 caracteres), as opções que ele marcou e a nota.</li>
          <li><strong class="font-semibold">Nunca</strong> o nome, o e-mail, o telefone, a empresa do cliente ou os dados do pedido.</li>
          <li>O provedor{{ dados.provedor ? ` (${dados.provedor})` : '' }} não guarda a conversa.</li>
          <li>Os temas saem só desta lista: {{ TEMAS_PADRAO.map((t) => t.rotulo).join(', ') }}.</li>
        </ul>
      </div>
    </section>
  </div>
</template>

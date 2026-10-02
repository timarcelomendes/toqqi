<script setup lang="ts">
import { computed, nextTick, onMounted, reactive, ref, watch } from 'vue'
import { onBeforeRouteLeave } from 'vue-router'
import { CalendarClock, FileText, Heart, Mail, MessageCircle, Power, Radio, Repeat, Send, UserRound } from 'lucide-vue-next'
import {
  enviosApi,
  formulariosApi,
  mensagemDoErro,
  whatsappAutomaticoApi,
  type CanalConfig,
  type ConfigEnvios,
  type FormularioResumo,
  type Id,
  type WhatsappIntegracao,
} from '@/api'
import { avisar } from '@/composables/avisos'
import { confirmar } from '@/composables/confirmacao'
import { useFormulario } from '@/composables/formulario'
import { useSessaoStore } from '@/stores/sessao'
import { CANAIS_CONFIG } from '@/utils/rotulos'
import { avisoCanal, disponibilidadeCanais, estadoFranquia } from '@/modulos/integracoes/logica'
import CabecalhoPagina from '@/components/app/CabecalhoPagina.vue'
import Alerta from '@/components/ui/Alerta.vue'
import Botao from '@/components/ui/Botao.vue'
import Campo from '@/components/ui/Campo.vue'
import Carregando from '@/components/ui/Carregando.vue'
import Interruptor from '@/components/ui/Interruptor.vue'
import Selecao from '@/components/ui/Selecao.vue'
import CampoMensagem from './CampoMensagem.vue'
import NavConfiguracoes from './NavConfiguracoes.vue'
import PreviaEmail from './PreviaEmail.vue'
import {
  LIMITE_ASSUNTO,
  LIMITE_TEXTO,
  VARIAVEIS_AGRADECIMENTO,
  VARIAVEIS_EMAIL,
  VARIAVEIS_WHATSAPP,
  ajustarDiasLembretes,
  montarPreviaEmail,
  normalizarCampos,
  renderizarMensagem,
  validarConfig,
} from './mensagens'

const sessao = useSessaoStore()
const podeSalvar = computed(() => sessao.pode('configuracoes.gerenciar'))

const carregando = ref(true)
const erroCarga = ref<string | null>(null)
const original = ref<string>('')
const formularios = ref<FormularioResumo[]>([])
const { enviando, erroGeral, erros, executar, limpar } = useFormulario()
const testando = ref(false)
const previaAtual = ref<'convite' | 'lembrete' | 'whatsapp'>('convite')

const f = reactive<ConfigEnvios>({
  envios_ativos: false,
  envio_automatico: false,
  formulario_id: null,
  intervalo_dias: 90,
  descanso_dias: 30,
  lembretes: 3,
  dias_lembretes: [3, 7, 15],
  janela_inicio: '08:00',
  janela_fim: '18:00',
  so_dias_uteis: true,
  responder_para: null,
  remetente_nome: null,
  assunto_convite: '',
  texto_convite: '',
  assunto_lembrete: '',
  texto_lembrete: '',
  texto_whatsapp: '',
  agradecimento_ativo: true,
  agradecimento: { promotor: '', neutro: '', detrator: '' },
  canal: 'email',
})
// Números editados como texto (o campo pode ficar vazio enquanto a pessoa digita).
const num = reactive({ intervalo: '90', descanso: '30', dias: ['3', '7', '15'] as string[] })

const inteiro = (v: string) => (/^\s*\d+\s*$/.test(v) ? Number.parseInt(v, 10) : Number.NaN)

/** Configuração pronta para salvar (junta os números digitados). */
function montar(): ConfigEnvios {
  return {
    ...f,
    agradecimento: { ...f.agradecimento },
    intervalo_dias: inteiro(num.intervalo),
    descanso_dias: inteiro(num.descanso),
    dias_lembretes: num.dias.slice(0, f.lembretes).map(inteiro),
    remetente_nome: f.remetente_nome?.trim() || null,
    responder_para: f.responder_para?.trim() || null,
  }
}

function aplicar(c: ConfigEnvios) {
  Object.assign(f, { ...c, canal: c.canal ?? 'email', agradecimento: { ...c.agradecimento }, dias_lembretes: [...(c.dias_lembretes ?? [])] })
  num.intervalo = String(c.intervalo_dias)
  num.descanso = String(c.descanso_dias)
  num.dias = ajustarDiasLembretes(c.dias_lembretes ?? [], c.lembretes).map(String)
  original.value = JSON.stringify(montar())
}

const alterado = computed(() => !!original.value && JSON.stringify(montar()) !== original.value)

// Ao mudar a quantidade de lembretes, completa ou corta os dias.
watch(
  () => f.lembretes,
  (n) => {
    const atuais = num.dias.map(inteiro).filter((d) => Number.isFinite(d))
    num.dias = ajustarDiasLembretes(atuais, Number(n)).map(String)
  },
)

const formularioSel = computed<Id | ''>({
  get: () => f.formulario_id ?? '',
  set: (v) => (f.formulario_id = v === '' ? null : v),
})
const opcoesFormularios = computed(() => {
  const ativos = formularios.value.filter((x) => x.ativo)
  const opcoes = ativos.map((x) => ({ valor: x.id, rotulo: x.nome + (x.padrao_nps ? ' (padrão NPS)' : x.padrao_csat ? ' (padrão CSAT)' : '') }))
  // O escolhido pode estar inativo/arquivado: aparece para a pessoa entender e trocar.
  if (f.formulario_id !== null && !ativos.some((x) => String(x.id) === String(f.formulario_id))) {
    const atual = formularios.value.find((x) => String(x.id) === String(f.formulario_id))
    opcoes.unshift({ valor: f.formulario_id, rotulo: `${atual?.nome ?? 'Formulário atual'} (desativado)` })
  }
  return opcoes
})
const tipoFormulario = computed(() => formularios.value.find((x) => String(x.id) === String(f.formulario_id))?.tipo_principal ?? 'nps')

// Canal: WhatsApp só fica disponível com o WhatsApp automático conectado (GET /integracoes/whatsapp).
const whatsapp = ref<WhatsappIntegracao | null>(null)
const canais = Object.keys(CANAIS_CONFIG) as CanalConfig[]
const disponiveis = computed(() => disponibilidadeCanais(whatsapp.value))
const aviso = computed(() => avisoCanal(f.canal, whatsapp.value))
const franquiaWhatsapp = computed(() => (whatsapp.value?.conectado ? estadoFranquia(whatsapp.value.franquia) : null))

const opcoesLembretes = [
  { valor: 0, rotulo: 'Nenhum lembrete' },
  { valor: 1, rotulo: '1 lembrete' },
  { valor: 2, rotulo: '2 lembretes' },
  { valor: 3, rotulo: '3 lembretes' },
]

const exemplo = computed(() => ({
  nome: 'Maria Silva',
  empresa: sessao.conta?.nome ?? 'Sua empresa',
  empresa_cliente: 'Mercado Bom Preço',
  link: `${window.location.origin}/r/exemplo`,
}))
// Logo do cabeçalho do e-mail: o do formulário dos convites; sem ele, o da empresa (como no e-mail de verdade).
const logoFormulario = ref<string | null>(null)
watch(
  () => f.formulario_id,
  async (id) => {
    logoFormulario.value = null
    if (!id || !sessao.pode('formularios.ver')) return
    try {
      const form = await formulariosApi.obter(id)
      if (String(f.formulario_id) === String(id)) logoFormulario.value = form.tema?.logo_url ?? null
    } catch {
      /* sem o formulário, a prévia usa o logo da empresa */
    }
  },
  { immediate: true },
)
const previaEmail = computed(() =>
  montarPreviaEmail(
    f,
    previaAtual.value === 'lembrete' ? 'lembrete' : 'convite',
    tipoFormulario.value,
    exemplo.value,
    logoFormulario.value || sessao.conta?.logo_url || null,
  ),
)
const dicaRemetente = computed(() => `Aparece como "${(f.remetente_nome || sessao.conta?.nome || 'Sua empresa').trim()} via Toqqi".`)
const textoWhatsapp = computed(() => renderizarMensagem(f.texto_whatsapp, exemplo.value))
const partesWhatsapp = computed(() => {
  const link = exemplo.value.link
  const t = textoWhatsapp.value
  const i = t.indexOf(link)
  return i < 0 ? { antes: t, link: '', depois: '' } : { antes: t.slice(0, i), link, depois: t.slice(i + link.length) }
})

async function carregar() {
  carregando.value = true
  erroCarga.value = null
  try {
    const [c] = await Promise.all([
      enviosApi.configuracao(),
      whatsappAutomaticoApi
        .obter()
        .then((w) => (whatsapp.value = w))
        .catch(() => (whatsapp.value = null)),
      sessao.pode('formularios.ver')
        ? formulariosApi
            .listar()
            .then((l) => (formularios.value = l))
            .catch(() => undefined)
        : Promise.resolve(),
    ])
    aplicar(c)
  } catch (e) {
    erroCarga.value = mensagemDoErro(e)
  } finally {
    carregando.value = false
  }
}

async function focarPrimeiroErro() {
  await nextTick()
  document.querySelector<HTMLElement>('#form-config-envios [aria-invalid="true"]')?.focus()
}

async function salvar(): Promise<boolean> {
  limpar()
  const dados = montar()
  const locais = validarConfig(dados)
  if (Object.keys(locais).length) {
    Object.assign(erros, locais)
    erroGeral.value = 'Confira os campos destacados.'
    focarPrimeiroErro()
    return false
  }
  const r = await executar(() => enviosApi.salvarConfiguracao(dados))
  if (!r) {
    const campos = normalizarCampos({ ...erros })
    for (const k of Object.keys(erros)) delete erros[k]
    Object.assign(erros, campos)
    if (Object.keys(campos).length) focarPrimeiroErro()
    return false
  }
  aplicar(r)
  avisar.sucesso('Configurações de envio salvas.')
  return true
}

function descartar() {
  if (original.value) aplicar(JSON.parse(original.value) as ConfigEnvios)
  limpar()
}

async function enviarTeste() {
  if (alterado.value) {
    const ok = await confirmar({
      titulo: 'Salvar antes de enviar o exemplo?',
      mensagem: 'O exemplo usa os textos salvos. Vamos salvar suas alterações e depois enviar.',
      confirmar: 'Salvar e enviar',
    })
    if (!ok || !(await salvar())) return
  }
  testando.value = true
  try {
    const r = await enviosApi.enviarTeste()
    avisar.sucesso(r?.mensagem || 'Enviamos um exemplo para o seu e-mail.')
  } catch (e) {
    avisar.erro(mensagemDoErro(e))
  } finally {
    testando.value = false
  }
}

onBeforeRouteLeave(async () => {
  if (!alterado.value || enviando.value) return true
  return confirmar({
    titulo: 'Sair sem salvar?',
    mensagem: 'Você mudou as configurações de envio e ainda não salvou. Se sair agora, as mudanças se perdem.',
    confirmar: 'Sair sem salvar',
    cancelar: 'Continuar editando',
    perigo: true,
  })
})

onMounted(carregar)
</script>

<template>
  <NavConfiguracoes />
  <CabecalhoPagina titulo="Configurações de envio" descricao="Quando, com que frequência e com quais palavras a pesquisa chega aos seus clientes.">
    <template v-if="podeSalvar && !carregando && !erroCarga" #acoes>
      <Botao variante="secundario" :carregando="testando" :desabilitado="enviando" @click="enviarTeste">
        <Mail v-if="!testando" class="size-4" aria-hidden="true" /> Enviar um exemplo para mim
      </Botao>
    </template>
  </CabecalhoPagina>

  <Carregando v-if="carregando" :linhas="4" />
  <Alerta v-else-if="erroCarga" tom="erro">
    {{ erroCarga }} <button type="button" class="link ml-1" @click="carregar">Tentar de novo</button>
  </Alerta>

  <form v-else id="form-config-envios" class="flex flex-col gap-6" novalidate @submit.prevent="salvar">
    <Alerta v-if="!podeSalvar" tom="info">Você pode ver as configurações, mas só um administrador consegue mudar.</Alerta>
    <Alerta v-if="erroGeral" tom="erro">{{ erroGeral }}</Alerta>

    <fieldset :disabled="!podeSalvar" class="flex min-w-0 flex-col gap-6">
      <legend class="sr-only">Configurações de envio</legend>

      <!-- Ligar e desligar -->
      <section class="cartao grid gap-6 p-5 sm:p-6 md:grid-cols-3" aria-labelledby="t-ligar">
        <div>
          <div class="mb-3 flex size-10 items-center justify-center rounded-xl bg-marca-suave text-marca-texto"><Power class="size-5" aria-hidden="true" /></div>
          <h2 id="t-ligar" class="text-base font-bold text-texto">Ligar os envios</h2>
          <p class="mt-1 text-sm text-texto-suave">Comece desligado, confira os textos e envie um exemplo para você antes de ligar.</p>
        </div>
        <div class="flex flex-col gap-5 md:col-span-2">
          <Interruptor
            v-model="f.envios_ativos"
            rotulo="Enviar pesquisas por e-mail"
            descricao="É a chave geral. Desligada, nenhuma pesquisa ou lembrete sai por e-mail, nem pelo botão Enviar agora."
          />
          <Interruptor
            v-model="f.envio_automatico"
            rotulo="Envio automático"
            descricao="O Toqqi manda a pesquisa sozinho para quem está na fila, dentro do horário escolhido abaixo. Desligado, você envia quando quiser pela tela Envios."
          />
          <p v-if="f.envio_automatico && !f.envios_ativos" class="text-sm text-atencao">
            O envio automático só funciona com "Enviar pesquisas por e-mail" ligado.
          </p>
        </div>
      </section>

      <!-- Canal -->
      <section class="cartao grid gap-6 p-5 sm:p-6 md:grid-cols-3" aria-labelledby="t-canal">
        <div>
          <div class="mb-3 flex size-10 items-center justify-center rounded-xl bg-marca-suave text-marca-texto"><Radio class="size-5" aria-hidden="true" /></div>
          <h2 id="t-canal" class="text-base font-bold text-texto">Por onde a pesquisa sai</h2>
          <p class="mt-1 text-sm text-texto-suave">Vale para o envio automático, o botão Enviar agora e os pedidos que chegam do sistema da sua empresa.</p>
        </div>
        <div class="flex flex-col gap-4 md:col-span-2">
          <fieldset :aria-describedby="erros.canal ? 'erro-canal' : undefined">
            <legend class="sr-only">Canal das pesquisas</legend>
            <div class="grid gap-2 lg:grid-cols-3">
              <label
                v-for="c in canais"
                :key="c"
                class="relative flex flex-col gap-1 rounded-xl border p-4 transition-colors has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-offset-2 has-[:focus-visible]:outline-foco"
                :class="[
                  f.canal === c ? 'border-marca bg-marca-suave' : 'border-borda-forte',
                  disponiveis[c].disponivel && podeSalvar ? 'cursor-pointer hover:bg-superficie-2' : 'cursor-not-allowed',
                  !disponiveis[c].disponivel && f.canal !== c ? 'opacity-60' : '',
                ]"
              >
                <input v-model="f.canal" type="radio" name="canal" :value="c" class="sr-only" :disabled="!disponiveis[c].disponivel" />
                <span class="flex items-center gap-2 text-sm font-bold text-texto">
                  <Mail v-if="c === 'email'" class="size-4 text-texto-fraco" aria-hidden="true" />
                  <MessageCircle v-else class="size-4 text-emerald-700" aria-hidden="true" />
                  {{ CANAIS_CONFIG[c].rotulo }}
                </span>
                <span v-if="CANAIS_CONFIG[c].recomendado" class="w-fit rounded-full bg-sucesso-suave px-2 py-0.5 text-[0.7rem] font-semibold text-sucesso">Recomendado</span>
                <span class="text-sm text-texto-suave">{{ CANAIS_CONFIG[c].descricao }}</span>
                <span v-if="disponiveis[c].motivo" class="text-xs font-medium text-texto-fraco">{{ disponiveis[c].motivo }}</span>
              </label>
            </div>
            <p v-if="erros.canal" id="erro-canal" class="mt-1.5 text-sm font-medium text-erro">{{ erros.canal }}</p>
          </fieldset>
          <Alerta v-if="aviso" tom="atencao">{{ aviso }}</Alerta>
          <p v-if="whatsapp && !whatsapp.conectado" class="text-sm text-texto-suave">
            Quer mandar pelo WhatsApp sem ninguém precisar apertar Enviar?
            <RouterLink v-if="sessao.admin" to="/integracoes?aba=whatsapp" class="link">Conecte o WhatsApp em Integrações</RouterLink>
            <template v-else>Peça a um administrador para conectar o WhatsApp em Integrações.</template>
          </p>
          <p v-else-if="franquiaWhatsapp" class="text-sm text-texto-suave">
            WhatsApp automático: {{ franquiaWhatsapp.resumo }}. Lembretes: só o primeiro vai pelo WhatsApp; os outros vão por e-mail.
          </p>
        </div>
      </section>

      <!-- Formulário -->
      <section class="cartao grid gap-6 p-5 sm:p-6 md:grid-cols-3" aria-labelledby="t-formulario">
        <div>
          <div class="mb-3 flex size-10 items-center justify-center rounded-xl bg-marca-suave text-marca-texto"><FileText class="size-5" aria-hidden="true" /></div>
          <h2 id="t-formulario" class="text-base font-bold text-texto">Pesquisa enviada</h2>
          <p class="mt-1 text-sm text-texto-suave">O formulário que o cliente responde ao abrir o e-mail.</p>
        </div>
        <div class="md:col-span-2 md:max-w-md">
          <Selecao
            v-if="opcoesFormularios.length"
            v-model="formularioSel"
            rotulo="Formulário do convite"
            :opcoes="opcoesFormularios"
            :vazio="f.formulario_id === null ? 'Escolha um formulário' : undefined"
            :erro="erros.formulario_id"
            dica="Só aparecem formulários ativos."
          />
          <template v-else>
            <p class="text-sm text-texto-suave">Não conseguimos listar os formulários. Veja em <RouterLink to="/formularios" class="link">Formulários</RouterLink>.</p>
            <p v-if="erros.formulario_id" class="mt-1 text-sm font-medium text-erro">{{ erros.formulario_id }}</p>
          </template>
        </div>
      </section>

      <!-- Frequência -->
      <section class="cartao grid gap-6 p-5 sm:p-6 md:grid-cols-3" aria-labelledby="t-frequencia">
        <div>
          <div class="mb-3 flex size-10 items-center justify-center rounded-xl bg-marca-suave text-marca-texto"><Repeat class="size-5" aria-hidden="true" /></div>
          <h2 id="t-frequencia" class="text-base font-bold text-texto">Frequência</h2>
          <p class="mt-1 text-sm text-texto-suave">Para ouvir o cliente sem incomodar.</p>
        </div>
        <div class="grid gap-5 sm:grid-cols-2 md:col-span-2">
          <Campo
            v-model="num.intervalo"
            rotulo="Repetir a pesquisa a cada (dias)"
            tipo="number"
            inputmode="numeric"
            min="30"
            max="365"
            :erro="erros.intervalo_dias"
            dica="Depois de receber, a pessoa volta para a fila depois desses dias. Entre 30 e 365."
          />
          <Campo
            v-model="num.descanso"
            rotulo="Descanso entre pesquisas (dias)"
            tipo="number"
            inputmode="numeric"
            min="0"
            max="180"
            :erro="erros.descanso_dias"
            dica="Anti-cansaço: quem recebeu qualquer pesquisa, por e-mail ou WhatsApp, há menos desses dias não recebe outra. Use 0 para desligar."
          />
          <div class="flex flex-col gap-3 sm:col-span-2">
            <div class="sm:max-w-xs">
              <Selecao
                v-model="f.lembretes"
                rotulo="Lembretes para quem não respondeu"
                :opcoes="opcoesLembretes"
                :erro="erros.lembretes"
              />
            </div>
            <fieldset v-if="f.lembretes > 0" class="flex flex-col gap-2" :aria-describedby="erros.dias_lembretes ? 'erro-dias-lembretes' : 'dica-dias-lembretes'">
              <legend class="mb-1 text-sm font-semibold text-texto">Quando cada lembrete sai</legend>
              <div class="flex flex-wrap gap-3">
                <label v-for="(_, i) in num.dias.slice(0, f.lembretes)" :key="i" class="flex items-center gap-2 text-sm text-texto-suave">
                  <span class="font-semibold text-texto">{{ i + 1 }}º:</span>
                  <input
                    v-model="num.dias[i]"
                    type="number"
                    inputmode="numeric"
                    min="1"
                    max="30"
                    :aria-label="`${i + 1}º lembrete: dias depois do convite`"
                    :aria-invalid="erros.dias_lembretes ? 'true' : undefined"
                    class="h-11 w-20 rounded-xl border bg-superficie px-3 text-center text-[0.95rem] text-texto focus:outline-none focus:ring-3 disabled:bg-superficie-2"
                    :class="erros.dias_lembretes ? 'border-erro focus:ring-erro/20' : 'border-borda-forte focus:border-marca focus:ring-marca/20'"
                  />
                  dias depois
                </label>
              </div>
              <p v-if="erros.dias_lembretes" id="erro-dias-lembretes" class="text-sm font-medium text-erro">{{ erros.dias_lembretes }}</p>
              <p id="dica-dias-lembretes" class="text-sm text-texto-fraco">Contando a partir do dia em que a pesquisa foi enviada. Entre 1 e 30, cada um depois do anterior.</p>
            </fieldset>
          </div>
        </div>
      </section>

      <!-- Horário -->
      <section class="cartao grid gap-6 p-5 sm:p-6 md:grid-cols-3" aria-labelledby="t-horario">
        <div>
          <div class="mb-3 flex size-10 items-center justify-center rounded-xl bg-marca-suave text-marca-texto"><CalendarClock class="size-5" aria-hidden="true" /></div>
          <h2 id="t-horario" class="text-base font-bold text-texto">Horário de envio</h2>
          <p class="mt-1 text-sm text-texto-suave">O envio automático e os lembretes só saem neste horário (de Brasília).</p>
        </div>
        <div class="flex flex-col gap-5 md:col-span-2">
          <div class="grid grid-cols-2 gap-3 sm:max-w-sm">
            <Campo v-model="f.janela_inicio" rotulo="Das" tipo="time" :erro="erros.janela_inicio" />
            <Campo v-model="f.janela_fim" rotulo="Até" tipo="time" :erro="erros.janela_fim" />
          </div>
          <Interruptor v-model="f.so_dias_uteis" rotulo="Só de segunda a sexta" descricao="Sem envios automáticos nem lembretes no fim de semana." />
        </div>
      </section>

      <!-- Remetente -->
      <section class="cartao grid gap-6 p-5 sm:p-6 md:grid-cols-3" aria-labelledby="t-remetente">
        <div>
          <div class="mb-3 flex size-10 items-center justify-center rounded-xl bg-marca-suave text-marca-texto"><UserRound class="size-5" aria-hidden="true" /></div>
          <h2 id="t-remetente" class="text-base font-bold text-texto">Quem envia</h2>
          <p class="mt-1 text-sm text-texto-suave">Como o seu cliente vê o remetente do e-mail.</p>
        </div>
        <div class="grid gap-5 sm:grid-cols-2 md:col-span-2">
          <Campo
            :model-value="f.remetente_nome ?? ''"
            rotulo="Nome do remetente"
            opcional
            maxlength="100"
            :placeholder="sessao.conta?.nome"
            :erro="erros.remetente_nome"
            :dica="dicaRemetente"
            @update:model-value="(v: string) => (f.remetente_nome = v)"
          />
          <Campo
            :model-value="f.responder_para ?? ''"
            rotulo="Respostas por e-mail vão para"
            tipo="email"
            opcional
            autocomplete="email"
            placeholder="atendimento@suaempresa.com.br"
            :erro="erros.responder_para"
            dica="Se o cliente responder o e-mail, a mensagem chega neste endereço."
            @update:model-value="(v: string) => (f.responder_para = v)"
          />
        </div>
      </section>

      <!-- Mensagens + prévia -->
      <section class="cartao p-5 sm:p-6" aria-labelledby="t-mensagens">
        <div class="mb-5 flex items-start gap-3">
          <div class="flex size-10 shrink-0 items-center justify-center rounded-xl bg-marca-suave text-marca-texto"><Send class="size-5" aria-hidden="true" /></div>
          <div>
            <h2 id="t-mensagens" class="text-base font-bold text-texto">Mensagens</h2>
            <p class="mt-1 text-sm text-texto-suave">
              Escreva do seu jeito. Os botões da nota e o link para sair da lista entram sozinhos no e-mail. Use os botões "Inserir" para colocar o nome do cliente e outras informações.
            </p>
          </div>
        </div>
        <div class="grid gap-8 lg:grid-cols-[minmax(0,1fr)_minmax(0,26rem)]">
          <div class="flex min-w-0 flex-col gap-6">
            <fieldset class="flex flex-col gap-4" @focusin="previaAtual = 'convite'">
              <legend class="mb-2 flex items-center gap-2 font-bold text-texto"><Mail class="size-4 text-texto-fraco" aria-hidden="true" /> Convite por e-mail</legend>
              <CampoMensagem v-model="f.assunto_convite" rotulo="Assunto" :variaveis="VARIAVEIS_EMAIL" :maximo="LIMITE_ASSUNTO" :erro="erros.assunto_convite" />
              <CampoMensagem v-model="f.texto_convite" rotulo="Texto" multilinha :variaveis="VARIAVEIS_EMAIL" :maximo="LIMITE_TEXTO" :erro="erros.texto_convite" dica="Deixe uma linha em branco para começar outro parágrafo." />
            </fieldset>
            <fieldset v-if="f.lembretes > 0 || f.assunto_lembrete" class="flex flex-col gap-4" @focusin="previaAtual = 'lembrete'">
              <legend class="mb-2 flex items-center gap-2 font-bold text-texto"><Mail class="size-4 text-texto-fraco" aria-hidden="true" /> Lembrete</legend>
              <CampoMensagem v-model="f.assunto_lembrete" rotulo="Assunto do lembrete" :variaveis="VARIAVEIS_EMAIL" :maximo="LIMITE_ASSUNTO" :erro="erros.assunto_lembrete" />
              <CampoMensagem v-model="f.texto_lembrete" rotulo="Texto do lembrete" multilinha :linhas="4" :variaveis="VARIAVEIS_EMAIL" :maximo="LIMITE_TEXTO" :erro="erros.texto_lembrete" />
            </fieldset>
            <fieldset class="flex flex-col gap-4" @focusin="previaAtual = 'whatsapp'">
              <legend class="mb-2 flex items-center gap-2 font-bold text-texto"><MessageCircle class="size-4 text-emerald-700" aria-hidden="true" /> WhatsApp</legend>
              <CampoMensagem
                v-model="f.texto_whatsapp"
                rotulo="Mensagem do WhatsApp"
                multilinha
                :linhas="3"
                :variaveis="VARIAVEIS_WHATSAPP"
                :maximo="LIMITE_TEXTO"
                :erro="erros.texto_whatsapp"
                dica="Usada no botão WhatsApp. Precisa ter {link}: é por ele que a pessoa abre a pesquisa."
              />
            </fieldset>
          </div>

          <div class="min-w-0 lg:sticky lg:top-24 lg:self-start">
            <div class="mb-3 flex items-center justify-between gap-2">
              <h3 class="text-sm font-bold text-texto">Como o cliente vê</h3>
              <div class="inline-flex rounded-xl border border-borda-forte p-0.5" role="radiogroup" aria-label="Qual mensagem ver na prévia">
                <button
                  v-for="o in [{ v: 'convite', r: 'Convite' }, { v: 'lembrete', r: 'Lembrete' }, { v: 'whatsapp', r: 'WhatsApp' }] as const"
                  :key="o.v"
                  type="button"
                  role="radio"
                  :aria-checked="previaAtual === o.v"
                  class="h-8 rounded-[0.6rem] px-2.5 text-xs font-semibold transition-colors"
                  :class="previaAtual === o.v ? 'bg-marca-suave text-marca-texto' : 'text-texto-fraco hover:text-texto'"
                  @click="previaAtual = o.v"
                >
                  {{ o.r }}
                </button>
              </div>
            </div>
            <div aria-live="polite" aria-atomic="false">
              <PreviaEmail v-if="previaAtual !== 'whatsapp'" :previa="previaEmail" :empresa="sessao.conta?.nome ?? ''" />
              <div v-else class="rounded-2xl bg-[#e5ddd5] p-4" aria-label="Prévia da mensagem de WhatsApp">
                <p class="ml-auto max-w-[85%] whitespace-pre-line break-words rounded-xl rounded-tr-sm bg-[#dcf8c6] px-3 py-2 text-sm text-slate-900 shadow-sm">
                  {{ partesWhatsapp.antes }}<span v-if="partesWhatsapp.link" class="text-sky-700 underline">{{ partesWhatsapp.link }}</span>{{ partesWhatsapp.depois }}
                </p>
                <p class="mt-2 text-center text-xs text-slate-600">A mensagem abre pronta no WhatsApp; quem envia aperta o botão Enviar.</p>
              </div>
            </div>
            <p class="mt-2 text-xs text-texto-fraco">Exemplo com uma cliente chamada Maria, da empresa Mercado Bom Preço.</p>
          </div>
        </div>
      </section>

      <!-- Agradecimento -->
      <section class="cartao grid gap-6 p-5 sm:p-6 md:grid-cols-3" aria-labelledby="t-agradecimento">
        <div>
          <div class="mb-3 flex size-10 items-center justify-center rounded-xl bg-marca-suave text-marca-texto"><Heart class="size-5" aria-hidden="true" /></div>
          <h2 id="t-agradecimento" class="text-base font-bold text-texto">Agradecimento</h2>
          <p class="mt-1 text-sm text-texto-suave">Um e-mail curto de obrigado logo depois que o cliente responde, com texto conforme a nota.</p>
        </div>
        <div class="flex flex-col gap-5 md:col-span-2">
          <Interruptor v-model="f.agradecimento_ativo" rotulo="Agradecer quem responde" descricao="Só vai para quem tem e-mail e não saiu da lista." />
          <template v-if="f.agradecimento_ativo">
            <CampoMensagem
              v-model="f.agradecimento.promotor"
              rotulo="Para quem deu nota alta"
              multilinha
              :linhas="3"
              :variaveis="VARIAVEIS_AGRADECIMENTO"
              :maximo="LIMITE_TEXTO"
              :erro="erros['agradecimento.promotor']"
              dica="Nota 9 ou 10 (ou 4 e 5 estrelas)."
            />
            <CampoMensagem
              v-model="f.agradecimento.neutro"
              rotulo="Para quem deu nota média"
              multilinha
              :linhas="3"
              :variaveis="VARIAVEIS_AGRADECIMENTO"
              :maximo="LIMITE_TEXTO"
              :erro="erros['agradecimento.neutro']"
              dica="Nota 7 ou 8 (ou 3 estrelas)."
            />
            <CampoMensagem
              v-model="f.agradecimento.detrator"
              rotulo="Para quem deu nota baixa"
              multilinha
              :linhas="3"
              :variaveis="VARIAVEIS_AGRADECIMENTO"
              :maximo="LIMITE_TEXTO"
              :erro="erros['agradecimento.detrator']"
              dica="Nota de 0 a 6 (ou 1 e 2 estrelas). Vale mostrar que você vai cuidar do problema."
            />
          </template>
        </div>
      </section>
    </fieldset>

    <div v-if="podeSalvar" data-barra-fixa class="sticky bottom-0 z-10 -mx-4 flex flex-col-reverse gap-2 border-t border-borda bg-fundo/90 px-4 py-3 backdrop-blur sm:-mx-6 sm:flex-row sm:justify-end sm:px-6 lg:-mx-10 lg:px-10">
      <p v-if="alterado" class="text-sm text-texto-fraco sm:mr-auto sm:self-center">Você tem alterações não salvas.</p>
      <Botao v-if="alterado" variante="secundario" :desabilitado="enviando" @click="descartar">Descartar</Botao>
      <Botao tipo="submit" :carregando="enviando" :desabilitado="!alterado">Salvar alterações</Botao>
    </div>
  </form>
</template>

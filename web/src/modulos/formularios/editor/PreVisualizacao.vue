<script setup lang="ts">
// Pré-visualização do editor: a página da pesquisa (como hoje) e, para quem vê os envios, o convite por e-mail e a
// mensagem do WhatsApp com os textos de Configurações › Envios, o logo e os botões de nota deste formulário.
// Etapa 5c: com as indicações ligadas, terminar a página com nota de promotor mostra o cartão de indicação de exemplo
// (com o envio desligado), com os textos de Configurações › Crescimento.
import { computed, ref } from 'vue'
import { RouterLink } from 'vue-router'
import { ImageIcon, RotateCcw } from 'lucide-vue-next'
import { crescimentoApi, enviosApi, mensagemDoErro, type ConfigCrescimento, type ConfigEnvios } from '@/api'
import type { ConviteIndicacao, Pergunta, Tema, TipoFormulario } from '@/api/tipos'
import { useSessaoStore } from '@/stores/sessao'
import { logoParaCliente } from '@/utils/imagens'
import Pesquisa from '@/pesquisa/Pesquisa.vue'
import Alerta from '@/components/ui/Alerta.vue'
import Carregando from '@/components/ui/Carregando.vue'
import PreviaEmail from '@/modulos/configuracoes/PreviaEmail.vue'
import PreviaWhatsapp from '@/modulos/configuracoes/PreviaWhatsapp.vue'
import { previaConvite } from '@/modulos/configuracoes/configCrescimento'
import { montarPreviaEmail, renderizarMensagem } from '@/modulos/configuracoes/mensagens'

// `titulo`: o rótulo "Pré-visualização" no topo (a janela do celular já tem o próprio título).
const props = withDefaults(
  defineProps<{ nome: string; perguntas: Pergunta[]; tema: Tema; nomeEmpresa: string; tipo?: TipoFormulario; titulo?: boolean }>(),
  { tipo: 'nps', titulo: true },
)
const sessao = useSessaoStore()
const chave = ref(0)
// Sem logo no formulário, o cliente vê o logo da empresa (a API faz o mesmo na página pública e nos e-mails).
const logo = computed(() => logoParaCliente(props.tema.logo_url, sessao.conta?.logo_url))
const temaPrevia = computed<Tema>(() => ({ ...props.tema, logo_url: logo.value.url }))

type Canal = 'pagina' | 'email' | 'whatsapp'
const CANAIS: { valor: Canal; rotulo: string }[] = [
  { valor: 'pagina', rotulo: 'Página' },
  { valor: 'email', rotulo: 'E-mail' },
  { valor: 'whatsapp', rotulo: 'WhatsApp' },
]
const canal = ref<Canal>('pagina')
// Os textos dos convites vêm de Configurações › Envios (GET /envios/configuracao pede envios.ver).
const veMensagens = computed(() => sessao.pode('envios.ver'))
const podeEditarMensagens = computed(() => sessao.pode('configuracoes.gerenciar'))

const config = ref<ConfigEnvios | null>(null)
const carregando = ref(false)
const erro = ref<string | null>(null)

async function carregarMensagens() {
  if (config.value || carregando.value) return
  carregando.value = true
  erro.value = null
  try {
    config.value = await enviosApi.configuracao()
  } catch (e) {
    erro.value = mensagemDoErro(e)
  } finally {
    carregando.value = false
  }
}

function escolher(c: Canal) {
  canal.value = c
  if (c !== 'pagina') void carregarMensagens()
}

const exemplo = computed(() => ({
  nome: 'Maria Souza',
  empresa: props.nomeEmpresa || sessao.conta?.nome || 'Sua empresa',
  empresa_cliente: 'Mercado Bom Preço',
  link: `${window.location.origin}/r/exemplo`,
}))
const previaEmail = computed(() =>
  config.value ? montarPreviaEmail(config.value, 'convite', props.tipo, exemplo.value, logo.value.url || null) : null,
)
const textoWhatsapp = computed(() => (config.value ? renderizarMensagem(config.value.texto_whatsapp, exemplo.value) : ''))

// Etapa 5c: o convite de indicação de exemplo (GET /crescimento/configuracao pede crescimento.ver ou configuracoes.gerenciar),
// buscado só quando a pré-visualização termina com nota de promotor, e uma vez só.
const veCrescimento = computed(() => sessao.pode('crescimento.ver') || sessao.pode('configuracoes.gerenciar'))
let configCrescimento: Promise<ConfigCrescimento | null> | null = null
async function indicacaoExemplo(): Promise<ConviteIndicacao | null> {
  if (!veCrescimento.value) return null
  configCrescimento ??= crescimentoApi.configuracao().catch(() => {
    configCrescimento = null
    return null
  })
  const c = await configCrescimento
  return c?.indicacoes_ativas ? previaConvite(c, { empresa: exemplo.value.empresa, nome: 'Maria Souza' }) : null
}
</script>

<template>
  <div class="flex h-full flex-col overflow-hidden rounded-cartao border border-borda bg-slate-100">
    <div class="flex flex-col gap-2 border-b border-borda bg-superficie px-3 py-2">
      <div v-if="titulo || canal === 'pagina'" class="flex items-center justify-between gap-2">
        <p v-if="titulo" class="text-xs font-semibold uppercase tracking-wide text-texto-fraco">Pré-visualização</p>
        <button
          v-if="canal === 'pagina'"
          type="button"
          class="ml-auto inline-flex items-center gap-1 rounded-lg px-2 py-1 text-xs font-semibold text-texto-suave hover:bg-superficie-2"
          @click="chave++"
        >
          <RotateCcw class="size-3.5" aria-hidden="true" /> Recomeçar
        </button>
      </div>
      <div v-if="veMensagens" class="flex rounded-xl border border-borda-forte p-0.5" role="radiogroup" aria-label="Como o cliente recebe" data-canais-previa>
        <button
          v-for="o in CANAIS"
          :key="o.valor"
          type="button"
          role="radio"
          :aria-checked="canal === o.valor"
          :data-canal="o.valor"
          class="h-8 flex-1 rounded-[0.6rem] px-2 text-xs font-semibold transition-colors"
          :class="canal === o.valor ? 'bg-marca-suave text-marca-texto' : 'text-texto-fraco hover:text-texto'"
          @click="escolher(o.valor)"
        >
          {{ o.rotulo }}
        </button>
      </div>
    </div>

    <div v-if="canal === 'pagina'" class="flex-1 overflow-y-auto">
      <Pesquisa
        :key="chave"
        :formulario="{ nome, perguntas, tema: temaPrevia }"
        :variaveis="{ empresa: nomeEmpresa, nome: 'Maria Souza', assunto: '', referencia: 'Pedido 12345' }"
        previa
        :indicacao-exemplo="indicacaoExemplo"
      />
    </div>
    <div v-else class="flex-1 overflow-y-auto p-3" aria-live="polite" data-previa-canal>
      <Carregando v-if="carregando" rotulo="Carregando as mensagens" />
      <Alerta v-else-if="erro" tom="erro">
        {{ erro }}
        <button type="button" class="link ml-1" @click="carregarMensagens">Tentar de novo</button>
      </Alerta>
      <template v-else-if="config">
        <PreviaEmail v-if="canal === 'email' && previaEmail" :previa="previaEmail" :empresa="exemplo.empresa" />
        <PreviaWhatsapp v-else-if="canal === 'whatsapp'" :texto="textoWhatsapp" :link="exemplo.link" />
      </template>
    </div>

    <div class="flex flex-col gap-0.5 border-t border-borda bg-superficie px-3 py-2 text-xs text-texto-fraco">
      <p v-if="logo.daEmpresa && canal !== 'whatsapp'" class="flex items-center gap-1.5 font-semibold text-texto-suave" data-aviso-logo>
        <ImageIcon class="size-3.5 shrink-0" aria-hidden="true" /> Usando o logo da empresa
      </p>
      <p v-if="canal === 'pagina'">Exemplo com cliente “Maria” e referência “Pedido 12345”. Nada é gravado aqui.</p>
      <template v-else>
        <p>
          {{ canal === 'email' ? 'Convite por e-mail' : 'Mensagem do botão WhatsApp' }} com os textos de Configurações › Envios.
          Exemplo com a cliente Maria, da Mercado Bom Preço.
        </p>
        <RouterLink v-if="podeEditarMensagens" to="/configuracoes/envios" class="link self-start font-semibold" data-editar-mensagens>
          Editar as mensagens
        </RouterLink>
      </template>
    </div>
  </div>
</template>

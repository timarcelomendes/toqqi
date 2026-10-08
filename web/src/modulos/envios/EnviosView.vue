<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Bell, Bot, MessageCircle, MoreHorizontal, Settings } from 'lucide-vue-next'
import { enviosApi, mensagemDoErro, whatsappAutomaticoApi, type PreCondicoes, type ResultadoTarefa, type WhatsappIntegracao } from '@/api'
import { avisar } from '@/composables/avisos'
import { confirmar } from '@/composables/confirmacao'
import { useSessaoStore } from '@/stores/sessao'
import { plural } from '@/utils/formatos'
import CabecalhoPagina from '@/components/app/CabecalhoPagina.vue'
import ItemMenu from '@/components/app/ItemMenu.vue'
import Abas from '@/components/ui/Abas.vue'
import Botao from '@/components/ui/Botao.vue'
import MenuSuspenso from '@/components/ui/MenuSuspenso.vue'
import AbaDescadastros from './AbaDescadastros.vue'
import AbaFila from './AbaFila.vue'
import AbaHistorico from './AbaHistorico.vue'
import AvisoPreCondicoes from './AvisoPreCondicoes.vue'
import PanoramaEnvios from './PanoramaEnvios.vue'
import { estadoFranquia } from '@/modulos/integracoes/logica'

type Aba = 'contatos' | 'historico' | 'descadastros'
const abas: { valor: Aba; rotulo: string }[] = [
  { valor: 'contatos', rotulo: 'Contatos' },
  { valor: 'historico', rotulo: 'Histórico' },
  { valor: 'descadastros', rotulo: 'Descadastros' },
]

const sessao = useSessaoStore()
const rota = useRoute()
const router = useRouter()
const valida = (v: unknown): Aba => (abas.some((a) => a.valor === v) ? (v as Aba) : 'contatos')
const aba = ref<Aba>(valida(rota.query.aba))
watch(aba, (a) => {
  if (valida(rota.query.aba) !== a) router.replace({ query: a === 'contatos' ? {} : { ...rota.query, aba: a } })
})
watch(
  () => rota.query.aba,
  (v) => (aba.value = valida(v)),
)
const visitadas = ref(new Set<Aba>([aba.value]))
watch(aba, (a) => visitadas.value.add(a))

const preCondicoes = ref<PreCondicoes | null>(null)
const fila = ref<InstanceType<typeof AbaFila> | null>(null)
const historico = ref<InstanceType<typeof AbaHistorico> | null>(null)
const panorama = ref<InstanceType<typeof PanoramaEnvios> | null>(null)
const ocupado = ref<'lembretes' | 'robo' | null>(null)
const admin = computed(() => sessao.usuario?.perfil === 'admin')

const whatsapp = ref<WhatsappIntegracao | null>(null)
const franquia = computed(() => (whatsapp.value?.conectado ? estadoFranquia(whatsapp.value.franquia) : null))
const corFranquia = { ok: 'text-sucesso', atencao: 'text-atencao', esgotada: 'text-erro' } as const

async function carregarWhatsapp() {
  try {
    whatsapp.value = await whatsappAutomaticoApi.obter()
  } catch {
    /* sem o WhatsApp automático, a tela segue igual */
  }
}

async function carregarPreCondicoes() {
  try {
    preCondicoes.value = await enviosApi.preCondicoes()
  } catch {
    /* sem o aviso, a tela segue; se faltar algo, o envio responde com a explicação */
  }
}

function contar(v: ResultadoTarefa['ignorados']): number {
  return Array.isArray(v) ? v.length : typeof v === 'number' ? v : 0
}

function aposTarefa() {
  fila.value?.recarregar()
  historico.value?.recarregar()
  panorama.value?.recarregar()
}

async function enviarLembretes() {
  ocupado.value = 'lembretes'
  try {
    const previa = await enviosApi.previaLembretes()
    ocupado.value = null
    if (!previa.hoje) {
      avisar.info(
        previa.amanha
          ? `Nenhum lembrete para hoje. Amanhã sairão ${plural(previa.amanha, 'lembrete', 'lembretes')}.`
          : 'Nenhum lembrete para enviar agora.',
      )
      return
    }
    const ok = await confirmar({
      titulo: `Enviar ${plural(previa.hoje, 'lembrete', 'lembretes')} agora?`,
      mensagem:
        'Os lembretes do dia saem agora, sem esperar o horário de sempre. Vai para quem recebeu a pesquisa e ainda não respondeu.' +
        (previa.amanha ? ` Amanhã há mais ${plural(previa.amanha, 'lembrete previsto', 'lembretes previstos')}.` : ''),
      confirmar: 'Enviar lembretes',
    })
    if (!ok) return
    ocupado.value = 'lembretes'
    const r = await enviosApi.executarLembretes()
    const ignorados = contar(r.ignorados)
    avisar.sucesso(
      `${plural(r.enviados ?? 0, 'lembrete enviado', 'lembretes enviados')}.` +
        (ignorados ? ` ${plural(ignorados, 'ficou', 'ficaram')} de fora pelas regras de envio.` : ''),
    )
    aposTarefa()
  } catch (e) {
    avisar.erro(mensagemDoErro(e))
  } finally {
    ocupado.value = null
  }
}

async function rodarRobo() {
  const ok = await confirmar({
    titulo: 'Rodar o envio automático agora?',
    mensagem:
      'Manda a pesquisa para quem está na fila agora (até 100 contatos, os mais atrasados primeiro), sem esperar o horário de envio. As outras regras continuam valendo, como o descanso e quem saiu da lista.',
    confirmar: 'Rodar agora',
  })
  if (!ok) return
  ocupado.value = 'robo'
  try {
    const r = await enviosApi.executarRobo()
    const ignorados = contar(r.ignorados)
    avisar.sucesso(
      `${plural(r.agendados ?? 0, 'pesquisa está saindo', 'pesquisas estão saindo')} agora.` +
        (ignorados ? ` ${plural(ignorados, 'contato ficou', 'contatos ficaram')} de fora pelas regras de envio.` : ''),
    )
    aposTarefa()
  } catch (e) {
    avisar.erro(mensagemDoErro(e))
  } finally {
    ocupado.value = null
  }
}

onMounted(() => {
  carregarPreCondicoes()
  carregarWhatsapp()
})
</script>

<template>
  <CabecalhoPagina titulo="Envios" descricao="Quem vai receber a pesquisa, o que já saiu e quem pediu para não receber mais.">
    <template #acoes>
      <Botao variante="secundario" para="/configuracoes/envios"><Settings class="size-4" aria-hidden="true" /> Configurações de envio</Botao>
      <MenuSuspenso v-if="admin" rotulo="Mais ações de envio">
        <template #gatilho="{ props }">
          <Botao v-bind="props" variante="secundario" :carregando="!!ocupado">
            <MoreHorizontal v-if="!ocupado" class="size-4" aria-hidden="true" /> Mais ações
          </Botao>
        </template>
        <ItemMenu :icone="Bell" @click="enviarLembretes">Enviar lembretes agora</ItemMenu>
        <ItemMenu :icone="Bot" @click="rodarRobo">Rodar envio automático agora</ItemMenu>
      </MenuSuspenso>
    </template>
  </CabecalhoPagina>

  <p v-if="whatsapp && franquia" class="-mt-3 mb-5 flex flex-wrap items-center gap-x-2 gap-y-1 text-sm text-texto-suave sm:-mt-5">
    <MessageCircle class="size-4 text-emerald-700" aria-hidden="true" />
    <span>
      WhatsApp automático: <strong class="tabular-nums" :class="corFranquia[franquia.nivel]">{{ franquia.semLimite ? franquia.usadas : `${franquia.usadas} de ${franquia.limite}` }}</strong> no mês<template v-if="!whatsapp.ativo"> (desligado)</template><template v-else-if="franquia.nivel === 'esgotada'">{{ whatsapp.franquia.excedente_ativo ? ' (franquia acabou: mensagens extras liberadas)' : ' (franquia acabou: indo por e-mail)' }}</template>
    </span>
    <RouterLink v-if="admin" to="/integracoes?aba=whatsapp" class="link">Ver detalhes</RouterLink>
  </p>

  <PanoramaEnvios ref="panorama" />

  <AvisoPreCondicoes v-if="preCondicoes && !preCondicoes.pronto" :dados="preCondicoes" class="mb-6" />

  <Abas v-model="aba" :abas="abas" rotulo="Seções de envios">
    <AbaFila
      v-if="visitadas.has('contatos')"
      v-show="aba === 'contatos'"
      ref="fila"
      :email-liberado="preCondicoes?.pronto ?? true"
      @pre-condicao="carregarPreCondicoes"
      @enviou="panorama?.recarregar()"
    />
    <AbaHistorico v-if="visitadas.has('historico')" v-show="aba === 'historico'" ref="historico" />
    <AbaDescadastros v-if="visitadas.has('descadastros')" v-show="aba === 'descadastros'" />
  </Abas>
</template>

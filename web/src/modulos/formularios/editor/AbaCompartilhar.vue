<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import { Download, ExternalLink, RefreshCw, Star } from 'lucide-vue-next'
import { formulariosApi, mensagemDoErro, salvarBlob, type Formulario } from '@/api'
import { avisar } from '@/composables/avisos'
import { confirmar } from '@/composables/confirmacao'
import { corValida } from '@/pesquisa/cor'
import { montarLinkComContexto, type ValoresLinkContexto } from '@/pesquisa/contexto'
import { CAMPOS_CONTEXTO, ROTULOS_CONTEXTO } from '@/pesquisa/tipos'
import Alerta from '@/components/ui/Alerta.vue'
import Botao from '@/components/ui/Botao.vue'
import BotaoCopiar from '@/components/ui/BotaoCopiar.vue'
import Campo from '@/components/ui/Campo.vue'
import Etiqueta from '@/components/ui/Etiqueta.vue'
import Interruptor from '@/components/ui/Interruptor.vue'
import Selecao from '@/components/ui/Selecao.vue'

const props = defineProps<{ formulario: Formulario; podeEditar: boolean; alterado: boolean }>()
const emit = defineEmits<{ atualizado: [Partial<Formulario>] }>()

const origem = window.location.origin
const link = computed(() => `${origem}/f/${props.formulario.codigo_publico}`)
const linkQr = computed(() => `${link.value}?canal=qr`)
const mudandoPublico = ref(false)
const mudandoEdicao = ref(false)
const gerandoCodigo = ref(false)
const definindo = ref<'nps' | 'csat' | null>(null)

// QR Code (a biblioteca só é carregada quando esta aba abre)
const qrPng = ref<string | null>(null)
const qrSvg = ref<string | null>(null)
const erroQr = ref(false)
async function gerarQr() {
  erroQr.value = false
  try {
    const QRCode = (await import('qrcode')).default
    const opcoes = { margin: 2, errorCorrectionLevel: 'M' as const, color: { dark: '#0f172a', light: '#ffffff' } }
    qrPng.value = await QRCode.toDataURL(linkQr.value, { ...opcoes, width: 1024 })
    qrSvg.value = await QRCode.toString(linkQr.value, { ...opcoes, type: 'svg' })
  } catch {
    erroQr.value = true
  }
}
watch(linkQr, gerarQr, { immediate: true })

const nomeArquivo = computed(() => `qrcode-${props.formulario.nome.normalize('NFD').replace(/[^\w]+/g, '-').replace(/^-|-$/g, '').toLowerCase() || 'pesquisa'}`)
async function baixarPng() {
  if (!qrPng.value) return
  salvarBlob(await (await fetch(qrPng.value)).blob(), `${nomeArquivo.value}.png`)
}
function baixarSvg() {
  if (qrSvg.value) salvarBlob(new Blob([qrSvg.value], { type: 'image/svg+xml' }), `${nomeArquivo.value}.svg`)
}

// Widget
const widget = reactive({ texto: 'Avalie-nos', cor: corValida(props.formulario.tema?.cor, '#d63a18'), posicao: 'direita' as 'direita' | 'esquerda' })
const snippet = computed(() => {
  const attrs = [`src="${origem}/widget.js"`, `data-toqqi="${props.formulario.codigo_publico}"`]
  const texto = widget.texto.trim().replace(/"/g, '&quot;')
  if (texto && texto !== 'Avalie-nos') attrs.push(`data-texto="${texto}"`)
  if (/^#[0-9a-f]{6}$/i.test(widget.cor)) attrs.push(`data-cor="${widget.cor}"`)
  if (widget.posicao === 'esquerda') attrs.push('data-posicao="esquerda"')
  return `<script ${attrs.join(' ')} async><\/script>`
})

// Link com contexto
const contexto = reactive<ValoresLinkContexto>({})
const canalContexto = ref<'qr' | 'widget' | ''>('')
const linkContexto = computed(() => montarLinkComContexto(origem, props.formulario.codigo_publico, { ...contexto, canal: canalContexto.value }))

/** O cliente pode mudar a resposta (docs/api-editar-resposta.md): vale na hora, sem publicar. */
async function mudarEdicao(v: boolean) {
  mudandoEdicao.value = true
  try {
    const f = await formulariosApi.atualizar(props.formulario.id, { permite_editar: v })
    emit('atualizado', { permite_editar: f?.permite_editar ?? v, atualizado_em: f?.atualizado_em })
    avisar.sucesso(v ? 'Pronto: quem responder pode mudar a resposta por 7 dias.' : 'Pronto: a resposta enviada não muda mais.')
  } catch (e) {
    avisar.erro(mensagemDoErro(e))
  } finally {
    mudandoEdicao.value = false
  }
}

async function mudarPublico(v: boolean) {
  mudandoPublico.value = true
  try {
    const f = await formulariosApi.atualizar(props.formulario.id, { publico: v })
    emit('atualizado', { publico: f?.publico ?? v, atualizado_em: f?.atualizado_em })
    avisar.sucesso(v ? 'Link público ligado. Quem tiver o link pode responder.' : 'Link público desligado. Só convites individuais funcionam.')
  } catch (e) {
    avisar.erro(mensagemDoErro(e))
  } finally {
    mudandoPublico.value = false
  }
}

async function novoCodigo() {
  const ok = await confirmar({
    titulo: 'Gerar um novo link?',
    mensagem: 'O link, o QR Code e o widget antigos param de funcionar na hora. Use se o link vazou ou se quer encerrar uma campanha. Convites individuais não mudam.',
    confirmar: 'Gerar novo link',
    perigo: true,
  })
  if (!ok) return
  gerandoCodigo.value = true
  try {
    const r = await formulariosApi.novoCodigo(props.formulario.id)
    const codigo = r?.codigo_publico ?? (await formulariosApi.obter(props.formulario.id)).codigo_publico
    emit('atualizado', { codigo_publico: codigo })
    avisar.sucesso('Novo link gerado. Atualize onde tinha o link antigo.')
  } catch (e) {
    avisar.erro(mensagemDoErro(e))
  } finally {
    gerandoCodigo.value = false
  }
}

async function definirPadrao(uso: 'nps' | 'csat') {
  definindo.value = uso
  try {
    await formulariosApi.definirPadrao(props.formulario.id, uso)
    emit('atualizado', uso === 'nps' ? { padrao_nps: true } : { padrao_csat: true })
    avisar.sucesso(`Pronto: este é o formulário padrão de ${uso.toUpperCase()}.`)
  } catch (e) {
    avisar.erro(mensagemDoErro(e))
  } finally {
    definindo.value = null
  }
}
</script>

<template>
  <div class="flex flex-col gap-5">
    <Alerta v-if="alterado" tom="info" data-alerta-rascunho>Há alterações não publicadas. O link, o QR Code e o widget mostram a versão publicada até você clicar em Publicar.</Alerta>
    <Alerta v-if="!formulario.ativo" tom="atencao" titulo="Formulário desativado">Ninguém consegue responder enquanto ele estiver desativado. Ative no topo da página.</Alerta>

    <!-- Link público -->
    <section class="cartao flex flex-col gap-4 p-5" aria-labelledby="t-link">
      <h2 id="t-link" class="font-bold text-texto">Link público</h2>
      <Interruptor
        :model-value="formulario.publico"
        rotulo="Qualquer pessoa com o link pode responder"
        descricao="Desligado, só funcionam os convites individuais (um link por contato)."
        :desabilitado="!podeEditar || mudandoPublico"
        @update:model-value="mudarPublico"
      />
      <template v-if="formulario.publico">
        <div class="flex flex-col gap-2 sm:flex-row">
          <label for="link-publico" class="sr-only">Link público</label>
          <input id="link-publico" :value="link" readonly class="h-10 min-w-0 flex-1 rounded-xl border border-borda-forte bg-superficie-2 px-3.5 text-sm text-texto" @focus="($event.target as HTMLInputElement).select()" />
          <div class="flex gap-2">
            <BotaoCopiar :texto="link" rotulo="Copiar link" />
            <a :href="link" target="_blank" rel="noopener" class="inline-flex h-10 items-center gap-2 rounded-xl px-3 text-sm font-semibold text-texto-suave hover:bg-superficie-2">
              <ExternalLink class="size-4" aria-hidden="true" /> Abrir
            </a>
          </div>
        </div>
        <div v-if="podeEditar">
          <Botao variante="fantasma" tamanho="sm" :carregando="gerandoCodigo" @click="novoCodigo"><RefreshCw class="size-4" aria-hidden="true" /> Gerar novo link</Botao>
        </div>
      </template>
    </section>

    <!-- Depois de responder: o cliente pode mudar a resposta (vale para o convite e para o link público) -->
    <section class="cartao flex flex-col gap-3 p-5" aria-labelledby="t-edicao" data-secao-edicao>
      <h2 id="t-edicao" class="font-bold text-texto">Depois de responder</h2>
      <Interruptor
        :model-value="!!formulario.permite_editar"
        rotulo="O cliente pode mudar a resposta"
        descricao="Até 7 dias depois de responder. No convite (e-mail ou WhatsApp), ele abre o link de novo e vê as respostas preenchidas; no link público, o botão “Editar minha resposta” aparece logo depois de enviar. A resposta muda, sem criar outra."
        :desabilitado="!podeEditar || mudandoEdicao"
        data-permite-editar
        @update:model-value="mudarEdicao"
      />
    </section>

    <template v-if="formulario.publico">
      <!-- QR Code -->
      <section class="cartao flex flex-col gap-4 p-5 sm:flex-row sm:items-center" aria-labelledby="t-qr">
        <div class="flex size-40 shrink-0 items-center justify-center self-center rounded-xl border border-borda bg-white p-2">
          <img v-if="qrPng" :src="qrPng" :alt="`QR Code para ${link}`" class="size-full" />
          <p v-else-if="erroQr" class="text-center text-xs text-erro">Não deu para gerar o QR Code.</p>
          <span v-else class="size-8 animate-pulse rounded bg-superficie-2" aria-hidden="true" />
        </div>
        <div class="flex flex-col gap-2">
          <h2 id="t-qr" class="font-bold text-texto">QR Code</h2>
          <p class="text-sm text-texto-suave">Imprima no balcão, na nota fiscal, na embalagem ou no caminhão. As respostas chegam marcadas como “QR Code”.</p>
          <div class="flex flex-wrap gap-2">
            <Botao variante="secundario" tamanho="sm" :desabilitado="!qrPng" @click="baixarPng"><Download class="size-4" aria-hidden="true" /> Baixar PNG</Botao>
            <Botao variante="secundario" tamanho="sm" :desabilitado="!qrSvg" @click="baixarSvg"><Download class="size-4" aria-hidden="true" /> Baixar SVG (para gráfica)</Botao>
          </div>
        </div>
      </section>

      <!-- Widget -->
      <section class="cartao flex flex-col gap-4 p-5" aria-labelledby="t-widget">
        <div>
          <h2 id="t-widget" class="font-bold text-texto">Botão no seu site</h2>
          <p class="text-sm text-texto-suave">Cole este código no seu site (antes de &lt;/body&gt;). Aparece um botão flutuante que abre a pesquisa numa janela.</p>
        </div>
        <div class="grid gap-3 sm:grid-cols-3">
          <Campo v-model="widget.texto" rotulo="Texto do botão" maxlength="30" />
          <Campo v-model="widget.cor" rotulo="Cor do botão" maxlength="7" spellcheck="false" />
          <Selecao v-model="widget.posicao" rotulo="Posição" :opcoes="[{ valor: 'direita', rotulo: 'Canto direito' }, { valor: 'esquerda', rotulo: 'Canto esquerdo' }]" />
        </div>
        <pre class="overflow-x-auto rounded-xl bg-slate-900 p-4 text-xs leading-relaxed text-slate-100"><code>{{ snippet }}</code></pre>
        <div><BotaoCopiar :texto="snippet" rotulo="Copiar código" /></div>
      </section>

      <!-- Link com contexto -->
      <section class="cartao flex flex-col gap-4 p-5" aria-labelledby="t-contexto">
        <div>
          <h2 id="t-contexto" class="font-bold text-texto">Link com informações da entrega</h2>
          <p class="text-sm text-texto-suave">
            Monte um link que já leva o número do pedido, a rota ou o motorista. Essas informações ficam junto da resposta, para você saber de qual entrega a pessoa está falando.
            Seu sistema pode gerar links assim trocando os valores.
          </p>
        </div>
        <div class="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          <Campo v-for="c in CAMPOS_CONTEXTO" :key="c" v-model="contexto[c]" :rotulo="ROTULOS_CONTEXTO[c]" maxlength="120" autocomplete="off" />
          <Campo v-model="contexto.referencia" rotulo="Referência" maxlength="120" autocomplete="off" dica="Aparece no lugar de {referencia}." />
          <Selecao
            v-model="canalContexto"
            rotulo="Onde o link vai ser usado"
            :opcoes="[{ valor: 'qr', rotulo: 'QR Code' }, { valor: 'widget', rotulo: 'Site' }]"
            vazio="Link (padrão)"
          />
        </div>
        <div class="flex flex-col gap-2 sm:flex-row">
          <label for="link-contexto" class="sr-only">Link montado</label>
          <input id="link-contexto" :value="linkContexto" readonly class="h-10 min-w-0 flex-1 rounded-xl border border-borda-forte bg-superficie-2 px-3.5 font-mono text-xs text-texto" @focus="($event.target as HTMLInputElement).select()" />
          <BotaoCopiar :texto="linkContexto" rotulo="Copiar" />
        </div>
      </section>
    </template>

    <!-- Padrão -->
    <section class="cartao flex flex-col gap-3 p-5" aria-labelledby="t-padrao">
      <h2 id="t-padrao" class="font-bold text-texto">Formulário padrão</h2>
      <p class="text-sm text-texto-suave">O padrão é o que vai quando você não escolhe um formulário (nos envios e nos links gerados para um contato).</p>
      <div class="flex flex-wrap items-center gap-2">
        <template v-if="formulario.tipo_principal === 'nps'">
          <Etiqueta v-if="formulario.padrao_nps" tom="sucesso"><Star class="size-3" aria-hidden="true" /> Padrão de NPS</Etiqueta>
          <Botao v-else-if="podeEditar" variante="secundario" :desabilitado="!formulario.ativo" :carregando="definindo === 'nps'" @click="definirPadrao('nps')">Usar como padrão de NPS</Botao>
        </template>
        <template v-else-if="formulario.tipo_principal === 'csat'">
          <Etiqueta v-if="formulario.padrao_csat" tom="sucesso"><Star class="size-3" aria-hidden="true" /> Padrão de CSAT</Etiqueta>
          <Botao v-else-if="podeEditar" variante="secundario" :desabilitado="!formulario.ativo" :carregando="definindo === 'csat'" @click="definirPadrao('csat')">Usar como padrão de CSAT</Botao>
        </template>
        <p v-else class="text-sm text-texto-fraco">Só formulários com nota NPS ou CSAT podem ser padrão.</p>
      </div>
      <p v-if="alterado && podeEditar" class="text-xs text-texto-fraco">O padrão usa a versão publicada (a nota principal dela).</p>
    </section>
  </div>
</template>

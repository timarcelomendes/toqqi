<script setup lang="ts">
// Passo a passo para conectar o número próprio (WhatsApp Business Platform da Meta) e o formulário de conexão.
import { computed, nextTick, reactive } from 'vue'
import { ExternalLink, Link2 } from 'lucide-vue-next'
import { whatsappAutomaticoApi, type WhatsappIntegracao } from '@/api'
import { avisar } from '@/composables/avisos'
import { useFormulario } from '@/composables/formulario'
import Alerta from '@/components/ui/Alerta.vue'
import Botao from '@/components/ui/Botao.vue'
import Campo from '@/components/ui/Campo.vue'
import BlocoCodigo from './BlocoCodigo.vue'
import { modeloSugerido } from './logica'

const props = defineProps<{ dados: WhatsappIntegracao }>()
const emit = defineEmits<{ conectado: [w: WhatsappIntegracao] }>()

const { enviando, erroGeral, erros, executar, limpar } = useFormulario()
const f = reactive({ phone_number_id: '', waba_id: '', token: '', modelo_nome: 'pesquisa_satisfacao', modelo_idioma: 'pt_BR' })
const modelo = computed(() => modeloSugerido(window.location.origin))
// As marcas {{1}}, {{2}} e {{3}} do modelo, fora do template (lá dentro "}}" fecharia a interpolação).
const V = { um: '{{1}}', dois: '{{2}}', tres: '{{3}}' } as const

const ROTULOS: Record<keyof typeof f, string> = {
  phone_number_id: 'a identificação do número',
  waba_id: 'a identificação da conta do WhatsApp Business',
  token: 'o token de acesso',
  modelo_nome: 'o nome do modelo',
  modelo_idioma: 'o idioma do modelo',
}

async function conectar() {
  limpar()
  const dados = {
    phone_number_id: f.phone_number_id.trim(),
    waba_id: f.waba_id.trim(),
    token: f.token.trim(),
    modelo_nome: f.modelo_nome.trim(),
    modelo_idioma: f.modelo_idioma.trim() || 'pt_BR',
  }
  for (const k of Object.keys(ROTULOS) as (keyof typeof f)[]) {
    if (!dados[k]) erros[k] = `Informe ${ROTULOS[k]}.`
  }
  if (dados.phone_number_id && !/^\d+$/.test(dados.phone_number_id)) erros.phone_number_id = 'Use só os números da identificação (não é o telefone).'
  if (dados.waba_id && !/^\d+$/.test(dados.waba_id)) erros.waba_id = 'Use só os números da identificação.'
  if (Object.keys(erros).length) {
    focarErro()
    return
  }
  const r = await executar(() => whatsappAutomaticoApi.conectar(dados))
  if (!r) {
    focarErro()
    return
  }
  f.token = ''
  avisar.sucesso('WhatsApp conectado! Agora escolha o canal em Configurações de envio.')
  emit('conectado', r)
}

async function focarErro() {
  await nextTick()
  document.querySelector<HTMLElement>('#form-whatsapp [aria-invalid="true"]')?.focus()
}
</script>

<template>
  <div class="flex flex-col gap-6">
    <Alerta tom="info">
      Com o WhatsApp automático, a pesquisa chega no WhatsApp do cliente sem ninguém precisar apertar Enviar. As mensagens saem do número da sua
      empresa, pela plataforma oficial da Meta (dona do WhatsApp). A conexão leva uns 30 minutos e, se precisar, peça ajuda a quem cuida da
      tecnologia na sua empresa.
    </Alerta>

    <ol class="flex flex-col gap-4">
      <li class="cartao p-5 sm:p-6">
        <h3 class="flex items-center gap-3 font-bold text-texto">
          <span class="flex size-8 shrink-0 items-center justify-center rounded-full bg-marca-suave text-sm text-marca-texto">1</span>
          Tenha uma conta no WhatsApp Business Platform
        </h3>
        <div class="mt-3 flex flex-col gap-2 text-sm text-texto-suave sm:pl-11">
          <p>
            Entre no <a href="https://business.facebook.com" target="_blank" rel="noopener" class="link inline-flex items-center gap-1">Meta Business <ExternalLink class="size-3.5" aria-hidden="true" /></a>
            (o antigo Gerenciador de Negócios) com a conta da empresa. Se ainda não tiver, crie: é gratuito.
          </p>
          <p>Em "Contas do WhatsApp", crie a conta do WhatsApp Business. Para enviar para muitos clientes, a Meta pede a verificação da empresa (CNPJ e documentos).</p>
        </div>
      </li>

      <li class="cartao p-5 sm:p-6">
        <h3 class="flex items-center gap-3 font-bold text-texto">
          <span class="flex size-8 shrink-0 items-center justify-center rounded-full bg-marca-suave text-sm text-marca-texto">2</span>
          Cadastre o número que vai enviar
        </h3>
        <div class="mt-3 flex flex-col gap-2 text-sm text-texto-suave sm:pl-11">
          <p>
            No <a href="https://business.facebook.com/wa/manage/phone-numbers/" target="_blank" rel="noopener" class="link inline-flex items-center gap-1">WhatsApp Manager <ExternalLink class="size-3.5" aria-hidden="true" /></a>,
            adicione o número e confirme com o código que chega por SMS ou ligação.
          </p>
          <p>
            <strong class="text-texto">Atenção:</strong> o número não pode estar em uso no aplicativo do WhatsApp (nem no WhatsApp Business do celular). Use um número novo ou apague a conta dele no celular antes.
          </p>
          <p>Anote a <strong class="text-texto">Identificação do número de telefone</strong> e a <strong class="text-texto">Identificação da conta do WhatsApp Business</strong>: elas aparecem em "Configuração da API" e vão no formulário lá embaixo.</p>
        </div>
      </li>

      <li class="cartao p-5 sm:p-6">
        <h3 class="flex items-center gap-3 font-bold text-texto">
          <span class="flex size-8 shrink-0 items-center justify-center rounded-full bg-marca-suave text-sm text-marca-texto">3</span>
          Crie o modelo de mensagem
        </h3>
        <div class="mt-3 flex flex-col gap-3 text-sm text-texto-suave sm:pl-11">
          <p>
            A Meta só deixa a empresa puxar conversa com mensagens aprovadas antes. No WhatsApp Manager, vá em "Modelos de mensagem" → "Criar modelo"
            e use os dados abaixo. A aprovação costuma sair em minutos (pode levar até 24 horas).
          </p>
          <dl class="grid gap-3 sm:grid-cols-3">
            <div class="rounded-xl border border-borda p-3">
              <dt class="text-xs font-semibold uppercase tracking-wide text-texto-fraco">Categoria</dt>
              <dd class="mt-1 font-semibold text-texto">{{ modelo.categoria }}</dd>
            </div>
            <div class="rounded-xl border border-borda p-3">
              <dt class="text-xs font-semibold uppercase tracking-wide text-texto-fraco">Nome</dt>
              <dd class="mt-1 break-all font-mono text-texto">{{ modelo.nome }}</dd>
            </div>
            <div class="rounded-xl border border-borda p-3">
              <dt class="text-xs font-semibold uppercase tracking-wide text-texto-fraco">Idioma</dt>
              <dd class="mt-1 font-semibold text-texto">{{ modelo.idioma }}</dd>
            </div>
          </dl>
          <BlocoCodigo :texto="modelo.corpo" rotulo="Copiar texto" quebrar><template #titulo>Corpo da mensagem</template></BlocoCodigo>
          <p>
            <code class="font-mono text-xs">{{ V.um }}</code> é o primeiro nome do cliente, <code class="font-mono text-xs">{{ V.dois }}</code> o nome da sua empresa e
            <code class="font-mono text-xs">{{ V.tres }}</code> o que está sendo avaliado (por exemplo, "seu pedido 48213" ou "nosso atendimento"). Quando a Meta pedir exemplos, use
            "Maria", "{{ modelo.exemplos[V.dois] }}" e "{{ modelo.exemplos[V.tres] }}".
          </p>
          <BlocoCodigo :texto="modelo.rodape" rotulo="Copiar rodapé" quebrar><template #titulo>Rodapé (opcional, recomendado)</template></BlocoCodigo>
          <p>Em "Botões", adicione <strong class="text-texto">Chamada para ação → Visitar site</strong>, com URL <strong class="text-texto">dinâmica</strong>:</p>
          <div class="grid gap-3 sm:grid-cols-2">
            <BlocoCodigo :texto="modelo.botaoTexto" rotulo="Copiar" quebrar><template #titulo>Texto do botão</template></BlocoCodigo>
            <BlocoCodigo :texto="modelo.botaoUrl" rotulo="Copiar" quebrar><template #titulo>URL do botão (dinâmica)</template></BlocoCodigo>
          </div>
          <p>No exemplo da URL, a Meta pede um valor qualquer para o <code class="font-mono text-xs">{{ V.um }}</code> do botão: use <code class="font-mono text-xs">exemplo</code>.</p>
        </div>
      </li>

      <li class="cartao p-5 sm:p-6">
        <h3 class="flex items-center gap-3 font-bold text-texto">
          <span class="flex size-8 shrink-0 items-center justify-center rounded-full bg-marca-suave text-sm text-marca-texto">4</span>
          Gere o token permanente
        </h3>
        <div class="mt-3 flex flex-col gap-2 text-sm text-texto-suave sm:pl-11">
          <p>É a autorização para o Toqqi enviar pelo seu número. No Meta Business, vá em "Configurações do negócio" → "Usuários do sistema":</p>
          <ol class="flex list-decimal flex-col gap-1 pl-5">
            <li>Adicione um usuário do sistema com função de administrador.</li>
            <li>Em "Atribuir ativos", dê controle total do app e da conta do WhatsApp.</li>
            <li>Clique em "Gerar token", escolha expiração <strong class="text-texto">Nunca</strong> e marque as permissões <code class="font-mono text-xs">whatsapp_business_messaging</code> e <code class="font-mono text-xs">whatsapp_business_management</code>.</li>
            <li>Copie o token. Ele vai no formulário abaixo e fica guardado com criptografia: nem a nossa equipe consegue ver.</li>
          </ol>
        </div>
      </li>

      <li class="cartao p-5 sm:p-6">
        <h3 class="flex items-center gap-3 font-bold text-texto">
          <span class="flex size-8 shrink-0 items-center justify-center rounded-full bg-marca-suave text-sm text-marca-texto">5</span>
          Avise a Meta para onde mandar as confirmações
        </h3>
        <div class="mt-3 flex flex-col gap-3 text-sm text-texto-suave sm:pl-11">
          <p>
            É assim que o Toqqi fica sabendo se a mensagem foi entregue e lida, e quando o cliente responde SAIR. No painel do app da Meta
            (<a href="https://developers.facebook.com/apps" target="_blank" rel="noopener" class="link inline-flex items-center gap-1">developers.facebook.com <ExternalLink class="size-3.5" aria-hidden="true" /></a>),
            em WhatsApp → Configuração → Webhook, clique em "Editar", cole os dois dados abaixo, salve e assine o campo <code class="font-mono text-xs">messages</code>.
          </p>
          <div class="grid gap-3 sm:grid-cols-2">
            <BlocoCodigo v-if="props.dados.webhook_url" :texto="props.dados.webhook_url" rotulo="Copiar" quebrar><template #titulo>URL de retorno de chamada</template></BlocoCodigo>
            <BlocoCodigo v-if="props.dados.webhook_verificacao" :texto="props.dados.webhook_verificacao" rotulo="Copiar" quebrar><template #titulo>Token de verificação</template></BlocoCodigo>
          </div>
          <p v-if="!props.dados.webhook_url || !props.dados.webhook_verificacao" class="text-atencao">
            Não recebemos esses dados agora. Recarregue a página; se continuar, fale com o suporte do Toqqi.
          </p>
        </div>
      </li>

      <li class="cartao p-5 sm:p-6">
        <h3 class="flex items-center gap-3 font-bold text-texto">
          <span class="flex size-8 shrink-0 items-center justify-center rounded-full bg-marca-forte text-sm text-white">6</span>
          Cole os dados aqui
        </h3>
        <form id="form-whatsapp" class="mt-4 flex flex-col gap-5 sm:pl-11" novalidate @submit.prevent="conectar">
          <Alerta v-if="erroGeral" tom="erro" titulo="Não deu para conectar">{{ erroGeral }}</Alerta>
          <div class="grid gap-5 sm:grid-cols-2">
            <Campo
              v-model="f.phone_number_id"
              rotulo="Identificação do número de telefone"
              inputmode="numeric"
              autocomplete="off"
              spellcheck="false"
              obrigatorio
              placeholder="Ex.: 106540352242922"
              :erro="erros.phone_number_id"
              dica='Em inglês, "Phone number ID". Não é o número do telefone.'
            />
            <Campo
              v-model="f.waba_id"
              rotulo="Identificação da conta do WhatsApp Business"
              inputmode="numeric"
              autocomplete="off"
              spellcheck="false"
              obrigatorio
              placeholder="Ex.: 102290129340398"
              :erro="erros.waba_id"
              dica='Em inglês, "WhatsApp Business Account ID".'
            />
          </div>
          <Campo
            v-model="f.token"
            rotulo="Token permanente"
            tipo="password"
            autocomplete="off"
            spellcheck="false"
            obrigatorio
            :erro="erros.token"
            dica="O do passo 4. Guardamos com criptografia e ele nunca aparece de novo na tela."
          />
          <div class="grid gap-5 sm:grid-cols-2">
            <Campo
              v-model="f.modelo_nome"
              rotulo="Nome do modelo de mensagem"
              autocomplete="off"
              spellcheck="false"
              obrigatorio
              :erro="erros.modelo_nome"
              dica="Igual ao do passo 3. O modelo precisa estar aprovado."
            />
            <Campo v-model="f.modelo_idioma" rotulo="Idioma do modelo" autocomplete="off" spellcheck="false" obrigatorio :erro="erros.modelo_idioma" dica="Para português do Brasil, deixe pt_BR." />
          </div>
          <div class="flex flex-col gap-2 sm:flex-row sm:items-center">
            <Botao tipo="submit" :carregando="enviando"><Link2 v-if="!enviando" class="size-4" aria-hidden="true" /> Conectar WhatsApp</Botao>
            <p class="text-sm text-texto-fraco">Vamos conferir os dados com a Meta. Leva alguns segundos.</p>
          </div>
        </form>
      </li>
    </ol>
  </div>
</template>

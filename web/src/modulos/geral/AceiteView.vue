<script setup lang="ts">
// Tela "Antes de continuar" (docs/api-aceite-lgpd.md §3): bloqueia o app até a pessoa aceitar os Termos de uso e a
// Política de privacidade da versão atual. A outra saída é "Sair". Fica no layout de acesso (sem assistente nem avisos).
import { computed, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Cookie, Database, Building2, UserCheck } from 'lucide-vue-next'
import { ApiError, euApi, mensagemDoErro } from '@/api'
import { useSessaoStore } from '@/stores/sessao'
import Alerta from '@/components/ui/Alerta.vue'
import Botao from '@/components/ui/Botao.vue'
import CaixaSelecao from '@/components/ui/CaixaSelecao.vue'
import CabecalhoAcesso from '@/modulos/acesso/CabecalhoAcesso.vue'
import { destinoDepoisDoAceite, textoAbertura } from './legal/aceite'
import { VERSAO_DOCUMENTOS } from './legal/versao'

const sessao = useSessaoStore()
const rota = useRoute()
const router = useRouter()

const marcado = ref(false)
const enviando = ref(false)
const saindo = ref(false)
const erro = ref<string | null>(null)
const aviso = ref<string | null>(null)

const abertura = computed(() => textoAbertura(sessao.usuario?.aceite))
/**
 * A API já está numa versão maior que a do texto que este site mostra (o site foi atualizado depois de a página
 * abrir): não adianta aceitar daqui; o botão vira "Recarregar a página".
 */
const siteDesatualizado = computed(() => (sessao.usuario?.aceite?.versao_atual ?? 0) > VERSAO_DOCUMENTOS)
/** Versão nova (já aceitou uma anterior) e pode gerenciar a assinatura: mostra o caminho para cancelar sem aceitar. */
const mostrarCancelar = computed(
  () => sessao.usuario?.aceite?.versao_aceita != null && sessao.pode('assinatura.gerenciar'),
)

function recarregarPagina() {
  location.reload()
}

async function aceitar() {
  if (!marcado.value || enviando.value || saindo.value || siteDesatualizado.value) return
  enviando.value = true
  erro.value = null
  aviso.value = null
  try {
    // Sempre a versão do texto que este site mostra (não a que a API diz ser a atual): é essa que a pessoa leu.
    const aceite = await euApi.aceitar(VERSAO_DOCUMENTOS)
    sessao.atualizarAceite(aceite)
    await router.replace(destinoDepoisDoAceite(rota.query.de))
  } catch (e) {
    if (e instanceof ApiError && e.status === 409) {
      // Os textos mudaram enquanto a tela estava aberta: busca a situação nova e pede para ler de novo. Se a API está
      // numa versão maior que a deste site, o botão vira "Recarregar a página" (siteDesatualizado).
      marcado.value = false
      aviso.value = e.mensagem || 'Os termos foram atualizados. Leia a versão nova antes de aceitar.'
      try {
        await sessao.recarregar()
      } catch {
        /* sem conexão: fica o aviso */
      }
    } else {
      erro.value = mensagemDoErro(e)
    }
  } finally {
    enviando.value = false
  }
}

async function sair() {
  if (saindo.value) return
  saindo.value = true
  await sessao.sair()
  saindo.value = false
  router.push({ name: 'entrar' })
}

const itens = [
  { icone: Database, texto: 'Coletamos os dados do seu cadastro, do uso e dos seus clientes só para o Toqqi funcionar. Não vendemos dados.' },
  { icone: Building2, texto: 'A sua empresa controla os dados dos clientes dela. O Toqqi trata esses dados em nome dela.' },
  { icone: UserCheck, texto: 'Você pode pedir acesso, correção ou exclusão dos seus dados em', email: 'privacidade@toqqi.com' },
]
</script>

<template>
  <CabecalhoAcesso titulo="Antes de continuar">
    <p class="mt-1.5 text-[0.95rem] leading-relaxed text-texto-suave" data-teste="abertura">
      {{ abertura }} Eles explicam como tratamos os seus dados e os dos seus clientes, seguindo a LGPD.
    </p>
  </CabecalhoAcesso>

  <Alerta v-if="aviso" tom="atencao" class="mb-5">{{ aviso }}</Alerta>
  <Alerta v-if="erro" tom="erro" class="mb-5">{{ erro }}</Alerta>

  <ul class="flex flex-col gap-3">
    <li v-for="item in itens" :key="item.texto" class="flex items-start gap-3 text-sm leading-relaxed text-texto-suave">
      <span class="flex size-8 shrink-0 items-center justify-center rounded-lg bg-marca-suave text-marca-texto">
        <component :is="item.icone" class="size-4" aria-hidden="true" />
      </span>
      <span class="pt-1">
        {{ item.texto }}
        <template v-if="item.email">
          <a class="link whitespace-nowrap" :href="`mailto:${item.email}`">{{ item.email }}</a>.
        </template>
      </span>
    </li>
  </ul>

  <section class="mt-5 rounded-xl border border-borda bg-superficie-2/60 p-4" aria-labelledby="aceite-cookies">
    <h2 id="aceite-cookies" class="flex items-center gap-2 text-sm font-bold text-texto">
      <Cookie class="size-4 text-texto-fraco" aria-hidden="true" /> Cookies
    </h2>
    <p class="mt-1.5 text-sm leading-relaxed text-texto-suave">
      Não usamos cookies de publicidade nem de análise. Guardamos no seu navegador só o necessário para o Toqqi
      funcionar: a sessão, o tema e preferências da tela. Por isso não há o que recusar.
      <RouterLink to="/privacidade#cookies" target="_blank" class="link">Saiba mais</RouterLink>
    </p>
  </section>

  <div class="mt-6">
    <CaixaSelecao v-model="marcado" rotulo="Li e aceito os Termos de uso e a Política de privacidade">
      Li e aceito os <RouterLink to="/termos" target="_blank" class="link">Termos de uso</RouterLink> e a
      <RouterLink to="/privacidade" target="_blank" class="link">Política de privacidade</RouterLink>.
    </CaixaSelecao>
  </div>

  <div class="mt-6 flex flex-col gap-3">
    <Botao v-if="siteDesatualizado" tamanho="lg" bloco data-teste="recarregar" @click="recarregarPagina">
      Recarregar a página
    </Botao>
    <Botao
      v-else
      tamanho="lg"
      bloco
      :desabilitado="!marcado || saindo"
      :carregando="enviando"
      data-teste="aceitar"
      @click="aceitar"
    >
      Aceitar e continuar
    </Botao>
    <Botao variante="secundario" bloco :carregando="saindo" :desabilitado="enviando" data-teste="sair" @click="sair">Sair</Botao>
  </div>

  <p v-if="mostrarCancelar" class="mt-4 text-center text-xs text-texto-fraco" data-teste="cancelar">
    Não concorda? Você pode <RouterLink to="/assinatura" class="link">cancelar a assinatura</RouterLink>.
  </p>
</template>

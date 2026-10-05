<script setup lang="ts">
// Configurações › Crescimento (etapa 5c): ligar o convite de indicação da tela final da pesquisa, os textos do convite
// e da recompensa, e o texto da oferta que a equipe manda pelo WhatsApp em Crescimento › Oportunidades. Com "Inserir"
// variáveis (o mesmo campo de Configurações › Envios) e as prévias: o cartão como na pesquisa e o balão do WhatsApp.
import { computed, nextTick, onMounted, reactive, ref } from 'vue'
import { onBeforeRouteLeave } from 'vue-router'
import { MessageCircle, Power, Quote, UserPlus } from 'lucide-vue-next'
import { crescimentoApi, mensagemDoErro, type ConfigCrescimento } from '@/api'
import { avisar } from '@/composables/avisos'
import { confirmar } from '@/composables/confirmacao'
import { useFormulario } from '@/composables/formulario'
import { useSessaoStore } from '@/stores/sessao'
import CartaoIndicacao from '@/pesquisa/CartaoIndicacao.vue'
import { TEMA_PADRAO } from '@/pesquisa/tipos'
import CabecalhoPagina from '@/components/app/CabecalhoPagina.vue'
import Alerta from '@/components/ui/Alerta.vue'
import Botao from '@/components/ui/Botao.vue'
import Campo from '@/components/ui/Campo.vue'
import Carregando from '@/components/ui/Carregando.vue'
import Interruptor from '@/components/ui/Interruptor.vue'
import CampoMensagem from './CampoMensagem.vue'
import NavConfiguracoes from './NavConfiguracoes.vue'
import PreviaWhatsapp from './PreviaWhatsapp.vue'
import {
  EXEMPLO_RECOMPENSA,
  LIMITES_CRESCIMENTO,
  PADRAO_CRESCIMENTO,
  normalizarConfigCrescimento,
  previaConvite,
  previaOferta,
  validarConfigCrescimento,
} from './configCrescimento'
import { VARIAVEIS_CONVITE_INDICACAO, VARIAVEIS_OFERTA } from './mensagens'

const sessao = useSessaoStore()
const podeSalvar = computed(() => sessao.pode('configuracoes.gerenciar'))
const carregando = ref(true)
const erroCarga = ref<string | null>(null)
const original = ref('')
const { enviando, erroGeral, erros, executar, limpar } = useFormulario()

const f = reactive<ConfigCrescimento & { recompensa: string; link_avaliacao: string }>({ ...PADRAO_CRESCIMENTO, recompensa: '', link_avaliacao: '' })

function aplicar(c: ConfigCrescimento) {
  Object.assign(f, {
    indicacoes_ativas: !!c.indicacoes_ativas,
    titulo_convite: c.titulo_convite ?? '',
    texto_convite: c.texto_convite ?? '',
    recompensa: c.recompensa ?? '',
    texto_oferta: c.texto_oferta ?? '',
    depoimentos_ativos: !!c.depoimentos_ativos,
    link_avaliacao: c.link_avaliacao ?? '',
  })
  original.value = JSON.stringify(normalizarConfigCrescimento(f))
}

const atual = computed(() => normalizarConfigCrescimento(f))
const alterado = computed(() => !!original.value && JSON.stringify(atual.value) !== original.value)

// Prévias com valores de exemplo: a cliente Maria, da Mercado Bom Preço, e o primeiro nome de quem está logado.
const exemplo = computed(() => ({
  empresa: sessao.conta?.nome ?? 'Sua empresa',
  nome: 'Maria Souza',
  empresa_cliente: 'Mercado Bom Preço',
  representante: sessao.usuario?.nome ?? 'Ana',
}))
const convite = computed(() => previaConvite(f, exemplo.value))
const oferta = computed(() => previaOferta(f, exemplo.value))

async function carregar() {
  carregando.value = true
  erroCarga.value = null
  try {
    aplicar(await crescimentoApi.configuracao())
  } catch (e) {
    erroCarga.value = mensagemDoErro(e)
  } finally {
    carregando.value = false
  }
}

async function focarPrimeiroErro() {
  await nextTick()
  document.querySelector<HTMLElement>('#form-config-crescimento [aria-invalid="true"]')?.focus()
}

async function salvar(): Promise<boolean> {
  limpar()
  const locais = validarConfigCrescimento(f)
  if (Object.keys(locais).length) {
    Object.assign(erros, locais)
    erroGeral.value = 'Confira os campos destacados.'
    focarPrimeiroErro()
    return false
  }
  const ligou = atual.value.indicacoes_ativas && !(JSON.parse(original.value || '{}') as ConfigCrescimento).indicacoes_ativas
  const r = await executar(() => crescimentoApi.salvarConfiguracao(atual.value))
  if (!r) {
    if (Object.keys(erros).length) focarPrimeiroErro()
    return false
  }
  aplicar(r)
  avisar.sucesso(ligou ? 'Convite de indicação ligado. Ele aparece para quem der nota alta nos próximos convites.' : 'Configurações de crescimento salvas.')
  return true
}

function descartar() {
  if (original.value) aplicar(JSON.parse(original.value) as ConfigCrescimento)
  limpar()
}

onBeforeRouteLeave(async () => {
  if (!alterado.value || enviando.value) return true
  return confirmar({
    titulo: 'Sair sem salvar?',
    mensagem: 'Você mudou as configurações de crescimento e ainda não salvou. Se sair agora, as mudanças se perdem.',
    confirmar: 'Sair sem salvar',
    cancelar: 'Continuar editando',
    perigo: true,
  })
})

onMounted(carregar)
</script>

<template>
  <NavConfiguracoes />
  <CabecalhoPagina
    titulo="Crescimento"
    descricao="O convite para quem deu nota alta indicar outra empresa e o texto da oferta que a equipe manda pelo WhatsApp."
  />

  <Carregando v-if="carregando" :linhas="4" />
  <Alerta v-else-if="erroCarga" tom="erro">
    {{ erroCarga }} <button type="button" class="link ml-1" @click="carregar">Tentar de novo</button>
  </Alerta>

  <form v-else id="form-config-crescimento" class="flex flex-col gap-6" novalidate @submit.prevent="salvar">
    <Alerta v-if="!podeSalvar" tom="info">Você pode ver estas configurações, mas só um administrador consegue mudar.</Alerta>
    <Alerta v-if="erroGeral" tom="erro">{{ erroGeral }}</Alerta>

    <fieldset :disabled="!podeSalvar" class="flex min-w-0 flex-col gap-6">
      <legend class="sr-only">Configurações de crescimento</legend>

      <!-- Ligar o convite -->
      <section class="cartao grid gap-6 p-5 sm:p-6 md:grid-cols-3" aria-labelledby="t-ligar-indicacoes">
        <div>
          <div class="mb-3 flex size-10 items-center justify-center rounded-xl bg-marca-suave text-marca-texto"><Power class="size-5" aria-hidden="true" /></div>
          <h2 id="t-ligar-indicacoes" class="text-base font-bold text-texto">Convite de indicação</h2>
          <p class="mt-1 text-sm text-texto-suave">Quem está feliz indica outras empresas. As indicações chegam em Crescimento › Indicações.</p>
        </div>
        <div class="flex flex-col gap-3 md:col-span-2">
          <Interruptor
            v-model="f.indicacoes_ativas"
            rotulo="Convidar quem deu nota alta para indicar"
            descricao="Aparece na tela final da pesquisa para quem deu 9 ou 10 (ou 5 no CSAT), só nos convites enviados a um contato: o link público não tem a quem atribuir a indicação."
            :desabilitado="!podeSalvar"
          />
          <p class="text-sm text-texto-fraco">
            Cada pessoa pode indicar até 3 empresas por pesquisa. O responsável pela empresa de quem indicou recebe um e-mail a cada indicação (sem
            responsável, os administradores).
          </p>
        </div>
      </section>

      <!-- Textos do convite + prévia -->
      <section class="cartao p-5 sm:p-6" aria-labelledby="t-textos-convite">
        <div class="mb-5 flex items-start gap-3">
          <div class="flex size-10 shrink-0 items-center justify-center rounded-xl bg-marca-suave text-marca-texto"><UserPlus class="size-5" aria-hidden="true" /></div>
          <div>
            <h2 id="t-textos-convite" class="text-base font-bold text-texto">Textos do convite</h2>
            <p class="mt-1 text-sm text-texto-suave">O cartão aparece logo depois do agradecimento, com o formulário para indicar.</p>
          </div>
        </div>
        <div class="grid gap-8 lg:grid-cols-[minmax(0,1fr)_minmax(0,24rem)]">
          <div class="flex min-w-0 flex-col gap-5">
            <CampoMensagem
              v-model="f.titulo_convite"
              rotulo="Título"
              :variaveis="VARIAVEIS_CONVITE_INDICACAO"
              :maximo="LIMITES_CRESCIMENTO.titulo_convite"
              :erro="erros.titulo_convite"
            />
            <CampoMensagem
              v-model="f.texto_convite"
              rotulo="Texto"
              multilinha
              :linhas="3"
              :variaveis="VARIAVEIS_CONVITE_INDICACAO"
              :maximo="LIMITES_CRESCIMENTO.texto_convite"
              :erro="erros.texto_convite"
            />
            <CampoMensagem
              v-model="f.recompensa"
              rotulo="Recompensa (opcional)"
              multilinha
              :linhas="2"
              :variaveis="VARIAVEIS_CONVITE_INDICACAO"
              :maximo="LIMITES_CRESCIMENTO.recompensa"
              :placeholder="EXEMPLO_RECOMPENSA"
              :erro="erros.recompensa"
              dica="Só fica registrada no convite: a sua empresa combina e paga do jeito dela. Em branco, o cartão sai sem recompensa."
            />
          </div>
          <div class="min-w-0 lg:sticky lg:top-24 lg:self-start">
            <h3 class="mb-3 text-sm font-bold text-texto">Como o cliente vê</h3>
            <div class="rounded-2xl bg-slate-100 p-3 sm:p-4" role="group" aria-label="Prévia do cartão de indicação" aria-live="polite" data-previa-convite>
              <CartaoIndicacao :convite="convite" :empresa="exemplo.empresa" :cor="TEMA_PADRAO.cor" />
            </div>
            <p class="mt-2 text-xs text-texto-fraco">Exemplo com uma cliente chamada Maria. O cartão segue a cor de cada formulário.</p>
          </div>
        </div>
      </section>

      <!-- Prova social (melhoria 5) -->
      <section class="cartao grid gap-6 p-5 sm:p-6 md:grid-cols-3" aria-labelledby="t-prova-social" data-prova-social>
        <div>
          <div class="mb-3 flex size-10 items-center justify-center rounded-xl bg-marca-suave text-marca-texto"><Quote class="size-5" aria-hidden="true" /></div>
          <h2 id="t-prova-social" class="text-base font-bold text-texto">Depoimentos e avaliações</h2>
          <p class="mt-1 text-sm text-texto-suave">Transforme a nota alta em prova social: depoimentos para o seu site e avaliações no Google.</p>
        </div>
        <div class="flex flex-col gap-4 md:col-span-2">
          <Interruptor
            v-model="f.depoimentos_ativos"
            rotulo="Pedir para publicar o comentário como depoimento"
            descricao="Quem deu 9 ou 10 (ou 5 no CSAT) e deixou um comentário vê “Podemos publicar seu comentário?”. Os autorizados chegam em Crescimento › Depoimentos para você aprovar."
            :desabilitado="!podeSalvar"
          />
          <Campo
            v-model="f.link_avaliacao"
            rotulo="Link para avaliar a sua empresa (opcional)"
            tipo="url"
            placeholder="https://g.page/r/sua-empresa/review"
            :erro="erros.link_avaliacao"
            dica="O link de avaliação do Google (Perfil da Empresa › Pedir avaliações), do Reclame Aqui ou outro. Aparece como botão para quem deu nota alta. Em branco, não aparece."
          />
        </div>
      </section>

      <!-- Oferta + prévia -->
      <section class="cartao p-5 sm:p-6" aria-labelledby="t-texto-oferta">
        <div class="mb-5 flex items-start gap-3">
          <div class="flex size-10 shrink-0 items-center justify-center rounded-xl bg-marca-suave text-marca-texto"><MessageCircle class="size-5" aria-hidden="true" /></div>
          <div>
            <h2 id="t-texto-oferta" class="text-base font-bold text-texto">Oferta pelo WhatsApp</h2>
            <p class="mt-1 text-sm text-texto-suave">
              Em Crescimento › Oportunidades, “Oferecer pelo WhatsApp” abre a conversa com este texto pronto, do WhatsApp de quem está oferecendo.
            </p>
          </div>
        </div>
        <div class="grid gap-8 lg:grid-cols-[minmax(0,1fr)_minmax(0,24rem)]">
          <div class="min-w-0">
            <CampoMensagem
              v-model="f.texto_oferta"
              rotulo="Texto da oferta"
              multilinha
              :linhas="4"
              :variaveis="VARIAVEIS_OFERTA"
              :maximo="LIMITES_CRESCIMENTO.texto_oferta"
              :erro="erros.texto_oferta"
              dica="Sem telefone, a oferta vai por e-mail com o mesmo texto. Dá para ajustar a mensagem no WhatsApp antes de enviar."
            />
          </div>
          <div class="min-w-0 lg:sticky lg:top-24 lg:self-start">
            <h3 class="mb-3 text-sm font-bold text-texto">Como chega no WhatsApp</h3>
            <div aria-live="polite">
              <PreviaWhatsapp :texto="oferta" link="" />
            </div>
            <p class="mt-2 text-xs text-texto-fraco">Exemplo com a cliente Maria, da Mercado Bom Preço.</p>
          </div>
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

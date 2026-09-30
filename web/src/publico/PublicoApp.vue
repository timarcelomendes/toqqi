<script setup lang="ts">
// Página pública de resposta: /r/:token (convite individual) e /f/:codigo (link público).
import { computed, onMounted, ref } from 'vue'
import { ApiError } from '@/api/erros'
import { publicoApi, type PesquisaPublica } from '@/api/publico'
import Pesquisa from '@/pesquisa/Pesquisa.vue'
import { lerParametros } from '@/pesquisa/contexto'
import type { Respostas, TelaFinal } from '@/pesquisa/tipos'

type Estado = 'carregando' | 'pronto' | 'invalido' | 'ja_respondido' | 'erro'

const params = lerParametros(window.location.search)
const rota = (() => {
  const m = window.location.pathname.match(/^\/(r|f)\/([^/?#]+)/)
  return m ? { tipo: m[1] as 'r' | 'f', chave: decodeURIComponent(m[2]!) } : null
})()

const estado = ref<Estado>('carregando')
const mensagemErro = ref('')
const dados = ref<PesquisaPublica | null>(null)

if (params.embed) document.documentElement.classList.add('embed')

const titulo = computed(() => dados.value?.formulario.nome ?? 'Pesquisa')

async function carregar() {
  if (!rota) {
    estado.value = 'invalido'
    return
  }
  estado.value = 'carregando'
  try {
    const r = rota.tipo === 'r' ? await publicoApi.convite(rota.chave) : await publicoApi.formulario(rota.chave)
    dados.value = r
    document.title = r.formulario?.nome || 'Pesquisa'
    estado.value = r.ja_respondido ? 'ja_respondido' : 'pronto'
  } catch (e) {
    if (e instanceof ApiError && (e.status === 404 || e.codigo === 'link_invalido')) estado.value = 'invalido'
    else {
      mensagemErro.value =
        e instanceof ApiError && e.status !== 0 && e.status < 500
          ? e.mensagem
          : 'Não conseguimos carregar a pesquisa. Confira sua internet e tente de novo.'
      estado.value = 'erro'
    }
  }
}

async function enviar(respostas: Respostas): Promise<TelaFinal | null> {
  try {
    const r =
      rota!.tipo === 'r'
        ? await publicoApi.responderConvite(rota!.chave, respostas)
        : await publicoApi.responderFormulario(rota!.chave, {
            respostas,
            canal: params.canal,
            ...(params.referencia ? { referencia: params.referencia } : {}),
            ...(Object.keys(params.contexto).length ? { contexto: params.contexto } : {}),
          })
    // 200 silencioso (resposta repetida) pode vir sem corpo: usa os textos do tema.
    return r && typeof r === 'object' ? r : ({ titulo_final: '', texto_final: '' } as TelaFinal)
  } catch (e) {
    if (e instanceof ApiError && e.codigo === 'ja_respondido') {
      estado.value = 'ja_respondido'
      return null
    }
    if (e instanceof ApiError && (e.status === 404 || e.codigo === 'link_invalido')) {
      estado.value = 'invalido'
      return null
    }
    if (e instanceof ApiError && e.status === 0) {
      throw { mensagem: 'Sem conexão no momento. Suas respostas continuam aqui: tente enviar de novo.' }
    }
    throw { mensagem: e instanceof ApiError ? e.mensagem : undefined, campos: e instanceof ApiError ? e.campos : undefined }
  }
}

onMounted(carregar)
</script>

<template>
  <main :class="params.embed ? 'min-h-0' : 'flex min-h-dvh flex-col'" :aria-label="titulo">
    <div v-if="estado === 'carregando'" class="flex flex-1 items-center justify-center py-24" role="status">
      <svg viewBox="0 0 24 24" class="size-8 animate-spin text-slate-400" fill="none" stroke="currentColor" stroke-width="2.5" aria-hidden="true"><path d="M12 3a9 9 0 1 0 9 9" stroke-linecap="round" /></svg>
      <span class="sr-only">Carregando a pesquisa…</span>
    </div>

    <Pesquisa
      v-else-if="estado === 'pronto' && dados"
      :formulario="dados.formulario"
      :variaveis="dados.variaveis"
      :nota-inicial="params.nota"
      :compacto="params.embed"
      :enviar="enviar"
    />

    <section v-else class="mx-auto flex w-full max-w-md flex-1 flex-col items-center justify-center px-6 py-16 text-center">
      <span
        class="mb-4 flex size-14 items-center justify-center rounded-full"
        :class="estado === 'ja_respondido' ? 'bg-emerald-50 text-emerald-600' : 'bg-slate-100 text-slate-500'"
        aria-hidden="true"
      >
        <svg v-if="estado === 'ja_respondido'" viewBox="0 0 24 24" class="size-8" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12.5l4.5 4.5L19 7.5" /></svg>
        <svg v-else viewBox="0 0 24 24" class="size-8" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="12" cy="12" r="9.5" /><path d="M12 7.5v5.5M12 16.5v.3" /></svg>
      </span>
      <template v-if="estado === 'ja_respondido'">
        <h1 class="text-xl font-extrabold text-slate-900">Você já respondeu esta pesquisa</h1>
        <p class="mt-2 text-slate-600">Obrigado! Sua opinião já chegou até a gente.</p>
      </template>
      <template v-else-if="estado === 'invalido'">
        <h1 class="text-xl font-extrabold text-slate-900">Este link não está mais valendo</h1>
        <p class="mt-2 text-slate-600">A pesquisa pode ter sido encerrada ou o endereço veio incompleto. Se recebeu por mensagem, confira se copiou o link inteiro.</p>
      </template>
      <template v-else>
        <h1 class="text-xl font-extrabold text-slate-900">Não deu para abrir a pesquisa</h1>
        <p class="mt-2 text-slate-600">{{ mensagemErro }}</p>
        <button
          type="button"
          class="mt-6 inline-flex h-12 items-center rounded-xl bg-slate-900 px-6 font-bold text-white hover:bg-slate-700 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-slate-900"
          @click="carregar"
        >
          Tentar de novo
        </button>
      </template>
    </section>

    <footer v-if="!params.embed && estado !== 'carregando'" class="pb-6 text-center text-xs text-slate-400">
      Pesquisa feita com <a href="https://toqqi.com" class="font-semibold text-slate-500 hover:text-slate-700" target="_blank" rel="noopener">toqqi</a>
    </footer>
  </main>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { Check, ImagePlus, Trash2 } from 'lucide-vue-next'
import type { Tema } from '@/api/tipos'
import { corValida } from '@/pesquisa/cor'
import AreaTexto from '@/components/ui/AreaTexto.vue'
import Botao from '@/components/ui/Botao.vue'
import Campo from '@/components/ui/Campo.vue'
import CampoVariaveis from './CampoVariaveis.vue'

const props = defineProps<{ erros: Record<string, string> }>()
const tema = defineModel<Tema>('tema', { required: true })
const descricao = defineModel<string | null>('descricao', { default: '' })

const PRESETS = [
  { cor: '#d63a18', nome: 'Coral' },
  { cor: '#2563eb', nome: 'Azul' },
  { cor: '#0891b2', nome: 'Turquesa' },
  { cor: '#059669', nome: 'Verde' },
  { cor: '#7c3aed', nome: 'Roxo' },
  { cor: '#db2777', nome: 'Rosa' },
  { cor: '#ea580c', nome: 'Laranja' },
  { cor: '#0f172a', nome: 'Grafite' },
]
const LIMITE_LOGO = 300 * 1024

const corTexto = ref(tema.value.cor)
const erroCor = ref<string | null>(null)
// Descartar alterações muda a cor por fora: acompanha.
watch(
  () => tema.value.cor,
  (c) => {
    if (corValida(corTexto.value, '') !== c) {
      corTexto.value = c
      erroCor.value = null
    }
  },
)
const erroLogo = ref<string | null>(null)
const entrada = ref<HTMLInputElement | null>(null)
const logoEhArquivo = computed(() => tema.value.logo_url?.startsWith('data:') ?? false)
const erro = (c: string) => props.erros[`tema.${c}`] ?? null

function definirCor(c: string) {
  tema.value.cor = corValida(c)
  corTexto.value = tema.value.cor
  erroCor.value = null
}

function aoDigitarCor(v: string) {
  corTexto.value = v
  const t = v.trim().startsWith('#') ? v.trim() : `#${v.trim()}`
  if (/^#[0-9a-f]{6}$/i.test(t)) {
    tema.value.cor = t.toLowerCase()
    erroCor.value = null
  } else erroCor.value = 'Use o formato #RRGGBB, ex.: #d63a18.'
}

function enviarLogo(f: File | undefined) {
  erroLogo.value = null
  if (!f) return
  if (!/^image\/(png|jpeg|svg\+xml|webp|gif)$/.test(f.type)) {
    erroLogo.value = 'Use uma imagem PNG, JPG, SVG ou WebP.'
    return
  }
  if (f.size > LIMITE_LOGO) {
    erroLogo.value = 'A imagem passa de 300 KB. Diminua o tamanho ou use um endereço (URL).'
    return
  }
  const leitor = new FileReader()
  leitor.onload = () => {
    tema.value.logo_url = String(leitor.result)
  }
  leitor.onerror = () => (erroLogo.value = 'Não conseguimos ler a imagem. Tente outra.')
  leitor.readAsDataURL(f)
}
</script>

<template>
  <div class="flex flex-col gap-5">
    <section class="cartao flex flex-col gap-4 p-5" aria-labelledby="t-cor">
      <h2 id="t-cor" class="font-bold text-texto">Cor e logo</h2>
      <fieldset>
        <legend class="mb-2 text-sm font-semibold text-texto">Cor principal</legend>
        <div class="flex flex-wrap items-center gap-2">
          <button
            v-for="p in PRESETS"
            :key="p.cor"
            type="button"
            class="flex size-9 items-center justify-center rounded-full ring-offset-2 ring-offset-superficie transition focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-foco"
            :class="tema.cor === p.cor ? 'ring-2 ring-texto' : ''"
            :style="{ backgroundColor: p.cor }"
            :aria-label="p.nome"
            :aria-pressed="tema.cor === p.cor"
            @click="definirCor(p.cor)"
          >
            <Check v-if="tema.cor === p.cor" class="size-4 text-white" aria-hidden="true" />
          </button>
          <label class="relative flex size-9 cursor-pointer items-center justify-center overflow-hidden rounded-full border border-borda-forte bg-superficie-2" title="Outra cor">
            <span class="sr-only">Escolher outra cor</span>
            <input type="color" :value="tema.cor" class="absolute inset-0 size-full cursor-pointer opacity-0" @input="definirCor(($event.target as HTMLInputElement).value)" />
            <span class="size-5 rounded-full" :style="{ background: 'conic-gradient(red, yellow, lime, aqua, blue, magenta, red)' }" aria-hidden="true" />
          </label>
          <Campo :model-value="corTexto" rotulo="Código da cor" rotulo-oculto class="w-32" maxlength="7" spellcheck="false" :erro="erroCor ?? erro('cor')" @update:model-value="aoDigitarCor" />
        </div>
        <p class="mt-2 text-sm text-texto-fraco">Usada nos botões e na barra de progresso. O texto dos botões fica branco ou preto, o que ler melhor.</p>
      </fieldset>

      <div class="flex flex-col gap-2">
        <p class="text-sm font-semibold text-texto">Logo <span class="font-normal text-texto-fraco">(opcional)</span></p>
        <div v-if="tema.logo_url" class="flex items-center gap-3 rounded-xl border border-borda bg-white p-3">
          <img :src="tema.logo_url" alt="Logo atual" class="max-h-12 max-w-48 object-contain" />
          <Botao variante="perigo-suave" tamanho="sm" class="ml-auto" @click="tema.logo_url = null"><Trash2 class="size-4" aria-hidden="true" /> Tirar logo</Botao>
        </div>
        <div class="flex flex-col gap-2 sm:flex-row sm:items-end">
          <Campo
            v-if="!logoEhArquivo"
            :model-value="tema.logo_url ?? ''"
            rotulo="Endereço da imagem"
            tipo="url"
            placeholder="https://suaempresa.com.br/logo.png"
            class="flex-1"
            :erro="erro('logo_url')"
            @update:model-value="(v: string) => (tema.logo_url = v.trim() || null)"
          />
          <Botao variante="secundario" @click="entrada?.click()"><ImagePlus class="size-4" aria-hidden="true" /> Enviar imagem</Botao>
          <input ref="entrada" type="file" accept="image/png,image/jpeg,image/svg+xml,image/webp,image/gif" class="sr-only" tabindex="-1" aria-hidden="true" @change="enviarLogo(($event.target as HTMLInputElement).files?.[0]); ($event.target as HTMLInputElement).value = ''" />
        </div>
        <p class="text-sm text-texto-fraco">Imagem até 300 KB. Fundo transparente fica melhor.</p>
        <p v-if="erroLogo" class="text-sm font-medium text-erro" role="alert">{{ erroLogo }}</p>
      </div>
    </section>

    <section class="cartao flex flex-col gap-3 p-5" aria-labelledby="t-modo">
      <h2 id="t-modo" class="font-bold text-texto">Jeito de mostrar</h2>
      <div class="grid gap-2 sm:grid-cols-2" role="radiogroup" aria-labelledby="t-modo">
        <label
          v-for="m in [
            { v: 'uma_por_vez', t: 'Uma pergunta por vez', d: 'Mais rápido no celular. Ao tocar numa nota, já passa para a próxima.' },
            { v: 'paginas', t: 'Em páginas', d: 'Várias perguntas juntas. Use quebras de página para dividir.' },
          ] as const"
          :key="m.v"
          class="flex cursor-pointer flex-col gap-0.5 rounded-xl border p-3 transition-colors has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-offset-2 has-[:focus-visible]:outline-foco"
          :class="tema.modo === m.v ? 'border-marca bg-marca-suave' : 'border-borda-forte hover:bg-superficie-2'"
        >
          <input v-model="tema.modo" type="radio" :value="m.v" class="sr-only" />
          <span class="text-sm font-bold text-texto">{{ m.t }}</span>
          <span class="text-xs text-texto-suave">{{ m.d }}</span>
        </label>
      </div>
    </section>

    <section class="cartao flex flex-col gap-4 p-5" aria-labelledby="t-textos">
      <div>
        <h2 id="t-textos" class="font-bold text-texto">Textos</h2>
        <p class="text-sm text-texto-fraco">Use as variáveis para personalizar: {empresa} vira o nome da sua empresa, {nome} o primeiro nome do cliente.</p>
      </div>
      <CampoVariaveis v-model="tema.titulo_abertura" rotulo="Título de boas-vindas" opcional :maximo="150" :erro="erro('titulo_abertura')" dica="Se preencher, aparece uma tela de abertura antes da primeira pergunta." />
      <CampoVariaveis v-model="tema.texto_abertura" rotulo="Texto de boas-vindas" opcional multilinha :maximo="600" :erro="erro('texto_abertura')" />
      <CampoVariaveis v-model="tema.texto_botao" rotulo="Texto do botão de enviar" sem-variaveis :maximo="40" placeholder="Enviar" :erro="erro('texto_botao')" />
      <CampoVariaveis v-model="tema.titulo_final" rotulo="Título do agradecimento" :maximo="150" placeholder="Obrigado!" :erro="erro('titulo_final')" />
      <CampoVariaveis v-model="tema.texto_final" rotulo="Texto do agradecimento" multilinha :maximo="600" :erro="erro('texto_final')" />
    </section>

    <section class="cartao flex flex-col gap-3 p-5" aria-labelledby="t-desc">
      <h2 id="t-desc" class="font-bold text-texto">Anotação interna</h2>
      <AreaTexto :model-value="descricao ?? ''" rotulo="Descrição" opcional :linhas="2" :maximo="500" dica="Só a sua equipe vê. Ajuda a lembrar para que serve este formulário." :erro="erros.descricao" @update:model-value="(v) => (descricao = v)" />
    </section>
  </div>
</template>

<script setup lang="ts">
// "Sua marca nas pesquisas" no "Comece por aqui" (etapa 5h, docs/api-etapa-5h.md §1). Só para configuracoes.gerenciar
// (quem mostra decide); opcional, fora dos 4 passos. Mostra se a conta já tem logo e cor (GET /conta/marca) e abre o
// modal que envia o logo (PUT /conta/logo) e salva a cor (PUT /conta/marca). Feito = tem logo ou cor própria.
import { computed, onMounted, ref } from 'vue'
import { Palette } from 'lucide-vue-next'
import { marcaApi, type MarcaConta } from '@/api'
import { useSessaoStore } from '@/stores/sessao'
import Botao from '@/components/ui/Botao.vue'
import Etiqueta from '@/components/ui/Etiqueta.vue'
import ModalMarca from './ModalMarca.vue'
import { COR_DOS_MODELOS, marcaFeita } from './logica'

const sessao = useSessaoStore()
const marca = ref<MarcaConta | null>(null)
const aberto = ref(false)
const logoUrl = computed(() => sessao.conta?.logo_url ?? null)
const temLogo = computed(() => !!logoUrl.value || !!marca.value?.tem_logo)
const feito = computed(() => marcaFeita({ cor: marca.value?.cor ?? null, tem_logo: temLogo.value }))

onMounted(async () => {
  try {
    marca.value = await marcaApi.obter()
  } catch {
    marca.value = null // sem a leitura, o cartão mostra o que a sessão sabe (o logo) e o botão continua
  }
})

function aoSalvarCor(cor: string) {
  marca.value = { cor, tem_logo: temLogo.value }
}
function aoTrocarLogo(url: string | null) {
  sessao.atualizarConta({ logo_url: url })
  marca.value = { cor: marca.value?.cor ?? null, tem_logo: !!url }
}
</script>

<template>
  <section class="cartao flex flex-col gap-4 p-5" aria-labelledby="t-marca" data-cartao-marca>
    <header class="flex items-start gap-3">
      <span class="flex size-10 shrink-0 items-center justify-center rounded-xl bg-marca-suave text-marca-texto" aria-hidden="true">
        <Palette class="size-5" />
      </span>
      <div class="min-w-0 flex-1">
        <div class="flex flex-wrap items-center gap-x-2 gap-y-1">
          <h2 id="t-marca" class="text-base font-bold text-texto">Sua marca nas pesquisas</h2>
          <Etiqueta v-if="feito" tom="sucesso" data-marca-feita>Feito</Etiqueta>
          <Etiqueta v-else>Opcional</Etiqueta>
        </div>
        <p class="mt-0.5 text-sm text-texto-suave">O logo e a cor que seus clientes veem na pesquisa e nos e-mails.</p>
      </div>
    </header>

    <dl class="divide-y divide-borda rounded-xl bg-superficie-2 text-sm">
      <div class="flex min-h-12 items-center justify-between gap-3 px-3.5 py-2">
        <dt class="font-semibold text-texto-suave">Logo</dt>
        <dd class="flex min-w-0 items-center justify-end" data-marca-logo>
          <img v-if="logoUrl" :src="logoUrl" alt="Logo da sua empresa" class="max-h-7 max-w-36 object-contain" />
          <span v-else-if="temLogo" class="font-semibold text-texto">Enviado</span>
          <span v-else class="text-texto-fraco">Ainda não tem</span>
        </dd>
      </div>
      <div class="flex min-h-12 items-center justify-between gap-3 px-3.5 py-2">
        <dt class="font-semibold text-texto-suave">Cor</dt>
        <dd class="flex min-w-0 items-center justify-end gap-2" data-marca-cor>
          <span
            class="size-5 shrink-0 rounded-md ring-1 ring-inset ring-black/10 dark:ring-white/20"
            :style="{ backgroundColor: marca?.cor ?? COR_DOS_MODELOS }"
            aria-hidden="true"
          />
          <span v-if="marca?.cor" class="truncate font-mono font-semibold text-texto">{{ marca.cor }}</span>
          <span v-else class="truncate text-texto-fraco">A dos modelos</span>
        </dd>
      </div>
    </dl>

    <Botao variante="secundario" class="self-start" data-escolher-marca @click="aberto = true">
      <Palette class="size-4" aria-hidden="true" /> Escolher logo e cor
    </Botao>

    <ModalMarca
      v-model:aberto="aberto"
      :cor="marca?.cor ?? null"
      :logo-url="logoUrl"
      :empresa="sessao.conta?.nome ?? 'sua empresa'"
      @cor-salva="aoSalvarCor"
      @logo-trocado="aoTrocarLogo"
    />
  </section>
</template>

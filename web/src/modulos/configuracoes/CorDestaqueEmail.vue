<script setup lang="ts">
// Cor de destaque dos e-mails (Configurações › Envios › Visual dos e-mails): a do formulário de cada envio (padrão) ou
// uma cor da conta, com 6 sugestões, o seletor do sistema e o campo #RRGGBB. Avisa quando a cor é clara demais para
// texto branco: o botão "Responder pesquisa" sai com o texto escuro (a regra de contraste da API).
import { computed, useId } from 'vue'
import { AlertTriangle, Check } from 'lucide-vue-next'
import Campo from '@/components/ui/Campo.vue'
import Interruptor from '@/components/ui/Interruptor.vue'
import { COR_PADRAO_EMAIL, SUGESTOES_COR_EMAIL, corDestaque, corHexValida, normalizarCorHex, textoDoBotaoEscuro } from './visualEmail'

const props = defineProps<{
  /** A cor do tema do formulário dos convites (null se não deu para saber). */
  corFormulario: string | null
  nomeFormulario?: string | null
  /** Erro do campo `email_cor` (conferência antes de salvar ou da API). */
  erro?: string | null
}>()
const usarFormulario = defineModel<boolean>('usarFormulario', { required: true })
/** O que está no campo #RRGGBB (pode estar incompleto enquanto a pessoa digita). */
const cor = defineModel<string>('cor', { required: true })
const id = useId()

const corLida = computed(() => normalizarCorHex(cor.value))
const erroLocal = computed(() => (cor.value.trim() && !corLida.value ? 'Use o formato #RRGGBB, por exemplo #D63A18.' : null))
const escura = computed(() => !usarFormulario.value && textoDoBotaoEscuro(corLida.value))
// A cor que vale com "Usar a cor do formulário" ligado (sem cor válida no formulário, o coral padrão).
const corDoFormulario = computed(() => corDestaque(null, props.corFormulario))
const formularioSemCor = computed(() => !!props.corFormulario && !corHexValida(props.corFormulario))

// Ao desligar "Usar a cor do formulário", começa pela cor que já estava valendo (a prévia não pula). Feito aqui, junto
// com a troca, e não num watch: o campo #RRGGBB nasce já com a cor (criado e atualizado no mesmo ciclo, o v-model do
// campo voltava a ficar vazio).
const usar = computed({
  get: () => usarFormulario.value,
  set: (v: boolean) => {
    if (!v && !normalizarCorHex(cor.value)) cor.value = corDoFormulario.value.toUpperCase()
    usarFormulario.value = v
  },
})

function escolher(c: string) {
  cor.value = normalizarCorHex(c) ?? cor.value
}
/** Ao sair do campo, mostra a cor no formato da API (#RRGGBB, maiúsculas). */
function arrumar() {
  if (corLida.value) cor.value = corLida.value
}
</script>

<template>
  <div class="flex flex-col gap-3" data-cor-destaque>
    <Interruptor
      v-model="usar"
      rotulo="Usar a cor do formulário"
      descricao="Cada e-mail sai com a cor do formulário da pesquisa: na faixa do topo e no botão “Responder pesquisa”. Desligado, vale a cor que você escolher para todos."
    />
    <p v-if="usarFormulario" class="flex items-center gap-2 text-sm text-texto-suave" data-cor-formulario>
      <span class="size-4 shrink-0 rounded-full border border-black/10 dark:border-white/25" :style="{ backgroundColor: corDoFormulario }" aria-hidden="true" />
      <span v-if="corFormulario && !formularioSemCor">
        Agora: <span class="font-mono">{{ corDoFormulario.toUpperCase() }}</span><template v-if="nomeFormulario">, do formulário “{{ nomeFormulario }}”</template>.
      </span>
      <span v-else>Sem a cor do formulário, vale o coral do Toqqi (<span class="font-mono">{{ COR_PADRAO_EMAIL }}</span>).</span>
    </p>

    <fieldset v-else class="flex min-w-0 flex-col gap-2" :aria-describedby="`${id}-uso`">
      <legend class="mb-1 text-sm font-semibold text-texto">Cor de destaque</legend>
      <div class="flex flex-wrap items-center gap-2">
        <button
          v-for="s in SUGESTOES_COR_EMAIL"
          :key="s.cor"
          type="button"
          class="flex size-9 items-center justify-center rounded-full border border-black/10 ring-offset-2 ring-offset-superficie transition focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-foco disabled:cursor-not-allowed disabled:opacity-55 dark:border-white/25"
          :class="corLida === s.cor ? 'ring-2 ring-texto' : ''"
          :style="{ backgroundColor: s.cor }"
          :aria-label="`${s.nome} (${s.cor})`"
          :aria-pressed="corLida === s.cor"
          :data-sugestao="s.cor"
          @click="escolher(s.cor)"
        >
          <Check v-if="corLida === s.cor" class="size-4 text-white" aria-hidden="true" />
        </button>
        <label
          class="relative flex size-9 cursor-pointer items-center justify-center overflow-hidden rounded-full border border-borda-forte bg-superficie-2 has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-offset-2 has-[:focus-visible]:outline-foco"
          title="Outra cor"
        >
          <span class="sr-only">Escolher outra cor</span>
          <input
            type="color"
            :value="(corLida ?? corDoFormulario).toLowerCase()"
            class="absolute inset-0 size-full cursor-pointer opacity-0 disabled:cursor-not-allowed"
            @input="escolher(($event.target as HTMLInputElement).value)"
          />
          <span class="size-5 rounded-full" :style="{ background: 'conic-gradient(red, yellow, lime, aqua, blue, magenta, red)' }" aria-hidden="true" />
        </label>
        <Campo
          v-model="cor"
          rotulo="Código da cor"
          rotulo-oculto
          class="w-36"
          maxlength="7"
          spellcheck="false"
          autocomplete="off"
          placeholder="#RRGGBB"
          :erro="erroLocal ?? erro"
          @blur="arrumar"
        />
      </div>
      <p :id="`${id}-uso`" class="text-sm text-texto-fraco">Vale para a faixa do topo, o botão “Responder pesquisa” e os links do texto. Os botões da nota continuam vermelho, amarelo e verde.</p>
    </fieldset>

    <!-- Região sempre presente: o aviso que aparece é lido pelo leitor de tela -->
    <div role="status" aria-live="polite">
      <p v-if="escura" class="flex items-start gap-1.5 text-sm font-medium text-atencao" data-aviso-contraste>
        <AlertTriangle class="mt-0.5 size-4 shrink-0" aria-hidden="true" />
        Cor clara: o texto do botão vai ficar escuro, para continuar fácil de ler.
      </p>
    </div>
  </div>
</template>

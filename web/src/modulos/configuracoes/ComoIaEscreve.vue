<script setup lang="ts">
// Configurações › IA (etapa 5d, docs/api-etapa-5d.md §6.4): "Como a IA escreve". O modelo e o estilo da conta (valem
// para o assistente, o resumo do painel, o parecer dos relatórios e os passos das ações) e se as ações criadas a partir
// de uma resposta ganham passos sugeridos. Cada mudança é salva na hora, só com o campo que mudou (uma de cada vez, na
// ordem); se der erro, volta como estava e avisa. Não há modo só leitura: a tela e o GET /conta/ia já pedem
// configuracoes.gerenciar.
import { computed, ref, watch } from 'vue'
import { PenLine } from 'lucide-vue-next'
import { iaApi, mensagemDoErro, type ConfigIa, type DadosConfigIa } from '@/api'
import { avisar } from '@/composables/avisos'
import Interruptor from '@/components/ui/Interruptor.vue'
import { textoEscritaSalva, type CampoEscritaIa } from '@/modulos/ia/logica'
import EscolhaIa from './EscolhaIa.vue'

const props = defineProps<{ dados: ConfigIa }>()
const emit = defineEmits<{ salvo: [ConfigIa] }>()

interface Valores {
  modelo: string
  estilo: string
  passos_acoes: boolean
}

function valoresDe(d: ConfigIa): Valores {
  return { modelo: d.modelo ?? '', estilo: d.estilo ?? '', passos_acoes: !!d.passos_acoes }
}

const modelos = computed(() => (Array.isArray(props.dados.modelos) ? props.dados.modelos : []))
const estilos = computed(() => (Array.isArray(props.dados.estilos) ? props.dados.estilos : []))

/** O que está na tela (muda na hora do clique) e o que o servidor confirmou por último. */
const valores = ref<Valores>(valoresDe(props.dados))
let confirmados: Valores = valoresDe(props.dados)
/** Quantas mudanças estão na fila (salvas uma de cada vez, para as respostas chegarem na ordem). */
const salvando = ref(0)
let fila: Promise<void> = Promise.resolve()

// Os dados da tela mudaram por fora (leitura nova ou a análise ligada/desligada): acompanha, se nada estiver indo.
watch(
  () => props.dados,
  (d) => {
    confirmados = valoresDe(d)
    if (!salvando.value) valores.value = { ...confirmados }
  },
)

function definir(campo: CampoEscritaIa, valor: string | boolean) {
  valores.value = { ...valores.value, [campo]: valor }
}

async function salvar(campo: CampoEscritaIa) {
  const valor = valores.value[campo]
  if (valor === confirmados[campo]) return
  try {
    const r = await iaApi.atualizar({ [campo]: valor } as DadosConfigIa)
    confirmados = valoresDe(r)
    // A tela fica com o que foi salvo (se a pessoa não mudou de novo enquanto ia).
    if (valores.value[campo] === valor) definir(campo, confirmados[campo])
    emit('salvo', r)
    avisar.sucesso(textoEscritaSalva(campo, { ...r, modelos: r.modelos ?? modelos.value, estilos: r.estilos ?? estilos.value }))
  } catch (e) {
    definir(campo, confirmados[campo])
    avisar.erro(mensagemDoErro(e))
  }
}

function mudar(campo: CampoEscritaIa, valor: string | boolean) {
  definir(campo, valor)
  salvando.value++
  fila = fila.then(() => salvar(campo)).finally(() => {
    salvando.value--
  })
}
</script>

<template>
  <section class="cartao grid grid-cols-1 gap-6 p-5 sm:p-6 md:grid-cols-3" aria-labelledby="t-ia-escrita" data-como-ia-escreve>
    <div>
      <div class="mb-3 flex size-10 items-center justify-center rounded-xl bg-marca-suave text-marca-texto"><PenLine class="size-5" aria-hidden="true" /></div>
      <h2 id="t-ia-escrita" class="text-base font-bold text-texto">Como a IA escreve</h2>
      <p class="mt-1 text-sm text-texto-suave">
        Vale para o ToqqiAI, o resumo do painel, o parecer dos relatórios e os passos das ações. A análise de cada comentário continua igual.
      </p>
    </div>
    <div class="flex min-w-0 flex-col gap-6 md:col-span-2" :aria-busy="salvando > 0 || undefined">
      <EscolhaIa
        v-if="modelos.length"
        :model-value="valores.modelo"
        legenda="Modelo"
        :opcoes="modelos"
        data-escolha="modelo"
        @update:model-value="mudar('modelo', $event)"
      />
      <EscolhaIa
        v-if="estilos.length"
        :model-value="valores.estilo"
        legenda="Estilo"
        :opcoes="estilos"
        data-escolha="estilo"
        @update:model-value="mudar('estilo', $event)"
      />
      <Interruptor
        :model-value="valores.passos_acoes"
        rotulo="Sugerir passos nas ações"
        descricao="Ao criar uma ação a partir de uma resposta, a IA sugere até 3 passos. Não gasta a cota do plano."
        @update:model-value="mudar('passos_acoes', $event)"
      />
    </div>
  </section>
</template>

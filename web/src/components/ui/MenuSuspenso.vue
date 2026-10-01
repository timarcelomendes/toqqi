<script setup lang="ts">
import { nextTick, onBeforeUnmount, ref, useId, watch } from 'vue'

const props = withDefaults(
  defineProps<{
    rotulo: string
    alinhar?: 'esquerda' | 'direita'
    /** Posição fixa na tela: use dentro de áreas com rolagem (ex.: tabelas), para o menu não ser cortado. */
    fixo?: boolean
  }>(),
  { alinhar: 'direita' },
)
// Fora da tela até medir: o menu "fixo" nunca entra no fluxo (senão empurraria o botão antes da medida).
const estiloFixo = ref<Record<string, string>>({ top: '-9999px', left: '-9999px' })

function posicionar() {
  const gatilho = raiz.value?.querySelector<HTMLElement>('[aria-haspopup]')
  if (!props.fixo || !gatilho) return
  const r = gatilho.getBoundingClientRect()
  const alturaMenu = menu.value?.offsetHeight ?? 200
  const cabeAbaixo = r.bottom + 8 + alturaMenu <= window.innerHeight
  estiloFixo.value = {
    position: 'fixed',
    top: `${cabeAbaixo ? r.bottom + 8 : Math.max(8, r.top - 8 - alturaMenu)}px`,
    ...(props.alinhar === 'direita' ? { right: `${window.innerWidth - r.right}px` } : { left: `${r.left}px` }),
  }
}

const aberto = ref(false)
const raiz = ref<HTMLElement | null>(null)
const menu = ref<HTMLElement | null>(null)
const id = `menu-${useId()}`

function itens(): HTMLElement[] {
  return menu.value ? Array.from(menu.value.querySelectorAll<HTMLElement>('[role="menuitem"]')) : []
}

async function abrir(focarUltimo = false) {
  aberto.value = true
  await nextTick()
  posicionar()
  const lista = itens()
  ;(focarUltimo ? lista[lista.length - 1] : lista[0])?.focus()
}

function fechar(devolverFoco = true) {
  aberto.value = false
  if (devolverFoco) raiz.value?.querySelector<HTMLElement>('[aria-haspopup]')?.focus()
}

function aoTeclarMenu(e: KeyboardEvent) {
  const lista = itens()
  const i = lista.indexOf(document.activeElement as HTMLElement)
  if (e.key === 'ArrowDown') lista[(i + 1) % lista.length]?.focus()
  else if (e.key === 'ArrowUp') lista[(i - 1 + lista.length) % lista.length]?.focus()
  else if (e.key === 'Home') lista[0]?.focus()
  else if (e.key === 'End') lista[lista.length - 1]?.focus()
  else if (e.key === 'Escape') fechar()
  else if (e.key === 'Tab') return fechar(false)
  else return
  e.preventDefault()
}

/**
 * Escolheu um item: o menu fecha e o foco volta ao botão do menu (para o teclado não se perder), a não ser
 * que a ação do item já tenha levado o foco para outro lugar (ex.: abriu uma janela de confirmação).
 */
function aoEscolher() {
  const foco = document.activeElement
  const ficouNoMenu = !foco || foco === document.body || !!menu.value?.contains(foco)
  fechar(ficouNoMenu)
}

function cliqueFora(e: MouseEvent) {
  if (raiz.value && !raiz.value.contains(e.target as Node)) fechar(false)
}

const fecharSemFoco = () => fechar(false)

/** Rolou a página com o menu "fixo" aberto: ele acompanha o botão; se o botão sair da tela, fecha. */
function aoRolar() {
  const gatilho = raiz.value?.querySelector<HTMLElement>('[aria-haspopup]')
  if (!gatilho) return fecharSemFoco()
  const r = gatilho.getBoundingClientRect()
  if (r.bottom < 0 || r.top > window.innerHeight) fecharSemFoco()
  else posicionar()
}

watch(aberto, (v) => {
  if (v) {
    document.addEventListener('mousedown', cliqueFora)
    if (props.fixo) {
      window.addEventListener('scroll', aoRolar, true)
      window.addEventListener('resize', aoRolar)
    }
  } else {
    document.removeEventListener('mousedown', cliqueFora)
    window.removeEventListener('scroll', aoRolar, true)
    window.removeEventListener('resize', aoRolar)
  }
})
onBeforeUnmount(() => {
  document.removeEventListener('mousedown', cliqueFora)
  window.removeEventListener('scroll', aoRolar, true)
  window.removeEventListener('resize', aoRolar)
})
</script>

<template>
  <div ref="raiz" class="relative">
    <slot
      name="gatilho"
      :props="{
        'aria-haspopup': 'menu' as const,
        'aria-expanded': aberto,
        'aria-controls': id,
        'aria-label': rotulo,
        onClick: () => (aberto ? fechar(false) : abrir()),
        onKeydown: (e: KeyboardEvent) => {
          if (e.key === 'ArrowDown') { e.preventDefault(); abrir() }
          else if (e.key === 'ArrowUp') { e.preventDefault(); abrir(true) }
          else if (e.key === 'Escape' && aberto) { e.preventDefault(); fechar() }
        },
      }"
    />
    <div
      v-show="aberto"
      :id="id"
      ref="menu"
      role="menu"
      :aria-label="rotulo"
      class="z-40 min-w-56 overflow-hidden rounded-xl border border-borda bg-superficie p-1.5 text-left shadow-lg animate-surgir"
      :class="fixo ? 'fixed' : ['absolute mt-2', alinhar === 'direita' ? 'right-0' : 'left-0']"
      :style="fixo ? estiloFixo : undefined"
      @keydown="aoTeclarMenu"
      @click="aoEscolher"
    >
      <slot />
    </div>
  </div>
</template>

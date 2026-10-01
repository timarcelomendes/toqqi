import { afterEach, describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import { nextTick, ref } from 'vue'
import BarraGrupos from '@/components/app/BarraGrupos.vue'
import GraficoEvolucao from '@/modulos/painel/GraficoEvolucao.vue'
import SeletorNota from '@/modulos/respostas/SeletorNota.vue'
import SeloNota from '@/modulos/respostas/SeloNota.vue'

afterEach(() => {
  document.body.innerHTML = ''
})

describe('barra dos grupos do NPS', () => {
  it('mostra nome, porcentagem e quantidade de cada grupo (a cor nunca fala sozinha)', () => {
    const w = mount(BarraGrupos, { props: { detratores: 27, neutros: 31, promotores: 62, pct: { detratores: 22.5, neutros: 25.8, promotores: 51.7 } } })
    const texto = w.text()
    expect(texto).toContain('Detratores')
    expect(texto).toContain('22,5%')
    expect(texto).toContain('51,7%')
    expect(texto).toContain('notas 9 e 10')
    expect(w.find('[role="img"]').attributes('aria-label')).toBe('Detratores: 22,5% (27); Neutros: 25,8% (31); Promotores: 51,7% (62)')
    // Três segmentos, proporcionais às quantidades.
    const segmentos = w.findAll('[role="img"] > div')
    expect(segmentos).toHaveLength(3)
    expect(segmentos[2]!.attributes('style')).toContain('flex-grow: 0.516')
  })

  it('sem porcentagem da API, calcula; grupo vazio não vira segmento', () => {
    const w = mount(BarraGrupos, { props: { detratores: 0, neutros: 1, promotores: 3, tipo: 'csat', legenda: 'compacta' } })
    expect(w.text()).toContain('3 satisfeitos (75%)')
    expect(w.text()).toContain('0 insatisfeitos (0%)')
    expect(w.findAll('[role="img"] > div')).toHaveLength(2)
  })

  it('sem respostas', () => {
    const w = mount(BarraGrupos, { props: { detratores: 0, neutros: 0, promotores: 0 } })
    expect(w.find('[role="img"]').attributes('aria-label')).toBe('Sem respostas')
  })
})

describe('gráfico da evolução do NPS', () => {
  const pontos = [
    { mes: '2026-07', nps: 29, total: 40 },
    { mes: '2026-08', nps: 36, total: 35 },
    { mes: '2026-09', nps: -4, total: 50 },
  ]

  it('desenha a linha, escreve o valor do último mês e o zero', () => {
    const w = mount(GraficoEvolucao, { props: { pontos } })
    const d = w.find('path').attributes('d')!
    expect(d.startsWith('M')).toBe(true)
    expect(d.match(/L/g)).toHaveLength(2)
    expect(w.text()).toContain('−4') // valor do último mês, com sinal de menos
    expect(w.text()).toContain('set/26')
    expect(w.findAll('circle')).toHaveLength(3)
  })

  it('mês sem NPS interrompe a linha', () => {
    const w = mount(GraficoEvolucao, { props: { pontos: [pontos[0]!, { mes: '2026-08', nps: null, total: 3 }, pontos[2]!] } })
    expect(w.find('path').attributes('d')!.match(/M/g)).toHaveLength(2)
  })

  it('mês que a API não mandou (sem respostas) também vira buraco, no gráfico e na tabela', async () => {
    const w = mount(GraficoEvolucao, { props: { pontos: [pontos[0]!, pontos[2]!] } })
    expect(w.find('path').attributes('d')!.match(/M/g)).toHaveLength(2)
    expect(w.findAll('circle')).toHaveLength(2)
    await w.setProps({ tabela: true })
    const linhas = w.findAll('tbody tr')
    expect(linhas).toHaveLength(3)
    expect(linhas[1]!.text()).toContain('agosto de 2026')
    expect(linhas[1]!.text()).toContain('0')
  })

  it('pelo teclado: as setas mostram cada mês e o leitor de tela ouve o valor', async () => {
    const w = mount(GraficoEvolucao, { props: { pontos }, attachTo: document.body })
    const grupo = w.find('[role="group"]')
    // Foco de verdade pelo teclado (como o Tab): só ele escolhe o último mês sozinho.
    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Tab', bubbles: true }))
    ;(grupo.element as HTMLElement).focus()
    await nextTick()
    expect(w.find('[aria-live="polite"]').text()).toBe('setembro de 2026: NPS −4, 50 respostas.')
    await grupo.trigger('keydown', { key: 'ArrowLeft' })
    expect(w.find('[aria-live="polite"]').text()).toBe('agosto de 2026: NPS 36, 35 respostas.')
    await grupo.trigger('keydown', { key: 'Home' })
    expect(w.find('[aria-live="polite"]').text()).toContain('julho de 2026')
    // A dica visual aparece junto.
    expect(w.text()).toContain('NPS 29')
  })

  it('a mesma informação em tabela', async () => {
    const tabela = ref(false)
    const w = mount(GraficoEvolucao, { props: { pontos, tabela: tabela.value, 'onUpdate:tabela': (v: boolean) => (tabela.value = v) } })
    expect(w.find('table').exists()).toBe(false)
    await w.setProps({ tabela: true })
    await nextTick()
    const linhas = w.findAll('tbody tr')
    expect(linhas).toHaveLength(3)
    expect(linhas[1]!.text()).toContain('agosto de 2026')
    expect(linhas[1]!.text()).toContain('36')
  })
})

describe('escolha da nota', () => {
  it('marca a nota e diz a categoria', async () => {
    const w = mount(SeletorNota, { props: { rotulo: 'Nota', modelValue: null, 'onUpdate:modelValue': (v: number | null) => w.setProps({ modelValue: v }) } })
    expect(w.findAll('input[type="radio"]')).toHaveLength(11)
    await w.find('input[value="3"]').setValue(true)
    expect(w.emitted('update:modelValue')![0]).toEqual([3])
    expect(w.text()).toContain('Nota 3: detrator (notas 0 a 6)')
  })

  it('CSAT vai de 1 a 5', async () => {
    const w = mount(SeletorNota, { props: { rotulo: 'Nota', tipo: 'csat', modelValue: 3 } })
    expect(w.findAll('input[type="radio"]').map((i) => i.attributes('value'))).toEqual(['1', '2', '3', '4', '5'])
    expect(w.text()).toContain('Nota 3: neutro (nota 3)')
  })

  it('o selo da nota tem a cor da categoria e o texto para leitor de tela', () => {
    const w = mount(SeloNota, { props: { nota: 2, grupo: 'detrator', tipo: 'nps' } })
    expect(w.classes()).toContain('bg-erro-suave')
    expect(w.text()).toContain('Nota 2 de 10, detrator')
  })
})

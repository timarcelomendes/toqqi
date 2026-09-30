<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { Ban, CheckCircle2, MailPlus, MoreHorizontal, Pencil, Search, Trash2, UserCheck, Users } from 'lucide-vue-next'
import { equipeApi, mensagemDoErro, type SituacaoUsuario, type Usuario } from '@/api'
import { avisar } from '@/composables/avisos'
import { confirmar } from '@/composables/confirmacao'
import { useSessaoStore } from '@/stores/sessao'
import { formatarDataHora } from '@/utils/datas'
import { iniciais, PERFIS, SITUACOES_USUARIO } from '@/utils/rotulos'
import ItemMenu from '@/components/app/ItemMenu.vue'
import Alerta from '@/components/ui/Alerta.vue'
import Botao from '@/components/ui/Botao.vue'
import Campo from '@/components/ui/Campo.vue'
import EstadoVazio from '@/components/ui/EstadoVazio.vue'
import Etiqueta from '@/components/ui/Etiqueta.vue'
import MenuSuspenso from '@/components/ui/MenuSuspenso.vue'
import Tabela, { type Coluna } from '@/components/ui/Tabela.vue'
import ModalUsuario from './ModalUsuario.vue'

const sessao = useSessaoStore()
const usuarios = ref<Usuario[]>([])
const carregando = ref(true)
const erro = ref<string | null>(null)
const busca = ref('')
const soPendentes = ref(false)
const ocupado = ref<Usuario['id'] | null>(null)

const modalAberto = ref(false)
const emEdicao = ref<Usuario | null>(null)

const colunas: Coluna[] = [
  { chave: 'nome', rotulo: 'Nome e e-mail' },
  { chave: 'cargo', rotulo: 'Cargo', classe: 'hidden lg:table-cell' },
  { chave: 'perfil', rotulo: 'Perfil', classe: 'hidden sm:table-cell' },
  { chave: 'situacao', rotulo: 'Situação', classe: 'hidden md:table-cell' },
  { chave: 'ultimo_acesso', rotulo: 'Último acesso', classe: 'hidden xl:table-cell' },
  { chave: 'acoes', rotulo: 'Ações', rotuloOculto: true, alinhar: 'direita' },
]

const ordemSituacao: Record<SituacaoUsuario, number> = { pendente: 0, ativo: 1, bloqueado: 2 }
const pendentes = computed(() => usuarios.value.filter((u) => u.situacao === 'pendente').length)

function normalizar(t: string) {
  return t.normalize('NFD').replace(/\p{Diacritic}/gu, '').toLowerCase()
}

const filtrados = computed(() => {
  const termo = normalizar(busca.value.trim())
  return usuarios.value
    .filter((u) => !soPendentes.value || u.situacao === 'pendente')
    .filter((u) => !termo || normalizar(`${u.nome} ${u.email} ${u.cargo ?? ''}`).includes(termo))
    .sort((a, b) => ordemSituacao[a.situacao] - ordemSituacao[b.situacao] || a.nome.localeCompare(b.nome, 'pt-BR'))
})

function ehVoce(u: Usuario) {
  return String(u.id) === String(sessao.usuario?.id)
}

async function carregar() {
  carregando.value = true
  erro.value = null
  try {
    usuarios.value = await equipeApi.listar()
  } catch (e) {
    erro.value = mensagemDoErro(e)
  } finally {
    carregando.value = false
  }
}

function substituir(u: Usuario) {
  const i = usuarios.value.findIndex((x) => String(x.id) === String(u.id))
  if (i >= 0) usuarios.value.splice(i, 1, u)
  else usuarios.value.push(u)
}

function novo() {
  emEdicao.value = null
  modalAberto.value = true
}
function editar(u: Usuario) {
  emEdicao.value = u
  modalAberto.value = true
}

async function mudarSituacao(u: Usuario, situacao: SituacaoUsuario) {
  const textos: Record<SituacaoUsuario, { titulo: string; mensagem: string; botao: string; ok: string; perigo?: boolean }> = {
    ativo:
      u.situacao === 'pendente'
        ? { titulo: `Aprovar ${u.nome}?`, mensagem: `${u.email} vai poder entrar no Toqqi com o perfil ${PERFIS[u.perfil]?.rotulo ?? u.perfil}.`, botao: 'Aprovar', ok: 'Acesso aprovado.' }
        : { titulo: `Desbloquear ${u.nome}?`, mensagem: 'A pessoa volta a poder entrar no Toqqi.', botao: 'Desbloquear', ok: 'Acesso liberado de novo.' },
    bloqueado: {
      titulo: `Bloquear ${u.nome}?`,
      mensagem: 'A pessoa é desconectada na hora e não consegue mais entrar até você desbloquear.',
      botao: 'Bloquear',
      ok: 'Acesso bloqueado.',
      perigo: true,
    },
    pendente: { titulo: '', mensagem: '', botao: '', ok: '' },
  }
  const t = textos[situacao]
  if (!(await confirmar({ titulo: t.titulo, mensagem: t.mensagem, confirmar: t.botao, perigo: t.perigo }))) return
  ocupado.value = u.id
  try {
    substituir(await equipeApi.atualizar(u.id, { situacao }))
    avisar.sucesso(t.ok)
  } catch (e) {
    avisar.erro(mensagemDoErro(e))
  } finally {
    ocupado.value = null
  }
}

async function excluir(u: Usuario) {
  const ok = await confirmar({
    titulo: `Excluir ${u.nome}?`,
    mensagem: 'A pessoa perde o acesso e sai da lista da equipe. O histórico do que ela fez continua na auditoria. Não dá para desfazer.',
    confirmar: 'Excluir',
    perigo: true,
  })
  if (!ok) return
  ocupado.value = u.id
  try {
    await equipeApi.excluir(u.id)
    usuarios.value = usuarios.value.filter((x) => String(x.id) !== String(u.id))
    avisar.sucesso(`${u.nome} foi excluído(a) da equipe.`)
  } catch (e) {
    avisar.erro(mensagemDoErro(e))
  } finally {
    ocupado.value = null
  }
}

async function reenviar(u: Usuario) {
  ocupado.value = u.id
  try {
    const r = await equipeApi.reenviarConfirmacao(u.id)
    avisar.sucesso(r?.mensagem || `Enviamos um novo e-mail de confirmação para ${u.email}.`)
  } catch (e) {
    avisar.erro(mensagemDoErro(e))
  } finally {
    ocupado.value = null
  }
}

onMounted(carregar)
defineExpose({ novo })
</script>

<template>
  <div class="flex flex-col gap-4">
    <Alerta v-if="pendentes > 0 && !soPendentes" tom="atencao" :titulo="pendentes === 1 ? '1 pessoa pediu acesso' : `${pendentes} pessoas pediram acesso`">
      Confira quem é e aprove ou bloqueie.
      <button type="button" class="link ml-1" @click="soPendentes = true">Ver pedidos</button>
    </Alerta>

    <div class="cartao">
      <div class="flex flex-col gap-3 border-b border-borda p-4 sm:flex-row sm:items-center sm:px-5">
        <Campo v-model="busca" rotulo="Buscar na equipe" rotulo-oculto tipo="search" placeholder="Buscar por nome, e-mail ou cargo" class="sm:max-w-sm sm:flex-1">
          <template #antes><Search class="size-4" aria-hidden="true" /></template>
        </Campo>
        <div class="flex items-center gap-3 sm:ml-auto">
          <Botao v-if="soPendentes" variante="fantasma" tamanho="sm" @click="soPendentes = false">Mostrar todos</Botao>
          <p class="text-sm text-texto-fraco" aria-live="polite">
            {{ filtrados.length }} {{ filtrados.length === 1 ? 'pessoa' : 'pessoas' }}
          </p>
        </div>
      </div>

      <Alerta v-if="erro" tom="erro" class="m-4">
        {{ erro }} <button type="button" class="link ml-1" @click="carregar">Tentar de novo</button>
      </Alerta>

      <Tabela v-else :colunas="colunas" :linhas="filtrados" :chave="(u) => u.id" :carregando="carregando" legenda="Pessoas da equipe">
        <template #cel-nome="{ linha: u }">
          <div class="flex items-center gap-3">
            <span class="flex size-9 shrink-0 items-center justify-center rounded-full bg-superficie-2 text-xs font-bold text-texto-suave" aria-hidden="true">
              {{ iniciais(u.nome) }}
            </span>
            <div class="min-w-0">
              <p class="truncate font-semibold text-texto">
                {{ u.nome }} <span v-if="ehVoce(u)" class="font-normal text-texto-fraco">(você)</span>
              </p>
              <p class="truncate text-texto-fraco">{{ u.email }}</p>
              <p v-if="!u.email_confirmado && u.situacao !== 'pendente'" class="text-xs text-atencao">E-mail ainda não confirmado</p>
              <!-- No celular, perfil e situação aparecem aqui -->
              <div class="mt-1 flex flex-wrap gap-1.5 md:hidden">
                <Etiqueta class="sm:hidden" :tom="PERFIS[u.perfil]?.tom">{{ PERFIS[u.perfil]?.rotulo ?? u.perfil }}</Etiqueta>
                <Etiqueta :tom="SITUACOES_USUARIO[u.situacao]?.tom" ponto>{{ SITUACOES_USUARIO[u.situacao]?.rotulo ?? u.situacao }}</Etiqueta>
              </div>
            </div>
          </div>
        </template>
        <template #cel-cargo="{ linha: u }">
          <span class="text-texto-suave">{{ u.cargo || '—' }}</span>
        </template>
        <template #cel-perfil="{ linha: u }">
          <Etiqueta :tom="PERFIS[u.perfil]?.tom">{{ PERFIS[u.perfil]?.rotulo ?? u.perfil }}</Etiqueta>
        </template>
        <template #cel-situacao="{ linha: u }">
          <Etiqueta :tom="SITUACOES_USUARIO[u.situacao]?.tom" ponto>{{ SITUACOES_USUARIO[u.situacao]?.rotulo ?? u.situacao }}</Etiqueta>
        </template>
        <template #cel-ultimo_acesso="{ linha: u }">
          <span class="whitespace-nowrap text-texto-suave">{{ formatarDataHora(u.ultimo_acesso, 'Nunca entrou') }}</span>
        </template>
        <template #cel-acoes="{ linha: u }">
          <div class="flex items-center justify-end gap-1">
            <Botao
              v-if="u.situacao === 'pendente'"
              tamanho="sm"
              variante="secundario"
              :carregando="ocupado === u.id"
              @click="mudarSituacao(u, 'ativo')"
            >
              <UserCheck class="size-4" aria-hidden="true" /> Aprovar<span class="sr-only"> {{ u.nome }}</span>
            </Botao>
            <MenuSuspenso :rotulo="`Ações para ${u.nome}`" fixo>
              <template #gatilho="{ props }">
                <button
                  v-bind="props"
                  type="button"
                  class="flex size-9 items-center justify-center rounded-lg text-texto-fraco hover:bg-superficie-2 hover:text-texto disabled:opacity-50"
                  :disabled="ocupado === u.id"
                >
                  <MoreHorizontal class="size-5" aria-hidden="true" />
                </button>
              </template>
              <ItemMenu :icone="Pencil" @click="editar(u)">Editar</ItemMenu>
              <ItemMenu v-if="!u.email_confirmado && u.situacao !== 'pendente'" :icone="MailPlus" @click="reenviar(u)">Reenviar confirmação</ItemMenu>
              <template v-if="!ehVoce(u)">
                <ItemMenu v-if="u.situacao === 'bloqueado'" :icone="CheckCircle2" @click="mudarSituacao(u, 'ativo')">Desbloquear</ItemMenu>
                <ItemMenu v-else :icone="Ban" @click="mudarSituacao(u, 'bloqueado')">Bloquear</ItemMenu>
                <ItemMenu :icone="Trash2" perigo @click="excluir(u)">Excluir</ItemMenu>
              </template>
            </MenuSuspenso>
          </div>
        </template>
        <template #vazio>
          <EstadoVazio
            v-if="busca || soPendentes"
            :icone="Search"
            titulo="Ninguém encontrado"
            :descricao="soPendentes ? 'Não há pedidos de acesso esperando você.' : 'Tente buscar por outro nome ou e-mail.'"
          />
          <EstadoVazio v-else :icone="Users" titulo="Sua equipe começa aqui" descricao="Chame quem vai acompanhar os clientes com você.">
            <Botao @click="novo">Novo usuário</Botao>
          </EstadoVazio>
        </template>
      </Tabela>
    </div>

    <ModalUsuario v-model:aberto="modalAberto" :usuario="emEdicao" :eh-voce="!!emEdicao && ehVoce(emEdicao)" @salvo="substituir" />
  </div>
</template>

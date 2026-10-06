<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { Ban, CheckCircle2, MailPlus, MoreHorizontal, Pencil, Search, ShieldMinus, ShieldPlus, Trash2, UserCheck, Users, X } from 'lucide-vue-next'
import { equipeApi, mensagemDoErro, type Perfil, type SituacaoUsuario, type Usuario } from '@/api'
import { avisar } from '@/composables/avisos'
import { usarPedidosAcesso } from '@/composables/pedidosAcesso'
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
import ModalAdministrador from './ModalAdministrador.vue'
import ModalUsuario from './ModalUsuario.vue'

const sessao = useSessaoStore()
const usuarios = ref<Usuario[]>([])
const carregando = ref(true)
const erro = ref<string | null>(null)
const busca = ref('')
// `?pedidos=1` (o botão "Ver pedidos" do e-mail do pedido de acesso) já abre só com os pedidos.
const soPendentes = ref(useRoute().query.pedidos === '1')
const ocupado = ref<Usuario['id'] | null>(null)

const modalAberto = ref(false)
const emEdicao = ref<Usuario | null>(null)
const perfilNovo = ref<Perfil>('gestor')
const modalAdminAberto = ref(false)

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
// O número ao lado de Equipe no menu acompanha a lista (aprovar, bloquear e excluir mudam na hora).
const pedidosAcesso = usarPedidosAcesso()
watch(pendentes, (n) => pedidosAcesso.definir(n))

// Administradores ativos (o quadro do topo) e quem pode virar administrador (ativo e com outro perfil).
const porNome = (a: Usuario, b: Usuario) => a.nome.localeCompare(b.nome, 'pt-BR')
const administradores = computed(() => usuarios.value.filter((u) => u.perfil === 'admin' && u.situacao === 'ativo').sort(porNome))
const candidatosAdmin = computed(() => usuarios.value.filter((u) => u.perfil !== 'admin' && u.situacao === 'ativo').sort(porNome))

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

function novo(perfil: Perfil = 'gestor') {
  emEdicao.value = null
  perfilNovo.value = perfil
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

async function tornarAdmin(u: Usuario) {
  const ok = await confirmar({
    titulo: `Dar acesso de administrador a ${u.nome}?`,
    mensagem: 'A pessoa passa a poder tudo no Toqqi, inclusive cuidar da equipe, das configurações e da assinatura.',
    confirmar: 'Tornar administrador',
  })
  if (!ok) return
  ocupado.value = u.id
  try {
    substituir(await equipeApi.atualizar(u.id, { perfil: 'admin' }))
    avisar.sucesso(`${u.nome} agora administra a conta.`)
  } catch (e) {
    avisar.erro(mensagemDoErro(e))
  } finally {
    ocupado.value = null
  }
}

/** Quem sai dos administradores fica com o perfil Gestor (dá para trocar depois em Editar). */
async function removerAdmin(u: Usuario) {
  const ok = await confirmar({
    titulo: `Remover ${u.nome} dos administradores?`,
    mensagem:
      'A pessoa passa a ter o perfil Gestor e deixa de cuidar da equipe, das configurações e da assinatura. Dá para trocar o perfil depois em Editar.',
    confirmar: 'Remover dos administradores',
    perigo: true,
  })
  if (!ok) return
  ocupado.value = u.id
  try {
    substituir(await equipeApi.atualizar(u.id, { perfil: 'gestor' }))
    avisar.sucesso(`${u.nome} não administra mais a conta e ficou com o perfil Gestor.`)
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

    <section v-if="!carregando && !erro && !soPendentes" class="cartao flex flex-col gap-3 p-4 sm:flex-row sm:items-start sm:px-5" aria-labelledby="titulo-administradores" data-administradores>
      <div class="min-w-0 flex-1">
        <h2 id="titulo-administradores" class="font-semibold text-texto">Administradores da conta</h2>
        <p class="text-sm text-texto-fraco">
          Podem tudo no Toqqi, inclusive cuidar da equipe, das configurações e da assinatura. Todos da equipe veem quem são em Minha conta.
        </p>
        <ul class="mt-3 flex flex-wrap gap-2">
          <li
            v-for="u in administradores"
            :key="u.id"
            class="inline-flex max-w-full items-center gap-2 rounded-full border border-borda py-1 pl-1 text-sm"
            :class="ehVoce(u) ? 'pr-3' : 'pr-1'"
            data-administrador
          >
            <span class="flex size-7 shrink-0 items-center justify-center rounded-full bg-marca-suave text-xs font-bold text-marca-texto" aria-hidden="true">
              {{ iniciais(u.nome) }}
            </span>
            <span class="truncate font-semibold text-texto">{{ u.nome }}</span>
            <span v-if="ehVoce(u)" class="text-texto-fraco">(você)</span>
            <button
              v-else
              type="button"
              class="flex size-7 shrink-0 items-center justify-center rounded-full text-texto-fraco hover:bg-superficie-2 hover:text-erro disabled:opacity-50"
              :disabled="ocupado === u.id"
              :aria-label="`Remover ${u.nome} dos administradores`"
              :title="`Remover ${u.nome} dos administradores`"
              data-remover-admin
              @click="removerAdmin(u)"
            >
              <X class="size-4" aria-hidden="true" />
            </button>
          </li>
        </ul>
      </div>
      <Botao variante="secundario" tamanho="sm" class="self-start" data-adicionar-admin @click="modalAdminAberto = true">
        <ShieldPlus class="size-4" aria-hidden="true" /> Adicionar administrador
      </Botao>
    </section>

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
                <ItemMenu v-if="u.perfil === 'admin'" :icone="ShieldMinus" @click="removerAdmin(u)">Remover dos administradores</ItemMenu>
                <ItemMenu v-else-if="u.situacao === 'ativo'" :icone="ShieldPlus" @click="tornarAdmin(u)">Tornar administrador</ItemMenu>
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
            <Botao @click="novo()">Novo usuário</Botao>
          </EstadoVazio>
        </template>
      </Tabela>
    </div>

    <ModalUsuario
      v-model:aberto="modalAberto"
      :usuario="emEdicao"
      :eh-voce="!!emEdicao && ehVoce(emEdicao)"
      :perfil-inicial="perfilNovo"
      @salvo="substituir"
    />
    <ModalAdministrador v-model:aberto="modalAdminAberto" :candidatos="candidatosAdmin" @salvo="substituir" @novo="novo('admin')" />
  </div>
</template>

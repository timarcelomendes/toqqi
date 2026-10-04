// Atalhos para as telas (docs/api-etapa-5b.md §5.4), usados pela Ajuda (campo `atalho` de cada seção) e pelo
// assistente (atalhos de cada resposta). A API já tira os do assistente que a pessoa não pode abrir; a tela confere de
// novo com as permissões da sessão e só mostra os que ela conhece (o caminho sai sempre desta tabela).
import type { AtalhoAssistente, ChaveAtalho, Permissao } from '@/api/tipos'

export interface DefinicaoAtalho {
  rotulo: string
  caminho: string
  permissao?: Permissao
  /** Só para o perfil administrador da conta. */
  admin?: boolean
}

export interface Atalho extends DefinicaoAtalho {
  chave: ChaveAtalho
}

export const ATALHOS: Record<ChaveAtalho, DefinicaoAtalho> = {
  inicio: { rotulo: 'Início', caminho: '/inicio' },
  contatos: { rotulo: 'Contatos', caminho: '/contatos', permissao: 'contatos.ver' },
  importar_contatos: { rotulo: 'Importar contatos', caminho: '/contatos/importar', permissao: 'importacao.usar' },
  envios: { rotulo: 'Envios', caminho: '/envios', permissao: 'envios.ver' },
  formularios: { rotulo: 'Formulários', caminho: '/formularios', permissao: 'formularios.ver' },
  respostas: { rotulo: 'Respostas', caminho: '/respostas', permissao: 'respostas.ver' },
  planos_de_acao: { rotulo: 'Planos de ação', caminho: '/planos-de-acao', permissao: 'acoes.ver' },
  relatorios: { rotulo: 'Relatórios', caminho: '/relatorios/empresas', permissao: 'relatorios.ver' },
  crescimento: { rotulo: 'Crescimento', caminho: '/crescimento/indicacoes', permissao: 'crescimento.ver' },
  equipe: { rotulo: 'Equipe', caminho: '/equipe', permissao: 'equipe.gerenciar' },
  config_empresa: { rotulo: 'Dados da empresa', caminho: '/configuracoes/empresa', permissao: 'configuracoes.gerenciar' },
  config_envios: { rotulo: 'Configurações de envio', caminho: '/configuracoes/envios', permissao: 'configuracoes.gerenciar' },
  config_acoes: { rotulo: 'Configurações de ações', caminho: '/configuracoes/acoes', permissao: 'configuracoes.gerenciar' },
  config_ia: { rotulo: 'Configurações de IA', caminho: '/configuracoes/ia', permissao: 'configuracoes.gerenciar' },
  seguranca: { rotulo: 'Segurança', caminho: '/configuracoes/seguranca', permissao: 'configuracoes.gerenciar' },
  integracoes: { rotulo: 'Integrações', caminho: '/integracoes', admin: true },
  assinatura: { rotulo: 'Assinatura', caminho: '/assinatura', permissao: 'assinatura.gerenciar' },
  minha_conta: { rotulo: 'Minha conta', caminho: '/minha-conta' },
  ajuda: { rotulo: 'Ajuda', caminho: '/ajuda' },
}

/** Quem está vendo: as permissões e se é administrador da conta (como em `useSessaoStore`). */
export interface Acesso {
  pode: (p: Permissao) => boolean
  admin: boolean
}

/** Se a chave é de uma tela da tabela (uma chave desconhecida não é atalho nenhum, nem negado). */
export function atalhoConhecido(chave: string | null | undefined): chave is ChaveAtalho {
  return !!chave && Object.prototype.hasOwnProperty.call(ATALHOS, chave)
}

/** O atalho, se a chave é conhecida e a pessoa pode abrir a tela; senão null. */
export function atalhoPermitido(chave: string | null | undefined, acesso: Acesso): Atalho | null {
  if (!atalhoConhecido(chave)) return null
  const d = ATALHOS[chave]
  if (d.admin && !acesso.admin) return null
  if (d.permissao && !acesso.pode(d.permissao)) return null
  return { chave, ...d }
}

/** Atalhos de uma resposta do assistente: só os conhecidos e permitidos, sem repetir, no máximo 2. */
export function atalhosDaResposta(atalhos: AtalhoAssistente[] | null | undefined, acesso: Acesso): Atalho[] {
  const vistos = new Set<string>()
  const lista: Atalho[] = []
  for (const a of atalhos ?? []) {
    const ok = atalhoPermitido(a?.chave, acesso)
    if (!ok || vistos.has(ok.chave)) continue
    vistos.add(ok.chave)
    lista.push(ok)
    if (lista.length === 2) break
  }
  return lista
}

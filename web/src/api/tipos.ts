// Tipos do contrato da API (docs/api-etapa-1.md, -2, -3, -3b, -4a, -4b, -5a, -5b, -5c, -5d, -5e e -5f).
import type { Contexto, Final, GrupoNota, Pergunta, Tema } from '@/pesquisa/tipos'

export type Perfil = 'admin' | 'gestor' | 'consulta'
export type SituacaoUsuario = 'ativo' | 'pendente' | 'bloqueado'

/** Permissões conhecidas. O tipo aceita outras strings para não quebrar se a API crescer. */
export type Permissao =
  | 'painel.ver'
  | 'painel.exportar'
  | 'contatos.ver'
  | 'contatos.editar'
  | 'contatos.excluir'
  | 'importacao.usar'
  | 'envios.ver'
  | 'envios.disparar'
  | 'formularios.ver'
  | 'formularios.editar'
  | 'respostas.ver'
  | 'respostas.editar'
  | 'acoes.ver'
  | 'acoes.tratar'
  | 'acoes.excluir'
  | 'relatorios.ver'
  | 'equipe.gerenciar'
  | 'configuracoes.gerenciar'
  | 'assinatura.gerenciar'
  | 'auditoria.ver'
  | 'zona_risco.usar'
  | 'crescimento.ver'
  | 'crescimento.tratar'
  | (string & {})

export interface Usuario {
  id: number | string
  nome: string
  email: string
  cargo: string | null
  perfil: Perfil
  situacao: SituacaoUsuario
  email_confirmado: boolean
  ultimo_acesso: string | null
  superadmin: boolean
  /** Etapa 4b (só no próprio usuário, em /eu e no login): e-mails do Toqqi que ele recebe. */
  recebe_resumo_semanal?: boolean
  recebe_alertas?: boolean
  /** Aceite dos Termos de uso e da Política de privacidade (GET /eu e login). Ver docs/api-aceite-lgpd.md §2. */
  aceite?: Aceite
}

/** Situação do aceite dos documentos legais do usuário logado. */
export interface Aceite {
  versao_atual: number
  /** Maior versão aceita (null = nunca aceitou). */
  versao_aceita: number | null
  aceito_em: string | null
  /** versao_aceita é null ou menor que versao_atual. */
  pendente: boolean
  /**
   * Data da retirada do aceite mais recente, quando ela é posterior ao último aceite em vigor (senão null). Opcional:
   * a API anterior à §5 de docs/api-aceite-lgpd.md não manda o campo.
   */
  revogado_em?: string | null
}

export interface Conta {
  id: number | string
  nome: string
  plano: string | null
  situacao: SituacaoConta
  teste_ate: string | null
  /** Logo da empresa (vem de GET /eu); aparece nas pesquisas e nos e-mails quando o formulário não tem logo. */
  logo_url?: string | null
  /** Etapa 4b: IA disponível na plataforma + análise ligada na conta + assinatura em dia (GET /eu e login). */
  ia_ativa?: boolean
  /** Etapa 5a (GET /eu e login): se os envios estão liberados e o aviso do topo das telas. */
  cobranca?: CobrancaConta
}

// ───────────────────── Dados da empresa e logo (docs/api-dados-empresa.md) ─────────────────────

/**
 * GET/PUT /conta/dados (no contrato, `DadosEmpresa`; aqui com outro nome porque `DadosEmpresa` já é o corpo das
 * empresas dos contatos). Vazios vêm como null; documento, telefone e CEP só com dígitos (telefone com o 55). */
export interface DadosEmpresaConta {
  nome: string
  razao_social: string | null
  /** CPF (11) ou CNPJ (14), só dígitos. */
  documento: string | null
  telefone: string | null
  email_contato: string | null
  /** Sempre com http(s):// (o servidor completa). */
  site: string | null
  cep: string | null
  logradouro: string | null
  numero: string | null
  complemento: string | null
  bairro: string | null
  cidade: string | null
  uf: string | null
  logo_url: string | null
  atualizado_em: string | null
}

/** Corpo de PUT /conta/dados: todos os campos de texto (os opcionais vazios vão como null). */
export type DadosEmpresaContaIn = Omit<DadosEmpresaConta, 'logo_url' | 'atualizado_em'>

/** Etapa 5h: GET /conta/marca (para quem vê o Início). `cor` = a cor dos e-mails (#RRGGBB) ou null. */
export interface MarcaConta {
  cor: string | null
  tem_logo: boolean
}

/** Etapa 5h: PUT /conta/marca. `formularios_atualizados` = os que estavam na cor dos modelos e passaram para a nova. */
export interface ResultadoMarca {
  cor: string
  formularios_atualizados: number
}

export interface DadosSessao {
  usuario: Usuario
  conta: Conta
  permissoes: Permissao[]
}

export interface Sessao extends DadosSessao {
  token: string
  expira_em: string
}

export interface Mensagem {
  mensagem: string
}

/** Entrar com o Google (docs/api-login-google.md): quem ainda não tem conta termina o cadastro com este token
 * (15 minutos), sem precisar do Google de novo. */
export interface CadastroGooglePendente {
  novo: true
  cadastro: string
  email: string
  nome: string
}

export interface RegrasSenha {
  minimo: number
  maximo: number
  exige: string[]
}

export interface SessaoAparelho {
  id: number | string
  aparelho: string
  ip: string | null
  criada_em: string
  ultimo_uso: string | null
  atual: boolean
}

export interface ItemCatalogoPermissao {
  chave: Permissao
  rotulo: string
  grupo: string
  somente_admin: boolean
}

export interface PermissoesEquipe {
  catalogo: ItemCatalogoPermissao[]
  gestor: Permissao[]
  consulta: Permissao[]
}

export interface Seguranca {
  sessao_minutos: number
  dominios: string[]
}

/** Minha conta › Administradores da conta (GET /conta/administradores, para qualquer perfil): os administradores ativos. */
export interface AdministradorConta {
  id: number | string
  nome: string
  email: string
  cargo: string | null
  /** É quem está vendo. */
  voce: boolean
}

export type Gravidade = 'info' | 'sucesso' | 'atencao' | 'erro'

export interface ItemAuditoria {
  id: number | string
  criado_em: string
  evento: string
  rotulo: string
  gravidade: Gravidade
  usuario: { id: number | string; nome: string } | null
  /** O contrato não fixa o formato: pode vir texto ou objeto. */
  detalhe: string | Record<string, unknown> | null
  ip: string | null
  /** Etapa 5f: a chave do grupo do evento (GET /auditoria/grupos); pode faltar no servidor antigo. */
  grupo?: string | null
}

export interface PaginaAuditoria {
  itens: ItemAuditoria[]
  total: number
  pagina: number
  por_pagina: number
}

export interface ContaPlataforma {
  id: number | string
  nome: string
  plano: string | null
  situacao: SituacaoConta
  teste_ate: string | null
  usuarios: number
  criada_em: string
  /** Etapa 5a: último dia coberto por pagamento (AAAA-MM-DD). */
  pago_ate?: string | null
  /** Etapa 5a: vencimento da fatura em atraso mais antiga (AAAA-MM-DD). */
  atrasada_desde?: string | null
  /** Etapa 5a: a assinatura ativa, se houver. */
  assinatura?: { plano: string; valor: ValorDecimal; situacao: string } | null
  /** Administradores da conta, o mais antigo primeiro. */
  admins?: AdminPlataforma[]
  /** Etapa 5f: dia (AAAA-MM-DD) da exclusão automática já avisada aos administradores; null fora disso. */
  exclusao_em?: string | null
  /** A nota de risco (docs/api-plataforma-risco.md); null nas contas da equipe. Só na listagem. */
  risco?: RiscoConta | null
}

/** Risco da conta: a soma dos pontos dos sinais (0 a 100). `alto` 60 ou mais, `medio` 30 a 59. */
export interface RiscoConta {
  pontos: number
  nivel: 'baixo' | 'medio' | 'alto'
  sinais: SinalRisco[]
}

/** Outra conta citada num sinal de repetido (até 3; `total` diz quantas são). */
export interface ContaCitada {
  id: number | string
  nome: string
}

type Repetido = { pontos: number; contas: ContaCitada[]; total: number }

export type SinalRisco =
  | { tipo: 'email_temporario' | 'email_pessoal'; pontos: number; dominio: string }
  | { tipo: 'email_nao_confirmado'; pontos: number; dias: number }
  | { tipo: 'nome_de_teste'; pontos: number }
  | ({ tipo: 'documento_repetido'; documento: 'cpf' | 'cnpj' } & Repetido)
  | ({ tipo: 'telefone_repetido' | 'nome_repetido' } & Repetido)
  | ({ tipo: 'dominio_repetido'; dominio: string } & Repetido)
  | { tipo: 'descadastros'; pontos: number; saidas: number; destinatarios: number; taxa: number }
  | { tipo: 'invalidos'; pontos: number; invalidos: number; tentativas: number; taxa: number }
  | { tipo: 'sem_respostas'; pontos: number; convites: number; respostas: number }
  | { tipo: 'volume_inicio'; pontos: number; dias: number; envios: number }
  | {
      tipo: 'formulario_sensivel'
      pontos: number
      formulario: { id: number | string; nome: string }
      termo: 'senha' | 'cartao' | 'banco' | 'codigo'
      trecho: string
    }
  | { tipo: 'estorno'; pontos: number; quantas: number; ultima_em: string }

export interface AdminPlataforma {
  nome: string
  email: string
  email_confirmado: boolean
}

// ── Etapa 5h (docs/api-etapa-5h.md §4 e §5): Plataforma › Visão geral e Erros ──

/** Os 4 passos da ativação (os mesmos de `primeiros_passos` do painel). */
export interface AtivacaoConta {
  contatos: boolean
  envios_ligados: boolean
  primeiro_envio: boolean
  primeira_resposta: boolean
}

/** Situação na visão geral: a da conta, com `pausada` para a atrasada que passou dos 7 dias de carência. */
export type SituacaoVisao = 'teste' | 'teste_expirado' | 'ativa' | 'atrasada' | 'pausada' | 'cancelada' | 'cortesia'

export interface TotaisVisao {
  contas: number
  /** Cada conta numa situação só. */
  por_situacao: Partial<Record<SituacaoVisao | (string & {}), number>>
  /** Contas com assinatura ativa no ambiente atual do Asaas. */
  pagantes: number
  /** Soma do valor dessas assinaturas. */
  receita_mensal: ValorDecimal
  ambiente: 'sandbox' | 'producao' | null
  novas_7d: number
  novas_30d: number
}

/** Das contas com teste criadas entre 60 e 15 dias atrás (`de` e `ate`, AAAA-MM-DD), quantas criaram assinatura. */
export interface ConversaoVisao {
  de: string
  ate: string
  contas: number
  assinaram: number
  /** De 0 a 1; null sem contas no período. */
  taxa: number | null
}

export interface TesteAcabando {
  id: Id
  nome: string
  /** E-mail do administrador mais antigo. */
  email: string | null
  teste_ate: string
  /** Dias até o último dia do teste (0 = hoje). */
  dias: number
  ultimo_acesso: string | null
  ativacao: AtivacaoConta
}

export interface ContaVisao {
  id: Id
  nome: string
  situacao: SituacaoVisao | (string & {})
  plano: string | null
  criada_em: string
  teste_ate: string | null
  /** A última entrada de algum usuário. */
  ultimo_acesso: string | null
  usuarios: number
  admin_email: string | null
  contatos_ativos: number
  convites_30d: number
  respostas_30d: number
  respostas_total: number
  ativacao: AtivacaoConta
  /** Teto de segurança de IA usado no mês. */
  ia_analises_mes: number
  assinatura: { plano: string; valor: ValorDecimal } | null
  /** Etapa 5i: "pesquisa · rodape · email" (utm do cadastro) ou null. */
  origem?: string | null
}

/** Etapa 5i: cadastros por origem nos últimos `dias` dias e quantos pagam hoje. */
export interface OrigensVisao {
  dias: number
  itens: { rotulo: string; cadastros: number; pagantes: number }[]
  sem_origem: { cadastros: number; pagantes: number }
}

/** GET /plataforma/visao. */
export interface VisaoPlataforma {
  gerado_em: string
  origens?: OrigensVisao
  totais: TotaisVisao
  conversao: ConversaoVisao
  testes_acabando: TesteAcabando[]
  /** Melhoria 9: o teste até a primeira resposta (contas com teste criadas entre 90 e 14 dias atrás). */
  teste?: TempoTeste
  contas: ContaVisao[]
}

export interface TempoTeste {
  de: string
  ate: string
  contas: number
  chegaram: number
  ate_7_dias: number
  ate_14_dias: number
  mediana_dias: number | null
  /** De 0 a 1 (null sem base). */
  conversao_com_resposta: number | null
  conversao_sem_resposta: number | null
}

export type OrigemErro = 'api' | 'site' | 'tarefa'
export type SituacaoErros = 'abertos' | 'resolvidos' | 'todos'

/** Item de GET /plataforma/erros (a última ocorrência mais recente primeiro). */
export interface ErroPlataforma {
  id: Id
  origem: OrigemErro | (string & {})
  tipo: string
  mensagem: string
  /** A rota (com o modelo do caminho), a tela ou o nome da tarefa. */
  local: string
  /** Uma linha por quadro, a chamada mais recente primeiro. */
  pilha: string
  versao: string
  ocorrencias: number
  primeira_em: string
  ultima_em: string
  ultimo_request_id: string | null
  conta_id: Id | null
  /** Null sem conta ou com a conta já excluída. */
  conta_nome: string | null
  resolvido_em: string | null
}

// ───────────────────────── Etapa 2 (docs/api-etapa-2.md) ─────────────────────────

export type {
  BotaoFinal,
  Condicao,
  CondicaoPergunta,
  Contexto,
  ExibicaoEscolha,
  Final,
  FormatoTexto,
  Grupo,
  GrupoNota,
  Juncao,
  Logica,
  ModoConteudo,
  ModoTema,
  Operador,
  Pergunta,
  Regra,
  Tema,
  TipoPergunta,
  ValorCondicao,
} from '@/pesquisa/tipos'

export type Id = number | string

export interface Pagina<T> {
  itens: T[]
  total: number
  pagina: number
  por_pagina: number
}

export interface Referencia {
  id: Id
  nome: string
}

export type TipoCadastro = 'grupos' | 'segmentos' | 'perfis' | 'cargos'

export interface ItemCadastro {
  id: Id
  nome: string
  em_uso: number
}

export interface Responsavel {
  id: Id
  nome: string
  funcao: string | null
  email: string | null
  foto_url: string | null
  teams_webhook: string | null
  empresas: number
}

export interface DadosResponsavel {
  nome: string
  funcao?: string | null
  email?: string | null
  foto_url?: string | null
  teams_webhook?: string | null
}

export interface Empresa {
  id: Id
  nome: string
  documento: string | null
  grupo: Referencia | null
  segmento: Referencia | null
  responsavel: Referencia | null
  valor_mensal: number | string | null
  cliente_desde: string | null
  codigo_externo: string | null
  ativa: boolean
  contatos: number
  criada_em: string
  /** Etapa 5i: desfecho. */
  renovacao_em?: string | null
  situacao?: SituacaoEmpresa
  perdida_em?: string | null
  motivo_perda?: MotivoPerda | null
  motivo_perda_rotulo?: string | null
  motivo_detalhe?: string | null
  /** Etapa 5i: saúde da conta (null: pausada, perdida ou sem permissão para os números). */
  saude?: import('./etapa5iSaude').SaudeResumo | null
}

/** Etapa 5i: um marco da linha do tempo da empresa (GET /empresas/{id}/historico). */
export interface MarcoEmpresa {
  id: Id
  tipo: 'entrada' | 'valor' | 'perdida' | 'reativada'
  data: string
  valor_antes: ValorDecimal | null
  valor_depois: ValorDecimal | null
  motivo: MotivoPerda | null
  motivo_rotulo: string | null
  motivo_detalhe: string | null
  contatos: number | null
  origem: string
  origem_rotulo: string
  usuario: Referencia | null
  criado_em: string
}

export type SituacaoEmpresa = 'ativa' | 'pausada' | 'perdida'
export type MotivoPerda = 'preco' | 'concorrente' | 'atendimento' | 'produto' | 'encerrou' | 'outro'

export interface DadosEmpresa {
  nome: string
  documento?: string | null
  grupo_id?: Id | null
  segmento_id?: Id | null
  responsavel_id?: Id | null
  valor_mensal?: number | null
  cliente_desde?: string | null
  codigo_externo?: string | null
  ativa?: boolean
  renovacao_em?: string | null
}

/** Etapa 3: `nunca_enviado` deixou de existir (vira `na_fila`). */
export type SituacaoContato =
  | 'na_fila'
  | 'aguardando'
  | 'respondeu'
  | 'nao_saiu'
  | 'saiu_da_lista'
  | 'inativo'
  | 'enviando'
  | 'aguardando_intervalo'

export interface Contato {
  id: Id
  codigo: string
  nome: string
  email: string | null
  telefone: string | null
  empresa: Referencia | null
  cargo: Referencia | null
  perfil: Referencia | null
  codigo_externo: string | null
  recebe_pesquisas: boolean
  ativo: boolean
  situacao: SituacaoContato
  ultimo_envio: string | null
  proximo_envio: string | null
  ultima_nota: number | null
  criado_em: string
}

export interface ItemHistorico {
  tipo: 'resposta' | (string & {})
  data: string
  nota: number | null
  grupo: string | null
  comentario: string | null
  /** O contrato não fixa: pode vir o nome ou {id, nome}. */
  formulario: string | Referencia | null
  /** Etapa 4a (vêm do servidor novo; podem faltar no antigo). */
  id?: Id
  tipo_nota?: 'nps' | 'csat' | null
  canal?: CanalResposta
  origem?: OrigemResposta
  arquivada?: boolean
}

export interface ContatoDetalhe extends Contato {
  historico: ItemHistorico[]
}

export interface DadosContato {
  nome: string
  email?: string | null
  telefone?: string | null
  empresa_id?: Id | null
  cargo_id?: Id | null
  perfil_id?: Id | null
  codigo_externo?: string | null
  recebe_pesquisas?: boolean
  ativo?: boolean
}

export interface LinkPesquisa {
  link: string
  token: string
  expira_em: string | null
}

// Importação
export type ChaveImportacao = 'email' | 'codigo_externo' | 'telefone'
/** Etapa 4a: a mesma tela importa contatos ou respostas antigas. */
export type TipoImportacao = 'contatos' | 'respostas'

export interface CampoImportacao {
  chave: string
  rotulo: string
  obrigatorio: boolean
}

export interface AnaliseImportacao {
  id: Id
  /** Etapa 4a: o tipo escolhido na análise (vale para conferir e importar). */
  tipo?: TipoImportacao
  colunas: string[]
  mapeamento_sugerido: Record<string, string | null>
  total_linhas: number
  amostra: { linha: number; valores: Record<string, unknown> | unknown[] }[]
  campos: CampoImportacao[]
}

export interface CorpoImportacao {
  mapeamento: Record<string, string>
  chave: ChaveImportacao
  atualizar_existentes: boolean
  grupo_id?: Id
}

/** Respostas antigas: só o mapeamento e se atualiza as já importadas (chave e grupo não se aplicam). */
export interface CorpoImportacaoRespostas {
  mapeamento: Record<string, string>
  atualizar_existentes: boolean
}

export interface ProblemaImportacao {
  linha: number
  motivo: string
}

export interface ConferenciaImportacao {
  prontas: number
  com_problema: number
  novos: number
  atualizados: number
  problemas: ProblemaImportacao[]
  avisos: string[]
}

export interface ResultadoImportacao {
  /** Etapa 5i: empresas marcadas como perdidas pela coluna "Perdida em" (só vem quando > 0). */
  empresas_perdidas?: number
  novos: number
  atualizados: number
  ignorados: number
  /** O contrato não fixa: pode vir a lista ou só a quantidade. */
  problemas: ProblemaImportacao[] | number
  /**
   * Etapa 5h (só na de respostas): quantos comentários importados dos últimos 90 dias foram para a fila da IA (a análise
   * começa logo depois). Pode faltar no servidor antigo.
   */
  ia_marcadas?: number
}

// Formulários
export type TipoFormulario = 'nps' | 'csat' | 'personalizado'

export interface FormularioResumo {
  id: Id
  nome: string
  descricao: string | null
  tipo_principal: TipoFormulario
  tema?: Tema
  ativo: boolean
  publico: boolean
  codigo_publico: string
  padrao_nps: boolean
  padrao_csat: boolean
  respostas: number
  atualizado_em: string
  /** O cliente pode mudar a resposta até 7 dias depois (docs/api-editar-resposta.md). Pode faltar na API antiga. */
  permite_editar?: boolean
  /** Etapa 5l: há alterações salvas no rascunho que ainda não foram publicadas. */
  tem_rascunho?: boolean
  /** Etapa 5l: a versão publicada (sobe a cada publicação). */
  versao?: number
  publicado_em?: string | null
  /** Etapa 5l: quantas perguntas (sem blocos de conteúdo nem quebras de página). */
  perguntas_total?: number
}

/** Etapa 5l: o documento que o editor salva no rascunho e publica. */
export interface DocumentoFormulario {
  perguntas: Pergunta[]
  tema: Tema
  finais: Final[]
}

/** Etapa 5l: o rascunho guardado (null = sem alterações pendentes). */
export interface RascunhoFormulario extends DocumentoFormulario {
  salvo_em?: string | null
  salvo_por_nome?: string | null
}

export interface Formulario extends FormularioResumo {
  perguntas: Pergunta[]
  tema: Tema
  /** Etapa 5l: os finais publicados (em ordem; vale o 1º cuja condição vale). */
  finais?: Final[]
  publicado_por_nome?: string | null
  /** Etapa 5l: as alterações em edição, ou null. */
  rascunho?: RascunhoFormulario | null
  /** Etapa 5l: controle de concorrência do rascunho (sobe a cada gravação, publicação e descarte). */
  rascunho_rev?: number
  /** Etapa 5l: o começo das URLs das imagens da plataforma (só essas entram no HTML). */
  prefixo_imagens?: string | null
}

export interface DadosFormulario {
  nome?: string
  descricao?: string | null
  perguntas?: Pergunta[]
  tema?: Tema
  finais?: Final[]
  ativo?: boolean
  publico?: boolean
  permite_editar?: boolean
}

/** Etapa 5l: resposta de PUT /formularios/{id}/rascunho. `rascunho` já normalizado (ids gerados, HTML limpo). */
export interface RespostaRascunho {
  rev: number
  salvo_em: string | null
  /** Mesmas chaves da validação (`perguntas.<i>.<campo>`, `finais.<i>.<campo>`, `tema.<campo>`), mais os avisos de citação. */
  problemas?: Record<string, string> | null
  /** As chaves de `problemas` que são só aviso (citação que sai vazia): não bloqueiam publicar. */
  avisos?: Record<string, string> | null
  /** O servidor guardou rascunho? (`false` quando o documento normalizado ficou igual ao publicado) */
  tem_rascunho?: boolean
  /** O documento normalizado (ids gerados, HTML limpo), para o editor aplicar. */
  rascunho: DocumentoFormulario | null
}

/** Etapa 5l: 409 `rascunho_desatualizado` (o `erro` traz quem salvou e quando). */
export interface ConflitoRascunho {
  rev?: number | null
  salvo_em?: string | null
  salvo_por_nome?: string | null
}

/** Etapa 5l: imagem de um bloco de conteúdo (POST /formularios/{id}/imagens). */
export interface ImagemConteudo {
  url: string
  largura?: number | null
  altura?: number | null
}

export interface ModeloFormulario {
  chave: string
  nome: string
  descricao: string
  perguntas: Pergunta[]
  tema: Tema
  /** Etapa 5l: os modelos com finais por segmento. */
  finais?: Final[]
}

export interface ResultadoPergunta {
  id: string
  tipo: string
  titulo: string
  respostas: number
  distribuicao?: Record<string, number>
  media?: number | null
  opcoes?: Record<string, number>
  textos?: { texto: string; data: string }[]
}

export interface Resultados {
  total: number
  nps?: { valor: number; promotores: number; neutros: number; detratores: number } | null
  csat?: { percentual: number; media: number } | null
  perguntas: ResultadoPergunta[]
}

/** Etapa 4a: respostas registradas à mão também podem vir por telefone ou reunião. */
export type CanalResposta = 'email' | 'whatsapp' | 'link' | 'qr' | 'widget' | 'api' | 'importacao' | 'manual' | 'telefone' | 'reuniao'

export interface Resposta {
  id: Id
  formulario: Referencia
  contato: { id: Id; nome: string; email: string | null } | null
  empresa: Referencia | null
  canal: CanalResposta
  nota: number | null
  tipo_nota: 'nps' | 'csat' | null
  grupo: string | null
  comentario: string | null
  respostas: Record<string, unknown>
  contexto: Contexto
  referencia: string | null
  criada_em: string
  /** Etapa 4a: a data da resposta (a informada, à mão ou na importação; sem ela, a de entrada). Ordena e filtra. */
  data?: string
  /** Etapa 4a: como a resposta entrou (pela pesquisa, registrada à mão ou importada). */
  origem?: OrigemResposta
}

// ───────────────────────── Etapa 3a (docs/api-etapa-3.md) ─────────────────────────

export interface ItemPreCondicao {
  chave: 'assinatura' | 'provedor' | 'formulario' | 'envios_ativos' | (string & {})
  ok: boolean
  /** Vem null quando o item já está ok. */
  mensagem: string | null
  acao: { rotulo: string; rota: string } | null
}

export interface PreCondicoes {
  pronto: boolean
  itens: ItemPreCondicao[]
}

export interface Agradecimentos {
  promotor: string
  neutro: string
  detrator: string
}

export interface ConfigEnvios {
  envios_ativos: boolean
  envio_automatico: boolean
  formulario_id: Id | null
  intervalo_dias: number
  descanso_dias: number
  lembretes: number
  dias_lembretes: number[]
  janela_inicio: string
  janela_fim: string
  so_dias_uteis: boolean
  responder_para: string | null
  remetente_nome: string | null
  assunto_convite: string
  texto_convite: string
  assunto_lembrete: string
  texto_lembrete: string
  texto_whatsapp: string
  agradecimento_ativo: boolean
  agradecimento: Agradecimentos
  /** Etapa 3b: por onde a pesquisa sai. Se não vier (API antiga), vale "email". */
  canal?: CanalConfig
  /**
   * Etapa 5e (visual dos e-mails de pesquisa; opcionais porque a API antiga não manda). Cor de destaque `#RRGGBB`;
   * null = a cor do tema do formulário do envio.
   */
  email_cor?: string | null
  /** Mostra o logo (o do formulário; sem ele, o da empresa). Sem o campo, vale true. */
  email_mostrar_logo?: boolean
  /** Imagem de topo: uma imagem do banco de imagens da conta. */
  email_imagem_topo?: ImagemTopoEmail | null
  /** Texto puro, até 300 (null = sem assinatura). */
  email_assinatura?: string | null
  /** Texto puro, até 500 (null = só as linhas fixas do rodapé). */
  email_rodape?: string | null
  /** Etapa 5i: a conta pediu para tirar "Pesquisa feita com Toqqi" (só vale onde o plano permite). */
  ocultar_mencao_toqqi?: boolean
  /** Etapa 5i: só leitura (GET/PUT devolvem): o plano permite tirar? A menção aparece hoje? */
  mencao_toqqi?: { pode_ocultar: boolean; aparece: boolean }
}

/**
 * Corpo de PUT /envios/configuracao (parcial: só os campos enviados mudam). A imagem de topo vai pelo id
 * (`email_imagem_topo_id`: uma imagem do banco da conta, ou null), não pelo objeto que o GET devolve.
 */
export type DadosConfigEnvios = Partial<Omit<ConfigEnvios, 'email_imagem_topo'>> & { email_imagem_topo_id?: Id | null }

export interface ResumoEnvios {
  na_fila: number
  aguardando: number
  responderam: number
  com_erro: number
  saiu_da_lista: number
  lembretes_hoje: number
  enviados_30d: number
}

/**
 * GET /envios/panorama (docs/api-envios-panorama.md): o estado do envio automático e a próxima rodada, a agenda dos
 * próximos 14 dias e quantos responderam nos últimos 30 dias (e nos 30 anteriores).
 */
export interface PanoramaEnvios {
  automatico: {
    /** desligado = envios desligados; parado = falta uma pré-condição; manual = sem o automático; ligado. */
    estado: 'desligado' | 'parado' | 'manual' | 'ligado'
    /** Quando a próxima rodada pode sair (hora de São Paulo); só com o automático ligado e pronto. */
    proxima_rodada: string | null
    /** Quem está na fila e pode receber agora (cada rodada leva até `por_rodada`). */
    na_fila: number
    /** Na fila, mas fora da rodada: sem canal, em descanso ou com 3 falhas seguidas. */
    fora_da_rodada: number
    por_rodada: number
    /** Com a fila vazia: o dia em que o próximo contato entra nela. */
    proximo_contato: string | null
    janela_inicio: string
    janela_fim: string
    so_dias_uteis: boolean
    intervalo_dias: number
    canal: 'email' | 'whatsapp' | 'whatsapp_e_email'
    lembretes: number
  }
  /** 14 dias a partir de hoje; `sai` = o dia tem envio (o que cairia num dia sem envio vai para o próximo). */
  agenda: { dia: string; pesquisas: number; lembretes: number; sai: boolean }[]
  respostas: RespostasEnvios & { anterior: RespostasEnvios }
}

export interface RespostasEnvios {
  de: string
  ate: string
  enviadas: number
  respondidas: number
  taxa: number | null
  /** Em quantas horas metade das respondidas chegou (mediana). */
  horas_ate_metade: number | null
  canais: { canal: 'email' | 'whatsapp'; enviadas: number; respondidas: number; taxa: number | null }[]
}

export interface ContatoEnvio {
  id: Id
  nome: string
  email: string | null
  telefone: string | null
  empresa: Referencia | null
  grupo: Referencia | null
  responsavel: Referencia | null
  ativo: boolean
  situacao: SituacaoContato
  ultimo_envio: string | null
  proximo_envio: string | null
  lembretes_enviados: number
  proximo_lembrete: string | null
  descanso_ate: string | null
  ultimo_erro: string | null
  enviando: boolean
}

export interface IgnoradoEnvio {
  contato_id: Id
  nome: string
  motivo: string
}

export interface ResultadoDisparo {
  agendados: number
  ignorados: IgnoradoEnvio[]
}

export type CanalEnvio = 'email' | 'whatsapp'
export type TipoEnvio = 'convite' | 'lembrete' | 'agradecimento' | 'retorno'
export type OrigemEnvio = 'manual' | 'automatico' | 'lembrete' | 'resposta'
/** `entregue` e `lido` vêm do WhatsApp automático (etapa 3b), atualizados pelo aviso da Meta. */
export type SituacaoEnvio = 'pendente' | 'enviado' | 'entregue' | 'lido' | 'erro' | 'aberto_no_whatsapp'

export interface Envio {
  id: Id
  criado_em: string
  contato: Referencia | null
  para: string
  canal: CanalEnvio
  tipo: TipoEnvio
  origem: OrigemEnvio
  situacao: SituacaoEnvio
  erro: string | null
  usuario: Referencia | null
  pode_tentar_de_novo: boolean
}

export type OrigemDescadastro = 'link' | 'um_clique' | 'manual' | 'whatsapp'

export interface Descadastro {
  /** Na etapa 3b o descadastro pode ser só por telefone (pedido "SAIR" no WhatsApp): aí o e-mail vem null. */
  email: string | null
  telefone?: string | null
  contato: Referencia | null
  motivo: string | null
  origem: OrigemDescadastro | (string & {})
  criado_em: string
}

export interface WhatsappContato {
  url: string
  mensagem: string
  link: string
}

/** Resultado de "Enviar lembretes agora" / "Rodar envio automático agora". O contrato não fixa se ignorados é lista ou número. */
export interface ResultadoTarefa {
  enviados?: number
  agendados?: number
  ignorados?: number | unknown[]
}

// ───────────────────────── Etapa 3b (docs/api-etapa-3b.md) ─────────────────────────

/** Canal escolhido em Configurações de envio. */
export type CanalConfig = 'email' | 'whatsapp' | 'whatsapp_e_email'

export interface ChaveIntegracao {
  existe: boolean
  prefixo: string | null
  criada_em: string | null
  ultimo_uso: string | null
}

/** Resposta de POST /integracoes/chave: a chave completa vem só aqui, uma vez. */
export interface ChaveGerada {
  chave: string
  prefixo: string
  criada_em: string
}

/** Etapa 5c: `indicacao.criada` e `indicacao.atualizada` (situação mudou). */
export type EventoWebhook =
  | 'resposta.criada'
  | 'contato.descadastrado'
  | 'indicacao.criada'
  | 'indicacao.atualizada'
  | 'empresa.perdida'
  | 'empresa.reativada'
  | 'resposta.atualizada'

export interface Webhook {
  id: Id
  url: string
  eventos: EventoWebhook[]
  ativo: boolean
  segredo_prefixo: string | null
  criado_em: string
  ultima_entrega: { quando: string; status_http: number | null; ok: boolean } | null
  falhas_seguidas: number
}

/** POST /integracoes/webhooks devolve o webhook e o segredo (mostrado uma vez). */
export interface WebhookCriado extends Webhook {
  segredo: string
}

export interface ResultadoTesteWebhook {
  ok: boolean
  status_http: number | null
  mensagem: string
}

export interface EntregaWebhook {
  id: Id
  evento: EventoWebhook | (string & {})
  criado_em: string
  tentativas: number
  status_http: number | null
  ok: boolean
  erro: string | null
}

export interface FranquiaWhatsapp {
  plano: string | null
  /** Mensagens por mês; null = sem franquia (etapa 5k, o padrão: a Meta cobra a conta do cliente). */
  limite: number | null
  usadas_mes: number
  excedente_ativo: boolean
  excedentes_mes: number
  valor_excedente: number
}

export interface WhatsappIntegracao {
  conectado: boolean
  numero_exibicao: string | null
  nome_verificado: string | null
  phone_number_id: string | null
  waba_id: string | null
  modelo: { nome: string; idioma: string } | null
  ativo: boolean
  franquia: FranquiaWhatsapp
  ultimo_erro: string | null
  /** Para colar no painel da Meta. Podem não vir para quem só lê (envios.ver). */
  webhook_url?: string | null
  webhook_verificacao?: string | null
}

/**
 * Situação do número na Meta, lida na hora (GET /integracoes/whatsapp/numero; docs/api-whatsapp-registro.md):
 * `falta_registrar` é o "Pendente" do WhatsApp Manager (adicionado, mas sem o registro na Cloud API).
 */
export type SituacaoNumero = 'registrado' | 'falta_registrar' | 'atencao' | 'problema' | 'desconhecida'

export interface NumeroWhatsapp {
  situacao: SituacaoNumero
  /** O `status` da Meta (CONNECTED, PENDING, FLAGGED...), ou null se ela não informou. */
  status: string | null
  /** O número foi confirmado com o código (SMS ou ligação); null se a Meta não informou. */
  codigo_confirmado: boolean | null
}

export interface ConexaoWhatsapp {
  phone_number_id: string
  waba_id: string
  token: string
  modelo_nome: string
  modelo_idioma: string
}

// ───────────────────────── Etapa 4a (docs/api-etapa-4a.md) ─────────────────────────

export type TipoNota = 'nps' | 'csat'

/** Faixa do NPS: ≥ 75 excelente, ≥ 50 muito bom, ≥ 0 pode melhorar, < 0 crítico. */
export type FaixaNps = 'excelente' | 'muito_bom' | 'pode_melhorar' | 'critico'

export type OrigemResposta = 'pesquisa' | 'manual' | 'importacao'

/** Canais aceitos ao registrar uma resposta à mão (POST /respostas). */
export type CanalManual = 'manual' | 'whatsapp' | 'telefone' | 'email' | 'reuniao'

/** Assunto do comentário, achado por palavras-chave (GET /respostas/temas). */
export interface TemaResposta {
  chave: string
  rotulo: string
}

export type SituacaoAcao = 'a_fazer' | 'em_andamento' | 'concluida'
export type PrioridadeAcao = 'alta' | 'media' | 'baixa'
export type OrigemAcao = 'automatica' | 'manual'
/** Só para ação não concluída com prazo; null = prazo depois de amanhã (ou sem prazo). */
export type SeloPrazo = 'vencido' | 'hoje' | 'amanha'

/** A ação ligada a uma resposta: a automática; senão a mais recente. */
export interface AcaoDaResposta {
  id: Id
  situacao: SituacaoAcao
  prazo: string | null
  prazo_selo: SeloPrazo | null
}

/** Resposta da etapa 4a (lista, registro, análise, arquivar): o formato da etapa 2 com mais campos. */
export interface RespostaItem extends Omit<Resposta, 'contato' | 'empresa' | 'grupo' | 'tipo_nota'> {
  /** Data da resposta (informada ou, sem ela, a de entrada): a data de toda regra de período. */
  data: string
  respondida_em: string | null
  origem: OrigemResposta
  tipo_nota: TipoNota | null
  /** Categoria (grupo da nota). */
  grupo: GrupoNota | null
  temas: string[]
  temas_manuais: boolean
  o_que_faltou: string | null
  o_que_combinamos: string | null
  analisada_em: string | null
  analisada_por: Referencia | null
  registrada_por: Referencia | null
  arquivada: boolean
  /** O cliente mudou a resposta (a última vez e quantas vezes); pode faltar na API antiga. */
  editada_em?: string | null
  edicoes?: number
  contato: { id: Id; nome: string; email: string | null; perfil: Referencia | null } | null
  empresa: { id: Id; nome: string; grupo: Referencia | null } | null
  acao: AcaoDaResposta | null
  /** Etapa 4b: análise da IA (null quando a resposta não passa pela IA; pode faltar no servidor antigo). */
  ia?: AnaliseIa | null
}

/** Pergunta com a resposta já em texto (ex.: "Sim", "31/12/2025"). */
export interface PerguntaRespondida {
  id: string
  titulo: string
  tipo: string
  resposta: string | null
}

export interface RespostaDetalhe extends RespostaItem {
  perguntas: PerguntaRespondida[]
  convite: { evento: string | null; referencia: string | null; assunto: string | null } | null
  /** Todas as ações ligadas à resposta (resumidas). */
  acoes: (AcaoDaResposta & { titulo: string })[]
}

export interface NpsResumo {
  valor: number | null
  faixa: FaixaNps | null
  promotores: number
  neutros: number
  detratores: number
  total: number
}

/** Métricas de GET /respostas, sobre o mesmo filtro (todas as páginas). */
export interface MetricasRespostas {
  nps: NpsResumo | null
  csat: { percentual: number | null; media: number | null; total: number } | null
  total: number
  /** Triagem (docs/api-respostas-triagem.md), contada sobre os outros filtros: nota baixa ou comentário sem análise. */
  para_analisar?: number
  /** Com algo escrito pelo cliente. */
  com_comentario?: number
  /** Temas citados (menções e quantas com nota baixa), dos mais citados aos menos. */
  temas?: { chave: string; rotulo: string; mencoes: number; nota_baixa: number }[]
}

export interface PaginaRespostas extends Pagina<RespostaItem> {
  metricas?: MetricasRespostas | null
}

export interface FiltrosRespostas {
  busca?: string
  categoria?: GrupoNota | ''
  tipo_nota?: TipoNota | ''
  /** Grupo de empresas. */
  grupo_id?: Id | ''
  empresa_id?: Id | ''
  contato_id?: Id | ''
  tema?: string
  perfil_id?: Id | ''
  canal?: CanalResposta | ''
  origem?: OrigemResposta | ''
  formulario_id?: Id | ''
  de?: string
  ate?: string
  /** "entrada" filtra pela data em que a resposta chegou ao Toqqi. */
  data_por?: 'resposta' | 'entrada'
  arquivadas?: 'false' | 'true' | 'todas'
  /** Tira as respostas de empresas desativadas (as sem empresa continuam), como no painel. */
  so_ativos?: boolean
  /** Etapa 4b: sentimento da IA ("sem_analise" = com texto do cliente e ainda sem análise). */
  sentimento?: FiltroSentimento | ''
  /** Etapa 4b: só reclamações (com `tema`, reclamações daquele tema). */
  reclamacao?: boolean
  /** Triagem: nota baixa ou comentário, ainda sem análise da equipe. */
  para_analisar?: boolean
  /** Triagem: só as com comentário do cliente. */
  com_comentario?: boolean
  /** Etapa 4b: valor do contexto do pedido (sem diferenciar maiúsculas e espaços nas pontas). */
  motorista?: string
  rota?: string
  filial?: string
  transportadora?: string
  pagina?: number
  por_pagina?: number
}

export interface DadosRegistroResposta {
  contato_id: Id
  nota: number
  canal?: CanalManual
  comentario?: string
  /** AAAA-MM-DD; sem ela, vale hoje. */
  data?: string
}

/** PATCH /respostas/{id}: só o que mudou. Mandar `temas` marca os temas como escolhidos à mão. */
export interface DadosAnaliseResposta {
  nota?: number
  comentario?: string | null
  o_que_faltou?: string | null
  o_que_combinamos?: string | null
  temas?: string[]
}

export interface ResponsavelAcao {
  id: Id
  nome: string
  email: string | null
  foto_url: string | null
}

export interface Acao {
  id: Id
  titulo: string
  descricao: string
  /** "O que foi feito". Obrigatória para concluir. */
  resolucao: string | null
  situacao: SituacaoAcao
  prioridade: PrioridadeAcao
  prazo: string | null
  prazo_selo: SeloPrazo | null
  empresa: Referencia | null
  contato: Referencia | null
  responsavel: ResponsavelAcao | null
  resposta: { id: Id; nota: number | null; tipo_nota: TipoNota | null; grupo: GrupoNota | null; comentario: string | null; data: string } | null
  origem: OrigemAcao
  grupo: GrupoNota | null
  tipo_nota: TipoNota | null
  nota: number | null
  criada_em: string
  atualizada_em: string
  iniciada_em: string | null
  concluida_em: string | null
  criado_por: Referencia | null
  concluida_por: Referencia | null
  /**
   * Etapa 5d: até 3 passos sugeridos pela IA ao criar a ação de uma resposta, e a situação (null = sem passos: nada
   * aparece). Opcionais: a API anterior à 5d não manda.
   */
  ia_passos?: string[] | null
  ia_passos_situacao?: SituacaoPassosIa | null
  /** Melhoria 4: quando o cliente foi avisado do que foi feito (uma vez) e o texto enviado. */
  retorno_em?: string | null
  retorno_texto?: string | null
  /** O cliente mudou a nota da resposta depois do plano criado: a nota nova e quando (null = não mudou). */
  nota_editada?: number | null
  nota_editada_em?: string | null
}

export interface TotaisQuadro {
  a_fazer: number
  em_andamento: number
  concluida: number
  vencidas: number
}

export interface QuadroAcoes {
  colunas: Record<SituacaoAcao, Acao[]>
  totais: TotaisQuadro
}

/**
 * GET /acoes/panorama (docs/api-acoes-panorama.md), com os filtros do quadro (menos "Só vencidas"; a lista de
 * responsáveis ignora também o filtro de responsável): os prazos das abertas, quem está com quantas e as concluídas.
 */
export interface PanoramaAcoes {
  prazos: { abertas: number; vencidas: number; hoje: number; proximos_7_dias: number; depois: number; sem_prazo: number }
  /** Até 8: primeiro quem tem mais vencidas, depois mais abertas; `responsavel` nulo = sem responsável. */
  responsaveis: { responsavel: Referencia | null; abertas: number; vencidas: number }[]
  concluidas: ConcluidasAcoes & { anterior: ConcluidasAcoes }
}

export interface ConcluidasAcoes {
  de: string
  ate: string
  total: number
  /** Mediana de dias da criação à conclusão. */
  mediana_dias: number | null
  /** Com o e-mail "Avisar o cliente" enviado. */
  com_retorno: number
}

export interface FiltrosAcoes {
  busca?: string
  categoria?: GrupoNota | ''
  tipo_nota?: TipoNota | ''
  /** 0 = sem responsável. */
  responsavel_id?: Id | ''
  empresa_id?: Id | ''
  /** Grupo de empresas. */
  grupo_id?: Id | ''
  /** Data de criação da ação. */
  de?: string
  ate?: string
  so_vencidas?: boolean
}

export interface DadosNovaAcao {
  titulo: string
  descricao?: string
  empresa_id?: Id | null
  contato_id?: Id | null
  resposta_id?: Id | null
  responsavel_id?: Id | null
  prioridade?: PrioridadeAcao
  prazo?: string | null
}

/** PATCH /acoes/{id}: null limpa os opcionais. Mover = mudar a situação. */
export interface DadosEdicaoAcao {
  titulo?: string
  descricao?: string
  resolucao?: string | null
  responsavel_id?: Id | null
  prioridade?: PrioridadeAcao
  prazo?: string | null
  situacao?: SituacaoAcao
  empresa_id?: Id | null
}

/** Prazos (1 a 90 dias) das ações automáticas e se promotor também ganha ação. */
export interface ConfigAcoes {
  prazo_detrator: number
  prazo_neutro: number
  prazo_promotor: number
  acao_promotor: boolean
}

/** Etapa 5h: POST /acoes/detratores. Até 100 por chamada; `restantes` = os que ficaram para a próxima. */
export interface ResultadoDetratores {
  criadas: number
  restantes: number
}

export interface FiltrosPainel {
  de?: string
  ate?: string
  /** Grupo de empresas. */
  grupo_id?: Id | ''
  so_ativos?: boolean
}

export interface ItemMovimentacao {
  tipo: 'resgatado' | 'deixou_de_ser_promotor'
  contato: Referencia
  empresa: Referencia | null
  nota_anterior: number
  nota_atual: number
  data_anterior: string
  data_atual: string
}

export interface EmpresaAtencao {
  empresa: Referencia
  nps: number | null
  acoes_abertas: number
  acoes_vencidas: number
  /** Data da ação aberta mais antiga. */
  desde: string | null
  responsavel: Referencia | null
  ultimo_comentario_detrator: string | null
  /** A ação mais urgente (botão Tratar). */
  acao_id: Id | null
}

export interface EmpresaNps {
  empresa: Referencia
  nps: number
  respostas: number
  /** Painel v2: contrato mensal da empresa (pode faltar no servidor antigo; null sem valor cadastrado). */
  valor_mensal?: ValorDecimal | null
}

/** Painel v2: um mês da evolução de 12 meses (grupo e só ativas valem; o período não). */
export interface MesEvolucao12m {
  /** AAAA-MM */
  mes: string
  nps: number | null
  total: number
  /** O mês cruza o período do filtro. */
  no_periodo: boolean
}

/** Painel v2: tom (sentimento da IA) dos comentários do cliente nas respostas do período (NPS e CSAT). */
export interface TomComentarios {
  /** Com comentário e com sentimento da IA. */
  analisados: number
  com_comentario: number
  total_respostas: number
  /** Com comentário e análise da IA na fila (`ia_situacao = pendente`); pode faltar em servidor antigo. */
  pendentes?: number
  /** Etapa 5h: IA disponível na plataforma e análise ligada na conta (pode faltar no servidor antigo). */
  ia_ligada?: boolean
  /** Etapa 5h: comentários do período que a IA leria, nem analisados nem na fila (pode faltar no servidor antigo). */
  sem_analise?: number
  negativo: number
  misto: number
  neutro: number
  positivo: number
  /** O mesmo no período anterior (só com período). */
  anterior: { analisados: number; negativo: number } | null
}

export interface Painel {
  periodo: { de: string | null; ate: string | null; anterior: { de: string; ate: string } | null }
  nps: NpsResumo & {
    pct: { promotores: number; neutros: number; detratores: number }
    decisores: { valor: number | null; total: number }
  }
  /** valor = NPS do período − NPS do período anterior (anterior). Null sem período ou sem NPS em um dos dois. */
  variacao: { valor: number; anterior: number } | null
  csat: { percentual: number | null; media: number | null; total: number; satisfeitos: number }
  taxa_resposta: { percentual: number | null; responderam: number; convidados: number; amostra_pequena: boolean }
  movimentacao: { resgatados: number; deixaram_de_ser_promotores: number; itens: ItemMovimentacao[] }
  atencao: {
    acoes_abertas: number
    acoes_vencidas: number
    tudo_em_dia: boolean
    empresas: EmpresaAtencao[]
    /** `carteira` (painel v2): soma do valor mensal das empresas no filtro; null se nenhuma tem valor (pode faltar). */
    receita_em_risco: { valor: number | string; empresas: number; sem_valor: number; carteira?: ValorDecimal | null }
    /**
     * Etapa 5h: empresas (ou contatos sem empresa) com detrator no filtro e sem plano aberto, quantos planos
     * POST /acoes/detratores criaria agora (pode faltar no servidor antigo).
     */
    detratores_sem_plano?: number
  }
  /**
   * Etapa 4b: `reclamacoes` (menções que contam como reclamação) e `variacao` (menções no período − no período
   * anterior de mesmo tamanho; null sem período). Podem faltar no servidor antigo.
   */
  temas: { chave: string; rotulo: string; mencoes: number; nota_media: number | null; reclamacoes?: number; variacao?: number | null }[]
  comentarios: {
    resposta_id: Id
    data: string
    nota: number | null
    tipo_nota: TipoNota | null
    grupo: GrupoNota | null
    comentario: string
    contato: Referencia | null
    empresa: Referencia | null
  }[]
  /** NPS por mês (AAAA-MM), em ordem cronológica. */
  evolucao: { mes: string; nps: number | null; total: number }[]
  empresas: { menor: EmpresaNps[]; maior: EmpresaNps[] }
  /** `tom` da palavra: o contrato ainda não manda; se um dia vier, a nuvem usa (sem ele, a cor segue o tamanho). */
  palavras: { palavra: string; total: number; tom?: 'negativo' | 'positivo' | 'neutro' | null }[]
  /** Cada passo: feito ou não (o contrato não fixa se vem booleano ou contagem). */
  primeiros_passos: {
    contatos: boolean | number
    envios_ligados: boolean | number
    primeiro_envio: boolean | number
    primeira_resposta: boolean | number
  }
  /** Etapa 4b: temas com pico de reclamações nos últimos 7 dias (sem os filtros da tela). */
  picos?: Pico[]
  /** Painel v2: sempre 12 meses terminando no fim do período (pode faltar no servidor antigo: o site usa `evolucao`). */
  evolucao_12m?: MesEvolucao12m[]
  /** Painel v2: tom dos comentários (pode faltar no servidor antigo: o bloco não aparece). */
  tom?: TomComentarios
}

// ───────────────────────── Etapa 4b (docs/api-etapa-4b.md) ─────────────────────────

export type Sentimento = 'positivo' | 'neutro' | 'negativo'
/** Tom geral do comentário: "misto" quando há elogio e reclamação. */
export type SentimentoGeral = Sentimento | 'misto'
export type FiltroSentimento = SentimentoGeral | 'sem_analise'
export type SituacaoIa = 'pendente' | 'analisada' | 'falhou' | 'limite'

/** Análise da IA de uma resposta (`ia` na lista e no detalhe). */
export interface AnaliseIa {
  situacao: SituacaoIa
  sentimento: SentimentoGeral | null
  /** Uma frase curta (até 160 caracteres). */
  resumo: string | null
  /** Temas citados, com o sentimento do cliente sobre cada um. */
  temas: { tema: string; sentimento: Sentimento }[] | null
  /** Quando foi analisada. */
  em: string | null
}

/** Tema com 3+ reclamações nos últimos 7 dias e pelo menos o dobro da média semanal das 4 semanas antes. */
export interface Pico {
  tema: string
  rotulo: string
  reclamacoes: number
  /** Média semanal das 4 semanas anteriores (uma casa). */
  media_anterior: number
  /** Os 7 dias (AAAA-MM-DD). */
  de: string
  ate: string
}

/** Configurações › IA (GET/PUT /conta/ia). */
export interface ConfigIa {
  /** A IA está ligada na plataforma (chave configurada). */
  disponivel: boolean
  provedor: string | null
  /** A chave da conta: "Analisar comentários com IA". */
  analise_respostas: boolean
  /** AAAA-MM */
  mes: string
  analises: number
  /** Teto de segurança do mês (pelo plano). */
  limite: number
  pendentes: number
  falharam_no_mes: number
  /**
   * Etapa 5b: cota de IA do plano no mês (cada pergunta ao assistente, resumo ou parecer usa 1, ou 2 no Mais detalhado;
   * a análise de cada resposta não entra).
   */
  cota?: CotaIa
  /** Etapa 5d: como a IA escreve (assistente, resumo, parecer e passos) e se as ações ganham passos sugeridos. */
  modelo?: NivelModeloIa | (string & {})
  estilo?: EstiloIa | (string & {})
  passos_acoes?: boolean
  /** Etapa 5d: as opções, com os textos da API (na ordem). */
  modelos?: OpcaoIa[]
  estilos?: OpcaoIa[]
}

/** PUT /conta/ia (etapa 5d): só os campos que mudaram (pelo menos um). Devolve o estado inteiro. */
export interface DadosConfigIa {
  analise_respostas?: boolean
  modelo?: NivelModeloIa | (string & {})
  estilo?: EstiloIa | (string & {})
  passos_acoes?: boolean
}

export interface ResultadoAnalisarRecentes {
  marcadas: number
  restantes_no_mes: number
}

/** Valor decimal da API (reais): pode chegar como número ou como texto ("1250.00"). */
export type ValorDecimal = number | string

export type FaixaValor = 'ate_2k' | '2k_10k' | '10k_50k' | 'acima_50k' | 'sem_valor'
export type TempoCliente = 'ate_3m' | '3_6m' | '6_12m' | 'mais_1a' | 'sem_data'
export type Quadrante = 'proteger' | 'manter' | 'corrigir' | 'crescer'
export type DimensaoEntrega = 'motorista' | 'rota' | 'filial' | 'transportadora'
export type OrdemEmpresas = 'prioridade' | 'nps' | 'valor' | 'cobertura' | 'respostas' | 'nome'
export type OrdemEntregas = 'respostas' | 'nps' | 'csat' | 'reclamacoes' | 'valor'

/** Filtros comuns dos relatórios. Sem `de`/`ate` = todo o histórico; `so_ativos` padrão true. */
export interface FiltrosRelatorio {
  de?: string
  ate?: string
  /** Grupo de empresas. */
  grupo_id?: Id | ''
  so_ativos?: boolean
}

/** Filtros de empresa (0 = sem segmento / sem responsável). */
export interface FiltrosEmpresaRelatorio extends FiltrosRelatorio {
  segmento_id?: Id | ''
  responsavel_id?: Id | ''
  faixa_valor?: FaixaValor | ''
  tempo_cliente?: TempoCliente | ''
}

export interface FiltrosRelatorioEmpresas extends FiltrosEmpresaRelatorio {
  busca?: string
  respostas?: 'com' | 'sem' | ''
  quadrante?: Quadrante | ''
  ordem?: OrdemEmpresas
  pagina?: number
  por_pagina?: number
}

export type FiltrosRelatorioGrupos = Omit<FiltrosEmpresaRelatorio, 'responsavel_id'>

export interface FiltrosRelatorioEntregas extends FiltrosRelatorio {
  dimensao?: DimensaoEntrega
  busca?: string
  ordem?: OrdemEntregas
  pagina?: number
  por_pagina?: number
}

export interface CsatResumo {
  percentual: number | null
  media: number | null
  total: number
}

/** Contatos ativos que responderam (NPS) no período ÷ contatos ativos. */
export interface Cobertura {
  contatos_ativos: number
  responderam: number
  percentual: number | null
}

export interface UltimaResposta {
  data: string
  nota: number | null
  tipo_nota: TipoNota | null
}

export interface PontoMatriz {
  empresa: Referencia
  nps: number
  valor_mensal: ValorDecimal
  respostas: number
  quadrante: Quadrante
}

export interface ItemRelatorioEmpresa {
  empresa: { id: Id; nome: string; ativa: boolean }
  grupo: Referencia | null
  segmento: Referencia | null
  responsavel: Referencia | null
  valor_mensal: ValorDecimal | null
  cliente_desde: string | null
  nps: NpsResumo
  cobertura: Cobertura
  /** A mais recente, de qualquer data. */
  ultima_resposta: UltimaResposta | null
  /** Teve detrator no período. */
  em_risco: boolean
  quadrante: Quadrante | null
  /** Agora (sem o período). */
  acoes_abertas: number
}

export interface RelatorioEmpresas extends Pagina<ItemRelatorioEmpresa> {
  resumo: {
    empresas: number
    com_respostas: number
    cobertura: Cobertura
    receita: { total: ValorDecimal; em_risco: ValorDecimal; empresas_em_risco: number; sem_valor: number; percentual: number | null }
    por_faixa: Record<FaixaNps | 'sem_respostas', number>
  }
  matriz: {
    mediana_valor: ValorDecimal | null
    quadrantes: Record<Quadrante, number>
    /** Até 1.000, maiores valores primeiro. */
    pontos: PontoMatriz[]
    /** Empresas com NPS e sem valor cadastrado (fora do gráfico). */
    sem_valor: number
  }
}

export interface LinhaGrupoNps {
  empresas: number
  nps: NpsResumo
}

export interface PrioridadeTema {
  tema: string
  rotulo: string
  mencoes: number
  nota_media: number | null
  reclamacoes: number
}

export interface RelatorioGrupos {
  segmentos: (LinhaGrupoNps & { segmento: Referencia | null })[]
  grupos: (LinhaGrupoNps & { grupo: Referencia | null })[]
  tempo_cliente: (LinhaGrupoNps & { faixa: TempoCliente; rotulo: string })[]
  valor: (LinhaGrupoNps & { faixa: FaixaValor; rotulo: string })[]
  /** "O que resolver primeiro": mais citados e com nota mais baixa primeiro. */
  prioridades: PrioridadeTema[]
}

export interface ContagemSentimento {
  positivo: number
  neutro: number
  negativo: number
  sem_analise: number
}

export interface TemaRelatorio {
  tema: string
  rotulo: string
  mencoes: number
  reclamacoes: number
  elogios: number
  nota_media: number | null
  variacao: number | null
  /** Menções de respostas analisadas pela IA, pelo sentimento sobre o tema. */
  sentimento: ContagemSentimento
}

export interface SemanaTemas {
  /** Segunda-feira (AAAA-MM-DD). */
  inicio: string
  /** Domingo. */
  fim: string
  respostas: number
  temas: Record<string, { mencoes: number; reclamacoes: number }>
}

export interface RelatorioTemas {
  ia: { ativa: boolean; analisadas: number; com_comentario: number }
  /** Respostas com texto do cliente, pelo sentimento geral. */
  sentimento: ContagemSentimento & { misto: number }
  /** Os 6 temas, na ordem da tabela de temas. */
  temas: TemaRelatorio[]
  /** Em ordem cronológica, com as semanas vazias. */
  semanas: SemanaTemas[]
  picos: Pico[]
}

export interface ItemEntrega {
  /** Motorista, rota, filial ou transportadora (a forma mais frequente). */
  valor: string
  respostas: number
  nps: NpsResumo
  csat: CsatResumo
  reclamacoes: number
  /** Até 2. */
  temas: { tema: string; rotulo: string; mencoes: number }[]
  ultima_resposta: string | null
  /** Menos de 5 respostas. */
  amostra_pequena: boolean
}

export interface RelatorioEntregas extends Pagina<ItemEntrega> {
  dimensao: DimensaoEntrega
  /** Respostas do filtro sem essa informação. */
  sem_valor: number
}

export interface ItemResponsavelRelatorio {
  /** null = "Sem responsável". */
  responsavel: { id: Id; nome: string; foto_url: string | null } | null
  empresas: number
  empresas_com_respostas: number
  nps: NpsResumo
  receita: ValorDecimal
  receita_em_risco: ValorDecimal
  acoes_abertas: number
  acoes_vencidas: number
}

export interface RelatorioResponsaveis {
  itens: ItemResponsavelRelatorio[]
}

export interface EmpresaDaCarteira {
  empresa: Referencia
  nps: NpsResumo
  nota_media: number | null
  valor_mensal: ValorDecimal | null
  ultima_resposta: UltimaResposta | null
  acoes_abertas: number
}

export interface ContatoSemResposta {
  contato: { id: Id; nome: string; email: string | null }
  empresa: Referencia | null
  ultimo_envio: string
  dias: number
  /** Mais dias que o intervalo entre envios. */
  atrasado: boolean
}

export interface RelatorioOperacao {
  taxa_resposta: Painel['taxa_resposta']
  canais: { canal: CanalEnvio; convidados: number; responderam: number; percentual: number | null }[]
  acoes: { concluidas: number; tempo_medio_dias: number | null; no_prazo_percentual: number | null; abertas: number; vencidas: number }
  sem_resposta: { total: number; atrasados: number; intervalo_dias: number; itens: ContatoSemResposta[] }
}

export interface ItemLinhaDoTempo {
  resposta_id: Id
  data: string
  nota: number | null
  tipo_nota: TipoNota | null
  grupo: GrupoNota | null
  /** `cargo` e `perfil` vêm como nome (o contrato não fixa; aceitamos também {id, nome}). */
  contato: { id: Id; nome: string; cargo: string | Referencia | null; perfil: string | Referencia | null } | null
  canal: CanalResposta
  origem: OrigemResposta
  comentario: string | null
  temas: string[]
  ia: { sentimento: SentimentoGeral | null; resumo: string | null } | null
  acao: { id: Id; situacao: SituacaoAcao } | null
}

export interface HistoricoEmpresa {
  empresa: {
    id: Id
    nome: string
    ativa: boolean
    grupo: Referencia | null
    segmento: Referencia | null
    responsavel: Referencia | null
    valor_mensal: ValorDecimal | null
    cliente_desde: string | null
  }
  nps: NpsResumo
  csat: CsatResumo | null
  cobertura: Cobertura
  acoes: { abertas: number; vencidas: number; concluidas: number }
  /** Meses com dados, até os 24 mais recentes, em ordem cronológica. */
  evolucao: { mes: string; nps: number | null; total: number }[]
  /** Até 500, mais recentes primeiro. */
  linha_do_tempo: ItemLinhaDoTempo[]
  /** Respostas da empresa no período (todas, não só as da linha do tempo). */
  total: number
}

// ───────────────────── Etapa 5a: assinatura e cobrança pelo Asaas (docs/api-etapa-5a.md) ─────────────────────

/** Situação da conta (seção 3). Aceita outras strings para não quebrar se a API crescer. */
export type SituacaoConta = 'teste' | 'teste_expirado' | 'ativa' | 'atrasada' | 'cancelada' | 'cortesia' | (string & {})

export type TipoAvisoCobranca =
  | 'teste_acabando'
  | 'teste_expirado'
  | 'atrasada'
  | 'pausada'
  | 'cancelada'
  | 'cancelada_encerrada'
  | 'aguardando_pagamento'

/** Aviso do topo das telas (`conta.cobranca.aviso`). */
export interface AvisoCobranca {
  tipo: TipoAvisoCobranca | (string & {})
  /**
   * AAAA-MM-DD. teste_acabando e teste_expirado: último dia do teste; atrasada: dia em que os envios param;
   * pausada: vencimento da fatura em atraso; cancelada e cancelada_encerrada: `pago_ate`; aguardando_pagamento:
   * vencimento da primeira fatura de quem já assinou.
   */
  data: string | null
  /** Dias até `data` (0 = hoje), em teste_acabando, atrasada e cancelada. */
  dias: number | null
}

export interface CobrancaConta {
  /** Envios, robô, lembretes, CSAT e IA podem rodar. */
  liberada: boolean
  /** Tem assinatura ativa (mesmo antes do primeiro pagamento). */
  assinada?: boolean
  pago_ate: string | null
  atrasada_desde: string | null
  /** Quando os envios param (data e hora), se estão liberados com prazo. */
  pausa_em: string | null
  aviso: AvisoCobranca | null
  /**
   * Etapa 5f: dia (AAAA-MM-DD) em que a conta encerrada será excluída, depois do aviso por e-mail aos administradores;
   * null (ou ausente, no servidor antigo) quando não há exclusão marcada. Assinar um plano cancela.
   */
  exclusao_em?: string | null
}

export type ChavePlano = 'essencial' | 'profissional' | 'empresa'

export interface PlanoAssinatura {
  chave: ChavePlano | (string & {})
  nome: string
  /** Reais por mês (pode vir como texto decimal, "349.00"). */
  preco: ValorDecimal
  /** Contatos ativos permitidos; null = sem limite. */
  contatos: number | null
  /** Etapa 5k (ausentes no servidor antigo): perguntas ao ToqqiAI por mês, comentários lidos pela IA por mês e a franquia
   * do WhatsApp automático (null = sem franquia). */
  ia_cota?: number
  ia_teto?: number
  whatsapp?: number | null
}

/** Dados de cobrança (cliente no Asaas). Documento e telefone só com dígitos. */
export interface DadosCobranca {
  razao_social: string
  /** CPF (11) ou CNPJ (14). */
  documento: string
  email_cobranca: string
  /** Com DDD (a API guarda com o 55). */
  telefone: string
}

export type SituacaoCobranca = 'pendente' | 'paga' | 'vencida' | 'estornada' | 'removida'
export type FormaPagamento = 'pix' | 'boleto' | 'cartao'

/** A fatura pendente ou vencida mais antiga da assinatura. */
export interface FaturaAberta {
  valor: ValorDecimal
  /** AAAA-MM-DD. */
  vencimento: string
  situacao: SituacaoCobranca | (string & {})
  /** Página da fatura no Asaas (Pix, boleto ou cartão). */
  link: string | null
}

export interface CobrancaAssinatura extends FaturaAberta {
  /** Como foi (ou vai ser) paga; null enquanto o cliente não escolheu. */
  forma: FormaPagamento | (string & {}) | null
  pago_em: string | null
}

/** Etapa 5k: ciclo e forma de pagamento da assinatura. */
export type CicloAssinatura = 'mensal' | 'anual'
export type FormaAssinatura = 'pix' | 'qualquer'

/** Etapa 5k: descontos em % (Pix no mensal; anual, sem somar com o Pix). */
export interface DescontosPlanos {
  pix: number
  anual: number
}

/** Etapa 5k: a tabela do Personalizado (a calculadora em `utils/precos.ts` faz a conta). */
export interface TabelaPersonalizado {
  base: ValorDecimal
  /** Preço a cada 100 contatos até `ate` (null = acima da última faixa). */
  faixas: { ate: number | null; preco: ValorDecimal }[]
  /** Pacotes de perguntas ao ToqqiAI por mês (o primeiro vem incluído, preço 0). */
  ia: { cota: number; preco: ValorDecimal }[]
  contatos_min: number
  contatos_max: number
  passo: number
}

export interface Assinatura {
  plano: ChavePlano | 'personalizado' | (string & {})
  /** Etapa 5k: "Profissional", "Personalizado (2.000 contatos, 500 perguntas)". */
  nome?: string
  /** O valor de cada fatura (por mês, ou o total do ano no anual). */
  valor: ValorDecimal
  ciclo?: CicloAssinatura
  forma?: FormaAssinatura
  contatos?: number | null
  cota_ia?: number | null
  situacao: 'ativa' | 'cancelada' | (string & {})
  criada_em: string
  cancelada_em: string | null
  /** AAAA-MM-DD. */
  primeiro_vencimento: string
  dados: DadosCobranca
}

/** GET /assinatura (e a resposta das rotas que mudam a assinatura). */
export interface EstadoAssinatura {
  conta: {
    situacao: SituacaoConta
    plano: string | null
    teste_ate: string | null
    pago_ate: string | null
    atrasada_desde: string | null
    liberada: boolean
    pausa_em: string | null
    contatos_personalizado?: number | null
    cota_ia_personalizada?: number | null
  }
  contatos_ativos: number
  /** O Asaas está configurado na plataforma. */
  disponivel: boolean
  planos: PlanoAssinatura[]
  /** Etapa 5k (ausentes no servidor antigo). */
  descontos?: DescontosPlanos
  personalizado?: TabelaPersonalizado
  /** Dos dados da empresa e do e-mail do admin, para preencher o formulário de cobrança. */
  dados_sugeridos: { [K in keyof DadosCobranca]: string | null }
  /** A assinatura ativa (null sem assinatura ou depois de cancelar). */
  assinatura: Assinatura | null
  fatura_aberta: FaturaAberta | null
  /** As 12 mais recentes. */
  cobrancas: CobrancaAssinatura[]
}

// ───────────────────────── Etapa 5b (docs/api-etapa-5b.md) ─────────────────────────

/** Cota de IA do plano no mês: GET /assistente, cada resposta do assistente e GET /conta/ia. */
export interface CotaIa {
  usadas: number
  limite: number
  /** Nunca negativo. */
  restantes: number
  /** AAAA-MM (mês do calendário de São Paulo). */
  mes: string
}

/** Telas que a Ajuda e o assistente indicam (§5.4). */
export type ChaveAtalho =
  | 'inicio'
  | 'contatos'
  | 'importar_contatos'
  | 'envios'
  | 'formularios'
  | 'respostas'
  | 'planos_de_acao'
  | 'relatorios'
  /** Etapa 5c. */
  | 'crescimento'
  | 'equipe'
  | 'config_empresa'
  | 'config_envios'
  | 'config_acoes'
  | 'config_ia'
  | 'seguranca'
  | 'integracoes'
  | 'assinatura'
  | 'minha_conta'
  | 'ajuda'

/** Texto puro (sem HTML, markdown ou links). Um tipo novo, que a tela ainda não conhece, é ignorado. */
export type BlocoAjuda =
  | { tipo: 'paragrafo'; texto: string }
  | { tipo: 'passos'; itens: string[] }
  | { tipo: 'lista'; itens: string[] }
  | { tipo: 'dica'; texto: string }

export interface SecaoAjuda {
  /** kebab-case, único dentro do tópico; é a âncora do endereço (/ajuda/contatos#importar-planilha). */
  id: string
  titulo: string
  somente_admin: boolean
  /** Tela indicada (chave de §5.4) ou null. */
  atalho: ChaveAtalho | (string & {}) | null
  palavras: string[]
  blocos: BlocoAjuda[]
}

export interface TopicoAjuda {
  id: string
  titulo: string
  resumo: string
  secoes: SecaoAjuda[]
}

/** Grupo da jornada: `ciclo` ("Do cadastro ao resultado", numeradas e com "Próxima jornada") ou `alem` ("Para ir além"). */
export type GrupoJornada = 'ciclo' | 'alem'

/** Uma jornada da Ajuda (docs/ajuda-jornadas.md §1): onde fica, como fazer e o resultado. Texto puro. */
export interface JornadaAjuda {
  /** kebab-case, único entre as jornadas; é a âncora do endereço (/ajuda/jornadas#cadastrar-seus-clientes). */
  id: string
  grupo: GrupoJornada
  titulo: string
  objetivo: string
  somente_admin: boolean
  /** O caminho até a tela, em pedaços, sem o "›" (a tela põe o separador). */
  onde: string[]
  /** Tela indicada (chave de §5.4 da 5b) ou null. */
  atalho: ChaveAtalho | (string & {}) | null
  /** 2 a 6 passos curtos. */
  como: string[]
  /** O que a pessoa vê no fim. */
  resultado: string
  /** 1 a 3 referências "topico#secao"; a primeira diz o tópico "dono" da jornada. */
  veja: string[]
  palavras: string[]
}

/** GET /ajuda: o conteúdo inteiro, como está no arquivo da API. */
export interface ConteudoAjuda {
  versao: number
  /** Opcional no formato (conteúdo antigo não tem); depois de `lerConteudo`, sempre uma lista. */
  jornadas?: JornadaAjuda[]
  topicos: TopicoAjuda[]
}

/**
 * Por que a IA sob demanda não está disponível. `cota_esgotada`: nenhuma análise no mês; `cota_insuficiente` (03/10):
 * restam análises, mas menos que o custo do nível da conta (ex.: 1 no Mais detalhado, que gasta 2).
 */
export type MotivoAssistente = 'ia_indisponivel' | 'conta_pausada' | 'cota_esgotada' | 'cota_insuficiente'

/** GET /assistente. */
export interface EstadoAssistente {
  disponivel: boolean
  /** null quando disponível. */
  motivo: MotivoAssistente | (string & {}) | null
  /** null sem IA na plataforma. */
  cota: CotaIa | null
  /** Análises que uma pergunta gasta no nível da conta (1, ou 2 no Mais detalhado); null sem IA na plataforma. */
  custo?: number | null
  /** Até 3 perguntas de exemplo, conforme as permissões (vazio quando não está disponível). */
  sugestoes: string[]
}

export type PapelMensagem = 'usuario' | 'assistente'

/** Item do histórico mandado em cada pergunta (até 8; texto de 1 a 4.000 caracteres). */
export interface MensagemHistorico {
  papel: PapelMensagem
  texto: string
}

export interface AtalhoAssistente {
  chave: ChaveAtalho | (string & {})
  rotulo: string
  caminho: string
}

/** POST /assistente/perguntar (200). */
export interface RespostaAssistente {
  /** Texto puro: quebras de linha e listas com "- ". */
  resposta: string
  /** Até 3 próximas perguntas. */
  sugestoes: string[]
  /** 0 a 2, já filtrados pelas permissões. */
  atalhos: AtalhoAssistente[]
  cota: CotaIa
  /** Análises que esta pergunta gastou (o custo do nível da conta). */
  custo?: number
}

// ───────────────────────── Etapa 5c (docs/api-etapa-5c.md) ─────────────────────────

/** O convite de indicação da tela final e o corpo da indicação pública ficam com os tipos da pesquisa (página leve). */
export type { ConviteIndicacao, DadosIndicacao } from '@/pesquisa/tipos'

export type SituacaoIndicacao = 'nova' | 'em_contato' | 'cliente' | 'nao_avancou'
export type OrigemIndicacao = 'pesquisa' | 'manual'

/** Item de GET /crescimento/indicacoes (mais novas primeiro). */
export interface Indicacao {
  id: Id
  origem: OrigemIndicacao
  nome: string
  empresa: string | null
  /** Só dígitos, com o 55. */
  telefone: string | null
  email: string | null
  observacao: string | null
  indicador: { contato: Referencia | null; empresa: Referencia | null }
  /** Quem indicou deixou dizer à pessoa indicada que foi ele. */
  pode_identificar: boolean
  responsavel: Referencia | null
  situacao: SituacaoIndicacao
  /** Só com 'cliente'. */
  valor_mensal: ValorDecimal | null
  /** Só com 'nao_avancou'. */
  motivo: string | null
  criada_em: string
  atualizada_em: string
}

/** Contagem com os mesmos filtros de período e responsável da lista. */
export interface ResumoIndicacoes {
  novas: number
  em_contato: number
  clientes: number
  nao_avancou: number
  receita_mensal: ValorDecimal | null
}

export interface PaginaIndicacoes extends Pagina<Indicacao> {
  resumo: ResumoIndicacoes
}

export interface FiltrosIndicacoes {
  situacao?: SituacaoIndicacao
  responsavel_id?: Id
  de?: string
  ate?: string
  busca?: string
  pagina?: number
  por_pagina?: number
}

/** POST /crescimento/indicacoes (registro à mão, sem `confirmo`). Opcionais vazios vão como null. */
export interface DadosNovaIndicacao {
  nome: string
  empresa: string | null
  telefone: string | null
  email: string | null
  observacao: string | null
  indicador_contato_id: Id | null
  indicador_empresa_id: Id | null
  responsavel_id: Id | null
}

/** PATCH /crescimento/indicacoes/{id}: 'cliente' pede `valor_mensal` (>= 0); 'nao_avancou' aceita `motivo` (até 300). */
export interface DadosEdicaoIndicacao {
  situacao?: SituacaoIndicacao
  valor_mensal?: number | null
  motivo?: string | null
  responsavel_id?: Id | null
}

export type ListaOportunidade = 'pode_crescer' | 'promotores'
export type ResultadoOferta = 'aceitou' | 'recusou' | 'sem_resposta'
/** WhatsApp quando o contato tem telefone; só e-mail → mailto:. */
export type CanalOferta = 'whatsapp' | 'email'

export interface UltimaOferta {
  id: Id
  criada_em: string
  resultado: ResultadoOferta | null
  /** Só com 'aceitou'. */
  valor: ValorDecimal | null
}

/** Item de GET /crescimento/oportunidades (uma empresa). */
export interface Oportunidade {
  empresa: { id: Id; nome: string; valor_mensal: ValorDecimal | null }
  grupo: Referencia | null
  responsavel: Referencia | null
  nps: { valor: number | null; total: number }
  /** Quem deu a resposta mais recente no período, ativo, fora da lista de descadastro e com telefone ou e-mail. */
  contato: { id: Id; nome: string; telefone: string | null; email: string | null } | null
  ultima_resposta: UltimaResposta | null
  ultima_oferta: UltimaOferta | null
}

export interface FiltrosOportunidades {
  lista?: ListaOportunidade
  grupo_id?: Id
  responsavel_id?: Id
  pagina?: number
}

/** POST /crescimento/ofertas (201) e PATCH /crescimento/ofertas/{id}. */
export interface Oferta extends UltimaOferta {
  empresa: Referencia
  /** null: oferta sem contato, ou o contato foi apagado depois. */
  contato: Referencia | null
  lista: ListaOportunidade
  canal: CanalOferta
  texto: string
  /** Quem registrou (null se o usuário foi apagado). */
  usuario: Referencia | null
  resultado_em: string | null
}

/** 422 quando a empresa saiu das oportunidades (ou o contato saiu da lista) depois que a lista abriu. */
export interface DadosNovaOferta {
  empresa_id: Id
  contato_id: Id | null
  lista: ListaOportunidade
  /** Por onde a oferta saiu (o link que a tela abriu). */
  canal: CanalOferta
  /** Até 2.000 caracteres. */
  texto: string
}

/** Corpo parcial: sem `valor`, a API mantém o que já estava (e os resultados que não são 'aceitou' o limpam). */
export interface DadosResultadoOferta {
  resultado: ResultadoOferta
  /** Só com 'aceitou' (>= 0). */
  valor?: number
}

/** GET /crescimento/resumo (padrão: últimos 90 dias). */
export interface ResumoCrescimento {
  indicacoes: { recebidas: number; clientes: number; taxa: number | null; receita_mensal: ValorDecimal | null }
  ofertas: { feitas: number; aceitas: number; taxa: number | null; receita: ValorDecimal | null }
}

/**
 * GET /crescimento/panorama (docs/api-crescimento-panorama.md): o topo da tela de Crescimento no período (padrão: 90
 * dias). `receita` é a mesma conta da "Receita gerada pelo Toqqi" do Início, com o período anterior de mesmo tamanho.
 */
export interface PanoramaCrescimento {
  periodo: { de: string | null; ate: string | null }
  anterior: { de: string; ate: string } | null
  receita: { total: ValorDecimal; indicacoes: ValorDecimal; ofertas: ValorDecimal; anterior: ValorDecimal | null }
  /**
   * Promotores = respostas de nota máxima (NPS 9–10 ou CSAT 5); abordadas = as que já saíram de "nova";
   * `esperando_contato` = as em "nova" agora, de qualquer data.
   */
  indicacoes: {
    promotores: number
    recebidas: number
    novas: number
    em_contato: number
    clientes: number
    nao_avancou: number
    abordadas: number
    esperando_contato: number
  }
  /** `prontas` = empresas nas listas de Oportunidades agora; `sem_oferta` = delas, sem oferta nos últimos 90 dias. */
  ofertas: { feitas: number; aceitas: number; recusadas: number; sem_resposta: number; aguardando: number; prontas: number; sem_oferta: number }
  /** Quem mais indicou no período (até 5). */
  fas: { empresa: { id: Id; nome: string }; indicacoes: number; clientes: number; receita_mensal: ValorDecimal }[]
  depoimentos: {
    aprovados: number
    pendentes: number
    destaque: { resposta_id: Id; comentario: string; assinatura: string; nota: number | null; tipo_nota: string | null; data_resposta: string | null } | null
  }
  /** A receita nova de cada um dos 12 meses que terminam no mês de hoje ("2026-10"; o mês de hoje, até hoje). */
  meses: { mes: string; indicacoes: ValorDecimal; ofertas: ValorDecimal; total: ValorDecimal }[]
  /** A conta já teve um promotor, uma indicação ou uma oferta, em qualquer data (sem nada, a tela explica como funciona). */
  tem_historico: boolean
}

/** GET/PUT /crescimento/configuracao. Sem linha no banco, a API devolve os padrões. */
export interface ConfigCrescimento {
  indicacoes_ativas: boolean
  /** Até 120. Variáveis: {empresa} e {nome}. */
  titulo_convite: string
  /** Até 500. */
  texto_convite: string
  /** Até 300, opcional. */
  recompensa: string | null
  /** Até 1.000. Variáveis: {nome}, {empresa}, {empresa_cliente} e {representante}. */
  texto_oferta: string
  /** Melhoria 5: pedir ao promotor com comentário para publicar como depoimento. */
  depoimentos_ativos?: boolean
  /** Melhoria 5: link para avaliar a empresa (Google, Reclame Aqui...), só https. */
  link_avaliacao?: string | null
}

/** Melhoria 5: depoimento autorizado pelo cliente (GET /crescimento/depoimentos). */
export type SituacaoDepoimento = 'pendente' | 'aprovado' | 'oculto'
export interface Depoimento {
  resposta_id: Id
  nota: number | null
  tipo_nota: 'nps' | 'csat' | null
  comentario: string
  autorizado_em: string
  situacao: SituacaoDepoimento
  data_resposta: string
  contato: Referencia | null
  empresa: Referencia | null
  /** "Ana, Mercado Azul". */
  assinatura: string
}

// ───────────────────────── Etapa 5d (docs/api-etapa-5d.md) ─────────────────────────

/** Nível do modelo da conta (Configurações › IA). */
export type NivelModeloIa = 'rapido' | 'equilibrado' | 'detalhado'
/** Estilo da escrita da IA (Configurações › IA). */
export type EstiloIa = 'objetiva' | 'equilibrada' | 'criativa'

/** Uma opção de modelo ou de estilo, com os textos da API (GET /conta/ia). */
export interface OpcaoIa {
  valor: string
  rotulo: string
  descricao: string
  /** Só nos níveis de modelo: análises da cota que cada geração ou pergunta gasta nele (1, ou 2 no Mais detalhado). */
  analises?: number
}

/** Situação dos passos sugeridos pela IA numa ação. */
export type SituacaoPassosIa = 'pendente' | 'pronta' | 'falhou' | 'limite'

/**
 * Filtros do resumo do painel e do parecer dos relatórios: os mesmos de GET /painel e os comuns dos relatórios. Sem
 * `de`/`ate` = todo o período; `so_ativos` vazio = true.
 */
export interface FiltrosGeracaoIa {
  de?: string
  ate?: string
  grupo_id?: Id | ''
  so_ativos?: boolean
}

/** Corpo do POST: os quatro filtros, com null no que não foi escolhido. */
export interface CorpoGeracaoIa {
  de: string | null
  ate: string | null
  grupo_id: Id | null
  so_ativos: boolean
}

/** Resumo do painel: uma frase cada (até 300 caracteres). */
export interface ConteudoResumoIa {
  melhorar: string
  funciona: string
  proximo_passo: string
}

/** Parecer dos relatórios: 2 a 3 frases (até 600) e 1 a 3 recomendações para a semana (até 200 cada). */
export interface ConteudoParecerIa {
  resumo: string
  recomendacoes: string[]
}

/** O último resumo (ou parecer) salvo para os mesmos filtros. */
export interface ItemGeracaoIa<C = unknown> {
  conteudo: C
  filtros: Record<string, unknown>
  gerado_em: string
  /** null: o usuário foi removido. */
  gerado_por: Referencia | null
  modelo: NivelModeloIa | (string & {})
  /** "Rápido" | "Equilibrado" | "Mais detalhado". */
  modelo_rotulo: string
  estilo: EstiloIa | (string & {})
}

/** GET /painel/resumo-ia e GET /relatorios/parecer-ia. */
export interface EstadoGeracaoIa<C = unknown> {
  /** Como GET /assistente: false com o motivo. */
  disponivel: boolean
  motivo: MotivoAssistente | (string & {}) | null
  /** null sem IA na plataforma. */
  cota: CotaIa | null
  /** Análises que uma geração gasta no nível da conta (1, ou 2 no Mais detalhado); null sem IA na plataforma. */
  custo?: number | null
  /** O salvo para os mesmos filtros, ou null (vem mesmo com `disponivel: false`). */
  item: ItemGeracaoIa<C> | null
  /** A última geração deste tipo na conta (qualquer filtro) + 30 s, se ainda no futuro; senão null. */
  pode_gerar_em: string | null
}

/**
 * POST /painel/resumo-ia e POST /relatorios/parecer-ia (200). Gasta o custo do nível da conta (1 análise da cota, ou 2 no
 * Mais detalhado; devolvidas se falhar).
 */
export interface ResultadoGeracaoIa<C = unknown> {
  item: ItemGeracaoIa<C>
  cota: CotaIa
  /** Análises que esta geração gastou. */
  custo?: number
  pode_gerar_em: string | null
}

// ───────────────────────── Etapa 5e (docs/api-etapa-5e.md) ─────────────────────────

/** A imagem de topo dos e-mails, como vem em GET /envios/configuracao. Dimensões nulas quando não deu para ler. */
export interface ImagemTopoEmail {
  id: Id
  url: string
  largura: number | null
  altura: number | null
}

/** Item do banco de imagens da conta (GET /imagens e a resposta 201 de POST /imagens). */
export interface ImagemBanco {
  id: Id
  /** URL pública (/publico/imagens/{chave}), sem login. */
  url: string
  /** Nome do arquivo enviado, limpo (até 120); pode faltar. */
  nome: string | null
  /** "image/png" ou "image/jpeg". */
  tipo: string
  /** Em bytes. */
  tamanho: number
  largura: number | null
  altura: number | null
  criada_em: string
  /** É a imagem de topo dos e-mails (a configuração salva): não dá para excluir. */
  em_uso: boolean
}

/** GET /imagens: só as do banco, mais novas primeiro, e o limite da conta (30). */
export interface BancoImagens {
  itens: ImagemBanco[]
  limite: number
}

/** Quem gerou cada e-mail registrado em Auditoria › E-mails enviados (a API manda também o rótulo em português). */
export type TipoEmailEnviado =
  | 'convite'
  | 'lembrete'
  | 'agradecimento'
  | 'retorno'
  | 'teste'
  | 'confirmacao'
  | 'senha'
  | 'boas_vindas'
  | 'alerta_risco'
  | 'resumo_semanal'
  | 'pico'
  | 'indicacao'
  | 'aviso'
  | 'cobranca'
  | 'feedback'
  | (string & {})

/** `enviado`: o provedor aceitou (devoluções da caixa de quem recebe não aparecem); `falhou`: com o erro em texto simples. */
export type SituacaoEmailEnviado = 'enviado' | 'falhou'

export interface EmailEnviado {
  id: Id
  tipo: TipoEmailEnviado
  tipo_rotulo: string
  destinatario: string
  /** Como saiu (cortado em 300). Nada do corpo. */
  assunto: string
  situacao: SituacaoEmailEnviado | (string & {})
  erro: string | null
  criado_em: string
}

/** GET /auditoria/emails: a página e as falhas da conta nos últimos 7 dias (sem os filtros). */
export interface PaginaEmailsEnviados extends Pagina<EmailEnviado> {
  falhas_7_dias: number
}

/** Filtros de GET /auditoria/emails. Sem `de`/`ate`, a API usa os últimos 30 dias (até 90). */
export interface FiltrosEmailsEnviados {
  de?: string
  ate?: string
  situacao?: SituacaoEmailEnviado | ''
  tipo?: TipoEmailEnviado | ''
  busca?: string
  pagina?: number
  por_pagina?: number
}

// ───────────────────────── Etapa 5f (docs/api-etapa-5f.md) ─────────────────────────

/** Opções da Zona de risco, da menor para a maior (cada uma inclui a anterior). */
export type OpcaoZonaRisco = 'respostas' | 'contatos' | 'tudo'

/** O que a opção "Respostas" apaga (respostas NPS e personalizadas) e as ações que perdem o vínculo. */
export interface ContagemZonaRespostas {
  respostas: number
  acoes_sem_vinculo: number
}

/** "Contatos": o de cima + contatos, convites com contato e envios; as CSAT ficam, sem o contato. */
export interface ContagemZonaContatos {
  contatos: number
  respostas: number
  convites: number
  envios: number
  csat_sem_contato: number
}

/** "Recomeçar do zero": o de cima + empresas, ações, indicações e ofertas. */
export interface ContagemZonaTudo extends ContagemZonaContatos {
  empresas: number
  acoes: number
  indicacoes: number
  ofertas: number
}

/** O que fica em qualquer opção. */
export interface MantidosZonaRisco {
  csat: number
  descadastros: number
  usuarios: number
  formularios: number
}

/** GET /conta/zona-de-risco (`zona_risco.usar`, só administrador). */
export interface ZonaRisco {
  opcoes: {
    respostas: ContagemZonaRespostas
    contatos: ContagemZonaContatos
    tudo: ContagemZonaTudo
  }
  mantidos: MantidosZonaRisco
}

/**
 * POST /conta/zona-de-risco (200). `apagados`: as mesmas chaves das contagens da opção no GET (as linhas que o comando
 * apagou ou desligou); `mantidos`: as de `MantidosZonaRisco`.
 */
export interface ResultadoZonaRisco {
  opcao: OpcaoZonaRisco
  apagados: Record<string, number>
  mantidos: Partial<MantidosZonaRisco>
}

/** Item de GET /auditoria/grupos, na ordem da API. */
export interface GrupoAuditoria {
  chave: string
  rotulo: string
}

// ───────────────────────── Etapa 5g (docs/api-etapa-5g.md) ─────────────────────────

/** Os quatro grupos de Plataforma › Parâmetros, na ordem da tela. */
export type GrupoParametros = 'planos' | 'ia' | 'whatsapp' | 'teste'

/** De onde vem o valor em uso: salvo na tela (banco), da variável de ambiente ou do código. */
export type OrigemParametro = 'banco' | 'ambiente' | 'codigo'

/** Valor de um parâmetro: dinheiro em texto ("149.00"), inteiro, null (sem limite) ou texto. */
export type ValorParametro = string | number | null

/** Um grupo de GET /plataforma/parametros (e a resposta do PUT). */
export interface GrupoParametrosPlataforma {
  grupo: GrupoParametros | (string & {})
  rotulo: string
  /** Id da última linha do histórico do grupo (0 sem nenhuma): vai no PUT. */
  versao: number
  alterado_em: string | null
  alterado_por: string | null
  valores: Record<string, ValorParametro>
  padroes: Record<string, ValorParametro>
  origens: Record<string, OrigemParametro | (string & {})>
  /** Só no PUT do grupo `ia`: os níveis cujo modelo foi testado na OpenAI antes de salvar. */
  testados?: string[]
}

export interface ParametrosPlataforma {
  grupos: GrupoParametrosPlataforma[]
}

/** Uma mudança (valores efetivos, antes e depois). */
export interface MudancaParametro {
  chave: string
  de: ValorParametro
  para: ValorParametro
}

export interface ExemploImpactoParametro {
  id: Id
  nome: string
  uso: number
}

/** Contas atingidas por um valor que diminui (ou pelas análises que aumentam); `exemplos`: até 5, de maior uso. */
export interface ImpactoParametro {
  chave: string
  contas: number
  exemplos: ExemploImpactoParametro[]
}

/** POST /plataforma/parametros/{grupo}/previa. */
export interface PreviaParametros {
  mudancas: MudancaParametro[]
  precisa_confirmar: boolean
  impactos: ImpactoParametro[]
}

/** Item de GET /plataforma/parametros/historico (mais novos primeiro). */
export interface ItemHistoricoParametros {
  id: Id
  criado_em: string
  grupo: GrupoParametros | (string & {})
  /** E-mail de quem salvou. */
  por: string
  mudancas: MudancaParametro[]
}

export type PaginaHistoricoParametros = Pagina<ItemHistoricoParametros>

/** Um plano de GET /publico/planos (`preco` no formato de GET /assinatura/planos). */
export interface PlanoPublico {
  chave: ChavePlano | (string & {})
  nome: string
  preco: ValorDecimal
  /** null = sem limite. */
  contatos: number | null
  /** Franquia mensal do WhatsApp automático (5k: null = sem franquia, o padrão). */
  whatsapp: number | null
  /** Cota de IA do plano (perguntas ao ToqqiAI, resumos e pareceres). */
  ia_cota: number
  /** Teto de segurança (comentários lidos pela IA e passos das ações). */
  ia_teto: number
}

/** GET /publico/planos (sem login): os números que o site e as telas públicas mostram. */
export interface PlanosPublicos {
  planos: PlanoPublico[]
  teste: { dias: number; plano: ChavePlano | (string & {}); whatsapp: number | null; ia_teto: number; ia_cota?: number }
  ia_analises: { rapido: number; equilibrado: number; detalhado: number }
  /** Etapa 5k. */
  descontos?: DescontosPlanos
  personalizado?: TabelaPersonalizado & { whatsapp: number | null }
}

// ---- etapa 5i: Relatórios › Desfecho ----------------------------------------------------

export type GrupoAntesDeSair = 'detrator' | 'neutro' | 'promotor' | 'sem_resposta'

export interface BlocoAntesDeSair {
  total: number
  detrator: number
  neutro: number
  promotor: number
  sem_resposta: number
  percentuais: Record<GrupoAntesDeSair, number | null>
}

export interface EmpresaPerdida {
  empresa: Referencia
  perdida_em: string
  motivo: MotivoPerda
  motivo_rotulo: string
  motivo_detalhe: string | null
  valor_mensal: ValorDecimal | null
  responsavel: Referencia | null
  antes: GrupoAntesDeSair
  ultima_nota: { nota: number; data: string } | null
  plano_antes: boolean
}

export interface RelatorioDesfecho {
  periodo: { de: string; ate: string }
  perdidas: { empresas: number; receita_mensal: ValorDecimal; sem_valor: number; itens: EmpresaPerdida[] }
  motivos: { motivo: MotivoPerda; rotulo: string; empresas: number; receita_mensal: ValorDecimal }[]
  antes_de_sair: { perdidas: BlocoAntesDeSair; carteira: BlocoAntesDeSair; amostra_pequena: boolean }
  retencao: {
    inicio: { data: string; empresas: number; receita: ValorDecimal; sem_valor: number }
    perdida: ValorDecimal
    reducao: ValorDecimal
    aumento: ValorDecimal
    fim: ValorDecimal
    novas: { empresas: number; receita: ValorDecimal }
    grr: number | null
    nrr: number | null
    historico_parcial: boolean
  } | null
}

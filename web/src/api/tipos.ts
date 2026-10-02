// Tipos do contrato da API (docs/api-etapa-1.md, -2, -3, -3b, -4a, -4b e -5a).
import type { Contexto, GrupoNota, Pergunta, Tema } from '@/pesquisa/tipos'

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
}

// ───────────────────────── Etapa 2 (docs/api-etapa-2.md) ─────────────────────────

export type {
  CondicaoPergunta,
  Contexto,
  FormatoTexto,
  GrupoNota,
  ModoTema,
  Pergunta,
  Tema,
  TipoPergunta,
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
}

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
  novos: number
  atualizados: number
  ignorados: number
  /** O contrato não fixa: pode vir a lista ou só a quantidade. */
  problemas: ProblemaImportacao[] | number
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
}

export interface Formulario extends FormularioResumo {
  perguntas: Pergunta[]
  tema: Tema
}

export interface DadosFormulario {
  nome?: string
  descricao?: string | null
  perguntas?: Pergunta[]
  tema?: Tema
  ativo?: boolean
  publico?: boolean
}

export interface ModeloFormulario {
  chave: string
  nome: string
  descricao: string
  perguntas: Pergunta[]
  tema: Tema
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
}

export interface ResumoEnvios {
  na_fila: number
  aguardando: number
  responderam: number
  com_erro: number
  saiu_da_lista: number
  lembretes_hoje: number
  enviados_30d: number
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
export type TipoEnvio = 'convite' | 'lembrete' | 'agradecimento'
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

export type EventoWebhook = 'resposta.criada' | 'contato.descadastrado'

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
  limite: number
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
    receita_em_risco: { valor: number | string; empresas: number; sem_valor: number }
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
  palavras: { palavra: string; total: number }[]
  /** Cada passo: feito ou não (o contrato não fixa se vem booleano ou contagem). */
  primeiros_passos: {
    contatos: boolean | number
    envios_ligados: boolean | number
    primeiro_envio: boolean | number
    primeira_resposta: boolean | number
  }
  /** Etapa 4b: temas com pico de reclamações nos últimos 7 dias (sem os filtros da tela). */
  picos?: Pico[]
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
}

export type ChavePlano = 'essencial' | 'profissional' | 'empresa'

export interface PlanoAssinatura {
  chave: ChavePlano | (string & {})
  nome: string
  /** Reais por mês (pode vir como texto decimal, "349.00"). */
  preco: ValorDecimal
  /** Contatos ativos permitidos; null = sem limite. */
  contatos: number | null
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

export interface Assinatura {
  plano: ChavePlano | (string & {})
  valor: ValorDecimal
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
  }
  contatos_ativos: number
  /** O Asaas está configurado na plataforma. */
  disponivel: boolean
  planos: PlanoAssinatura[]
  /** Dos dados da empresa e do e-mail do admin, para preencher o formulário de cobrança. */
  dados_sugeridos: { [K in keyof DadosCobranca]: string | null }
  /** A assinatura ativa (null sem assinatura ou depois de cancelar). */
  assinatura: Assinatura | null
  fatura_aberta: FaturaAberta | null
  /** As 12 mais recentes. */
  cobrancas: CobrancaAssinatura[]
}

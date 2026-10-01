// Tipos do contrato da API (docs/api-etapa-1.md, -2, -3, -3b e -4a).
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
}

export interface Conta {
  id: number | string
  nome: string
  plano: string | null
  situacao: string
  teste_ate: string | null
  /** Logo da empresa (vem de GET /eu); aparece nas pesquisas e nos e-mails quando o formulário não tem logo. */
  logo_url?: string | null
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
  situacao: string
  teste_ate: string | null
  usuarios: number
  criada_em: string
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
  temas: { chave: string; rotulo: string; mencoes: number; nota_media: number | null }[]
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
}

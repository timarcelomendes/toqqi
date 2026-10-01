"""Modelos ORM. O esquema real (incluindo RLS) é criado pelas migrações Alembic."""
import uuid
from datetime import date, datetime, time
from decimal import Decimal

from sqlalchemy import BigInteger, Boolean, Computed, Date, ForeignKey, Integer, Numeric, SmallInteger, Text, Time, text
from sqlalchemy.dialects.postgresql import ARRAY, CITEXT, JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.types import DateTime

TZ = DateTime(timezone=True)
AGORA = text("now()")
CONTA_ATUAL = text("app_conta()")


class Base(DeclarativeBase):
    pass


class Conta(Base):
    __tablename__ = "contas"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    nome: Mapped[str] = mapped_column(Text)
    plano: Mapped[str] = mapped_column(Text, server_default="profissional")
    situacao: Mapped[str] = mapped_column(Text, server_default="teste")
    teste_ate: Mapped[datetime | None] = mapped_column(TZ)
    sessao_minutos: Mapped[int] = mapped_column(Integer, server_default="60")
    termos_aceitos_em: Mapped[datetime | None] = mapped_column(TZ)
    termos_versao: Mapped[str | None] = mapped_column(Text)
    termos_ip: Mapped[str | None] = mapped_column(Text)
    criada_em: Mapped[datetime] = mapped_column(TZ, server_default=AGORA)


class Usuario(Base):
    __tablename__ = "usuarios"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    conta_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("contas.id"), server_default=CONTA_ATUAL)
    nome: Mapped[str] = mapped_column(Text)
    email: Mapped[str] = mapped_column(CITEXT)
    senha_hash: Mapped[str] = mapped_column(Text)
    cargo: Mapped[str | None] = mapped_column(Text)
    telefone: Mapped[str | None] = mapped_column(Text)
    perfil: Mapped[str] = mapped_column(Text)
    situacao: Mapped[str] = mapped_column(Text, server_default="ativo")
    email_confirmado: Mapped[bool] = mapped_column(Boolean, server_default="false")
    ultimo_acesso: Mapped[datetime | None] = mapped_column(TZ)
    criado_em: Mapped[datetime] = mapped_column(TZ, server_default=AGORA)


class Sessao(Base):
    __tablename__ = "sessoes"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    conta_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("contas.id"), server_default=CONTA_ATUAL)
    usuario_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("usuarios.id"))
    criada_em: Mapped[datetime] = mapped_column(TZ, server_default=AGORA)
    ultimo_uso: Mapped[datetime] = mapped_column(TZ, server_default=AGORA)
    expira_em: Mapped[datetime] = mapped_column(TZ)
    ip: Mapped[str | None] = mapped_column(Text)
    agente: Mapped[str | None] = mapped_column(Text)
    revogada_em: Mapped[datetime | None] = mapped_column(TZ)


class TokenUsoUnico(Base):
    __tablename__ = "tokens_uso_unico"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    conta_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("contas.id"), server_default=CONTA_ATUAL)
    usuario_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("usuarios.id"))
    finalidade: Mapped[str] = mapped_column(Text)
    token_hash: Mapped[str] = mapped_column(Text)
    criado_em: Mapped[datetime] = mapped_column(TZ, server_default=AGORA)
    expira_em: Mapped[datetime] = mapped_column(TZ)
    usado_em: Mapped[datetime | None] = mapped_column(TZ)


class PerfilPermissao(Base):
    __tablename__ = "perfil_permissoes"
    conta_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("contas.id"), primary_key=True, server_default=CONTA_ATUAL)
    perfil: Mapped[str] = mapped_column(Text, primary_key=True)
    permissao: Mapped[str] = mapped_column(Text, primary_key=True)


class DominioLiberado(Base):
    __tablename__ = "dominios_liberados"
    conta_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("contas.id"), server_default=CONTA_ATUAL)
    dominio: Mapped[str] = mapped_column(CITEXT, primary_key=True)


class Auditoria(Base):
    __tablename__ = "auditoria"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    conta_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("contas.id"), server_default=CONTA_ATUAL)
    usuario_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("usuarios.id"))
    evento: Mapped[str] = mapped_column(Text)
    gravidade: Mapped[str] = mapped_column(Text)
    detalhe: Mapped[dict] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))
    ip: Mapped[str | None] = mapped_column(Text)
    criado_em: Mapped[datetime] = mapped_column(TZ, server_default=AGORA)


# ---- etapa 2: cadastros, formulários e respostas ------------------------------

class _Auxiliar:
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    conta_id: Mapped[int] = mapped_column(BigInteger, server_default=CONTA_ATUAL)
    nome: Mapped[str] = mapped_column(CITEXT)
    criado_em: Mapped[datetime] = mapped_column(TZ, server_default=AGORA)


class Grupo(_Auxiliar, Base):
    __tablename__ = "grupos"


class Segmento(_Auxiliar, Base):
    __tablename__ = "segmentos"


class PerfilContato(_Auxiliar, Base):
    __tablename__ = "perfis_contato"


class Cargo(_Auxiliar, Base):
    __tablename__ = "cargos"


class Responsavel(Base):
    __tablename__ = "responsaveis"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    conta_id: Mapped[int] = mapped_column(BigInteger, server_default=CONTA_ATUAL)
    nome: Mapped[str] = mapped_column(Text)
    funcao: Mapped[str | None] = mapped_column(Text)
    email: Mapped[str | None] = mapped_column(CITEXT)
    foto_url: Mapped[str | None] = mapped_column(Text)
    teams_webhook: Mapped[str | None] = mapped_column(Text)
    criado_em: Mapped[datetime] = mapped_column(TZ, server_default=AGORA)


class Empresa(Base):
    __tablename__ = "empresas"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    conta_id: Mapped[int] = mapped_column(BigInteger, server_default=CONTA_ATUAL)
    nome: Mapped[str] = mapped_column(CITEXT)
    documento: Mapped[str | None] = mapped_column(Text)
    grupo_id: Mapped[int | None] = mapped_column(BigInteger)
    segmento_id: Mapped[int | None] = mapped_column(BigInteger)
    responsavel_id: Mapped[int | None] = mapped_column(BigInteger)
    valor_mensal: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    cliente_desde: Mapped[date | None] = mapped_column(Date)
    codigo_externo: Mapped[str | None] = mapped_column(Text)
    ativa: Mapped[bool] = mapped_column(Boolean, server_default="true")
    criada_em: Mapped[datetime] = mapped_column(TZ, server_default=AGORA)


class Contato(Base):
    __tablename__ = "contatos"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    conta_id: Mapped[int] = mapped_column(BigInteger, server_default=CONTA_ATUAL)
    codigo: Mapped[str] = mapped_column(Text)
    nome: Mapped[str] = mapped_column(Text)
    email: Mapped[str | None] = mapped_column(CITEXT)
    telefone: Mapped[str | None] = mapped_column(Text)
    empresa_id: Mapped[int | None] = mapped_column(BigInteger)
    cargo_id: Mapped[int | None] = mapped_column(BigInteger)
    perfil_id: Mapped[int | None] = mapped_column(BigInteger)
    codigo_externo: Mapped[str | None] = mapped_column(Text)
    recebe_pesquisas: Mapped[bool] = mapped_column(Boolean, server_default="true")
    ativo: Mapped[bool] = mapped_column(Boolean, server_default="true")
    ultima_nota: Mapped[int | None] = mapped_column(SmallInteger)
    proximo_envio: Mapped[date | None] = mapped_column(Date)
    ultimo_envio: Mapped[datetime | None] = mapped_column(TZ)
    falhas: Mapped[int] = mapped_column(Integer, server_default="0")
    criado_em: Mapped[datetime] = mapped_column(TZ, server_default=AGORA)


class Formulario(Base):
    __tablename__ = "formularios"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    conta_id: Mapped[int] = mapped_column(BigInteger, server_default=CONTA_ATUAL)
    nome: Mapped[str] = mapped_column(Text)
    descricao: Mapped[str] = mapped_column(Text, server_default="")
    perguntas: Mapped[list] = mapped_column(JSONB, server_default=text("'[]'::jsonb"))
    tema: Mapped[dict] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))
    ativo: Mapped[bool] = mapped_column(Boolean, server_default="true")
    publico: Mapped[bool] = mapped_column(Boolean, server_default="true")
    codigo_publico: Mapped[str] = mapped_column(Text)
    padrao_nps: Mapped[bool] = mapped_column(Boolean, server_default="false")
    padrao_csat: Mapped[bool] = mapped_column(Boolean, server_default="false")
    arquivado: Mapped[bool] = mapped_column(Boolean, server_default="false")
    criado_em: Mapped[datetime] = mapped_column(TZ, server_default=AGORA)
    atualizado_em: Mapped[datetime] = mapped_column(TZ, server_default=AGORA)


class Convite(Base):
    __tablename__ = "convites"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    conta_id: Mapped[int] = mapped_column(BigInteger, server_default=CONTA_ATUAL)
    token_hash: Mapped[str] = mapped_column(Text)
    formulario_id: Mapped[int] = mapped_column(BigInteger)
    contato_id: Mapped[int | None] = mapped_column(BigInteger)
    empresa_id: Mapped[int | None] = mapped_column(BigInteger)
    canal: Mapped[str] = mapped_column(Text)
    assunto: Mapped[str | None] = mapped_column(Text)
    referencia: Mapped[str | None] = mapped_column(Text)
    contexto: Mapped[dict] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))
    criado_em: Mapped[datetime] = mapped_column(TZ, server_default=AGORA)
    respondido_em: Mapped[datetime | None] = mapped_column(TZ)
    lembretes_enviados: Mapped[int] = mapped_column(SmallInteger, server_default="0")
    ultimo_lembrete_em: Mapped[datetime | None] = mapped_column(TZ)
    token_semente: Mapped[str | None] = mapped_column(Text)
    evento: Mapped[str | None] = mapped_column(Text)


class Resposta(Base):
    __tablename__ = "respostas"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    conta_id: Mapped[int] = mapped_column(BigInteger, server_default=CONTA_ATUAL)
    formulario_id: Mapped[int] = mapped_column(BigInteger)
    convite_id: Mapped[int | None] = mapped_column(BigInteger)
    contato_id: Mapped[int | None] = mapped_column(BigInteger)
    empresa_id: Mapped[int | None] = mapped_column(BigInteger)
    canal: Mapped[str] = mapped_column(Text)
    nota: Mapped[int | None] = mapped_column(SmallInteger)
    tipo_nota: Mapped[str | None] = mapped_column(Text)
    grupo: Mapped[str | None] = mapped_column(Text)
    comentario: Mapped[str] = mapped_column(Text, server_default="")
    respostas: Mapped[dict] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))
    contexto: Mapped[dict] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))
    referencia: Mapped[str | None] = mapped_column(Text)
    ip_hash: Mapped[str | None] = mapped_column(Text)
    arquivada: Mapped[bool] = mapped_column(Boolean, server_default="false")
    criada_em: Mapped[datetime] = mapped_column(TZ, server_default=AGORA)
    # etapa 4a
    respondida_em: Mapped[datetime | None] = mapped_column(TZ)  # data informada (à mão, importação)
    data_resposta: Mapped[datetime] = mapped_column(TZ, Computed("coalesce(respondida_em, criada_em)", persisted=True))
    origem: Mapped[str] = mapped_column(Text, server_default="pesquisa")
    temas: Mapped[list[str]] = mapped_column(ARRAY(Text), server_default=text("'{}'"))
    temas_manuais: Mapped[bool] = mapped_column(Boolean, server_default="false")
    o_que_faltou: Mapped[str | None] = mapped_column(Text)
    o_que_combinamos: Mapped[str | None] = mapped_column(Text)
    analisada_em: Mapped[datetime | None] = mapped_column(TZ)
    analisada_por: Mapped[int | None] = mapped_column(BigInteger)
    registrada_por: Mapped[int | None] = mapped_column(BigInteger)
    arquivada_em: Mapped[datetime | None] = mapped_column(TZ)
    # só o que o cliente escreveu (painel, palavras, temas); `comentario` segue sendo o resumo da etapa 2
    comentario_cliente: Mapped[str] = mapped_column(Text, server_default="")


class Importacao(Base):
    __tablename__ = "importacoes"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True,
                                          server_default=text("gen_random_uuid()"))
    conta_id: Mapped[int] = mapped_column(BigInteger, server_default=CONTA_ATUAL)
    usuario_id: Mapped[int] = mapped_column(BigInteger)
    arquivo_nome: Mapped[str] = mapped_column(Text)
    dados: Mapped[list] = mapped_column(JSONB)
    colunas: Mapped[list] = mapped_column(JSONB)
    criada_em: Mapped[datetime] = mapped_column(TZ, server_default=AGORA)
    expira_em: Mapped[datetime] = mapped_column(TZ)
    tipo: Mapped[str] = mapped_column(Text, server_default="contatos")  # contatos | respostas


# ---- etapa 3a: envios ---------------------------------------------------------

class ConfigEnvios(Base):
    __tablename__ = "config_envios"
    conta_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, server_default=CONTA_ATUAL)
    envios_ativos: Mapped[bool] = mapped_column(Boolean, server_default="false")
    envio_automatico: Mapped[bool] = mapped_column(Boolean, server_default="false")
    formulario_id: Mapped[int | None] = mapped_column(BigInteger)
    intervalo_dias: Mapped[int] = mapped_column(Integer, server_default="90")
    descanso_dias: Mapped[int] = mapped_column(Integer, server_default="30")
    lembretes: Mapped[int] = mapped_column(Integer, server_default="3")
    dias_lembretes: Mapped[list[int]] = mapped_column(ARRAY(Integer))
    janela_inicio: Mapped[time] = mapped_column(Time)
    janela_fim: Mapped[time] = mapped_column(Time)
    so_dias_uteis: Mapped[bool] = mapped_column(Boolean, server_default="true")
    responder_para: Mapped[str | None] = mapped_column(CITEXT)
    remetente_nome: Mapped[str | None] = mapped_column(Text)
    assunto_convite: Mapped[str] = mapped_column(Text)
    texto_convite: Mapped[str] = mapped_column(Text)
    assunto_lembrete: Mapped[str] = mapped_column(Text)
    texto_lembrete: Mapped[str] = mapped_column(Text)
    texto_whatsapp: Mapped[str] = mapped_column(Text)
    agradecimento_ativo: Mapped[bool] = mapped_column(Boolean, server_default="true")
    agradecimento: Mapped[dict] = mapped_column(JSONB)
    canal: Mapped[str] = mapped_column(Text, server_default="email")
    robo_rodou_em: Mapped[datetime | None] = mapped_column(TZ)
    lembretes_rodou_em: Mapped[date | None] = mapped_column(Date)
    atualizado_em: Mapped[datetime] = mapped_column(TZ, server_default=AGORA)


class Envio(Base):
    __tablename__ = "envios"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    conta_id: Mapped[int] = mapped_column(BigInteger, server_default=CONTA_ATUAL)
    contato_id: Mapped[int | None] = mapped_column(BigInteger)
    convite_id: Mapped[int | None] = mapped_column(BigInteger)
    resposta_id: Mapped[int | None] = mapped_column(BigInteger)
    usuario_id: Mapped[int | None] = mapped_column(BigInteger)
    canal: Mapped[str] = mapped_column(Text)
    tipo: Mapped[str] = mapped_column(Text)
    origem: Mapped[str] = mapped_column(Text)
    situacao: Mapped[str] = mapped_column(Text, server_default="pendente")
    para: Mapped[str] = mapped_column(Text)
    erro: Mapped[str | None] = mapped_column(Text)
    lembrete: Mapped[int | None] = mapped_column(SmallInteger)
    criado_em: Mapped[datetime] = mapped_column(TZ, server_default=AGORA)
    tentativa_em: Mapped[datetime | None] = mapped_column(TZ)
    enviado_em: Mapped[datetime | None] = mapped_column(TZ)
    wamid: Mapped[str | None] = mapped_column(Text)
    cobranca: Mapped[str | None] = mapped_column(Text)


class Descadastro(Base):
    __tablename__ = "descadastros"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    conta_id: Mapped[int] = mapped_column(BigInteger, server_default=CONTA_ATUAL)
    email: Mapped[str | None] = mapped_column(CITEXT)
    telefone: Mapped[str | None] = mapped_column(Text)
    motivo: Mapped[str | None] = mapped_column(Text)
    origem: Mapped[str] = mapped_column(Text)
    usuario_id: Mapped[int | None] = mapped_column(BigInteger)
    criado_em: Mapped[datetime] = mapped_column(TZ, server_default=AGORA)


# ---- etapa 3b: integrações e WhatsApp automático ------------------------------

class IntegracaoChave(Base):
    __tablename__ = "integracao_chaves"
    conta_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, server_default=CONTA_ATUAL)
    hash: Mapped[str] = mapped_column(Text)
    prefixo: Mapped[str] = mapped_column(Text)
    usuario_id: Mapped[int | None] = mapped_column(BigInteger)
    criada_em: Mapped[datetime] = mapped_column(TZ, server_default=AGORA)
    ultimo_uso: Mapped[datetime | None] = mapped_column(TZ)


class Webhook(Base):
    __tablename__ = "webhooks"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    conta_id: Mapped[int] = mapped_column(BigInteger, server_default=CONTA_ATUAL)
    url: Mapped[str] = mapped_column(Text)
    eventos: Mapped[list[str]] = mapped_column(ARRAY(Text))
    ativo: Mapped[bool] = mapped_column(Boolean, server_default="true")
    segredo_cifrado: Mapped[str] = mapped_column(Text)
    segredo_prefixo: Mapped[str] = mapped_column(Text)
    falhas_seguidas: Mapped[int] = mapped_column(Integer, server_default="0")
    ultima_entrega_em: Mapped[datetime | None] = mapped_column(TZ)
    ultimo_status_http: Mapped[int | None] = mapped_column(Integer)
    ultima_ok: Mapped[bool | None] = mapped_column(Boolean)
    criado_em: Mapped[datetime] = mapped_column(TZ, server_default=AGORA)


class WebhookEntrega(Base):
    __tablename__ = "webhook_entregas"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True,
                                          server_default=text("gen_random_uuid()"))
    conta_id: Mapped[int] = mapped_column(BigInteger, server_default=CONTA_ATUAL)
    webhook_id: Mapped[int] = mapped_column(BigInteger)
    evento: Mapped[str] = mapped_column(Text)
    corpo: Mapped[dict] = mapped_column(JSONB)
    status: Mapped[str] = mapped_column(Text, server_default="pendente")
    tentativas: Mapped[int] = mapped_column(SmallInteger, server_default="0")
    proxima_tentativa: Mapped[datetime] = mapped_column(TZ, server_default=AGORA)
    status_http: Mapped[int | None] = mapped_column(Integer)
    erro: Mapped[str | None] = mapped_column(Text)
    criado_em: Mapped[datetime] = mapped_column(TZ, server_default=AGORA)


class WhatsappConta(Base):
    __tablename__ = "whatsapp_contas"
    conta_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, server_default=CONTA_ATUAL)
    phone_number_id: Mapped[str] = mapped_column(Text)
    waba_id: Mapped[str] = mapped_column(Text)
    token_cifrado: Mapped[str] = mapped_column(Text)
    modelo_nome: Mapped[str] = mapped_column(Text)
    modelo_idioma: Mapped[str] = mapped_column(Text)
    modelo_botao: Mapped[int] = mapped_column(SmallInteger, server_default="0")
    ativo: Mapped[bool] = mapped_column(Boolean, server_default="true")
    excedente_ativo: Mapped[bool] = mapped_column(Boolean, server_default="false")
    ultimo_erro: Mapped[str | None] = mapped_column(Text)
    numero_exibicao: Mapped[str | None] = mapped_column(Text)
    nome_verificado: Mapped[str | None] = mapped_column(Text)
    conectado_em: Mapped[datetime] = mapped_column(TZ, server_default=AGORA)


class WhatsappUso(Base):
    __tablename__ = "whatsapp_uso"
    conta_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, server_default=CONTA_ATUAL)
    mes: Mapped[str] = mapped_column(Text, primary_key=True)
    usadas: Mapped[int] = mapped_column(Integer, server_default="0")
    excedentes: Mapped[int] = mapped_column(Integer, server_default="0")
    avisou_80: Mapped[bool] = mapped_column(Boolean, server_default="false")
    avisou_100: Mapped[bool] = mapped_column(Boolean, server_default="false")


class EventoIdempotencia(Base):
    __tablename__ = "eventos_idempotencia"
    conta_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, server_default=CONTA_ATUAL)
    id_evento: Mapped[str] = mapped_column(Text, primary_key=True)
    resposta: Mapped[dict] = mapped_column(JSONB)
    expira: Mapped[datetime] = mapped_column(TZ)


# ---- etapa 4a: planos de ação -------------------------------------------------

class Acao(Base):
    __tablename__ = "acoes"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    conta_id: Mapped[int] = mapped_column(BigInteger, server_default=CONTA_ATUAL)
    resposta_id: Mapped[int | None] = mapped_column(BigInteger)
    empresa_id: Mapped[int | None] = mapped_column(BigInteger)
    contato_id: Mapped[int | None] = mapped_column(BigInteger)
    responsavel_id: Mapped[int | None] = mapped_column(BigInteger)  # responsaveis (carteira), não usuário
    titulo: Mapped[str] = mapped_column(Text)
    descricao: Mapped[str] = mapped_column(Text, server_default="")
    resolucao: Mapped[str | None] = mapped_column(Text)
    prioridade: Mapped[str] = mapped_column(Text)
    prazo: Mapped[date | None] = mapped_column(Date)
    situacao: Mapped[str] = mapped_column(Text, server_default="a_fazer")
    origem: Mapped[str] = mapped_column(Text, server_default="manual")
    grupo: Mapped[str | None] = mapped_column(Text)
    tipo_nota: Mapped[str | None] = mapped_column(Text)
    nota: Mapped[int | None] = mapped_column(SmallInteger)
    criado_por: Mapped[int | None] = mapped_column(BigInteger)
    criada_em: Mapped[datetime] = mapped_column(TZ, server_default=AGORA)
    atualizada_em: Mapped[datetime] = mapped_column(TZ, server_default=AGORA)
    iniciada_em: Mapped[datetime | None] = mapped_column(TZ)
    concluida_em: Mapped[datetime | None] = mapped_column(TZ)
    concluida_por: Mapped[int | None] = mapped_column(BigInteger)


class ConfigAcoes(Base):
    __tablename__ = "config_acoes"
    conta_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, server_default=CONTA_ATUAL)
    prazo_detrator: Mapped[int] = mapped_column(Integer, server_default="2")
    prazo_neutro: Mapped[int] = mapped_column(Integer, server_default="5")
    prazo_promotor: Mapped[int] = mapped_column(Integer, server_default="7")
    acao_promotor: Mapped[bool] = mapped_column(Boolean, server_default="false")
    atualizado_em: Mapped[datetime] = mapped_column(TZ, server_default=AGORA)

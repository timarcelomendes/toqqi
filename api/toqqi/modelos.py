"""Modelos ORM. O esquema real (incluindo RLS) é criado pelas migrações Alembic."""
import uuid
from datetime import date, datetime, time
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Boolean,
    Computed,
    Date,
    ForeignKey,
    Integer,
    LargeBinary,
    Numeric,
    SmallInteger,
    Text,
    Time,
    text,
)
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
    # dados da empresa (Configurações › Empresa); o logo fica em `imagens`
    razao_social: Mapped[str | None] = mapped_column(Text)
    documento: Mapped[str | None] = mapped_column(Text)  # CPF (11 dígitos) ou CNPJ (14, alfanumérico em maiúsculas)
    telefone: Mapped[str | None] = mapped_column(Text)  # só dígitos, com 55
    email_contato: Mapped[str | None] = mapped_column(CITEXT)
    site: Mapped[str | None] = mapped_column(Text)
    cep: Mapped[str | None] = mapped_column(Text)
    logradouro: Mapped[str | None] = mapped_column(Text)
    numero: Mapped[str | None] = mapped_column(Text)
    complemento: Mapped[str | None] = mapped_column(Text)
    bairro: Mapped[str | None] = mapped_column(Text)
    cidade: Mapped[str | None] = mapped_column(Text)
    uf: Mapped[str | None] = mapped_column(Text)
    dados_atualizados_em: Mapped[datetime | None] = mapped_column(TZ)
    # etapa 4b: análise de comentários pela IA (chave da conta, ligada por padrão)
    ia_analise_respostas: Mapped[bool] = mapped_column(Boolean, server_default="true")
    # etapa 5a: cobrança (Asaas). `situacao` é decidida por assinatura.servico.recalcular
    asaas_cliente_id: Mapped[str | None] = mapped_column(Text)  # cliente no Asaas (reaproveitado)
    asaas_ambiente: Mapped[str | None] = mapped_column(Text)  # sandbox | producao (o do cliente acima)
    asaas_conferida_em: Mapped[date | None] = mapped_column(Date)  # última conferência diária (São Paulo)
    pago_ate: Mapped[date | None] = mapped_column(Date)  # último dia coberto por pagamento (inclusivo)
    atrasada_desde: Mapped[date | None] = mapped_column(Date)  # vencimento da fatura em atraso mais antiga
    # cópia do primeiro vencimento da assinatura ativa (null sem assinatura ativa): a regra de "liberada" sai só da
    # linha da conta, lida a cada requisição
    primeiro_vencimento: Mapped[date | None] = mapped_column(Date)


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
    # etapa 4b: e-mails do Toqqi (Minha conta)
    recebe_resumo_semanal: Mapped[bool] = mapped_column(Boolean, server_default="true")
    recebe_alertas: Mapped[bool] = mapped_column(Boolean, server_default="true")


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
    # etapa 4b: análise pela IA (null = não passa pela IA)
    ia_situacao: Mapped[str | None] = mapped_column(Text)  # pendente | analisada | falhou | limite
    ia_temas: Mapped[list | None] = mapped_column(JSONB(none_as_null=True))  # [{tema, sentimento}]
    ia_sentimento: Mapped[str | None] = mapped_column(Text)
    ia_resumo: Mapped[str | None] = mapped_column(Text)
    ia_modelo: Mapped[str | None] = mapped_column(Text)
    ia_em: Mapped[datetime | None] = mapped_column(TZ)
    ia_tentativas: Mapped[int] = mapped_column(SmallInteger, server_default="0")
    ia_reservada_em: Mapped[datetime | None] = mapped_column(TZ)
    ia_texto_hash: Mapped[str | None] = mapped_column(Text)
    # colunas geradas (regra em classe_tema, migração 0007)
    temas_reclamacao: Mapped[list[str]] = mapped_column(
        ARRAY(Text), Computed("temas_reclamacao(temas, ia_temas, ia_situacao, grupo)", persisted=True))
    temas_elogio: Mapped[list[str]] = mapped_column(
        ARRAY(Text), Computed("temas_elogio(temas, ia_temas, ia_situacao, grupo)", persisted=True))


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


class Imagem(Base):
    """Logo da conta ou de um formulário. `dados` só é lido quando pedido (deferred): os bytes não vêm junto nas
    buscas de URL."""
    __tablename__ = "imagens"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    conta_id: Mapped[int] = mapped_column(BigInteger, server_default=CONTA_ATUAL)
    uso: Mapped[str] = mapped_column(Text)  # logo_conta | logo_formulario
    formulario_id: Mapped[int | None] = mapped_column(BigInteger)
    chave: Mapped[str] = mapped_column(Text)
    tipo: Mapped[str] = mapped_column(Text)
    dados: Mapped[bytes] = mapped_column(LargeBinary, deferred=True)
    tamanho: Mapped[int] = mapped_column(Integer)
    sha256: Mapped[str] = mapped_column(Text)
    criada_em: Mapped[datetime] = mapped_column(TZ, server_default=AGORA)


# ---- etapa 4b: IA, picos e resumo semanal ----------------------------------------

class IaUsoMensal(Base):
    __tablename__ = "ia_uso_mensal"
    conta_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, server_default=CONTA_ATUAL)
    mes: Mapped[date] = mapped_column(Date, primary_key=True)  # dia 1 do mês (São Paulo)
    analises: Mapped[int] = mapped_column(Integer, server_default="0")
    tokens_entrada: Mapped[int] = mapped_column(BigInteger, server_default="0")
    tokens_saida: Mapped[int] = mapped_column(BigInteger, server_default="0")
    # etapa 5b: cota de IA do plano (hoje só o assistente gasta), separada do teto da análise por resposta acima
    cota_usada: Mapped[int] = mapped_column(Integer, server_default="0")
    cota_tokens_entrada: Mapped[int] = mapped_column(BigInteger, server_default="0")
    cota_tokens_saida: Mapped[int] = mapped_column(BigInteger, server_default="0")


class AlertaPico(Base):
    __tablename__ = "alertas_pico"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    conta_id: Mapped[int] = mapped_column(BigInteger, server_default=CONTA_ATUAL)
    tema: Mapped[str] = mapped_column(Text)
    reclamacoes: Mapped[int] = mapped_column(Integer)
    media_anterior: Mapped[Decimal] = mapped_column(Numeric(6, 1))
    detectado_em: Mapped[datetime] = mapped_column(TZ, server_default=AGORA)
    enviado_em: Mapped[datetime | None] = mapped_column(TZ)
    destinatarios: Mapped[int] = mapped_column(Integer, server_default="0")


class ResumoSemanal(Base):
    __tablename__ = "resumos_semanais"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    conta_id: Mapped[int] = mapped_column(BigInteger, server_default=CONTA_ATUAL)
    semana: Mapped[date] = mapped_column(Date)  # a segunda-feira da semana resumida
    enviado_em: Mapped[datetime | None] = mapped_column(TZ)
    destinatarios: Mapped[int] = mapped_column(Integer, server_default="0")


# ---- etapa 5a: assinatura e cobrança (Asaas) ----------------------------------------

class Assinatura(Base):
    __tablename__ = "assinaturas"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    conta_id: Mapped[int] = mapped_column(BigInteger, server_default=CONTA_ATUAL)
    asaas_id: Mapped[str] = mapped_column(Text)
    ambiente: Mapped[str] = mapped_column(Text)  # sandbox | producao: o do Asaas em que ela existe
    plano: Mapped[str] = mapped_column(Text)
    valor: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    situacao: Mapped[str] = mapped_column(Text, server_default="ativa")  # ativa | cancelada
    razao_social: Mapped[str] = mapped_column(Text)
    documento: Mapped[str] = mapped_column(Text)  # CPF (11 dígitos) ou CNPJ (14, alfanumérico em maiúsculas)
    email_cobranca: Mapped[str] = mapped_column(CITEXT)
    telefone: Mapped[str] = mapped_column(Text)  # só dígitos, com 55
    primeiro_vencimento: Mapped[date] = mapped_column(Date)
    criada_em: Mapped[datetime] = mapped_column(TZ, server_default=AGORA)
    criada_por: Mapped[int | None] = mapped_column(BigInteger)
    cancelada_em: Mapped[datetime | None] = mapped_column(TZ)
    cancelada_por: Mapped[int | None] = mapped_column(BigInteger)
    nao_encontrada_desde: Mapped[date | None] = mapped_column(Date)  # 1º dia seguido de 404 na conferência


class Cobranca(Base):
    __tablename__ = "cobrancas"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    conta_id: Mapped[int] = mapped_column(BigInteger, server_default=CONTA_ATUAL)
    assinatura_id: Mapped[int | None] = mapped_column(BigInteger)
    asaas_id: Mapped[str] = mapped_column(Text)
    valor: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    valor_liquido: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    vencimento: Mapped[date] = mapped_column(Date)
    situacao: Mapped[str] = mapped_column(Text)  # pendente | paga | vencida | estornada | removida
    situacao_asaas: Mapped[str | None] = mapped_column(Text)
    forma: Mapped[str | None] = mapped_column(Text)  # pix | boleto | cartao
    pago_em: Mapped[datetime | None] = mapped_column(TZ)
    link: Mapped[str | None] = mapped_column(Text)  # fatura do Asaas (Pix, boleto ou cartão)
    criada_em: Mapped[datetime] = mapped_column(TZ, server_default=AGORA)
    atualizada_em: Mapped[datetime] = mapped_column(TZ, server_default=AGORA)


class AsaasEvento(Base):
    """Avisos do webhook do Asaas (tabela da plataforma: só em modo sistema). Só ids e tipo, nunca o corpo."""
    __tablename__ = "asaas_eventos"
    id: Mapped[str] = mapped_column(Text, primary_key=True)  # id do evento ("evt_...")
    tipo: Mapped[str] = mapped_column(Text)
    conta_id: Mapped[int | None] = mapped_column(BigInteger)
    cobranca_asaas_id: Mapped[str | None] = mapped_column(Text)
    assinatura_asaas_id: Mapped[str | None] = mapped_column(Text)
    recebido_em: Mapped[datetime] = mapped_column(TZ, server_default=AGORA)
    processado_em: Mapped[datetime | None] = mapped_column(TZ)
    ignorado: Mapped[bool] = mapped_column(Boolean, server_default="false")
    tentativas: Mapped[int] = mapped_column(SmallInteger, server_default="0")
    erro: Mapped[str | None] = mapped_column(Text)


class AsaasRemocao(Base):
    """Assinatura que precisa ser removida no Asaas e ainda não foi (a tarefa `assinaturas` tenta de novo)."""
    __tablename__ = "asaas_remocoes"
    asaas_id: Mapped[str] = mapped_column(Text, primary_key=True)
    ambiente: Mapped[str] = mapped_column(Text)
    conta_id: Mapped[int | None] = mapped_column(BigInteger, server_default=CONTA_ATUAL)
    motivo: Mapped[str] = mapped_column(Text)
    criada_em: Mapped[datetime] = mapped_column(TZ, server_default=AGORA)
    tentativas: Mapped[int] = mapped_column(SmallInteger, server_default="0")
    erro: Mapped[str | None] = mapped_column(Text)
    removida_em: Mapped[datetime | None] = mapped_column(TZ)

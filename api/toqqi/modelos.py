"""Modelos ORM. O esquema real (incluindo RLS) é criado pelas migrações Alembic."""
import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import BigInteger, Boolean, Date, ForeignKey, Integer, Numeric, SmallInteger, Text, text
from sqlalchemy.dialects.postgresql import CITEXT, JSONB, UUID
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
    conta_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("contas.id"), server_default=CONTA_ATUAL)
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

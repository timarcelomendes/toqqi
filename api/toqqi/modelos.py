"""Modelos ORM. O esquema real (incluindo RLS) é criado pelas migrações Alembic."""
import uuid
from datetime import datetime

from sqlalchemy import BigInteger, Boolean, ForeignKey, Integer, Text, text
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

"""Autenticação por requisição e checagem de permissões.

A cada requisição autenticada, sessão + usuário + conta + permissões são lidos em
UMA consulta, já dentro do contexto RLS da conta indicada no token. Se a sessão for
de outra conta, simplesmente não aparece (RLS) e a resposta é 401.
"""
import uuid
from dataclasses import dataclass, field
from datetime import timedelta

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import func, select, update

from toqqi.apresentacao import conta_json, eh_superadmin, usuario_json
from toqqi.core.db import em_conta
from toqqi.core.errors import AppError
from toqqi.core.permissoes import TODAS, ordenar
from toqqi.core.security import ler_token_acesso
from toqqi.modelos import Conta, PerfilPermissao, Sessao, Usuario

_bearer = HTTPBearer(auto_error=False)


@dataclass
class Contexto:
    usuario_id: int
    conta_id: int
    sessao_id: uuid.UUID
    email: str
    perfil: str
    superadmin: bool
    permissoes: list[str]
    usuario: dict = field(default_factory=dict)
    conta: dict = field(default_factory=dict)


def sessao_invalida(mensagem: str) -> AppError:
    return AppError(401, "sessao_invalida", mensagem)


def contexto_atual(
    request: Request, cred: HTTPAuthorizationCredentials | None = Depends(_bearer)
) -> Contexto:
    if cred is None or cred.scheme.lower() != "bearer":
        raise sessao_invalida("Entre na sua conta para continuar.")
    dados = ler_token_acesso(cred.credentials)
    if dados is None:
        raise sessao_invalida("Sua sessão expirou. Entre novamente.")

    perms_subq = (
        select(func.array_agg(PerfilPermissao.permissao))
        .where(PerfilPermissao.conta_id == Usuario.conta_id, PerfilPermissao.perfil == Usuario.perfil)
        .scalar_subquery()
    )
    with em_conta(dados["conta_id"]) as s:
        linha = s.execute(
            select(Sessao, Usuario, Conta, perms_subq, func.now())
            .join(Usuario, Usuario.id == Sessao.usuario_id)
            .join(Conta, Conta.id == Sessao.conta_id)
            .where(Sessao.id == dados["sessao_id"], Sessao.usuario_id == dados["usuario_id"])
        ).one_or_none()
        if linha is None:
            raise sessao_invalida("Sua sessão foi encerrada. Entre novamente.")
        sessao, usuario, conta, perms, agora = linha
        if sessao.revogada_em is not None:
            raise sessao_invalida("Sua sessão foi encerrada. Entre novamente.")
        if sessao.expira_em <= agora:
            raise sessao_invalida("Sua sessão expirou. Entre novamente.")
        if usuario.situacao != "ativo":
            raise sessao_invalida("Seu acesso foi bloqueado. Fale com o administrador da sua conta.")
        if agora - sessao.ultimo_uso > timedelta(minutes=1):
            s.execute(update(Sessao).where(Sessao.id == sessao.id).values(ultimo_uso=func.now()))

        permissoes = list(TODAS) if usuario.perfil == "admin" else ordenar(perms or [])
        return Contexto(
            usuario_id=usuario.id,
            conta_id=conta.id,
            sessao_id=sessao.id,
            email=usuario.email,
            perfil=usuario.perfil,
            superadmin=eh_superadmin(usuario.email) and bool(usuario.email_confirmado),
            permissoes=permissoes,
            usuario=usuario_json(usuario),
            conta=conta_json(conta),
        )


def requer(*permissoes: str):
    """Dependência: exige usuário autenticado e (opcionalmente) as permissões dadas."""

    def _dep(ctx: Contexto = Depends(contexto_atual)) -> Contexto:
        faltando = [p for p in permissoes if p not in ctx.permissoes]
        if faltando:
            raise AppError(403, "sem_permissao", "Seu perfil não tem permissão para fazer isso.")
        return ctx

    return _dep


def requer_admin(ctx: Contexto = Depends(contexto_atual)) -> Contexto:
    if ctx.perfil != "admin":
        raise AppError(403, "sem_permissao", "Só o administrador da conta pode fazer isso.")
    return ctx


def requer_superadmin(ctx: Contexto = Depends(contexto_atual)) -> Contexto:
    if not ctx.superadmin:
        raise AppError(403, "sem_permissao", "Esta área é exclusiva da equipe Toqqi.")
    return ctx

"""Descadastro (conta + e-mail): token assinado, página pública e tela interna.

O token leva conta_id e e-mail, assinados com HMAC(JWT_SECRET); não expira. A página pública só confia
na conta que vem de um token com assinatura válida e trabalha dentro de em_conta(conta).
"""
import base64
import binascii
import hashlib
import hmac

from sqlalchemy import String, cast, delete, func, or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from toqqi.core.auditoria import registrar
from toqqi.core.config import config
from toqqi.core.db import em_conta
from toqqi.core.deps import Contexto
from toqqi.core.errors import AppError
from toqqi.core.paginacao import Pagina
from toqqi.modelos import Conta, Contato, Descadastro

_MAX_TOKEN = 600


def _b64(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()


def _assinatura(dados: str) -> str:
    mac = hmac.new(config().JWT_SECRET.encode(), f"descadastro|{dados}".encode(), hashlib.sha256).digest()
    return _b64(mac[:18])


def token_descadastro(conta_id: int, email: str) -> str:
    dados = _b64(f"{int(conta_id)}:{email.strip().lower()}".encode())
    return f"{dados}.{_assinatura(dados)}"


def ler_token(token: str) -> tuple[int, str] | None:
    if not token or len(token) > _MAX_TOKEN or token.count(".") != 1:
        return None
    dados, assinatura = token.split(".")
    if not hmac.compare_digest(assinatura.encode(), _assinatura(dados).encode()):
        return None
    try:
        conta, _, email = base64.urlsafe_b64decode(dados + "=" * (-len(dados) % 4)).decode().partition(":")
        return int(conta), email
    except (binascii.Error, UnicodeDecodeError, ValueError):
        return None


def link_descadastro(conta_id: int, email: str) -> str:
    return f"{config().FRONTEND_URL.rstrip('/')}/sair/{token_descadastro(conta_id, email)}"


def link_um_clique(conta_id: int, email: str) -> str:
    return f"{config().API_PUBLIC_URL.rstrip('/')}/api/v1/publico/descadastro/{token_descadastro(conta_id, email)}"


def mascarar(email: str) -> str:
    """ "maria@empresa.com.br" → "ma***@empresa.com.br"."""
    nome, _, dominio = email.partition("@")
    return f"{nome[:2]}***@{dominio}"


def esta_descadastrado(s: Session, email: str | None) -> bool:
    return bool(email) and s.scalar(select(func.count()).select_from(Descadastro)
                                    .where(Descadastro.email == email)) > 0


def gravar(s: Session, email: str, origem: str, motivo: str | None, usuario_id: int | None = None) -> None:
    """Registra (ou mantém) o descadastro e audita sem o e-mail completo."""
    s.execute(insert(Descadastro).values(email=email, origem=origem, motivo=motivo, usuario_id=usuario_id)
              .on_conflict_do_nothing(index_elements=["conta_id", "email"]))
    registrar(s, "descadastro", "atencao", {"email": mascarar(email), "origem": origem, "motivo": motivo},
              usuario_id=usuario_id)


# ---- página pública ---------------------------------------------------------

def link_invalido() -> AppError:
    return AppError(404, "link_invalido", "Este link não é válido ou não está mais disponível.")


def _abrir_token(token: str) -> tuple[int, str]:
    lido = ler_token(token)
    if lido is None:
        raise link_invalido()
    return lido


def _nome_conta(s: Session) -> str:
    nome = s.scalar(select(Conta.nome))
    if nome is None:  # conta excluída
        raise link_invalido()
    return nome


def abrir(token: str) -> dict:
    conta_id, email = _abrir_token(token)
    with em_conta(conta_id) as s:
        return {"email_mascarado": mascarar(email), "empresa": _nome_conta(s),
                "descadastrado": esta_descadastrado(s, email)}


def descadastrar(token: str, motivo: str | None, origem: str) -> dict:
    conta_id, email = _abrir_token(token)
    with em_conta(conta_id) as s:
        _nome_conta(s)
        if not esta_descadastrado(s, email):
            gravar(s, email, origem, motivo)
    return {"descadastrado": True}


def voltar(token: str) -> dict:
    conta_id, email = _abrir_token(token)
    with em_conta(conta_id) as s:
        _nome_conta(s)
        if s.execute(delete(Descadastro).where(Descadastro.email == email)).rowcount:
            registrar(s, "descadastro_desfeito", "info", {"email": mascarar(email)})
    return {"descadastrado": False}


# ---- tela interna -----------------------------------------------------------

def _json(d: Descadastro, contato_id: int | None, contato_nome: str | None) -> dict:
    return {"email": d.email, "contato": {"id": contato_id, "nome": contato_nome} if contato_id else None,
            "motivo": d.motivo, "origem": d.origem, "criado_em": d.criado_em}


def _consulta():
    return select(Descadastro, Contato.id, Contato.nome).outerjoin(Contato, Contato.email == Descadastro.email)


def listar(ctx: Contexto, pg: Pagina, busca: str | None) -> dict:
    filtros = []
    if busca:
        termo = f"%{busca}%"
        filtros.append(or_(cast(Descadastro.email, String).ilike(termo), Contato.nome.ilike(termo)))
    with em_conta(ctx.conta_id) as s:
        total = s.scalar(select(func.count()).select_from(_consulta().where(*filtros).subquery()))
        linhas = s.execute(_consulta().where(*filtros).order_by(Descadastro.criado_em.desc(), Descadastro.id.desc())
                           .limit(pg.por_pagina).offset(pg.offset)).all()
    return pg.resultado([_json(*x) for x in linhas], total)


def adicionar(ctx: Contexto, dados) -> dict:
    with em_conta(ctx.conta_id) as s:
        if not esta_descadastrado(s, dados.email):
            gravar(s, dados.email, "manual", dados.motivo, usuario_id=ctx.usuario_id)
        return _json(*s.execute(_consulta().where(Descadastro.email == dados.email)).one())

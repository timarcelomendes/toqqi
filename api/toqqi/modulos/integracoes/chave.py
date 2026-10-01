"""Chave de integração da conta (ERP, Zapier, Make, n8n).

Formato `tq_live_<40 caracteres url-safe>`. No banco fica só o sha256 (e o prefixo para exibição); a chave
inteira aparece uma vez, ao gerar. Uma chave por conta: gerar outra invalida a anterior na hora.
A conta da chave é descoberta em modo sistema só pelo hash; todo o resto roda em em_conta(conta).
"""
import secrets
from dataclasses import dataclass

from fastapi import Request
from sqlalchemy import delete, select, update
from sqlalchemy.dialects.postgresql import insert

from toqqi.core import relogio
from toqqi.core.auditoria import registrar
from toqqi.core.db import em_conta, modo_sistema
from toqqi.core.deps import Contexto
from toqqi.core.errors import AppError
from toqqi.core.security import hash_token
from toqqi.modelos import Conta, IntegracaoChave

PREFIXO = "tq_live_"
_TAMANHO = len(PREFIXO) + 40


@dataclass
class ContextoIntegracao:
    conta_id: int
    conta_nome: str


def chave_invalida() -> AppError:
    return AppError(401, "chave_invalida", "Chave de integração inválida ou revogada.")


def _prefixo(chave: str) -> str:
    return chave[: len(PREFIXO) + 4] + "…"


def chave_do_pedido(request: Request) -> str | None:
    """`X-Api-Key: <chave>` ou `Authorization: Bearer tq_live_...`."""
    chave = request.headers.get("x-api-key")
    if not chave:
        esquema, _, valor = request.headers.get("authorization", "").partition(" ")
        if esquema.lower() == "bearer" and valor.strip().startswith(PREFIXO):
            chave = valor
    chave = (chave or "").strip()
    return chave if chave.startswith(PREFIXO) and len(chave) == _TAMANHO else None


def limite_por_chave(request: Request) -> str:
    """Chave do limite de chamadas: o hash da chave (nunca a chave em si)."""
    chave = chave_do_pedido(request)
    return f"chave:{hash_token(chave)[:32]}" if chave else f"ip:{request.client.host if request.client else ''}"


def contexto_integracao(request: Request) -> ContextoIntegracao:
    """Dependência das rotas /integracao: a chave age como a conta (sem usuário)."""
    chave = chave_do_pedido(request)
    if chave is None:
        raise chave_invalida()
    with modo_sistema() as s:  # só descobre a conta pelo hash
        conta_id = s.scalar(update(IntegracaoChave).where(IntegracaoChave.hash == hash_token(chave))
                            .values(ultimo_uso=relogio.agora()).returning(IntegracaoChave.conta_id))
    if conta_id is None:
        raise chave_invalida()
    with em_conta(conta_id) as s:
        nome = s.scalar(select(Conta.nome))
    if nome is None:
        raise chave_invalida()
    return ContextoIntegracao(conta_id=conta_id, conta_nome=nome)


# ---- tela de Integrações (perfil admin) ------------------------------------

def ver(ctx: Contexto) -> dict:
    with em_conta(ctx.conta_id) as s:
        c = s.scalar(select(IntegracaoChave))
    if c is None:
        return {"existe": False, "prefixo": None, "criada_em": None, "ultimo_uso": None}
    return {"existe": True, "prefixo": c.prefixo, "criada_em": c.criada_em, "ultimo_uso": c.ultimo_uso}


def gerar(ctx: Contexto) -> dict:
    chave = PREFIXO + secrets.token_urlsafe(30)
    prefixo, agora = _prefixo(chave), relogio.agora()
    valores = {"hash": hash_token(chave), "prefixo": prefixo, "usuario_id": ctx.usuario_id, "criada_em": agora,
               "ultimo_uso": None}
    with em_conta(ctx.conta_id) as s:
        s.execute(insert(IntegracaoChave).values(**valores)
                  .on_conflict_do_update(index_elements=["conta_id"], set_=valores))
        registrar(s, "chave_gerada", "atencao", {"prefixo": prefixo}, usuario_id=ctx.usuario_id)
    return {"chave": chave, "prefixo": prefixo, "criada_em": agora}


def revogar(ctx: Contexto) -> None:
    with em_conta(ctx.conta_id) as s:
        prefixo = s.scalar(delete(IntegracaoChave).returning(IntegracaoChave.prefixo))
        if prefixo is not None:
            registrar(s, "chave_revogada", "atencao", {"prefixo": prefixo}, usuario_id=ctx.usuario_id)

"""Limites por plano. O banco garante o mesmo limite (função limite_contatos + gatilho em contatos)."""
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from toqqi.core.errors import AppError
from toqqi.modelos import Conta, Contato

LIMITE_CONTATOS = {"essencial": 300, "profissional": 1500, "empresa": None}


def limite_contatos(plano: str, situacao: str) -> int | None:
    """Contatos ativos permitidos (None = ilimitado). Em teste vale o plano do teste."""
    if situacao == "cortesia":
        return None
    return LIMITE_CONTATOS.get(plano)


def erro_limite(limite: int) -> AppError:
    return AppError(402, "limite_do_plano", f"Seu plano permite até {limite} contatos ativos.")


def limite_da_conta(s: Session, conta_id: int) -> int | None:
    plano, situacao = s.execute(select(Conta.plano, Conta.situacao).where(Conta.id == conta_id)).one()
    return limite_contatos(plano, situacao)


def contatos_ativos(s: Session) -> int:
    return s.scalar(select(func.count()).select_from(Contato).where(Contato.ativo.is_(True)))

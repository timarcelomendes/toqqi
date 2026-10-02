"""Planos (preço e limite de contatos). O banco garante o mesmo limite (função limite_contatos + gatilho em
contatos)."""
from decimal import Decimal

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from toqqi.core.errors import AppError
from toqqi.modelos import Conta, Contato

# (chave, nome, preço mensal em reais, contatos ativos — None = sem limite), na ordem da tela
PLANOS = (
    ("essencial", "Essencial", Decimal("149.00"), 300),
    ("profissional", "Profissional", Decimal("349.00"), 1500),
    ("empresa", "Empresa", Decimal("799.00"), None),
)
NOMES = {p[0]: p[1] for p in PLANOS}
PRECOS = {p[0]: p[2] for p in PLANOS}
LIMITE_CONTATOS = {p[0]: p[3] for p in PLANOS}
TRAVA_CONTATOS = 740221  # mesma trava consultiva do gatilho contatos_limite_plano (por conta)


def planos_json() -> list[dict]:
    return [{"chave": c, "nome": n, "preco": p, "contatos": lim} for c, n, p, lim in PLANOS]


def limite_contatos(plano: str, situacao: str) -> int | None:
    """Contatos ativos permitidos (None = ilimitado). Em teste vale o plano do teste."""
    if situacao == "cortesia":
        return None
    return LIMITE_CONTATOS.get(plano)


def numero(n: int) -> str:
    """1500 → "1.500"."""
    return f"{n:,}".replace(",", ".")


def erro_limite(limite: int) -> AppError:
    """402 da etapa 2 (mesmo texto do gatilho do banco); `campos.limite` leva o limite para a tela oferecer "Ver
    planos"."""
    return AppError(402, "limite_do_plano", f"Seu plano permite até {limite} contatos ativos.",
                    {"limite": str(limite)})


def limite_da_conta(s: Session, conta_id: int) -> int | None:
    plano, situacao = s.execute(select(Conta.plano, Conta.situacao).where(Conta.id == conta_id)).one()
    return limite_contatos(plano, situacao)


def contatos_ativos(s: Session) -> int:
    return s.scalar(select(func.count()).select_from(Contato).where(Contato.ativo.is_(True)))


def travar_contatos(s: Session, conta_id: int) -> None:
    """Espera as inclusões de contatos em andamento na conta (e segura as novas) até o fim da transação: a contagem
    feita depois não corre com o gatilho do limite."""
    s.execute(text("select pg_advisory_xact_lock(:t, :c)"), {"t": TRAVA_CONTATOS, "c": int(conta_id)})

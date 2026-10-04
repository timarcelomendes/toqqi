"""Planos (chave e nome, na ordem da tela). Preço e limite de contatos são parâmetros da plataforma (etapa 5g,
`core.parametros`: `planos.{plano}.preco` e `planos.{plano}.contatos`): `preco` e `planos_json` leem do cache (até 30 s
em outro processo); o limite de contatos de uma conta é perguntado ao banco (`select limite_contatos(...)`, a mesma
função do gatilho em contatos, que lê a tabela `parametros` na hora)."""
from decimal import Decimal

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from toqqi.core import parametros
from toqqi.core.errors import AppError
from toqqi.modelos import Conta, Contato

PLANOS = (("essencial", "Essencial"), ("profissional", "Profissional"), ("empresa", "Empresa"))
NOMES = dict(PLANOS)
TRAVA_CONTATOS = 740221  # mesma trava consultiva do gatilho contatos_limite_plano (por conta)


def preco(plano: str) -> Decimal:
    """O preço atual do plano (vale para assinaturas novas e trocas de plano)."""
    return parametros.valor(f"planos.{plano}.preco")


def contatos_do_plano(plano: str) -> int | None:
    """O limite de contatos ativos do plano pelo cache (None = sem limite); para uma conta, `limite_da_conta`."""
    return parametros.valor(f"planos.{plano}.contatos")


def planos_json() -> list[dict]:
    """[{chave, nome, preco, contatos}] com o preço e o limite atuais."""
    return [{"chave": c, "nome": n, "preco": preco(c), "contatos": contatos_do_plano(c)} for c, n in PLANOS]


def limite_contatos(s: Session, plano: str, situacao: str) -> int | None:
    """Contatos ativos permitidos (None = ilimitado; cortesia nunca tem limite), pela regra do gatilho do banco."""
    return s.scalar(select(func.limite_contatos(plano, situacao)))


def numero(n: int) -> str:
    """1500 → "1.500"."""
    return f"{n:,}".replace(",", ".")


def erro_limite(limite: int) -> AppError:
    """402 da etapa 2 (mesmo texto do gatilho do banco); `campos.limite` leva o limite para a tela oferecer "Ver
    planos"."""
    return AppError(402, "limite_do_plano", f"Seu plano permite até {limite} contatos ativos.",
                    {"limite": str(limite)})


def limite_da_conta(s: Session, conta_id: int) -> int | None:
    return s.scalar(select(func.limite_contatos(Conta.plano, Conta.situacao)).where(Conta.id == conta_id))


def contatos_ativos(s: Session) -> int:
    return s.scalar(select(func.count()).select_from(Contato).where(Contato.ativo.is_(True)))


def travar_contatos(s: Session, conta_id: int) -> None:
    """Espera as inclusões de contatos em andamento na conta (e segura as novas) até o fim da transação: a contagem
    feita depois não corre com o gatilho do limite."""
    s.execute(text("select pg_advisory_xact_lock(:t, :c)"), {"t": TRAVA_CONTATOS, "c": int(conta_id)})

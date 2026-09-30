"""Acesso ao banco com isolamento por conta garantido pelo RLS do PostgreSQL.

Toda transação da aplicação define, com set_config(..., true) (vale só na transação):
- app.conta_id → a conta em nome da qual a transação age; as políticas RLS só
  mostram/aceitam linhas dessa conta;
- app.sistema = 'on' → modo sistema, usado de propósito e no mínimo possível
  (login por e-mail, tokens de uso único, cadastro, pedido de acesso, plataforma).

Sem nenhum dos dois, o papel da aplicação não enxerga nenhuma linha.
"""
from collections.abc import Iterator
from contextlib import contextmanager
from functools import lru_cache
from pathlib import Path

from sqlalchemy import Engine, create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from toqqi.core.config import config

RAIZ_API = Path(__file__).resolve().parents[2]


@lru_cache
def engine() -> Engine:
    return create_engine(config().DATABASE_URL, pool_pre_ping=True, future=True)


@lru_cache
def _fabrica() -> sessionmaker[Session]:
    return sessionmaker(engine(), expire_on_commit=False, autoflush=True)


@contextmanager
def em_conta(conta_id: int) -> Iterator[Session]:
    """Transação restrita a uma conta. Faz commit ao sair sem erro; rollback em caso de erro."""
    with _fabrica()() as s, s.begin():
        s.execute(text("select set_config('app.conta_id', :c, true)"), {"c": str(int(conta_id))})
        yield s


@contextmanager
def modo_sistema() -> Iterator[Session]:
    """Transação que enxerga todas as contas. Use só onde não existe conta conhecida."""
    with _fabrica()() as s, s.begin():
        s.execute(text("select set_config('app.sistema', 'on', true)"))
        yield s


def migrar() -> None:
    """Aplica as migrações pendentes (alembic upgrade head) com a conexão de migração."""
    from alembic import command
    from alembic.config import Config as AlembicConfig

    cfg = AlembicConfig(str(RAIZ_API / "alembic.ini"))
    cfg.set_main_option("script_location", str(RAIZ_API / "alembic"))
    cfg.attributes["url"] = config().url_migracao
    command.upgrade(cfg, "head")

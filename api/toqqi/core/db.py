"""Acesso ao banco com isolamento por conta garantido pelo RLS do PostgreSQL.

Toda transação da aplicação define, com set_config(..., true) (vale só na transação):
- app.conta_id → a conta em nome da qual a transação age; as políticas RLS só
  mostram/aceitam linhas dessa conta;
- app.sistema = 'on' → modo sistema, usado de propósito e no mínimo possível
  (login por e-mail, tokens de uso único, cadastro, pedido de acesso, plataforma).

Sem nenhum dos dois, o papel da aplicação não enxerga nenhuma linha.

Erros de SQL não levam dados de clientes ao log: o engine esconde os parâmetros (`hide_parameters`) e
`core.log_seguro` troca a mensagem dos erros do banco (que pode trazer valores das linhas) por um resumo sem dados.
"""
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from functools import lru_cache
from pathlib import Path

from sqlalchemy import Engine, create_engine, event, text
from sqlalchemy.orm import Session, sessionmaker

from toqqi.core import log_seguro
from toqqi.core.config import config

log_seguro.instalar()

RAIZ_API = Path(__file__).resolve().parents[2]


_url_app_forcada: str | None = None


def usar_url_app(url: str) -> None:
    """Chamado pela implantação quando o papel restrito não pôde ser criado (volta para o dono)."""
    global _url_app_forcada
    _url_app_forcada = url
    engine.cache_clear()
    _fabrica.cache_clear()


@lru_cache
def engine() -> Engine:
    return create_engine(_url_app_forcada or config().url_app, pool_pre_ping=True, future=True,
                         hide_parameters=True)


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


def sem_jit(s: Session) -> None:
    """Desliga o JIT do PostgreSQL até o fim da transação: nas leituras grandes (painel, listas, CSV) compilar a
    consulta custava mais que executá-la."""
    s.execute(text("SET LOCAL jit = off"))


def travar(s: Session, chave: str) -> None:
    """Trava pelo texto `chave` até o fim da transação (serializa operações concorrentes da mesma chave)."""
    s.execute(text("select pg_advisory_xact_lock(hashtextextended(:k, 0))"), {"k": chave})


def apos_commit(s: Session, fn: Callable[[], None]) -> None:
    """Roda `fn` depois que a transação de `s` for confirmada (não roda se ela for desfeita)."""
    event.listen(s, "after_commit", lambda _s: fn(), once=True)


def migrar() -> None:
    """Aplica as migrações pendentes (alembic upgrade head) com a conexão de migração."""
    from alembic.config import Config as AlembicConfig

    from alembic import command

    cfg = AlembicConfig(str(RAIZ_API / "alembic.ini"))
    cfg.set_main_option("script_location", str(RAIZ_API / "alembic"))
    cfg.attributes["url"] = config().url_migracao
    command.upgrade(cfg, "head")

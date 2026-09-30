"""Testes contra PostgreSQL real (toqqi_test).

- Migrações rodam com o papel dono (TEST_OWNER_DATABASE_URL).
- A aplicação conecta com o papel toqqi_app (sem superusuário e sem BYPASSRLS),
  então as políticas RLS são de fato exercitadas.
"""
import os

OWNER_URL = os.environ.get("TEST_OWNER_DATABASE_URL", "postgresql+psycopg://toqqi:toqqi@localhost:5432/toqqi_test")
APP_URL = os.environ.get("TEST_DATABASE_URL", "postgresql+psycopg://toqqi_app:toqqi_app@localhost:5432/toqqi_test")

os.environ.update({
    "DATABASE_URL": APP_URL,
    "MIGRATION_DATABASE_URL": OWNER_URL,
    "JWT_SECRET": "segredo-de-teste-com-tamanho-suficiente",
    "EMAIL_PROVIDER": "memory",
    "FRONTEND_URL": "http://app.teste",
    "SUPERADMIN_EMAILS": "root@toqqi.com",
    "AUTO_MIGRATE": "0",
    "RATE_LIMIT_ENABLED": "0",
    "ALLOWED_ORIGINS": "http://app.teste",
})

import pytest  # noqa: E402
from alembic import command  # noqa: E402
from alembic.config import Config as AlembicConfig  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine, text  # noqa: E402

from toqqi.core.db import RAIZ_API  # noqa: E402
from toqqi.core.email import caixa_memoria  # noqa: E402
from toqqi.core.rate_limit import limiter  # noqa: E402
from toqqi.main import create_app  # noqa: E402

TABELAS = "auditoria, dominios_liberados, perfil_permissoes, tokens_uso_unico, sessoes, usuarios, contas"


@pytest.fixture(scope="session")
def dono():
    eng = create_engine(OWNER_URL)
    with eng.connect().execution_options(isolation_level="AUTOCOMMIT") as c:
        c.execute(text("DROP SCHEMA IF EXISTS public CASCADE"))
        c.execute(text("CREATE SCHEMA public"))
    cfg = AlembicConfig(str(RAIZ_API / "alembic.ini"))
    cfg.set_main_option("script_location", str(RAIZ_API / "alembic"))
    cfg.attributes["url"] = OWNER_URL
    command.upgrade(cfg, "head")
    yield eng
    eng.dispose()


@pytest.fixture(autouse=True)
def limpar(dono):
    with dono.begin() as c:
        c.execute(text(f"TRUNCATE {TABELAS} RESTART IDENTITY CASCADE"))
    caixa_memoria.clear()
    limiter.reset()
    yield


@pytest.fixture(scope="session")
def app(dono):
    return create_app()


@pytest.fixture
def client(app):
    with TestClient(app) as c:
        yield c


@pytest.fixture
def app_engine():
    eng = create_engine(APP_URL)
    yield eng
    eng.dispose()



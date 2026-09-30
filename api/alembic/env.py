"""Ambiente Alembic: usa MIGRATION_DATABASE_URL (dono das tabelas) ou DATABASE_URL."""
import os

from alembic import context
from sqlalchemy import create_engine, pool


def _url() -> str:
    url = (context.config.attributes.get("url")
           or os.environ.get("MIGRATION_DATABASE_URL")
           or os.environ.get("DATABASE_URL"))
    if url:
        return url
    from toqqi.core.config import config  # lê o .env

    return config().url_migracao


url = _url()


def run_migrations_offline() -> None:
    context.configure(url=url, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    engine = create_engine(url, poolclass=pool.NullPool)
    with engine.connect() as conn:
        context.configure(connection=conn, transaction_per_migration=True)
        with context.begin_transaction():
            context.run_migrations()
    engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

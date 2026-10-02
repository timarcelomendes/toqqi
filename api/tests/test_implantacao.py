"""Subida em produção: papel restrito criado pela própria API e admin inicial."""
from sqlalchemy import create_engine, text

from toqqi.core import config as config_mod
from toqqi.core.config import Config


def test_url_do_render_vira_psycopg():
    c = Config(DATABASE_URL="postgres://dono:x@host:5432/banco", JWT_SECRET="x" * 32)
    assert c.DATABASE_URL.startswith("postgresql+psycopg://dono:x@host")


def test_url_app_usa_o_papel_restrito_com_a_mesma_base():
    c = Config(DATABASE_URL="postgresql://dono:segredo@host:5432/banco", MIGRATION_DATABASE_URL="", JWT_SECRET="x" * 32,
               APP_DB_ROLE="toqqi_app", APP_DB_PASSWORD="S3nh@-app")
    assert c.url_app == "postgresql+psycopg://toqqi_app:S3nh%40-app@host:5432/banco"


def test_admin_inicial_criado_uma_vez_e_entra(client, monkeypatch):
    from toqqi.core import implantacao
    monkeypatch.setenv("ADMIN_INICIAL_EMAIL", "fundador@toqqi.com")
    monkeypatch.setenv("ADMIN_INICIAL_SENHA", "Senha@Forte123")
    config_mod.config.cache_clear()
    try:
        implantacao.garantir_admin_inicial()
        implantacao.garantir_admin_inicial()  # idempotente
        r = client.post("/api/v1/auth/entrar", json={"email": "fundador@toqqi.com", "senha": "Senha@Forte123"})
        assert r.status_code == 200, r.text
        assert r.json()["conta"]["situacao"] == "cortesia"
    finally:
        monkeypatch.delenv("ADMIN_INICIAL_EMAIL")
        monkeypatch.delenv("ADMIN_INICIAL_SENHA")
        config_mod.config.cache_clear()


def test_conta_inicial_so_com_o_banco_vazio(client, dono, monkeypatch, caplog):
    """Trocar ADMIN_INICIAL_EMAIL depois da primeira subida não cria outra conta (as outras saem da Plataforma)."""
    from util import cadastrar, entrar, sql

    from toqqi.core import implantacao
    monkeypatch.setenv("ADMIN_INICIAL_SENHA", "Senha@Forte123")
    monkeypatch.setenv("ADMIN_INICIAL_EMAIL", "fundador@toqqi.com")
    config_mod.config.cache_clear()
    try:
        implantacao.garantir_admin_inicial()
        monkeypatch.setenv("ADMIN_INICIAL_EMAIL", "outro@toqqi.com")
        config_mod.config.cache_clear()
        with caplog.at_level("WARNING", logger="toqqi"):
            implantacao.garantir_admin_inicial()
        assert sql(dono, "select count(*) from contas")[0][0] == 1
        assert entrar(client, "outro@toqqi.com", "Senha@Forte123").status_code == 401
        assert "o banco já tem contas" in caplog.text and "outro@toqqi.com" not in caplog.text  # e-mail mascarado
        assert entrar(client, "fundador@toqqi.com", "Senha@Forte123").status_code == 200

        # banco com uma conta de cadastro (e nenhuma inicial): também não cria
        sql(dono, "truncate contas restart identity cascade")
        cadastrar(client, "ana@alfa.com.br", empresa="Alfa")
        implantacao.garantir_admin_inicial()
        assert sql(dono, "select count(*) from contas")[0][0] == 1
        assert entrar(client, "outro@toqqi.com", "Senha@Forte123").status_code == 401
    finally:
        monkeypatch.delenv("ADMIN_INICIAL_EMAIL")
        monkeypatch.delenv("ADMIN_INICIAL_SENHA")
        config_mod.config.cache_clear()


def test_papel_restrito_criado_sem_privilegios(monkeypatch):
    from toqqi.core import implantacao
    cfg = config_mod.config()
    monkeypatch.setenv("APP_DB_ROLE", "toqqi_app_teste")
    monkeypatch.setenv("APP_DB_PASSWORD", "Outra@Senha123")
    config_mod.config.cache_clear()
    try:
        implantacao.garantir_papel_app()
        eng = create_engine(config_mod.config().url_migracao)
        with eng.connect() as c:
            linha = c.execute(text("select rolsuper, rolbypassrls, rolcanlogin from pg_roles "
                                   "where rolname = 'toqqi_app_teste'")).one()
        eng.dispose()
        assert tuple(linha) == (False, False, True)
    finally:
        for v in ("APP_DB_ROLE", "APP_DB_PASSWORD"):
            monkeypatch.delenv(v)
        config_mod.config.cache_clear()
        from toqqi.core import db
        db.usar_url_app(cfg.url_app)
        db._url_app_forcada = None

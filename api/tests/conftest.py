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
    "IA_PROVEDOR": "memoria",
    "OPENAI_API_KEY": "",
    "ASAAS_API_KEY": "",
    "ASAAS_WEBHOOK_TOKEN": "",
    "ASAAS_URL": "",
})

import pytest  # noqa: E402
from alembic.config import Config as AlembicConfig  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine, text  # noqa: E402

from alembic import command  # noqa: E402
from toqqi.core.db import RAIZ_API  # noqa: E402
from toqqi.core.email import caixa_memoria  # noqa: E402
from toqqi.core.rate_limit import limiter  # noqa: E402
from toqqi.main import create_app  # noqa: E402

TABELAS = ("registros_acesso, emails_enviados, ia_pareceres, aceites_termos, asaas_remocoes, asaas_eventos, cobrancas, assinaturas, ia_uso_mensal, alertas_pico, resumos_semanais, imagens, acoes, config_acoes, envios, descadastros, config_envios, importacoes, respostas, convites, formularios, contatos, empresas, responsaveis, grupos, segmentos, "
           "perfis_contato, cargos, auditoria, dominios_liberados, perfil_permissoes, tokens_uso_unico, sessoes, usuarios, contas")


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




@pytest.fixture(autouse=True)
def sem_rede(monkeypatch):
    """Nada sai para a rede: a Graph API, a OpenAI, o Asaas e os webhooks de saída só respondem pelos dublês dos
    testes."""
    import httpx

    from toqqi.core import asaas, ia, ia_conversa, ia_texto, rede
    from toqqi.modulos.ajuda import servico as ajuda
    from toqqi.modulos.assistente.limite import limite
    from toqqi.modulos.whatsapp import graph

    def recusar(*_a, **_k):
        raise httpx.ConnectError("rede bloqueada nos testes")

    monkeypatch.setattr(graph, "transporte", httpx.MockTransport(recusar))
    monkeypatch.setattr(ia, "transporte", httpx.MockTransport(recusar))  # a conversa do assistente usa o mesmo
    monkeypatch.setattr(asaas, "transporte", httpx.MockTransport(recusar))
    monkeypatch.setattr(rede, "enviar_post", recusar)
    ia.memoria.limpar()  # provedor de IA dos testes (IA_PROVEDOR=memoria): sem chamadas nem falhas programadas
    ia_conversa.memoria.limpar()  # o mesmo para o assistente (sem programa = padrão por palavras)
    ia_texto.memoria.limpar()  # o mesmo para o resumo, o parecer e os passos (sem programa = padrão do formato)
    limite.zerar()  # perguntas por minuto (os ids de usuário recomeçam a cada teste)
    ajuda.limpar_cache()


@pytest.fixture
def meta(monkeypatch):
    """Graph API falsa (WhatsApp) + segredos do app da Meta configurados."""
    import httpx
    from util import APP_SECRET, VERIFY_TOKEN, MetaFalsa

    from toqqi.core.config import config
    from toqqi.modulos.whatsapp import graph

    m = MetaFalsa()
    monkeypatch.setattr(graph, "transporte", httpx.MockTransport(m))
    monkeypatch.setattr(config(), "WHATSAPP_APP_SECRET", APP_SECRET)
    monkeypatch.setattr(config(), "WHATSAPP_VERIFY_TOKEN", VERIFY_TOKEN)
    return m


@pytest.fixture
def destino(monkeypatch):
    """Endereço de webhook falso: o nome resolve para um IP público e o POST fica registrado."""
    from util import DestinoFalso

    from toqqi.core import rede

    d = DestinoFalso()
    monkeypatch.setattr(rede, "resolver", lambda host: ["52.96.1.10"])
    monkeypatch.setattr(rede, "enviar_post", d)
    return d


@pytest.fixture
def asaas_falso(client, monkeypatch):
    """Asaas falso (scripts/asaas_falso.py) atrás do adaptador, com a chave e o token do webhook configurados."""
    import httpx
    from util import CHAVE_ASAAS, TOKEN_WEBHOOK, AsaasFalso

    from toqqi.core import asaas
    from toqqi.core.config import config

    falso = AsaasFalso(client)
    monkeypatch.setattr(asaas, "transporte", httpx.MockTransport(falso))
    monkeypatch.setattr(config(), "ASAAS_API_KEY", CHAVE_ASAAS)
    monkeypatch.setattr(config(), "ASAAS_WEBHOOK_TOKEN", TOKEN_WEBHOOK)
    return falso


@pytest.fixture
def relogio_estavel(monkeypatch):
    """Relógio das regras ao meio-dia de hoje (São Paulo), andando no tempo real: o "hoje" do teste e o da API
    não viram à meia-noite no meio do teste. Devolve a data."""
    import time as _t
    from datetime import datetime, time, timedelta

    from toqqi.core import relogio

    inicio = datetime.combine(datetime.now(relogio.FUSO).date(), time(12), tzinfo=relogio.FUSO)
    t0 = _t.monotonic()
    monkeypatch.setattr(relogio, "agora", lambda: inicio + timedelta(seconds=_t.monotonic() - t0))
    return inicio.date()

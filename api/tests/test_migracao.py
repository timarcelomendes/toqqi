"""Dados iniciais de conta: backfill da migração 0002 e contas novas (cadastro e plataforma)."""
from alembic.config import Config as AlembicConfig
from conftest import OWNER_URL
from util import API, conta_pronta, formularios, sql

from alembic import command
from toqqi.core.db import RAIZ_API


def _alembic() -> AlembicConfig:
    cfg = AlembicConfig(str(RAIZ_API / "alembic.ini"))
    cfg.set_main_option("script_location", str(RAIZ_API / "alembic"))
    cfg.attributes["url"] = OWNER_URL
    return cfg


def test_backfill_de_contas_existentes(client, dono):
    a = conta_pronta(client, "ana@alfa.com.br", empresa="Alfa")
    cfg = _alembic()
    command.downgrade(cfg, "0001_inicial")  # volta ao esquema da etapa 1, com a conta já criada
    try:
        assert sql(dono, "select to_regclass('formularios')")[0][0] is None
        command.upgrade(cfg, "head")
    finally:
        command.upgrade(cfg, "head")
    fs = formularios(client, a["h"])
    assert set(fs) == {"Pesquisa NPS", "Satisfação pós-entrega"}
    assert fs["Pesquisa NPS"]["padrao_nps"] and fs["Satisfação pós-entrega"]["padrao_csat"]
    perfis = client.get(f"{API}/cadastros/perfis", headers=a["h"]).json()
    assert [p["nome"] for p in perfis] == ["Decisor", "Influenciador"]


def test_conta_criada_pela_plataforma_recebe_padroes(client):
    from util import auth, entrar

    root = conta_pronta(client, "root@toqqi.com", empresa="Toqqi")
    r = client.post(f"{API}/plataforma/contas", headers=root["h"], json={
        "empresa": "Gama", "admin_nome": "Gui", "admin_email": "gui@gama.com.br", "admin_senha": "Senha@123"})
    assert r.status_code == 201
    h = auth(entrar(client, "gui@gama.com.br").json()["token"])
    assert set(formularios(client, h)) == {"Pesquisa NPS", "Satisfação pós-entrega"}
    assert len(client.get(f"{API}/cadastros/perfis", headers=h).json()) == 2

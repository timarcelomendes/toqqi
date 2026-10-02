"""Migração 0009 (assistente): colunas da cota do plano em ia_uso_mensal, restrição e descer/subir."""
import pytest
from alembic.config import Config as AlembicConfig
from conftest import OWNER_URL
from sqlalchemy.exc import IntegrityError
from util import conta_pronta, cota_do_mes, perguntar, sql

from alembic import command
from toqqi.core import relogio
from toqqi.core.db import RAIZ_API

COLUNAS = {"cota_usada", "cota_tokens_entrada", "cota_tokens_saida"}
pytestmark = pytest.mark.usefixtures("relogio_estavel")


def _alembic() -> AlembicConfig:
    cfg = AlembicConfig(str(RAIZ_API / "alembic.ini"))
    cfg.set_main_option("script_location", str(RAIZ_API / "alembic"))
    cfg.attributes["url"] = OWNER_URL
    return cfg


def _colunas(dono) -> set[str]:
    return {c for (c,) in sql(dono, "select column_name from information_schema.columns "
                                    "where table_schema = 'public' and table_name = 'ia_uso_mensal'")}


@pytest.fixture
def conta(client):
    return conta_pronta(client, "ana@alfa.com.br", empresa="Alfa")


def test_colunas_padrao_e_restricao(conta, dono):
    c = conta["conta"]["id"]
    mes = relogio.hoje().replace(day=1)
    sql(dono, "insert into ia_uso_mensal (conta_id, mes, analises) values (:c, :m, 3)", c=c, m=mes)
    assert cota_do_mes(dono, c) == (0, 0, 0)
    with pytest.raises(IntegrityError):
        sql(dono, "update ia_uso_mensal set cota_usada = -1 where conta_id = :c", c=c)
    for coluna in COLUNAS:
        with pytest.raises(IntegrityError):  # NOT NULL
            sql(dono, f"update ia_uso_mensal set {coluna} = null where conta_id = :c", c=c)


def test_descer_e_subir_a_0009(client, conta, dono):
    c = conta["conta"]["id"]
    assert perguntar(client, conta["h"]).status_code == 200
    assert cota_do_mes(dono, c)[0] == 1
    sql(dono, "update ia_uso_mensal set analises = 7 where conta_id = :c", c=c)
    cfg = _alembic()
    command.downgrade(cfg, "0008_assinaturas")
    try:
        assert not COLUNAS & _colunas(dono)
        assert sql(dono, "select analises from ia_uso_mensal where conta_id = :c", c=c) == [(7,)]  # o teto fica
    finally:
        command.upgrade(cfg, "head")
    assert COLUNAS <= _colunas(dono)
    assert cota_do_mes(dono, c) == (0, 0, 0)
    # o papel da aplicação continua lendo e gravando a tabela (permissões da tabela inteira)
    assert perguntar(client, conta["h"]).status_code == 200
    assert cota_do_mes(dono, c)[0] == 1

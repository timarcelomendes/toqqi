"""Migração 0017 (erros): a tabela (CHECKs, UNIQUE da impressão, índice, sem FK), RLS forçado com só a política
`sistema`, os privilégios do papel da aplicação (lê, grava, muda e apaga), descer para a 0016 (a tabela sai) e subir de
novo. RLS: em conta, nada aparece e nada grava; em sistema, tudo."""
import pytest
from alembic.config import Config as AlembicConfig
from conftest import OWNER_URL
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, IntegrityError
from util import conta_pronta, sql

from alembic import command
from toqqi.core import erros
from toqqi.core.db import RAIZ_API

IMPRESSAO = "a" * 64


def _alembic() -> AlembicConfig:
    cfg = AlembicConfig(str(RAIZ_API / "alembic.ini"))
    cfg.set_main_option("script_location", str(RAIZ_API / "alembic"))
    cfg.attributes["url"] = OWNER_URL
    return cfg


def _inserir(dono, **campos) -> None:
    valores = {"impressao": IMPRESSAO, "origem": "api", "tipo": "E", "versao": "local", **campos}
    colunas = ", ".join(valores)
    sql(dono, f"insert into erros ({colunas}) values ({', '.join(':' + c for c in valores)})", **valores)


def test_objetos_politica_e_permissoes(dono):
    assert sql(dono, "select to_regclass('erros_ultima_idx')")[0][0] is not None
    assert sql(dono, "select count(*) from pg_constraint where conrelid = 'erros'::regclass and contype = 'f'") == [(0,)]
    assert sql(dono, """
        select c.relrowsecurity, c.relforcerowsecurity, p.polname, p.polcmd
          from pg_class c join pg_policy p on p.polrelid = c.oid where c.relname = 'erros'
    """) == [(True, True, "sistema", "*")]
    privilegios = {p for (p,) in sql(dono, "select privilege_type from information_schema.role_table_grants "
                                           "where table_name = 'erros' and grantee = 'toqqi_app'")}
    assert {"SELECT", "INSERT", "UPDATE", "DELETE"} <= privilegios
    colunas = [c for (c,) in sql(dono, "select column_name from information_schema.columns "
                                       "where table_name = 'erros' order by ordinal_position")]
    assert colunas == ["id", "impressao", "origem", "tipo", "mensagem", "local", "pilha", "versao", "ocorrencias",
                       "primeira_em", "ultima_em", "ultimo_request_id", "conta_id", "resolvido_em"]


@pytest.mark.parametrize("campos", [
    {"impressao": "curta"},
    {"origem": "outra"},
    {"tipo": ""},
    {"tipo": "x" * 81},
    {"mensagem": "m" * 301},
    {"local": "l" * 201},
    {"pilha": "p" * 1001},
    {"versao": ""},
    {"versao": "v" * 41},
    {"ultimo_request_id": "r" * 65},
    {"ocorrencias": 0},
])
def test_checks(dono, campos):
    with pytest.raises(IntegrityError):
        _inserir(dono, **campos)


def test_impressao_unica_e_padroes(dono):
    _inserir(dono)
    with pytest.raises(IntegrityError):
        _inserir(dono, origem="site")
    assert sql(dono, "select mensagem, local, pilha, ocorrencias, primeira_em = ultima_em, resolvido_em, conta_id "
                     "from erros") == [("", "", "", 1, True, None, None)]


def test_rls_em_conta_e_em_sistema(client, dono, app_engine):
    a = conta_pronta(client, "ana@alfa.com.br", empresa="Alfa")
    _inserir(dono, conta_id=a["conta"]["id"])

    def rodar(contexto: str, consulta: str):
        with app_engine.begin() as c:
            if contexto == "conta":
                c.execute(text("select set_config('app.conta_id', :c, true)"), {"c": str(a["conta"]["id"])})
            elif contexto == "sistema":
                c.execute(text("select set_config('app.sistema', 'on', true)"))
            r = c.execute(text(consulta))
            return r.all() if r.returns_rows else r.rowcount

    for contexto in ("nenhum", "conta"):  # nem a conta do erro enxerga
        assert rodar(contexto, "select count(*) from erros") == [(0,)]
        assert rodar(contexto, "update erros set ocorrencias = 2") == 0
        assert rodar(contexto, "delete from erros") == 0
        with pytest.raises(DBAPIError):  # o RLS recusa a linha nova
            rodar(contexto, f"insert into erros (impressao, origem, tipo, versao) values ('{'b' * 64}', 'api', 'E', 'v')")
    assert rodar("sistema", "select count(*) from erros") == [(1,)]
    assert rodar("sistema", "update erros set ocorrencias = 2") == 1
    rodar("sistema", f"insert into erros (impressao, origem, tipo, versao) values ('{'b' * 64}', 'site', 'E', 'v')")
    assert rodar("sistema", "delete from erros") == 2
    # o registro de verdade (papel da aplicação, modo sistema, engine próprio)
    assert erros.registrar("api", "E", "", "GET /x", "")
    assert sql(dono, "select count(*) from erros") == [(1,)]


def test_descer_e_subir(client, dono):
    conta_pronta(client, "ana@alfa.com.br", empresa="Alfa")
    _inserir(dono)
    cfg = _alembic()
    command.downgrade(cfg, "0016_parametros")
    try:
        assert sql(dono, "select to_regclass('erros')") == [(None,)]
        assert sql(dono, "select to_regclass('parametros')")[0][0] is not None  # a 0016 fica
    finally:
        command.upgrade(cfg, "head")
    assert sql(dono, "select count(*) from erros") == [(0,)]  # tabela nova, vazia
    assert erros.registrar("site", "TypeError", "x", "/inicio", "")
    assert sql(dono, "select origem, ocorrencias from erros") == [("site", 1)]

"""Migração 0016 (parâmetros): as duas tabelas (CHECKs, índice, sem FK), RLS forçado com as políticas `sistema` e
`ler_limites`, os privilégios do papel da aplicação (histórico só lê e insere), `limite_contatos` STABLE lendo a tabela,
descer para a 0015 (a função IMMUTABLE volta e as tabelas saem) e subir de novo. RLS: em conta, `parametros` só mostra
as linhas `planos.%.contatos` e nada grava nem muda; o histórico, nada; em sistema, tudo; UPDATE e DELETE no histórico
recusados mesmo em sistema."""
import pytest
from alembic.config import Config as AlembicConfig
from conftest import OWNER_URL
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, IntegrityError, ProgrammingError
from util import conta_pronta, sql

from alembic import command
from toqqi.core.db import RAIZ_API


def _alembic() -> AlembicConfig:
    cfg = AlembicConfig(str(RAIZ_API / "alembic.ini"))
    cfg.set_main_option("script_location", str(RAIZ_API / "alembic"))
    cfg.attributes["url"] = OWNER_URL
    return cfg


def _volatilidade(dono) -> str:
    return sql(dono, "select provolatile from pg_proc where proname = 'limite_contatos'")[0][0]


def _gravar(dono, chave: str, valor: str) -> None:
    sql(dono, "insert into parametros (chave, valor) values (:c, cast(:v as jsonb))", c=chave, v=valor)


def test_objetos_politicas_e_permissoes(dono):
    assert sql(dono, "select to_regclass('parametros_historico_grupo_idx')")[0][0] is not None
    for tabela in ("parametros", "parametros_historico"):
        assert sql(dono, "select count(*) from pg_constraint where conrelid = cast(:t as regclass) and contype = 'f'",
                   t=tabela)[0][0] == 0
    politicas = sql(dono, """
        select c.relname, c.relrowsecurity, c.relforcerowsecurity, p.polname, p.polcmd
          from pg_class c join pg_policy p on p.polrelid = c.oid
         where c.relname in ('parametros', 'parametros_historico') order by 1, 4
    """)
    assert politicas == [("parametros", True, True, "ler_limites", "r"), ("parametros", True, True, "sistema", "*"),
                         ("parametros_historico", True, True, "sistema", "*")]

    def privilegios(tabela):
        return {p for (p,) in sql(dono, "select privilege_type from information_schema.role_table_grants "
                                        "where table_name = :t and grantee = 'toqqi_app'", t=tabela)}

    assert privilegios("parametros") == {"SELECT", "INSERT", "UPDATE", "DELETE"}
    assert privilegios("parametros_historico") == {"SELECT", "INSERT"}
    assert _volatilidade(dono) == "s"  # STABLE (lê a tabela)
    with pytest.raises(IntegrityError):
        _gravar(dono, "outro.grupo", "1")
    with pytest.raises(IntegrityError):
        _gravar(dono, "planos.Essencial.preco", '"149.00"')
    with pytest.raises(IntegrityError):
        sql(dono, "insert into parametros_historico (grupo, por, mudancas) values ('ia', 'x', '{}')")
    with pytest.raises(IntegrityError):
        sql(dono, "insert into parametros_historico (grupo, por, mudancas) values ('outro', 'x', '[]')")


@pytest.mark.parametrize("situacao", ["teste", "ativa", "cancelada", "cortesia"])
def test_limite_contatos_do_banco_igual_ao_padrao(dono, situacao):
    from toqqi.core import parametros

    for plano in parametros.PLANOS:
        esperado = None if situacao == "cortesia" else parametros.padrao(f"planos.{plano}.contatos")
        assert sql(dono, "select limite_contatos(:p, :s)", p=plano, s=situacao) == [(esperado,)]
    _gravar(dono, "planos.essencial.contatos", "2")
    _gravar(dono, "planos.empresa.contatos", "5")
    _gravar(dono, "planos.profissional.contatos", "null")  # JSON null: sem limite
    linhas = [sql(dono, "select limite_contatos(:p, :s)", p=p, s=situacao)[0][0] for p in parametros.PLANOS]
    assert linhas == ([None] * 3 if situacao == "cortesia" else [2, None, 5])


def test_rls_em_conta_e_em_sistema(client, dono, app_engine):
    a = conta_pronta(client, "ana@alfa.com.br", empresa="Alfa")
    _gravar(dono, "planos.essencial.contatos", "2")
    _gravar(dono, "planos.essencial.preco", '"159.00"')
    sql(dono, "insert into parametros_historico (grupo, por, mudancas) values ('planos', 'root@toqqi.com', '[]')")

    def em_conta(consulta: str, **params):
        with app_engine.begin() as c:
            c.execute(text("select set_config('app.conta_id', :c, true)"), {"c": str(a["conta"]["id"])})
            r = c.execute(text(consulta), params)
            return r.all() if r.returns_rows else r.rowcount

    def em_sistema(consulta: str, **params):
        with app_engine.begin() as c:
            c.execute(text("select set_config('app.sistema', 'on', true)"))
            r = c.execute(text(consulta), params)
            return r.all() if r.returns_rows else r.rowcount

    assert em_conta("select chave from parametros") == [("planos.essencial.contatos",)]
    assert em_conta("select limite_contatos('essencial', 'ativa')") == [(2,)]
    assert em_conta("select count(*) from parametros_historico") == [(0,)]
    assert em_conta("update parametros set valor = '3'") == 0
    assert em_conta("delete from parametros") == 0
    with pytest.raises(DBAPIError):  # o RLS recusa a linha nova
        em_conta("insert into parametros (chave, valor) values ('teste.dias', '7')")
    with pytest.raises(DBAPIError):
        em_conta("insert into parametros_historico (grupo, por, mudancas) values ('ia', 'x', '[]')")
    assert sorted(em_sistema("select chave from parametros")) == [("planos.essencial.contatos",),
                                                                  ("planos.essencial.preco",)]
    assert em_sistema("select count(*) from parametros_historico") == [(1,)]
    assert em_sistema("update parametros set valor = valor") == 2
    em_sistema("insert into parametros_historico (grupo, por, mudancas) values ('ia', 'x', '[]')")
    for comando in ("update parametros_historico set por = 'z'", "delete from parametros_historico"):
        with pytest.raises(ProgrammingError):  # sem o privilégio, mesmo em sistema
            em_sistema(comando)
    assert em_sistema("delete from parametros where chave = 'planos.essencial.preco'") == 1


def test_em_conta_so_a_chave_e_o_valor_dos_limites(client, dono, app_engine):
    """A política `ler_limites` deixa a conta ler as linhas dos limites de contatos (o gatilho): a tabela só tem a
    chave e o valor (quem alterou e quando ficam no histórico, que a conta não lê)."""
    a = conta_pronta(client, "ana@alfa.com.br", empresa="Alfa")
    _gravar(dono, "planos.essencial.contatos", "2")
    _gravar(dono, "teste.dias", "7")
    assert sql(dono, "select column_name from information_schema.columns where table_name = 'parametros' "
                     "order by ordinal_position") == [("chave",), ("valor",)]
    with app_engine.begin() as c:
        c.execute(text("select set_config('app.conta_id', :c, true)"), {"c": str(a["conta"]["id"])})
        r = c.execute(text("select * from parametros"))
        assert (list(r.keys()), r.all()) == (["chave", "valor"], [("planos.essencial.contatos", 2)])


def test_descer_e_subir(client, dono):
    conta_pronta(client, "ana@alfa.com.br", empresa="Alfa")
    _gravar(dono, "planos.essencial.contatos", "2")
    cfg = _alembic()
    command.downgrade(cfg, "0015_dados_conta")
    try:
        assert sql(dono, "select to_regclass('parametros'), to_regclass('parametros_historico')") == [(None, None)]
        assert _volatilidade(dono) == "i"  # IMMUTABLE de novo
        assert sql(dono, "select limite_contatos('essencial', 'ativa')") == [(300,)]
    finally:
        command.upgrade(cfg, "head")
    assert _volatilidade(dono) == "s"
    assert sql(dono, "select limite_contatos('essencial', 'ativa')") == [(300,)]  # tabela nova, vazia

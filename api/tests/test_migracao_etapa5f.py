"""Migração 0015 (dados da conta): `registros_acesso` (sem FK, CHECK dos eventos, RLS forçado com as três políticas e
sem UPDATE para o papel da aplicação), as colunas do aviso de exclusão em `contas` (os dois nulos ou os dois
preenchidos), os índices parciais da zona de risco, descer para a 0014 (tudo desfeito) e subir de novo."""
import pytest
from alembic.config import Config as AlembicConfig
from conftest import OWNER_URL
from sqlalchemy.exc import IntegrityError
from util import API, conta_pronta, entrar, sql

from alembic import command
from toqqi.core.acessos import EVENTOS
from toqqi.core.db import RAIZ_API

INDICES = ("envios_resposta_idx", "indicacoes_resposta_idx", "indicacoes_indicador_contato_idx",
           "indicacoes_indicador_empresa_idx", "ofertas_contato_idx", "convites_empresa_idx",
           "registros_acesso_criado_idx")


def _alembic() -> AlembicConfig:
    cfg = AlembicConfig(str(RAIZ_API / "alembic.ini"))
    cfg.set_main_option("script_location", str(RAIZ_API / "alembic"))
    cfg.attributes["url"] = OWNER_URL
    return cfg


def _objeto(dono, nome: str):
    return sql(dono, "select to_regclass(:n)", n=nome)[0][0]


def _colunas(dono, tabela: str) -> set[str]:
    return {c for (c,) in sql(dono, "select column_name from information_schema.columns "
                                    "where table_schema = 'public' and table_name = :t", t=tabela)}


def test_objetos_politicas_e_permissoes(dono):
    for nome in INDICES:
        assert _objeto(dono, nome) is not None, nome
    assert sql(dono, "select indexdef from pg_indexes where indexname = 'convites_empresa_idx'")[0][0].endswith(
        "WHERE (empresa_id IS NOT NULL)")
    assert sql(dono, "select count(*) from pg_constraint where conrelid = 'registros_acesso'::regclass "
                     "and contype = 'f'")[0][0] == 0  # sem FK
    linhas = sql(dono, """
        select c.relrowsecurity, c.relforcerowsecurity, p.polname, p.polcmd
          from pg_class c join pg_policy p on p.polrelid = c.oid where c.relname = 'registros_acesso' order by 3
    """)
    assert linhas == [(True, True, "apagar", "d"), (True, True, "gravar", "a"), (True, True, "ler", "r")]
    privilegios = {p for (p,) in sql(dono, "select privilege_type from information_schema.role_table_grants "
                                           "where table_name = 'registros_acesso' and grantee = 'toqqi_app'")}
    assert privilegios == {"SELECT", "INSERT", "DELETE"}
    definicao = sql(dono, "select pg_get_constraintdef(oid) from pg_constraint where conrelid = "
                          "'registros_acesso'::regclass and contype = 'c' and conname like '%evento%'")[0][0]
    assert all(f"'{e}'" in definicao for e in EVENTOS)
    with pytest.raises(IntegrityError):
        sql(dono, "insert into registros_acesso (evento) values ('pagina')")
    with pytest.raises(IntegrityError):
        sql(dono, "insert into registros_acesso (evento, ip) values ('login', repeat('1', 65))")


def test_aviso_de_exclusao_os_dois_ou_nenhum(client, dono):
    a = conta_pronta(client, "ana@alfa.com.br", empresa="Alfa")
    assert sql(dono, "select exclusao_avisada_para, exclusao_avisada_em from contas") == [(None, None)]
    with pytest.raises(IntegrityError):
        sql(dono, "update contas set exclusao_avisada_para = current_date where id = :c", c=a["conta"]["id"])
    with pytest.raises(IntegrityError):
        sql(dono, "update contas set exclusao_avisada_em = now() where id = :c", c=a["conta"]["id"])
    sql(dono, "update contas set exclusao_avisada_para = current_date, exclusao_avisada_em = now() where id = :c",
        c=a["conta"]["id"])


def test_descer_e_subir(client, dono):
    conta_pronta(client, "ana@alfa.com.br", empresa="Alfa")
    cfg = _alembic()
    command.downgrade(cfg, "0014_emails")
    try:
        assert _objeto(dono, "registros_acesso") is None
        for nome in INDICES:
            assert _objeto(dono, nome) is None, nome
        assert not {"exclusao_avisada_para", "exclusao_avisada_em"} & _colunas(dono, "contas")
    finally:
        command.upgrade(cfg, "head")
    assert {"exclusao_avisada_para", "exclusao_avisada_em"} <= _colunas(dono, "contas")
    # a aplicação volta a gravar os registros (permissões do papel da aplicação na tabela nova)
    assert entrar(client, "ana@alfa.com.br").status_code == 200
    assert sql(dono, "select evento from registros_acesso") == [("login",)]
    assert client.get(f"{API}/auditoria/grupos").status_code == 401

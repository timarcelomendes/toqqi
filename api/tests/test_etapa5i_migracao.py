"""Migração 0018 (desfecho, saúde e origem): colunas e CHECKs novos, `empresa_historico` (RLS forçado, privilégios do
papel da aplicação), o gatilho do histórico (entrada, valor, perda com data passada, edição da perda, retorno, entrada
da pausada antiga, origem, usuário e dia pelos GUCs), o gatilho do contato em empresa perdida (TQ409 → 409), o CHECK
dos eventos de webhook, a semente só das ativas e descer e subir de novo."""
from datetime import date

import pytest
from alembic.config import Config as AlembicConfig
from conftest import OWNER_URL
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, IntegrityError
from util import API, conta_pronta, criar_contato, criar_empresa, sql

from alembic import command
from toqqi.core.db import RAIZ_API

ANTERIOR = "0017_erros"


def _alembic() -> AlembicConfig:
    cfg = AlembicConfig(str(RAIZ_API / "alembic.ini"))
    cfg.set_main_option("script_location", str(RAIZ_API / "alembic"))
    cfg.attributes["url"] = OWNER_URL
    return cfg


def _em_conta(app_engine, conta_id: int, consulta: str, gucs: dict | None = None, **params):
    """Roda como o papel da aplicação, na conta, com os GUCs dados (`app.hoje`, `app.empresa_origem`...)."""
    with app_engine.begin() as c:
        c.execute(text("select set_config('app.conta_id', :c, true)"), {"c": str(conta_id)})
        for nome, valor in (gucs or {}).items():
            c.execute(text("select set_config(:n, :v, true)"), {"n": nome, "v": str(valor)})
        r = c.execute(text(consulta), params)
        return r.all() if r.returns_rows else r.rowcount


def _historico(dono, empresa_id: int) -> list[tuple]:
    return sql(dono, """
        select tipo, data, valor_antes, valor_depois, motivo, motivo_detalhe, contatos, origem, usuario_id
          from empresa_historico where empresa_id = :e order by data, id
    """, e=empresa_id)


def _empresa_sql(dono, conta_id: int, nome: str = "Alfa Ltda", **campos) -> int:
    valores = {"conta_id": conta_id, "nome": nome, **campos}
    colunas = ", ".join(valores)
    return sql(dono, f"insert into empresas ({colunas}) values ({', '.join(':' + c for c in valores)}) returning id",
               **valores)[0][0]


@pytest.fixture
def conta(client):
    return conta_pronta(client, "ana@alfa.com.br", empresa="Alfa")


def test_objetos_politica_e_permissoes(dono):
    for indice in ("empresas_renovacao_idx", "empresas_perdidas_idx", "empresa_historico_empresa_idx",
                   "empresa_historico_perdas_idx", "empresa_historico_usuario_idx", "convites_empresa_recentes_idx",
                   "convites_empresa_idx"):
        assert sql(dono, "select to_regclass(:i)", i=indice)[0][0] is not None, indice
    assert sql(dono, """
        select c.relrowsecurity, c.relforcerowsecurity, p.polname, p.polcmd
          from pg_class c join pg_policy p on p.polrelid = c.oid where c.relname = 'empresa_historico'
    """) == [(True, True, "isolamento_conta", "*")]
    privilegios = {p for (p,) in sql(dono, "select privilege_type from information_schema.role_table_grants "
                                           "where table_name = 'empresa_historico' and grantee = 'toqqi_app'")}
    assert {"SELECT", "INSERT", "UPDATE"} <= privilegios
    assert not privilegios & {"DELETE", "TRUNCATE"}
    gatilhos = {t for (t,) in sql(dono, "select tgname from pg_trigger where not tgisinternal "
                                        "and tgrelid in ('empresas'::regclass, 'contatos'::regclass)")}
    assert {"empresas_historico", "contatos_empresa_perdida", "contatos_limite_plano"} <= gatilhos
    assert sql(dono, "select column_default, is_nullable from information_schema.columns "
                     "where table_name = 'config_envios' and column_name = 'ocultar_mencao_toqqi'") == [("false", "NO")]


@pytest.mark.parametrize("campos", [
    {"perdida_em": date(2026, 9, 1)},  # sem motivo
    {"perdida_em": date(2026, 9, 1), "motivo_perda": "preco", "ativa": True},  # perdida ativa
    {"motivo_perda": "preco", "ativa": False},  # motivo sem perda
    {"motivo_detalhe": "x", "ativa": False},  # detalhe sem perda
    {"perdida_em": date(2026, 9, 1), "motivo_perda": "outro motivo", "ativa": False},
    {"perdida_em": date(2026, 9, 1), "motivo_perda": "outro", "motivo_detalhe": "d" * 301, "ativa": False},
])
def test_checks_da_perda(dono, conta, campos):
    with pytest.raises(IntegrityError):
        _empresa_sql(dono, conta["conta"]["id"], **campos)


def test_perdida_valida_e_renovacao(dono, conta):
    e = _empresa_sql(dono, conta["conta"]["id"], perdida_em=date(2026, 9, 1), motivo_perda="outro",
                     motivo_detalhe="d" * 300, ativa=False, renovacao_em=date(2020, 1, 1))
    assert sql(dono, "select ativa, renovacao_em from empresas where id = :e", e=e) == [(False, date(2020, 1, 1))]


@pytest.mark.parametrize("origem", [
    "{}", "[]", '"google"', '{"utm_source": "Google"}', '{"utm_source": "a b"}', '{"utm_source": ""}',
    '{"utm_source": "' + "a" * 61 + '"}', '{"utm_source": 1}', '{"utm_term": "x"}', '{"email": "a@b.com"}',
    '{"utm_source": "x", "gclid": "y"}', '{"utm_source": "x\\n"}',
])
def test_check_origem_recusa(dono, conta, origem):
    with pytest.raises(IntegrityError):
        sql(dono, "update contas set origem = cast(:o as jsonb) where id = :c", o=origem, c=conta["conta"]["id"])


@pytest.mark.parametrize("origem", [
    '{"utm_source": "newsletter"}',
    '{"utm_source": "mencao", "utm_medium": "email", "utm_campaign": "pesquisa_2026.10-a"}',
    '{"utm_campaign": "' + "a" * 60 + '"}',
])
def test_check_origem_aceita(dono, conta, origem):
    sql(dono, "update contas set origem = cast(:o as jsonb) where id = :c", o=origem, c=conta["conta"]["id"])
    sql(dono, "update contas set origem = null where id = :c", c=conta["conta"]["id"])


@pytest.mark.parametrize("linha", [
    {"tipo": "outro"},
    {"tipo": "perdida"},  # perdida sem motivo
    {"tipo": "entrada", "motivo": "preco"},  # motivo fora da perdida
    {"tipo": "perdida", "motivo": "nenhum"},
    {"tipo": "entrada", "contatos": [1]},  # contatos fora da perdida
    {"tipo": "valor", "valor_antes": 10, "valor_depois": 10},
    {"tipo": "valor"},  # nulo → nulo também não é mudança
    {"tipo": "entrada", "origem": "planilha"},
    {"tipo": "perdida", "motivo": "preco", "motivo_detalhe": "d" * 301},
])
def test_checks_do_historico(dono, conta, linha):
    e = _empresa_sql(dono, conta["conta"]["id"])
    valores = {"conta_id": conta["conta"]["id"], "empresa_id": e, "data": date(2026, 1, 1), "origem": "sistema",
               **linha}
    colunas = ", ".join(valores)
    with pytest.raises(IntegrityError):
        sql(dono, f"insert into empresa_historico ({colunas}) values ({', '.join(':' + c for c in valores)})",
            **valores)


def test_rls_do_historico(client, conta, app_engine):
    b = conta_pronta(client, "bia@beta.com.br", empresa="Beta")
    criar_empresa(client, conta["h"], "Cliente da Alfa")
    criar_empresa(client, b["h"], "Cliente da Beta")
    ida, idb = conta["conta"]["id"], b["conta"]["id"]
    assert _em_conta(app_engine, ida, "select count(*) from empresa_historico") == [(1,)]
    assert _em_conta(app_engine, ida, "select count(*) from empresa_historico where conta_id = :b", b=idb) == [(0,)]
    assert _em_conta(app_engine, ida, "update empresa_historico set data = '2020-01-01' where conta_id = :b",
                     b=idb) == 0
    with app_engine.begin() as c:  # sem conta nem sistema: nada
        assert c.execute(text("select count(*) from empresa_historico")).scalar() == 0
    with pytest.raises(DBAPIError):  # sem DELETE
        _em_conta(app_engine, ida, "delete from empresa_historico")


def test_gatilho_entrada_valor_perda_edicao_e_retorno(dono, conta, client, app_engine):
    cid, uid = conta["conta"]["id"], conta["usuario"]["id"]
    tela = {"app.empresa_origem": "tela", "app.usuario_id": uid}
    e = _em_conta(app_engine, cid, "insert into empresas (nome, valor_mensal) values ('Cliente', 100) returning id",
                  {**tela, "app.hoje": "2026-03-10"})[0][0]
    assert _historico(dono, e) == [("entrada", date(2026, 3, 10), None, 100, None, None, None, "tela", uid)]

    # mudar outra coluna, ou o valor para o mesmo, não grava nada
    _em_conta(app_engine, cid, "update empresas set nome = 'Cliente SA', valor_mensal = 100, ativa = false "
                               "where id = :e", tela, e=e)
    _em_conta(app_engine, cid, "update empresas set ativa = true where id = :e", tela, e=e)
    assert len(_historico(dono, e)) == 1

    # valor, pela importação e sem usuário
    _em_conta(app_engine, cid, "update empresas set valor_mensal = 150 where id = :e",
              {"app.empresa_origem": "importacao", "app.hoje": "2026-04-01"}, e=e)
    # perdida com data passada, com os contatos desativados
    _em_conta(app_engine, cid, "update empresas set ativa = false, perdida_em = '2026-03-31', motivo_perda = "
                               "'preco', motivo_detalhe = 'achou mais barato' where id = :e",
              {**tela, "app.hoje": "2026-04-05", "app.contatos_desativados": "7,8"}, e=e)
    # mudar o valor enquanto perdida não grava `valor`
    _em_conta(app_engine, cid, "update empresas set valor_mensal = 160 where id = :e", tela, e=e)
    # edição da perda: atualiza a linha
    _em_conta(app_engine, cid, "update empresas set perdida_em = '2026-03-20', motivo_perda = 'concorrente', "
                               "motivo_detalhe = null where id = :e", {"app.empresa_origem": "api"}, e=e)
    # reativada com valor novo, sem linha `valor`
    _em_conta(app_engine, cid, "update empresas set ativa = true, perdida_em = null, motivo_perda = null, "
                               "valor_mensal = 200 where id = :e", {**tela, "app.hoje": "2026-06-01"}, e=e)

    assert _historico(dono, e) == [
        ("entrada", date(2026, 3, 10), None, 100, None, None, None, "tela", uid),
        ("perdida", date(2026, 3, 20), 150, None, "concorrente", None, [7, 8], "tela", uid),
        ("valor", date(2026, 4, 1), 100, 150, None, None, None, "importacao", None),
        ("reativada", date(2026, 6, 1), 160, 200, None, None, None, "tela", uid),
    ]

    # sem GUCs: origem sistema, sem usuário, o dia do banco em São Paulo
    sql(dono, "update empresas set valor_mensal = null where id = :e", e=e)
    hoje = sql(dono, "select (now() at time zone 'America/Sao_Paulo')::date")[0][0]
    assert _historico(dono, e)[-1] == ("valor", hoje, 200, None, None, None, None, "sistema", None)


def test_gatilho_usuario_de_outra_conta_fica_nulo(dono, client, conta, app_engine):
    b = conta_pronta(client, "bia@beta.com.br", empresa="Beta")
    e = _em_conta(app_engine, conta["conta"]["id"], "insert into empresas (nome) values ('X') returning id",
                  {"app.usuario_id": b["usuario"]["id"], "app.empresa_origem": "tela"})[0][0]
    assert _historico(dono, e)[0][-2:] == ("tela", None)


def test_gatilho_nasce_perdida(dono, conta, app_engine):
    e = _em_conta(app_engine, conta["conta"]["id"],
                  "insert into empresas (nome, valor_mensal, ativa, perdida_em, motivo_perda) "
                  "values ('Y', 80, false, '2026-02-01', 'encerrou') returning id",
                  {"app.empresa_origem": "api", "app.hoje": "2026-05-01"})[0][0]
    assert _historico(dono, e) == [
        ("entrada", date(2026, 2, 1), None, 80, None, None, None, "api", None),
        ("perdida", date(2026, 2, 1), 80, None, "encerrou", None, [], "api", None),
    ]


def test_gatilho_pausada_antiga_ganha_entrada(dono, conta, app_engine):
    cid = conta["conta"]["id"]
    e = _empresa_sql(dono, cid, valor_mensal=90, ativa=False)
    sql(dono, "delete from empresa_historico where empresa_id = :e", e=e)  # como as pausadas de antes da 0018
    _em_conta(app_engine, cid, "update empresas set perdida_em = '2026-01-15', motivo_perda = 'produto' "
                               "where id = :e", {"app.hoje": "2026-03-01"}, e=e)
    assert [h[:4] for h in _historico(dono, e)] == [
        ("entrada", date(2026, 1, 15), None, 90),
        ("perdida", date(2026, 1, 15), 90, None),
    ]
    f = _empresa_sql(dono, cid, "Outra", valor_mensal=50, ativa=False)
    sql(dono, "delete from empresa_historico where empresa_id = :e", e=f)
    _em_conta(app_engine, cid, "update empresas set valor_mensal = 70 where id = :e", {"app.hoje": "2026-03-01"},
              e=f)
    assert [h[:4] for h in _historico(dono, f)] == [
        ("entrada", date(2026, 3, 1), None, 50),
        ("valor", date(2026, 3, 1), 50, 70),
    ]


def test_contato_ativo_em_empresa_perdida_409(client, dono, conta):
    h = conta["h"]
    emp = criar_empresa(client, h, "Perdida SA")
    outra = criar_empresa(client, h, "Ativa SA")
    ct = criar_contato(client, h, empresa_id=emp["id"])
    sql(dono, "update contatos set ativo = false where id = :c", c=ct["id"])
    sql(dono, "update empresas set ativa = false, perdida_em = '2026-09-01', motivo_perda = 'preco' where id = :e",
        e=emp["id"])

    r = client.patch(f"{API}/contatos/{ct['id']}", headers=h, json={"ativo": True})
    assert r.status_code == 409, r.text
    assert r.json()["erro"]["codigo"] == "empresa_perdida"
    assert "Voltou a ser cliente" in r.json()["erro"]["mensagem"]
    r = client.post(f"{API}/contatos", headers=h, json={"nome": "Novo", "email": "n@x.com.br", "empresa_id": emp["id"]})
    assert r.status_code == 409, r.text
    # inativo pode entrar; ativo em outra empresa também; mudar de empresa perdida para ativa reativa
    criar_contato(client, h, empresa_id=emp["id"], ativo=False)
    r = client.patch(f"{API}/contatos/{ct['id']}", headers=h, json={"ativo": True, "empresa_id": outra["id"]})
    assert r.status_code == 200, r.text
    r = client.patch(f"{API}/contatos/{ct['id']}", headers=h, json={"empresa_id": emp["id"]})
    assert r.status_code == 409, r.text


def test_excluir_empresa_leva_o_historico(client, dono, conta):
    emp = criar_empresa(client, conta["h"], "Some", valor_mensal="10.00")
    assert len(_historico(dono, emp["id"])) == 1
    assert client.delete(f"{API}/empresas/{emp['id']}", headers=conta["h"]).status_code == 204
    assert sql(dono, "select count(*) from empresa_historico") == [(0,)]


def test_check_eventos_webhook(dono, conta):
    cid = conta["conta"]["id"]
    inserir = ("insert into webhooks (conta_id, url, eventos, segredo_cifrado, segredo_prefixo) "
               "values (:c, 'https://x.com.br/h', cast(:ev as text[]), 'x', 'whsec_x')")
    sql(dono, inserir, c=cid, ev="{empresa.perdida,empresa.reativada,resposta.criada}")
    with pytest.raises(IntegrityError):
        sql(dono, inserir, c=cid, ev="{empresa.excluida}")


def test_descer_semente_e_subir(client, dono, conta):
    cid = conta["conta"]["id"]
    ativa = _empresa_sql(dono, cid, "Ativa", valor_mensal=120)
    pausada = _empresa_sql(dono, cid, "Pausada", valor_mensal=60, ativa=False)
    perdida = _empresa_sql(dono, cid, "Perdida", ativa=False, perdida_em=date(2026, 8, 1), motivo_perda="preco")
    sql(dono, "update empresas set criada_em = '2026-01-01 01:30:00+00' where id = :e", e=ativa)  # 31/12 em SP
    sql(dono, "update contas set origem = '{\"utm_source\": \"mencao\"}' where id = :c", c=cid)
    inserir = ("insert into webhooks (conta_id, url, eventos, segredo_cifrado, segredo_prefixo) "
               "values (:c, :u, cast(:ev as text[]), 'x', 'whsec_x') returning id")
    so_novos = sql(dono, inserir, c=cid, u="https://a.com.br", ev="{empresa.perdida}")[0][0]
    misto = sql(dono, inserir, c=cid, u="https://b.com.br", ev="{empresa.reativada,resposta.criada}")[0][0]
    sql(dono, "insert into webhook_entregas (conta_id, webhook_id, evento, corpo) "
              "values (:c, :w, 'empresa.reativada', '{}')", c=cid, w=misto)

    cfg = _alembic()
    command.downgrade(cfg, ANTERIOR)
    try:
        assert sql(dono, "select to_regclass('empresa_historico')") == [(None,)]
        assert sql(dono, "select count(*) from information_schema.columns where column_name in "
                         "('perdida_em', 'renovacao_em', 'motivo_perda', 'motivo_detalhe', 'ocultar_mencao_toqqi', "
                         "'origem') and table_name in ('empresas', 'config_envios', 'contas')") == [(0,)]
        assert sql(dono, "select count(*) from pg_proc where proname in "
                         "('empresas_registrar_historico', 'contatos_checar_empresa_perdida')") == [(0,)]
        assert sql(dono, "select to_regclass('convites_empresa_recentes_idx'), "
                         "to_regclass('convites_empresa_idx') is not null") == [(None, True)]
        assert sql(dono, "select id, eventos from webhooks order by id") == [(misto, ["resposta.criada"])]
        assert so_novos not in [w for (w,) in sql(dono, "select id from webhooks")]
        assert sql(dono, "select count(*) from webhook_entregas") == [(0,)]
        assert sql(dono, "select nome, ativa from empresas order by id") == [
            ("Ativa", True), ("Pausada", False), ("Perdida", False)]
        with pytest.raises(IntegrityError):
            sql(dono, "insert into webhooks (conta_id, url, eventos, segredo_cifrado, segredo_prefixo) "
                      "values (:c, 'https://c.com.br', '{empresa.perdida}', 'x', 'whsec_x')", c=cid)
    finally:
        command.upgrade(cfg, "head")

    # a semente: só a ativa, no dia da criação em São Paulo, com o valor de hoje
    assert sql(dono, "select empresa_id, tipo, data, valor_antes, valor_depois, origem, usuario_id "
                     "from empresa_historico") == [(ativa, "entrada", date(2025, 12, 31), None, 120, "migracao", None)]
    assert sql(dono, "select perdida_em, origem from empresas, contas where empresas.id = :e and contas.id = :c",
               e=perdida, c=cid) == [(None, None)]
    assert pausada

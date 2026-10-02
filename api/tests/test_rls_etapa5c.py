"""Etapa 5c: isolamento entre contas (RLS) em `config_crescimento`, `indicacoes` e `ofertas`, chaves compostas (uma
indicação ou oferta não aponta para cadastro de outra conta) e as rotas de uma conta sem ver a outra."""
import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError, ProgrammingError
from util import API, conta_pronta, criar_contato, criar_empresa, sql

TABELAS = ["config_crescimento", "indicacoes", "ofertas"]


def _como(c, conta_id: int) -> None:
    c.execute(text("select set_config('app.conta_id', :c, true)"), {"c": str(conta_id)})


@pytest.fixture
def ab(client):
    """A sem nada; B com configuração, uma indicação e uma oferta."""
    a = conta_pronta(client, "ana@alfa.com.br", empresa="Alfa")
    b = conta_pronta(client, "bia@beta.com.br", empresa="Beta")
    h = b["h"]
    assert client.put(f"{API}/crescimento/configuracao", headers=h, json={"indicacoes_ativas": True}).status_code == 200
    e = criar_empresa(client, h, "Mercado Beta")
    c = criar_contato(client, h, nome="Bruno", email="bruno@mercado.com.br", empresa_id=e["id"])
    i = client.post(f"{API}/crescimento/indicacoes", headers=h, json={"nome": "João", "email": "joao@x.com.br",
                                                                        "indicador_contato_id": c["id"]}).json()
    o = client.post(f"{API}/crescimento/ofertas", headers=h, json={"empresa_id": e["id"], "contato_id": c["id"],
                                                                     "lista": "promotores", "texto": "Oi"}).json()
    b.update(empresa=e, contato=c, indicacao=i, oferta=o)
    return a, b


def test_tabelas_novas_tem_rls_forcado(dono):
    linhas = sql(dono, """
        select c.relname, c.relrowsecurity, c.relforcerowsecurity, array_agg(p.polname order by p.polname)
          from pg_class c join pg_policy p on p.polrelid = c.oid
         where c.relname = any(:t) group by 1, 2, 3
    """, t=TABELAS)
    assert {x[0]: x[1:] for x in linhas} == {t: (True, True, ["isolamento_conta"]) for t in TABELAS}


def test_sql_sem_contexto_e_com_outra_conta(ab, app_engine, dono):
    a, b = ab
    idb = b["conta"]["id"]
    for t in TABELAS:
        assert sql(dono, f"select count(*) from {t} where conta_id = :b", b=idb)[0][0] == 1, t
    with app_engine.connect() as c:
        for t in TABELAS:
            assert c.execute(text(f"select count(*) from {t}")).scalar() == 0, t
    with app_engine.begin() as c:
        _como(c, a["conta"]["id"])
        for t in TABELAS:
            assert c.execute(text(f"select count(*) from {t}")).scalar() == 0, t
        assert c.execute(text("update indicacoes set situacao = 'em_contato'")).rowcount == 0
        assert c.execute(text("update ofertas set resultado = 'recusou', resultado_em = now()")).rowcount == 0
        assert c.execute(text("update config_crescimento set indicacoes_ativas = false")).rowcount == 0
        for t in TABELAS:
            assert c.execute(text(f"delete from {t}")).rowcount == 0, t
    assert sql(dono, "select situacao from indicacoes") == [("nova",)]
    for comando in (
        "insert into indicacoes (conta_id, origem, nome, email) values (:b, 'manual', 'Intrusa', 'x@x.com.br')",
        "insert into ofertas (conta_id, empresa_id, lista, texto) values (:b, :e, 'promotores', 'x')",
        "insert into config_crescimento (conta_id) values (:b)",
    ):
        with pytest.raises(ProgrammingError, match="row-level security"):
            with app_engine.begin() as c:
                _como(c, a["conta"]["id"])
                c.execute(text(comando), {"b": idb, "e": b["empresa"]["id"]})


def test_chaves_compostas(ab, app_engine):
    """Na conta A (contexto dela), a indicação e a oferta não podem apontar para empresa, contato ou resposta de B."""
    a, b = ab
    for comando in (
        "insert into indicacoes (origem, nome, email, indicador_contato_id) values ('manual', 'X', 'x@x.com', :c)",
        "insert into indicacoes (origem, nome, email, indicador_empresa_id) values ('manual', 'X', 'x@x.com', :e)",
        "insert into ofertas (empresa_id, lista, texto) values (:e, 'promotores', 'x')",
    ):
        with pytest.raises(IntegrityError):
            with app_engine.begin() as c:
                _como(c, a["conta"]["id"])
                c.execute(text(comando), {"c": b["contato"]["id"], "e": b["empresa"]["id"]})


def test_rotas_nao_veem_a_outra_conta(client, ab):
    a, b = ab
    h = a["h"]
    assert client.get(f"{API}/crescimento/indicacoes", headers=h).json()["total"] == 0
    assert client.get(f"{API}/crescimento/configuracao", headers=h).json()["indicacoes_ativas"] is False
    assert client.get(f"{API}/crescimento/resumo", headers=h).json()["ofertas"]["feitas"] == 0
    r = client.patch(f"{API}/crescimento/indicacoes/{b['indicacao']['id']}", headers=h, json={"situacao": "em_contato"})
    assert r.status_code == 404
    assert client.delete(f"{API}/crescimento/indicacoes/{b['indicacao']['id']}", headers=h).status_code == 404
    assert client.patch(f"{API}/crescimento/ofertas/{b['oferta']['id']}", headers=h,
                        json={"resultado": "aceitou"}).status_code == 404
    r = client.post(f"{API}/crescimento/indicacoes", headers=h, json={
        "nome": "Intrusa", "email": "x@x.com.br", "indicador_contato_id": b["contato"]["id"],
        "indicador_empresa_id": b["empresa"]["id"]})
    assert r.status_code == 422 and set(r.json()["erro"]["campos"]) == {"indicador_contato_id", "indicador_empresa_id"}
    assert client.get(f"{API}/crescimento/indicacoes", headers=b["h"]).json()["total"] == 1

"""Etapa 5a: isolamento entre contas (RLS) em `assinaturas`, `cobrancas` e `asaas_remocoes`, `asaas_eventos` só em modo
sistema, chaves compostas e as rotas da assinatura de uma conta sem ver a outra."""
from datetime import date, datetime, time

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError, ProgrammingError
from util import API, FUSO, assinar, conta_pronta, fixar_relogio, sql

TABELAS = ["assinaturas", "cobrancas"]


def momento(dia: str, hora: int = 10) -> datetime:
    return datetime.combine(date.fromisoformat(dia), time(hora), tzinfo=FUSO)


def _como(c, conta_id: int) -> None:
    c.execute(text("select set_config('app.conta_id', :c, true)"), {"c": str(conta_id)})


@pytest.fixture
def ab(client, dono, asaas_falso, monkeypatch):
    """A sem assinatura; B assinada e paga (uma cobrança e um evento do webhook)."""
    fixar_relogio(monkeypatch, momento("2026-10-10"))
    a = conta_pronta(client, "ana@alfa.com.br", empresa="Alfa")
    b = conta_pronta(client, "bia@beta.com.br", empresa="Beta")
    # o cadastro conta o teste pelo relógio de verdade: fixa o fim para a primeira fatura vencer em 15/10
    sql(dono, "update contas set teste_ate = :t where id = :b", t=momento("2026-10-15", 14), b=b["conta"]["id"])
    assert assinar(client, b["h"], razao_social="Beta Ltda").status_code == 201
    asaas_falso.simular("pagar", asaas_falso.cobrancas()[0]["id"], forma="PIX")
    assert sql(dono, "select count(*) from asaas_eventos")[0][0] == 1
    return a, b


def test_tabelas_novas_tem_rls_forcado(dono):
    linhas = sql(dono, """
        select c.relname, c.relrowsecurity, c.relforcerowsecurity, array_agg(p.polname order by p.polname)
          from pg_class c join pg_policy p on p.polrelid = c.oid
         where c.relname = any(:t) group by 1, 2, 3
    """, t=TABELAS + ["asaas_eventos", "asaas_remocoes"])
    assert {x[0]: x[1:] for x in linhas} == {"assinaturas": (True, True, ["isolamento_conta"]),
                                            "cobrancas": (True, True, ["isolamento_conta"]),
                                            "asaas_remocoes": (True, True, ["isolamento_conta"]),
                                            "asaas_eventos": (True, True, ["so_sistema"])}


def test_sql_sem_contexto_e_com_outra_conta(ab, app_engine, dono):
    a, b = ab
    idb = b["conta"]["id"]
    for t in TABELAS:
        assert sql(dono, f"select count(*) from {t} where conta_id = :b", b=idb)[0][0] == 1, t
    with app_engine.connect() as c:
        for t in TABELAS + ["asaas_eventos"]:
            assert c.execute(text(f"select count(*) from {t}")).scalar() == 0, t
    with app_engine.begin() as c:
        _como(c, a["conta"]["id"])
        for t in TABELAS:
            assert c.execute(text(f"select count(*) from {t}")).scalar() == 0, t
        assert c.execute(text("update assinaturas set plano = 'empresa'")).rowcount == 0
        assert c.execute(text("update cobrancas set situacao = 'paga'")).rowcount == 0
        assert c.execute(text("delete from cobrancas")).rowcount == 0
        assert c.execute(text("delete from assinaturas")).rowcount == 0
        assert c.execute(text("update contas set pago_ate = '2030-01-01'")).rowcount == 1  # só a própria
    assert sql(dono, "select pago_ate from contas where id = :b", b=idb) == [(date(2026, 11, 14),)]
    for comando in (
        "insert into assinaturas (conta_id, asaas_id, ambiente, plano, valor, razao_social, documento, "
        "email_cobranca, telefone, primeiro_vencimento) values (:b, 'sub_x', 'sandbox', 'essencial', 149, 'X', "
        "'11222333000181', 'x@x.com', '5511987654321', '2026-10-15')",
        "insert into asaas_remocoes (asaas_id, ambiente, conta_id, motivo) values ('sub_y', 'sandbox', :b, 'x')",
        "insert into cobrancas (conta_id, asaas_id, valor, vencimento, situacao) values (:b, 'pay_x', 1, "
        "'2026-10-15', 'paga')",
    ):
        with pytest.raises(ProgrammingError, match="row-level security"):
            with app_engine.begin() as c:
                _como(c, a["conta"]["id"])
                c.execute(text(comando), {"b": idb})


def test_asaas_eventos_so_em_modo_sistema(ab, app_engine, dono):
    a, b = ab
    with app_engine.begin() as c:
        _como(c, b["conta"]["id"])  # nem a própria conta enxerga os avisos dela
        assert c.execute(text("select count(*) from asaas_eventos")).scalar() == 0
        assert c.execute(text("update asaas_eventos set erro = 'x'")).rowcount == 0
        assert c.execute(text("delete from asaas_eventos")).rowcount == 0
    with pytest.raises(ProgrammingError, match="row-level security"):
        with app_engine.begin() as c:
            _como(c, b["conta"]["id"])
            c.execute(text("insert into asaas_eventos (id, tipo, conta_id) values ('evt_x', 'PAYMENT_CREATED', :b)"),
                      {"b": b["conta"]["id"]})
    with app_engine.begin() as c:
        c.execute(text("select set_config('app.sistema', 'on', true)"))
        assert c.execute(text("select count(*) from asaas_eventos")).scalar() == 1
        c.execute(text("insert into asaas_eventos (id, tipo) values ('evt_y', 'PAYMENT_CREATED')"))
    assert sql(dono, "select count(*) from asaas_eventos")[0][0] == 2


def test_chave_composta_impede_apontar_para_outra_conta(ab, dono):
    a, b = ab
    (sub_b,), = sql(dono, "select id from assinaturas where conta_id = :b", b=b["conta"]["id"])
    with pytest.raises(IntegrityError):  # nem em modo sistema
        sql(dono, "insert into cobrancas (conta_id, assinatura_id, asaas_id, valor, vencimento, situacao) "
                  "values (:a, :s, 'pay_z', 1, '2026-10-15', 'pendente')", a=a["conta"]["id"], s=sub_b)


def test_api_de_a_nao_ve_nem_mexe_na_assinatura_de_b(client, ab, dono, asaas_falso):
    a, b = ab
    h = a["h"]
    d = client.get(f"{API}/assinatura", headers=h).json()
    assert (d["assinatura"], d["fatura_aberta"], d["cobrancas"]) == (None, None, [])
    assert d["conta"]["situacao"] == "teste"
    for metodo, rota, corpo in (("put", "/plano", {"plano": "empresa"}), ("post", "/cancelar", None)):
        r = client.request(metodo.upper(), f"{API}/assinatura{rota}", headers=h, json=corpo)
        assert r.status_code == 409 and r.json()["erro"]["codigo"] == "sem_assinatura"
    assert sql(dono, "select plano, situacao from assinaturas") == [("profissional", "ativa")]
    assert client.get(f"{API}/eu", headers=h).json()["conta"]["cobranca"]["pago_ate"] is None
    # B vê a sua
    d = client.get(f"{API}/assinatura", headers=b["h"]).json()
    assert d["assinatura"]["dados"]["razao_social"] == "Beta Ltda" and len(d["cobrancas"]) == 1
    # A pode assinar com o mesmo CNPJ (o Asaas é que decide), sem mexer na de B
    assert assinar(client, h).status_code == 201
    assert sql(dono, "select count(*) from assinaturas where situacao = 'ativa'")[0][0] == 2


def test_remocoes_pendentes_isoladas_por_conta(ab, app_engine, dono):
    a, b = ab
    sql(dono, "insert into asaas_remocoes (asaas_id, ambiente, conta_id, motivo) values "
              "('sub_b', 'sandbox', :b, 'duplicada'), ('sub_sem_conta', 'sandbox', null, 'duplicada')",
        b=b["conta"]["id"])
    with app_engine.begin() as c:
        _como(c, a["conta"]["id"])
        assert c.execute(text("select count(*) from asaas_remocoes")).scalar() == 0
        assert c.execute(text("update asaas_remocoes set tentativas = 9")).rowcount == 0
    with app_engine.begin() as c:
        _como(c, b["conta"]["id"])  # só a dela (a sem conta, só em modo sistema)
        assert c.execute(text("select asaas_id from asaas_remocoes")).scalars().all() == ["sub_b"]
    with app_engine.begin() as c:
        c.execute(text("select set_config('app.sistema', 'on', true)"))
        assert c.execute(text("select count(*) from asaas_remocoes")).scalar() == 2

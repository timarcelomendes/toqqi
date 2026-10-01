"""Isolamento entre contas nas tabelas e rotas da etapa 3a, e exclusão de conta pela plataforma."""
import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, ProgrammingError
from util import (
    API,
    conta_pronta,
    criar_contato,
    disparar,
    emails_para,
    fila,
    form_padrao,
    historico,
    ligar_envios,
    sql,
    token_do_convite,
)

TABELAS = ["config_envios", "envios", "descadastros"]


@pytest.fixture
def ab(client):
    a = conta_pronta(client, "ana@alfa.com.br", empresa="Alfa")
    b = conta_pronta(client, "bia@beta.com.br", empresa="Beta")
    ligar_envios(client, a["h"])
    ligar_envios(client, b["h"])
    c = criar_contato(client, b["h"], nome="Contato B", email="cb@b.com.br", telefone="11911112222")
    disparar(client, b["h"], [c["id"]])
    client.post(f"{API}/envios/descadastros", headers=b["h"], json={"email": "saiu@b.com.br"})
    b.update(contato=c, envio=historico(client, b["h"])[0])
    return a, b


def test_tabelas_novas_tem_rls_forcado(dono):
    linhas = sql(dono, """
        select c.relname, c.relrowsecurity, c.relforcerowsecurity,
               (select count(*) from pg_policy p where p.polrelid = c.oid)
          from pg_class c where c.relname = any(:t)
    """, t=TABELAS)
    assert {x[0] for x in linhas} == set(TABELAS)
    for nome, rls, forcado, politicas in linhas:
        assert rls and forcado and politicas == 1, nome


def test_sql_sem_contexto_e_com_outra_conta(ab, app_engine):
    a, b = ab
    with app_engine.connect() as c:
        for t in TABELAS:
            assert c.execute(text(f"select count(*) from {t}")).scalar() == 0, t
    with app_engine.begin() as c:
        c.execute(text("select set_config('app.conta_id', :c, true)"), {"c": str(a["conta"]["id"])})
        for t in TABELAS:
            assert c.execute(text(f"select count(*) from {t} where conta_id <> :a"),
                             {"a": a["conta"]["id"]}).scalar() == 0, t
    with pytest.raises(ProgrammingError, match="row-level security"):
        with app_engine.begin() as c:
            c.execute(text("select set_config('app.conta_id', :c, true)"), {"c": str(a["conta"]["id"])})
            c.execute(text("insert into descadastros (conta_id, email, origem) values (:b, 'x@x.com', 'manual')"),
                      {"b": b["conta"]["id"]})


def test_envio_nao_aponta_para_contato_de_outra_conta(ab, app_engine):
    a, b = ab
    with pytest.raises(DBAPIError, match="foreign key"):
        with app_engine.begin() as c:
            c.execute(text("select set_config('app.conta_id', :c, true)"), {"c": str(a["conta"]["id"])})
            c.execute(text("insert into envios (contato_id, canal, tipo, origem, para) "
                           "values (:k, 'email', 'convite', 'manual', 'x@x.com')"), {"k": b["contato"]["id"]})


def test_api_de_a_nao_ve_nem_envia_para_b(client, ab):
    a, b = ab
    h = a["h"]
    assert fila(client, h) == {}
    assert historico(client, h) == []
    assert client.get(f"{API}/envios/descadastros", headers=h).json()["total"] == 0
    assert client.get(f"{API}/envios/resumo", headers=h).json()["enviados_30d"] == 0
    antes = len(emails_para("cb@b.com.br"))
    r = disparar(client, h, [b["contato"]["id"]], ignorar_descanso=True)
    assert r.json() == {"agendados": 0, "ignorados": []}
    assert client.post(f"{API}/envios/{b['envio']['id']}/tentar-de-novo", headers=h).status_code == 404
    assert client.post(f"{API}/contatos/{b['contato']['id']}/whatsapp", headers=h, json={}).status_code == 404
    r = client.post(f"{API}/envios/disparar", headers=h, json={"toda_fila": True})
    assert r.json()["agendados"] == 0
    assert len(emails_para("cb@b.com.br")) == antes
    assert client.put(f"{API}/envios/configuracao", headers=h,
                      json={"formulario_id": form_padrao(client, b["h"])["id"]}).status_code == 422
    # B segue com o seu histórico
    assert len(historico(client, b["h"])) == 1


def test_resposta_em_b_gera_agradecimento_so_em_b(client, ab, dono):
    a, b = ab
    nps = form_padrao(client, b["h"])
    token = token_do_convite(emails_para("cb@b.com.br")[0])
    client.post(f"{API}/publico/convites/{token}/responder", json={"respostas": {nps["perguntas"][0]["id"]: 10}})
    linhas = sql(dono, "select conta_id, tipo from envios where tipo = 'agradecimento'")
    assert linhas == [(b["conta"]["id"], "agradecimento")]
    assert historico(client, a["h"]) == []


# ---- plataforma: excluir conta ----------------------------------------------

def test_excluir_conta(client, ab, dono):
    a, b = ab
    root = conta_pronta(client, "root@toqqi.com", empresa="Toqqi")
    cid = b["conta"]["id"]
    nps = form_padrao(client, b["h"])
    token = token_do_convite(emails_para("cb@b.com.br")[0])
    client.post(f"{API}/publico/convites/{token}/responder", json={"respostas": {nps["perguntas"][0]["id"]: 3}})
    url = f"{API}/plataforma/contas/{cid}"
    assert client.request("DELETE", url, headers=a["h"], json={"confirmar_nome": "Beta"}).status_code == 403
    r = client.request("DELETE", url, headers=root["h"], json={"confirmar_nome": "Gama"})
    assert r.status_code == 409 and r.json()["erro"]["codigo"] == "nome_nao_confere"
    r = client.request("DELETE", f"{API}/plataforma/contas/{root['conta']['id']}", headers=root["h"],
                       json={"confirmar_nome": "Toqqi"})
    assert r.status_code == 409 and r.json()["erro"]["codigo"] == "propria_conta"
    assert client.request("DELETE", f"{API}/plataforma/contas/99999", headers=root["h"],
                          json={"confirmar_nome": "X"}).status_code == 404
    assert client.request("DELETE", url, headers=root["h"], json={}).status_code == 422

    r = client.request("DELETE", url, headers=root["h"], json={"confirmar_nome": "  beta "})
    assert r.status_code == 204
    tabelas = [t for (t,) in sql(dono, """select table_name from information_schema.columns
                                          where column_name = 'conta_id' and table_schema = 'public'""")]
    assert len(tabelas) >= 20
    for t in tabelas:
        assert sql(dono, f"select count(*) from {t} where conta_id = :c", c=cid)[0][0] == 0, t
    assert sql(dono, "select count(*) from contas where id = :c", c=cid)[0][0] == 0
    # auditoria global, sem conta, visível só em modo sistema
    [(conta_id, detalhe)] = sql(dono, "select conta_id, detalhe from auditoria where evento = 'conta_excluida'")
    assert conta_id is None and detalhe["conta"] == {"id": cid, "nome": "Beta"} and detalhe["por"] == "root@toqqi.com"
    assert "conta_excluida" not in [e["evento"] for e in client.get(f"{API}/auditoria", headers=root["h"]).json()["itens"]]
    # sessão da conta apagada deixa de valer; as outras contas seguem intactas
    assert client.get(f"{API}/eu", headers=b["h"]).status_code == 401
    assert client.get(f"{API}/eu", headers=a["h"]).status_code == 200
    assert {c["nome"] for c in client.get(f"{API}/plataforma/contas", headers=root["h"]).json()} == {"Alfa", "Toqqi"}

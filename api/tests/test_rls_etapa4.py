"""Etapa 4a: isolamento entre contas (RLS) nas tabelas novas e nas rotas de respostas, ações, painel e importação."""
import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, ProgrammingError
from util import (
    API,
    conta_pronta,
    criar_contato,
    criar_empresa,
    criar_responsavel,
    lista_respostas,
    quadro,
    registrar_resposta,
    sql,
)

TABELAS = ["acoes", "config_acoes"]
pytestmark = pytest.mark.usefixtures("relogio_estavel")


@pytest.fixture
def ab(client):
    a = conta_pronta(client, "ana@alfa.com.br", empresa="Alfa")
    b = conta_pronta(client, "bia@beta.com.br", empresa="Beta")
    hb = b["h"]
    rb = criar_responsavel(client, hb, "Resp B", email="resp@beta.com.br")
    eb = criar_empresa(client, hb, "Empresa B", responsavel_id=rb["id"], valor_mensal="900.00")
    cb = criar_contato(client, hb, nome="Contato B", email="cb@b.com.br", empresa_id=eb["id"])
    resposta = registrar_resposta(client, hb, cb["id"], 2, comentario="Frete caro").json()
    client.put(f"{API}/acoes/configuracao", headers=hb, json={"prazo_detrator": 9, "acao_promotor": True})
    b.update(resp=rb, empresa=eb, contato=cb, resposta=resposta, acao=resposta["acao"])
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
    for comando in ("insert into acoes (conta_id, titulo, prioridade) values (:b, 'invasora', 'alta')",
                    "insert into config_acoes (conta_id) values (:b)"):
        with pytest.raises(ProgrammingError, match="row-level security"):
            with app_engine.begin() as c:
                c.execute(text("select set_config('app.conta_id', :c, true)"), {"c": str(a["conta"]["id"])})
                c.execute(text(comando), {"b": b["conta"]["id"]})


@pytest.mark.parametrize("coluna", ["resposta_id", "empresa_id", "contato_id", "responsavel_id"])
def test_acao_nao_aponta_para_outra_conta(ab, app_engine, coluna):
    a, b = ab
    alvo = {"resposta_id": b["resposta"]["id"], "empresa_id": b["empresa"]["id"], "contato_id": b["contato"]["id"],
            "responsavel_id": b["resp"]["id"]}[coluna]
    with pytest.raises(DBAPIError, match="foreign key"):
        with app_engine.begin() as c:
            c.execute(text("select set_config('app.conta_id', :c, true)"), {"c": str(a["conta"]["id"])})
            c.execute(text(f"insert into acoes (titulo, prioridade, {coluna}) values ('x', 'alta', :v)"),
                      {"v": alvo})


def test_api_de_a_nao_ve_nem_mexe_em_b(client, ab):
    a, b = ab
    h = a["h"]
    r, acao = b["resposta"]["id"], b["acao"]["id"]
    assert lista_respostas(client, h)["total"] == 0
    assert quadro(client, h)["totais"] == {"a_fazer": 0, "em_andamento": 0, "concluida": 0, "vencidas": 0}
    assert client.get(f"{API}/acoes", headers=h).json()["total"] == 0
    for metodo, url, corpo in [
        ("get", f"/respostas/{r}", None), ("patch", f"/respostas/{r}", {"nota": 9}),
        ("post", f"/respostas/{r}/arquivar", None), ("post", f"/respostas/{r}/restaurar", None),
        ("delete", f"/respostas/{r}", None),
        ("get", f"/acoes/{acao}", None), ("patch", f"/acoes/{acao}", {"situacao": "em_andamento"}),
        ("delete", f"/acoes/{acao}", None),
    ]:
        resp = client.request(metodo.upper(), f"{API}{url}", headers=h, json=corpo)
        assert resp.status_code == 404, (metodo, url, resp.status_code)
    # ids de B nos cadastros de A
    r1 = registrar_resposta(client, h, b["contato"]["id"], 5)
    assert r1.status_code == 422 and "contato_id" in r1.json()["erro"]["campos"]
    for campo, valor in (("empresa_id", b["empresa"]["id"]), ("resposta_id", r), ("contato_id", b["contato"]["id"]),
                         ("responsavel_id", b["resp"]["id"])):
        x = client.post(f"{API}/acoes", headers=h, json={"titulo": "x", campo: valor})
        assert x.status_code == 422 and campo in x.json()["erro"]["campos"], campo
    minha = client.post(f"{API}/acoes", headers=h, json={"titulo": "Minha"}).json()
    x = client.patch(f"{API}/acoes/{minha['id']}", headers=h, json={"responsavel_id": b["resp"]["id"]})
    assert x.status_code == 422
    # configuração e painel de A não veem B
    assert client.get(f"{API}/acoes/configuracao", headers=h).json() == {
        "prazo_detrator": 2, "prazo_neutro": 5, "prazo_promotor": 7, "acao_promotor": False}
    p = client.get(f"{API}/painel", headers=h).json()
    assert p["nps"]["total"] == 0 and p["atencao"]["acoes_abertas"] == 1  # só a "Minha", de A
    assert p["atencao"]["receita_em_risco"] == {"valor": 0, "empresas": 0, "sem_valor": 0}
    assert p["comentarios"] == [] and p["primeiros_passos"]["primeira_resposta"] is False
    assert client.get(f"{API}/respostas.csv", headers=h).content.decode("utf-8-sig").count("\r\n") == 1
    # B continua intacto, com a própria configuração
    assert client.get(f"{API}/respostas/{r}", headers=b["h"]).json()["nota"] == 2
    assert client.get(f"{API}/acoes/{acao}", headers=b["h"]).json()["prazo"] == b["acao"]["prazo"]
    assert client.get(f"{API}/acoes/configuracao", headers=b["h"]).json()["prazo_detrator"] == 9
    pb = client.get(f"{API}/painel", headers=b["h"]).json()
    assert pb["nps"]["total"] == 1 and pb["atencao"]["receita_em_risco"]["valor"] == 900.0


def test_importacao_de_respostas_so_acha_contatos_da_conta(client, ab):
    a, b = ab
    h = a["h"]
    conteudo = "email;data;nota\r\ncb@b.com.br;10/01/2025;9\r\n".encode()
    d = client.post(f"{API}/importacao/analisar", headers=h, files={"arquivo": ("r.csv", conteudo)},
                    data={"tipo": "respostas"}).json()
    c = client.post(f"{API}/importacao/{d['id']}/conferir", headers=h,
                    json={"mapeamento": d["mapeamento_sugerido"]}).json()
    assert c["com_problema"] == 1
    assert c["problemas"][0]["motivo"] == "Contato não encontrado: cadastre ou importe os contatos antes."
    assert client.post(f"{API}/importacao/{d['id']}/conferir", headers=b["h"],
                       json={"mapeamento": d["mapeamento_sugerido"]}).status_code == 404


def test_alerta_e_acao_ficam_na_conta_da_resposta(client, ab, dono):
    a, b = ab
    linhas = sql(dono, "select conta_id, origem, prazo - current_date from acoes")
    assert [(conta, origem) for conta, origem, _ in linhas] == [(b["conta"]["id"], "automatica")]

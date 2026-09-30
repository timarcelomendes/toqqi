"""Isolamento entre contas nas tabelas da etapa 2 (RLS)."""
import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, ProgrammingError
from util import (
    API,
    conta_pronta,
    criar_contato,
    criar_empresa,
    criar_form,
    form_padrao,
    link_pesquisa,
    responder_link,
    sql,
)

TABELAS = ["grupos", "segmentos", "perfis_contato", "cargos", "responsaveis", "empresas", "contatos",
           "formularios", "convites", "respostas", "importacoes"]
NPS = {"tipo": "nps", "titulo": "Recomendaria?", "obrigatoria": True}


@pytest.fixture
def ab(client):
    a = conta_pronta(client, "ana@alfa.com.br", empresa="Alfa")
    b = conta_pronta(client, "bia@beta.com.br", empresa="Beta")
    # B tem um pouco de tudo
    g = client.post(f"{API}/cadastros/grupos", headers=b["h"], json={"nome": "Grupo B"}).json()
    resp = client.post(f"{API}/responsaveis", headers=b["h"], json={"nome": "Resp B"}).json()
    e = criar_empresa(client, b["h"], "Empresa B", grupo_id=g["id"], responsavel_id=resp["id"])
    c = criar_contato(client, b["h"], nome="Contato B", email="cb@b.com.br", empresa_id=e["id"])
    f = criar_form(client, b["h"], [NPS], nome="Form B")
    token = link_pesquisa(client, b["h"], c["id"], formulario_id=f["id"])
    client.post(f"{API}/publico/convites/{token}/responder", json={"respostas": {f["perguntas"][0]["id"]: 9}})
    client.post(f"{API}/importacao/analisar", headers=b["h"], files={"arquivo": ("x.csv", b"nome;email\r\nA;a@a.com\r\n")})
    b.update(grupo=g, resp=resp, empresa=e, contato=c, form=f)
    return a, b


def test_todas_as_tabelas_novas_tem_rls_forcado(dono):
    linhas = sql(dono, """
        select c.relname, c.relrowsecurity, c.relforcerowsecurity,
               (select count(*) from pg_policy p where p.polrelid = c.oid)
          from pg_class c where c.relname = any(:t)
    """, t=TABELAS)
    assert {x[0] for x in linhas} == set(TABELAS)
    for nome, rls, forcado, politicas in linhas:
        assert rls and forcado and politicas == 1, nome


def test_sql_sem_contexto_nao_ve_nada(ab, app_engine):
    with app_engine.connect() as c:
        for t in TABELAS:
            assert c.execute(text(f"select count(*) from {t}")).scalar() == 0, t


def test_sql_com_contexto_ve_so_a_propria_conta(ab, app_engine):
    a, b = ab
    with app_engine.begin() as c:
        c.execute(text("select set_config('app.conta_id', :c, true)"), {"c": str(a["conta"]["id"])})
        for t in TABELAS:
            outras = c.execute(text(f"select count(*) from {t} where conta_id <> :a"), {"a": a["conta"]["id"]}).scalar()
            assert outras == 0, t
        assert c.execute(text("select count(*) from formularios")).scalar() == 2  # só os padrão de A


def test_nao_grava_em_outra_conta(ab, app_engine):
    a, b = ab
    with pytest.raises(ProgrammingError, match="row-level security"):
        with app_engine.begin() as c:
            c.execute(text("select set_config('app.conta_id', :c, true)"), {"c": str(a["conta"]["id"])})
            c.execute(text("insert into grupos (conta_id, nome) values (:b, 'invasor')"), {"b": b["conta"]["id"]})


def test_fk_nao_aponta_para_linha_de_outra_conta(ab, app_engine):
    """Mesmo sabendo o id, a chave composta (id, conta_id) impede ligar à empresa de B."""
    a, b = ab
    with pytest.raises(DBAPIError):
        with app_engine.begin() as c:
            c.execute(text("select set_config('app.conta_id', :c, true)"), {"c": str(a["conta"]["id"])})
            c.execute(text("insert into contatos (codigo, nome, email, empresa_id) values "
                           "('123456789', 'X', 'x@x.com', :e)"), {"e": b["empresa"]["id"]})


def test_api_de_a_nao_ve_nem_mexe_em_b(client, ab):
    a, b = ab
    h = a["h"]
    # listas
    assert client.get(f"{API}/empresas", headers=h).json()["total"] == 0
    assert client.get(f"{API}/contatos", headers=h).json()["total"] == 0
    assert client.get(f"{API}/cadastros/grupos", headers=h).json() == []
    assert client.get(f"{API}/responsaveis", headers=h).json() == []
    assert "Form B" not in [f["nome"] for f in client.get(f"{API}/formularios", headers=h).json()]
    # por id
    e, c, f, g, r = b["empresa"]["id"], b["contato"]["id"], b["form"]["id"], b["grupo"]["id"], b["resp"]["id"]
    for metodo, url, corpo in [
        ("get", f"/empresas/{e}", None), ("patch", f"/empresas/{e}", {"nome": "X"}), ("delete", f"/empresas/{e}", None),
        ("get", f"/contatos/{c}", None), ("patch", f"/contatos/{c}", {"nome": "X"}), ("delete", f"/contatos/{c}", None),
        ("post", f"/contatos/{c}/link-pesquisa", {}),
        ("get", f"/formularios/{f}", None), ("patch", f"/formularios/{f}", {"nome": "X"}),
        ("delete", f"/formularios/{f}", None), ("post", f"/formularios/{f}/duplicar", None),
        ("post", f"/formularios/{f}/novo-codigo", None), ("get", f"/formularios/{f}/resultados", None),
        ("get", f"/formularios/{f}/respostas", None), ("get", f"/formularios/{f}/respostas.csv", None),
        ("patch", f"/cadastros/grupos/{g}", {"nome": "X"}), ("delete", f"/cadastros/grupos/{g}", None),
        ("patch", f"/responsaveis/{r}", {"nome": "Xx"}), ("delete", f"/responsaveis/{r}", None),
        ("post", f"/responsaveis/{r}/testar-teams", None),
    ]:
        resp = client.request(metodo.upper(), f"{API}{url}", headers=h, json=corpo)
        assert resp.status_code == 404, (metodo, url, resp.status_code)
    # usar ids de B em cadastros de A
    assert client.post(f"{API}/empresas", headers=h, json={"nome": "Minha", "grupo_id": g}).status_code == 422
    assert client.post(f"{API}/contatos", headers=h,
                       json={"nome": "Meu", "email": "m@a.com.br", "empresa_id": e}).status_code == 422
    assert client.post(f"{API}/contatos", headers=h, json={"nome": "Meu", "email": "m@a.com.br"}).status_code == 201
    link = client.post(f"{API}/contatos", headers=h, json={"nome": "Outro", "email": "o@a.com.br"}).json()
    assert client.post(f"{API}/contatos/{link['id']}/link-pesquisa", headers=h,
                       json={"formulario_id": f}).status_code == 422
    # B continua intacto
    assert client.get(f"{API}/contatos/{c}", headers=b["h"]).json()["nome"] == "Contato B"
    assert client.get(f"{API}/formularios/{f}", headers=b["h"]).json()["respostas"] == 1


def test_importacao_de_b_invisivel_para_a(client, ab, dono):
    a, b = ab
    imp_id = sql(dono, "select id from importacoes")[0][0]
    corpo = {"mapeamento": {"nome": "nome", "email": "email"}, "chave": "email"}
    assert client.post(f"{API}/importacao/{imp_id}/conferir", headers=a["h"], json=corpo).status_code == 404
    assert client.post(f"{API}/importacao/{imp_id}/importar", headers=a["h"], json=corpo).status_code == 404
    assert client.post(f"{API}/importacao/{imp_id}/conferir", headers=b["h"], json=corpo).status_code == 200


def test_link_publico_de_b_grava_em_b(client, ab, dono):
    a, b = ab
    f = b["form"]
    # mesmo e-mail cadastrado nas duas contas: a resposta só pode identificar o contato de B
    criar_contato(client, a["h"], email="cb@b.com.br")
    form_b = client.patch(f"{API}/formularios/{f['id']}", headers=b["h"], json={"perguntas": f["perguntas"] + [
        {"tipo": "texto_curto", "titulo": "E-mail", "formato": "email"}]}).json()
    p = [x["id"] for x in form_b["perguntas"]]
    assert responder_link(client, f["codigo_publico"], {p[0]: 3, p[1]: "cb@b.com.br"}).status_code == 201
    linhas = sql(dono, "select conta_id, contato_id from respostas where nota = 3")
    assert linhas == [(b["conta"]["id"], b["contato"]["id"])]
    assert client.get(f"{API}/formularios/{f['id']}/respostas", headers=b["h"]).json()["total"] == 2
    nps_a = form_padrao(client, a["h"])
    assert client.get(f"{API}/formularios/{nps_a['id']}/respostas", headers=a["h"]).json()["total"] == 0

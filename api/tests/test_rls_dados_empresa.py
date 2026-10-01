"""Dados da empresa e imagens: isolamento entre contas (RLS) na tabela `imagens` e nas rotas novas."""
import hashlib

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, ProgrammingError
from util import API, caminho_imagem, conta_pronta, criar_contato, form_padrao, link_pesquisa, png, sql

TABELAS = ["imagens"]


def _arquivo(conteudo: bytes) -> dict:
    return {"arquivo": ("logo.png", conteudo, "image/png")}


@pytest.fixture
def ab(client):
    a = conta_pronta(client, "ana@alfa.com.br", empresa="Alfa")
    b = conta_pronta(client, "bia@beta.com.br", empresa="Beta")
    hb = b["h"]
    r = client.put(f"{API}/conta/dados", headers=hb, json={"nome": "Beta", "documento": "11.222.333/0001-81",
                                                           "cidade": "Recife"})
    assert r.status_code == 200, r.text
    logo = client.put(f"{API}/conta/logo", headers=hb, files=_arquivo(png(1))).json()["logo_url"]
    form = form_padrao(client, hb)
    logo_form = client.post(f"{API}/formularios/{form['id']}/logo", headers=hb, files=_arquivo(png(2))).json()
    b.update(logo=logo, form=form, logo_form=logo_form["logo_url"], csat=form_padrao(client, hb, "csat"))
    return a, b


def _como(c, conta_id: int) -> None:
    c.execute(text("select set_config('app.conta_id', :c, true)"), {"c": str(conta_id)})


def test_imagens_tem_rls_forcado(dono):
    linhas = sql(dono, """
        select c.relname, c.relrowsecurity, c.relforcerowsecurity,
               (select count(*) from pg_policy p where p.polrelid = c.oid)
          from pg_class c where c.relname = any(:t)
    """, t=TABELAS)
    assert {x[0] for x in linhas} == set(TABELAS)
    for nome, rls, forcado, politicas in linhas:
        assert rls and forcado and politicas == 1, nome


def test_sql_sem_contexto_e_com_outra_conta(ab, app_engine, dono):
    a, b = ab
    assert sql(dono, "select count(*) from imagens where conta_id = :b", b=b["conta"]["id"])[0][0] == 2
    with app_engine.connect() as c:
        assert c.execute(text("select count(*) from imagens")).scalar() == 0
    with app_engine.begin() as c:
        _como(c, a["conta"]["id"])
        assert c.execute(text("select count(*) from imagens")).scalar() == 0
        assert c.execute(text("delete from imagens")).rowcount == 0
        assert c.execute(text("update imagens set tipo = 'image/jpeg'")).rowcount == 0
    dados = png(9)
    valores = {"b": b["conta"]["id"], "k": "k" * 43, "d": dados, "t": len(dados),
               "h": hashlib.sha256(dados).hexdigest(), "f": b["csat"]["id"]}
    with pytest.raises(ProgrammingError, match="row-level security"):
        with app_engine.begin() as c:
            _como(c, a["conta"]["id"])
            c.execute(text("insert into imagens (conta_id, uso, chave, tipo, dados, tamanho, sha256) "
                           "values (:b, 'logo_conta', :k, 'image/png', :d, :t, :h)"), valores)
    # logo de formulário de A apontando para um formulário de B: a chave composta não deixa
    with pytest.raises(DBAPIError, match="foreign key"):
        with app_engine.begin() as c:
            _como(c, a["conta"]["id"])
            c.execute(text("insert into imagens (uso, formulario_id, chave, tipo, dados, tamanho, sha256) "
                           "values ('logo_formulario', :f, :k, 'image/png', :d, :t, :h)"), valores)


def test_api_de_a_nao_ve_nem_mexe_em_b(client, ab):
    a, b = ab
    h = a["h"]
    d = client.get(f"{API}/conta/dados", headers=h).json()
    assert (d["nome"], d["documento"], d["cidade"], d["logo_url"]) == ("Alfa", None, None, None)
    assert client.get(f"{API}/eu", headers=h).json()["conta"]["logo_url"] is None
    # logo no formulário de B → 404, como qualquer formulário que não é da conta
    r = client.post(f"{API}/formularios/{b['form']['id']}/logo", headers=h, files=_arquivo(png(3)))
    assert r.status_code == 404
    # A mexe nos próprios dados e logo; B continua igual
    assert client.delete(f"{API}/conta/logo", headers=h).status_code == 204
    assert client.put(f"{API}/conta/dados", headers=h, json={"nome": "Alfa Nova", "cidade": "Natal"}).status_code == 200
    logo_a = client.put(f"{API}/conta/logo", headers=h, files=_arquivo(png(4))).json()["logo_url"]
    db = client.get(f"{API}/conta/dados", headers=b["h"]).json()
    assert (db["nome"], db["documento"], db["cidade"], db["logo_url"]) == ("Beta", "11222333000181", "Recife",
                                                                           b["logo"])
    for url in (b["logo"], b["logo_form"]):
        assert client.get(caminho_imagem(url)).status_code == 200
    assert [i["evento"] for i in client.get(f"{API}/auditoria", headers=h).json()["itens"]
            if i["evento"].startswith(("logo", "dados_empresa"))] == ["logo_alterado", "dados_empresa_alterados"]
    # o formulário de A não "pega emprestada" a imagem de B: na página pública vale o logo de A
    nps = form_padrao(client, h)
    r = client.patch(f"{API}/formularios/{nps['id']}", headers=h, json={"tema": {"logo_url": b["logo_form"]}})
    assert r.status_code == 200
    token = link_pesquisa(client, h, criar_contato(client, h)["id"])
    assert client.get(f"{API}/publico/convites/{token}").json()["formulario"]["tema"]["logo_url"] == logo_a


def test_excluir_conta_leva_as_imagens(client, ab, dono):
    a, b = ab
    root = conta_pronta(client, "root@toqqi.com", empresa="Toqqi")
    logo_a = client.put(f"{API}/conta/logo", headers=a["h"], files=_arquivo(png(5))).json()["logo_url"]
    r = client.request("DELETE", f"{API}/plataforma/contas/{b['conta']['id']}", headers=root["h"],
                       json={"confirmar_nome": "Beta"})
    assert r.status_code == 204, r.text
    assert sql(dono, "select count(*) from imagens where conta_id = :b", b=b["conta"]["id"])[0][0] == 0
    for url in (b["logo"], b["logo_form"]):
        assert client.get(caminho_imagem(url)).status_code == 404
    assert client.get(caminho_imagem(logo_a)).status_code == 200  # a outra conta segue intacta

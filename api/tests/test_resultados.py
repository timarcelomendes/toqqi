"""Resultados (NPS, CSAT, por pergunta), lista de respostas e exportação CSV."""
import csv
import io

import pytest
from util import API, conta_pronta, criar_contato, criar_empresa, criar_form, link_pesquisa, responder_link, sql

NPS = {"tipo": "nps", "titulo": "Recomendaria a {empresa}?", "obrigatoria": True}


@pytest.fixture
def admin(client):
    return conta_pronta(client, "ana@alfa.com.br", empresa="Alfa Distribuidora")


def test_nps_e_perguntas(client, admin):
    h = admin["h"]
    f = criar_form(client, h, [
        NPS,
        {"tipo": "escolha_multipla", "titulo": "Motivos", "opcoes": ["Preço", "Prazo", "Mix"]},
        {"tipo": "sim_nao", "titulo": "Compraria de novo?"},
        {"tipo": "comentario", "titulo": "Comentário"},
    ])
    p = [x["id"] for x in f["perguntas"]]
    # 5 promotores, 2 neutros, 3 detratores → NPS = 50% - 30% = 20
    notas = [10, 10, 9, 9, 9, 8, 7, 6, 3, 0]
    for i, n in enumerate(notas):
        resp = {p[0]: n, p[2]: n >= 7}
        if i < 3:
            resp[p[1]] = ["Preço", "Prazo"] if i == 0 else ["Prazo"]
            resp[p[3]] = f"texto {i}"
        assert responder_link(client, f["codigo_publico"], resp).status_code == 201
    r = client.get(f"{API}/formularios/{f['id']}/resultados", headers=h).json()
    assert r["total"] == 10
    assert r["nps"] == {"valor": 20, "promotores": 5, "neutros": 2, "detratores": 3}
    assert "csat" not in r
    q = {x["id"]: x for x in r["perguntas"]}
    assert q[p[0]]["respostas"] == 10
    assert q[p[0]]["distribuicao"]["10"] == 2 and q[p[0]]["distribuicao"]["5"] == 0
    assert len(q[p[0]]["distribuicao"]) == 11
    assert q[p[0]]["media"] == 7.1
    assert q[p[1]]["opcoes"] == {"Preço": 1, "Prazo": 3, "Mix": 0} and q[p[1]]["respostas"] == 3
    assert q[p[2]]["opcoes"] == {"Sim": 7, "Não": 3}
    assert [t["texto"] for t in q[p[3]]["textos"]] == ["texto 2", "texto 1", "texto 0"]


def test_csat_percentual_e_media(client, admin):
    h = admin["h"]
    f = criar_form(client, h, [{"tipo": "csat", "titulo": "Como foi?", "obrigatoria": True}])
    pid = f["perguntas"][0]["id"]
    for n in [5, 5, 4, 3, 1, 2]:  # 3 satisfeitos de 6 = 50%, média 3,33
        assert responder_link(client, f["codigo_publico"], {pid: n}).status_code == 201
    r = client.get(f"{API}/formularios/{f['id']}/resultados", headers=h).json()
    assert r["csat"] == {"percentual": 50.0, "media": 3.33}
    assert "nps" not in r
    assert r["perguntas"][0]["distribuicao"] == {"1": 1, "2": 1, "3": 1, "4": 1, "5": 2}


def test_filtro_de_periodo(client, admin, dono):
    h = admin["h"]
    f = criar_form(client, h, [NPS])
    pid = f["perguntas"][0]["id"]
    responder_link(client, f["codigo_publico"], {pid: 10})
    responder_link(client, f["codigo_publico"], {pid: 0})
    sql(dono, "update respostas set criada_em = '2025-01-15 12:00-03' where nota = 0")
    r = client.get(f"{API}/formularios/{f['id']}/resultados?de=2025-01-01&ate=2025-01-31", headers=h).json()
    assert r["total"] == 1 and r["nps"]["valor"] == -100
    assert r["perguntas"][0]["respostas"] == 1
    lista = client.get(f"{API}/formularios/{f['id']}/respostas?de=2025-02-01", headers=h).json()
    assert lista["total"] == 1 and lista["itens"][0]["nota"] == 10
    r = client.get(f"{API}/formularios/{f['id']}/resultados?de=15-01-2025", headers=h)
    assert r.status_code == 422


def test_sem_respostas(client, admin):
    f = criar_form(client, admin["h"], [NPS])
    r = client.get(f"{API}/formularios/{f['id']}/resultados", headers=admin["h"]).json()
    assert r["total"] == 0 and r["nps"]["valor"] is None and r["perguntas"][0]["media"] is None


def test_exportacao_csv(client, admin):
    h = admin["h"]
    f = criar_form(client, h, [NPS, {"tipo": "escolha_multipla", "titulo": "Motivos", "opcoes": ["Preço", "Prazo"]},
                               {"tipo": "comentario", "titulo": "Comentário"}], nome="Satisfação 2026")
    p = [x["id"] for x in f["perguntas"]]
    e = criar_empresa(client, h, "Atacado Norte")
    c = criar_contato(client, h, nome="Paula", email="paula@norte.com.br", empresa_id=e["id"])
    token = link_pesquisa(client, h, c["id"], formulario_id=f["id"], referencia="PED-9",
                          contexto={"pedido": "9", "transportadora": "Rápido"})
    client.post(f"{API}/publico/convites/{token}/responder",
                json={"respostas": {p[0]: 9, p[1]: ["Preço", "Prazo"], p[2]: "=HYPERLINK(\"x\")"}})
    responder_link(client, f["codigo_publico"], {p[0]: 3})
    r = client.get(f"{API}/formularios/{f['id']}/respostas.csv", headers=h)
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/csv")
    assert 'filename="respostas-satisfacao-2026.csv"' in r.headers["content-disposition"]
    assert r.content.startswith(b"\xef\xbb\xbf")
    linhas = list(csv.reader(io.StringIO(r.content.decode("utf-8-sig")), delimiter=";"))
    assert linhas[0] == ["Data", "Contato", "E-mail", "Empresa", "Canal", "Referência", "Pedido", "Nota fiscal",
                         "Rota", "Motorista", "Filial", "Transportadora",
                         "Recomendaria a Alfa Distribuidora?", "Motivos", "Comentário"]
    assert len(linhas) == 3
    convite = next(x for x in linhas[1:] if x[1] == "Paula")
    assert convite[2:7] == ["paula@norte.com.br", "Atacado Norte", "link", "PED-9", "9"]
    assert convite[11] == "Rápido"
    assert convite[12:] == ["9", "Preço, Prazo", "'=HYPERLINK(\"x\")"]
    anonima = next(x for x in linhas[1:] if x[1] == "")
    assert anonima[12] == "3" and anonima[13] == ""

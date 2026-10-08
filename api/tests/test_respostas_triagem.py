"""Triagem de Respostas (docs/api-respostas-triagem.md): "Para analisar" (nota baixa ou comentário do cliente, ainda
sem análise da equipe), "Com comentário" e os temas citados, contados sobre os outros filtros da lista."""
import pytest
from util import API, conta_pronta, criar_contato, criar_empresa, form_padrao, lista_respostas, registrar_resposta, responder_link


@pytest.fixture
def conta(client):
    a = conta_pronta(client, "ana@alfa.com.br", empresa="Alfa")
    h = a["h"]
    e = criar_empresa(client, h, "Mercado Azul")
    c = criar_contato(client, h, nome="Bia Souza", email="bia@azul.com.br", empresa_id=e["id"])
    ids = {}
    for chave, nota, comentario in (("detrator", 3, "A entrega atrasou de novo"), ("elogio", 10, "Atendimento excelente"),
                                    ("promotor", 9, None), ("neutro", 7, None)):
        r = registrar_resposta(client, h, c["id"], nota, **({"comentario": comentario} if comentario else {}))
        assert r.status_code == 201, r.text
        ids[chave] = r.json()["id"]
    csat = form_padrao(client, h, "csat")
    assert responder_link(client, csat["codigo_publico"], {csat["perguntas"][0]["id"]: 1}).status_code == 201
    return {"h": h, "ids": ids}


def test_contagens_e_temas(client, conta):
    m = lista_respostas(client, conta["h"])["metricas"]
    # para analisar: o detrator (nota baixa e comentário), o elogio (comentário) e o CSAT 1 (nota baixa)
    assert (m["para_analisar"], m["com_comentario"]) == (3, 2)
    assert m["temas"] == [
        {"chave": "prazo_entrega", "rotulo": "Prazo e entrega", "mencoes": 1, "nota_baixa": 1},
        {"chave": "atendimento", "rotulo": "Atendimento", "mencoes": 1, "nota_baixa": 0},
    ]


def test_filtros_da_triagem_e_analise(client, conta):
    h, ids = conta["h"], conta["ids"]
    d = lista_respostas(client, h, para_analisar="true")
    assert d["total"] == 3 and {x["id"] for x in d["itens"]} >= {ids["detrator"], ids["elogio"]}
    # as métricas e as contagens dos atalhos ignoram o próprio atalho (descrevem os outros filtros)
    assert d["metricas"]["para_analisar"] == 3 and d["metricas"]["com_comentario"] == 2
    assert d["metricas"]["total"] == 5 and d["metricas"]["nps"]["total"] == 4
    d = lista_respostas(client, h, com_comentario="true")
    assert {x["id"] for x in d["itens"]} == {ids["detrator"], ids["elogio"]}
    # analisar tira da fila
    r = client.patch(f"{API}/respostas/{ids['detrator']}", headers=h, json={"o_que_faltou": "Combinar o horário."})
    assert r.status_code == 200, r.text
    m = lista_respostas(client, h)["metricas"]
    assert m["para_analisar"] == 2 and m["com_comentario"] == 2
    # os outros filtros valem para as contagens
    m = lista_respostas(client, h, categoria="detrator")["metricas"]
    assert (m["para_analisar"], m["com_comentario"]) == (0, 1)
    assert [t["chave"] for t in m["temas"]] == ["prazo_entrega"]
    # arquivada sai das contagens (como da lista)
    client.post(f"{API}/respostas/{ids['elogio']}/arquivar", headers=h)
    m = lista_respostas(client, h)["metricas"]
    assert (m["para_analisar"], m["com_comentario"]) == (1, 1)
    # o CSV respeita os atalhos
    r = client.get(f"{API}/respostas.csv", headers=h, params={"para_analisar": "true"})
    assert r.status_code == 200 and r.text.count("\n") == 2  # cabeçalho + o CSAT 1


def test_sem_respostas(client):
    a = conta_pronta(client, "bia@beta.com.br", empresa="Beta")
    m = lista_respostas(client, a["h"])["metricas"]
    assert (m["para_analisar"], m["com_comentario"], m["temas"]) == (0, 0, [])

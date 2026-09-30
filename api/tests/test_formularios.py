"""Formulários: padrões, modelos, validação, nota principal e regras dos padrões."""
import pytest
from util import API, conta_pronta, criar_form, form_padrao, formularios, membro, responder_link

NPS = {"tipo": "nps", "titulo": "Quanto recomendaria?", "obrigatoria": True}
CSAT = {"tipo": "csat", "titulo": "Como foi?", "obrigatoria": True}


@pytest.fixture
def admin(client):
    return conta_pronta(client, "ana@alfa.com.br", empresa="Alfa Distribuidora")


def test_conta_nova_recebe_formularios_padrao(client, admin):
    fs = formularios(client, admin["h"])
    assert set(fs) == {"Pesquisa NPS", "Satisfação pós-entrega"}
    nps, csat = fs["Pesquisa NPS"], fs["Satisfação pós-entrega"]
    assert nps["padrao_nps"] and nps["tipo_principal"] == "nps" and not nps["padrao_csat"]
    assert csat["padrao_csat"] and csat["tipo_principal"] == "csat"
    assert len(nps["codigo_publico"]) == 8 and nps["ativo"] and nps["publico"]
    assert "perguntas" not in nps  # lista resumida
    completo = client.get(f"{API}/formularios/{csat['id']}", headers=admin["h"]).json()
    p0 = completo["perguntas"][0]
    assert p0["titulo"] == "Como foi a entrega do seu pedido {referencia}?"
    assert all(p["id"].startswith("p_") and len(p["id"]) == 8 for p in completo["perguntas"])
    assert completo["perguntas"][2]["condicao"] == {"tipo": "grupo", "grupos": ["insatisfeito", "neutro"]}


def test_modelos(client, admin):
    ms = client.get(f"{API}/formularios/modelos", headers=admin["h"]).json()
    assert [m["chave"] for m in ms] == ["nps_simples", "pos_entrega", "pos_atendimento", "nps_distribuidora",
                                        "pesquisa_rapida", "em_branco"]
    pos = next(m for m in ms if m["chave"] == "pos_atendimento")
    assert pos["perguntas"][1]["tipo"] == "escala" and (pos["perguntas"][1]["min"], pos["perguntas"][1]["max"]) == (1, 7)
    f = client.post(f"{API}/formularios", headers=admin["h"], json={"nome": "Distribuidora", "modelo": "nps_distribuidora"})
    assert f.status_code == 201 and f.json()["tipo_principal"] == "nps"
    assert len(f.json()["perguntas"]) == 4
    vazio = client.post(f"{API}/formularios", headers=admin["h"], json={"nome": "Branco", "modelo": "em_branco"}).json()
    assert vazio["perguntas"] == [] and vazio["tipo_principal"] == "personalizado"


@pytest.mark.parametrize("perguntas,esperado", [
    ([NPS, CSAT], "nps"),
    ([CSAT, NPS], "nps"),
    ([{"tipo": "estrelas", "titulo": "Estrelas"}, CSAT], "csat"),
    ([{"tipo": "escala", "titulo": "Escala", "min": 1, "max": 7}], "personalizado"),
    ([{"tipo": "texto_curto", "titulo": "Nome"}], "personalizado"),
])
def test_tipo_principal(client, admin, perguntas, esperado):
    assert criar_form(client, admin["h"], perguntas)["tipo_principal"] == esperado


def test_ids_gerados_e_mantidos(client, admin):
    h = admin["h"]
    f = criar_form(client, h, [NPS, {"tipo": "comentario", "titulo": "Por quê?"}])
    ids = [p["id"] for p in f["perguntas"]]
    assert len(set(ids)) == 2
    novas = f["perguntas"] + [{"tipo": "sim_nao", "titulo": "Voltaria a comprar?"}]
    novas[1]["titulo"] = "Por que essa nota?"
    f2 = client.patch(f"{API}/formularios/{f['id']}", headers=h, json={"perguntas": novas}).json()
    assert [p["id"] for p in f2["perguntas"]][:2] == ids
    assert f2["perguntas"][1]["titulo"] == "Por que essa nota?"


def _erro(client, h, perguntas):
    r = client.post(f"{API}/formularios", headers=h, json={"nome": "X", "perguntas": perguntas})
    assert r.status_code == 422, r.text
    return r.json()["erro"]["campos"]


def test_condicao_so_depois_da_nota_principal(client, admin):
    cond = {"tipo": "grupo", "grupos": ["detrator"]}
    campos = _erro(client, admin["h"], [{"tipo": "comentario", "titulo": "Antes", "condicao": cond}, NPS])
    assert "perguntas.0.condicao" in campos
    campos = _erro(client, admin["h"], [{"tipo": "comentario", "titulo": "Sem nota", "condicao": cond}])
    assert "perguntas.0.condicao" in campos
    # grupo de CSAT numa pesquisa NPS
    campos = _erro(client, admin["h"], [NPS, {"tipo": "comentario", "titulo": "X",
                                              "condicao": {"tipo": "grupo", "grupos": ["satisfeito"]}}])
    assert "perguntas.1.condicao" in campos
    campos = _erro(client, admin["h"], [CSAT, {"tipo": "comentario", "titulo": "X",
                                               "condicao": {"tipo": "nota", "operador": "<=", "valor": 9}}])
    assert "perguntas.1.condicao" in campos
    ok = criar_form(client, admin["h"], [NPS, {"tipo": "comentario", "titulo": "X",
                                               "condicao": {"tipo": "nota", "operador": "<=", "valor": 6}}])
    assert ok["perguntas"][1]["condicao"] == {"tipo": "nota", "operador": "<=", "valor": 6}


def test_validacoes_de_perguntas(client, admin):
    h = admin["h"]
    assert "perguntas.0.titulo" in _erro(client, h, [{"tipo": "nps", "titulo": "  "}])
    assert "perguntas.0.tipo" in _erro(client, h, [{"tipo": "matriz", "titulo": "X"}])
    assert "perguntas.0.opcoes" in _erro(client, h, [{"tipo": "escolha_unica", "titulo": "X", "opcoes": ["Só uma"]}])
    assert "perguntas.0.opcoes" in _erro(client, h, [{"tipo": "escolha_multipla", "titulo": "X", "opcoes": ["A", "a"]}])
    assert "perguntas.0.opcoes" in _erro(client, h, [{"tipo": "escolha_unica", "titulo": "X",
                                                      "opcoes": [str(i) for i in range(31)]}])
    assert "perguntas.0.max" in _erro(client, h, [{"tipo": "escala", "titulo": "X", "min": 1, "max": 11}])
    assert "perguntas.0.min" in _erro(client, h, [{"tipo": "escala", "titulo": "X", "min": 2, "max": 5}])
    assert "perguntas.0.formato" in _erro(client, h, [{"tipo": "texto_curto", "titulo": "X", "formato": "cpf"}])
    assert "perguntas.1.id" in _erro(client, h, [{**NPS, "id": "p_a"}, {"tipo": "comentario", "titulo": "Y", "id": "p_a"}])
    muitas = [{"tipo": "sim_nao", "titulo": f"P{i}"} for i in range(61)]
    assert "perguntas" in _erro(client, h, muitas)
    r = client.post(f"{API}/formularios", headers=h, json={"nome": "X", "tema": {"cor": "azul"}})
    assert r.status_code == 422 and "tema.cor" in r.json()["erro"]["campos"]


def test_quebras_de_pagina_limpas_e_faixas_fixas(client, admin):
    q = {"tipo": "quebra_pagina", "titulo": ""}
    f = criar_form(client, admin["h"], [q, NPS, q, q, {"tipo": "comentario", "titulo": "X"}, q],
                   tema={"cor": "#FF0000", "modo": "paginas"})
    assert [p["tipo"] for p in f["perguntas"]] == ["nps", "quebra_pagina", "comentario"]
    assert (f["perguntas"][0]["min"], f["perguntas"][0]["max"]) == (0, 10)
    assert f["tema"]["cor"] == "#ff0000" and f["tema"]["modo"] == "paginas"
    assert f["tema"]["titulo_final"] == "Obrigado!"


def test_regras_do_padrao(client, admin):
    h = admin["h"]
    nps = form_padrao(client, h, "nps")
    r = client.patch(f"{API}/formularios/{nps['id']}", headers=h, json={"ativo": False})
    assert r.status_code == 409 and r.json()["erro"]["codigo"] == "formulario_padrao"
    assert client.delete(f"{API}/formularios/{nps['id']}", headers=h).status_code == 409
    r = client.patch(f"{API}/formularios/{nps['id']}", headers=h, json={"perguntas": [CSAT]})
    assert r.status_code == 409
    # pode mudar texto mantendo NPS
    r = client.patch(f"{API}/formularios/{nps['id']}", headers=h, json={"nome": "NPS trimestral", "publico": False})
    assert r.status_code == 200 and r.json()["nome"] == "NPS trimestral" and r.json()["publico"] is False

    novo = criar_form(client, h, [NPS])
    r = client.post(f"{API}/formularios/{novo['id']}/padrao", headers=h, json={"uso": "csat"})
    assert r.status_code == 409  # não tem CSAT
    r = client.post(f"{API}/formularios/{novo['id']}/padrao", headers=h, json={"uso": "nps"})
    assert r.status_code == 200 and r.json()["padrao_nps"] is True
    antigo = client.get(f"{API}/formularios/{nps['id']}", headers=h).json()
    assert antigo["padrao_nps"] is False
    # agora o antigo pode ser desativado
    assert client.patch(f"{API}/formularios/{nps['id']}", headers=h, json={"ativo": False}).status_code == 200
    padroes = [f for f in formularios(client, h).values() if f["padrao_nps"]]
    assert len(padroes) == 1


def test_duplicar_excluir_arquivar_novo_codigo(client, admin):
    h = admin["h"]
    f = criar_form(client, h, [NPS])
    d = client.post(f"{API}/formularios/{f['id']}/duplicar", headers=h).json()
    assert d["nome"] == "Cópia de Pesquisa teste" and d["codigo_publico"] != f["codigo_publico"]
    assert [p["id"] for p in d["perguntas"]] == [p["id"] for p in f["perguntas"]]
    assert client.delete(f"{API}/formularios/{d['id']}", headers=h).status_code == 204
    assert client.get(f"{API}/formularios/{d['id']}", headers=h).status_code == 404

    # com respostas: arquiva
    assert responder_link(client, f["codigo_publico"], {f["perguntas"][0]["id"]: 10}).status_code == 201
    antigo = f["codigo_publico"]
    novo = client.post(f"{API}/formularios/{f['id']}/novo-codigo", headers=h).json()["codigo_publico"]
    assert novo != antigo
    assert client.get(f"{API}/publico/formularios/{antigo}").status_code == 404
    assert client.get(f"{API}/publico/formularios/{novo}").status_code == 200
    assert client.delete(f"{API}/formularios/{f['id']}", headers=h).status_code == 204
    assert f["id"] not in [x["id"] for x in formularios(client, h).values()]
    assert client.get(f"{API}/publico/formularios/{novo}").status_code == 404
    eventos = [i["evento"] for i in client.get(f"{API}/auditoria", headers=h).json()["itens"]]
    assert "formulario_arquivado" in eventos and "formulario_excluido" in eventos


def test_permissoes_formularios(client, admin):
    consulta = membro(client, admin["h"], "caio@alfa.com.br", "consulta")
    f = form_padrao(client, admin["h"])
    assert client.get(f"{API}/formularios/{f['id']}", headers=consulta["h"]).status_code == 200
    assert client.get(f"{API}/formularios/{f['id']}/resultados", headers=consulta["h"]).status_code == 200
    assert client.patch(f"{API}/formularios/{f['id']}", headers=consulta["h"], json={"nome": "X"}).status_code == 403
    assert client.post(f"{API}/formularios", headers=consulta["h"], json={"nome": "X"}).status_code == 403

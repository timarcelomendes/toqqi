"""Páginas públicas: convites, link público, lógica, duplicadas e variáveis."""
import pytest
from util import API, conta_pronta, criar_contato, criar_form, form_padrao, link_pesquisa, responder_link, sql

from toqqi.core.db import em_conta
from toqqi.modelos import Formulario
from toqqi.modulos.respostas import eventos
from toqqi.modulos.respostas.convites import criar_convite
from toqqi.modulos.respostas.registro import renderizar, variaveis

NPS = {"tipo": "nps", "titulo": "De 0 a 10, quanto recomendaria a {empresa}?", "obrigatoria": True}


@pytest.fixture
def admin(client):
    return conta_pronta(client, "ana@alfa.com.br", empresa="Alfa Distribuidora")


def _logica(client, h):
    return criar_form(client, h, [
        NPS,
        {"tipo": "comentario", "titulo": "O que faltou?", "obrigatoria": True,
         "condicao": {"tipo": "grupo", "grupos": ["detrator"]}},
        {"tipo": "escolha_unica", "titulo": "Voltaria?", "opcoes": ["Sim", "Talvez"]},
        {"tipo": "texto_curto", "titulo": "Seu e-mail", "formato": "email"},
    ])


# ---- variáveis --------------------------------------------------------------

@pytest.mark.parametrize("texto,v,esperado", [
    ("Olá, {nome}!", {"nome": "Paula"}, "Olá, Paula!"),
    ("Olá, {nome}!", {"nome": ""}, "Olá!"),
    ("{nome}, como foi?", {"nome": ""}, "Como foi?"),
    ("Como foi a entrega do seu pedido {referencia}?", {"referencia": ""}, "Como foi a entrega do seu pedido?"),
    ("Como foi a entrega do seu pedido {referencia}?", {"referencia": "4521"},
     "Como foi a entrega do seu pedido 4521?"),
    ("Como você avalia {assunto}?", variaveis("Alfa"), "Como você avalia o nosso atendimento?"),
    ("Recomendaria a {empresa}?", variaveis("Alfa"), "Recomendaria a Alfa?"),
])
def test_renderizar_variaveis(texto, v, esperado):
    assert renderizar(texto, v) == esperado


def test_variaveis_primeiro_nome():
    assert variaveis("Alfa", "Paula Regina Lima")["nome"] == "Paula"


# ---- convite ----------------------------------------------------------------

def test_fluxo_do_convite(client, admin):
    h = admin["h"]
    c = criar_contato(client, h, nome="Paula Lima")
    csat = form_padrao(client, h, "csat")
    token = link_pesquisa(client, h, c["id"], formulario_id=csat["id"], referencia="4521",
                          contexto={"pedido": "4521", "motorista": "João"})
    aberto = client.get(f"{API}/publico/convites/{token}")
    assert aberto.status_code == 200
    d = aberto.json()
    assert d["ja_respondido"] is False
    assert d["variaveis"] == {"empresa": "Alfa Distribuidora", "nome": "Paula", "assunto": "o nosso atendimento",
                              "referencia": "4521"}
    assert d["formulario"]["perguntas"][0]["titulo"] == "Como foi a entrega do seu pedido 4521?"
    assert d["formulario"]["tema"]["titulo_abertura"] == "Olá, Paula!"
    p = [x["id"] for x in d["formulario"]["perguntas"]]

    # satisfeito: perguntas para insatisfeitos são descartadas
    r = client.post(f"{API}/publico/convites/{token}/responder", json={"respostas": {
        p[0]: 5, p[1]: ["Atrasou"], p[2]: "texto escondido", p[3]: "Motorista muito educado"}})
    assert r.status_code == 201, r.text
    assert r.json()["titulo_final"] == "Obrigado!"
    assert "Alfa Distribuidora" in r.json()["texto_final"]

    r = client.post(f"{API}/publico/convites/{token}/responder", json={"respostas": {p[0]: 1}})
    assert r.status_code == 409
    assert r.json()["erro"] == {"codigo": "ja_respondido", "mensagem": "Você já respondeu esta pesquisa. Obrigado!",
                                "campos": {}}
    assert client.get(f"{API}/publico/convites/{token}").json()["ja_respondido"] is True

    resp = client.get(f"{API}/formularios/{csat['id']}/respostas", headers=h).json()["itens"][0]
    assert resp["respostas"] == {p[0]: 5, p[3]: "Motorista muito educado"}
    assert resp["nota"] == 5 and resp["tipo_nota"] == "csat" and resp["grupo"] == "satisfeito"
    assert resp["canal"] == "link" and resp["referencia"] == "4521"
    assert resp["contexto"] == {"pedido": "4521", "motorista": "João"}
    assert resp["contato"]["nome"] == "Paula Lima"
    # uma única resposta extra vira só o texto do cliente
    assert resp["comentario"] == "Motorista muito educado"


def test_obrigatoria_visivel_e_validacao(client, admin):
    h = admin["h"]
    f = _logica(client, h)
    c = criar_contato(client, h)
    with em_conta(admin["conta"]["id"]) as s:
        token = criar_convite(s, f["id"], contato_id=c["id"], canal="email", assunto="o pedido 10")
    p = [x["id"] for x in f["perguntas"]]
    url = f"{API}/publico/convites/{token}/responder"
    # detrator: comentário passa a ser obrigatório
    r = client.post(url, json={"respostas": {p[0]: 3}})
    assert r.status_code == 422 and r.json()["erro"]["campos"] == {p[1]: "Responda esta pergunta."}
    # fora da faixa, opção inexistente, e-mail inválido
    r = client.post(url, json={"respostas": {p[0]: 11, p[2]: "Nunca", p[3]: "nao-e-email"}})
    campos = r.json()["erro"]["campos"]
    assert set(campos) == {p[0], p[2], p[3]}
    r = client.post(url, json={"respostas": {}})
    assert r.status_code == 422
    # principal obrigatória
    r = client.post(url, json={"respostas": {p[2]: "Sim"}})
    assert r.status_code == 422 and p[0] in r.json()["erro"]["campos"]
    # nada foi gravado e o convite continua aberto
    assert client.get(f"{API}/publico/convites/{token}").json()["ja_respondido"] is False
    r = client.post(url, json={"respostas": {p[0]: 3, p[1]: "Atraso"}})
    assert r.status_code == 201
    resp = client.get(f"{API}/formularios/{f['id']}/respostas", headers=h).json()["itens"][0]
    assert resp["canal"] == "email" and resp["grupo"] == "detrator"


def test_convite_invalido_e_formulario_desativado(client, admin):
    assert client.get(f"{API}/publico/convites/nao-existe").status_code == 404
    assert client.get(f"{API}/publico/convites/nao-existe").json()["erro"]["codigo"] == "link_invalido"
    h = admin["h"]
    f = criar_form(client, h, [NPS])
    token = link_pesquisa(client, h, criar_contato(client, h)["id"], formulario_id=f["id"])
    client.patch(f"{API}/formularios/{f['id']}", headers=h, json={"ativo": False})
    assert client.get(f"{API}/publico/convites/{token}").status_code == 404


def test_token_guardado_so_como_hash(client, admin, dono):
    h = admin["h"]
    token = link_pesquisa(client, h, criar_contato(client, h)["id"])
    guardados = [x[0] for x in sql(dono, "select token_hash from convites")]
    assert token not in guardados and len(guardados[0]) == 64


# ---- link público -----------------------------------------------------------

def test_link_publico_com_contexto_e_email_identifica_contato(client, admin):
    h = admin["h"]
    f = _logica(client, h)
    c = criar_contato(client, h, nome="Marcos", email="marcos@cliente.com.br")
    aberto = client.get(f"{API}/publico/formularios/{f['codigo_publico']}?referencia=NF 900")
    assert aberto.status_code == 200
    d = aberto.json()
    assert "ja_respondido" not in d
    assert d["formulario"]["perguntas"][0]["titulo"] == "De 0 a 10, quanto recomendaria a Alfa Distribuidora?"
    p = [x["id"] for x in f["perguntas"]]
    r = responder_link(client, f["codigo_publico"], {p[0]: 10, p[1]: "escondida", p[3]: "MARCOS@cliente.com.br"},
                       canal="qr", referencia="NF 900",
                       contexto={"pedido": "123", "rota": "Sul", "desconhecido": "x", "motorista": "J" * 200})
    assert r.status_code == 201, r.text
    resp = client.get(f"{API}/formularios/{f['id']}/respostas", headers=h).json()["itens"][0]
    assert resp["canal"] == "qr" and resp["referencia"] == "NF 900"
    assert resp["contexto"] == {"pedido": "123", "rota": "Sul", "motorista": "J" * 120}
    assert resp["contato"]["id"] == c["id"]
    assert p[1] not in resp["respostas"]
    assert client.get(f"{API}/contatos/{c['id']}", headers=h).json()["ultima_nota"] == 10
    r = responder_link(client, f["codigo_publico"], {p[0]: 9}, referencia="x" * 121)
    assert r.status_code == 422
    r = responder_link(client, f["codigo_publico"], {p[0]: 9}, canal="email")
    assert r.status_code == 422


def test_protecao_contra_duplicada(client, admin, dono):
    h = admin["h"]
    f = criar_form(client, h, [NPS])
    pid = f["perguntas"][0]["id"]
    r1 = responder_link(client, f["codigo_publico"], {pid: 8}, ip="203.0.113.7")
    r2 = responder_link(client, f["codigo_publico"], {pid: 8}, ip="203.0.113.7")
    assert r1.status_code == r2.status_code == 201 and r1.json() == r2.json()
    assert client.get(f"{API}/formularios/{f['id']}/respostas", headers=h).json()["total"] == 1
    # outra resposta do mesmo IP, ou a mesma de outro IP, é gravada
    assert responder_link(client, f["codigo_publico"], {pid: 7}, ip="203.0.113.7").status_code == 201
    assert responder_link(client, f["codigo_publico"], {pid: 8}, ip="203.0.113.8").status_code == 201
    assert client.get(f"{API}/formularios/{f['id']}/respostas", headers=h).json()["total"] == 3
    # o IP não é guardado, só o hash do dia
    ips = [x[0] for x in sql(dono, "select ip_hash from respostas")]
    assert all(len(x) == 64 and "203.0" not in x for x in ips)


def test_formulario_inativo_ou_nao_publico_404(client, admin):
    h = admin["h"]
    f = criar_form(client, h, [NPS])
    pid = f["perguntas"][0]["id"]
    client.patch(f"{API}/formularios/{f['id']}", headers=h, json={"publico": False})
    assert client.get(f"{API}/publico/formularios/{f['codigo_publico']}").status_code == 404
    assert responder_link(client, f["codigo_publico"], {pid: 9}).status_code == 404
    client.patch(f"{API}/formularios/{f['id']}", headers=h, json={"publico": True, "ativo": False})
    assert client.get(f"{API}/publico/formularios/{f['codigo_publico']}").status_code == 404
    assert client.get(f"{API}/publico/formularios/zzzzzzzz").status_code == 404
    assert client.get(f"{API}/publico/formularios/../../x").status_code == 404


def test_tipos_de_resposta(client, admin):
    f = criar_form(client, admin["h"], [
        {"tipo": "estrelas", "titulo": "Estrelas"},
        {"tipo": "escala", "titulo": "Esforço", "min": 1, "max": 7},
        {"tipo": "escolha_multipla", "titulo": "Motivos", "opcoes": ["Preço", "Prazo", "Mix"]},
        {"tipo": "sim_nao", "titulo": "Compraria de novo?"},
        {"tipo": "data", "titulo": "Data da entrega"},
        {"tipo": "texto_curto", "titulo": "Telefone", "formato": "telefone"},
        {"tipo": "texto_curto", "titulo": "Volume", "formato": "numero"},
    ])
    p = [x["id"] for x in f["perguntas"]]
    ruim = responder_link(client, f["codigo_publico"], {p[0]: 6, p[1]: 0, p[2]: ["Outro"], p[3]: "talvez",
                                                        p[4]: "31/12/2025", p[5]: "123", p[6]: "muito"})
    assert set(ruim.json()["erro"]["campos"]) == set(p)
    bom = responder_link(client, f["codigo_publico"], {p[0]: 4, p[1]: 7, p[2]: ["Mix", "Preço"], p[3]: False,
                                                       p[4]: "2025-12-31", p[5]: "(11) 3333-4444", p[6]: "12,5"})
    assert bom.status_code == 201, bom.text
    resp = client.get(f"{API}/formularios/{f['id']}/respostas", headers=admin["h"]).json()["itens"][0]
    assert resp["respostas"][p[2]] == ["Preço", "Mix"]  # na ordem das opções
    assert resp["tipo_nota"] == "csat" and resp["grupo"] == "satisfeito"
    assert "Compraria de novo? Não" in resp["comentario"]
    assert "Data da entrega: 31/12/2025" in resp["comentario"]
    assert not resp["comentario"].startswith("Estrelas")


def test_resumo_limitado(client, admin):
    f = criar_form(client, admin["h"], [NPS] + [{"tipo": "comentario", "titulo": f"Pergunta {i}"} for i in range(3)])
    p = [x["id"] for x in f["perguntas"]]
    r = responder_link(client, f["codigo_publico"], {p[0]: 9, **{x: "a" * 4000 for x in p[1:]}})
    assert r.status_code == 201
    resp = client.get(f"{API}/formularios/{f['id']}/respostas", headers=admin["h"]).json()["itens"][0]
    assert len(resp["comentario"]) == 2000


def test_ponto_unico_resposta_registrada(client, admin, monkeypatch):
    chamadas = []
    monkeypatch.setattr(eventos, "GANCHOS", [lambda s, r: chamadas.append((r.id, r.nota, r.grupo))])
    f = criar_form(client, admin["h"], [NPS])
    responder_link(client, f["codigo_publico"], {f["perguntas"][0]["id"]: 6})
    token = link_pesquisa(client, admin["h"], criar_contato(client, admin["h"])["id"], formulario_id=f["id"])
    client.post(f"{API}/publico/convites/{token}/responder", json={"respostas": {f["perguntas"][0]["id"]: 10}})
    assert [(n, g) for _, n, g in chamadas] == [(6, "detrator"), (10, "promotor")]
    assert all(i is not None for i, _, _ in chamadas)


def test_convite_criado_por_servico(client, admin):
    """Função de serviço (usada pela etapa 3) cria convite na conta da transação."""
    h = admin["h"]
    c = criar_contato(client, h, nome="Rosa")
    with em_conta(admin["conta"]["id"]) as s:
        fid = s.query(Formulario.id).filter(Formulario.padrao_nps.is_(True)).scalar()
        token = criar_convite(s, fid, contato_id=c["id"], canal="whatsapp", referencia="PED-1",
                              contexto={"filial": "Campinas", "x": "y"})
    d = client.get(f"{API}/publico/convites/{token}").json()
    assert d["variaveis"]["nome"] == "Rosa" and d["variaveis"]["referencia"] == "PED-1"

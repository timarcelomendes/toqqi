"""Etapa 4a: tela Respostas (lista, métricas, detalhe, registro à mão, análise, arquivar, excluir, CSV) e as telas
da etapa 2 usando a data da resposta."""
import csv
import io
import json
from datetime import datetime, time, timedelta

import pytest
from util import (
    API,
    FUSO,
    conta_pronta,
    criar_contato,
    criar_empresa,
    criar_form,
    criar_responsavel,
    emails_para,
    form_padrao,
    historico,
    ligar_envios,
    link_pesquisa,
    lista_respostas,
    membro,
    perfil_id,
    registrar_resposta,
    responder_convite,
    responder_link,
    sql,
)

from toqqi.core import relogio
from toqqi.core.email import caixa_memoria
from toqqi.modulos.respostas import indicadores

pytestmark = pytest.mark.usefixtures("relogio_estavel")


def hoje():
    return relogio.hoje()


@pytest.fixture
def admin(client):
    return conta_pronta(client, "ana@alfa.com.br", empresa="Alfa Distribuidora")


def _auditoria(client, h, evento):
    return [i for i in client.get(f"{API}/auditoria", headers=h).json()["itens"] if i["evento"] == evento]


# ---- registro à mão ---------------------------------------------------------

def test_registrar_resposta_a_mao(client, admin, destino, dono):
    h = admin["h"]
    ligar_envios(client, h)  # com agradecimento ligado: mesmo assim a resposta à mão não agradece
    w = client.post(f"{API}/integracoes/webhooks", headers=h,
                    json={"url": "https://erp.cliente.com.br/x", "eventos": ["resposta.criada"]}).json()
    rita = criar_responsavel(client, h, "Rita Gomes", email="rita@alfa.com.br")
    e = criar_empresa(client, h, "Atacado Norte", responsavel_id=rita["id"])
    c = criar_contato(client, h, nome="Paula Lima", email="paula@norte.com.br", telefone="11988887777",
                      empresa_id=e["id"])
    ontem = hoje() - timedelta(days=1)
    r = registrar_resposta(client, h, c["id"], 3, canal="telefone", comentario="A entrega atrasou de novo",
                           data=ontem.isoformat())
    assert r.status_code == 201, r.text
    d = r.json()
    assert (d["origem"], d["canal"], d["nota"], d["tipo_nota"], d["grupo"]) == ("manual", "telefone", 3, "nps",
                                                                                "detrator")
    assert d["registrada_por"] == {"id": admin["usuario"]["id"], "nome": admin["usuario"]["nome"]}
    assert d["comentario"] == "A entrega atrasou de novo" and d["temas"] == ["prazo_entrega"]
    esperado = datetime.combine(ontem, time(12), tzinfo=FUSO)
    assert datetime.fromisoformat(d["respondida_em"]) == esperado == datetime.fromisoformat(d["data"])
    assert d["contato"] == {"id": c["id"], "nome": "Paula Lima", "email": "paula@norte.com.br", "perfil": None}
    assert d["empresa"] == {"id": e["id"], "nome": "Atacado Norte", "grupo": None}
    nps = form_padrao(client, h)
    assert d["formulario"]["id"] == nps["id"] and d["respostas"] == {nps["perguntas"][0]["id"]: 3}
    assert d["arquivada"] is False and d["analisada_em"] is None and d["temas_manuais"] is False

    # ação automática, com o responsável da empresa
    assert d["acao"]["situacao"] == "a_fazer" and d["acao"]["prazo_selo"] is None
    acao = client.get(f"{API}/acoes/{d['acao']['id']}", headers=h).json()
    assert acao["titulo"] == "[Detrator NPS 3] Ação requerida: Atacado Norte"
    assert acao["prioridade"] == "alta" and acao["prazo"] == (hoje() + timedelta(days=2)).isoformat()
    assert acao["responsavel"]["id"] == rita["id"] and acao["origem"] == "automatica"

    # sem agradecimento; webhook entregue; alerta ao responsável
    assert historico(client, h) == []
    assert emails_para("paula@norte.com.br") == []
    assert len(destino.recebidos) == 1
    corpo = json.loads(destino.recebidos[0]["corpo"])
    assert corpo["evento"] == "resposta.criada" and corpo["dados"]["origem"] == "manual"
    assert corpo["dados"]["nota"] == 3 and corpo["dados"]["canal"] == "telefone"
    alerta, = emails_para("rita@alfa.com.br")
    assert alerta.assunto == "Alerta de risco: Atacado Norte deu nota 3"
    assert f"/planos-de-acao/{acao['id']}" in alerta.texto
    # o contato respondeu: fila e última nota atualizadas
    contato = client.get(f"{API}/contatos/{c['id']}", headers=h).json()
    assert contato["ultima_nota"] == 3
    assert contato["proximo_envio"] == (hoje() + timedelta(days=90)).isoformat()
    assert w["id"]


def test_registrar_sem_data_usa_a_entrada(client, admin):
    h = admin["h"]
    c = criar_contato(client, h)
    d = registrar_resposta(client, h, c["id"], 10).json()
    assert d["respondida_em"] is None and d["data"] == d["criada_em"] and d["canal"] == "manual"
    assert d["grupo"] == "promotor" and d["acao"] is None  # promotor: sem ação (padrão)


def test_registrar_validacoes(client, admin):
    h = admin["h"]
    c = criar_contato(client, h)

    def campos(r):
        assert r.status_code == 422, r.text
        return r.json()["erro"]["campos"]

    assert campos(registrar_resposta(client, h, 99999, 5)) == {"contato_id": "Contato não encontrado."}
    assert campos(registrar_resposta(client, h, c["id"], 11)) == {"nota": "A nota precisa ser de 0 a 10."}
    assert campos(registrar_resposta(client, h, c["id"], -1)) == {"nota": "A nota precisa ser de 0 a 10."}
    assert "nota" in campos(registrar_resposta(client, h, c["id"], 7.5))
    amanha = (hoje() + timedelta(days=1)).isoformat()
    assert campos(registrar_resposta(client, h, c["id"], 5, data=amanha)) == {
        "data": "A data não pode ser no futuro."}
    assert "data" in campos(registrar_resposta(client, h, c["id"], 5, data="1999-12-31"))
    assert "data" in campos(registrar_resposta(client, h, c["id"], 5, data="31/12/2025"))
    assert "canal" in campos(registrar_resposta(client, h, c["id"], 5, canal="qr"))
    assert "comentario" in campos(registrar_resposta(client, h, c["id"], 5, comentario="x" * 4001))
    assert lista_respostas(client, h)["total"] == 0
    for canal in ("manual", "whatsapp", "telefone", "email", "reuniao"):
        assert registrar_resposta(client, h, c["id"], 9, canal=canal).status_code == 201
    assert registrar_resposta(client, h, c["id"], 9, data="2000-01-01").status_code == 201


def test_ultima_nota_segue_a_resposta_mais_recente(client, admin):
    h = admin["h"]
    c = criar_contato(client, h)
    registrar_resposta(client, h, c["id"], 9)
    # registrada depois, mas com data antiga: não é a mais recente
    antiga = registrar_resposta(client, h, c["id"], 2, data="2024-05-10").json()
    assert client.get(f"{API}/contatos/{c['id']}", headers=h).json()["ultima_nota"] == 9
    historico_ = client.get(f"{API}/contatos/{c['id']}", headers=h).json()["historico"]
    assert [x["nota"] for x in historico_] == [9, 2]
    assert historico_[1]["id"] == antiga["id"]
    assert datetime.fromisoformat(historico_[1]["data"]) == datetime(2024, 5, 10, 12, tzinfo=FUSO)
    # mudar a nota da antiga não mexe na última nota; mudar a da mais recente, sim
    client.patch(f"{API}/respostas/{antiga['id']}", headers=h, json={"nota": 5})
    assert client.get(f"{API}/contatos/{c['id']}", headers=h).json()["ultima_nota"] == 9
    client.patch(f"{API}/respostas/{historico_[0]['id']}", headers=h, json={"nota": 7})
    assert client.get(f"{API}/contatos/{c['id']}", headers=h).json()["ultima_nota"] == 7


# ---- lista, filtros e métricas ----------------------------------------------

@pytest.fixture
def base(client, admin, dono):
    """Duas empresas (grupos diferentes), três contatos e respostas variadas."""
    h = admin["h"]
    g1 = client.post(f"{API}/cadastros/grupos", headers=h, json={"nome": "Rede Leste"}).json()
    g2 = client.post(f"{API}/cadastros/grupos", headers=h, json={"nome": "Rede Oeste"}).json()
    e1 = criar_empresa(client, h, "Atacado Norte", grupo_id=g1["id"])
    e2 = criar_empresa(client, h, "Mercado Sul", grupo_id=g2["id"])
    decisor = perfil_id(client, h, "Decisor")
    c1 = criar_contato(client, h, nome="Paula Lima", email="paula@norte.com.br", empresa_id=e1["id"],
                       perfil_id=decisor)
    c2 = criar_contato(client, h, nome="Marcos Reis", email="marcos@sul.com.br", empresa_id=e2["id"])
    c3 = criar_contato(client, h, nome="Júlia Sá", email="julia@x.com.br")
    r1 = registrar_resposta(client, h, c1["id"], 10, comentario="Atendimento excelente", data="2025-03-10").json()
    r2 = registrar_resposta(client, h, c2["id"], 3, comentario="Frete caro e atrasou", canal="reuniao",
                            data="2025-03-20").json()
    responder_convite(client, h, c3["id"], 8, comentario="Bom, mas o site é lento", referencia="PED-77")
    csat = form_padrao(client, h, "csat")
    responder_convite(client, h, c1["id"], 5, formulario=csat)
    r3 = next(x for x in lista_respostas(client, h)["itens"] if x["nota"] == 8)
    return {"h": h, "g1": g1, "g2": g2, "e1": e1, "e2": e2, "c1": c1, "c2": c2, "c3": c3, "r1": r1, "r2": r2,
            "r3": r3, "decisor": decisor, "csat": csat}


def _notas(d) -> list:
    return [x["nota"] for x in d["itens"]]


def test_lista_ordem_formato_e_metricas(client, base):
    h = base["h"]
    d = lista_respostas(client, h)
    assert d["total"] == 4 and d["pagina"] == 1
    # ordem: data da resposta (as de hoje primeiro; depois 20/03 e 10/03 de 2025)
    assert _notas(d)[2:] == [3, 10] and set(_notas(d)[:2]) == {8, 5}
    assert {k: d["metricas"][k] for k in ("nps", "csat", "total")} == {
        "nps": {"valor": 0, "faixa": "pode_melhorar", "promotores": 1, "neutros": 1, "detratores": 1, "total": 3},
        "csat": {"percentual": 100, "media": 5.0, "total": 1},
        "total": 4,
    }  # os atalhos da triagem (para analisar, com comentário, temas) estão em test_respostas_triagem.py
    r1 = next(x for x in d["itens"] if x["id"] == base["r1"]["id"])
    assert r1["contato"]["perfil"] == {"id": base["decisor"], "nome": "Decisor"}
    assert r1["empresa"]["grupo"] == {"id": base["g1"]["id"], "nome": "Rede Leste"}
    assert r1["temas"] == ["atendimento"] and r1["origem"] == "manual"
    r3 = next(x for x in d["itens"] if x["nota"] == 8)
    assert r3["origem"] == "pesquisa" and r3["canal"] == "link" and r3["referencia"] == "PED-77"
    assert r3["temas"] == ["sistema_pedidos"] and r3["registrada_por"] is None
    assert r3["acao"]["situacao"] == "a_fazer"  # neutro também gera ação
    paginado = client.get(f"{API}/respostas", headers=h, params={"por_pagina": 1, "pagina": 2}).json()
    assert paginado["total"] == 4 and len(paginado["itens"]) == 1 and paginado["metricas"]["total"] == 4


@pytest.mark.parametrize("filtros,notas", [
    ({"categoria": "detrator"}, [3]),
    ({"categoria": "satisfeito"}, [5]),
    ({"tipo_nota": "csat"}, [5]),
    ({"tipo_nota": "nps"}, [8, 3, 10]),
    ({"tema": "prazo_entrega"}, [3]),
    ({"tema": "atendimento"}, [10]),
    ({"canal": "reuniao"}, [3]),
    ({"origem": "pesquisa"}, None),  # as duas de pesquisa
    ({"origem": "manual"}, [3, 10]),
    ({"busca": "paula"}, None),  # contato: as duas da Paula
    ({"busca": "sul.com"}, [3]),  # e-mail do contato
    ({"busca": "mercado"}, [3]),  # empresa
    ({"busca": "site é lento"}, [8]),  # comentário
    ({"busca": "PED-7"}, [8]),  # referência
    ({"de": "2025-03-01", "ate": "2025-03-15"}, [10]),
    ({"de": "2025-03-15", "ate": "2025-03-31"}, [3]),
    ({"de": "2025-03-01", "ate": "2025-03-31", "data_por": "entrada"}, []),
    ({"categoria": "", "tema": "", "de": ""}, None),  # vazios são ignorados
])
def test_filtros(client, base, filtros, notas):
    d = lista_respostas(client, base["h"], **filtros)
    if notas is not None:
        assert _notas(d) == notas, filtros
    elif filtros.get("origem") == "pesquisa":
        assert sorted(_notas(d)) == [5, 8]
    elif filtros.get("busca") == "paula":
        assert sorted(_notas(d)) == [5, 10]
    else:
        assert d["total"] == 4


def test_filtros_por_id(client, base):
    h = base["h"]
    assert _notas(lista_respostas(client, h, grupo_id=base["g2"]["id"])) == [3]
    assert sorted(_notas(lista_respostas(client, h, empresa_id=base["e1"]["id"]))) == [5, 10]
    assert sorted(_notas(lista_respostas(client, h, contato_id=base["c1"]["id"]))) == [5, 10]
    assert sorted(_notas(lista_respostas(client, h, perfil_id=base["decisor"]))) == [5, 10]
    assert _notas(lista_respostas(client, h, formulario_id=base["csat"]["id"])) == [5]
    d = lista_respostas(client, h, data_por="entrada", de=hoje().isoformat(), ate=hoje().isoformat())
    assert d["total"] == 4  # todas entraram hoje
    for filtros in ({"categoria": "otimo"}, {"tema": "outro"}, {"data_por": "x"}, {"arquivadas": "nao"},
                    {"de": "10/03/2025"}, {"canal": "fax"}):
        r = client.get(f"{API}/respostas", headers=h, params=filtros)
        assert r.status_code == 422, filtros


def test_nps_arredonda_meio_para_longe_do_zero(client, admin):
    assert indicadores.nps(3, 2, 8) == 13      # 12,5
    assert indicadores.nps(2, 3, 8) == -13     # −12,5
    assert indicadores.nps(1, 0, 3) == 33 and indicadores.nps(2, 0, 3) == 67
    assert indicadores.percentual(1, 8) == 13 and indicadores.percentual(1, 3, 1) == 33.3
    assert indicadores.faixa(75) == "excelente" and indicadores.faixa(50) == "muito_bom"
    assert indicadores.faixa(0) == "pode_melhorar" and indicadores.faixa(-1) == "critico"
    h = admin["h"]
    c = criar_contato(client, h)
    for nota in (10, 9, 9, 8, 7, 7, 3, 0):  # 3 promotores, 3 neutros, 2 detratores
        registrar_resposta(client, h, c["id"], nota)
    assert lista_respostas(client, h)["metricas"]["nps"]["valor"] == 13
    c2 = criar_contato(client, h)
    for nota in (10, 10, 8, 8, 8, 6, 6, 6):
        registrar_resposta(client, h, c2["id"], nota)
    assert lista_respostas(client, h, contato_id=c2["id"])["metricas"]["nps"]["valor"] == -13


def test_csat_percentual_inteiro(client, admin):
    h = admin["h"]
    csat = form_padrao(client, h, "csat")
    pid = csat["perguntas"][0]["id"]
    for n in (5, 4, 4, 3, 2, 1, 5, 2):  # 4 de 8 satisfeitos = 50%; média 26/8 = 3,25
        assert responder_link(client, csat["codigo_publico"], {pid: n}).status_code == 201
    d = lista_respostas(client, h)
    assert {k: d["metricas"][k] for k in ("nps", "csat", "total")} == {
        "nps": None, "csat": {"percentual": 50, "media": 3.25, "total": 8}, "total": 8}
    # 1 de 8 satisfeitos = 12,5% → 13 (meio para cima)
    d = lista_respostas(client, h, categoria="", busca="")
    assert indicadores.percentual(1, 8) == 13 and d["total"] == 8


# ---- detalhe ----------------------------------------------------------------

def test_detalhe_com_perguntas_convite_e_acoes(client, admin):
    h = admin["h"]
    f = criar_form(client, h, [
        {"tipo": "nps", "titulo": "Recomendaria a {empresa}?", "obrigatoria": True},
        {"tipo": "sim_nao", "titulo": "Compraria de novo?"},
        {"tipo": "data", "titulo": "Quando foi a entrega?"},
        {"tipo": "comentario", "titulo": "Algo mais, {nome}?"},
    ])
    p = [x["id"] for x in f["perguntas"]]
    c = criar_contato(client, h, nome="Paula Lima")
    token = link_pesquisa(client, h, c["id"], formulario_id=f["id"], referencia="NF 9", assunto="o pedido 9",
                          contexto={"pedido": "9", "motorista": "Zé"})
    client.post(f"{API}/publico/convites/{token}/responder",
                json={"respostas": {p[0]: 4, p[1]: True, p[2]: "2025-12-31"}})
    item = lista_respostas(client, h)["itens"][0]
    d = client.get(f"{API}/respostas/{item['id']}", headers=h).json()
    assert d["perguntas"] == [
        {"id": p[0], "titulo": "Recomendaria a Alfa Distribuidora?", "tipo": "nps", "resposta": "4"},
        {"id": p[1], "titulo": "Compraria de novo?", "tipo": "sim_nao", "resposta": "Sim"},
        {"id": p[2], "titulo": "Quando foi a entrega?", "tipo": "data", "resposta": "31/12/2025"},
        {"id": p[3], "titulo": "Algo mais, Paula?", "tipo": "comentario", "resposta": None},
    ]
    assert d["convite"] == {"evento": None, "referencia": "NF 9", "assunto": "o pedido 9"}
    assert d["contexto"] == {"pedido": "9", "motorista": "Zé"}
    assert [a["id"] for a in d["acoes"]] == [d["acao"]["id"]]
    assert d["acoes"][0]["titulo"].startswith("[Detrator NPS 4]")
    # ação manual ligada à mesma resposta: a da lista continua sendo a automática
    nova = client.post(f"{API}/acoes", headers=h, json={"titulo": "Ligar", "resposta_id": d["id"]}).json()
    d2 = client.get(f"{API}/respostas/{d['id']}", headers=h).json()
    assert d2["acao"]["id"] == d["acao"]["id"] and [a["id"] for a in d2["acoes"]] == [d["acao"]["id"], nova["id"]]
    assert client.get(f"{API}/respostas/99999", headers=h).status_code == 404


# ---- análise ----------------------------------------------------------------

def test_analisar_nota_comentario_e_temas(client, admin):
    h = admin["h"]
    c = criar_contato(client, h)
    d = registrar_resposta(client, h, c["id"], 9, comentario="Tudo certo").json()
    acao_antes = d["acao"]
    assert d["temas"] == [] and acao_antes is None
    url = f"{API}/respostas/{d['id']}"

    r = client.patch(url, headers=h, json={"nota": 4, "comentario": "O boleto veio errado"})
    assert r.status_code == 200, r.text
    x = r.json()
    assert (x["nota"], x["grupo"], x["temas"], x["temas_manuais"]) == (4, "detrator", ["preco_condicoes"], False)
    assert x["analisada_por"]["id"] == admin["usuario"]["id"] and x["analisada_em"]
    assert x["acao"] is None  # a ação já criada (ou não criada) não muda
    nps = form_padrao(client, h)
    assert x["respostas"] == {nps["perguntas"][0]["id"]: 4}
    assert client.get(f"{API}/contatos/{c['id']}", headers=h).json()["ultima_nota"] == 4

    # "o que faltou" também entra nos temas
    x = client.patch(url, headers=h, json={"o_que_faltou": "Retorno do vendedor"}).json()
    assert x["temas"] == ["atendimento", "preco_condicoes", "comunicacao"]
    # temas escolhidos à mão valem e não são mais recalculados
    x = client.patch(url, headers=h, json={"temas": ["sistema_pedidos", "atendimento", "atendimento"],
                                           "o_que_combinamos": "Trocar o boleto até sexta"}).json()
    assert (x["temas"], x["temas_manuais"]) == (["atendimento", "sistema_pedidos"], True)
    x = client.patch(url, headers=h, json={"comentario": "Frete caro"}).json()
    assert x["temas"] == ["atendimento", "sistema_pedidos"] and x["o_que_combinamos"] == "Trocar o boleto até sexta"
    # limpar campos opcionais
    x = client.patch(url, headers=h, json={"o_que_faltou": None, "o_que_combinamos": ""}).json()
    assert x["o_que_faltou"] is None and x["o_que_combinamos"] is None

    eventos = _auditoria(client, h, "resposta_editada")
    assert len(eventos) == 2  # nota+comentário e só comentário; temas/campos de análise não auditam
    assert eventos[-1]["detalhe"] == {"resposta_id": d["id"], "antes": {"nota": 9}, "depois": {"nota": 4},
                                      "comentario_alterado": True}
    assert eventos[0]["detalhe"]["antes"] == eventos[0]["detalhe"]["depois"] == {"nota": 4}


def test_analisar_validacoes(client, admin):
    h = admin["h"]
    c = criar_contato(client, h)
    d = registrar_resposta(client, h, c["id"], 9).json()
    url = f"{API}/respostas/{d['id']}"
    r = client.patch(url, headers=h, json={"nota": 11})
    assert r.status_code == 422 and r.json()["erro"]["campos"] == {"nota": "A nota precisa ser de 0 a 10."}
    assert client.patch(url, headers=h, json={"temas": ["inventado"]}).status_code == 422
    assert client.patch(url, headers=h, json={"o_que_faltou": "x" * 2001}).status_code == 422
    # CSAT: 1 a 5
    csat = form_padrao(client, h, "csat")
    responder_convite(client, h, c["id"], 4, formulario=csat)
    item = lista_respostas(client, h, tipo_nota="csat")["itens"][0]
    r = client.patch(f"{API}/respostas/{item['id']}", headers=h, json={"nota": 0})
    assert r.status_code == 422 and r.json()["erro"]["campos"] == {"nota": "A nota precisa ser de 1 a 5."}
    r = client.patch(f"{API}/respostas/{item['id']}", headers=h, json={"nota": 2})
    assert r.json()["grupo"] == "insatisfeito"
    # formulário sem nota: 422 ao mudar a nota
    f = criar_form(client, h, [{"tipo": "comentario", "titulo": "Diga", "obrigatoria": True}])
    responder_link(client, f["codigo_publico"], {f["perguntas"][0]["id"]: "Oi"})
    sem_nota = lista_respostas(client, h, formulario_id=f["id"])["itens"][0]
    r = client.patch(f"{API}/respostas/{sem_nota['id']}", headers=h, json={"nota": 5})
    assert r.status_code == 422 and r.json()["erro"]["campos"] == {"nota": "Esta resposta não tem nota."}
    assert client.patch(f"{API}/respostas/99999", headers=h, json={"nota": 5}).status_code == 404


# ---- arquivar, restaurar e excluir ------------------------------------------

def test_arquivada_sai_dos_indicadores(client, admin):
    h = admin["h"]
    c = criar_contato(client, h)
    registrar_resposta(client, h, c["id"], 10, data="2025-01-10")
    d = registrar_resposta(client, h, c["id"], 0).json()
    assert lista_respostas(client, h)["metricas"]["nps"]["valor"] == 0
    r = client.post(f"{API}/respostas/{d['id']}/arquivar", headers=h)
    assert r.status_code == 200 and r.json()["arquivada"] is True and r.json()["arquivada_em"]
    padrao = lista_respostas(client, h)
    assert padrao["total"] == 1 and padrao["metricas"]["nps"]["valor"] == 100
    assert [x["id"] for x in lista_respostas(client, h, arquivadas="true")["itens"]] == [d["id"]]
    assert lista_respostas(client, h, arquivadas="todas")["total"] == 2
    assert client.get(f"{API}/contatos/{c['id']}", headers=h).json()["ultima_nota"] == 10
    assert client.get(f"{API}/painel", headers=h).json()["nps"]["total"] == 1
    nps = form_padrao(client, h)
    assert client.get(f"{API}/formularios/{nps['id']}/resultados", headers=h).json()["total"] == 1
    r = client.post(f"{API}/respostas/{d['id']}/restaurar", headers=h)
    assert r.json()["arquivada"] is False and r.json()["arquivada_em"] is None
    assert lista_respostas(client, h)["total"] == 2
    assert client.get(f"{API}/contatos/{c['id']}", headers=h).json()["ultima_nota"] == 0


def test_excluir_so_admin_e_apaga_acoes(client, admin, dono):
    h = admin["h"]
    gestor = membro(client, h, "gil@alfa.com.br", "gestor")
    c = criar_contato(client, h, nome="Paula Lima")
    registrar_resposta(client, h, c["id"], 9, data="2025-01-10")
    d = registrar_resposta(client, h, c["id"], 2).json()
    manual = client.post(f"{API}/acoes", headers=h, json={"titulo": "Visitar", "resposta_id": d["id"]}).json()
    outra = client.post(f"{API}/acoes", headers=h, json={"titulo": "Sem resposta"}).json()
    url = f"{API}/respostas/{d['id']}"
    r = client.delete(url, headers=gestor["h"])
    assert r.status_code == 403
    assert client.delete(url, headers=h).status_code == 204
    assert client.get(url, headers=h).status_code == 404
    assert client.get(f"{API}/acoes/{d['acao']['id']}", headers=h).status_code == 404
    assert client.get(f"{API}/acoes/{manual['id']}", headers=h).status_code == 404
    assert client.get(f"{API}/acoes/{outra['id']}", headers=h).status_code == 200
    assert client.get(f"{API}/contatos/{c['id']}", headers=h).json()["ultima_nota"] == 9
    ev, = _auditoria(client, h, "resposta_excluida")
    assert ev["gravidade"] == "atencao" and ev["rotulo"] == "Resposta excluída"
    assert ev["detalhe"] == {"resposta_id": d["id"], "contato": {"id": c["id"], "nome": "Paula Lima"}, "nota": 2,
                             "acoes_apagadas": 2}
    assert client.delete(url, headers=h).status_code == 404


def test_permissoes(client, admin):
    h = admin["h"]
    consulta = membro(client, h, "caio@alfa.com.br", "consulta")
    gestor = membro(client, h, "gil@alfa.com.br", "gestor")
    c = criar_contato(client, h)
    d = registrar_resposta(client, h, c["id"], 5).json()
    hc, hg = consulta["h"], gestor["h"]
    assert client.get(f"{API}/respostas", headers=hc).status_code == 200
    assert client.get(f"{API}/respostas/{d['id']}", headers=hc).status_code == 200
    assert registrar_resposta(client, hc, c["id"], 5).status_code == 403
    assert client.patch(f"{API}/respostas/{d['id']}", headers=hc, json={"nota": 6}).status_code == 403
    assert client.post(f"{API}/respostas/{d['id']}/arquivar", headers=hc).status_code == 403
    assert client.delete(f"{API}/respostas/{d['id']}", headers=hc).status_code == 403
    assert client.get(f"{API}/respostas.csv", headers=hc).status_code == 403  # sem painel.exportar
    assert client.patch(f"{API}/respostas/{d['id']}", headers=hg, json={"nota": 6}).status_code == 200
    assert registrar_resposta(client, hg, c["id"], 5).status_code == 201
    assert client.post(f"{API}/respostas/{d['id']}/arquivar", headers=hg).status_code == 200
    assert client.get(f"{API}/respostas.csv", headers=hg).status_code == 200
    assert client.delete(f"{API}/respostas/{d['id']}", headers=hg).status_code == 403


# ---- CSV ----------------------------------------------------------------------

def test_csv(client, base, admin):
    h = base["h"]
    client.patch(f"{API}/respostas/{base['r2']['id']}", headers=h,
                 json={"o_que_faltou": "=1+1", "o_que_combinamos": "Desconto no próximo pedido"})
    client.post(f"{API}/respostas/{base['r1']['id']}/arquivar", headers=h)
    r = client.get(f"{API}/respostas.csv", headers=h, params={"tipo_nota": "nps", "arquivadas": "todas"})
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/csv")
    assert 'filename="respostas-' in r.headers["content-disposition"]
    assert r.content.startswith(b"\xef\xbb\xbf")
    linhas = list(csv.reader(io.StringIO(r.content.decode("utf-8-sig")), delimiter=";"))
    assert linhas[0] == ["Data", "Contato", "E-mail", "Empresa", "Grupo de empresas", "Perfil", "Tipo", "Nota",
                         "Categoria", "Temas", "Comentário", "O que faltou", "O que combinamos", "Canal", "Origem",
                         "Referência", "Pedido", "Nota fiscal", "Rota", "Motorista", "Filial", "Transportadora",
                         "Arquivada", "Sentimento", "Resumo da IA"]
    assert len(linhas) == 4
    marcos = next(x for x in linhas[1:] if x[1] == "Marcos Reis")
    assert marcos == ["20/03/2025 12:00", "Marcos Reis", "marcos@sul.com.br", "Mercado Sul", "Rede Oeste", "",
                      "NPS", "3", "Detrator", "Prazo e entrega, Preço e condições", "Frete caro e atrasou", "'=1+1",
                      "Desconto no próximo pedido", "Reunião", "Registrada à mão", "", "", "", "", "", "", "", "Não",
                      "Negativo", "Frete caro e atrasou"]  # análise da IA (provedor de testes)
    paula = next(x for x in linhas[1:] if x[1] == "Paula Lima")
    assert paula[5] == "Decisor" and paula[22] == "Sim"
    so_padrao = client.get(f"{API}/respostas.csv", headers=h).content.decode("utf-8-sig")
    assert "Paula Lima;" in so_padrao and so_padrao.count("\r\n") == 4  # arquivada fora; CSAT da Paula entra


# ---- telas da etapa 2 pela data da resposta ---------------------------------

def test_resultados_e_respostas_do_formulario_pela_data_da_resposta(client, admin):
    h = admin["h"]
    c = criar_contato(client, h)
    nps = form_padrao(client, h)
    responder_convite(client, h, c["id"], 10)
    registrar_resposta(client, h, c["id"], 0, data="2025-01-15")
    r = client.get(f"{API}/formularios/{nps['id']}/resultados?de=2025-01-01&ate=2025-01-31", headers=h).json()
    assert r["total"] == 1 and r["nps"]["valor"] == -100
    lista = client.get(f"{API}/formularios/{nps['id']}/respostas", headers=h).json()
    assert [x["nota"] for x in lista["itens"]] == [10, 0]
    assert datetime.fromisoformat(lista["itens"][1]["data"]) == datetime(2025, 1, 15, 12, tzinfo=FUSO)
    assert lista["itens"][1]["origem"] == "manual"
    csv_ = client.get(f"{API}/formularios/{nps['id']}/respostas.csv", headers=h).content.decode("utf-8-sig")
    assert "15/01/2025 12:00" in csv_
    caixa_memoria.clear()


# ---- rodada de revisão --------------------------------------------------------

def test_registrar_com_a_data_de_hoje_usa_a_hora_real(client, admin):
    """A tela sempre manda a data de hoje: vale a hora real de entrada (12:00 poderia ficar no futuro)."""
    h = admin["h"]
    c = criar_contato(client, h)
    d = registrar_resposta(client, h, c["id"], 9, data=hoje().isoformat()).json()
    assert d["respondida_em"] is None and d["data"] == d["criada_em"]
    ontem = registrar_resposta(client, h, c["id"], 3, data=(hoje() - timedelta(days=1)).isoformat()).json()
    assert datetime.fromisoformat(ontem["respondida_em"]) == datetime.combine(hoje() - timedelta(days=1), time(12),
                                                                               tzinfo=FUSO)
    assert client.get(f"{API}/contatos/{c['id']}", headers=h).json()["ultima_nota"] == 9  # a de hoje é a mais recente


def test_filtro_so_ativos(client, admin):
    h = admin["h"]
    ativa = criar_empresa(client, h, "Ativa")
    inativa = criar_empresa(client, h, "Inativa", ativa=False)
    for empresa, nota in ((ativa, 10), (inativa, 0), (None, 7)):
        c = criar_contato(client, h, empresa_id=empresa["id"] if empresa else None)
        registrar_resposta(client, h, c["id"], nota)
    assert sorted(_notas(lista_respostas(client, h))) == [0, 7, 10]  # padrão: todas
    assert sorted(_notas(lista_respostas(client, h, so_ativos="false"))) == [0, 7, 10]
    d = lista_respostas(client, h, so_ativos="true")
    assert sorted(_notas(d)) == [7, 10] and d["metricas"]["nps"]["total"] == 2  # sem empresa sempre conta
    csv_ = client.get(f"{API}/respostas.csv", headers=h, params={"so_ativos": "true"}).content.decode("utf-8-sig")
    assert csv_.count("\r\n") == 3 and "Inativa" not in csv_
    assert client.get(f"{API}/respostas", headers=h, params={"so_ativos": "talvez"}).status_code == 422


@pytest.mark.parametrize("url,params,campo", [
    ("/respostas", {"ate": "9999-12-31"}, "ate"),
    ("/respostas", {"de": "1999-12-31"}, "de"),
    ("/respostas.csv", {"ate": "9999-12-31"}, "ate"),
    ("/acoes", {"ate": "9999-12-31"}, "ate"),
    ("/acoes/quadro", {"de": "0001-01-01"}, "de"),
    ("/painel", {"ate": "9999-12-31"}, "ate"),
    ("/painel", {"de": "0001-01-01", "ate": "2026-01-01"}, "de"),
    ("/painel/exportar.csv", {"ate": "9999-12-31"}, "ate"),
    ("/envios/historico", {"ate": "9999-12-31"}, "ate"),
    ("/envios/contatos", {"ultimo_ate": "9999-12-31"}, "ultimo_ate"),
    ("/auditoria", {"ate": "9999-12-31"}, "ate"),
])
def test_datas_fora_da_faixa_viram_422(client, admin, url, params, campo):
    r = client.get(f"{API}{url}", headers=admin["h"], params=params)
    assert r.status_code == 422, r.text
    assert r.json()["erro"]["campos"] == {campo: "Use uma data entre 01/01/2000 e 31/12/2100."}


def test_datas_fora_da_faixa_nos_resultados_do_formulario(client, admin):
    nps = form_padrao(client, admin["h"])
    for params, campo in (({"ate": "9999-12-31"}, "ate"), ({"de": "0001-01-01"}, "de")):
        for sufixo in ("resultados", "respostas", "respostas.csv"):
            r = client.get(f"{API}/formularios/{nps['id']}/{sufixo}", headers=admin["h"], params=params)
            assert r.status_code == 422 and campo in r.json()["erro"]["campos"], (sufixo, params)
    ok = client.get(f"{API}/respostas", headers=admin["h"], params={"de": "2000-01-01", "ate": "2100-12-31"})
    assert ok.status_code == 200


def test_mudar_a_nota_nao_muda_a_acao_ja_criada(client, admin):
    h = admin["h"]
    c = criar_contato(client, h, nome="Paula")
    d = registrar_resposta(client, h, c["id"], 3).json()
    antes = client.get(f"{API}/acoes/{d['acao']['id']}", headers=h).json()
    x = client.patch(f"{API}/respostas/{d['id']}", headers=h, json={"nota": 10}).json()
    assert x["grupo"] == "promotor" and x["acao"]["id"] == antes["id"]
    depois = client.get(f"{API}/acoes/{antes['id']}", headers=h).json()
    for campo in ("titulo", "prioridade", "prazo", "grupo", "nota", "descricao", "situacao", "atualizada_em"):
        assert depois[campo] == antes[campo], campo
    assert depois["resposta"]["nota"] == 10  # o resumo da resposta ligada mostra a nota atual


def test_sem_formulario_padrao_de_nps(client, admin, dono):
    h = admin["h"]
    c = criar_contato(client, h)
    sql(dono, "update formularios set padrao_nps = false")
    r = registrar_resposta(client, h, c["id"], 5)
    assert r.status_code == 409 and r.json()["erro"]["codigo"] == "sem_formulario_nps"
    assert lista_respostas(client, h)["total"] == 0


def test_csv_protege_contra_formula(client, admin):
    h = admin["h"]
    c = criar_contato(client, h, nome="=Maria", email="maria@x.com.br")
    token = link_pesquisa(client, h, c["id"], referencia="@pedido")
    nps = form_padrao(client, h)
    client.post(f"{API}/publico/convites/{token}/responder",
                json={"respostas": {nps["perguntas"][0]["id"]: 9, nps["perguntas"][1]["id"]: "+SUM(A1:A9)"}})
    linhas = list(csv.reader(io.StringIO(client.get(f"{API}/respostas.csv", headers=h).content.decode("utf-8-sig")),
                             delimiter=";"))
    cab, linha = linhas[0], linhas[1]
    assert linha[cab.index("Contato")] == "'=Maria"
    assert linha[cab.index("Comentário")] == "'+SUM(A1:A9)"
    assert linha[cab.index("Referência")] == "'@pedido"


def test_dia_de_sao_paulo_na_lista(client, admin, dono):
    """23:30 de D (horário de Brasília) conta em D; 00:30 de D+1, não (em UTC as duas já são D+1)."""
    h = admin["h"]
    c = criar_contato(client, h)
    a = registrar_resposta(client, h, c["id"], 9).json()
    b = registrar_resposta(client, h, c["id"], 3).json()
    sql(dono, "update respostas set respondida_em = '2026-04-10 23:30-03' where id = :r", r=a["id"])
    sql(dono, "update respostas set respondida_em = '2026-04-11 00:30-03' where id = :r", r=b["id"])
    assert [x["id"] for x in lista_respostas(client, h, de="2026-04-10", ate="2026-04-10")["itens"]] == [a["id"]]
    assert [x["id"] for x in lista_respostas(client, h, de="2026-04-11", ate="2026-04-11")["itens"]] == [b["id"]]

"""Conectores do Pipedrive e do HubSpot (os CRMs são falsos: as funções de `conectores.pipedrive` e `conectores.hubspot`
são trocadas). Conectar (token conferido e cifrado; no Pipedrive, o aviso cadastrado), sincronizar (cria empresas e
contatos, não duplica), negócio ganho → pesquisa uma vez (Pipedrive pelo aviso, só na passagem para ganho; HubSpot pela
tarefa, a partir de quando ligou), a nota de volta ao Pipedrive, Plano Grátis fechado e desconectar. Também a leitura dos
campos dos dois (formatos reais das APIs)."""
from datetime import datetime, timedelta

import pytest
from util import API, conta_pronta, form_padrao, ligar_envios, membro, sql, token_do_convite

from toqqi.core import relogio
from toqqi.core.email import caixa_memoria
from toqqi.modulos.conectores import crm, hubspot, pipedrive, servico

TOKEN = "tok_crm_0123456789abcdef"
ORGS = [{"id": "1", "nome": "Mercado Azul"}, {"id": "2", "nome": "Padaria Sol"}]
PESSOAS = [
    {"id": "10", "nome": "Ana Azul", "email": "Ana@Azul.com.br", "telefone": None, "empresa_id": "1", "empresa_nome": None},
    {"id": "11", "nome": "Beto Sol", "email": None, "telefone": "(11) 98765-4321", "empresa_id": "2", "empresa_nome": None},
    {"id": "12", "nome": "Sem Contato", "email": None, "telefone": None, "empresa_id": None, "empresa_nome": None},
]


@pytest.fixture
def pd(monkeypatch):
    estado = {"webhooks": [], "removidos": [], "token_ok": True, "notas": []}

    def conferir(token):
        if not estado["token_ok"]:
            raise pipedrive.ErroPipedrive("O Pipedrive recusou o token.")

    def criar(token, url):
        estado["webhooks"].append(url)
        return str(len(estado["webhooks"]))

    monkeypatch.setattr(pipedrive, "conferir_token", conferir)
    monkeypatch.setattr(pipedrive, "criar_webhook", criar)
    monkeypatch.setattr(pipedrive, "remover_webhook", lambda token, wid: estado["removidos"].append(wid))
    monkeypatch.setattr(pipedrive, "empresas", lambda token, maximo: iter(ORGS))
    monkeypatch.setattr(pipedrive, "contatos", lambda token, maximo: iter(PESSOAS))
    monkeypatch.setattr(pipedrive, "pessoas_do_negocio", lambda token, deal: [PESSOAS[0]])
    monkeypatch.setattr(pipedrive, "organizacao", lambda token, org: {"id": org, "nome": "Mercado Azul"})
    monkeypatch.setattr(pipedrive, "anotar", lambda token, deal, texto: estado["notas"].append((token, deal, texto)))
    return estado


@pytest.fixture
def hs(monkeypatch):
    estado = {"negocios": [], "desde": [], "token_ok": True}

    def conferir(token):
        if not estado["token_ok"]:
            raise hubspot.ErroHubspot("O HubSpot recusou a chave.")

    def ganhos(token, desde, maximo=200):
        estado["desde"].append(desde)
        return list(estado["negocios"])

    monkeypatch.setattr(hubspot, "conferir_token", conferir)
    monkeypatch.setattr(hubspot, "empresas", lambda token, maximo: iter(ORGS))
    monkeypatch.setattr(hubspot, "contatos", lambda token, maximo: iter(PESSOAS))
    monkeypatch.setattr(hubspot, "negocios_ganhos", ganhos)
    monkeypatch.setattr(hubspot, "contatos_do_negocio",
                        lambda token, deal, maximo: ([PESSOAS[0]], {"id": "1", "nome": "Mercado Azul"}))
    return estado


@pytest.fixture
def admin(client, dono):
    a = conta_pronta(client, "ana@alfa.com.br", empresa="Alfa")
    sql(dono, "update contas set situacao = 'cortesia' where id = :c", c=a["conta"]["id"])
    return a


def _conectar(client, h, chave, **corpo):
    return client.put(f"{API}/integracoes/conectores/{chave}", headers=h,
                      json={"token": TOKEN, "pesquisar_ao_ganhar": True, **corpo})


def _segredo(estado) -> str:
    return estado["webhooks"][-1].rsplit("/", 1)[-1]


def _ganho(deal_id=7, anterior="open", status="won"):
    return {"meta": {"action": "change", "entity": "deal", "entity_id": str(deal_id), "version": "2.0"},
            "data": {"id": deal_id, "title": "Contrato anual", "status": status, "person_id": 10, "org_id": 1},
            "previous": {"status": anterior} if anterior is not None else {"value": 100}}


# ---- Pipedrive -------------------------------------------------------------------------------------------------

def test_pipedrive_conectar_e_alterar(client, dono, admin, pd):
    h = admin["h"]
    ver = client.get(f"{API}/integracoes/conectores", headers=h).json()
    assert ver["pipedrive"] == {"conectado": False} and ver["hubspot"] == {"conectado": False}
    r = _conectar(client, h, "pipedrive")
    assert r.status_code == 200, r.text
    assert r.json()["conectado"] and r.json()["aviso_cadastrado"] and r.json()["pesquisar_ao_ganhar"]
    assert "/api/v1/publico/conectores/pipedrive/" in pd["webhooks"][0]
    (cifrado, hash_), = sql(dono, "select token_cifrado, segredo_hash from conectores where provedor = 'pipedrive'")
    assert TOKEN not in cifrado and _segredo(pd) not in hash_
    r = client.patch(f"{API}/integracoes/conectores/pipedrive", headers=h, json={"pesquisar_ao_ganhar": False})
    assert r.json()["aviso_cadastrado"] is False and r.json()["pesquisar_ao_ganhar"] is False and pd["removidos"] == ["1"]
    r = client.patch(f"{API}/integracoes/conectores/pipedrive", headers=h, json={"pesquisar_ao_ganhar": True})
    assert r.json()["aviso_cadastrado"] is True and len(pd["webhooks"]) == 2
    pd["token_ok"] = False
    r = _conectar(client, h, "pipedrive")
    assert r.status_code == 502 and r.json()["erro"]["codigo"] == "conector_falhou"
    assert client.put(f"{API}/integracoes/conectores/salesforce", headers=h, json={"token": TOKEN}).status_code in (404, 405, 422)


def test_so_administrador_e_nada_no_gratis(client, dono, admin, pd):
    gestor = membro(client, admin["h"], "gil@alfa.com.br", perfil="gestor")
    assert _conectar(client, gestor["h"], "pipedrive").status_code == 403
    sql(dono, "update contas set situacao = 'gratis', gratis_desde = now(), gratis_motivo = 'teste' where id = :c",
        c=admin["conta"]["id"])
    r = _conectar(client, admin["h"], "hubspot")
    assert r.status_code == 403 and r.json()["erro"]["codigo"] == "recurso_do_plano"


def test_pipedrive_sincronizar_sem_duplicar(client, dono, admin, pd):
    h = admin["h"]
    _conectar(client, h, "pipedrive")
    r = client.post(f"{API}/integracoes/conectores/pipedrive/sincronizar", headers=h)
    assert r.status_code == 200, r.text
    assert r.json() == {"empresas_novas": 2, "empresas_existentes": 0, "contatos_novos": 2, "contatos_existentes": 0,
                        "sem_email_ou_telefone": 1, "limite_do_plano": False, "cortado": False}
    linhas = sql(dono, "select c.nome, c.email, c.codigo_externo, e.nome, e.codigo_externo from contatos c "
                       "left join empresas e on e.id = c.empresa_id order by c.nome")
    assert [tuple(x) for x in linhas] == [("Ana Azul", "ana@azul.com.br", "pd:10", "Mercado Azul", "pd:1"),
                                         ("Beto Sol", None, "pd:11", "Padaria Sol", "pd:2")]
    r = client.post(f"{API}/integracoes/conectores/pipedrive/sincronizar", headers=h).json()
    assert (r["empresas_novas"], r["contatos_novos"], r["contatos_existentes"]) == (0, 0, 2)


def test_pipedrive_negocio_ganho_manda_uma_vez_e_a_nota_volta(client, dono, admin, pd):
    h = admin["h"]
    form = form_padrao(client, h)
    ligar_envios(client, h)
    _conectar(client, h, "pipedrive")
    url = f"{API}/publico/conectores/pipedrive/{_segredo(pd)}"
    antes = len(caixa_memoria)
    assert client.post(url, json=_ganho()).status_code == 200
    assert [m.para for m in caixa_memoria[antes:]] == ["ana@azul.com.br"]
    assert client.post(url, json=_ganho()).status_code == 200  # repetido: não manda de novo
    # ganho que não mudou o status, negócio perdido, outra entidade, segredo errado e corpo estranho: nada
    for corpo in (_ganho(8, anterior=None), _ganho(9, status="lost"), {"meta": {"entity": "person"}, "data": {"id": 1}}):
        assert client.post(url, json=corpo).status_code == 200
    assert client.post(f"{API}/publico/conectores/pipedrive/errado", json=_ganho(10)).status_code == 200
    assert client.post(url, content=b"x", headers={"content-type": "application/json"}).status_code == 200
    assert len(caixa_memoria) == antes + 1
    (evento, referencia, origem), = sql(dono, "select evento, referencia, origem_externa from convites")
    assert (evento, referencia, origem) == ("negocio_ganho", "Contrato anual", "pd:7")
    # a nota volta como anotação no negócio
    m = caixa_memoria[antes]
    r = client.post(f"{API}/publico/convites/{token_do_convite(m)}/responder",
                    json={"respostas": {form["perguntas"][0]["id"]: 4}, "comentario": "Atrasou"})
    assert r.status_code == 201, r.text
    assert servico.devolver_notas() == {"anotadas": 1, "falharam": 0, "negocios_hubspot": 0}
    assert pd["notas"][0][:2] == (TOKEN, "7") and "Ana Azul deu nota 4 (detrator)" in pd["notas"][0][2]
    assert servico.devolver_notas()["anotadas"] == 0  # uma vez só


def test_pipedrive_desligado_nao_manda(client, admin, pd):
    h = admin["h"]
    form_padrao(client, h)
    ligar_envios(client, h)
    _conectar(client, h, "pipedrive")
    segredo = _segredo(pd)
    client.patch(f"{API}/integracoes/conectores/pipedrive", headers=h, json={"pesquisar_ao_ganhar": False})
    antes = len(caixa_memoria)
    client.post(f"{API}/publico/conectores/pipedrive/{segredo}", json=_ganho())
    assert len(caixa_memoria) == antes


def test_desconectar(client, dono, admin, pd, hs):
    h = admin["h"]
    _conectar(client, h, "pipedrive")
    _conectar(client, h, "hubspot")
    assert client.delete(f"{API}/integracoes/conectores/pipedrive", headers=h).status_code == 204
    assert pd["removidos"] == ["1"]
    assert sql(dono, "select provedor from conectores") == [("hubspot",)]
    assert client.delete(f"{API}/integracoes/conectores/hubspot", headers=h).status_code == 204
    assert sql(dono, "select count(*) from conectores")[0][0] == 0


# ---- HubSpot -------------------------------------------------------------------------------------------------

def test_hubspot_conectar_e_sincronizar(client, dono, admin, hs):
    h = admin["h"]
    r = _conectar(client, h, "hubspot")
    assert r.status_code == 200, r.text
    assert r.json()["conectado"] and r.json()["pesquisar_ao_ganhar"] and "aviso_cadastrado" not in r.json()
    assert r.json()["consultado_em"] is None
    r = client.post(f"{API}/integracoes/conectores/hubspot/sincronizar", headers=h).json()
    assert (r["empresas_novas"], r["contatos_novos"]) == (2, 2)
    assert sql(dono, "select codigo_externo from contatos order by codigo_externo") == [("hs:10",), ("hs:11",)]
    hs["token_ok"] = False
    r = _conectar(client, h, "hubspot")
    assert r.status_code == 502 and "recusou" in r.json()["erro"]["mensagem"]


def test_hubspot_tarefa_consulta_os_ganhos_desde_que_ligou(client, dono, admin, hs):
    h = admin["h"]
    form_padrao(client, h)
    ligar_envios(client, h)
    ligou = relogio.agora()
    _conectar(client, h, "hubspot")
    assert servico.devolver_notas()["negocios_hubspot"] == 0  # nenhum ganho ainda
    assert abs(hs["desde"][0] - (ligou - crm.FOLGA_CONSULTA)) < timedelta(seconds=5)
    hs["negocios"] = [{"id": "501", "nome": "Renovação", "alterado_em": 1}]
    antes = len(caixa_memoria)
    assert servico.devolver_notas()["negocios_hubspot"] == 1
    assert [m.para for m in caixa_memoria[antes:]] == ["ana@azul.com.br"]
    (evento, referencia, origem), = sql(dono, "select evento, referencia, origem_externa from convites")
    assert (evento, referencia, origem) == ("negocio_ganho", "Renovação", None)  # HubSpot: sem nota de volta
    # a mesma consulta devolve o mesmo negócio (folga de 10 minutos): não manda de novo
    assert servico.devolver_notas()["negocios_hubspot"] == 0
    assert len(caixa_memoria) == antes + 1
    ver = client.get(f"{API}/integracoes/conectores", headers=h).json()["hubspot"]
    assert ver["consultado_em"] and ver["erro"] is None
    (opcoes,), = sql(dono, "select opcoes from conectores where provedor = 'hubspot'")
    assert opcoes["vistos"] == ["501"]


def test_hubspot_desligado_ou_erro(client, dono, admin, hs, monkeypatch):
    h = admin["h"]
    _conectar(client, h, "hubspot", pesquisar_ao_ganhar=False)
    hs["negocios"] = [{"id": "501", "nome": "Renovação", "alterado_em": 1}]
    assert servico.devolver_notas()["negocios_hubspot"] == 0 and hs["desde"] == []  # desligado: nem consulta
    client.patch(f"{API}/integracoes/conectores/hubspot", headers=h, json={"pesquisar_ao_ganhar": True})

    def falha(token, desde, maximo=200):
        raise hubspot.ErroHubspot("O HubSpot pediu uma pausa.")

    monkeypatch.setattr(hubspot, "negocios_ganhos", falha)
    (antes,), = sql(dono, "select opcoes->>'desde' from conectores")
    assert servico.devolver_notas()["negocios_hubspot"] == 0
    (depois, erro), = sql(dono, "select opcoes->>'desde', erro from conectores")
    assert depois == antes and "pediu uma pausa" in erro  # a próxima rodada tenta o mesmo período


# ---- leitura dos campos (formatos das APIs) ---------------------------------------------------------------------------

def test_pipedrive_leitura_dos_campos():
    p = pipedrive.pessoa({"id": 5, "name": "Ana", "email": [{"value": "b@x.com", "primary": False},
                                                            {"value": "a@x.com", "primary": True}],
                          "phone": [{"value": "", "primary": True}, {"value": "11 98765-4321"}],
                          "org_id": {"value": 3, "name": "Mercado"}})
    assert p == {"id": "5", "nome": "Ana", "email": "a@x.com", "telefone": "11 98765-4321", "empresa_id": "3",
                 "empresa_nome": "Mercado"}
    assert pipedrive.pessoa({"id": 6, "name": "Beto", "org_id": 9})["empresa_id"] == "9"
    # v1 (current/previous) e v2 (data/previous)
    v1 = {"current": {"id": 1, "status": "won"}, "previous": {"id": 1, "status": "open"}, "meta": {"object": "deal"}}
    assert pipedrive.acabou_de_ganhar(*pipedrive.negocio_do_aviso(v1))
    assert pipedrive.negocio_do_aviso({"meta": {"entity": "person"}, "data": {}}) is None
    assert not pipedrive.acabou_de_ganhar({"status": "won"}, {"value": 1})
    assert not pipedrive.acabou_de_ganhar({"status": "won"}, {"status": "won"})


def test_hubspot_leitura_dos_campos():
    c = hubspot.contato({"id": "51", "properties": {"email": " ana@x.com ", "firstname": "Ana", "lastname": "Azul",
                                                    "phone": "1133334444", "mobilephone": "11987654321"},
                         "associations": {"companies": {"results": [{"id": "77", "type": "contact_to_company"}]}}})
    assert c == {"id": "51", "nome": "Ana Azul", "email": "ana@x.com", "telefone": "11987654321", "empresa_id": "77",
                 "empresa_nome": None}
    assert hubspot.contato({"id": "52", "properties": {"firstname": None, "lastname": None}})["nome"] is None
    assert hubspot._ms("2026-11-10T12:00:00.000Z") == int(datetime.fromisoformat("2026-11-10T12:00:00+00:00").timestamp() * 1000)
    assert hubspot._ms("1700000000000") == 1700000000000 and hubspot._ms("x") is None


# ---- os clientes HTTP (httpx trocado) -------------------------------------------------------------------------------

class _Resp:
    def __init__(self, status: int, corpo):
        import json as _json
        self.status_code, self._corpo = status, corpo
        self.content = _json.dumps(corpo).encode()

    def json(self):
        return self._corpo


def test_pipedrive_cliente_pagina_e_usa_o_cabecalho(monkeypatch):
    import httpx

    pedidos = []
    paginas = [{"success": True, "data": [{"id": 1, "name": "A"}, {"id": 2, "name": "B"}],
                "additional_data": {"pagination": {"more_items_in_collection": True, "next_start": 2}}},
               {"success": True, "data": [{"id": 3, "name": "C"}],
                "additional_data": {"pagination": {"more_items_in_collection": False}}}]

    def pedir(metodo, url, params=None, json=None, timeout=None, headers=None):
        pedidos.append((metodo, url, params, headers))
        return _Resp(200, paginas[len(pedidos) - 1])

    monkeypatch.setattr(httpx, "request", pedir)
    assert [o["nome"] for o in pipedrive.empresas(TOKEN, 10)] == ["A", "B", "C"]
    assert [p[2]["start"] for p in pedidos] == [0, 2]
    assert pedidos[0][1] == "https://api.pipedrive.com/v1/organizations" and pedidos[0][3]["x-api-token"] == TOKEN
    assert TOKEN not in pedidos[0][1] and "api_token" not in pedidos[0][2]  # o token nunca vai no endereço
    monkeypatch.setattr(httpx, "request", lambda *a, **k: _Resp(401, {"success": False}))
    with pytest.raises(pipedrive.ErroPipedrive, match="recusou o token"):
        pipedrive.conferir_token(TOKEN)
    monkeypatch.setattr(httpx, "request", lambda *a, **k: _Resp(200, {"success": True, "data": {"id": 99}}))
    assert pipedrive.criar_webhook(TOKEN, "https://x") == "99"


def test_hubspot_cliente_busca_os_ganhos(monkeypatch):
    import httpx

    pedidos = []

    def pedir(metodo, url, params=None, json=None, timeout=None, headers=None):
        pedidos.append((metodo, url, json, headers))
        return _Resp(200, {"results": [{"id": "9", "properties": {"dealname": "Renovação",
                                                                  "hs_lastmodifieddate": "2026-11-10T12:00:00Z"}}]})

    monkeypatch.setattr(httpx, "request", pedir)
    desde = datetime.fromisoformat("2026-11-10T10:00:00+00:00")
    assert hubspot.negocios_ganhos(TOKEN, desde) == [{"id": "9", "nome": "Renovação",
                                                     "alterado_em": hubspot._ms("2026-11-10T12:00:00Z")}]
    metodo, url, corpo, cab = pedidos[0]
    assert (metodo, url) == ("POST", "https://api.hubapi.com/crm/v3/objects/deals/search")
    assert cab["Authorization"] == f"Bearer {TOKEN}"
    filtros = {f["propertyName"]: f for f in corpo["filterGroups"][0]["filters"]}
    assert filtros["hs_is_closed_won"]["value"] == "true"
    assert filtros["hs_lastmodifieddate"]["value"] == str(int(desde.timestamp() * 1000))
    monkeypatch.setattr(httpx, "request", lambda *a, **k: _Resp(403, {}))
    with pytest.raises(hubspot.ErroHubspot, match="escopos"):
        hubspot.conferir_token(TOKEN)

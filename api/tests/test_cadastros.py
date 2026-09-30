"""Cadastros auxiliares e responsáveis."""
import httpx
import pytest
from util import API, conta_pronta, criar_contato, criar_empresa, membro

from toqqi.core import rede


@pytest.fixture
def admin(client):
    return conta_pronta(client, "ana@alfa.com.br", empresa="Alfa Distribuidora")


def test_conta_nova_ja_tem_perfis_padrao(client, admin):
    itens = client.get(f"{API}/cadastros/perfis", headers=admin["h"]).json()
    assert [i["nome"] for i in itens] == ["Decisor", "Influenciador"]
    assert all(i["em_uso"] == 0 for i in itens)


def test_crud_auxiliar_em_uso_e_exclusao_deixa_sem_item(client, admin):
    h = admin["h"]
    r = client.post(f"{API}/cadastros/grupos", headers=h, json={"nome": "Rede Sul"})
    assert r.status_code == 201
    grupo = r.json()
    assert grupo == {"id": grupo["id"], "nome": "Rede Sul", "em_uso": 0}
    # nome repetido (sem diferenciar maiúsculas)
    r = client.post(f"{API}/cadastros/grupos", headers=h, json={"nome": "rede sul"})
    assert r.status_code == 409 and r.json()["erro"]["codigo"] == "nome_em_uso"
    # mesmo nome em outro tipo é permitido
    assert client.post(f"{API}/cadastros/segmentos", headers=h, json={"nome": "Rede Sul"}).status_code == 201

    e = criar_empresa(client, h, "Supermercado Andorinha", grupo_id=grupo["id"])
    assert e["grupo"] == {"id": grupo["id"], "nome": "Rede Sul"}
    itens = client.get(f"{API}/cadastros/grupos", headers=h).json()
    assert itens[0]["em_uso"] == 1

    r = client.patch(f"{API}/cadastros/grupos/{grupo['id']}", headers=h, json={"nome": "Rede Sul-Sudeste"})
    assert r.status_code == 200 and r.json()["nome"] == "Rede Sul-Sudeste"

    assert client.delete(f"{API}/cadastros/grupos/{grupo['id']}", headers=h).status_code == 204
    assert client.get(f"{API}/empresas/{e['id']}", headers=h).json()["grupo"] is None
    assert client.get(f"{API}/cadastros/grupos", headers=h).json() == []


def test_excluir_cargo_deixa_contato_sem_cargo(client, admin):
    h = admin["h"]
    cargo = client.post(f"{API}/cadastros/cargos", headers=h, json={"nome": "Comprador"}).json()
    c = criar_contato(client, h, cargo_id=cargo["id"])
    assert c["cargo"]["nome"] == "Comprador"
    assert client.get(f"{API}/cadastros/cargos", headers=h).json()[0]["em_uso"] == 1
    client.delete(f"{API}/cadastros/cargos/{cargo['id']}", headers=h)
    assert client.get(f"{API}/contatos/{c['id']}", headers=h).json()["cargo"] is None


def test_tipo_invalido_e_item_inexistente(client, admin):
    assert client.get(f"{API}/cadastros/cidades", headers=admin["h"]).status_code == 422
    assert client.patch(f"{API}/cadastros/grupos/999", headers=admin["h"], json={"nome": "X"}).status_code == 404


def test_consulta_le_mas_nao_edita_cadastros(client, admin):
    consulta = membro(client, admin["h"], "caio@alfa.com.br", "consulta")
    assert client.get(f"{API}/cadastros/grupos", headers=consulta["h"]).status_code == 200
    r = client.post(f"{API}/cadastros/grupos", headers=consulta["h"], json={"nome": "X"})
    assert r.status_code == 403
    assert client.post(f"{API}/responsaveis", headers=consulta["h"], json={"nome": "Rui"}).status_code == 403


def test_responsaveis_crud_e_contagem(client, admin):
    h = admin["h"]
    r = client.post(f"{API}/responsaveis", headers=h, json={
        "nome": "Rita Vendas", "funcao": "Executiva de contas", "email": "rita@alfa.com.br",
        "teams_webhook": "https://alfa.webhook.office.com/webhookb2/abc"})
    assert r.status_code == 201, r.text
    resp = r.json()
    assert resp["empresas"] == 0 and resp["teams_webhook"].startswith("https://")
    criar_empresa(client, h, "Cliente 1", responsavel_id=resp["id"])
    assert client.get(f"{API}/responsaveis", headers=h).json()[0]["empresas"] == 1
    r = client.patch(f"{API}/responsaveis/{resp['id']}", headers=h, json={"funcao": "Gerente"})
    assert r.json()["funcao"] == "Gerente" and r.json()["nome"] == "Rita Vendas"
    assert client.delete(f"{API}/responsaveis/{resp['id']}", headers=h).status_code == 204
    empresa = client.get(f"{API}/empresas", headers=h).json()["itens"][0]
    assert empresa["responsavel"] is None


@pytest.mark.parametrize("url", [
    "http://alfa.webhook.office.com/x",       # sem https
    "https://127.0.0.1/x",                    # loopback
    "https://10.0.0.5/x",                     # rede privada
    "https://169.254.169.254/latest",         # link-local (metadados de nuvem)
    "https://localhost/x",
    "https://intranet/x",
    "https://user:senha@alfa.webhook.office.com/x",
])
def test_webhook_teams_so_https_publico(client, admin, url):
    r = client.post(f"{API}/responsaveis", headers=admin["h"], json={"nome": "Rita", "teams_webhook": url})
    assert r.status_code == 422, url
    assert "teams_webhook" in r.json()["erro"]["campos"]


def test_testar_teams(client, admin, monkeypatch):
    h = admin["h"]
    resp = client.post(f"{API}/responsaveis", headers=h, json={
        "nome": "Rita", "teams_webhook": "https://alfa.webhook.office.com/webhookb2/abc"}).json()
    chamadas = []
    monkeypatch.setattr(rede, "resolver", lambda host: ["52.96.1.10"])

    def post_ok(url, ip, host, corpo):
        chamadas.append((url, ip, host, corpo))
        return httpx.Response(200, text="1")

    monkeypatch.setattr(rede, "enviar_post", post_ok)
    r = client.post(f"{API}/responsaveis/{resp['id']}/testar-teams", headers=h)
    assert r.status_code == 200 and "Teams" in r.json()["mensagem"]
    assert chamadas[0][1:3] == ("52.96.1.10", "alfa.webhook.office.com")

    # Teams recusou
    monkeypatch.setattr(rede, "enviar_post", lambda *a: httpx.Response(400, text="Bad payload"))
    r = client.post(f"{API}/responsaveis/{resp['id']}/testar-teams", headers=h)
    assert r.status_code == 422 and r.json()["erro"]["codigo"] == "teams_recusou"

    # nome que resolve para IP interno (DNS rebinding) é recusado antes de conectar
    monkeypatch.setattr(rede, "resolver", lambda host: ["10.1.2.3"])
    monkeypatch.setattr(rede, "enviar_post", lambda *a: pytest.fail("não deveria conectar"))
    r = client.post(f"{API}/responsaveis/{resp['id']}/testar-teams", headers=h)
    assert r.status_code == 422 and "teams_webhook" in r.json()["erro"]["campos"]

    # timeout
    def estoura(*a):
        raise httpx.ConnectTimeout("timeout")

    monkeypatch.setattr(rede, "resolver", lambda host: ["52.96.1.10"])
    monkeypatch.setattr(rede, "enviar_post", estoura)
    r = client.post(f"{API}/responsaveis/{resp['id']}/testar-teams", headers=h)
    assert r.status_code == 422


def test_testar_teams_sem_webhook(client, admin):
    resp = client.post(f"{API}/responsaveis", headers=admin["h"], json={"nome": "Rita"}).json()
    r = client.post(f"{API}/responsaveis/{resp['id']}/testar-teams", headers=admin["h"])
    assert r.status_code == 422

"""Campos de texto opcionais com limite de tamanho aceitam vazio e nulo (antes davam erro 500)."""
from util import API, conta_pronta


def test_campos_opcionais_aceitam_nulo_e_vazio(client):
    h = conta_pronta(client, "nulos@alfa.com.br", empresa="Alfa Nulos")["h"]
    r = client.post(f"{API}/responsaveis", headers=h, json={"nome": "Rita", "funcao": "Vendas"})
    assert r.status_code == 201, r.text
    rid = r.json()["id"]
    for valor in (None, ""):
        r = client.patch(f"{API}/responsaveis/{rid}", headers=h, json={"funcao": valor, "foto_url": valor, "teams_webhook": valor})
        assert r.status_code == 200, r.text
        assert r.json()["funcao"] is None
    r = client.post(f"{API}/empresas", headers=h, json={"nome": "Cliente Nulo", "codigo_externo": None})
    assert r.status_code == 201, r.text
    for valor in (None, ""):
        r = client.put(f"{API}/envios/configuracao", headers=h, json={"remetente_nome": valor})
        assert r.status_code == 200, r.text
    r = client.put(f"{API}/envios/configuracao", headers=h, json={"remetente_nome": "x" * 81})
    assert r.status_code == 422

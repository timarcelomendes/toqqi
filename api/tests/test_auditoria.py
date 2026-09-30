"""Registro de atividades: eventos, filtros e paginação."""
from util import conta_pronta, entrar, membro, sql

API = "/api/v1"


def test_eventos_registrados_com_rotulo_usuario_e_ip(client):
    a = conta_pronta(client, "ana@alfa.com.br")
    entrar(client, "ana@alfa.com.br", "Errada@123")
    membro(client, a["h"], "caio@alfa.com.br")
    client.put(f"{API}/conta/seguranca", headers=a["h"], json={"sessao_minutos": 90, "dominios": []})
    corpo = client.get(f"{API}/auditoria", headers=a["h"]).json()
    eventos = [i["evento"] for i in corpo["itens"]]
    for e in ["cadastro_conta", "login_ok", "login_falhou", "usuario_criado", "seguranca_alterada"]:
        assert e in eventos, e
    item = next(i for i in corpo["itens"] if i["evento"] == "usuario_criado")
    assert item["rotulo"] == "Usuário adicionado"
    assert item["usuario"] == {"id": a["usuario"]["id"], "nome": "Pessoa"}
    assert item["ip"] == "testclient"
    falha = next(i for i in corpo["itens"] if i["evento"] == "login_falhou")
    assert falha["gravidade"] == "atencao" and falha["usuario"] is None
    assert corpo["por_pagina"] == 50 and corpo["pagina"] == 1 and corpo["total"] == len(eventos)


def test_filtros_e_paginacao(client, dono):
    a = conta_pronta(client, "ana@alfa.com.br")
    cid = a["conta"]["id"]
    sql(dono, """insert into auditoria (conta_id, evento, gravidade, detalhe, criado_em)
                 select :c, 'usuario_alterado', 'info', jsonb_build_object('n', g), now() - interval '1 hour'
                 from generate_series(1, 60) g""", c=cid)
    sql(dono, """insert into auditoria (conta_id, evento, gravidade, criado_em)
                 values (:c, 'permissoes_alteradas', 'atencao', '2026-01-15 12:00-03')""", c=cid)
    h = a["h"]
    p1 = client.get(f"{API}/auditoria", headers=h).json()
    p2 = client.get(f"{API}/auditoria?pagina=2", headers=h).json()
    assert len(p1["itens"]) == 50 and p1["total"] == p2["total"] >= 62
    assert {i["id"] for i in p1["itens"]}.isdisjoint({i["id"] for i in p2["itens"]})

    r = client.get(f"{API}/auditoria?de=2026-01-15&ate=2026-01-15&gravidade=&busca=", headers=h).json()
    assert [i["evento"] for i in r["itens"]] == ["permissoes_alteradas"]
    r = client.get(f"{API}/auditoria?gravidade=atencao", headers=h).json()
    assert all(i["gravidade"] == "atencao" for i in r["itens"]) and r["total"] == 1
    r = client.get(f"{API}/auditoria?busca=permissões", headers=h).json()  # busca pelo rótulo
    assert r["total"] == 1
    r = client.get(f"{API}/auditoria?de=15-01-2026", headers=h)
    assert r.status_code == 422 and "de" in r.json()["erro"]["campos"]


def test_gestor_nao_ve_auditoria(client):
    a = conta_pronta(client, "ana@alfa.com.br")
    g = membro(client, a["h"], "gil@alfa.com.br", "gestor")
    assert client.get(f"{API}/auditoria", headers=g["h"]).status_code == 403

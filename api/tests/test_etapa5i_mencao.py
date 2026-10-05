"""Etapa 5i, "Pesquisa feita com Toqqi" e origem do cadastro (docs/api-etapa-5i.md §4): a menção aparece na página da
pesquisa e nos e-mails de pesquisa com o link utm (sem ids nem token); só o plano Empresa (ativa/atrasada) e a
cortesia podem tirar (403 nos outros; reenviar o salvo não dá 403); ao descer de plano ela volta. O cadastro grava a
origem limpa (só utm, sem e-mail ou telefone, nunca 422) e a Plataforma conta os cadastros por origem."""
import pytest
from util import API, cadastrar, conta_pronta, criar_contato, link_pesquisa, sql, superadmin

from toqqi.core.email import caixa_memoria
from toqqi.core.planos import limpar_origem, pode_ocultar_mencao

URL_PAGINA = "/?utm_source=pesquisa&utm_medium=rodape&utm_campaign=pagina"


@pytest.fixture
def admin(client):
    return conta_pronta(client, "ana@alfa.com.br", empresa="Alfa")


def _plano(dono, conta_id: int, plano: str, situacao: str) -> None:
    sql(dono, "update contas set plano = :p, situacao = :s where id = :c", p=plano, s=situacao, c=conta_id)


def _put(client, h, **corpo):
    return client.put(f"{API}/envios/configuracao", headers=h, json=corpo)


def _pagina(client, h) -> dict:
    contato = criar_contato(client, h)
    token = link_pesquisa(client, h, contato["id"])
    r = client.get(f"{API}/publico/convites/{token}")
    assert r.status_code == 200, r.text
    return r.json()["formulario"]


@pytest.mark.parametrize("plano,situacao,pode", [
    ("empresa", "ativa", True), ("empresa", "atrasada", True), ("empresa", "teste", False),
    ("empresa", "pausada", False), ("profissional", "ativa", False), ("essencial", "ativa", False),
    ("essencial", "cortesia", True), (None, None, False),
])
def test_quem_pode_tirar(plano, situacao, pode):
    assert pode_ocultar_mencao(plano, situacao) is pode


def test_pagina_mostra_a_mencao_sem_ids(client, admin):
    f = _pagina(client, admin["h"])
    assert f["mencao_toqqi"]["texto"] == "Pesquisa feita com Toqqi"
    assert f["mencao_toqqi"]["url"].endswith(URL_PAGINA)


def test_teste_nao_pode_tirar_e_reenviar_o_salvo_nao_da_403(client, admin):
    h = admin["h"]
    r = _put(client, h, ocultar_mencao_toqqi=True)
    assert r.status_code == 403 and r.json()["erro"]["codigo"] == "recurso_do_plano"
    r = _put(client, h, ocultar_mencao_toqqi=False, so_dias_uteis=False)
    assert r.status_code == 200
    assert r.json()["mencao_toqqi"] == {"pode_ocultar": False, "aparece": True}


def test_empresa_tira_e_volta_ao_descer_de_plano(client, dono, admin):
    h, cid = admin["h"], admin["conta"]["id"]
    _plano(dono, cid, "empresa", "ativa")
    r = _put(client, h, ocultar_mencao_toqqi=True)
    assert r.status_code == 200, r.text
    assert r.json()["ocultar_mencao_toqqi"] is True
    assert r.json()["mencao_toqqi"] == {"pode_ocultar": True, "aparece": False}
    assert _pagina(client, h)["mencao_toqqi"] is None
    _plano(dono, cid, "profissional", "ativa")
    cfg = client.get(f"{API}/envios/configuracao", headers=h).json()
    assert cfg["ocultar_mencao_toqqi"] is True and cfg["mencao_toqqi"]["aparece"] is True
    assert _pagina(client, h)["mencao_toqqi"] is not None
    # salvar outra coisa com o valor guardado não dá 403
    assert _put(client, h, ocultar_mencao_toqqi=True, so_dias_uteis=False).status_code == 200


def test_email_de_pesquisa_leva_a_mencao(client, dono, admin):
    h, cid = admin["h"], admin["conta"]["id"]
    r = client.post(f"{API}/envios/configuracao/teste", headers=h)
    assert r.status_code == 200, r.text
    m = caixa_memoria[-1]
    assert "Pesquisa feita com Toqqi" in m.html and "utm_campaign=email" in m.html
    assert 'rel="noopener noreferrer"' in m.html
    assert m.texto.splitlines()[-1].startswith("Pesquisa feita com Toqqi: ")
    _plano(dono, cid, "empresa", "ativa")
    assert _put(client, h, ocultar_mencao_toqqi=True).status_code == 200
    client.post(f"{API}/envios/configuracao/teste", headers=h)
    assert "Pesquisa feita com Toqqi" not in caixa_memoria[-1].html
    assert "Pesquisa feita com Toqqi" not in caixa_memoria[-1].texto


@pytest.mark.parametrize("bruta,limpa", [
    ({"utm_source": " Pesquisa ", "utm_medium": "rodape", "utm_campaign": "email"},
     {"utm_source": "pesquisa", "utm_medium": "rodape", "utm_campaign": "email"}),
    ({"utm_campaign": "black friday+2026", "outra": "x"}, {"utm_campaign": "black-friday-2026"}),
    ({"utm_source": "ana@x.com.br"}, None),
    ({"utm_source": "tel11987654321"}, None),
    ({"utm_source": "x" * 61}, None),
    ({"utm_source": 7}, None),
    ("pesquisa", None),
    (None, None),
])
def test_limpeza_da_origem(bruta, limpa):
    assert limpar_origem(bruta) == limpa


def test_cadastro_grava_a_origem_e_a_plataforma_conta(client, dono):
    root = superadmin(client)
    r = client.post(f"{API}/auth/cadastro", json={
        "empresa": "Beta", "nome": "Bia", "email": "bia@beta.com.br", "senha": "Senha-forte-123", "aceite_termos": True,
        "origem": {"utm_source": "pesquisa", "utm_medium": "rodape", "utm_campaign": "pagina", "utm_term": "z"},
    })
    assert r.status_code == 201, r.text
    # origem inválida nunca impede o cadastro
    r = client.post(f"{API}/auth/cadastro", json={
        "empresa": "Gama", "nome": "Gil", "email": "gil@gama.com.br", "senha": "Senha-forte-123", "aceite_termos": True,
        "origem": {"utm_source": "gil@gama.com.br"},
    })
    assert r.status_code == 201, r.text
    cadastrar(client, "dan@delta.com.br", empresa="Delta")
    origens = dict(sql(dono, "select nome, origem from contas where nome in ('Beta', 'Gama', 'Delta')"))
    assert origens == {"Beta": {"utm_source": "pesquisa", "utm_medium": "rodape", "utm_campaign": "pagina"},
                       "Gama": None, "Delta": None}
    v = client.get(f"{API}/plataforma/visao", headers=root["h"]).json()
    assert v["origens"]["dias"] == 90
    assert v["origens"]["itens"] == [{"rotulo": "pesquisa · rodape · pagina", "cadastros": 1, "pagantes": 0}]
    assert v["origens"]["sem_origem"]["cadastros"] == 3  # Gama, Delta e a própria conta da plataforma
    beta = next(c for c in v["contas"] if c["nome"] == "Beta")
    assert beta["origem"] == "pesquisa · rodape · pagina"

"""Descadastro: página pública (/sair), um clique (List-Unsubscribe), tela interna e efeito nos envios."""
import pytest
from util import (
    API,
    conta_pronta,
    criar_contato,
    disparar,
    emails_para,
    fila,
    ligar_envios,
    membro,
    token_de_saida,
)

from toqqi.modulos.envios.descadastro import token_descadastro


@pytest.fixture
def admin(client):
    a = conta_pronta(client, "ana@alfa.com.br", empresa="Alfa")
    ligar_envios(client, a["h"])
    return a


def _saida(client, h, email="maria@cliente.com.br") -> tuple[dict, str]:
    c = criar_contato(client, h, nome="Maria", email=email)
    disparar(client, h, [c["id"]])
    return c, token_de_saida(emails_para(email)[-1])


def _eventos(client, h) -> list[dict]:
    return client.get(f"{API}/auditoria", headers=h).json()["itens"]


def test_pagina_publica_sair_e_voltar(client, admin):
    h = admin["h"]
    c, token = _saida(client, h)
    url = f"{API}/publico/descadastro/{token}"
    assert client.get(url).json() == {"email_mascarado": "ma***@cliente.com.br", "empresa": "Alfa",
                                      "descadastrado": False}
    r = client.post(url, json={"motivo": "Recebo pesquisas demais"})
    assert r.status_code == 200 and r.json() == {"descadastrado": True}
    assert client.get(url).json()["descadastrado"] is True
    assert client.post(url, json={}).json() == {"descadastrado": True}  # repetir não duplica
    # tela interna
    lista = client.get(f"{API}/envios/descadastros", headers=h).json()
    assert lista["total"] == 1
    item = lista["itens"][0]
    assert item["email"] == "maria@cliente.com.br" and item["contato"] == {"id": c["id"], "nome": "Maria"}
    assert (item["motivo"], item["origem"]) == ("Recebo pesquisas demais", "link")
    # auditoria sem o e-mail completo
    evento = next(e for e in _eventos(client, h) if e["evento"] == "descadastro")
    assert evento["detalhe"]["email"] == "ma***@cliente.com.br" and "maria@" not in str(evento["detalhe"])
    # não recebe mais nada
    assert fila(client, h)[c["id"]]["situacao"] == "saiu_da_lista"
    r = disparar(client, h, [c["id"]], ignorar_descanso=True)
    assert r.json()["ignorados"][0]["motivo"] == "Saiu da lista"
    # mudou de ideia
    assert client.post(url, json={"voltar": True}).json() == {"descadastrado": False}
    assert client.get(f"{API}/envios/descadastros", headers=h).json()["total"] == 0
    assert "descadastro_desfeito" in [e["evento"] for e in _eventos(client, h)]
    assert disparar(client, h, [c["id"]], ignorar_descanso=True).json()["agendados"] == 1


def test_um_clique_do_programa_de_email(client, admin):
    h = admin["h"]
    c, token = _saida(client, h)
    r = client.post(f"{API}/publico/descadastro/{token}", data={"List-Unsubscribe": "One-Click"})
    assert r.status_code == 200 and r.json() == {"descadastrado": True}
    assert client.get(f"{API}/envios/descadastros", headers=h).json()["itens"][0]["origem"] == "um_clique"
    r = client.post(f"{API}/publico/descadastro/{token}", data={"outra": "coisa"})
    assert r.status_code == 422


def test_token_invalido(client, admin):
    _, token = _saida(client, admin["h"])
    dados, assinatura = token.split(".")
    for ruim in [f"{dados}.{assinatura[:-1]}x", "abc", f"{dados}", "a" * 700,
                 token_descadastro(admin["conta"]["id"], "outra@pessoa.com").split(".")[0] + "." + assinatura]:
        r = client.get(f"{API}/publico/descadastro/{ruim}")
        assert r.status_code == 404 and r.json()["erro"]["codigo"] == "link_invalido", ruim
        assert client.post(f"{API}/publico/descadastro/{ruim}", json={}).status_code == 404
    r = client.post(f"{API}/publico/descadastro/{token}", json={"motivo": "x" * 301})
    assert r.status_code == 422 and "motivo" in r.json()["erro"]["campos"]
    r = client.post(f"{API}/publico/descadastro/{token}", content=b"{nao json", headers={"content-type": "application/json"})
    assert r.status_code == 422


def test_descadastrado_continua_fora_mesmo_recriando_o_contato(client, admin):
    h = admin["h"]
    c, token = _saida(client, h)
    client.post(f"{API}/publico/descadastro/{token}", json={})
    assert client.delete(f"{API}/contatos/{c['id']}", headers=h).status_code == 204
    novo = criar_contato(client, h, nome="Maria de Novo", email="MARIA@cliente.com.br")
    assert fila(client, h)[novo["id"]]["situacao"] == "saiu_da_lista"
    assert disparar(client, h, [novo["id"]]).json()["agendados"] == 0
    # reimportação também não recoloca
    arquivo = "nome;email\r\nMaria Importada;maria@cliente.com.br\r\n".encode()
    imp = client.post(f"{API}/importacao/analisar", headers=h, files={"arquivo": ("c.csv", arquivo)}).json()
    corpo = {"mapeamento": {"nome": "nome", "email": "email"}, "chave": "email", "atualizar_existentes": True}
    assert client.post(f"{API}/importacao/{imp['id']}/importar", headers=h, json=corpo).status_code == 200
    assert fila(client, h)[novo["id"]]["situacao"] == "saiu_da_lista"
    assert client.get(f"{API}/envios/descadastros", headers=h).json()["itens"][0]["contato"]["id"] == novo["id"]


def test_descadastro_manual_e_permissoes(client, admin):
    h = admin["h"]
    r = client.post(f"{API}/envios/descadastros", headers=h, json={"email": "Pedro@Cliente.com.br",
                                                                   "motivo": "Pediu por telefone"})
    assert r.status_code == 201
    assert r.json()["email"] == "pedro@cliente.com.br" and r.json()["origem"] == "manual"
    assert r.json()["contato"] is None
    assert client.post(f"{API}/envios/descadastros", headers=h, json={"email": "x"}).status_code == 422
    client.post(f"{API}/envios/descadastros", headers=h, json={"email": "joana@outra.com"})
    assert client.get(f"{API}/envios/descadastros?busca=pedro", headers=h).json()["total"] == 1
    consulta = membro(client, h, "caio@alfa.com.br", "consulta")
    assert client.get(f"{API}/envios/descadastros", headers=consulta["h"]).json()["total"] == 2
    r = client.post(f"{API}/envios/descadastros", headers=consulta["h"], json={"email": "z@z.com"})
    assert r.status_code == 403
    assert client.post(f"{API}/contatos", headers=h, json={"nome": "Pedro", "email": "pedro@cliente.com.br"}
                       ).json()["situacao"] == "saiu_da_lista"


def test_descadastro_vale_so_na_propria_conta(client, admin):
    h = admin["h"]
    _, token = _saida(client, h)
    client.post(f"{API}/publico/descadastro/{token}", json={})
    b = conta_pronta(client, "bia@beta.com.br", empresa="Beta")
    ligar_envios(client, b["h"])
    cb = criar_contato(client, b["h"], email="maria@cliente.com.br")
    assert fila(client, b["h"])[cb["id"]]["situacao"] == "na_fila"
    assert client.get(f"{API}/envios/descadastros", headers=b["h"]).json()["total"] == 0
    assert disparar(client, b["h"], [cb["id"]]).json()["agendados"] == 1

"""Voltar a receber sem achar o e-mail antigo (docs/api-voltar-a-receber.md): a página /sair sem token pede o link
por e-mail (uma empresa por link, só as que já mandaram pesquisa ou de cuja lista a pessoa saiu), com a mesma
resposta sempre e os limites; e quem volta por um canal volta em todos."""
import re

import pytest
from fastapi.testclient import TestClient
from util import (
    API,
    conta_pronta,
    criar_contato,
    disparar,
    emails_para,
    ligar_envios,
    sql,
    token_de_saida,
)

from toqqi.core.email import caixa_memoria
from toqqi.core.rate_limit import limiter
from toqqi.modulos.envios.descadastro import MSG_LINK, token_descadastro

MARIA = "maria@cliente.com.br"
ASSUNTO = "Escolha as pesquisas que você recebe"


def _conta(client, email, empresa):
    a = conta_pronta(client, email, empresa=empresa)
    ligar_envios(client, a["h"])
    return a


def _pedir(client, email=MARIA, ip=None):
    if ip is None:
        return client.post(f"{API}/publico/descadastro/pedir-link", json={"email": email})
    with TestClient(client.app, client=(ip, 50000)) as outro:
        return outro.post(f"{API}/publico/descadastro/pedir-link", json={"email": email})


def _links(m) -> dict[str, str]:
    """{texto da linha: token} dos links /sair/{token} do e-mail (versão em texto: "Empresa: url")."""
    return {texto.strip(): token for texto, token in re.findall(r"^(.+?): \S+/sair/([\w.-]+)$", m.texto, re.M)}


def test_manda_um_link_por_empresa_que_ja_mandou_pesquisa(client, dono):
    alfa = _conta(client, "ana@alfa.com.br", "Alfa")
    beta = _conta(client, "bia@beta.com.br", "Beta")
    gama = _conta(client, "caio@gama.com.br", "Gama")
    # Alfa e Gama já mandaram pesquisa; a Beta só tem o contato (não entra: não revela a lista dela)
    for a in (alfa, gama):
        c = criar_contato(client, a["h"], nome="Maria", email=MARIA)
        assert disparar(client, a["h"], [c["id"]]).status_code == 202
    criar_contato(client, beta["h"], nome="Maria", email=MARIA)
    # saiu da lista da Alfa pelo link do e-mail
    token_alfa = token_de_saida(next(m for m in emails_para(MARIA) if "/sair/" in m.texto))
    assert client.post(f"{API}/publico/descadastro/{token_alfa}", json={}).json() == {"descadastrado": True}

    caixa_memoria.clear()
    r = _pedir(client, "  Maria@Cliente.com.br ")
    assert r.status_code == 200 and r.json() == {"mensagem": MSG_LINK}
    [m] = emails_para(MARIA)
    assert m.assunto == ASSUNTO
    links = _links(m)
    assert set(links) == {"Alfa (você saiu da lista)", "Gama"}
    assert "Beta" not in m.texto and "Não foi você que pediu?" in m.texto
    # cada link abre a página daquela empresa, com a situação certa
    alfa_pagina = client.get(f"{API}/publico/descadastro/{links['Alfa (você saiu da lista)']}").json()
    assert (alfa_pagina["empresa"], alfa_pagina["descadastrado"]) == ("Alfa", True)
    gama_pagina = client.get(f"{API}/publico/descadastro/{links['Gama']}").json()
    assert (gama_pagina["empresa"], gama_pagina["descadastrado"]) == ("Gama", False)
    # voltar pelo link novo
    assert client.post(f"{API}/publico/descadastro/{links['Alfa (você saiu da lista)']}",
                       json={"voltar": True}).json() == {"descadastrado": False}
    assert sql(dono, "select count(*) from descadastros")[0][0] == 0


def test_mesma_resposta_para_quem_nao_recebe_nada(client):
    a = _conta(client, "ana@alfa.com.br", "Alfa")
    criar_contato(client, a["h"], nome="Maria", email=MARIA)  # contato sem pesquisa enviada
    caixa_memoria.clear()
    for email in (MARIA, "ninguem@exemplo.com.br"):
        r = _pedir(client, email)
        assert r.status_code == 200 and r.json() == {"mensagem": MSG_LINK}
    assert list(caixa_memoria) == []


def test_uma_empresa_vem_com_o_botao_do_que_da_para_fazer(client):
    a = _conta(client, "ana@alfa.com.br", "Alfa")
    c = criar_contato(client, a["h"], nome="Maria", email=MARIA)
    disparar(client, a["h"], [c["id"]])
    caixa_memoria.clear()
    _pedir(client)
    [m] = emails_para(MARIA)
    assert "Alfa manda pesquisas de satisfação para este e-mail pelo Toqqi" in m.texto
    assert re.search(r"Não quero mais receber: \S+/sair/", m.texto)
    token = token_descadastro(a["conta"]["id"], MARIA)
    assert f"/sair/{token}" in m.texto
    client.post(f"{API}/publico/descadastro/{token}", json={"motivo": "Recebo pesquisas demais"})
    caixa_memoria.clear()
    _pedir(client)
    [m] = emails_para(MARIA)
    assert "Você saiu da lista de pesquisas de Alfa" in m.texto
    assert re.search(r"Voltar a receber as pesquisas: \S+/sair/", m.texto)


def test_email_invalido(client):
    for corpo in ({"email": "nao-e-email"}, {}, {"email": "a@b"}):
        r = client.post(f"{API}/publico/descadastro/pedir-link", json=corpo)
        assert r.status_code == 422, corpo


@pytest.fixture
def limites():
    limiter.enabled = True
    limiter.reset()
    try:
        yield
    finally:
        limiter.enabled = False
        limiter.reset()


def test_limite_por_email_e_por_ip(client, limites):
    a = _conta(client, "ana@alfa.com.br", "Alfa")
    c = criar_contato(client, a["h"], nome="Maria", email=MARIA)
    disparar(client, a["h"], [c["id"]])
    caixa_memoria.clear()
    # por e-mail: 3 por hora, mesmo de IPs diferentes; o quarto responde igual, sem mandar nada
    for i in range(4):
        r = _pedir(client, ip=f"203.0.113.{i + 1}")
        assert r.status_code == 200 and r.json() == {"mensagem": MSG_LINK}
    assert len(emails_para(MARIA)) == 3
    # por IP: 3 por minuto, qualquer e-mail
    for i in range(3):
        assert _pedir(client, f"outro{i}@exemplo.com.br", ip="198.51.100.9").status_code == 200
    r = _pedir(client, "mais@exemplo.com.br", ip="198.51.100.9")
    assert r.status_code == 429 and r.json()["erro"]["codigo"] == "muitas_tentativas"


def test_voltar_pelo_link_tira_tambem_o_telefone_do_mesmo_contato(client, dono):
    a = _conta(client, "ana@alfa.com.br", "Alfa")
    conta_id = a["conta"]["id"]
    criar_contato(client, a["h"], nome="Maria", email=MARIA, telefone="11987654321")
    # saiu pelo WhatsApp (SAIR): o telefone está na lista, o e-mail não
    sql(dono, "insert into descadastros (conta_id, telefone, origem) values (:c, '5511987654321', 'whatsapp')",
        c=conta_id)
    url = f"{API}/publico/descadastro/{token_descadastro(conta_id, MARIA)}"
    assert client.get(url).json()["descadastrado"] is True  # não recebe nada da Alfa, nem por e-mail
    assert client.post(url, json={"voltar": True}).json() == {"descadastrado": False}
    assert sql(dono, "select count(*) from descadastros")[0][0] == 0
    evento = next(e for e in client.get(f"{API}/auditoria", headers=a["h"]).json()["itens"]
                  if e["evento"] == "descadastro_desfeito")
    assert evento["detalhe"] == {"email": "ma***@cliente.com.br", "origem": "link"}
    # e o pedido do link já mostra a Alfa como fora da lista (antes de voltar) ou não (depois)
    sql(dono, "insert into descadastros (conta_id, telefone, origem) values (:c, '5511987654321', 'whatsapp')",
        c=conta_id)
    caixa_memoria.clear()
    _pedir(client)
    [m] = emails_para(MARIA)
    assert "Você saiu da lista de pesquisas de Alfa" in m.texto


def test_cada_conta_so_ve_o_proprio_descadastro(client, dono):
    alfa = _conta(client, "ana@alfa.com.br", "Alfa")
    beta = _conta(client, "bia@beta.com.br", "Beta")
    for a in (alfa, beta):
        c = criar_contato(client, a["h"], nome="Maria", email=MARIA)
        disparar(client, a["h"], [c["id"]])
    token_alfa = token_descadastro(alfa["conta"]["id"], MARIA)
    client.post(f"{API}/publico/descadastro/{token_alfa}", json={})
    # voltar na Alfa não mexe na Beta, e sair da Alfa não tira da Beta
    token_beta = token_descadastro(beta["conta"]["id"], MARIA)
    assert client.get(f"{API}/publico/descadastro/{token_beta}").json()["descadastrado"] is False
    client.post(f"{API}/publico/descadastro/{token_beta}", json={})
    client.post(f"{API}/publico/descadastro/{token_alfa}", json={"voltar": True})
    assert sql(dono, "select conta_id from descadastros") == [(beta["conta"]["id"],)]

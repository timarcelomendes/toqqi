"""Quem administra a conta: a lista para qualquer perfil (Minha conta) e o e-mail de pedido de acesso aprovado."""
from util import SENHA, conta_pronta, entrar, sql, token_do_email

from toqqi.core.email import caixa_memoria
from toqqi.modulos.acesso.emails import lista_de_admins

API = "/api/v1"


def _novo(client, h, nome, email, perfil):
    r = client.post(f"{API}/equipe", headers=h, json={"nome": nome, "email": email, "perfil": perfil, "senha": SENHA})
    assert r.status_code == 201, r.text
    return r.json()


def _h(client, email):
    r = entrar(client, email)
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}


def _renomear(client, h, sessao, nome):
    r = client.patch(f"{API}/equipe/{sessao['usuario']['id']}", headers=h, json={"nome": nome})
    assert r.status_code == 200, r.text


def test_qualquer_perfil_ve_os_administradores_ativos_da_propria_conta(client):
    a = conta_pronta(client, "ana@alfa.com.br")
    _renomear(client, a["h"], a, "Ana Souza")
    bruno = _novo(client, a["h"], "Bruno Lima", "bruno@alfa.com.br", "admin")
    dora = _novo(client, a["h"], "Dora Bloqueada", "dora@alfa.com.br", "admin")
    client.patch(f"{API}/equipe/{dora['id']}", headers=a["h"], json={"situacao": "bloqueado"})
    _novo(client, a["h"], "Gil Gestor", "gil@alfa.com.br", "gestor")
    _novo(client, a["h"], "Cid Consulta", "cid@alfa.com.br", "consulta")
    conta_pronta(client, "bia@beta.com.br")  # admin de outra conta: não aparece

    cid = _h(client, "cid@alfa.com.br")
    r = client.get(f"{API}/conta/administradores", headers=cid)
    assert r.status_code == 200, r.text
    assert r.json() == [
        {"id": a["usuario"]["id"], "nome": "Ana Souza", "email": "ana@alfa.com.br", "cargo": None, "voce": False},
        {"id": bruno["id"], "nome": "Bruno Lima", "email": "bruno@alfa.com.br", "cargo": None, "voce": False},
    ]
    # o gestor vê o mesmo; o administrador se vê marcado
    assert [x["nome"] for x in client.get(f"{API}/conta/administradores", headers=_h(client, "gil@alfa.com.br")).json()] \
        == ["Ana Souza", "Bruno Lima"]
    assert [(x["nome"], x["voce"]) for x in client.get(f"{API}/conta/administradores", headers=a["h"]).json()] == [
        ("Ana Souza", True), ("Bruno Lima", False)]
    # rebaixado a gestor, sai da lista
    client.patch(f"{API}/equipe/{bruno['id']}", headers=a["h"], json={"perfil": "gestor"})
    assert [x["nome"] for x in client.get(f"{API}/conta/administradores", headers=cid).json()] == ["Ana Souza"]
    assert client.get(f"{API}/conta/administradores").status_code == 401


def _pedir_acesso(client, nome, email, confirmar=True):
    r = client.post(f"{API}/auth/pedir-acesso", json={"nome": nome, "email": email, "senha": SENHA})
    assert r.status_code == 200, r.text
    if confirmar:
        r = client.post(f"{API}/auth/confirmar-email", json={"token": token_do_email(email, "confirmar-email")})
        assert r.status_code == 200, r.text


def _id(client, h, email):
    return next(u["id"] for u in client.get(f"{API}/equipe", headers=h).json() if u["email"] == email)


def test_aprovar_pedido_avisa_a_pessoa_com_quem_aprovou_e_os_administradores(client, dono):
    a = conta_pronta(client, "ana@alfa.com.br", empresa="Alfa Ltda")
    _renomear(client, a["h"], a, "Ana Souza")
    client.put(f"{API}/conta/seguranca", headers=a["h"], json={"sessao_minutos": 60, "dominios": ["alfa.com.br"]})
    _pedir_acesso(client, "Nina  Souza", "nina@alfa.com.br")
    nina = _id(client, a["h"], "nina@alfa.com.br")

    caixa_memoria.clear()
    r = client.patch(f"{API}/equipe/{nina}", headers=a["h"], json={"situacao": "ativo"})
    assert r.status_code == 200, r.text
    [m] = caixa_memoria
    assert m.para == "nina@alfa.com.br" and m.assunto == "Seu acesso ao Toqqi foi aprovado"
    assert "Olá, Nina Souza!" in m.texto
    assert "Ana Souza aprovou seu acesso à conta Alfa Ltda no Toqqi. Entre com nina@alfa.com.br" in m.texto
    assert "Você entra com o perfil Consulta." in m.texto
    assert "Quem administra a conta é Ana Souza (ana@alfa.com.br). Fale com essa pessoa" in m.texto
    assert "Entrar no Toqqi: http" in m.texto and m.texto.split("Entrar no Toqqi: ")[1].split()[0].endswith("/entrar")
    assert sql(dono, "select tipo, destinatario from emails_enviados where tipo = 'boas_vindas'") == [
        ("boas_vindas", "nina@alfa.com.br")]
    assert entrar(client, "nina@alfa.com.br").status_code == 200

    # bloquear e desbloquear não é aprovar: nada de novo e-mail
    client.patch(f"{API}/equipe/{nina}", headers=a["h"], json={"situacao": "bloqueado"})
    caixa_memoria.clear()
    client.patch(f"{API}/equipe/{nina}", headers=a["h"], json={"situacao": "ativo"})
    assert caixa_memoria == []

    # com dois administradores, os dois aparecem; aprovado como Gestor, o perfil vem certo
    _novo(client, a["h"], "Bruno Lima", "bruno@alfa.com.br", "admin")
    _pedir_acesso(client, "Otto", "otto@alfa.com.br")
    caixa_memoria.clear()
    client.patch(f"{API}/equipe/{_id(client, a['h'], 'otto@alfa.com.br')}", headers=a["h"],
                 json={"situacao": "ativo", "perfil": "gestor"})
    [m] = caixa_memoria
    assert "Você entra com o perfil Gestor." in m.texto
    assert ("Quem administra a conta: Ana Souza (ana@alfa.com.br) e Bruno Lima (bruno@alfa.com.br). "
            "Fale com uma dessas pessoas") in m.texto

    # aprovado já como administrador: a lista traz só os outros
    _pedir_acesso(client, "Paulo Reis", "paulo@alfa.com.br")
    caixa_memoria.clear()
    client.patch(f"{API}/equipe/{_id(client, a['h'], 'paulo@alfa.com.br')}", headers=a["h"],
                 json={"situacao": "ativo", "perfil": "admin"})
    [m] = caixa_memoria
    assert "Você entra com o perfil Administrador." in m.texto
    assert "Quem administra a conta: Ana Souza (ana@alfa.com.br) e Bruno Lima (bruno@alfa.com.br)." in m.texto
    assert "Paulo Reis (" not in m.texto


def test_pedido_sem_email_confirmado_aprovado_nao_manda_email(client):
    """Quem pede pode digitar o e-mail de outra pessoa: sem a confirmação, a aprovação não manda nada para ela."""
    a = conta_pronta(client, "ana@alfa.com.br")
    client.put(f"{API}/conta/seguranca", headers=a["h"], json={"sessao_minutos": 60, "dominios": ["alfa.com.br"]})
    _pedir_acesso(client, "Paula", "paula@alfa.com.br", confirmar=False)
    caixa_memoria.clear()
    r = client.patch(f"{API}/equipe/{_id(client, a['h'], 'paula@alfa.com.br')}", headers=a["h"],
                     json={"situacao": "ativo"})
    assert r.status_code == 200 and caixa_memoria == []


def test_lista_de_admins_no_email():
    assert lista_de_admins([("Ana", "ana@x.com")]) == "Ana (ana@x.com)"
    assert lista_de_admins([("Ana", "a@x"), ("Bia", "")]) == "Ana (a@x) e Bia"
    seis = [(f"P{i}", f"p{i}@x") for i in range(7)]
    assert lista_de_admins(seis) == "P0 (p0@x), P1 (p1@x), P2 (p2@x), P3 (p3@x), P4 (p4@x) e mais 2 administradores"
    assert lista_de_admins(seis[:6]).endswith("e mais 1 administrador")

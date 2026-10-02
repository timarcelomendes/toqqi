"""Área da plataforma (superadmin)."""
from datetime import datetime, timedelta, timezone

from util import cadastrar, conta_pronta, entrar, membro, sql

API = "/api/v1"


def test_so_superadmin_acessa(client):
    a = conta_pronta(client, "ana@alfa.com.br")
    assert a["usuario"]["superadmin"] is False
    for metodo, rota in [("get", "/plataforma/contas"), ("post", "/plataforma/contas/1/cortesia"),
                         ("post", "/plataforma/contas/1/estender-teste")]:
        r = getattr(client, metodo)(f"{API}{rota}", headers=a["h"])
        assert r.status_code == 403 and r.json()["erro"]["codigo"] == "sem_permissao"
    assert client.get(f"{API}/plataforma/contas").status_code == 401


def test_superadmin_lista_e_cria_contas(client):
    root = conta_pronta(client, "root@toqqi.com", empresa="Toqqi")
    assert root["usuario"]["superadmin"] is True
    conta_pronta(client, "ana@alfa.com.br", empresa="Alfa")
    r = client.post(f"{API}/plataforma/contas", headers=root["h"], json={
        "empresa": "Gama", "admin_nome": "Gui", "admin_email": "gui@gama.com.br",
        "admin_senha": "Senha@123", "situacao": "cortesia"})
    assert r.status_code == 201
    assert r.json()["situacao"] == "cortesia" and r.json()["teste_ate"] is None
    contas = client.get(f"{API}/plataforma/contas", headers=root["h"]).json()
    assert {c["nome"] for c in contas} == {"Toqqi", "Alfa", "Gama"}
    assert all(c["usuarios"] == 1 for c in contas)
    # o admin criado entra direto (já confirmado)
    assert entrar(client, "gui@gama.com.br").status_code == 200
    r = client.post(f"{API}/plataforma/contas", headers=root["h"], json={
        "empresa": "Delta", "admin_nome": "Ana", "admin_email": "ana@alfa.com.br", "admin_senha": "Senha@123"})
    assert r.status_code == 409 and r.json()["erro"]["codigo"] == "email_em_uso"


def test_lista_mostra_os_administradores_de_cada_conta(client):
    root = conta_pronta(client, "root@toqqi.com", empresa="Toqqi")
    alfa = conta_pronta(client, "ana@alfa.com.br", empresa="Alfa")
    membro(client, alfa["h"], "bia@alfa.com.br", perfil="admin")
    membro(client, alfa["h"], "caio@alfa.com.br")  # consulta: não é administrador
    cadastrar(client, "rui@beta.com.br", empresa="Beta")  # ainda sem confirmar o e-mail
    contas = {c["nome"]: c for c in client.get(f"{API}/plataforma/contas", headers=root["h"]).json()}
    assert [(a["email"], a["email_confirmado"]) for a in contas["Alfa"]["admins"]] == [
        ("ana@alfa.com.br", True), ("bia@alfa.com.br", True)]  # o mais antigo primeiro
    assert [(a["email"], a["email_confirmado"]) for a in contas["Beta"]["admins"]] == [("rui@beta.com.br", False)]
    assert [a["email"] for a in contas["Toqqi"]["admins"]] == ["root@toqqi.com"]
    assert contas["Alfa"]["usuarios"] == 3

    # criar, "+14 dias" e "Cortesia" devolvem a conta com os administradores
    r = client.post(f"{API}/plataforma/contas", headers=root["h"], json={
        "empresa": "Gama", "admin_nome": "Gui", "admin_email": "gui@gama.com.br", "admin_senha": "Senha@123"})
    assert r.status_code == 201 and r.json()["admins"] == [
        {"nome": "Gui", "email": "gui@gama.com.br", "email_confirmado": True}]
    cid = alfa["conta"]["id"]
    r = client.post(f"{API}/plataforma/contas/{cid}/estender-teste", headers=root["h"], json={"dias": 14})
    assert [a["email"] for a in r.json()["admins"]] == ["ana@alfa.com.br", "bia@alfa.com.br"]
    r = client.post(f"{API}/plataforma/contas/{cid}/cortesia", headers=root["h"])
    assert [a["email"] for a in r.json()["admins"]] == ["ana@alfa.com.br", "bia@alfa.com.br"]


def test_estender_teste_conta_do_fim_atual_ou_de_agora(client, dono):
    root = conta_pronta(client, "root@toqqi.com", empresa="Toqqi")
    a = conta_pronta(client, "ana@alfa.com.br", empresa="Alfa")
    cid = a["conta"]["id"]
    agora = datetime.now(timezone.utc)

    # teste ainda vigente: soma a partir do fim atual
    fim_atual = datetime.fromisoformat(a["conta"]["teste_ate"])
    r = client.post(f"{API}/plataforma/contas/{cid}/estender-teste", headers=root["h"], json={"dias": 14})
    assert r.status_code == 200
    novo = datetime.fromisoformat(r.json()["teste_ate"])
    assert abs(novo - (fim_atual + timedelta(days=14))) < timedelta(seconds=1)

    # teste já vencido: soma a partir de agora e volta a 'teste'
    sql(dono, "update contas set situacao='teste_expirado', teste_ate = now() - interval '10 days' where id=:c", c=cid)
    r = client.post(f"{API}/plataforma/contas/{cid}/estender-teste", headers=root["h"], json={"dias": 7})
    novo = datetime.fromisoformat(r.json()["teste_ate"])
    assert r.json()["situacao"] == "teste"
    assert abs(novo - (agora + timedelta(days=7))) < timedelta(minutes=1)

    r = client.post(f"{API}/plataforma/contas/{cid}/cortesia", headers=root["h"])
    assert r.json()["situacao"] == "cortesia"
    assert client.post(f"{API}/plataforma/contas/999999/cortesia", headers=root["h"]).status_code == 404
    eventos = [e for (e,) in sql(dono, "select evento from auditoria where conta_id=:c", c=cid)]
    assert eventos.count("teste_estendido") == 2 and "cortesia" in eventos


def test_admin_de_conta_nao_consegue_criar_o_email_do_superadmin(client):
    """Brecha fechada: um admin qualquer não pode criar 'root@toqqi.com' já confirmado e virar superadmin."""
    from tests.util import conta_pronta
    dono = conta_pronta(client, "dono.qualquer@empresa-x.com.br", empresa="Empresa X")
    h = dono["h"]
    r = client.post("/api/v1/equipe", headers=h, json={
        "nome": "Falso Root", "email": "root@toqqi.com", "perfil": "admin", "senha": "Senha@Forte123"})
    assert r.status_code == 409 and r.json()["erro"]["codigo"] == "email_em_uso"

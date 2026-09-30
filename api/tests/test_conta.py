"""Segurança da conta (domínios liberados, duração da sessão) e pedido de acesso."""
from datetime import datetime, timedelta, timezone

from toqqi.core.email import caixa_memoria
from util import SENHA, conta_pronta, entrar, sql, token_do_email

API = "/api/v1"


def _put(client, h, dominios, minutos=60):
    return client.put(f"{API}/conta/seguranca", headers=h, json={"sessao_minutos": minutos, "dominios": dominios})


def test_salvar_seguranca_normaliza_dominios(client):
    a = conta_pronta(client, "ana@alfa.com.br")
    r = _put(client, a["h"], ["@Alfa.com.br", " alfa.com.br", "filial.alfa.com.br"], 120)
    assert r.status_code == 200
    assert r.json() == {"sessao_minutos": 120, "dominios": ["alfa.com.br", "filial.alfa.com.br"]}
    assert client.get(f"{API}/conta/seguranca", headers=a["h"]).json() == r.json()
    s = entrar(client, "ana@alfa.com.br").json()
    restante = datetime.fromisoformat(s["expira_em"]) - datetime.now(timezone.utc)
    assert timedelta(minutes=119) < restante <= timedelta(minutes=120)


def test_dominio_gratuito_invalido_ou_de_outra_conta(client):
    a = conta_pronta(client, "ana@alfa.com.br")
    b = conta_pronta(client, "bia@beta.com.br")
    assert _put(client, b["h"], ["beta.com.br"]).status_code == 200
    for dominios, trecho in [(["gmail.com"], "gratuito"), (["yahoo.com.br"], "gratuito"),
                             (["nao é domínio"], "formato"), (["beta.com.br"], "outra conta")]:
        r = _put(client, a["h"], dominios)
        assert r.status_code == 422, dominios
        assert trecho in r.json()["erro"]["campos"]["dominios"]
    assert client.get(f"{API}/conta/seguranca", headers=a["h"]).json()["dominios"] == []


def test_sessao_minutos_fora_da_faixa(client):
    a = conta_pronta(client, "ana@alfa.com.br")
    for m in (29, 1441):
        r = _put(client, a["h"], [], m)
        assert r.status_code == 422 and "sessao_minutos" in r.json()["erro"]["campos"]


def test_pedir_acesso_so_cria_para_dominio_liberado(client, dono):
    a = conta_pronta(client, "ana@alfa.com.br")
    _put(client, a["h"], ["alfa.com.br"])
    caixa_memoria.clear()
    corpo = {"nome": "Novo", "senha": SENHA}
    respostas = [
        client.post(f"{API}/auth/pedir-acesso", json={**corpo, "email": e})
        for e in ["novo@alfa.com.br", "fulano@gmail.com", "x@naoliberado.com.br", "ana@alfa.com.br"]
    ]
    assert {r.status_code for r in respostas} == {200}
    assert len({r.json()["mensagem"] for r in respostas}) == 1
    assert [m.para for m in caixa_memoria] == ["novo@alfa.com.br"]

    linhas = sql(dono, "select email, perfil, situacao, email_confirmado, conta_id from usuarios order by id")
    assert len(linhas) == 2
    novo = linhas[1]
    assert tuple(novo[:4]) == ("novo@alfa.com.br", "consulta", "pendente", False)
    assert novo.conta_id == a["conta"]["id"]

    # confirma e-mail: continua pendente até o admin aprovar
    client.post(f"{API}/auth/confirmar-email", json={"token": token_do_email("novo@alfa.com.br", "confirmar-email")})
    r = entrar(client, "novo@alfa.com.br")
    assert r.status_code == 403 and r.json()["erro"]["codigo"] == "acesso_pendente"
    equipe = client.get(f"{API}/equipe", headers=a["h"]).json()
    pendente = next(u for u in equipe if u["email"] == "novo@alfa.com.br")
    client.patch(f"{API}/equipe/{pendente['id']}", headers=a["h"], json={"situacao": "ativo"})
    r = entrar(client, "novo@alfa.com.br")
    assert r.status_code == 200 and r.json()["usuario"]["perfil"] == "consulta"


def test_pedir_acesso_exige_senha_forte(client):
    r = client.post(f"{API}/auth/pedir-acesso", json={"nome": "Novo", "email": "n@alfa.com.br", "senha": "123"})
    assert r.status_code == 422 and "senha" in r.json()["erro"]["campos"]

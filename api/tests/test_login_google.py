"""Entrar com o Google (docs/api-login-google.md): o token do Google conferido com as chaves (falsas) do Google, a conta
do Google ligada na primeira entrada, o cadastro de quem ainda não tem conta e as recusas."""
import json
import time
from types import SimpleNamespace

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from jwt.algorithms import RSAAlgorithm
from util import SENHA, auth, conta_pronta, entrar, sql, token_do_email

from toqqi.core.config import config
from toqqi.core.email import caixa_memoria
from toqqi.modulos.acesso import google

API = "/api/v1"
CLIENT_ID = "123-abc.apps.googleusercontent.com"


def _chave():
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


@pytest.fixture(scope="module")
def chave():
    return _chave()


@pytest.fixture
def g(monkeypatch, chave):
    """O Google falso: as chaves públicas (uma, "k1") e o token assinado com a chave privada."""
    monkeypatch.setattr(config(), "GOOGLE_CLIENT_ID", CLIENT_ID)
    jwk = json.loads(RSAAlgorithm.to_jwk(chave.public_key()))
    jwk.update(kid="k1", alg="RS256", use="sig")
    estado = SimpleNamespace(pedidos=0, falhar=False)

    def responder(req: httpx.Request) -> httpx.Response:
        estado.pedidos += 1
        assert str(req.url) == config().GOOGLE_CHAVES_URL
        if estado.falhar:
            return httpx.Response(500)
        return httpx.Response(200, json={"keys": [jwk]}, headers={"Cache-Control": "public, max-age=19000"})

    monkeypatch.setattr(google, "transporte", httpx.MockTransport(responder))
    google.limpar_cache()

    def token(assinar=None, kid="k1", **claims):
        agora = int(time.time())
        dados = {"iss": "https://accounts.google.com", "aud": CLIENT_ID, "azp": CLIENT_ID, "sub": "1001",
                 "email": "ana@alfa.com.br", "email_verified": True, "name": "Ana  Souza", "iat": agora,
                 "exp": agora + 3600, **claims}
        return jwt.encode(dados, assinar or chave, algorithm="RS256", headers={"kid": kid})

    estado.token = token
    yield estado
    google.limpar_cache()


def _google(client, credencial: str, lembrar: bool = False):
    return client.post(f"{API}/auth/google", json={"credencial": credencial, "lembrar": lembrar})


def _eventos(dono, email: str) -> list[tuple]:
    return sql(dono, "select a.evento, a.detalhe->>'metodo' from auditoria a join usuarios u on u.id = a.usuario_id "
                     "where u.email = :e and a.evento like 'login%' order by a.id", e=email)


def test_config_e_desligado(client, monkeypatch):
    r = client.get(f"{API}/auth/google/config")
    assert r.status_code == 200 and r.json() == {"client_id": None}
    assert r.headers["cache-control"] == "public, max-age=300"
    r = _google(client, "x.y.z")
    assert r.status_code == 404 and r.json()["erro"]["codigo"] == "google_desligado"
    monkeypatch.setattr(config(), "GOOGLE_CLIENT_ID", f" {CLIENT_ID} ")
    assert client.get(f"{API}/auth/google/config").json() == {"client_id": CLIENT_ID}


def test_usuario_existente_entra_e_liga_a_conta_do_google(client, dono, g):
    conta_pronta(client, "ana@alfa.com.br", empresa="Alfa")
    r = _google(client, g.token(), lembrar=True)
    assert r.status_code == 200, r.text
    s = r.json()
    assert s["usuario"]["email"] == "ana@alfa.com.br" and s["conta"]["nome"] == "Alfa" and "novo" not in s
    assert client.get(f"{API}/eu", headers=auth(s["token"])).status_code == 200
    assert sql(dono, "select google_sub from usuarios where email = 'ana@alfa.com.br'") == [("1001",)]
    # a segunda entrada não liga de novo; a senha continua valendo
    assert _google(client, g.token()).status_code == 200
    assert entrar(client, "ana@alfa.com.br").status_code == 200
    eventos = _eventos(dono, "ana@alfa.com.br")
    assert [e for e in eventos if e[0] == "login_google_ligado"] == [("login_google_ligado", None)]
    assert [e for e in eventos if e[0] == "login_ok"][-3:] == [("login_ok", "google"), ("login_ok", "google"),
                                                              ("login_ok", None)]
    assert g.pedidos == 1  # as chaves do Google ficam em cache
    assert sql(dono, "select count(*) from registros_acesso where evento = 'login'")[0][0] >= 3


def test_outra_conta_do_google_com_o_mesmo_email_e_recusada(client, dono, g):
    conta_pronta(client, "ana@alfa.com.br", empresa="Alfa")
    assert _google(client, g.token()).status_code == 200
    r = _google(client, g.token(sub="2002"))
    assert r.status_code == 409 and r.json()["erro"]["codigo"] == "google_outra_conta"
    assert ("login_google_recusado", None) in _eventos(dono, "ana@alfa.com.br")
    # pela conta do Google ligada, entra mesmo que o e-mail no Google tenha mudado
    r = _google(client, g.token(email="ana.souza@gmail.com"))
    assert r.status_code == 200 and r.json()["usuario"]["email"] == "ana@alfa.com.br"


@pytest.mark.parametrize("mudanca", [
    {"aud": "outro.apps.googleusercontent.com"},
    {"iss": "https://outro.example.com"},
    {"exp": int(time.time()) - 3600},
    {"kid": "desconhecida"},
    {"assinar": "outra"},
])
def test_token_invalido(client, g, mudanca):
    if mudanca.get("assinar") == "outra":
        mudanca = {"assinar": _chave()}
    r = _google(client, g.token(**mudanca))
    assert r.status_code == 401 and r.json()["erro"]["codigo"] == "google_invalido"


def test_token_sem_rs256_lixo_e_email_nao_verificado(client, g):
    agora = int(time.time())
    hs = jwt.encode({"iss": "accounts.google.com", "aud": CLIENT_ID, "sub": "1", "email": "a@b.com.br",
                     "email_verified": True, "iat": agora, "exp": agora + 60}, "s" * 40, algorithm="HS256",
                    headers={"kid": "k1"})
    for credencial in (hs, "nao-e-um-jwt", g.token()[:-20] + "x" * 20):
        r = _google(client, credencial)
        assert r.status_code == 401 and r.json()["erro"]["codigo"] == "google_invalido", credencial
    r = _google(client, g.token(email_verified=False))
    assert r.status_code == 403 and r.json()["erro"]["codigo"] == "google_email_nao_verificado"
    assert _google(client, g.token(email_verified="true")).json()["novo"] is True  # o formato antigo do Google


def test_google_fora_do_ar(client, g):
    g.falhar = True
    r = _google(client, g.token())
    assert r.status_code == 503 and r.json()["erro"]["codigo"] == "google_fora_do_ar"


def test_cadastro_pelo_google(client, dono, g):
    r = _google(client, g.token(sub="3003", email="Bia@Beta.com.br", name="Bia  Lima"))
    assert r.status_code == 200, r.text
    novo = r.json()
    assert (novo["novo"], novo["email"], novo["nome"]) == (True, "bia@beta.com.br", "Bia Lima")
    assert sql(dono, "select count(*) from usuarios where email = 'bia@beta.com.br'") == [(0,)]  # nada criado ainda
    # o token de cadastro não vale como sessão
    assert client.get(f"{API}/eu", headers=auth(novo["cadastro"])).status_code == 401
    r = client.post(f"{API}/auth/google/cadastro", json={
        "cadastro": novo["cadastro"], "empresa": "Beta Atacado", "nome": "Bia Lima", "telefone": "11987654321",
        "aceite_termos": True, "origem": {"utm_source": "google"}})
    assert r.status_code == 201, r.text
    s = r.json()
    assert s["usuario"]["email"] == "bia@beta.com.br" and s["usuario"]["perfil"] == "admin"
    assert s["usuario"]["aceite"]["pendente"] is False
    assert s["conta"]["nome"] == "Beta Atacado" and s["conta"]["situacao"] == "teste"
    assert client.get(f"{API}/eu", headers=auth(s["token"])).status_code == 200
    assert sql(dono, "select email_confirmado, google_sub, telefone, perfil from usuarios "
                     "where email = 'bia@beta.com.br'") == [(True, "3003", "11987654321", "admin")]
    assert sql(dono, "select c.origem->>'utm_source' from contas c join usuarios u on u.conta_id = c.id "
                     "where u.email = 'bia@beta.com.br'") == [("google",)]
    assert sql(dono, "select detalhe->>'metodo' from auditoria where evento = 'cadastro_conta' "
                     "and detalhe->>'email' = 'bia@beta.com.br'") == [("google",)]
    assert sql(dono, "select origem from aceites_termos where usuario_email = 'bia@beta.com.br'") == [("cadastro",)]
    # o mesmo token de novo: a conta já existe
    r = client.post(f"{API}/auth/google/cadastro", json={
        "cadastro": novo["cadastro"], "empresa": "Beta 2", "nome": "Bia", "aceite_termos": True})
    assert r.status_code == 409 and r.json()["erro"]["codigo"] == "email_em_uso"
    # depois, o Google entra direto; a senha (aleatória) ninguém sabe
    r = _google(client, g.token(sub="3003", email="bia@beta.com.br"))
    assert r.status_code == 200 and "token" in r.json()
    assert entrar(client, "bia@beta.com.br", SENHA).status_code == 401


def test_cadastro_com_token_invalido_vencido_ou_sem_aceite(client, g):
    corpo = {"empresa": "Beta", "nome": "Bia", "aceite_termos": True}
    r = client.post(f"{API}/auth/google/cadastro", json={**corpo, "cadastro": "lixo"})
    assert r.status_code == 400 and r.json()["erro"]["codigo"] == "cadastro_vencido"
    cadastro = _google(client, g.token(sub="4004", email="rui@gama.com.br")).json()["cadastro"]
    r = client.post(f"{API}/auth/google/cadastro", json={**corpo, "cadastro": cadastro, "aceite_termos": False})
    assert r.status_code == 422
    # o token de sessão não vale como cadastro
    sessao = conta_pronta(client, "ana@alfa.com.br")["token"]
    r = client.post(f"{API}/auth/google/cadastro", json={**corpo, "cadastro": sessao})
    assert r.status_code == 400 and r.json()["erro"]["codigo"] == "cadastro_vencido"
    # vencido (passou dos 15 minutos)
    antes = int(time.time()) - 16 * 60
    vencido = jwt.encode({"sub": "4004", "email": "rui@gama.com.br", "nome": "Rui", "fin": "cadastro_google",
                          "iat": antes, "exp": antes + google.VALIDADE_CADASTRO}, google._chave_cadastro(),
                         algorithm="HS256")
    r = client.post(f"{API}/auth/google/cadastro", json={**corpo, "cadastro": vencido})
    assert r.status_code == 400 and r.json()["erro"]["codigo"] == "cadastro_vencido"
    assert client.post(f"{API}/auth/google/cadastro", json={**corpo, "cadastro": cadastro}).status_code == 201


def test_pedido_de_acesso_pendente_e_bloqueado(client, dono, g):
    a = conta_pronta(client, "ana@alfa.com.br", empresa="Alfa Ltda")
    client.put(f"{API}/conta/seguranca", headers=a["h"], json={"sessao_minutos": 60, "dominios": ["alfa.com.br"]})
    r = client.post(f"{API}/auth/pedir-acesso", json={"nome": "Nina Souza", "email": "nina@alfa.com.br", "senha": SENHA})
    assert r.status_code == 200, r.text
    token_do_email("nina@alfa.com.br", "confirmar-email")  # o e-mail de confirmação saiu (e não foi usado)
    caixa_memoria.clear()
    r = _google(client, g.token(sub="5005", email="nina@alfa.com.br"))
    assert r.status_code == 403 and r.json()["erro"]["codigo"] == "acesso_pendente"
    # o Google confirmou o e-mail: vale como a confirmação, e os administradores ficam sabendo do pedido
    assert sql(dono, "select email_confirmado, google_sub from usuarios where email = 'nina@alfa.com.br'") == [
        (True, None)]
    assert [m.para for m in caixa_memoria] == ["ana@alfa.com.br"]
    sql(dono, "update usuarios set situacao = 'bloqueado' where email = 'nina@alfa.com.br'")
    r = _google(client, g.token(sub="5005", email="nina@alfa.com.br"))
    assert r.status_code == 403 and r.json()["erro"]["codigo"] == "acesso_bloqueado"

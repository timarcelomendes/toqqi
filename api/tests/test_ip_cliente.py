"""IP do cliente atrás do proxy (etapa 5f): `X-Forwarded-For`/`X-Real-IP` ignorados; `CF-Connecting-IP` válido usado
(lista, texto, vazio e longo → o endereço da conexão); IPv4 mapeado; o mesmo /64 divide o limite; o 6º login com o
mesmo `CF-Connecting-IP` e `X-Forwarded-For` diferentes → 429."""
import pytest
from fastapi.testclient import TestClient
from starlette.requests import Request
from util import API, conta_pronta, entrar, sql

from toqqi.core.config import config
from toqqi.core.rate_limit import chave_ip, limiter
from toqqi.core.requisicao import ip_valido
from toqqi.main import create_app


@pytest.mark.parametrize("valor,esperado", [
    ("203.0.113.5", "203.0.113.5"),
    (" 203.0.113.5 ", "203.0.113.5"),
    ("2001:DB8:0:0::1", "2001:db8::1"),  # forma canônica
    ("::ffff:198.51.100.9", "198.51.100.9"),  # IPv4 mapeado vira IPv4
    ("203.0.113.5, 10.0.0.1", None),  # lista
    ("cliente", None),  # texto
    ("", None),
    (None, None),
    ("1" * 46, None),  # longo
    ("fe80::1%eth0", None),  # com zona
    ("01.2.3.4", None),
])
def test_ip_valido(valor, esperado):
    assert ip_valido(valor) == esperado


def _pedido(host: str) -> Request:
    return Request({"type": "http", "client": (host, 0), "headers": [], "method": "GET", "path": "/"})


def test_chave_do_limite():
    assert chave_ip(_pedido("203.0.113.5")) == "ip:203.0.113.5"
    assert chave_ip(_pedido("2001:db8:1:2:aaaa:bbbb:cccc:dddd")) == "ip6:2001:db8:1:2::/64"
    assert chave_ip(_pedido("2001:db8:1:2::1")) == chave_ip(_pedido("2001:db8:1:2:ffff::9"))
    assert chave_ip(_pedido("2001:db8:1:3::1")) != chave_ip(_pedido("2001:db8:1:2::1"))
    assert chave_ip(_pedido("testclient")) == "ip:testclient"


@pytest.fixture
def com_cabecalho(monkeypatch, dono):
    monkeypatch.setattr(config(), "IP_CLIENTE_CABECALHO", "CF-Connecting-IP")
    app = create_app()

    def cliente(conexao: str = "10.0.0.1") -> TestClient:
        return TestClient(app, client=(conexao, 51515))

    return cliente


def _ip_do_ultimo_login(dono) -> str:
    return sql(dono, "select ip from registros_acesso where evento = 'login' order by id desc limit 1")[0][0]


def _ip_da_auditoria(dono) -> str:
    return sql(dono, "select ip from auditoria where evento = 'login_ok' order by id desc limit 1")[0][0]


def test_sem_cabecalho_configurado_usa_a_conexao(client, dono):
    conta_pronta(client, "ana@alfa.com.br", empresa="Alfa")
    with TestClient(client.app, client=("192.0.2.80", 40000)) as c:
        r = c.post(f"{API}/auth/entrar", json={"email": "ana@alfa.com.br", "senha": "Senha@123"},
                   headers={"X-Forwarded-For": "6.6.6.6", "X-Real-IP": "7.7.7.7", "CF-Connecting-IP": "8.8.8.8"})
    assert r.status_code == 200
    assert _ip_do_ultimo_login(dono) == _ip_da_auditoria(dono) == "192.0.2.80"


@pytest.mark.parametrize("cabecalho,esperado", [
    ("203.0.113.77", "203.0.113.77"),
    ("::ffff:203.0.113.78", "203.0.113.78"),
    ("2001:db8::1, 203.0.113.1", "10.0.0.1"),
    ("nao-e-ip", "10.0.0.1"),
    ("", "10.0.0.1"),
    ("2" * 60, "10.0.0.1"),
])
def test_cf_connecting_ip(client, dono, com_cabecalho, cabecalho, esperado):
    conta_pronta(client, "ana@alfa.com.br", empresa="Alfa")
    with com_cabecalho() as c:
        r = c.post(f"{API}/auth/entrar", json={"email": "ana@alfa.com.br", "senha": "Senha@123"},
                   headers={"CF-Connecting-IP": cabecalho, "X-Forwarded-For": "6.6.6.6", "X-Real-IP": "7.7.7.7"})
    assert r.status_code == 200, r.text
    assert _ip_do_ultimo_login(dono) == _ip_da_auditoria(dono) == esperado
    sessao_ip = sql(dono, "select ip from sessoes order by criada_em desc limit 1")[0][0]
    assert sessao_ip == esperado


def test_sem_o_cabecalho_usa_a_conexao(client, dono, com_cabecalho):
    conta_pronta(client, "ana@alfa.com.br", empresa="Alfa")
    with com_cabecalho("192.0.2.99") as c:
        assert entrar(c, "ana@alfa.com.br").status_code == 200
    assert _ip_do_ultimo_login(dono) == "192.0.2.99"


@pytest.fixture
def limite():
    limiter.enabled = True
    limiter.reset()
    yield
    limiter.enabled = False
    limiter.reset()


def test_sexto_login_com_o_mesmo_ip_e_xff_diferente_429(client, com_cabecalho, limite):
    with com_cabecalho() as c:
        codigos = [c.post(f"{API}/auth/entrar", json={"email": "x@alfa.com.br", "senha": "Senha@123"},
                          headers={"CF-Connecting-IP": "203.0.113.200", "X-Forwarded-For": f"9.9.9.{i}"}).status_code
                   for i in range(6)]
        # outro IP real ainda entra
        outro = c.post(f"{API}/auth/entrar", json={"email": "x@alfa.com.br", "senha": "Senha@123"},
                       headers={"CF-Connecting-IP": "203.0.113.201"}).status_code
    assert codigos == [401] * 5 + [429]
    assert outro == 401


def test_o_mesmo_64_divide_o_limite(client, com_cabecalho, limite):
    with com_cabecalho() as c:
        codigos = [c.post(f"{API}/auth/entrar", json={"email": "x@alfa.com.br", "senha": "Senha@123"},
                          headers={"CF-Connecting-IP": f"2001:db8:1:2::{i + 1:x}"}).status_code for i in range(6)]
        outro = c.post(f"{API}/auth/entrar", json={"email": "x@alfa.com.br", "senha": "Senha@123"},
                       headers={"CF-Connecting-IP": "2001:db8:1:3::1"}).status_code
    assert codigos == [401] * 5 + [429]
    assert outro == 401

"""Formato de erro e limite de tentativas."""
import pytest
from util import SENHA

from toqqi.core.rate_limit import limiter

API = "/api/v1"


def _formato_ok(corpo):
    assert set(corpo) == {"erro"}
    assert set(corpo["erro"]) == {"codigo", "mensagem", "campos"}
    assert isinstance(corpo["erro"]["mensagem"], str) and corpo["erro"]["mensagem"]


def test_validacao_vira_formato_padrao_com_campos(client):
    r = client.post(f"{API}/auth/cadastro", json={"email": "invalido", "senha": "x"})
    assert r.status_code == 422
    corpo = r.json()
    _formato_ok(corpo)
    campos = corpo["erro"]["campos"]
    assert corpo["erro"]["codigo"] == "dados_invalidos"
    assert campos["empresa"] == "Preencha este campo."
    assert "e-mail válido" in campos["email"]
    assert "aceite_termos" in campos


def test_json_quebrado_404_e_401(client):
    r = client.post(f"{API}/auth/entrar", content=b"{nao json", headers={"Content-Type": "application/json"})
    assert r.status_code == 422
    _formato_ok(r.json())
    r = client.get(f"{API}/nao-existe")
    assert r.status_code == 404 and r.json()["erro"]["codigo"] == "nao_encontrado"
    r = client.get(f"{API}/eu")
    assert r.status_code == 401
    _formato_ok(r.json())
    assert r.headers.get("x-request-id")


@pytest.fixture
def limite_ligado():
    limiter.enabled = True
    limiter.reset()
    yield
    limiter.enabled = False
    limiter.reset()


def test_limite_de_tentativas_no_entrar(client, limite_ligado):
    corpo = {"email": "ninguem@alfa.com.br", "senha": SENHA}
    codigos = [client.post(f"{API}/auth/entrar", json=corpo).status_code for _ in range(6)]
    assert codigos == [401] * 5 + [429]
    r = client.post(f"{API}/auth/entrar", json=corpo)
    _formato_ok(r.json())
    assert r.json()["erro"] == {"codigo": "muitas_tentativas",
                                "mensagem": "Muitas tentativas. Aguarde um minuto.", "campos": {}}


def test_limite_mais_baixo_no_esqueci(client, limite_ligado):
    codigos = [client.post(f"{API}/auth/esqueci-senha", json={"email": "a@alfa.com.br"}).status_code
               for _ in range(4)]
    assert codigos == [200, 200, 200, 429]


def test_cors_permite_so_origem_configurada(client):
    ok = client.options(f"{API}/auth/entrar", headers={
        "Origin": "http://app.teste", "Access-Control-Request-Method": "POST"})
    ruim = client.options(f"{API}/auth/entrar", headers={
        "Origin": "http://malicioso.com", "Access-Control-Request-Method": "POST"})
    assert ok.headers.get("access-control-allow-origin") == "http://app.teste"
    assert "access-control-allow-origin" not in ruim.headers


def test_cors_expoe_o_nome_dos_arquivos(client):
    """O site fica em outra origem: sem expor o Content-Disposition, os CSV baixam com o nome genérico."""
    r = client.get(f"{API}/importacao/modelo", headers={"Origin": "http://app.teste"})
    assert "content-disposition" in r.headers.get("access-control-expose-headers", "").lower()

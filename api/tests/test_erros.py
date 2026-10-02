"""Formato de erro e limite de tentativas; valor recusado pelo banco vira 422 em qualquer rota."""
import logging

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from util import SENHA, conta_pronta

from toqqi.core.errors import dado_invalido, erro_do_banco
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


# ---- valor recusado pelo banco (rede de proteção das rotas antigas) ----------------------------

def test_dado_recusado_pelo_banco_vira_422_sem_dados_no_log(client, caplog):
    """Id além do bigint (no caminho ou num filtro) e NUL numa busca, em rotas que não validam isso: 422
    `dados_invalidos` (e não 500); o log registra pelo log_seguro, sem o valor enviado."""
    h = conta_pronta(client, "ana@alfa.com.br", empresa="Alfa")["h"]
    segredo = "SEGREDO" + "-DO-CLIENTE"  # montado aqui: a linha do teste não aparece com o texto no traceback
    with caplog.at_level(logging.WARNING, logger="toqqi"):
        for r in (client.get(f"{API}/contatos/{2**63}", headers=h),
                  client.get(f"{API}/contatos", headers=h, params={"empresa_id": 10**30}),
                  client.patch(f"{API}/empresas/{2**64}", headers=h, json={"nome": "Mercado"}),
                  client.get(f"{API}/contatos", headers=h, params={"busca": f"{segredo}\x00"})):
            assert r.status_code == 422, r.text
            assert r.json()["erro"] == {"codigo": "dados_invalidos", "mensagem": "Confira os dados enviados.",
                                        "campos": {}}
    assert caplog.text.count("Dado recusado pelo banco, respondido com 422") == 4
    assert "SQLSTATE 22003" in caplog.text and "Erro de banco" not in caplog.text
    assert segredo not in caplog.text and str(2**63) not in caplog.text
    assert client.get(f"{API}/contatos/{2**63 - 1}", headers=h).status_code == 404  # no limite: só não existe


def _erro(dono, *comandos, **params) -> DBAPIError:
    with dono.connect() as c:
        try:
            for comando in comandos:
                r = c.execute(text(comando), params)
                if r.returns_rows:
                    r.all()
        except DBAPIError as e:
            return e
    raise AssertionError("o banco deveria recusar")


@pytest.mark.parametrize("comandos,params,invalido", [
    (["select cast('12a' as integer)"], {}, True),  # 22P02
    (["select 9223372036854775807::bigint + 1"], {}, True),  # 22003
    (["select convert_from('\\x00'::bytea, 'UTF8')"], {}, True),  # 22021
    (["create temp table t_curto (v varchar(2)) on commit drop", "insert into t_curto values ('abc') returning v"],
     {}, True),  # 22001
    (["select :v"], {"v": "a\x00b"}, True),  # NUL: o psycopg recusa antes de enviar (sem SQLSTATE)
    (["select 1 / 0"], {}, False),  # 22012: erro nosso, segue 500
    (["select 'infinity'::date"], {}, False),  # data que o Python não lê: erro nosso, segue 500
])
def test_quais_erros_do_banco_sao_dado_invalido(dono, comandos, params, invalido):
    e = _erro(dono, *comandos, **params)
    assert dado_invalido(e) is invalido
    erro = erro_do_banco(e)
    assert (erro is not None and (erro.status, erro.codigo) == (422, "dados_invalidos")) is invalido

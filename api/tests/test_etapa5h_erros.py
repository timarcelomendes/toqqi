"""Etapa 5h, aviso de erros (docs/api-etapa-5h.md §4): limpeza dos textos (e-mails, CPF/CNPJ, telefones, tokens,
UUIDs, texto entre aspas, endereços), pilha e impressão estável, registro (upsert, contagem, reabrir, nunca lança, limite
por minuto, descanso depois de uma falha), tratadores de 500 (registram com a rota-modelo, o request id e a conta; os
4xx não), tarefas (a que falha registra e as outras seguem), POST /publico/erros (validação, limite, sem login, 4 KB),
GET /saude (ok e banco fora → 503), e-mail diário (8h, uma vez por dia, só com erro aberto nas últimas 24 h, só para
superadmins confirmados e ativos), limpeza de 30 dias e Plataforma › Erros (filtros, resolver e reabrir, 403)."""
import logging
from datetime import datetime, time

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from util import API, auth, cadastrar, conta_pronta, emails_para, entrar, fixar_relogio, membro, sql, superadmin

from toqqi import tarefas
from toqqi.core import erros, relogio
from toqqi.core.config import config
from toqqi.core.db import modo_sistema
from toqqi.core.email import caixa_memoria
from toqqi.core.errors import AppError
from toqqi.core.rate_limit import limiter
from toqqi.modulos.plataforma import erros as plataforma_erros

# ---- utilitários ----------------------------------------------------------------------------------------------

COLUNAS = ("id", "impressao", "origem", "tipo", "mensagem", "local", "pilha", "versao", "ocorrencias", "primeira_em",
           "ultima_em", "ultimo_request_id", "conta_id", "resolvido_em")


def linhas_erros(dono) -> list[dict]:
    return [dict(zip(COLUNAS, x, strict=True))
            for x in sql(dono, f"select {', '.join(COLUNAS)} from erros order by id")]


def unico(dono) -> dict:
    linhas = linhas_erros(dono)
    assert len(linhas) == 1, linhas
    return linhas[0]


def motor_quebrado():
    """Engine para um banco que não responde (conexão recusada na hora)."""
    return create_engine("postgresql+psycopg://x:y@127.0.0.1:1/nada", connect_args={"connect_timeout": 1})


@pytest.fixture
def limite_ligado():
    limiter.enabled = True
    limiter.reset()
    yield
    limiter.enabled = False
    limiter.reset()


# ---- limpeza dos textos ---------------------------------------------------------------------------------------

@pytest.mark.parametrize("bruto,esperado", [
    ("Falha ao enviar para ana.souza@empresa.com.br agora", "Falha ao enviar para … agora"),
    ("destino a%40b.com.br recusado", "destino … recusado"),
    ("CPF 123.456.789-09 e CPF 12345678909", "CPF … e CPF …"),
    ("CNPJ 11.222.333/0001-81 ou 11222333000181", "CNPJ … ou …"),
    ("telefone (11) 98765-4321, +55 11 3456-7890 e 5511987654321", "telefone (…, +… e …"),
    ("CEP 01310-100, IP 192.168.10.20 e data 2026-10-04", "CEP …, IP … e data …"),
    ("token Zx8kQ2mN4pR6sT8vW0yB2dF4 e AbC-dEf_123-GhI_jkl-MNO", "token … e …"),
    ("id 550e8400-e29b-41d4-a716-446655440000 aqui", "id … aqui"),
    ('valor "João da Silva", \'Maria Souza\', “Ana” e ‘Rua X’', "valor …, …, … e …"),
    ("GET https://toqqi.com/r/abc?email=x&nome=Joao#topo falhou", "GET https://toqqi.com/r/abc falhou"),
    ("erro 500 na linha 12 às 10:30", "erro 500 na linha 12 às 10:30"),  # menos de 4 dígitos ficam
    ("column exclusao_avisada_para does not exist", "column exclusao_avisada_para does not exist"),
    ("várias\n  linhas\tjuntas", "várias linhas juntas"),
    ("CheckViolation, SQLSTATE 23514, restrição x_check", "CheckViolation, SQLSTATE 23514, restrição x_check"),
    ("código 23514 sem o SQLSTATE", "código … sem o SQLSTATE"),
    (None, ""),
])
def test_limpeza_dos_textos(bruto, esperado):
    assert erros.limpar(bruto) == esperado


def test_limpeza_corta_no_maximo():
    assert erros.limpar("palavra " * 10, 30) == "palavra palavra palavra palav…"
    assert len(erros.limpar("palavra " * 100)) == 300


def test_pilha_do_site_mantem_linha_e_coluna_e_limpa_o_resto():
    bruta = "\n".join([
        "TypeError: Cannot read properties of undefined (reading 'nome')",
        "    at Ue (https://toqqi-web.onrender.com/assets/index-B2x9kQ1z.js:12:34567)",
        "    at https://toqqi-web.onrender.com/assets/vendor-AbCdEf12.js?v=3:1:200",
        "Ue@https://toqqi-web.onrender.com/assets/index-B2x9kQ1z.js:12:34567",
        "global code@https://toqqi.com/r/Zx8kQ2mN4pR6sT8vW0yB2dF4h:3:10",
        "",
        "    at enviar (https://toqqi.com/src/utils/x.ts?t=123#a:5:1)",
    ])
    # o hash do build sai do nome dos arquivos (com dígitos, a regra dos tokens comeria "ContatoView-B2x9kQ1z")
    assert erros.limpar_pilha(bruta).splitlines() == [
        "TypeError: Cannot read properties of undefined (reading …)",
        "at Ue (/assets/index.js:12:34567)",
        "at /assets/vendor.js:1:200",
        "Ue@/assets/index.js:12:34567",
        "global code@/r/…:3:10",
        "at enviar (/src/utils/x.ts:5:1)",
    ]
    assert erros.limpar_pilha("at Hn (https://toqqi.com/assets/ContatoView-B2x9kQ1z.js:1:2)") == \
        "at Hn (/assets/ContatoView.js:1:2)"
    assert len(erros.limpar_pilha("at x (/assets/a.js:1:2)\n" * 200)) == 1000


def _falhar_aqui():
    def interna():
        raise ZeroDivisionError("divisão")
    interna()


def test_pilha_da_api_so_com_quadros_do_toqqi_e_sem_codigo():
    try:
        _falhar_aqui()
    except ZeroDivisionError as e:
        pilha = erros.pilha_python(e)
    linhas = pilha.splitlines()
    # a chamada mais recente primeiro; os quadros deste arquivo (fora de toqqi/) só entram como o mais interno
    assert linhas[0].startswith("interna (") and linhas[0].endswith(f":{_falhar_aqui.__code__.co_firstlineno + 2})")
    assert len(linhas) == 1
    assert "raise" not in pilha and "divisão" not in pilha

    from toqqi.core import parametros

    try:
        parametros.validar("planos", {"x": 1})
    except AppError as e:
        pilha = erros.pilha_python(e)
    assert all("(toqqi/core/parametros.py:" in x for x in pilha.splitlines())


def test_impressao_estavel_entre_linhas_e_builds():
    api = erros.impressao("api", "ZeroDivisionError", "GET /api/v1/acoes/{acao_id}",
                          "execute (sqlalchemy/engine/base.py:1967)\nobter (toqqi/modulos/acoes/servico.py:120)")
    outra_linha = erros.impressao("api", "ZeroDivisionError", "GET /api/v1/acoes/{acao_id}",
                                  "execute (sqlalchemy/engine/base.py:2001)\nobter (toqqi/modulos/acoes/servico.py:131)")
    outra_funcao = erros.impressao("api", "ZeroDivisionError", "GET /api/v1/acoes/{acao_id}",
                                   "listar (toqqi/modulos/acoes/servico.py:120)")
    outra_rota = erros.impressao("api", "ZeroDivisionError", "GET /api/v1/acoes",
                                 "obter (toqqi/modulos/acoes/servico.py:120)")
    assert api == outra_linha
    assert len({api, outra_funcao, outra_rota}) == 3
    site = erros.impressao("site", "TypeError", "/contatos/:id", "TypeError: x\nat Ue (/assets/index-B2x9kQ1z.js:12:3)")
    outro_build = erros.impressao("site", "TypeError", "/contatos/:id", "TypeError: x\nat Ue (/assets/index-Qq81mZ0a.js:14:9)")
    assert site == outro_build
    assert erros.linha_util("site", "TypeError: x\nat Ue (/assets/index-B2x9kQ1z.js:12:3)") == "at Ue (/assets/index.js)"


def test_versao_da_api(monkeypatch):
    monkeypatch.delenv("RENDER_GIT_COMMIT", raising=False)
    assert erros.versao_api() == "local"
    monkeypatch.setenv("RENDER_GIT_COMMIT", "a1b2c3d4e5f6a7b8c9d0a1b2c3d4e5f6a7b8c9d0")
    assert erros.versao_api() == "a1b2c3d"


# ---- registro ------------------------------------------------------------------------------------------------

def test_registro_upsert_contagem_e_reabre(dono):
    assert erros.registrar("site", "TypeError", "falhou para ana@alfa.com.br", "/contatos/:id?busca=Ana#x",
                           "TypeError: falhou\nat Ue (/assets/index-B2x9kQ1z.js:1:2)", "abc1234", conta_id=7)
    e = unico(dono)
    assert (e["origem"], e["tipo"], e["mensagem"], e["local"], e["versao"], e["ocorrencias"], e["conta_id"]) == (
        "site", "TypeError", "falhou para …", "/contatos/:id", "abc1234", 1, 7)
    assert e["primeira_em"] == e["ultima_em"] and e["resolvido_em"] is None and len(e["impressao"]) == 64
    sql(dono, "update erros set resolvido_em = now(), ultima_em = now() - interval '1 hour', "
              "primeira_em = now() - interval '2 hours'")
    # a mesma falha, noutra linha do mesmo arquivo do build e sem conta: soma, reabre e fica a última mensagem
    assert erros.registrar("site", "TypeError", "falhou de novo", "/contatos/:id",
                           "TypeError: falhou\nat Ue (/assets/index-Qq81mZ0a.js:9:9)", "def5678")
    e2 = unico(dono)
    assert (e2["ocorrencias"], e2["mensagem"], e2["versao"], e2["conta_id"], e2["resolvido_em"]) == (
        2, "falhou de novo", "def5678", 7, None)
    assert e2["ultima_em"] > e["ultima_em"] and e2["primeira_em"] < e2["ultima_em"]
    # outra tela: outro erro
    assert erros.registrar("site", "TypeError", "falhou", "/respostas", "")
    assert len(linhas_erros(dono)) == 2


def test_registro_valida_e_corta(dono):
    assert erros.registrar("nada", "X") is False  # origem desconhecida: não lança
    assert erros.registrar("site", "", "palavra " * 100, "/tela" * 60, "x\n" * 900, "versão com espaço!") is True
    e = unico(dono)
    assert e["tipo"] == "Error" and len(e["mensagem"]) == 300 and len(e["local"]) == 200
    assert e["mensagem"].endswith("…") and e["local"].startswith("/tela/tela")
    assert len(e["pilha"]) <= 1000 and e["versao"] == "versocomespao"
    assert erros.registrar("site", "Y", versao=None) and linhas_erros(dono)[1]["versao"] == "desconhecida"


def test_registro_nunca_lanca_e_descansa_depois_de_falhar(dono, monkeypatch, caplog):
    agora = [1000.0]
    real = erros.engine_erros
    monkeypatch.setattr(erros, "_monotonico", lambda: agora[0])
    monkeypatch.setattr(erros, "engine_erros", motor_quebrado)
    with caplog.at_level(logging.WARNING, logger="toqqi"):
        assert erros.registrar("api", "ValueError", "x", "GET /x") is False
    assert "não foi possível registrar um erro (OperationalError" in caplog.text
    monkeypatch.setattr(erros, "engine_erros", real)
    agora[0] += 5  # ainda no descanso: nem tenta
    assert erros.registrar("api", "ValueError", "x", "GET /x") is False
    assert linhas_erros(dono) == []
    agora[0] += 6
    assert erros.registrar("api", "ValueError", "x", "GET /x") is True
    assert unico(dono)["ocorrencias"] == 1


def test_limite_por_minuto(dono, monkeypatch, caplog):
    agora = [60.0 * 1000]
    monkeypatch.setattr(erros, "_monotonico", lambda: agora[0])
    monkeypatch.setattr(erros, "LIMITE_POR_MINUTO", 3)
    with caplog.at_level(logging.WARNING, logger="toqqi"):
        feitos = [erros.registrar("api", "E", f"m{i}", f"GET /x{i}") for i in range(5)]
        assert feitos == [True, True, True, False, False]
        assert caplog.text.count("limite de 3 registros por minuto atingido") == 1
        agora[0] += 60  # o minuto virou: volta a registrar e conta os que ficaram de fora
        assert erros.registrar("api", "E", "m9", "GET /x9") is True
    assert "2 erro(s) do último minuto não foram registrados" in caplog.text
    assert len(linhas_erros(dono)) == 4


def test_mensagem_do_key_error_sem_as_aspas(dono):
    assert erros.mensagem_da_excecao(KeyError("coluna nome ausente")) == "coluna nome ausente"
    assert erros.registrar_excecao(KeyError("ana@cliente.com.br"), "tarefa", "robo")
    assert unico(dono)["mensagem"] == "…"
    assert erros.mensagem_da_excecao(KeyError(3)) == "3"


def test_excecao_do_banco_vira_resumo_sem_dados(dono):
    with pytest.raises(Exception) as info, modo_sistema() as s:  # noqa: PT011, PT012 - qualquer erro do banco
        s.execute(text("insert into erros (impressao, origem, tipo, versao) values ('x', 'site', 'Ana Silva', 'v')"))
    assert erros.registrar_excecao(info.value, "tarefa", "resumo")
    e = unico(dono)
    assert e["tipo"] == "IntegrityError"
    assert e["mensagem"] == "CheckViolation, SQLSTATE 23514, restrição erros_impressao_check, tabela erros"
    assert "Ana Silva" not in str(e) and e["local"] == "resumo" and e["origem"] == "tarefa"


# ---- tratadores de 500 ---------------------------------------------------------------------------------------

@pytest.fixture(scope="module")
def app_falhas(dono):
    """A aplicação de sempre com rotas que falham de propósito."""
    from toqqi.main import create_app

    a = create_app()

    @a.get("/api/v1/teste-5h/falha/{item_id}")
    def falha(item_id: int):
        raise ZeroDivisionError(f"divisão por zero para ana@alfa.com.br no item {item_id}")

    @a.get("/api/v1/teste-5h/banco")
    def banco():
        with modo_sistema() as s:
            s.execute(text("insert into erros (impressao, origem, tipo, versao) values ('x', 'site', 'Ana Silva', 'v')"))

    @a.get("/api/v1/teste-5h/conflito")
    def conflito():
        raise AppError(409, "conflito", "Já existe.")

    @a.get("/api/v1/teste-5h/dado")
    def dado():
        with modo_sistema() as s:
            s.execute(text("select cast('12a' as integer)"))

    return a


@pytest.fixture
def falhas(app_falhas):
    with TestClient(app_falhas, raise_server_exceptions=False) as c:
        yield c


def test_500_registra_com_rota_modelo_request_id_e_conta(client, falhas, dono):
    a = conta_pronta(client, "ana@alfa.com.br", empresa="Alfa")
    r = falhas.get(f"{API}/teste-5h/falha/123456", headers={**a["h"], "X-Request-ID": "rid-teste-5h"})
    assert r.status_code == 500
    assert r.json()["erro"] == {"codigo": "erro_interno", "campos": {},
                                "mensagem": "Algo deu errado do nosso lado. Tente de novo em instantes."}
    assert r.headers["x-request-id"] == "rid-teste-5h"
    e = unico(dono)
    assert (e["origem"], e["tipo"], e["local"], e["ultimo_request_id"], e["conta_id"], e["versao"]) == (
        "api", "ZeroDivisionError", "GET /api/v1/teste-5h/falha/{item_id}", "rid-teste-5h", a["conta"]["id"], "local")
    assert e["mensagem"] == "divisão por zero para … no item …"
    assert e["pilha"].splitlines()[0].startswith("falha (") and "123456" not in str(e)
    # sem login, sem request id do cliente: o gerado pela API, e a mesma impressão (+1)
    r = falhas.get(f"{API}/teste-5h/falha/7")
    assert r.status_code == 500 and len(r.headers["x-request-id"]) == 32
    e = unico(dono)
    assert e["ocorrencias"] == 2 and e["ultimo_request_id"] == r.headers["x-request-id"]
    assert e["conta_id"] == a["conta"]["id"]  # a última conta conhecida fica


def test_500_do_banco_registra_o_resumo_sem_dados(falhas, dono):
    r = falhas.get(f"{API}/teste-5h/banco")
    assert r.status_code == 500 and r.json()["erro"]["codigo"] == "erro_interno"
    e = unico(dono)
    assert (e["tipo"], e["local"]) == ("IntegrityError", "GET /api/v1/teste-5h/banco")
    assert e["mensagem"].startswith("CheckViolation, SQLSTATE 23514") and "Ana Silva" not in str(e)


def test_4xx_nao_registram(client, falhas, dono):
    h = conta_pronta(client, "ana@alfa.com.br", empresa="Alfa")["h"]
    assert falhas.get(f"{API}/teste-5h/conflito").status_code == 409
    assert falhas.get(f"{API}/teste-5h/dado").status_code == 422  # valor recusado pelo banco
    assert falhas.get(f"{API}/teste-5h/falha/abc").status_code == 422  # validação
    assert falhas.get(f"{API}/nao-existe").status_code == 404
    assert client.get(f"{API}/plataforma/erros", headers=h).status_code == 403
    assert client.get(f"{API}/eu").status_code == 401
    assert linhas_erros(dono) == []


def test_500_segue_mesmo_com_o_registro_quebrado(falhas, dono, monkeypatch, caplog):
    monkeypatch.setattr(erros, "engine_erros", motor_quebrado)
    with caplog.at_level(logging.WARNING, logger="toqqi"):
        r = falhas.get(f"{API}/teste-5h/falha/1")
    assert r.status_code == 500 and r.json()["erro"]["codigo"] == "erro_interno"
    assert "não foi possível registrar um erro" in caplog.text
    assert linhas_erros(dono) == []


def test_rota_de_verdade_com_parametro(client, dono, monkeypatch):
    from toqqi.modulos.acoes import servico as acoes

    h = conta_pronta(client, "ana@alfa.com.br", empresa="Alfa")["h"]

    def quebrar(*_a, **_k):
        raise RuntimeError("quebrou")

    monkeypatch.setattr(acoes, "obter_acao", quebrar)
    sem_excecoes = TestClient(client.app, raise_server_exceptions=False)
    assert sem_excecoes.get(f"{API}/acoes/987654", headers=h).status_code == 500
    e = unico(dono)
    assert (e["tipo"], e["local"], e["mensagem"]) == ("RuntimeError", "GET /api/v1/acoes/{acao_id}", "quebrou")


# ---- tarefas -------------------------------------------------------------------------------------------------

def test_tarefa_que_falha_registra_e_as_outras_seguem(dono, monkeypatch, capsys):
    from toqqi.modulos.envios import automacao

    def quebrar():
        raise RuntimeError("robô quebrou na conta 12345")

    monkeypatch.setattr(automacao, "robo", quebrar)
    r = tarefas.executar("tudo")
    assert r["robo"] == {"erro": "RuntimeError"}
    assert list(r) == ["assinaturas", "pendentes", "robo", "lembretes", "webhooks", "conectores", "ia", "picos", "resumo",
                       "erros", "limpeza"]
    assert r["lembretes"] == {"contas": 0, "enviados": 0, "ignorados": 0}
    e = unico(dono)
    assert (e["origem"], e["tipo"], e["local"], e["mensagem"], e["conta_id"], e["ultimo_request_id"]) == (
        "tarefa", "RuntimeError", "robo", "robô quebrou na conta …", None, None)
    assert e["pilha"].splitlines()[0].startswith("quebrar (")
    assert any(x.startswith("executar (toqqi/tarefas.py:") for x in e["pilha"].splitlines())
    # pela linha de comando: o resumo sai e a saída é 1
    assert tarefas.main(["robo"]) == 1
    assert '"robo": {"erro": "RuntimeError"}' in capsys.readouterr().out
    assert unico(dono)["ocorrencias"] == 2
    assert tarefas.main(["pendentes"]) == 0


def test_tarefa_segue_mesmo_com_o_registro_quebrado(dono, monkeypatch):
    from toqqi.modulos.envios import automacao

    monkeypatch.setattr(automacao, "pendentes", lambda: 1 / 0)
    monkeypatch.setattr(erros, "engine_erros", motor_quebrado)
    r = tarefas.executar("tudo")
    assert r["pendentes"] == {"erro": "ZeroDivisionError"} and r["robo"] == {"contas": 0, "agendados": 0,
                                                                              "ignorados": 0}


# ---- POST /publico/erros ---------------------------------------------------------------------------------------

ERRO_SITE = {"tipo": "TypeError", "mensagem": "Cannot read properties of undefined (reading 'nome') de ana@x.com",
             "local": "/contatos/:id", "pilha": "TypeError: x\n    at Ue (https://toqqi.com/assets/index-B2x9kQ1z.js:3:9)",
             "versao": "a1b2c3d"}


def test_erro_do_site_sem_login(client, dono):
    r = client.post(f"{API}/publico/erros", json=ERRO_SITE)
    assert r.status_code == 204 and r.content == b""
    e = unico(dono)
    assert (e["origem"], e["tipo"], e["local"], e["versao"], e["conta_id"], e["ultimo_request_id"]) == (
        "site", "TypeError", "/contatos/:id", "a1b2c3d", None, None)
    assert e["mensagem"] == "Cannot read properties of undefined (reading …) de …"
    assert e["pilha"] == "TypeError: x\nat Ue (/assets/index.js:3:9)"
    assert client.post(f"{API}/publico/erros", json={**ERRO_SITE, "versao": ""}).status_code == 204
    assert unico(dono)["ocorrencias"] == 2 and unico(dono)["versao"] == "desconhecida"


def test_erro_do_site_com_a_sessao_guarda_a_conta(client, dono):
    a = conta_pronta(client, "ana@alfa.com.br", empresa="Alfa")
    assert client.post(f"{API}/publico/erros", json=ERRO_SITE, headers=a["h"]).status_code == 204
    assert unico(dono)["conta_id"] == a["conta"]["id"]
    # token inválido não dá 401: só fica sem conta
    sql(dono, "delete from erros")
    assert client.post(f"{API}/publico/erros", json=ERRO_SITE, headers=auth("token-falso")).status_code == 204
    assert unico(dono)["conta_id"] is None


@pytest.mark.parametrize("corpo,campo", [
    ({"mensagem": "x"}, "tipo"),
    ({"tipo": ""}, "tipo"),
    ({"tipo": "x" * 201}, "tipo"),
    ({"tipo": "E", "mensagem": "m" * 2001}, "mensagem"),
    ({"tipo": "E", "versao": "a b"}, "versao"),
    ({"tipo": "E", "pilha": ["lista"]}, "pilha"),
])
def test_erro_do_site_validacao(client, dono, corpo, campo):
    r = client.post(f"{API}/publico/erros", json=corpo)
    assert r.status_code == 422 and campo in r.json()["erro"]["campos"]
    assert linhas_erros(dono) == []


def test_erro_do_site_corpo_ate_4kb(client, dono):
    r = client.post(f"{API}/publico/erros", json={"tipo": "E", "pilha": "x" * 3900, "mensagem": "m" * 400})
    assert r.status_code == 413 and r.json()["erro"]["codigo"] == "pedido_grande_demais"
    assert linhas_erros(dono) == []
    assert client.post(f"{API}/publico/erros", json={"tipo": "E", "pilha": "x" * 3500}).status_code == 204


def test_erro_do_site_limite_por_ip(client, dono, limite_ligado):
    codigos = [client.post(f"{API}/publico/erros", json=ERRO_SITE).status_code for _ in range(11)]
    assert codigos == [204] * 10 + [429]
    assert unico(dono)["ocorrencias"] == 10
    with TestClient(client.app, client=("198.51.100.9", 50000)) as outro:
        assert outro.post(f"{API}/publico/erros", json=ERRO_SITE).status_code == 204


# ---- GET /saude --------------------------------------------------------------------------------------------------

def test_saude_ok(client, monkeypatch):
    monkeypatch.delenv("RENDER_GIT_COMMIT", raising=False)
    r = client.get(f"{API}/saude")
    assert r.status_code == 200 and r.json() == {"ok": True, "banco": True, "versao": "local"}
    assert r.headers["cache-control"] == "no-store"
    monkeypatch.setenv("RENDER_GIT_COMMIT", "0123456789abcdef")
    assert client.get(f"{API}/saude").json()["versao"] == "0123456"


def test_saude_com_o_banco_fora(client, monkeypatch, caplog):
    import toqqi.main

    monkeypatch.setattr(toqqi.main, "engine", motor_quebrado)
    with caplog.at_level(logging.WARNING, logger="toqqi"):
        r = client.get(f"{API}/saude")
    assert r.status_code == 503 and r.json() == {"ok": False, "banco": False, "versao": "local"}
    assert "Saúde: o banco não respondeu (OperationalError" in caplog.text


# ---- e-mail diário -----------------------------------------------------------------------------------------------

def _hoje_as(monkeypatch, hora: int, minuto: int = 0) -> datetime:
    momento = datetime.combine(datetime.now(relogio.FUSO).date(), time(hora, minuto), tzinfo=relogio.FUSO)
    fixar_relogio(monkeypatch, momento)
    return momento


def _marcas(dono) -> list:
    return sql(dono, "select detalhe from auditoria where evento = 'erros_avisados' and conta_id is null")


def test_email_diario_so_depois_das_8h_e_uma_vez_por_dia(client, dono, monkeypatch):
    superadmin(client)
    caixa_memoria.clear()
    erros.registrar("api", "ZeroDivisionError", "divisão", "GET /api/v1/painel", "painel (toqqi/x.py:1)")
    erros.registrar("api", "ZeroDivisionError", "divisão", "GET /api/v1/painel", "painel (toqqi/x.py:2)")
    _hoje_as(monkeypatch, 7, 59)
    assert tarefas.executar("erros") == {"erros": None}
    assert emails_para("root@toqqi.com") == []
    _hoje_as(monkeypatch, 8)
    assert tarefas.executar("erros") == {"erros": {"erros": 1, "emails": 1}}
    (m,) = emails_para("root@toqqi.com")
    assert m.assunto == "Toqqi: 1 erro nas últimas 24 h"
    assert "ZeroDivisionError em GET /api/v1/painel (API): 2 vezes, a última em" in m.texto
    assert "Abrir Plataforma › Erros: http://app.teste/plataforma/erros" in m.texto
    assert m.texto.rstrip().endswith("só quando há erro aberto em Plataforma › Erros. http://app.teste/plataforma/erros")
    assert 'href="http://app.teste/plataforma/erros"' in m.html
    assert _marcas(dono) == [({"erros": 1, "emails": 1},)]
    # de novo no mesmo dia, com um erro novo: nada
    erros.registrar("site", "TypeError", "x", "/inicio", "")
    _hoje_as(monkeypatch, 15)
    assert tarefas.executar("erros") == {"erros": None}
    assert len(emails_para("root@toqqi.com")) == 1 and len(_marcas(dono)) == 1


def test_email_diario_so_com_erro_aberto_nas_ultimas_24h(client, dono, monkeypatch):
    superadmin(client)
    caixa_memoria.clear()
    _hoje_as(monkeypatch, 9)
    assert plataforma_erros.aviso_diario() == {"erros": 0, "emails": 0}  # nenhum erro: não marca o dia
    erros.registrar("api", "A", "", "GET /a", "")
    erros.registrar("api", "B", "", "GET /b", "")
    sql(dono, "update erros set resolvido_em = now() where tipo = 'A'")
    sql(dono, "update erros set ultima_em = now() - interval '25 hours' where tipo = 'B'")
    assert plataforma_erros.aviso_diario() == {"erros": 0, "emails": 0}
    assert caixa_memoria == [] and _marcas(dono) == []
    # a nova ocorrência de B (reaberto e dentro das 24 h) manda
    erros.registrar("api", "B", "", "GET /b", "")
    assert plataforma_erros.aviso_diario() == {"erros": 1, "emails": 1}
    assert len(_marcas(dono)) == 1


def test_email_diario_so_para_superadmins_confirmados_e_ativos(client, dono, monkeypatch, caplog):
    monkeypatch.setattr(config(), "SUPERADMIN_EMAILS",
                        "root@toqqi.com, BIA@toqqi.com, ninguem@toqqi.com, cris@toqqi.com")
    root = superadmin(client)
    cadastrar(client, "bia@toqqi.com", empresa="Toqqi B")  # e-mail não confirmado
    membro(client, root["h"], "cris@toqqi.com", perfil="gestor")  # confirmado e ativo
    conta_pronta(client, "ana@alfa.com.br", empresa="Alfa")  # cliente: nunca recebe
    caixa_memoria.clear()
    erros.registrar("tarefa", "RuntimeError", "x", "resumo", "")
    _hoje_as(monkeypatch, 10)
    with modo_sistema() as s:
        assert plataforma_erros.superadmins_confirmados(s) == ["cris@toqqi.com", "root@toqqi.com"]
    sql(dono, "update usuarios set situacao = 'bloqueado' where email = 'cris@toqqi.com'")
    assert plataforma_erros.aviso_diario() == {"erros": 1, "emails": 1}
    assert [m.para for m in caixa_memoria] == ["root@toqqi.com"]
    # sem nenhum superadmin confirmado: não manda nem marca o dia (a próxima rodada confere de novo)
    sql(dono, "delete from auditoria where evento = 'erros_avisados'")
    sql(dono, "update usuarios set email_confirmado = false where email = 'root@toqqi.com'")
    caixa_memoria.clear()
    with caplog.at_level(logging.WARNING, logger="toqqi"):
        assert plataforma_erros.aviso_diario() == {"erros": 1, "emails": 0}
    assert caixa_memoria == [] and _marcas(dono) == []
    assert "nenhum superadmin com o e-mail confirmado" in caplog.text


def test_email_diario_os_10_mais_frequentes(client, dono, monkeypatch):
    superadmin(client)
    caixa_memoria.clear()
    for i in range(12):
        for _ in range(i + 1):
            erros.registrar("site", f"Erro{i:02d}", "", f"/tela{i}", "")
    _hoje_as(monkeypatch, 9)
    assert plataforma_erros.aviso_diario() == {"erros": 12, "emails": 1}
    (m,) = caixa_memoria
    assert m.assunto == "Toqqi: 12 erros nas últimas 24 h"
    linhas = [x for x in m.texto.splitlines() if x.startswith("Erro")]
    assert [x.split(" ")[0] for x in linhas] == [f"Erro{i:02d}" for i in range(11, 1, -1)]
    assert linhas[0].startswith("Erro11 em /tela11 (site): 12 vezes, a última em ")
    assert linhas[-1].startswith("Erro02 em /tela2 (site): 3 vezes, a última em ")
    assert "E mais 2 erros na lista." in m.texto and "OS 10 MAIS FREQUENTES" in m.texto


def test_email_diario_sem_provedor_pula(client, dono, monkeypatch):
    superadmin(client)
    erros.registrar("api", "A", "", "GET /a", "")
    _hoje_as(monkeypatch, 9)
    monkeypatch.setattr(plataforma_erros, "provedor_ok", lambda: False)
    assert plataforma_erros.aviso_diario() is None and _marcas(dono) == []


# ---- limpeza de 30 dias ----------------------------------------------------------------------------------------

def test_limpeza_apaga_os_erros_de_mais_de_30_dias(dono, monkeypatch):
    from toqqi.modulos.assinatura import exclusao

    monkeypatch.setattr(exclusao, "executar", lambda: None)
    for tipo in ("Velho", "Quase", "Novo"):
        erros.registrar("api", tipo, "", f"GET /{tipo}", "")
    sql(dono, "update erros set ultima_em = now() - interval '30 days 1 minute' where tipo = 'Velho'")
    sql(dono, "update erros set ultima_em = now() - interval '29 days 23 hours' where tipo = 'Quase'")
    assert tarefas.limpeza()["erros_apagados"] == 1
    assert [e["tipo"] for e in linhas_erros(dono)] == ["Quase", "Novo"]
    assert tarefas.executar("limpeza")["limpeza"]["erros_apagados"] == 0


# ---- Plataforma › Erros ------------------------------------------------------------------------------------------

def _lista(client, h, **filtros) -> list[dict]:
    r = client.get(f"{API}/plataforma/erros", headers=h, params=filtros)
    assert r.status_code == 200, r.text
    return r.json()


def test_lista_filtros_ordem_e_conta(client, dono):
    root = superadmin(client)
    alfa = conta_pronta(client, "ana@alfa.com.br", empresa="Alfa")
    erros.registrar("api", "A", "a", "GET /a", "", conta_id=alfa["conta"]["id"])
    erros.registrar("site", "B", "b", "/b", "")
    erros.registrar("tarefa", "C", "c", "resumo", "", conta_id=999999)  # conta que não existe mais
    erros.registrar("api", "D", "d", "GET /d", "")
    sql(dono, "update erros set ultima_em = now() - interval '10 days' where tipo = 'D'")
    sql(dono, "update erros set ultima_em = now() - interval '1 hour' where tipo = 'A'")
    sql(dono, "update erros set resolvido_em = now() where tipo = 'B'")
    h = root["h"]
    abertos = _lista(client, h)
    assert [e["tipo"] for e in abertos] == ["C", "A"]  # padrão: abertos dos últimos 7 dias, a última mais recente 1º
    a = abertos[1]
    assert set(a) == {"id", "origem", "tipo", "mensagem", "local", "pilha", "versao", "ocorrencias", "primeira_em",
                      "ultima_em", "ultimo_request_id", "conta_id", "conta_nome", "resolvido_em"}
    assert (a["conta_id"], a["conta_nome"]) == (alfa["conta"]["id"], "Alfa")
    assert (abertos[0]["conta_id"], abertos[0]["conta_nome"]) == (999999, None)
    assert [e["tipo"] for e in _lista(client, h, situacao="todos")] == ["C", "B", "A"]
    assert [e["tipo"] for e in _lista(client, h, situacao="resolvidos")] == ["B"]
    assert [e["tipo"] for e in _lista(client, h, situacao="todos", dias=30)] == ["C", "B", "A", "D"]
    assert [e["tipo"] for e in _lista(client, h, situacao="todos", dias=30, origem="api")] == ["A", "D"]
    assert [e["tipo"] for e in _lista(client, h, origem="")] == ["C", "A"]
    for filtros, campo in (({"dias": 10}, "dias"), ({"situacao": "x"}, "situacao"), ({"origem": "x"}, "origem")):
        r = client.get(f"{API}/plataforma/erros", headers=h, params=filtros)
        assert r.status_code == 422 and campo in r.json()["erro"]["campos"]


def test_resolver_e_reabrir(client, dono):
    h = superadmin(client)["h"]
    erros.registrar("api", "A", "a", "GET /a", "")
    (eid,) = [e["id"] for e in _lista(client, h)]
    r = client.post(f"{API}/plataforma/erros/{eid}/resolver", headers=h)
    assert r.status_code == 200 and r.json()["resolvido_em"] is not None and r.json()["id"] == eid
    resolvido_em = r.json()["resolvido_em"]
    assert _lista(client, h) == []
    assert client.post(f"{API}/plataforma/erros/{eid}/resolver", headers=h).json()["resolvido_em"] == resolvido_em
    r = client.post(f"{API}/plataforma/erros/{eid}/reabrir", headers=h)
    assert r.status_code == 200 and r.json()["resolvido_em"] is None
    assert [e["id"] for e in _lista(client, h)] == [eid]
    for acao in ("resolver", "reabrir"):
        r = client.post(f"{API}/plataforma/erros/999999/{acao}", headers=h)
        assert r.status_code == 404 and r.json()["erro"]["codigo"] == "nao_encontrado"
    assert client.post(f"{API}/plataforma/erros/0/resolver", headers=h).status_code == 422


def test_rotas_so_para_superadmin(client, dono, monkeypatch):
    erros.registrar("api", "A", "a", "GET /a", "")
    cliente = conta_pronta(client, "ana@alfa.com.br", empresa="Alfa")
    monkeypatch.setattr(config(), "SUPERADMIN_EMAILS", "root@toqqi.com, bia@toqqi.com")
    cadastrar(client, "bia@toqqi.com", empresa="Toqqi B")
    sql(dono, "update usuarios set email_confirmado = true where email = 'bia@toqqi.com'")
    bia = auth(entrar(client, "bia@toqqi.com").json()["token"])
    sql(dono, "update usuarios set email_confirmado = false where email = 'bia@toqqi.com'")  # deixou de confirmar
    (eid,), = sql(dono, "select id from erros")
    for h in (cliente["h"], bia):
        for metodo, caminho in (("get", "/plataforma/erros"), ("post", f"/plataforma/erros/{eid}/resolver"),
                                ("post", f"/plataforma/erros/{eid}/reabrir"), ("get", "/plataforma/visao")):
            r = getattr(client, metodo)(f"{API}{caminho}", headers=h)
            assert r.status_code == 403 and r.json()["erro"]["codigo"] == "sem_permissao", (caminho, r.text)
    assert client.get(f"{API}/plataforma/erros").status_code == 401
    assert unico(dono)["resolvido_em"] is None


def test_tempos_em_dias(client, dono):
    """`dias` conta pela última ocorrência: 7 dias e 1 minuto atrás fica fora dos 7 dias."""
    h = superadmin(client)["h"]
    erros.registrar("api", "A", "", "GET /a", "")
    erros.registrar("api", "B", "", "GET /b", "")
    sql(dono, "update erros set ultima_em = now() - interval '7 days 1 minute' where tipo = 'A'")
    sql(dono, "update erros set ultima_em = now() - interval '6 days 23 hours' where tipo = 'B'")
    assert [e["tipo"] for e in _lista(client, h)] == ["B"]
    assert [e["tipo"] for e in _lista(client, h, dias=30)] == ["B", "A"]

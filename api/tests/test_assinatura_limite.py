"""Etapa 5a: o limite de contatos não corre com a troca de plano (duas sessões de verdade, em threads).

O gatilho `contatos_checar_limite` (0008) pega a trava da conta ANTES de ler o plano — sempre, mesmo sem limite — e a
troca para um plano menor segura a mesma trava enquanto confere os contatos ativos e grava o plano. Com a função antiga
(0002: lia o plano e só travava se houvesse limite), uma inclusão feita enquanto a troca de "empresa" (sem limite) para
"essencial" (300) estava em andamento passava: 301 ativos num plano de 300."""
import importlib.util
import threading
import time

import pytest
from sqlalchemy import text
from util import assinar, conta_pronta, encher_contatos, sql, trocar_plano

from toqqi.core import asaas
from toqqi.core.db import RAIZ_API, em_conta


def _migracao():
    spec = importlib.util.spec_from_file_location("m0008", RAIZ_API / "alembic/versions/0008_assinaturas.py")
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


M0008 = _migracao()


@pytest.fixture
def conta_empresa(client, dono, asaas_falso):
    """Conta assinada no plano Empresa (sem limite) com 300 contatos ativos."""
    a = conta_pronta(client, "ana@alfa.com.br", empresa="Alfa")
    assert assinar(client, a["h"], "empresa").status_code == 201
    encher_contatos(dono, a["conta"]["id"], 300)
    return a


def _incluir(conta_id: int, resultado: dict, antes_de_confirmar: threading.Event | None = None) -> None:
    """Inclui um contato ativo numa transação própria (outra sessão do banco)."""
    try:
        with em_conta(conta_id) as s:
            s.execute(text("insert into contatos (conta_id, codigo, nome, email, ativo) values "
                           "(:c, '900000001', 'Concorrente', 'concorrente@c.com.br', true)"), {"c": conta_id})
            resultado["incluido"] = True
            if antes_de_confirmar is not None:
                assert antes_de_confirmar.wait(10)
        resultado["ok"] = True
    except Exception as e:  # noqa: BLE001 - o teste confere
        resultado["erro"] = e


def _esperando_trava(dono) -> bool:
    """Alguma sessão está esperando uma trava consultiva (a do gatilho ou a da troca de plano)?"""
    fim = time.monotonic() + 5
    while time.monotonic() < fim:
        if sql(dono, "select count(*) from pg_locks where locktype = 'advisory' and not granted")[0][0]:
            return True
        time.sleep(0.05)
    return False


def _trocar_em_paralelo(client, h, monkeypatch) -> tuple[threading.Thread, dict, threading.Event, threading.Event]:
    """PUT /assinatura/plano essencial numa thread, parada na chamada ao Asaas (com as travas pegas)."""
    entrou, solta, resposta = threading.Event(), threading.Event(), {}
    original = asaas.atualizar_assinatura

    def lento(*a, **k):
        entrou.set()
        assert solta.wait(10)
        return original(*a, **k)

    monkeypatch.setattr(asaas, "atualizar_assinatura", lento)

    def trocar():
        resposta["r"] = trocar_plano(client, h, "essencial")

    t = threading.Thread(target=trocar)
    t.start()
    return t, resposta, entrou, solta


def _ativos(dono, conta_id: int) -> int:
    return sql(dono, "select count(*) from contatos where conta_id = :c and ativo", c=conta_id)[0][0]


def test_inclusao_durante_a_troca_le_o_plano_novo(client, dono, conta_empresa, monkeypatch):
    conta = conta_empresa["conta"]["id"]
    t, resposta, entrou, solta = _trocar_em_paralelo(client, conta_empresa["h"], monkeypatch)
    assert entrou.wait(10)  # a troca já conferiu 300 ativos e segura a trava
    resultado: dict = {}
    inclusao = threading.Thread(target=_incluir, args=(conta, resultado))
    inclusao.start()
    assert _esperando_trava(dono)  # o gatilho espera a troca, mesmo com o plano atual sem limite
    assert "incluido" not in resultado
    solta.set()
    t.join(10)
    inclusao.join(10)
    assert not t.is_alive() and not inclusao.is_alive()
    assert resposta["r"].status_code == 200, resposta["r"].text
    assert "Seu plano permite até 300 contatos ativos." in str(resultado.get("erro"))  # leu o plano novo
    assert _ativos(dono, conta) == 300
    assert sql(dono, "select plano from contas where id = :c", c=conta) == [("essencial",)]


def test_troca_durante_uma_inclusao_espera_e_conta_o_contato_novo(client, dono, conta_empresa, monkeypatch):
    conta = conta_empresa["conta"]["id"]
    confirma, resultado = threading.Event(), {}
    inclusao = threading.Thread(target=_incluir, args=(conta, resultado, confirma))
    inclusao.start()
    fim = time.monotonic() + 5
    while "incluido" not in resultado and time.monotonic() < fim:
        time.sleep(0.02)
    assert resultado.get("incluido")  # incluído, ainda sem confirmar (segura a trava do gatilho)
    t, resposta, entrou, solta = _trocar_em_paralelo(client, conta_empresa["h"], monkeypatch)
    solta.set()
    assert _esperando_trava(dono)  # a troca espera a inclusão antes de contar
    confirma.set()
    inclusao.join(10)
    t.join(10)
    assert not t.is_alive() and not inclusao.is_alive() and resultado.get("ok")
    r = resposta["r"]
    assert r.status_code == 422 and r.json()["erro"]["codigo"] == "limite_do_plano"
    assert r.json()["erro"]["mensagem"].startswith("Você tem 301 contatos ativos")
    assert not entrou.is_set()  # recusada antes de chamar o Asaas
    assert sql(dono, "select plano from contas where id = :c", c=conta) == [("empresa",)]


def test_com_a_funcao_antiga_a_conta_passava_do_limite(client, dono, conta_empresa, monkeypatch):
    """Reprodução do problema com a função da 0002 (a 0008 a substitui; o downgrade a devolve)."""
    conta = conta_empresa["conta"]["id"]
    sql(dono, M0008.FUNCAO_ANTIGA)
    try:
        t, resposta, entrou, solta = _trocar_em_paralelo(client, conta_empresa["h"], monkeypatch)
        assert entrou.wait(10)
        resultado: dict = {}
        _incluir(conta, resultado)  # não espera nada: o plano "empresa" não tem limite, então não travava
        assert resultado.get("ok")
        solta.set()
        t.join(10)
        assert resposta["r"].status_code == 200
        assert _ativos(dono, conta) == 301
        assert sql(dono, "select limite_contatos(plano, situacao) from contas where id = :c", c=conta) == [(300,)]
    finally:
        sql(dono, M0008.FUNCAO_NOVA)

"""Etapa 5a: plataforma (superadmin) — lista com `pago_ate`, `atrasada_desde` e a assinatura; "+14 dias" recusado com
assinatura ativa ou cortesia (e recalcula a situação); cortesia (e exclusão de conta) remove antes a assinatura no
Asaas (falhou → 503 e nada muda); a exclusão remove também qualquer outra viva com a referência da conta."""
from datetime import date, datetime, time

import httpx
import pytest
from util import API, FUSO, assinar, conta_pronta, fixar_relogio, situacao_conta, sql

from toqqi.core.config import config


def momento(dia: str, hora: int = 10, minuto: int = 0) -> datetime:
    return datetime.combine(date.fromisoformat(dia), time(hora, minuto), tzinfo=FUSO)


@pytest.fixture
def contas(client, dono, monkeypatch):
    fixar_relogio(monkeypatch, momento("2026-10-10"))
    root = conta_pronta(client, "root@toqqi.com", empresa="Toqqi")
    a = conta_pronta(client, "ana@alfa.com.br", empresa="Alfa")
    sql(dono, "update contas set teste_ate = :t where id = :c", t=momento("2026-10-15", 14, 30), c=a["conta"]["id"])
    return root, a


def listar(client, root) -> dict:
    r = client.get(f"{API}/plataforma/contas", headers=root["h"])
    assert r.status_code == 200, r.text
    return {c["nome"]: c for c in r.json()}


def test_lista_com_a_cobranca(client, dono, contas, asaas_falso):
    root, a = contas
    alfa = listar(client, root)["Alfa"]
    assert (alfa["pago_ate"], alfa["atrasada_desde"], alfa["assinatura"]) == (None, None, None)
    assinar(client, a["h"], "empresa")
    asaas_falso.simular("pagar", asaas_falso.cobrancas()[0]["id"], forma="PIX")
    alfa = listar(client, root)["Alfa"]
    assert alfa["situacao"] == "ativa" and alfa["pago_ate"] == "2026-11-14" and alfa["atrasada_desde"] is None
    assert alfa["assinatura"] == {"plano": "empresa", "valor": 799.0, "situacao": "ativa"}
    assert set(alfa) == {"id", "nome", "plano", "situacao", "teste_ate", "usuarios", "criada_em", "pago_ate",
                         "atrasada_desde", "assinatura"}
    client.post(f"{API}/assinatura/cancelar", headers=a["h"])
    assert listar(client, root)["Alfa"]["assinatura"] is None  # só a ativa


def test_mais_14_dias_recusado_com_assinatura_ativa_ou_cortesia(client, dono, contas, asaas_falso):
    root, a = contas
    url = f"{API}/plataforma/contas/{a['conta']['id']}/estender-teste"
    assinar(client, a["h"])
    r = client.post(url, headers=root["h"], json={"dias": 14})
    assert r.status_code == 409 and r.json()["erro"]["codigo"] == "assinatura_ativa"
    assert sql(dono, "select teste_ate from contas where id = :c", c=a["conta"]["id"])[0][0] == momento(
        "2026-10-15", 14, 30)
    # cancelou: volta a poder (conta a partir do fim do teste atual)
    client.post(f"{API}/assinatura/cancelar", headers=a["h"])
    r = client.post(url, headers=root["h"], json={"dias": 14})
    assert r.status_code == 200 and r.json()["teste_ate"] == "2026-10-29T17:30:00+00:00"
    assert r.json()["situacao"] == "teste"
    b = conta_pronta(client, "bia@beta.com.br", empresa="Beta")
    sql(dono, "update contas set situacao = 'cortesia' where id = :c", c=b["conta"]["id"])
    r = client.post(f"{API}/plataforma/contas/{b['conta']['id']}/estender-teste", headers=root["h"])
    assert r.status_code == 409 and r.json()["erro"]["codigo"] == "assinatura_ativa"


def test_cortesia_remove_a_assinatura_no_asaas(client, dono, contas, asaas_falso):
    root, a = contas
    conta = a["conta"]["id"]
    assinar(client, a["h"])
    sid, pid = asaas_falso.assinatura()["id"], asaas_falso.cobrancas()[0]["id"]
    r = client.post(f"{API}/plataforma/contas/{conta}/cortesia", headers=root["h"])
    assert r.status_code == 200, r.text
    assert r.json()["situacao"] == "cortesia" and r.json()["assinatura"] is None
    assert asaas_falso.dados["assinaturas"][sid]["deleted"] and asaas_falso.dados["cobrancas"][pid]["deleted"]
    assert sql(dono, "select situacao, cancelada_por from assinaturas") == [("cancelada", None)]
    assert sql(dono, "select situacao from cobrancas") == [("removida",)]
    assert situacao_conta(dono, conta) == ("cortesia", None, None, None)
    eventos = sql(dono, "select evento, detalhe from auditoria where conta_id = :c and evento in "
                        "('assinatura_cancelada', 'cortesia') order by id", c=conta)
    assert eventos == [("assinatura_cancelada", {"plano": "profissional", "motivo": "cortesia",
                                                 "por": "root@toqqi.com"}),
                       ("cortesia", {"por": "root@toqqi.com", "situacao_anterior": "teste"})]
    eu = client.get(f"{API}/eu", headers=a["h"]).json()["conta"]
    assert eu["situacao"] == "cortesia" and eu["cobranca"]["liberada"] is True and eu["cobranca"]["aviso"] is None
    # webhook atrasado da assinatura removida não tira a cortesia
    asaas_falso.dados["cobrancas"][pid].update(deleted=False, status="OVERDUE")
    asaas_falso.simular("vencer", pid)
    assert situacao_conta(dono, conta)[0] == "cortesia"


@pytest.mark.parametrize("falha", ["asaas_fora", "sem_chave"])
def test_cortesia_com_asaas_fora_nao_muda_nada(client, dono, contas, asaas_falso, monkeypatch, falha):
    root, a = contas
    conta = a["conta"]["id"]
    assinar(client, a["h"])
    if falha == "asaas_fora":
        asaas_falso.falhar(httpx.Response(503), "DELETE", "/subscriptions")
    else:
        monkeypatch.setattr(config(), "ASAAS_API_KEY", "")
    r = client.post(f"{API}/plataforma/contas/{conta}/cortesia", headers=root["h"])
    assert r.status_code == 503 and r.json()["erro"]["codigo"] == "cobranca_indisponivel"
    assert situacao_conta(dono, conta)[0] == "teste"
    assert sql(dono, "select situacao from assinaturas") == [("ativa",)]
    assert asaas_falso.assinatura()["deleted"] is False
    assert sql(dono, "select count(*) from auditoria where evento in ('cortesia', 'assinatura_cancelada')")[0][0] == 0


def test_cortesia_sem_assinatura_nao_chama_o_asaas(client, dono, contas, asaas_falso):
    root, a = contas
    r = client.post(f"{API}/plataforma/contas/{a['conta']['id']}/cortesia", headers=root["h"])
    assert r.status_code == 200 and r.json()["situacao"] == "cortesia"
    assert asaas_falso.pedidos == []


def test_excluir_conta_remove_a_assinatura_no_asaas(client, dono, contas, asaas_falso):
    root, a = contas
    conta = a["conta"]["id"]
    assinar(client, a["h"])
    asaas_falso.simular("pagar", asaas_falso.cobrancas()[0]["id"], forma="PIX")
    sid = asaas_falso.assinatura()["id"]
    url = f"{API}/plataforma/contas/{conta}"
    asaas_falso.falhar(httpx.Response(500), "DELETE", "/subscriptions")
    r = client.request("DELETE", url, headers=root["h"], json={"confirmar_nome": "Alfa"})
    assert r.status_code == 503
    assert sql(dono, "select count(*) from contas where id = :c", c=conta)[0][0] == 1
    r = client.request("DELETE", url, headers=root["h"], json={"confirmar_nome": "Alfa"})
    assert r.status_code == 204, r.text
    assert asaas_falso.dados["assinaturas"][sid]["deleted"] is True
    for t in ("assinaturas", "cobrancas"):
        assert sql(dono, f"select count(*) from {t} where conta_id = :c", c=conta)[0][0] == 0, t
    # os avisos do Asaas ficam (tabela da plataforma), sem a conta
    assert sql(dono, "select conta_id from asaas_eventos") == [(None,)]


def test_excluir_conta_remove_tambem_a_que_sobrou_no_asaas(client, dono, contas, asaas_falso):
    root, a = contas
    conta = a["conta"]["id"]
    assinar(client, a["h"])
    orfa = asaas_falso.criar_direto(conta, valor=149.0)  # um pedido que esgotou o tempo chegou a criar
    url = f"{API}/plataforma/contas/{conta}"
    asaas_falso.falhar(httpx.Response(503), "GET", "/subscriptions")  # sem conseguir listar, nada é apagado
    r = client.request("DELETE", url, headers=root["h"], json={"confirmar_nome": "Alfa"})
    assert r.status_code == 503
    assert sql(dono, "select count(*) from contas where id = :c", c=conta)[0][0] == 1
    assert len(asaas_falso.vivas()) == 2
    r = client.request("DELETE", url, headers=root["h"], json={"confirmar_nome": "Alfa"})
    assert r.status_code == 204, r.text
    assert asaas_falso.vivas() == [] and asaas_falso.dados["assinaturas"][orfa["id"]]["deleted"] is True


def test_mais_14_dias_recalcula_a_situacao(client, dono, contas, asaas_falso, monkeypatch):
    """Pagou e cancelou: enquanto o período pago for mais longo, segue `cancelada` (liberada até o fim dele); a
    tarefa passa para `teste` quando ele acaba com o teste estendido ainda valendo."""
    from toqqi import tarefas

    root, a = contas
    conta = a["conta"]["id"]
    assinar(client, a["h"])
    asaas_falso.simular("pagar", asaas_falso.cobrancas()[0]["id"], forma="PIX")
    client.post(f"{API}/assinatura/cancelar", headers=a["h"])
    url = f"{API}/plataforma/contas/{conta}/estender-teste"
    for _ in range(3):  # 15/10 + 42 dias = 26/11
        r = client.post(url, headers=root["h"], json={"dias": 14})
        assert r.status_code == 200 and r.json()["situacao"] == "cancelada"
    assert r.json()["teste_ate"] == "2026-11-26T17:30:00+00:00"
    fixar_relogio(monkeypatch, momento("2026-11-15", 0, 5))
    tarefas.executar("assinaturas")
    assert situacao_conta(dono, conta)[:2] == ("teste", date(2026, 11, 14))
    assert client.get(f"{API}/eu", headers=a["h"]).json()["conta"]["cobranca"]["liberada"] is True

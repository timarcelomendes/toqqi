"""Etapa 5a: webhook do Asaas — token (404 sem token, 401 errado), evento repetido, fora de ordem e forjado (a API
consulta o Asaas: vale o que ele diz), assinatura desconhecida (pendente: a API descobre a conta pelo Asaas e concilia;
de outro sistema ou de outro ambiente, ignorado; sem resolver em 1 hora, ignorado com log de erro), cobrança removida,
erro → 200 e a tarefa reprocessa (até 5 vezes; o Asaas fora do ar não gasta tentativa), e as transições de
`recalcular` pelos eventos (paga, vencida com e sem carência, estornada)."""
import logging
from datetime import date, datetime, time

import httpx
import pytest
from util import (
    API,
    CHAVE_ASAAS,
    FUSO,
    TOKEN_WEBHOOK,
    assinar,
    aviso_asaas,
    conta_pronta,
    fixar_relogio,
    situacao_conta,
    sql,
)

from toqqi import tarefas
from toqqi.core.config import config


def momento(dia: str, hora: int = 10, minuto: int = 0) -> datetime:
    return datetime.combine(date.fromisoformat(dia), time(hora, minuto), tzinfo=FUSO)


@pytest.fixture
def admin(client, dono, monkeypatch):
    fixar_relogio(monkeypatch, momento("2026-10-10"))
    a = conta_pronta(client, "ana@alfa.com.br", empresa="Alfa Distribuidora")
    sql(dono, "update contas set teste_ate = :t where id = :c", t=momento("2026-10-15", 14, 30), c=a["conta"]["id"])
    return a


@pytest.fixture
def assinada(client, admin, asaas_falso):
    """Conta que assinou no teste (fatura de 15/10 em aberto). Devolve (admin, id da fatura no Asaas)."""
    assert assinar(client, admin["h"]).status_code == 201
    return admin, asaas_falso.cobrancas()[0]["id"]


def evento(id_: str, tipo: str, pagamento: dict) -> dict:
    return {"id": id_, "event": tipo, "dateCreated": "2026-10-10 10:00:00", "payment": pagamento}


def gets(falso, pid: str) -> int:
    return len([p for p in falso.pedidos if p.method == "GET" and p.url.path == f"/v3/payments/{pid}"])


def eventos(dono) -> list[tuple]:
    return sql(dono, "select id, tipo, conta_id, cobranca_asaas_id, processado_em is not null, ignorado, tentativas, "
                     "erro from asaas_eventos order by recebido_em, id")


def erros(caplog) -> list[str]:
    return [r.getMessage() for r in caplog.records if r.levelno == logging.ERROR]


def reprocessar(dono, atraso: str = "3 minutes") -> dict:
    sql(dono, f"update asaas_eventos set recebido_em = now() - interval '{atraso}'")
    return tarefas.executar("assinaturas")["assinaturas"]


# ---- token e formato -----------------------------------------------------------------------------

def test_sem_token_configurado_404(client, monkeypatch):
    corpo = evento("evt_1", "PAYMENT_RECEIVED", {"id": "pay_1"})
    assert aviso_asaas(client, corpo).status_code == 404
    for ruim in ("curto-demais", "com espaco " + "x" * 40, "acentuação" + "x" * 40, "x" * 256, CHAVE_ASAAS):
        monkeypatch.setattr(config(), "ASAAS_API_KEY", CHAVE_ASAAS)
        monkeypatch.setattr(config(), "ASAAS_WEBHOOK_TOKEN", ruim)
        assert aviso_asaas(client, corpo, token=ruim if ruim.isascii() else "x").status_code == 404, ruim


def test_token_errado_401(client, dono, asaas_falso):
    corpo = evento("evt_1", "PAYMENT_RECEIVED", {"id": "pay_1"})
    r = aviso_asaas(client, corpo, token=TOKEN_WEBHOOK[:-1] + "x")
    assert r.status_code == 401 and r.json()["erro"]["codigo"] == "token_invalido"
    assert client.post(f"{API}/asaas/webhook", json=corpo).status_code == 401  # sem o cabeçalho
    assert eventos(dono) == []
    # o token certo, mas corpo que não serve: 422
    for ruim in (b"nao e json", b"[1, 2]", b'{"event": "PAYMENT_RECEIVED"}', b'{"id": "evt_1"}',
                 b'{"id": 7, "event": "PAYMENT_RECEIVED"}'):
        r = client.post(f"{API}/asaas/webhook", content=ruim,
                        headers={"asaas-access-token": TOKEN_WEBHOOK, "content-type": "application/json"})
        assert r.status_code == 422 and r.json()["erro"]["codigo"] == "dados_invalidos", ruim


# ---- processamento ---------------------------------------------------------------------------------

def test_pagamento_confirmado_e_evento_repetido(client, dono, assinada, asaas_falso):
    admin, pid = assinada
    conta = admin["conta"]["id"]
    asaas_falso.simular("pagar", pid, entregar=False, forma="PIX")
    aviso = asaas_falso.avisos.pop()
    r = aviso_asaas(client, aviso)
    assert r.status_code == 200 and r.json() == {"ok": True}
    assert situacao_conta(dono, conta) == ("ativa", date(2026, 11, 14), None, date(2026, 10, 15))
    assert gets(asaas_falso, pid) == 1  # a API consultou o Asaas antes de mudar a conta
    # repetido: 200 sem fazer nada
    r = aviso_asaas(client, aviso)
    assert r.status_code == 200 and r.json() == {"ok": True, "repetido": True}
    assert gets(asaas_falso, pid) == 1
    assert eventos(dono) == [(aviso["id"], "PAYMENT_RECEIVED", conta, pid, True, False, 0, None)]
    assert sql(dono, "select count(*) from auditoria where evento = 'pagamento_confirmado'")[0][0] == 1


def test_fora_de_ordem_vale_o_que_o_asaas_diz(client, dono, assinada, asaas_falso, monkeypatch):
    admin, pid = assinada
    conta = admin["conta"]["id"]
    vencida = evento("evt_vencida", "PAYMENT_OVERDUE", {**asaas_falso.cobrancas()[0], "status": "OVERDUE"})
    asaas_falso.simular("pagar", pid, forma="PIX")
    assert situacao_conta(dono, conta)[0] == "ativa"
    # o aviso de vencida chega depois do pagamento: o Asaas diz paga, a conta continua ativa
    fixar_relogio(monkeypatch, momento("2026-10-16", 9))
    assert aviso_asaas(client, vencida).status_code == 200
    assert situacao_conta(dono, conta)[0] == "ativa"
    assert sql(dono, "select situacao from cobrancas") == [("paga",)]
    assert sql(dono, "select count(*) from auditoria where evento = 'pagamento_vencido'")[0][0] == 0


def test_evento_forjado_nao_muda_nada(client, dono, assinada, asaas_falso):
    admin, pid = assinada
    falso = evento("evt_forjado", "PAYMENT_RECEIVED", {**asaas_falso.cobrancas()[0], "status": "RECEIVED"})
    assert aviso_asaas(client, falso).status_code == 200
    assert situacao_conta(dono, admin["conta"]["id"])[0] == "teste"  # o Asaas diz pendente
    assert sql(dono, "select situacao from cobrancas") == [("pendente",)]


def test_outros_eventos_ficam_ignorados(client, dono, asaas_falso):
    for id_, tipo, pagamento in (
        ("evt_b", "PAYMENT_CREATED", {"id": "pay_y"}),  # cobrança avulsa (sem assinatura)
        ("evt_c", "SUBSCRIPTION_CREATED", {}),
        ("evt_d", "PAYMENT_RECEIVED", {"subscription": "sub_1"}),  # sem id da cobrança
    ):
        r = aviso_asaas(client, evento(id_, tipo, pagamento))
        assert r.status_code == 200 and r.json() == {"ok": True, "ignorado": True}, id_
    assert [(e[0], e[2], e[4], e[5]) for e in eventos(dono)] == [
        ("evt_b", None, True, True), ("evt_c", None, True, True), ("evt_d", None, True, True)]
    assert asaas_falso.pedidos == []  # nem consultou o Asaas
    # guarda só ids e tipo (o corpo não é gravado)
    colunas = {c for (c,) in sql(dono, "select column_name from information_schema.columns "
                                       "where table_name = 'asaas_eventos'")}
    assert colunas == {"id", "tipo", "conta_id", "cobranca_asaas_id", "assinatura_asaas_id", "recebido_em",
                       "processado_em", "ignorado", "tentativas", "erro"}


def test_assinatura_de_outro_sistema_e_ignorada_depois_de_consultar(client, dono, asaas_falso, caplog):
    """Assinatura desconhecida: o aviso fica pendente e a API pergunta ao Asaas de quem ela é; com a referência de
    outro sistema (na mesma conta do Asaas), ignorado."""
    cliente = asaas_falso.http.post("/v3/customers", headers={"access_token": "x"}, json={
        "name": "Outro", "cpfCnpj": "52998224725", "email": "o@o.com.br", "mobilePhone": "11987654321"}).json()
    sub = asaas_falso.http.post("/v3/subscriptions", headers={"access_token": "x"}, json={
        "customer": cliente["id"], "value": 10, "nextDueDate": "2026-10-20", "externalReference": "pedido-123"}).json()
    pagamento = asaas_falso.cobrancas(sub["id"])[0]
    r = aviso_asaas(client, evento("evt_a", "PAYMENT_RECEIVED", pagamento))
    assert r.json() == {"ok": True}  # pendente, não ignorado de cara
    assert eventos(dono) == [("evt_a", "PAYMENT_RECEIVED", None, pagamento["id"], True, True, 0, None)]
    assert [p.url.path for p in asaas_falso.pedidos] == [f"/v3/payments/{pagamento['id']}",
                                                         f"/v3/subscriptions/{sub['id']}"]
    assert erros(caplog) == []
    # a cobrança que o Asaas não acha (aviso forjado): ignorado
    aviso_asaas(client, evento("evt_x", "PAYMENT_RECEIVED", {"id": "pay_x", "subscription": "sub_x"}))
    assert eventos(dono)[1][4:6] == (True, True)


def test_aviso_de_assinatura_desconhecida_da_conta_concilia_e_adota(client, dono, admin, asaas_falso, caplog):
    """O processo caiu entre criar a assinatura no Asaas e gravar aqui: o aviso da cobrança dela (com a referência da
    conta) não é ignorado — a API concilia (log de erro), adota a assinatura e grava a cobrança."""
    conta = admin["conta"]["id"]
    sub = asaas_falso.criar_direto(conta)
    sql(dono, "update contas set asaas_cliente_id = :k, asaas_ambiente = 'sandbox' where id = :c", k=sub["customer"],
        c=conta)
    pagamento = asaas_falso.cobrancas(sub["id"])[0]
    assert aviso_asaas(client, evento("evt_orfa", "PAYMENT_CREATED", pagamento)).json() == {"ok": True}
    assert any(f"não está gravada aqui (conta {conta})" in m for m in erros(caplog))
    assert sql(dono, "select asaas_id, plano, situacao from assinaturas") == [(sub["id"], "profissional", "ativa")]
    assert eventos(dono) == [("evt_orfa", "PAYMENT_CREATED", conta, pagamento["id"], True, False, 0, None)]
    assert sql(dono, "select asaas_id, situacao from cobrancas") == [(pagamento["id"], "pendente")]
    assert situacao_conta(dono, conta) == ("teste", None, None, date(2026, 10, 15))
    assert sql(dono, "select detalhe from auditoria where evento = 'assinatura_adotada'") == [
        ({"plano": "profissional", "valor": "349.00"},)]


def test_aviso_de_assinatura_desconhecida_com_outra_ativa_remove(client, dono, assinada, asaas_falso, caplog):
    admin, pid = assinada
    sid = asaas_falso.assinatura()["id"]
    orfa = asaas_falso.criar_direto(admin["conta"]["id"], valor=149.0)
    pagamento = asaas_falso.cobrancas(orfa["id"])[0]
    assert aviso_asaas(client, evento("evt_dup", "PAYMENT_CREATED", pagamento)).json() == {"ok": True}
    assert any("não está gravada aqui" in m for m in erros(caplog))
    assert [a["id"] for a in asaas_falso.vivas()] == [sid]  # nunca duas vivas
    assert eventos(dono)[0][4:6] == (True, True)  # processado e ignorado (a cobrança era da removida)
    assert sql(dono, "select asaas_id from cobrancas") == [(pid,)]
    assert sql(dono, "select detalhe from auditoria where evento = 'assinatura_removida_no_asaas'") == [
        ({"motivo": "duplicada", "valor": "149.00"},)]


def test_aviso_que_chega_antes_do_assinar_gravar(client, dono, admin, asaas_falso, monkeypatch, caplog):
    """O aviso da primeira cobrança chega enquanto o assinar ainda grava a assinatura: quando ele é processado, a
    assinatura já é conhecida — aplica sem conciliar e sem log de erro."""
    from toqqi.modulos.assinatura import webhook

    conta = admin["conta"]["id"]
    monkeypatch.setattr(webhook, "processar_depois", lambda _evento: None)  # o segundo plano ainda não rodou
    sub = asaas_falso.criar_direto(conta)
    pagamento = asaas_falso.cobrancas(sub["id"])[0]
    assert aviso_asaas(client, evento("evt_cedo", "PAYMENT_CREATED", pagamento)).json() == {"ok": True}
    assert eventos(dono)[0][2:6] == (None, pagamento["id"], False, False)
    sql(dono, """insert into assinaturas (conta_id, asaas_id, ambiente, plano, valor, razao_social, documento,
                                          email_cobranca, telefone, primeiro_vencimento)
                 values (:c, :s, 'sandbox', 'profissional', 349, 'Alfa', '11222333000181', 'a@a.com.br',
                         '5511987654321', '2026-10-15')""", c=conta, s=sub["id"])
    caplog.clear()
    assert reprocessar(dono)["eventos_reprocessados"] == 1
    assert erros(caplog) == []
    assert eventos(dono) == [("evt_cedo", "PAYMENT_CREATED", conta, pagamento["id"], True, False, 0, None)]
    assert sql(dono, "select asaas_id from cobrancas") == [(pagamento["id"],)]


def test_aviso_de_assinatura_desconhecida_tenta_resolver_por_1_hora(client, dono, admin, asaas_falso, caplog):
    sub = asaas_falso.criar_direto(admin["conta"]["id"])
    pagamento = asaas_falso.cobrancas(sub["id"])[0]
    asaas_falso.falhar(httpx.Response(503), "GET", "/payments")
    assert aviso_asaas(client, evento("evt_x", "PAYMENT_CREATED", pagamento)).json() == {"ok": True}
    assert eventos(dono) == [("evt_x", "PAYMENT_CREATED", None, pagamento["id"], False, False, 0, "Asaas: HTTP 503")]
    # a tarefa tenta de novo dentro da 1ª hora (o Asaas ainda fora: não gasta tentativa)
    asaas_falso.falhar(httpx.Response(503), "GET", "/payments")
    assert reprocessar(dono, "30 minutes")["eventos_reprocessados"] == 0
    assert eventos(dono)[0][4:] == (False, False, 0, "Asaas: HTTP 503")
    # passou de 1 hora sem resolver: ignorado, com log de erro (a conferência diária ainda concilia a conta)
    caplog.clear()
    pedidos = len(asaas_falso.pedidos)
    assert reprocessar(dono, "61 minutes")["eventos_reprocessados"] == 1
    assert eventos(dono)[0][4:] == (True, True, 0, "assinatura desconhecida")
    assert any("evt_x, de uma assinatura desconhecida, não foi resolvido em 1 hora" in m for m in erros(caplog))
    assert len(asaas_falso.pedidos) == pedidos


def test_aviso_de_assinatura_de_outro_ambiente_e_ignorado(client, dono, assinada, asaas_falso):
    admin, pid = assinada
    sql(dono, "update assinaturas set ambiente = 'producao'")  # a chave é de sandbox
    asaas_falso.simular("pagar", pid, entregar=False, forma="PIX")
    r = aviso_asaas(client, asaas_falso.avisos.pop())
    assert r.json() == {"ok": True, "ignorado": True}
    assert not [p for p in asaas_falso.pedidos if p.url.path.startswith("/v3/payments")]
    assert situacao_conta(dono, admin["conta"]["id"])[0] == "teste"


def test_cobranca_de_outra_assinatura_nao_entra(client, dono, assinada, asaas_falso):
    """O aviso diz que a cobrança é da assinatura da conta, mas o Asaas diz que é de outra assinatura: ignorado."""
    admin, pid = assinada
    sub_da_conta = asaas_falso.dados["cobrancas"][pid]["subscription"]
    outra = asaas_falso.http.post("/v3/subscriptions", headers={"access_token": "x"}, json={
        "customer": asaas_falso.dados["cobrancas"][pid]["customer"], "value": 10, "nextDueDate": "2026-10-20",
        "description": "outra", "externalReference": "x"}).json()
    alheia = next(p for p in asaas_falso.dados["cobrancas"].values() if p["subscription"] == outra["id"])
    corpo = evento("evt_alheio", "PAYMENT_RECEIVED", {**alheia, "subscription": sub_da_conta})
    assert aviso_asaas(client, corpo).json() == {"ok": True}
    assert sql(dono, "select asaas_id from cobrancas") == [(pid,)]
    assert eventos(dono)[0][4:6] == (True, True)  # processado e ignorado


def test_cobranca_removida(client, dono, assinada, asaas_falso):
    admin, pid = assinada
    # o Asaas não acha mais (404) → removida
    asaas_falso.falhar(httpx.Response(404, json={"errors": []}), "GET", f"/payments/{pid}")
    assert aviso_asaas(client, evento("evt_del", "PAYMENT_DELETED", {"id": pid, "subscription": "?"})).json() == {
        "ok": True}
    assert sql(dono, "select situacao from cobrancas") == [("removida",)]
    # deleted: true também
    sql(dono, "update cobrancas set situacao = 'pendente'")
    asaas_falso.dados["cobrancas"][pid]["deleted"] = True
    aviso_asaas(client, evento("evt_del2", "PAYMENT_DELETED", {"id": pid}))
    assert sql(dono, "select situacao from cobrancas") == [("removida",)]


def test_erro_responde_200_e_a_tarefa_reprocessa(client, dono, assinada, asaas_falso, caplog):
    admin, pid = assinada
    conta = admin["conta"]["id"]
    asaas_falso.simular("pagar", pid, entregar=False, forma="PIX")
    aviso = asaas_falso.avisos.pop()
    asaas_falso.falhar(httpx.Response(503), "GET", "/payments")
    r = aviso_asaas(client, aviso)
    assert r.status_code == 200 and r.json() == {"ok": True}
    # o Asaas fora do ar não gasta tentativa
    assert eventos(dono) == [(aviso["id"], "PAYMENT_RECEIVED", conta, pid, False, False, 0, "Asaas: HTTP 503")]
    assert situacao_conta(dono, conta)[0] == "teste"
    # a tarefa só pega depois de 2 minutos (o segundo plano da requisição pode estar rodando)
    assert tarefas.executar("assinaturas")["assinaturas"]["eventos_reprocessados"] == 0
    sql(dono, "update asaas_eventos set recebido_em = now() - interval '3 minutes'")
    assert tarefas.executar("assinaturas")["assinaturas"]["eventos_reprocessados"] == 1
    assert situacao_conta(dono, conta)[0] == "ativa"
    assert eventos(dono)[0][4:] == (True, False, 0, None)
    assert "11222333000181" not in caplog.text and CHAVE_ASAAS not in caplog.text


def test_ate_5_tentativas(client, dono, assinada, asaas_falso, caplog):
    admin, pid = assinada
    aviso = evento("evt_teimoso", "PAYMENT_RECEIVED", {"id": pid, "subscription": asaas_falso.assinatura()["id"]})
    for _ in range(10):  # erro que não é o Asaas fora do ar: gasta tentativa
        asaas_falso.falhar(httpx.Response(400, json={"errors": [{"code": "invalid_action", "description": "x"}]}),
                           "GET", f"/payments/{pid}")
    aviso_asaas(client, aviso)
    for tentativa in range(2, 7):
        reprocessar(dono)
        assert eventos(dono)[0][6] == min(tentativa, 5)
    assert eventos(dono)[0][4:] == (False, False, 5, "Asaas: HTTP 400 (invalid_action)")
    assert any(r.levelno == logging.ERROR and "5 de 5" in r.getMessage() for r in caplog.records)


def test_asaas_fora_do_ar_nao_gasta_tentativa(client, dono, assinada, asaas_falso):
    admin, pid = assinada
    asaas_falso.simular("pagar", pid, entregar=False, forma="PIX")
    aviso = asaas_falso.avisos.pop()
    for _ in range(8):
        asaas_falso.falhar(httpx.ReadTimeout("lento"), "GET", f"/payments/{pid}")
    aviso_asaas(client, aviso)
    for _ in range(7):  # mais vezes que o limite de tentativas: o evento continua na fila
        assert reprocessar(dono)["eventos_reprocessados"] == 0
    assert eventos(dono)[0][4:] == (False, False, 0, "Asaas: tempo esgotado")
    assert reprocessar(dono)["eventos_reprocessados"] == 1  # o Asaas voltou
    assert situacao_conta(dono, admin["conta"]["id"])[0] == "ativa"


def test_erro_do_banco_fica_no_evento_sem_dados(client, dono, assinada, asaas_falso, monkeypatch):
    from sqlalchemy import text

    from toqqi.modulos.assinatura import webhook

    admin, pid = assinada

    def quebrar(s, *_a, **_k):
        s.execute(text("select 1/0"))

    monkeypatch.setattr(webhook, "sincronizar_cobranca", quebrar)
    aviso_asaas(client, evento("evt_banco", "PAYMENT_RECEIVED", {"id": pid,
                                                                 "subscription": asaas_falso.assinatura()["id"]}))
    (erro,), = sql(dono, "select erro from asaas_eventos")
    assert erro.startswith("banco: DivisionByZero, SQLSTATE 22012")


def test_uma_conta_por_evento_nao_mexe_na_outra(client, dono, assinada, asaas_falso):
    admin, pid = assinada
    b = conta_pronta(client, "bia@beta.com.br", empresa="Beta")
    sql(dono, "update contas set teste_ate = :t where id = :c", t=momento("2026-10-20"), c=b["conta"]["id"])
    assinar(client, b["h"], razao_social="Beta Ltda")
    asaas_falso.simular("pagar", pid, forma="PIX")
    assert situacao_conta(dono, admin["conta"]["id"])[0] == "ativa"
    assert situacao_conta(dono, b["conta"]["id"])[0] == "teste"


# ---- transições pelos eventos --------------------------------------------------------------------

def test_primeira_fatura_vencida_no_teste_tem_carencia(client, dono, assinada, asaas_falso, monkeypatch):
    """Quem assinou no teste e não pagou a primeira fatura fica atrasada (7 dias de envios) depois do vencimento."""
    admin, pid = assinada
    conta = admin["conta"]["id"]
    fixar_relogio(monkeypatch, momento("2026-10-16", 6))
    asaas_falso.simular("vencer", pid)
    assert situacao_conta(dono, conta) == ("atrasada", None, date(2026, 10, 15), date(2026, 10, 15))
    assert client.get(f"{API}/eu", headers=admin["h"]).json()["conta"]["cobranca"]["aviso"] == {
        "tipo": "atrasada", "data": "2026-10-23", "dias": 7}
    assert sql(dono, "select gravidade, detalhe from auditoria where evento = 'pagamento_vencido'") == [
        ("atencao", {"valor": "349.00", "vencimento": "2026-10-15"})]


def test_estorno(client, dono, assinada, asaas_falso):
    admin, pid = assinada
    asaas_falso.simular("pagar", pid, forma="PIX")
    asaas_falso.simular("estornar", pid)
    assert sql(dono, "select situacao, situacao_asaas from cobrancas") == [("estornada", "REFUNDED")]
    assert sql(dono, "select gravidade from auditoria where evento = 'pagamento_estornado'") == [("atencao",)]
    # o período já pago não diminui (pago_ate só cresce)
    assert situacao_conta(dono, admin["conta"]["id"])[1] == date(2026, 11, 14)


def test_auditoria_so_quando_a_situacao_muda(client, dono, assinada, asaas_falso):
    admin, pid = assinada
    asaas_falso.simular("pagar", pid, forma="CREDIT_CARD")  # CONFIRMED
    p = asaas_falso.dados["cobrancas"][pid]
    p["status"] = "RECEIVED"  # no cartão, o RECEIVED chega ~32 dias depois
    aviso_asaas(client, evento("evt_recebido", "PAYMENT_RECEIVED", p))
    assert sql(dono, "select situacao, situacao_asaas, forma from cobrancas") == [("paga", "RECEIVED", "cartao")]
    assert sql(dono, "select count(*) from auditoria where evento = 'pagamento_confirmado'")[0][0] == 1

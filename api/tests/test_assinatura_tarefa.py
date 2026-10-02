"""Etapa 5a: tarefa `assinaturas` — teste vencido vira `teste_expirado` (e só as contas que mudam pela data), fatura
pendente que passou do vencimento, conferência diária (pega pagamento sem webhook, uma vez por dia, a partir das 6h,
assinaturas canceladas há menos de 40 dias, para com o Asaas fora e recalcula o que já tinha mudado), conciliação
(adota a assinatura criada sem a API saber; remove a duplicada e a cancelada aqui que segue viva lá), assinatura
removida, INACTIVE ou EXPIRED no Asaas, 404 por 3 dias seguidos, valor diferente no Asaas, sanidade, remoções
pendentes, troca da chave de sandbox para produção e, sem Asaas, só a primeira parte."""
import json
import logging
from datetime import date, datetime, time, timedelta

import httpx
import pytest
from util import CHAVE_ASAAS, FUSO, AsaasFalso, assinar, conta_pronta, fixar_relogio, situacao_conta, sql

from toqqi import tarefas
from toqqi.core import asaas
from toqqi.core.config import config

VAZIO = {"testes_expirados": 0, "contas_de_outro_ambiente": 0, "remocoes_no_asaas": 0, "eventos_reprocessados": 0,
         "contas_conferidas": 0}
CHAVE_PRODUCAO = CHAVE_ASAAS.replace("$aact_hmlg_", "$aact_prod_")


def momento(dia: str, hora: int = 10, minuto: int = 0) -> datetime:
    return datetime.combine(date.fromisoformat(dia), time(hora, minuto), tzinfo=FUSO)


def rodar(monkeypatch, quando: datetime) -> dict:
    fixar_relogio(monkeypatch, quando)
    return tarefas.executar("assinaturas")["assinaturas"]


def auditoria(dono, evento: str) -> list[tuple]:
    return sql(dono, "select gravidade, detalhe from auditoria where evento = :e order by id", e=evento)


def erros(caplog) -> list[str]:
    return [r.getMessage() for r in caplog.records if r.levelno == logging.ERROR]


@pytest.fixture
def admin(client, dono, monkeypatch):
    fixar_relogio(monkeypatch, momento("2026-10-10"))
    a = conta_pronta(client, "ana@alfa.com.br", empresa="Alfa Distribuidora")
    sql(dono, "update contas set teste_ate = :t where id = :c", t=momento("2026-10-15", 14, 30), c=a["conta"]["id"])
    return a


# ---- datas -----------------------------------------------------------------------------------------

def test_teste_vencido_vira_expirado_e_as_outras_ficam(client, dono, monkeypatch):
    fixar_relogio(monkeypatch, momento("2026-10-10"))
    ids = {}
    for nome, situacao, fim in (("vencido", "teste", "2026-10-09 23:00-03"),
                                ("valendo", "teste", "2026-10-11 00:00-03"),
                                ("cortesia", "cortesia", "2026-01-01 00:00-03"),
                                ("ativa", "ativa", "2026-01-01 00:00-03"),
                                ("expirado", "teste_expirado", "2026-12-01 00:00-03"),
                                ("sem_fim", "teste", None)):
        a = conta_pronta(client, f"{nome}@{nome.replace('_', '-')}.com.br", empresa=nome)
        sql(dono, "update contas set situacao = :s, teste_ate = :t where id = :c", s=situacao, t=fim,
            c=a["conta"]["id"])
        ids[nome] = a["conta"]["id"]
    assert rodar(monkeypatch, momento("2026-10-10")) == {**VAZIO, "testes_expirados": 2}
    situacoes = {nome: situacao_conta(dono, i)[0] for nome, i in ids.items()}
    assert situacoes == {"vencido": "teste_expirado", "valendo": "teste", "cortesia": "cortesia", "ativa": "ativa",
                         "expirado": "teste_expirado", "sem_fim": "teste_expirado"}
    assert rodar(monkeypatch, momento("2026-10-10", 23, 59))["testes_expirados"] == 0
    assert rodar(monkeypatch, momento("2026-10-11", 0, 0))["testes_expirados"] == 1  # "valendo" acabou à meia-noite
    assert tarefas.main(["assinaturas"]) == 0


def test_periodo_pago_acabou_com_o_teste_valendo_volta_ao_teste(client, dono, monkeypatch):
    fixar_relogio(monkeypatch, momento("2026-11-10"))
    a = conta_pronta(client, "ana@alfa.com.br", empresa="Alfa")
    conta = a["conta"]["id"]
    sql(dono, "update contas set situacao = 'cancelada', pago_ate = '2026-11-14', teste_ate = :t where id = :c",
        t=momento("2026-11-30"), c=conta)
    rodar(monkeypatch, momento("2026-11-14", 23))
    assert situacao_conta(dono, conta)[0] == "cancelada"
    rodar(monkeypatch, momento("2026-11-15", 0, 5))
    assert situacao_conta(dono, conta)[0] == "teste"


def test_assinou_no_teste_e_depois_do_vencimento_fica_atrasada(client, dono, admin, asaas_falso, monkeypatch):
    conta = admin["conta"]["id"]
    assinar(client, admin["h"])
    # passou do fim do teste, mas é o dia do vencimento: continua em teste e liberada
    assert rodar(monkeypatch, momento("2026-10-15", 15))["testes_expirados"] == 0
    assert situacao_conta(dono, conta)[0] == "teste"
    assert client.get("/api/v1/eu", headers=admin["h"]).json()["conta"]["cobranca"]["liberada"] is True
    # meia-noite: a fatura pendente passou do vencimento (o Asaas só marca de madrugada): atrasada, sem webhook
    assert rodar(monkeypatch, momento("2026-10-16", 0, 5))["testes_expirados"] == 0
    assert situacao_conta(dono, conta) == ("atrasada", None, date(2026, 10, 15), date(2026, 10, 15))
    assert client.get("/api/v1/eu", headers=admin["h"]).json()["conta"]["cobranca"]["aviso"] == {
        "tipo": "atrasada", "data": "2026-10-23", "dias": 7}
    assert client.get("/api/v1/assinatura", headers=admin["h"]).json()["fatura_aberta"]["situacao"] == "vencida"


def test_ativa_com_fatura_do_mes_seguinte_vencida(client, dono, admin, asaas_falso, monkeypatch):
    conta = admin["conta"]["id"]
    assinar(client, admin["h"])
    asaas_falso.simular("pagar", asaas_falso.cobrancas()[0]["id"], forma="PIX")
    asaas_falso.simular("proxima", asaas_falso.assinatura()["id"])  # vence em 15/11
    assert rodar(monkeypatch, momento("2026-11-15", 23))["testes_expirados"] == 0
    assert situacao_conta(dono, conta)[0] == "ativa"
    rodar(monkeypatch, momento("2026-11-16", 0, 30))
    assert situacao_conta(dono, conta) == ("atrasada", date(2026, 11, 14), date(2026, 11, 15), date(2026, 10, 15))


def test_uma_conta_com_erro_nao_derruba_as_outras(client, dono, monkeypatch):
    from toqqi.modulos.assinatura import servico

    fixar_relogio(monkeypatch, momento("2026-10-10"))
    ids = []
    for nome in ("alfa", "beta"):
        a = conta_pronta(client, f"x@{nome}.com.br", empresa=nome)
        sql(dono, "update contas set teste_ate = '2026-10-01' where id = :c", c=a["conta"]["id"])
        ids.append(a["conta"]["id"])
    original = servico.recalcular

    def quebrar_a_primeira(s, conta):
        if conta.id == ids[0]:
            raise RuntimeError("falhou")
        return original(s, conta)

    monkeypatch.setattr(servico, "recalcular", quebrar_a_primeira)
    assert rodar(monkeypatch, momento("2026-10-10"))["testes_expirados"] == 1
    assert [situacao_conta(dono, i)[0] for i in ids] == ["teste", "teste_expirado"]


def test_sem_asaas_so_a_primeira_parte(client, dono, admin, asaas_falso, monkeypatch):
    conta = admin["conta"]["id"]
    assinar(client, admin["h"])
    sql(dono, "insert into asaas_eventos (id, tipo, conta_id, cobranca_asaas_id, recebido_em) "
              "values ('evt_preso', 'PAYMENT_RECEIVED', :c, 'pay_x', now() - interval '1 hour')", c=conta)
    monkeypatch.setattr(config(), "ASAAS_API_KEY", "")
    pedidos = len(asaas_falso.pedidos)
    assert rodar(monkeypatch, momento("2026-10-16", 7)) == VAZIO
    assert len(asaas_falso.pedidos) == pedidos
    assert situacao_conta(dono, conta)[0] == "atrasada"  # a parte das datas roda sem o Asaas


# ---- conferência diária ------------------------------------------------------------------------------

def test_conferencia_diaria_pega_pagamento_sem_webhook(client, dono, admin, asaas_falso, monkeypatch):
    conta = admin["conta"]["id"]
    assinar(client, admin["h"])
    asaas_falso.simular("pagar", asaas_falso.cobrancas()[0]["id"], entregar=False, forma="PIX")
    asaas_falso.avisos.clear()  # o webhook se perdeu
    assert situacao_conta(dono, conta)[0] == "teste"
    assert rodar(monkeypatch, momento("2026-10-11", 5, 59))["contas_conferidas"] == 0  # antes das 6h
    assert rodar(monkeypatch, momento("2026-10-11", 6))["contas_conferidas"] == 1
    assert situacao_conta(dono, conta)[:2] == ("ativa", date(2026, 11, 14))
    assert sql(dono, "select asaas_conferida_em from contas where id = :c", c=conta) == [(date(2026, 10, 11),)]
    assert sql(dono, "select count(*) from auditoria where evento = 'pagamento_confirmado'")[0][0] == 1
    # uma vez por dia
    listas = len([p for p in asaas_falso.pedidos if p.url.path.endswith("/payments")])
    assert rodar(monkeypatch, momento("2026-10-11", 18))["contas_conferidas"] == 0
    assert len([p for p in asaas_falso.pedidos if p.url.path.endswith("/payments")]) == listas
    assert rodar(monkeypatch, momento("2026-10-12", 7))["contas_conferidas"] == 1


def test_conferencia_de_cancelada_ha_menos_de_40_dias(client, dono, admin, asaas_falso, monkeypatch):
    assinar(client, admin["h"])
    asaas_falso.simular("pagar", asaas_falso.cobrancas()[0]["id"], forma="PIX")
    client.post("/api/v1/assinatura/cancelar", headers=admin["h"])
    assert rodar(monkeypatch, momento("2026-10-20", 7))["contas_conferidas"] == 1
    sql(dono, "update contas set asaas_conferida_em = '2026-10-19'")
    sql(dono, "update assinaturas set cancelada_em = :q", q=momento("2026-10-20", 7) - timedelta(days=41))
    assert rodar(monkeypatch, momento("2026-10-20", 8))["contas_conferidas"] == 0


def test_conferencia_para_com_o_asaas_fora(client, dono, admin, asaas_falso, monkeypatch):
    b = conta_pronta(client, "bia@beta.com.br", empresa="Beta")
    for x in (admin, b):
        assert assinar(client, x["h"]).status_code == 201
    asaas_falso.falhar(httpx.Response(503), "GET", "/subscriptions")
    pedidos = len(asaas_falso.pedidos)
    assert rodar(monkeypatch, momento("2026-10-11", 7))["contas_conferidas"] == 0
    assert len(asaas_falso.pedidos) == pedidos + 1  # parou na primeira (as outras também falhariam)
    assert sql(dono, "select count(*) from contas where asaas_conferida_em is not null")[0][0] == 0
    assert rodar(monkeypatch, momento("2026-10-11", 7, 15))["contas_conferidas"] == 2


def test_parar_no_meio_recalcula_o_que_ja_mudou(client, dono, admin, asaas_falso, monkeypatch):
    """A assinatura foi removida no Asaas e a lista das cobranças falha logo depois: a conferência para, mas a conta
    sai recalculada (sem assinatura, de volta ao teste e ao plano do teste) e é conferida de novo na próxima vez."""
    conta = admin["conta"]["id"]
    assinar(client, admin["h"], "essencial")
    sid = asaas_falso.assinatura()["id"]
    assert asaas_falso.http.delete(f"/v3/subscriptions/{sid}", headers={"access_token": "x"}).status_code == 200
    asaas_falso.falhar(httpx.Response(503), "GET", "/payments")
    assert rodar(monkeypatch, momento("2026-10-11", 7))["contas_conferidas"] == 0
    assert sql(dono, "select situacao from assinaturas") == [("cancelada",)]
    assert situacao_conta(dono, conta) == ("teste", None, None, None)
    assert sql(dono, "select plano, asaas_conferida_em from contas where id = :c", c=conta) == [("profissional", None)]
    assert rodar(monkeypatch, momento("2026-10-11", 7, 15))["contas_conferidas"] == 1


def test_conferencia_cancela_a_assinatura_removida_no_painel_do_asaas(client, dono, admin, asaas_falso, monkeypatch):
    conta = admin["conta"]["id"]
    assinar(client, admin["h"])
    asaas_falso.simular("pagar", asaas_falso.cobrancas()[0]["id"], forma="PIX")
    sid = asaas_falso.assinatura()["id"]
    proxima = asaas_falso.simular("proxima", sid)["cobranca"]["id"]
    # alguém cancela direto no painel do Asaas (sem aviso para a API)
    assert asaas_falso.http.delete(f"/v3/subscriptions/{sid}", headers={"access_token": "x"}).status_code == 200
    assert rodar(monkeypatch, momento("2026-10-20", 7))["contas_conferidas"] == 1
    assert sql(dono, "select situacao, cancelada_por from assinaturas") == [("cancelada", None)]
    assert sql(dono, "select situacao from cobrancas where asaas_id = :p", p=proxima) == [("removida",)]
    assert situacao_conta(dono, conta) == ("cancelada", date(2026, 11, 14), None, None)
    assert auditoria(dono, "assinatura_cancelada") == [
        ("atencao", {"plano": "profissional", "motivo": "removida_no_asaas"})]


@pytest.mark.parametrize("status", ["INACTIVE", "EXPIRED"])
def test_inactive_ou_expired_no_asaas_conta_como_removida(client, dono, admin, asaas_falso, monkeypatch, status):
    conta = admin["conta"]["id"]
    assinar(client, admin["h"], "essencial")
    asaas_falso.simular("inativar", asaas_falso.assinatura()["id"], entregar=False, status=status)
    assert rodar(monkeypatch, momento("2026-10-11", 7))["contas_conferidas"] == 1
    assert sql(dono, "select situacao from assinaturas") == [("cancelada",)]
    assert auditoria(dono, "assinatura_cancelada") == [
        ("atencao", {"plano": "essencial", "motivo": "removida_no_asaas"})]
    # nunca pagou: de volta ao teste (ainda valendo) e ao plano do teste
    assert situacao_conta(dono, conta) == ("teste", None, None, None)
    assert sql(dono, "select plano from contas where id = :c", c=conta) == [("profissional",)]


def test_404_por_3_dias_seguidos_cancela_aqui(client, dono, admin, asaas_falso, monkeypatch, caplog):
    conta = admin["conta"]["id"]
    assinar(client, admin["h"])
    sid = asaas_falso.assinatura()["id"]

    def dia(texto: str, nao_acha: bool) -> str:
        if nao_acha:
            asaas_falso.falhar(httpx.Response(404, json={"errors": []}), "GET", f"/subscriptions/{sid}")
        caplog.clear()
        assert rodar(monkeypatch, momento(texto, 7))["contas_conferidas"] == 1
        if nao_acha:
            assert any("não existe no Asaas (404" in m for m in erros(caplog)), texto
        (situacao,), = sql(dono, "select situacao from assinaturas")
        return situacao

    # um dia em que o Asaas acha a assinatura zera a contagem
    assert [dia("2026-10-11", True), dia("2026-10-12", False), dia("2026-10-13", True)] == ["ativa"] * 3
    assert sql(dono, "select nao_encontrada_desde from assinaturas") == [(date(2026, 10, 13),)]
    assert dia("2026-10-14", True) == "ativa"
    assert dia("2026-10-15", True) == "cancelada"  # 3º dia seguido
    assert auditoria(dono, "assinatura_cancelada") == [
        ("atencao", {"plano": "profissional", "motivo": "nao_encontrada_no_asaas"})]
    assert situacao_conta(dono, conta)[0] == "teste"


def test_valor_diferente_no_asaas_volta_ao_daqui(client, dono, admin, asaas_falso, monkeypatch):
    """A troca de plano mudou o valor no Asaas e não foi gravada aqui (ou alguém mudou no painel): a conferência volta
    o valor do Asaas (e das faturas em aberto) para o daqui."""
    assinar(client, admin["h"], "profissional")
    sid = asaas_falso.assinatura()["id"]
    asaas_falso.dados["assinaturas"][sid]["value"] = 799.0
    asaas_falso.cobrancas()[0]["value"] = 799.0
    assert rodar(monkeypatch, momento("2026-10-11", 7))["contas_conferidas"] == 1
    put, = [p for p in asaas_falso.pedidos if p.method == "PUT" and p.url.path == f"/v3/subscriptions/{sid}"]
    assert json.loads(put.content) == {"value": 349.0, "description": "Toqqi – plano Profissional",
                                       "updatePendingPayments": True}
    assert asaas_falso.assinatura()["value"] == 349.0 and asaas_falso.cobrancas()[0]["value"] == 349.0
    assert sql(dono, "select valor from cobrancas") == [(349,)]
    assert auditoria(dono, "valor_realinhado") == [
        ("atencao", {"plano": "profissional", "de": "799.00", "para": "349.00"})]
    # no dia seguinte, já igual: nada a corrigir
    assert rodar(monkeypatch, momento("2026-10-12", 7))["contas_conferidas"] == 1
    assert len(auditoria(dono, "valor_realinhado")) == 1


def test_sanidade_ativa_sem_pagamento_recente_nem_fatura_em_aberto(client, dono, admin, asaas_falso, monkeypatch,
                                                                    caplog):
    assinar(client, admin["h"])
    asaas_falso.simular("pagar", asaas_falso.cobrancas()[0]["id"], forma="PIX")  # pago até 14/11
    rodar(monkeypatch, momento("2026-12-24", 7))  # 40 dias depois do pago_ate: ainda não
    assert not any("nenhuma fatura em aberto" in m for m in erros(caplog))
    caplog.clear()
    rodar(monkeypatch, momento("2026-12-25", 7))
    assert any(f"conta {admin['conta']['id']} tem assinatura ativa, pagamento só até 2026-11-14 e nenhuma fatura "
               "em aberto" in m for m in erros(caplog))
    assert sql(dono, "select situacao from assinaturas") == [("ativa",)]  # só o log


# ---- conciliação -------------------------------------------------------------------------------------

def test_adota_a_assinatura_criada_sem_a_api_saber(client, dono, admin, asaas_falso, monkeypatch):
    """O processo caiu entre criar a assinatura no Asaas e gravar aqui (o cliente já estava gravado): a conferência
    acha a assinatura pela referência da conta e a adota, com o plano do valor e os dados do cliente no Asaas."""
    conta = admin["conta"]["id"]
    sub = asaas_falso.criar_direto(conta, valor=149.0, vencimento="2026-10-15")
    sql(dono, "update contas set asaas_cliente_id = :k, asaas_ambiente = 'sandbox' where id = :c", k=sub["customer"],
        c=conta)
    assert rodar(monkeypatch, momento("2026-10-11", 7))["contas_conferidas"] == 1
    assert sql(dono, "select asaas_id, ambiente, plano, valor, situacao, razao_social, documento, email_cobranca, "
                     "telefone, primeiro_vencimento, criada_por from assinaturas") == [
        (sub["id"], "sandbox", "essencial", 149, "ativa", "Alfa Distribuidora Ltda", "11222333000181",
         "financeiro@alfa.com.br", "5511987654321", date(2026, 10, 15), None)]
    assert situacao_conta(dono, conta) == ("teste", None, None, date(2026, 10, 15))
    assert sql(dono, "select plano from contas where id = :c", c=conta) == [("essencial",)]
    assert sql(dono, "select situacao, vencimento from cobrancas") == [("pendente", date(2026, 10, 15))]
    assert auditoria(dono, "assinatura_adotada") == [("atencao", {"plano": "essencial", "valor": "149.00"})]
    assert client.get("/api/v1/assinatura", headers=admin["h"]).json()["assinatura"]["plano"] == "essencial"


def test_remove_a_duplicada_e_a_cancelada_aqui_que_segue_viva_la(client, dono, admin, asaas_falso, monkeypatch):
    conta = admin["conta"]["id"]
    assinar(client, admin["h"])
    sid = asaas_falso.assinatura()["id"]
    orfa = asaas_falso.criar_direto(conta, valor=149.0)
    assert rodar(monkeypatch, momento("2026-10-11", 7))["contas_conferidas"] == 1
    assert asaas_falso.dados["assinaturas"][orfa["id"]]["deleted"] is True
    assert [a["id"] for a in asaas_falso.vivas()] == [sid]
    assert auditoria(dono, "assinatura_removida_no_asaas") == [("atencao", {"motivo": "duplicada", "valor": "149.00"})]
    assert sql(dono, "select asaas_id, situacao from assinaturas") == [(sid, "ativa")]
    # cancelada aqui (o Asaas respondeu 404 ao remover), mas viva lá: removida na conferência seguinte
    asaas_falso.falhar(httpx.Response(404, json={"errors": []}), "DELETE", "/subscriptions")
    assert client.post("/api/v1/assinatura/cancelar", headers=admin["h"]).status_code == 200
    assert asaas_falso.dados["assinaturas"][sid]["deleted"] is False
    assert rodar(monkeypatch, momento("2026-10-12", 7))["contas_conferidas"] == 1
    assert asaas_falso.vivas() == []
    assert auditoria(dono, "assinatura_removida_no_asaas")[-1] == (
        "atencao", {"motivo": "cancelada_aqui", "valor": "349.00"})


def test_desconhecida_de_conta_cortesia_e_removida(client, dono, admin, asaas_falso, monkeypatch):
    conta = admin["conta"]["id"]
    sub = asaas_falso.criar_direto(conta)
    sql(dono, "update contas set situacao = 'cortesia', asaas_cliente_id = :k, asaas_ambiente = 'sandbox' "
              "where id = :c", k=sub["customer"], c=conta)
    assert rodar(monkeypatch, momento("2026-10-11", 7))["contas_conferidas"] == 1
    assert asaas_falso.vivas() == [] and sql(dono, "select count(*) from assinaturas")[0][0] == 0
    assert auditoria(dono, "assinatura_removida_no_asaas") == [("atencao", {"motivo": "cortesia", "valor": "349.00"})]


def test_remocao_que_falhou_a_tarefa_tenta_de_novo(client, dono, admin, asaas_falso, monkeypatch):
    from toqqi.modulos.assinatura import servico

    conta = admin["conta"]["id"]
    original = servico.recalcular

    def quebrar(*_a, **_k):
        raise RuntimeError("banco caiu")

    monkeypatch.setattr(servico, "recalcular", quebrar)
    asaas_falso.falhar(httpx.Response(503), "DELETE", "/subscriptions")
    with pytest.raises(RuntimeError):  # a gravação falhou e a remoção no Asaas também
        assinar(client, admin["h"])
    monkeypatch.setattr(servico, "recalcular", original)
    sub, = asaas_falso.vivas()
    assert sql(dono, "select asaas_id, ambiente, conta_id, motivo, tentativas, erro, removida_em is null "
                     "from asaas_remocoes") == [(sub["id"], "sandbox", conta, "gravacao_falhou", 0, "HTTP 503", True)]
    # antes das 6h (sem conferência): o Asaas segue fora na 1ª tentativa
    asaas_falso.falhar(httpx.Response(503), "DELETE", "/subscriptions")
    assert rodar(monkeypatch, momento("2026-10-11", 5))["remocoes_no_asaas"] == 0
    assert sql(dono, "select tentativas, erro from asaas_remocoes") == [(1, "HTTP 503")]
    assert rodar(monkeypatch, momento("2026-10-11", 5, 15))["remocoes_no_asaas"] == 1
    assert asaas_falso.vivas() == []
    assert sql(dono, "select removida_em is not null, erro from asaas_remocoes") == [(True, None)]
    assert auditoria(dono, "assinatura_removida_no_asaas") == [("atencao", {"motivo": "gravacao_falhou"})]
    assert rodar(monkeypatch, momento("2026-10-11", 5, 30))["remocoes_no_asaas"] == 0


def test_a_conciliacao_nunca_adota_a_que_espera_remocao(client, dono, admin, asaas_falso, monkeypatch):
    conta = admin["conta"]["id"]
    sub = asaas_falso.criar_direto(conta)
    sql(dono, "update contas set asaas_cliente_id = :k, asaas_ambiente = 'sandbox' where id = :c", k=sub["customer"],
        c=conta)
    sql(dono, "insert into asaas_remocoes (asaas_id, ambiente, conta_id, motivo, erro) "
              "values (:s, 'sandbox', :c, 'gravacao_falhou', 'HTTP 503')", s=sub["id"], c=conta)
    asaas_falso.falhar(httpx.Response(500), "DELETE", "/subscriptions")  # a tarefa falha antes da conferência
    assert rodar(monkeypatch, momento("2026-10-11", 7))["contas_conferidas"] == 1
    assert asaas_falso.vivas() == [] and sql(dono, "select count(*) from assinaturas")[0][0] == 0
    assert sql(dono, "select removida_em is not null from asaas_remocoes") == [(True,)]


# ---- ambiente do Asaas ---------------------------------------------------------------------------------

@pytest.mark.parametrize("quem_limpa", ["tarefa", "assinar"])
def test_troca_da_chave_de_sandbox_para_producao(client, dono, admin, asaas_falso, monkeypatch, quem_limpa):
    """O que foi feito no sandbox não vale em produção: a assinatura de sandbox é cancelada aqui (sem chamar o
    Asaas), o cliente é esquecido, `pago_ate` e `atrasada_desde` zerados, a conta recalculada e auditada."""
    h, conta = admin["h"], admin["conta"]["id"]
    assinar(client, h)
    asaas_falso.simular("pagar", asaas_falso.cobrancas()[0]["id"], forma="PIX")
    assert situacao_conta(dono, conta)[:2] == ("ativa", date(2026, 11, 14))
    cliente_sandbox = asaas_falso.assinatura()["customer"]
    producao = AsaasFalso(client)
    monkeypatch.setattr(asaas, "transporte", httpx.MockTransport(producao))
    monkeypatch.setattr(config(), "ASAAS_API_KEY", CHAVE_PRODUCAO)
    fixar_relogio(monkeypatch, momento("2026-10-12"))
    pedidos_sandbox = len(asaas_falso.pedidos)
    # para a chave de produção, a assinatura e as cobranças de sandbox não existem
    d = client.get("/api/v1/assinatura", headers=h).json()
    assert (d["assinatura"], d["fatura_aberta"], d["cobrancas"]) == (None, None, [])
    if quem_limpa == "tarefa":
        assert rodar(monkeypatch, momento("2026-10-12", 11))["contas_de_outro_ambiente"] == 1
        assert sql(dono, "select asaas_cliente_id, asaas_ambiente from contas where id = :c", c=conta) == [
            (None, None)]
        assert situacao_conta(dono, conta) == ("teste", None, None, None)  # o pagamento de sandbox não vale
        assert rodar(monkeypatch, momento("2026-10-12", 11, 15))["contas_de_outro_ambiente"] == 0  # uma vez só
    assert auditoria(dono, "ambiente_asaas_trocado") == ([] if quem_limpa == "assinar" else [
        ("atencao", {"de": "sandbox", "para": "producao", "assinatura_cancelada": True,
                     "pago_ate_anterior": "2026-11-14"})])
    # assina em produção: cliente e assinatura novos lá
    r = assinar(client, h)
    assert r.status_code == 201, r.text
    assert r.json()["assinatura"]["primeiro_vencimento"] == "2026-10-15"  # no fim do teste (o período pago não vale)
    assert len(producao.dados["clientes"]) == 1 and producao.assinatura()["customer"] != cliente_sandbox
    assert sql(dono, "select situacao, ambiente from assinaturas order by id") == [
        ("cancelada", "sandbox"), ("ativa", "producao")]
    assert sql(dono, "select asaas_ambiente from contas where id = :c", c=conta) == [("producao",)]
    assert len(auditoria(dono, "ambiente_asaas_trocado")) == 1
    assert len(asaas_falso.pedidos) == pedidos_sandbox  # nada foi pedido ao sandbox com a chave de produção
    assert situacao_conta(dono, conta) == ("teste", None, None, date(2026, 10, 15))


def test_chave_de_sandbox_com_dados_de_producao_nao_apaga_nada(client, dono, admin, asaas_falso, monkeypatch,
                                                              caplog):
    h, conta = admin["h"], admin["conta"]["id"]
    assinar(client, h)
    asaas_falso.simular("pagar", asaas_falso.cobrancas()[0]["id"], forma="PIX")
    sql(dono, "update assinaturas set ambiente = 'producao'")
    sql(dono, "update contas set asaas_ambiente = 'producao' where id = :c", c=conta)
    r = rodar(monkeypatch, momento("2026-10-11", 7))
    assert (r["contas_de_outro_ambiente"], r["contas_conferidas"]) == (0, 0)
    assert any("a chave do Asaas é de sandbox, mas 1 conta(s)" in m for m in erros(caplog))
    assert sql(dono, "select situacao, ambiente from assinaturas") == [("ativa", "producao")]
    assert sql(dono, "select pago_ate, asaas_ambiente from contas where id = :c", c=conta) == [
        (date(2026, 11, 14), "producao")]
    assert assinar(client, h).status_code == 503  # assinar de novo no sandbox: chave errada

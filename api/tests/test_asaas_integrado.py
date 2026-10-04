"""Etapa 5a: o fluxo inteiro contra o Asaas falso (scripts/asaas_falso.py) — assinar no teste, pagar por Pix, fatura
do mês seguinte vencida (atrasada → pausada), pagar de novo, trocar de plano, estorno, cancelar e assinar de novo —, com
os webhooks indo do Asaas falso para a API."""
from datetime import date, datetime, time

import pytest
from util import API, FUSO, assinar, conta_pronta, fixar_relogio, situacao_conta, sql, trocar_plano

from toqqi import tarefas


def momento(dia: str, hora: int = 10, minuto: int = 0) -> datetime:
    return datetime.combine(date.fromisoformat(dia), time(hora, minuto), tzinfo=FUSO)


@pytest.fixture
def admin(client, dono, monkeypatch):
    fixar_relogio(monkeypatch, momento("2026-10-10"))
    a = conta_pronta(client, "ana@alfa.com.br", empresa="Alfa Distribuidora")
    sql(dono, "update contas set teste_ate = :t where id = :c", t=momento("2026-10-15", 14, 30), c=a["conta"]["id"])
    return a


def _estado(client, h) -> dict:
    r = client.get(f"{API}/assinatura", headers=h)
    assert r.status_code == 200, r.text
    return r.json()


def test_fluxo_completo(client, dono, admin, asaas_falso, monkeypatch):
    h, conta = admin["h"], admin["conta"]["id"]
    r = assinar(client, h, "profissional")
    assert r.status_code == 201, r.text
    d = r.json()
    # assinou no teste: primeira fatura no último dia dele; o teste continua
    assert d["assinatura"]["primeiro_vencimento"] == "2026-10-15" and d["assinatura"]["valor"] == 349.0
    assert d["fatura_aberta"]["valor"] == 349.0 and d["fatura_aberta"]["vencimento"] == "2026-10-15"
    assert d["fatura_aberta"]["situacao"] == "pendente"
    assert d["fatura_aberta"]["link"].startswith("https://asaas.teste/fatura/pay_")
    assert (d["conta"]["situacao"], d["conta"]["liberada"]) == ("teste", True)
    cliente = asaas_falso.dados["clientes"][asaas_falso.assinatura()["customer"]]
    assert (cliente["name"], cliente["cpfCnpj"], cliente["email"], cliente["mobilePhone"]) == (
        "Alfa Distribuidora Ltda", "11222333000181", "financeiro@alfa.com.br", "11987654321")
    assert cliente["externalReference"] == f"toqqi-conta-{conta}"

    # paga por Pix: o webhook avisa, a API confere no Asaas e a conta fica ativa
    primeira = asaas_falso.cobrancas()[0]["id"]
    asaas_falso.simular("pagar", primeira, forma="PIX")
    d = _estado(client, h)
    assert (d["conta"]["situacao"], d["conta"]["pago_ate"]) == ("ativa", "2026-11-14")
    assert d["fatura_aberta"] is None
    assert d["cobrancas"][0] | {"pago_em": None} == {"valor": 349.0, "vencimento": "2026-10-15", "situacao": "paga",
                                                      "forma": "pix", "pago_em": None,
                                                      "link": f"https://asaas.teste/fatura/{primeira}"}
    assert d["cobrancas"][0]["pago_em"].startswith("2026-10-10T15:00:00")  # 12:00 de São Paulo, em UTC
    assert client.get(f"{API}/eu", headers=h).json()["conta"]["cobranca"] == {
        "liberada": True, "assinada": True, "pago_ate": "2026-11-14", "atrasada_desde": None, "pausa_em": None,
        "aviso": None, "exclusao_em": None}

    # fatura do mês seguinte: vence 15/11 e não é paga → atrasada (envios até 22/11) → pausada
    sid = asaas_falso.assinatura()["id"]
    segunda = asaas_falso.simular("proxima", sid)["cobranca"]["id"]
    fixar_relogio(monkeypatch, momento("2026-11-16", 9))
    asaas_falso.simular("vencer", segunda)
    assert situacao_conta(dono, conta) == ("atrasada", date(2026, 11, 14), date(2026, 11, 15), date(2026, 10, 15))
    cobranca = client.get(f"{API}/eu", headers=h).json()["conta"]["cobranca"]
    assert cobranca["aviso"] == {"tipo": "atrasada", "data": "2026-11-23", "dias": 7}
    assert cobranca["liberada"] is True and cobranca["pausa_em"] == "2026-11-23T03:00:00+00:00"
    fixar_relogio(monkeypatch, momento("2026-11-23", 0, 0))
    cobranca = client.get(f"{API}/eu", headers=h).json()["conta"]["cobranca"]
    assert (cobranca["liberada"], cobranca["aviso"]) == (False, {"tipo": "pausada", "data": "2026-11-15",
                                                                 "dias": None})
    assert _estado(client, h)["fatura_aberta"]["situacao"] == "vencida"

    # paga com boleto: volta a ativa
    asaas_falso.simular("pagar", segunda, forma="BOLETO")
    assert situacao_conta(dono, conta) == ("ativa", date(2026, 12, 14), None, date(2026, 10, 15))

    # troca de plano: valor novo no Asaas e na fatura em aberto
    terceira = asaas_falso.simular("proxima", sid)["cobranca"]["id"]
    r = trocar_plano(client, h, "empresa")
    assert r.status_code == 200, r.text
    assert r.json()["assinatura"]["plano"] == "empresa" and r.json()["fatura_aberta"]["valor"] == 799.0
    assert asaas_falso.dados["cobrancas"][terceira]["value"] == 799.0
    assert asaas_falso.assinatura()["value"] == 799.0
    assert client.get(f"{API}/eu", headers=h).json()["conta"]["plano"] == "empresa"

    # estorno da segunda: a cobrança fica estornada (auditoria), a conta segue ativa
    asaas_falso.simular("estornar", segunda)
    assert sql(dono, "select situacao from cobrancas where asaas_id = :p", p=segunda) == [("estornada",)]

    # cancela: o Asaas apaga a fatura em aberto; usa até o fim do período pago
    r = client.post(f"{API}/assinatura/cancelar", headers=h)
    assert r.status_code == 200, r.text
    assert r.json()["assinatura"] is None and r.json()["conta"]["situacao"] == "cancelada"
    assert asaas_falso.dados["assinaturas"][sid]["deleted"] is True
    assert asaas_falso.dados["cobrancas"][terceira]["deleted"] is True
    assert sql(dono, "select situacao from cobrancas where asaas_id = :p", p=terceira) == [("removida",)]
    assert client.get(f"{API}/eu", headers=h).json()["conta"]["cobranca"]["aviso"] == {
        "tipo": "cancelada", "data": "2026-12-14", "dias": 21}

    # assina de novo antes do fim do período pago: primeira fatura no dia seguinte ao pago_ate, conta segue ativa
    r = assinar(client, h, "essencial")
    assert r.status_code == 201, r.text
    assert r.json()["assinatura"]["primeiro_vencimento"] == "2026-12-15"
    assert r.json()["conta"]["situacao"] == "ativa"
    assert asaas_falso.assinatura()["customer"] == cliente["id"]  # o mesmo cliente no Asaas

    eventos = [e for (e,) in sql(dono, "select evento from auditoria where conta_id = :c order by id", c=conta)]
    for e in ("assinatura_criada", "pagamento_confirmado", "pagamento_vencido", "plano_alterado",
              "pagamento_estornado", "assinatura_cancelada"):
        assert e in eventos, e
    assert eventos.count("pagamento_confirmado") == 2
    assert tarefas.executar("assinaturas")["assinaturas"]["testes_expirados"] == 0

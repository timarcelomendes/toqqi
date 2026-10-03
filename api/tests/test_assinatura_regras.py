"""Etapa 5a: regras da assinatura sem banco — "liberada" e os limites de data em São Paulo (fim do teste, carência da
primeira fatura de quem assinou no teste, 7º dia de atraso, `pago_ate`, o mais tarde entre o teste e o período pago),
quando os envios param, o aviso do topo (coerente com a liberação) e o primeiro vencimento."""
from datetime import date, datetime, time, timedelta, timezone

import pytest
from util import FUSO

from toqqi.modelos import Conta
from toqqi.modulos.assinatura import regras
from toqqi.modulos.assinatura.regras import aviso, liberada, pausa_em, primeiro_vencimento

UM = timedelta(microseconds=1)


def sp(dia: str, hora: int = 0, minuto: int = 0) -> datetime:
    return datetime.combine(date.fromisoformat(dia), time(hora, minuto), tzinfo=FUSO)


def d(dia: str) -> date:
    return date.fromisoformat(dia)


def conta(situacao: str, teste_ate: datetime | None = None, pago_ate: str | None = None,
          atrasada_desde: str | None = None, primeiro_vencimento: str | None = None) -> Conta:
    return Conta(situacao=situacao, plano="profissional",
                 teste_ate=teste_ate.astimezone(timezone.utc) if teste_ate else None,
                 pago_ate=d(pago_ate) if pago_ate else None,
                 atrasada_desde=d(atrasada_desde) if atrasada_desde else None,
                 primeiro_vencimento=d(primeiro_vencimento) if primeiro_vencimento else None)


# ---- liberada ----------------------------------------------------------------------------

@pytest.mark.parametrize("situacao", ["cortesia", "ativa"])
def test_cortesia_e_ativa_sempre(situacao):
    c = conta(situacao, teste_ate=sp("2020-01-01"), pago_ate="2020-01-01", atrasada_desde="2020-01-01")
    assert liberada(c, sp("2030-01-01")) is True
    assert pausa_em(c, sp("2030-01-01")) is None and aviso(c, sp("2030-01-01")) is None


def test_teste_expirado_nunca():
    c = conta("teste_expirado", teste_ate=sp("2030-01-01"), pago_ate="2030-01-01")
    assert liberada(c, sp("2026-10-10")) is False and pausa_em(c, sp("2026-10-10")) is None


def test_teste_ate_o_fim_do_teste():
    c = conta("teste", teste_ate=sp("2026-10-15", 14, 30))
    assert liberada(c, sp("2026-10-15", 14, 30) - UM) is True
    assert liberada(c, sp("2026-10-15", 14, 30)) is False
    assert pausa_em(c, sp("2026-10-10")) == datetime(2026, 10, 15, 17, 30, tzinfo=timezone.utc)
    assert pausa_em(c, sp("2026-10-15", 15)) is None
    assert liberada(conta("teste"), sp("2026-10-10")) is False  # sem data de fim


def test_teste_com_assinatura_vai_ate_o_fim_da_carencia_da_primeira_fatura():
    """Quem assinou no teste e ainda não pagou segue liberado até o fim do 7º dia depois do primeiro vencimento — o
    mesmo prazo de quando a tarefa a marca `atrasada` (sem buraco entre a meia-noite do vencimento e a tarefa)."""
    c = conta("teste", teste_ate=sp("2026-10-15", 14, 30), primeiro_vencimento="2026-10-15")
    assert liberada(c, sp("2026-10-15", 14, 30)) is True  # passou do fim do teste: segue pela carência
    assert liberada(c, sp("2026-10-16", 0, 1)) is True  # venceu e a tarefa ainda não rodou
    assert liberada(c, sp("2026-10-23") - UM) is True
    assert liberada(c, sp("2026-10-23")) is False
    assert pausa_em(c, sp("2026-10-15", 20)) == datetime(2026, 10, 23, 3, tzinfo=timezone.utc)
    atrasada = conta("atrasada", teste_ate=sp("2026-10-15", 14, 30), atrasada_desde="2026-10-15",
                     primeiro_vencimento="2026-10-15")
    assert pausa_em(atrasada, sp("2026-10-16")) == pausa_em(c, sp("2026-10-16"))  # o mesmo prazo depois da tarefa
    # o aviso também: a fatura venceu (carência), antes e depois da tarefa
    esperado = {"tipo": "atrasada", "data": d("2026-10-23"), "dias": 7}
    assert aviso(c, sp("2026-10-16", 0, 1)) == esperado == aviso(atrasada, sp("2026-10-16", 0, 1))
    # assinatura feita depois do teste (vencimento depois do último dia dele) não estica o teste
    depois = conta("teste", teste_ate=sp("2026-10-15", 14, 30), primeiro_vencimento="2026-10-20")
    assert liberada(depois, sp("2026-10-15", 14, 30)) is False


def test_teste_que_acaba_a_meia_noite():
    # fim às 00:00 de 16/10 = o último dia é 15/10 (a assinatura no teste vence em 15/10)
    c = conta("teste", teste_ate=sp("2026-10-16"))
    assert regras.ultimo_dia_do_teste(c) == d("2026-10-15")
    assert primeiro_vencimento(c, sp("2026-10-10")) == d("2026-10-15")
    c.primeiro_vencimento = d("2026-10-15")
    assert liberada(c, sp("2026-10-23") - UM) is True and liberada(c, sp("2026-10-23")) is False


def test_teste_e_cancelada_vao_ate_o_mais_tarde_entre_o_teste_e_o_periodo_pago():
    # pagou no teste e o período pago vai além do fim do teste
    c = conta("teste", teste_ate=sp("2026-10-15", 14, 30), pago_ate="2026-11-14")
    assert liberada(c, sp("2026-11-15") - UM) is True and liberada(c, sp("2026-11-15")) is False
    assert pausa_em(c, sp("2026-11-01")) == datetime(2026, 11, 15, 3, tzinfo=timezone.utc)
    assert aviso(c, sp("2026-11-10")) == {"tipo": "cancelada", "data": d("2026-11-14"), "dias": 4}
    # cancelada com o teste (estendido) acabando depois do período pago: até o fim do teste, sem buraco
    c = conta("cancelada", teste_ate=sp("2026-11-20", 10), pago_ate="2026-11-14")
    assert liberada(c, sp("2026-11-17")) is True
    assert liberada(c, sp("2026-11-20", 10) - UM) is True and liberada(c, sp("2026-11-20", 10)) is False
    assert pausa_em(c, sp("2026-11-01")) == datetime(2026, 11, 20, 13, tzinfo=timezone.utc)
    # o aviso diz o último dia com envios
    assert aviso(c, sp("2026-11-10")) == {"tipo": "cancelada", "data": d("2026-11-20"), "dias": 10}
    assert aviso(c, sp("2026-11-17")) == {"tipo": "teste_acabando", "data": d("2026-11-20"), "dias": 3}
    assert aviso(c, sp("2026-11-20", 11))["tipo"] == "cancelada_encerrada"


def test_atrasada_ate_o_fim_do_7o_dia():
    c = conta("atrasada", pago_ate="2026-10-09", atrasada_desde="2026-10-10")
    assert liberada(c, sp("2026-10-17", 23, 59)) is True
    assert liberada(c, sp("2026-10-18") - UM) is True
    assert liberada(c, sp("2026-10-18")) is False
    assert pausa_em(c, sp("2026-10-11")) == datetime(2026, 10, 18, 3, tzinfo=timezone.utc)
    assert liberada(conta("atrasada"), sp("2026-10-10")) is False  # sem a data do atraso


def test_cancelada_ate_o_fim_do_dia_pago_ate():
    c = conta("cancelada", pago_ate="2026-11-14")
    assert liberada(c, sp("2026-11-15") - UM) is True
    assert liberada(c, sp("2026-11-15")) is False
    assert pausa_em(c, sp("2026-11-01")) == datetime(2026, 11, 15, 3, tzinfo=timezone.utc)
    assert liberada(conta("cancelada"), sp("2026-10-10")) is False


def test_relogio_de_sao_paulo_e_nao_utc():
    # 00:30 em UTC do dia 18 ainda é dia 17 (21:30) em São Paulo: liberada
    c = conta("atrasada", atrasada_desde="2026-10-10")
    assert liberada(c, datetime(2026, 10, 18, 0, 30, tzinfo=timezone.utc)) is True
    assert liberada(c, datetime(2026, 10, 18, 3, 0, tzinfo=timezone.utc)) is False


# ---- aviso -------------------------------------------------------------------------------------

def test_aviso_teste_acabando_com_5_dias_ou_menos():
    c = conta("teste", teste_ate=sp("2026-10-15", 14, 30))
    assert aviso(c, sp("2026-10-09", 23)) is None  # 6 dias
    assert aviso(c, sp("2026-10-10")) == {"tipo": "teste_acabando", "data": d("2026-10-15"), "dias": 5}
    assert aviso(c, sp("2026-10-15", 14)) == {"tipo": "teste_acabando", "data": d("2026-10-15"), "dias": 0}
    assert aviso(c, sp("2026-10-15", 15)) == {"tipo": "teste_expirado", "data": d("2026-10-15"), "dias": None}


def test_avisos_das_outras_situacoes():
    hoje = sp("2026-11-16", 9)
    assert aviso(conta("teste_expirado", teste_ate=sp("2026-10-15", 14)), hoje) == {
        "tipo": "teste_expirado", "data": d("2026-10-15"), "dias": None}
    assert aviso(conta("atrasada", atrasada_desde="2026-11-15"), hoje) == {
        "tipo": "atrasada", "data": d("2026-11-23"), "dias": 7}
    assert aviso(conta("atrasada", atrasada_desde="2026-11-01"), hoje) == {
        "tipo": "pausada", "data": d("2026-11-01"), "dias": None}
    assert aviso(conta("cancelada", pago_ate="2026-11-20"), hoje) == {
        "tipo": "cancelada", "data": d("2026-11-20"), "dias": 4}
    assert aviso(conta("cancelada", pago_ate="2026-11-16"), hoje) == {
        "tipo": "cancelada", "data": d("2026-11-16"), "dias": 0}
    assert aviso(conta("cancelada", pago_ate="2026-11-15"), hoje) == {
        "tipo": "cancelada_encerrada", "data": d("2026-11-15"), "dias": None}


def test_aviso_aguardando_pagamento_de_quem_ja_assinou():
    # assinou no teste (primeira fatura no último dia dele): nada de "teste acabando"; a 5 dias do vencimento, o aviso
    # da primeira fatura (envios liberados)
    c = conta("teste", teste_ate=sp("2026-10-15", 14, 30), primeiro_vencimento="2026-10-15")
    assert aviso(c, sp("2026-10-09", 23)) is None
    assert aviso(c, sp("2026-10-10")) == {"tipo": "aguardando_pagamento", "data": d("2026-10-15"), "dias": 5}
    assert aviso(c, sp("2026-10-15", 20)) == {"tipo": "aguardando_pagamento", "data": d("2026-10-15"), "dias": 0}
    assert liberada(c, sp("2026-10-15", 20)) is True
    # assinou com o teste vencido ou depois de cancelada (envios pausados até pagar): sempre
    for c in (conta("teste_expirado", teste_ate=sp("2026-09-15", 14), primeiro_vencimento="2026-10-02"),
              conta("cancelada", pago_ate="2026-09-20", primeiro_vencimento="2026-10-02")):
        assert liberada(c, sp("2026-10-01", 9)) is False
        assert aviso(c, sp("2026-10-01", 9)) == {"tipo": "aguardando_pagamento", "data": d("2026-10-02"), "dias": 1}
    # sem assinatura ativa, os avisos de sempre
    assert aviso(conta("cancelada", pago_ate="2026-09-20"), sp("2026-10-01"))["tipo"] == "cancelada_encerrada"
    assert regras.cobranca_json(conta("teste", teste_ate=sp("2026-10-15")), sp("2026-10-01"))["assinada"] is False


def test_cobranca_json():
    c = conta("atrasada", pago_ate="2026-11-14", atrasada_desde="2026-11-15", primeiro_vencimento="2026-10-15")
    assert regras.cobranca_json(c, sp("2026-11-16", 9)) == {
        "liberada": True, "assinada": True, "pago_ate": d("2026-11-14"), "atrasada_desde": d("2026-11-15"),
        "pausa_em": datetime(2026, 11, 23, 3, tzinfo=timezone.utc),
        "aviso": {"tipo": "atrasada", "data": d("2026-11-23"), "dias": 7}, "exclusao_em": None}


def test_mensagem_da_pre_condicao():
    assert regras.mensagem_pausa(conta("teste_expirado")) == regras.MSG_TESTE
    assert regras.mensagem_pausa(conta("atrasada", atrasada_desde="2026-10-01")) == regras.MSG_ATRASADA
    assert regras.mensagem_pausa(conta("cancelada", pago_ate="2026-10-01")) == regras.MSG_CANCELADA
    assert regras.mensagem_pausa(conta("teste_expirado", primeiro_vencimento="2026-10-11")) == regras.MSG_AGUARDANDO


# ---- primeiro vencimento e período pago --------------------------------------------------------

def test_primeiro_vencimento():
    agora = sp("2026-10-10", 10)
    no_teste = conta("teste", teste_ate=sp("2026-10-15", 14, 30))
    assert primeiro_vencimento(no_teste, agora) == d("2026-10-15")  # último dia do teste
    assert primeiro_vencimento(no_teste, sp("2026-10-15", 14)) == d("2026-10-15")  # o teste acaba hoje
    assert primeiro_vencimento(no_teste, sp("2026-10-15", 15)) == d("2026-10-16")  # já acabou: amanhã
    assert primeiro_vencimento(conta("teste_expirado", teste_ate=sp("2026-09-01")), agora) == d("2026-10-11")
    assert primeiro_vencimento(conta("cancelada", pago_ate="2026-11-14"), agora) == d("2026-11-15")
    assert primeiro_vencimento(conta("cancelada", pago_ate="2026-10-10"), agora) == d("2026-10-11")
    assert primeiro_vencimento(conta("cancelada", pago_ate="2026-10-09"), agora) == d("2026-10-11")
    # pagou no teste e cancelou: vale o fim do período pago (mais tarde)
    assert primeiro_vencimento(conta("teste", teste_ate=sp("2026-10-15", 14), pago_ate="2026-11-14"),
                               agora) == d("2026-11-15")


@pytest.mark.parametrize("vencimento,mais_um,fim", [
    ("2026-10-15", "2026-11-15", "2026-11-14"), ("2026-01-31", "2026-02-28", "2026-02-27"),
    ("2028-01-31", "2028-02-29", "2028-02-28"), ("2026-12-20", "2027-01-20", "2027-01-19"),
    ("2026-03-31", "2026-04-30", "2026-04-29"),
])
def test_mes_seguinte_e_fim_do_periodo_pago(vencimento, mais_um, fim):
    assert regras.mais_um_mes(d(vencimento)) == d(mais_um)
    assert regras.fim_do_periodo_pago(d(vencimento)) == d(fim)

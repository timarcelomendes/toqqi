"""Etapa 5a: todas as transições de `recalcular` (situação da conta pela assinatura e pelas cobranças), com a conta e
as cobranças montadas direto no banco e o relógio de São Paulo fixo; o plano do teste para quem sai da assinatura sem
nunca pagar; pagamentos de outro ambiente do Asaas não contam."""
from datetime import date, datetime, time

import pytest
from util import FUSO, conta_pronta, fixar_relogio, sql

from toqqi.core.db import em_conta
from toqqi.modelos import Conta
from toqqi.modulos.assinatura import regras
from toqqi.modulos.assinatura.servico import recalcular

FIM_DO_TESTE = "2026-10-15 14:30-03"  # último dia do teste: 15/10


def momento(dia: str, hora: int = 10) -> datetime:
    return datetime.combine(date.fromisoformat(dia), time(hora), tzinfo=FUSO)


def d(dia: str | None) -> date | None:
    return date.fromisoformat(dia) if dia else None


# nome: (agora, conta {situacao, teste_ate, pago_ate}, assinatura ativa (primeiro vencimento) ou None,
#        cobranças [(vencimento, situacao, da ativa?)], esperado (situacao, pago_ate, atrasada_desde), liberada)
CASOS = {
    "sem_assinatura_teste_valendo": (
        "2026-10-12", {"teste_ate": FIM_DO_TESTE}, None, [], ("teste", None, None), True),
    "sem_assinatura_teste_acabou": (
        "2026-10-16", {"teste_ate": FIM_DO_TESTE}, None, [], ("teste_expirado", None, None), False),
    "cancelada_ja_pagou": (
        "2026-10-20", {"teste_ate": FIM_DO_TESTE}, None, [("2026-10-15", "paga", False)],
        ("cancelada", "2026-11-14", None), True),
    "cancelada_periodo_acabou": (
        "2026-11-15", {"teste_ate": FIM_DO_TESTE}, None, [("2026-10-15", "paga", False)],
        ("cancelada", "2026-11-14", None), False),
    "cancelou_no_teste_depois_de_pagar": (  # o período pago vale mais que o teste: cancelada
        "2026-10-12", {"teste_ate": FIM_DO_TESTE}, None, [("2026-10-15", "paga", False)],
        ("cancelada", "2026-11-14", None), True),
    "cancelada_periodo_acabou_teste_valendo": (  # teste estendido depois do período pago: volta ao teste
        "2026-11-20", {"teste_ate": "2026-12-01 14:30-03", "situacao": "cancelada"}, None,
        [("2026-10-15", "paga", False)], ("teste", "2026-11-14", None), True),
    "cancelada_teste_e_periodo_acabaram": (
        "2026-12-02", {"teste_ate": "2026-12-01 14:30-03", "situacao": "cancelada"}, None,
        [("2026-10-15", "paga", False)], ("cancelada", "2026-11-14", None), False),
    "assinou_no_teste_fatura_em_aberto": (
        "2026-10-12", {"teste_ate": FIM_DO_TESTE}, "2026-10-15", [("2026-10-15", "pendente", True)],
        ("teste", None, None), True),
    "assinou_no_teste_dia_do_vencimento_depois_do_fim": (
        "2026-10-15 22", {"teste_ate": FIM_DO_TESTE}, "2026-10-15", [("2026-10-15", "pendente", True)],
        ("teste", None, None), True),
    "assinou_no_teste_pendente_passou_do_vencimento": (
        "2026-10-16 08", {"teste_ate": FIM_DO_TESTE}, "2026-10-15", [("2026-10-15", "pendente", True)],
        ("atrasada", None, "2026-10-15"), True),
    "assinou_no_teste_vencida_ha_8_dias": (
        "2026-10-23", {"teste_ate": FIM_DO_TESTE}, "2026-10-15", [("2026-10-15", "vencida", True)],
        ("atrasada", None, "2026-10-15"), False),
    "paga": (
        "2026-10-20", {"teste_ate": FIM_DO_TESTE}, "2026-10-15", [("2026-10-15", "paga", True)],
        ("ativa", "2026-11-14", None), True),
    "paga_e_a_seguinte_em_aberto": (
        "2026-11-10", {"teste_ate": FIM_DO_TESTE}, "2026-10-15",
        [("2026-10-15", "paga", True), ("2026-11-15", "pendente", True)], ("ativa", "2026-11-14", None), True),
    "paga_e_duas_vencidas": (
        "2027-01-10", {"teste_ate": FIM_DO_TESTE}, "2026-10-15",
        [("2026-10-15", "paga", True), ("2026-11-15", "vencida", True), ("2026-12-15", "vencida", True)],
        ("atrasada", "2026-11-14", "2026-11-15"), False),
    "vencida_paga_depois_fora_de_ordem": (
        "2026-11-20", {"teste_ate": FIM_DO_TESTE}, "2026-10-15",
        [("2026-10-15", "paga", True), ("2026-11-15", "paga", True)], ("ativa", "2026-12-14", None), True),
    "estornada_e_removida_nao_contam": (  # assinou no teste e não ficou paga: a carência da 1ª fatura (até 22/10)
        "2026-10-20", {"teste_ate": FIM_DO_TESTE}, "2026-10-15",
        [("2026-10-15", "estornada", True), ("2026-09-15", "removida", True)], ("teste", None, None), True),
    "estornada_depois_da_carencia": (
        "2026-10-23", {"teste_ate": FIM_DO_TESTE}, "2026-10-15",
        [("2026-10-15", "estornada", True)], ("teste_expirado", None, None), False),
    "assinou_depois_do_teste_em_aberto": (
        "2026-10-20", {"teste_ate": FIM_DO_TESTE, "situacao": "teste_expirado"}, "2026-10-21",
        [("2026-10-21", "pendente", True)], ("teste_expirado", None, None), False),
    "assinou_depois_do_teste_vencida_sem_carencia": (
        "2026-10-22", {"teste_ate": FIM_DO_TESTE, "situacao": "teste_expirado"}, "2026-10-21",
        [("2026-10-21", "vencida", True)], ("teste_expirado", None, "2026-10-21"), False),
    "assinou_de_novo_no_periodo_pago": (
        "2026-11-01", {"teste_ate": FIM_DO_TESTE, "pago_ate": "2026-11-14", "situacao": "cancelada"}, "2026-11-15",
        [("2026-11-15", "pendente", True)], ("ativa", "2026-11-14", None), True),
    "assinou_de_novo_no_periodo_pago_e_venceu": (
        "2026-11-17", {"teste_ate": FIM_DO_TESTE, "pago_ate": "2026-11-14", "situacao": "cancelada"}, "2026-11-15",
        [("2026-11-15", "vencida", True)], ("atrasada", "2026-11-14", "2026-11-15"), True),
    "assinou_de_novo_depois_do_periodo_pago": (
        "2026-12-01", {"teste_ate": FIM_DO_TESTE, "pago_ate": "2026-11-14", "situacao": "cancelada"}, "2026-12-02",
        [("2026-12-02", "pendente", True)], ("cancelada", "2026-11-14", None), False),
    "pago_ate_nunca_diminui": (
        "2026-12-20", {"teste_ate": FIM_DO_TESTE, "pago_ate": "2027-01-14", "situacao": "cancelada"}, None,
        [("2026-10-15", "paga", False)], ("cancelada", "2027-01-14", None), True),
    "cortesia_nao_muda": (
        "2026-12-20", {"teste_ate": None, "situacao": "cortesia"}, None, [("2026-10-15", "paga", False)],
        ("cortesia", "2026-11-14", None), True),
}


def _assinatura(dono, conta_id: int, asaas_id: str, primeiro: str, situacao: str = "ativa",
                ambiente: str = "sandbox", plano: str = "profissional") -> None:
    sql(dono, """insert into assinaturas (conta_id, asaas_id, ambiente, plano, valor, situacao, razao_social, documento,
                                          email_cobranca, telefone, primeiro_vencimento, cancelada_em)
                 values (:c, :a, :amb, :plano, 349, :s, 'Alfa', '11222333000181', 'a@a.com.br', '5511987654321', :p,
                         case when :s = 'cancelada' then now() end)""",
        c=conta_id, a=asaas_id, amb=ambiente, plano=plano, s=situacao, p=primeiro)


def _cobranca(dono, conta_id: int, asaas_id: str, assinatura: str, vencimento: str, situacao: str) -> None:
    sql(dono, """insert into cobrancas (conta_id, assinatura_id, asaas_id, valor, vencimento, situacao)
                 values (:c, (select id from assinaturas where asaas_id = :a), :id, 349, :v, :s)""",
        c=conta_id, a=assinatura, id=asaas_id, v=vencimento, s=situacao)


def _recalcular(conta_id: int) -> Conta:
    with em_conta(conta_id) as s:
        c = s.get(Conta, conta_id, with_for_update=True)
        recalcular(s, c)
        return c


def _agora(texto: str) -> datetime:
    dia, _, hora = texto.partition(" ")
    return momento(dia, int(hora) if hora else 10)


@pytest.mark.parametrize("nome", list(CASOS))
def test_transicoes(client, dono, monkeypatch, nome):
    agora, conta, primeiro, cobrancas, esperado, liberada = CASOS[nome]
    fixar_relogio(monkeypatch, momento("2026-10-10"))
    cid = conta_pronta(client, "ana@alfa.com.br", empresa="Alfa")["conta"]["id"]
    sql(dono, "update contas set situacao = :s, teste_ate = :t, pago_ate = :p where id = :c",
        s=conta.get("situacao", "teste"), t=conta["teste_ate"], p=conta.get("pago_ate"), c=cid)
    # assinatura antiga (cancelada) para as cobranças de fora da ativa
    _assinatura(dono, cid, "sub_antiga", "2026-09-15", situacao="cancelada")
    if primeiro:
        _assinatura(dono, cid, "sub_ativa", primeiro)
    for i, (vencimento, situacao, da_ativa) in enumerate(cobrancas):
        _cobranca(dono, cid, f"pay_{i}", "sub_ativa" if da_ativa else "sub_antiga", vencimento, situacao)
    fixar_relogio(monkeypatch, _agora(agora))
    with em_conta(cid) as s:
        c = s.get(Conta, cid, with_for_update=True)
        recalcular(s, c)
        resultado = (c.situacao, c.pago_ate, c.atrasada_desde)
        assert c.primeiro_vencimento == d(primeiro)
        assert regras.liberada(c) is liberada
    assert resultado == (esperado[0], d(esperado[1]), d(esperado[2]))


@pytest.mark.parametrize("pagou,plano", [(False, "profissional"), (True, "empresa")])
def test_sem_assinatura_e_sem_nunca_pagar_volta_ao_plano_do_teste(client, dono, monkeypatch, pagou, plano):
    fixar_relogio(monkeypatch, momento("2026-10-12"))
    cid = conta_pronta(client, "ana@alfa.com.br", empresa="Alfa")["conta"]["id"]
    sql(dono, "update contas set plano = 'empresa', teste_ate = :t where id = :c", t=FIM_DO_TESTE, c=cid)
    _assinatura(dono, cid, "sub_antiga", "2026-10-15", situacao="cancelada", plano="empresa")
    if pagou:
        _cobranca(dono, cid, "pay_1", "sub_antiga", "2026-10-15", "paga")
    c = _recalcular(cid)
    assert (c.situacao, c.plano) == ("cancelada" if pagou else "teste", plano)
    # cortesia não muda
    sql(dono, "update contas set plano = 'empresa', situacao = 'cortesia' where id = :c", c=cid)
    assert _recalcular(cid).plano == "empresa"


def test_pagamento_de_outro_ambiente_nao_conta(client, dono, monkeypatch):
    """Chave de produção: a assinatura de sandbox não existe para ela e os pagamentos dela não entram no pago_ate."""
    from util import CHAVE_ASAAS

    from toqqi.core.config import config

    fixar_relogio(monkeypatch, momento("2026-10-20"))
    cid = conta_pronta(client, "ana@alfa.com.br", empresa="Alfa")["conta"]["id"]
    sql(dono, "update contas set teste_ate = :t where id = :c", t=FIM_DO_TESTE, c=cid)
    _assinatura(dono, cid, "sub_sandbox", "2026-10-15")
    _cobranca(dono, cid, "pay_1", "sub_sandbox", "2026-10-15", "paga")
    monkeypatch.setattr(config(), "ASAAS_API_KEY", CHAVE_ASAAS.replace("$aact_hmlg_", "$aact_prod_"))
    c = _recalcular(cid)
    assert (c.situacao, c.pago_ate, c.primeiro_vencimento) == ("teste_expirado", None, None)
    monkeypatch.setattr(config(), "ASAAS_API_KEY", CHAVE_ASAAS)  # de volta ao sandbox: ela existe de novo
    c = _recalcular(cid)
    assert (c.situacao, c.pago_ate, c.primeiro_vencimento) == ("ativa", date(2026, 11, 14), date(2026, 10, 15))

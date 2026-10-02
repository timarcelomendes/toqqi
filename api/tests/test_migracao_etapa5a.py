"""Migração 0008 (assinaturas): restrições do banco (ambiente do Asaas, CNPJ alfanumérico, remoções pendentes); descer
para a 0007 (volta o gatilho do limite e os CHECKs antigos de documento) e subir de novo."""
from datetime import date

import pytest
from alembic.config import Config as AlembicConfig
from conftest import OWNER_URL
from sqlalchemy.exc import IntegrityError
from util import API, assinar, conta_pronta, sql

from alembic import command
from toqqi.core.db import RAIZ_API

TABELAS = ("assinaturas", "cobrancas", "asaas_eventos", "asaas_remocoes")
COLUNAS_CONTA = {"asaas_cliente_id", "asaas_ambiente", "asaas_conferida_em", "pago_ate", "atrasada_desde",
                 "primeiro_vencimento"}
ASSINATURA = ("insert into assinaturas (conta_id, asaas_id, ambiente, plano, valor, situacao, razao_social, documento, "
              "email_cobranca, telefone, primeiro_vencimento, cancelada_em) values (:c, :asaas, :ambiente, :plano, "
              ":valor, :situacao, 'Alfa', :doc, 'a@a.com.br', :tel, '2026-10-15', :cancelada)")


def _alembic() -> AlembicConfig:
    cfg = AlembicConfig(str(RAIZ_API / "alembic.ini"))
    cfg.set_main_option("script_location", str(RAIZ_API / "alembic"))
    cfg.attributes["url"] = OWNER_URL
    return cfg


def _colunas(dono, tabela: str) -> set[str]:
    return {c for (c,) in sql(dono, "select column_name from information_schema.columns "
                                    "where table_schema = 'public' and table_name = :t", t=tabela)}


@pytest.fixture
def conta(client):
    return conta_pronta(client, "ana@alfa.com.br", empresa="Alfa")


def _assinatura(dono, conta_id: int, **campos) -> None:
    valores = {"asaas": "sub_1", "ambiente": "sandbox", "plano": "essencial", "valor": 149, "situacao": "ativa",
               "doc": "11222333000181", "tel": "5511987654321", "cancelada": None, **campos}
    sql(dono, ASSINATURA, c=conta_id, **valores)


@pytest.mark.parametrize("campos", [
    {"plano": "ouro"}, {"valor": 0}, {"situacao": "suspensa"}, {"doc": "123"}, {"tel": "abc"},
    {"situacao": "cancelada"},  # cancelada sem data
    {"cancelada": "2026-10-10"},  # ativa com data de cancelamento
    {"asaas": ""}, {"ambiente": "teste"}, {"ambiente": None},
    {"doc": "12abc34501de35"}, {"doc": "12ABC34501DEAB"}, {"doc": "12ABC34501DE3"},  # minúsculas; letra no DV; 13
])
def test_restricoes_das_assinaturas(conta, dono, campos):
    with pytest.raises(IntegrityError):
        _assinatura(dono, conta["conta"]["id"], **campos)


@pytest.mark.parametrize("tabela", ["empresas", "contas", "assinaturas"])
def test_cnpj_alfanumerico_aceito_no_banco(conta, dono, tabela):
    c = conta["conta"]["id"]
    if tabela == "assinaturas":
        _assinatura(dono, c, doc="12ABC34501DE35")
    elif tabela == "contas":
        sql(dono, "update contas set documento = '12ABC34501DE35' where id = :c", c=c)
    else:
        sql(dono, "insert into empresas (conta_id, nome, documento) values (:c, 'Gama', '12ABC34501DE35')", c=c)
    assert sql(dono, f"select count(*) from {tabela} where documento = '12ABC34501DE35'")[0][0] == 1
    for ruim in ("12abc34501de35", "12ABC34501DEAB", "12ABC34501DE3", "12ABC34501DE355"):
        with pytest.raises(IntegrityError):
            if tabela == "empresas":
                sql(dono, "update empresas set documento = :d", d=ruim)
            else:
                sql(dono, f"update {tabela} set documento = :d where conta_id = :c" if tabela == "assinaturas"
                    else "update contas set documento = :d where id = :c", d=ruim, c=c)


def test_restricoes_das_remocoes_pendentes(conta, dono):
    c = conta["conta"]["id"]
    sql(dono, "insert into asaas_remocoes (asaas_id, ambiente, conta_id, motivo) values ('sub_1', 'sandbox', :c, "
              "'duplicada')", c=c)
    for comando in (
        "insert into asaas_remocoes (asaas_id, ambiente, motivo) values ('sub_1', 'sandbox', 'x')",  # repetida
        "insert into asaas_remocoes (asaas_id, ambiente, motivo) values ('sub_2', 'teste', 'x')",
        "insert into asaas_remocoes (asaas_id, ambiente, motivo) values ('sub_2', 'sandbox', '')",
        "insert into asaas_remocoes (asaas_id, ambiente, motivo, tentativas) values ('sub_2', 'sandbox', 'x', -1)",
        "insert into asaas_remocoes (asaas_id, ambiente, motivo) values ('', 'sandbox', 'x')",
    ):
        with pytest.raises(IntegrityError):
            sql(dono, comando)
    # a conta excluída não leva a remoção pendente junto (o Asaas ainda precisa remover)
    sql(dono, "delete from contas where id = :c", c=c)
    assert sql(dono, "select asaas_id, conta_id from asaas_remocoes") == [("sub_1", None)]


def test_uma_ativa_por_conta_e_restricoes_das_cobrancas(conta, dono):
    c = conta["conta"]["id"]
    _assinatura(dono, c)
    with pytest.raises(IntegrityError):
        _assinatura(dono, c, asaas="sub_2")
    _assinatura(dono, c, asaas="sub_3", situacao="cancelada", cancelada="2026-10-10")  # canceladas podem ser várias
    with pytest.raises(IntegrityError):  # asaas_id único
        _assinatura(dono, c, asaas="sub_3", situacao="cancelada", cancelada="2026-10-10")
    for comando in (
        "insert into cobrancas (conta_id, asaas_id, valor, vencimento, situacao) "
        "values (:c, 'p1', 1, '2026-10-15', 'x')",
        "insert into cobrancas (conta_id, asaas_id, valor, vencimento, situacao, forma) "
        "values (:c, 'p1', 1, '2026-10-15', 'paga', 'cheque')",
        "insert into cobrancas (conta_id, asaas_id, valor, vencimento, situacao) values (:c, 'p1', -1, '2026-10-15', "
        "'paga')",
        "insert into asaas_eventos (id, tipo, tentativas) values ('evt_1', 'PAYMENT_CREATED', -1)",
        "insert into asaas_eventos (id, tipo) values ('', 'PAYMENT_CREATED')",
        "update contas set asaas_cliente_id = '', asaas_ambiente = 'sandbox' where id = :c",
        "update contas set asaas_cliente_id = 'cus_1' where id = :c",  # cliente sem o ambiente
        "update contas set asaas_ambiente = 'sandbox' where id = :c",  # ambiente sem o cliente
        "update contas set asaas_cliente_id = 'cus_1', asaas_ambiente = 'teste' where id = :c",
    ):
        with pytest.raises(IntegrityError):
            sql(dono, comando, c=c)
    outra = sql(dono, "insert into contas (nome) values ('Outra') returning id")[0][0]
    sql(dono, "update contas set asaas_cliente_id = 'cus_1', asaas_ambiente = 'producao' where id = :c", c=c)
    with pytest.raises(IntegrityError):  # o mesmo cliente do Asaas em duas contas
        sql(dono, "update contas set asaas_cliente_id = 'cus_1', asaas_ambiente = 'producao' where id = :o", o=outra)


def _trava_antes_do_plano(dono) -> bool:
    """A função do gatilho do limite pega a trava antes de ler o plano?"""
    definicao = sql(dono, "select pg_get_functiondef('contatos_checar_limite'::regproc)")[0][0]
    return definicao.index("pg_advisory_xact_lock") < definicao.index("limite_contatos(")


def test_descer_e_subir_a_0008(client, conta, dono, asaas_falso):
    h, c = conta["h"], conta["conta"]["id"]
    assert assinar(client, h).status_code == 201
    asaas_falso.simular("pagar", asaas_falso.cobrancas()[0]["id"], forma="PIX")
    assert sql(dono, "select situacao from contas where id = :c", c=c) == [("ativa",)]
    sql(dono, "update contas set documento = '12ABC34501DE35' where id = :c", c=c)
    sql(dono, "insert into empresas (conta_id, nome, documento) values (:c, 'Gama', '12ABC34501DE35'), "
              "(:c, 'Delta', '11222333000181')", c=c)
    assert _trava_antes_do_plano(dono)
    cfg = _alembic()
    command.downgrade(cfg, "0007_ia_relatorios")
    try:
        assert sql(dono, "select to_regclass('assinaturas'), to_regclass('cobrancas'), "
                         "to_regclass('asaas_eventos'), to_regclass('asaas_remocoes')")[0] == (None, None, None, None)
        assert not COLUNAS_CONTA & _colunas(dono, "contas")
        assert sql(dono, "select situacao from contas where id = :c", c=c) == [("ativa",)]  # a situação fica
        # os CHECKs antigos de documento voltam (o alfanumérico fica sem valor) e a função antiga do gatilho também
        assert sql(dono, "select documento from contas where id = :c", c=c) == [(None,)]
        assert sql(dono, "select nome, documento from empresas order by nome") == [
            ("Delta", "11222333000181"), ("Gama", None)]
        with pytest.raises(IntegrityError):
            sql(dono, "update contas set documento = '12ABC34501DE35' where id = :c", c=c)
        assert not _trava_antes_do_plano(dono)
    finally:
        command.upgrade(cfg, "head")
    assert COLUNAS_CONTA <= _colunas(dono, "contas")
    assert _trava_antes_do_plano(dono)
    sql(dono, "update contas set documento = '12ABC34501DE35' where id = :c", c=c)
    for t in TABELAS:
        assert sql(dono, f"select count(*) from {t}")[0][0] == 0, t
    assert sql(dono, "select pago_ate, asaas_cliente_id from contas where id = :c", c=c) == [(None, None)]
    # o papel da aplicação volta a ter acesso às tabelas novas
    sql(dono, "update contas set situacao = 'teste', teste_ate = now() + interval '5 days' where id = :c", c=c)
    asaas_falso.dados["assinaturas"].clear()
    assert assinar(client, h).status_code == 201
    assert client.get(f"{API}/assinatura", headers=h).json()["assinatura"]["primeiro_vencimento"] >= str(date.today())

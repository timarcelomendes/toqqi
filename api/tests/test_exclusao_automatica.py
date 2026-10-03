"""Exclusão automática das contas encerradas (etapa 5f): regras puras (`encerramento`, `exclusao_em`), quem entra e quem
nunca entra, aviso uma vez (data = max(prevista, hoje + 7)), exclusão só com 7 dias nos dois relógios e conta com 100
dias, assinar depois cancela, novo encerramento avisa de novo, limite de 20, `simular`, uma vez por dia, antes das 9h,
rodada simultânea, Asaas fora, global e log sem dado pessoal, `cobranca.exclusao_em` e a lista da Plataforma.
Revisão: limites do dia contados pelos eventos de hoje (rodada interrompida ou evento do dia apagado não liberam mais),
erro numa conta não para as outras, aviso só vale entregue (sem administrador ativo, exclui com `admins: 0`), Asaas sem
a chave do ambiente do cliente → adiada, `EXCLUSAO_AUTOMATICA` com outro valor simula e a linha de comando mostra o log."""
import json
import logging
import os
import subprocess
import sys
import textwrap
from datetime import date, datetime, time, timedelta, timezone

import pytest
from sqlalchemy import text
from util import (
    API,
    CHAVE_ASAAS,
    FUSO,
    conta_pronta,
    criar_contato,
    erro_http,
    falhar_provedor,
    fixar_relogio,
    membro,
    sql,
)

from toqqi import tarefas
from toqqi.core.config import Config, config
from toqqi.core.db import RAIZ_API
from toqqi.core.email import Memoria, caixa_memoria
from toqqi.modelos import Conta
from toqqi.modulos.assinatura import exclusao, regras

HOJE = datetime.now(FUSO).date()
AGORA = datetime.combine(HOJE, time(10), tzinfo=FUSO)


def sp(d: date, hora: int = 12) -> datetime:
    return datetime.combine(d, time(hora), tzinfo=FUSO)


# ---- regras puras --------------------------------------------------------------------------------

def _conta(situacao: str, teste_ate: datetime | None = None, pago_ate: date | None = None,
           primeiro_vencimento: date | None = None, avisada: date | None = None) -> Conta:
    return Conta(situacao=situacao, plano="profissional", teste_ate=teste_ate, pago_ate=pago_ate,
                 primeiro_vencimento=primeiro_vencimento, exclusao_avisada_para=avisada)


def test_encerramento():
    d = date(2026, 1, 10)
    agora = sp(date(2026, 6, 1))
    assert regras.encerramento(_conta("teste_expirado", teste_ate=sp(d, 15)), agora) == (d, d + timedelta(days=90))
    # cancelada: o dia seguinte ao pago_ate (o fim do período pago é 00:00 do dia seguinte)
    assert regras.encerramento(_conta("cancelada", pago_ate=d), agora) == (d + timedelta(days=1),
                                                                            d + timedelta(days=91))
    # o mais tarde entre o teste e o período pago
    assert regras.encerramento(_conta("cancelada", teste_ate=sp(d + timedelta(days=5)), pago_ate=d), agora)[0] == \
        d + timedelta(days=5)
    for situacao in ("ativa", "atrasada", "cortesia", "teste"):
        assert regras.encerramento(_conta(situacao, teste_ate=sp(d), pago_ate=d), agora) is None, situacao
    assert regras.encerramento(_conta("cancelada", pago_ate=d, primeiro_vencimento=d), agora) is None  # assinou
    assert regras.encerramento(_conta("teste_expirado"), agora) is None  # sem data
    assert regras.encerramento(_conta("cancelada", pago_ate=date(2026, 6, 10)), agora) is None  # ainda liberada


def test_exclusao_em():
    d = date(2026, 1, 10)
    agora = sp(date(2026, 4, 5))
    prevista = d + timedelta(days=90)
    assert regras.exclusao_em(_conta("teste_expirado", teste_ate=sp(d), avisada=prevista), agora) == prevista
    assert regras.exclusao_em(_conta("teste_expirado", teste_ate=sp(d), avisada=prevista - timedelta(days=1)),
                              agora) is None  # aviso de um encerramento anterior
    assert regras.exclusao_em(_conta("ativa", teste_ate=sp(d), avisada=prevista), agora) is None  # assinou
    assert regras.exclusao_em(_conta("teste_expirado", teste_ate=sp(d)), agora) is None
    assert regras.cobranca_json(_conta("teste_expirado", teste_ate=sp(d), avisada=prevista), agora)["exclusao_em"] \
        == prevista


# ---- a rotina ------------------------------------------------------------------------------------

@pytest.fixture
def ligada(monkeypatch):
    fixar_relogio(monkeypatch, AGORA)
    monkeypatch.setattr(config(), "EXCLUSAO_AUTOMATICA", "ligada")


def _encerrar(dono, conta_id: int, dias: int = 90, situacao: str = "teste_expirado", criada_dias: int = 200,
              **campos) -> None:
    """Teste acabado há `dias` dias (o fim no meio do dia, São Paulo); conta criada há `criada_dias`."""
    valores = {"teste_ate": sp(HOJE - timedelta(days=dias)), "situacao": situacao,
               "criada": datetime.now(timezone.utc) - timedelta(days=criada_dias), **campos}
    extra = "".join(f", {k} = :{k}" for k in campos)
    sql(dono, f"update contas set situacao = :situacao, teste_ate = :teste_ate, criada_em = :criada{extra} "
              "where id = :c", c=conta_id, **valores)


def _avisada(dono, conta_id: int, para: date, dias_atras: int = 7, entregue: bool = True) -> None:
    """Aviso gravado há `dias_atras` dias (relógio do banco) para `para`; `entregue`: com o e-mail do aviso aceito pelo
    provedor no registro de e-mails enviados (um minuto depois do aviso)."""
    sql(dono, "update contas set exclusao_avisada_para = :p, exclusao_avisada_em = now() - make_interval(days => :d) "
              "where id = :c", c=conta_id, p=para, d=dias_atras)
    if entregue:
        _email_do_aviso(dono, conta_id, para)


def _email_do_aviso(dono, conta_id: int, para: date, situacao: str = "enviado", assunto: str | None = None,
                    depois: bool = True) -> None:
    """O e-mail do aviso em `emails_enviados`, um minuto depois (ou antes, com `depois=False`) do aviso gravado."""
    sql(dono, "insert into emails_enviados (conta_id, tipo, destinatario, assunto, situacao, erro, criado_em) "
              "select id, 'aviso', 'ana@alfa.com.br', :a, :s, :e, exclusao_avisada_em + make_interval(mins => :m) "
              "from contas where id = :c",
        c=conta_id, a=assunto or f"Sua conta no Toqqi será excluída em {para:%d/%m/%Y}", s=situacao,
        e="O provedor de e-mail está fora do ar; tentaremos de novo." if situacao == "falhou" else None,
        m=1 if depois else -1)


def _prontas(dono, n: int) -> list[int]:
    """n contas sem equipe prontas para a exclusão (teste acabado há 100 dias, avisadas há 8 dias para 3 dias atrás;
    sem administrador ativo, valem sem o e-mail do aviso)."""
    return [i for (i,) in sql(dono, """
        insert into contas (nome, situacao, teste_ate, criada_em, exclusao_avisada_para, exclusao_avisada_em)
        select 'Conta ' || g, 'teste_expirado', :t, now() - interval '300 days', :p, now() - interval '8 days'
          from generate_series(1, :n) g
        returning id
    """, t=sp(HOJE - timedelta(days=100)), p=HOJE - timedelta(days=3), n=n)]


def _a_avisar(dono, n: int) -> list[int]:
    """n contas sem equipe com o teste acabado há 90 dias (a exclusão prevista é hoje: hora do aviso)."""
    return [i for (i,) in sql(dono, """
        insert into contas (nome, situacao, teste_ate, criada_em)
        select 'Aviso ' || g, 'teste_expirado', :t, now() - interval '300 days' from generate_series(1, :n) g
        returning id
    """, t=sp(HOJE - timedelta(days=90)), n=n)]


def _contas(dono) -> int:
    return sql(dono, "select count(*) from contas")[0][0]


def _existe(dono, conta_id: int) -> bool:
    return bool(sql(dono, "select count(*) from contas where id = :c", c=conta_id)[0][0])


@pytest.fixture
def ana(client):
    return conta_pronta(client, "ana@alfa.com.br", empresa="Alfa")


def test_aviso_teste_vencido_ha_90_dias(client, dono, ana, ligada):
    c = ana["conta"]["id"]
    _encerrar(dono, c, dias=90)
    caixa_memoria.clear()
    r = tarefas.limpeza()["encerradas"]
    assert r == {"modo": "ligada", "avisadas": 1, "excluidas": 0, "adiadas": 0, "em_atraso_90_dias": 0,
                 "sem_data": 0}
    data = HOJE + timedelta(days=7)  # max(prevista = hoje, hoje + 7)
    ((para, em),) = sql(dono, "select exclusao_avisada_para, exclusao_avisada_em from contas where id = :c", c=c)
    assert para == data and em is not None
    ((detalhe, gravidade),) = sql(dono, "select detalhe, gravidade from auditoria where conta_id = :c "
                                        "and evento = 'exclusao_avisada'", c=c)
    assert gravidade == "atencao"
    assert detalhe == {"exclusao_em": data.isoformat(), "encerrada_em": (HOJE - timedelta(days=90)).isoformat(),
                       "admins": 1}
    (m,) = [m for m in caixa_memoria if m.para == "ana@alfa.com.br"]
    assert m.assunto == f"Sua conta no Toqqi será excluída em {data:%d/%m/%Y}"
    assert "Configurações › Dados da conta" in m.texto and "/configuracoes/dados-da-conta" in m.texto
    assert "assinar um plano" in m.texto and "Baixar os dados" in m.html
    assert sql(dono, "select tipo from emails_enviados where conta_id = :c and assunto = :a", c=c,
               a=m.assunto) == [("aviso",)]
    # o aviso aparece em conta.cobranca e na lista da Plataforma; nada é excluído ainda
    assert client.get(f"{API}/eu", headers=ana["h"]).json()["conta"]["cobranca"]["exclusao_em"] == data.isoformat()
    from toqqi.modulos.plataforma import servico as plataforma
    (item,) = [x for x in plataforma.listar() if x["id"] == c]
    assert item["exclusao_em"] == data
    assert _existe(dono, c)
    # uma vez por dia; amanhã não avisa de novo (o aviso vale para este encerramento)
    assert tarefas.limpeza()["encerradas"] is None
    sql(dono, "delete from auditoria where conta_id is null")
    r = tarefas.limpeza()["encerradas"]
    assert r["avisadas"] == 0 and len([m for m in caixa_memoria if m.para == "ana@alfa.com.br"]) == 1


def test_cancelada_com_pago_ate(client, dono, ana, ligada):
    c = ana["conta"]["id"]
    # pago_ate há 84 dias: encerrada no dia seguinte (há 83), prevista daqui a 7 → avisa
    _encerrar(dono, c, dias=300, situacao="cancelada", pago_ate=HOJE - timedelta(days=84))
    assert tarefas.limpeza()["encerradas"]["avisadas"] == 1
    assert sql(dono, "select exclusao_avisada_para from contas where id = :c", c=c) == [(HOJE + timedelta(days=7),)]
    # pago_ate há 82 dias: prevista daqui a 9 → ainda não
    b = conta_pronta(client, "bia@beta.com.br", empresa="Beta")
    _encerrar(dono, b["conta"]["id"], dias=300, situacao="cancelada", pago_ate=HOJE - timedelta(days=82))
    sql(dono, "delete from auditoria where conta_id is null")
    assert tarefas.limpeza()["encerradas"]["avisadas"] == 0


@pytest.mark.parametrize("caso", ["assinatura_ativa", "atrasada", "cortesia", "teste", "ativa", "sem_data",
                                  "primeiro_vencimento"])
def test_quem_nunca_entra(client, dono, ana, ligada, caso):
    c = ana["conta"]["id"]
    _encerrar(dono, c, dias=200)
    if caso == "assinatura_ativa":
        sql(dono, "insert into assinaturas (conta_id, asaas_id, ambiente, plano, valor, razao_social, documento, "
                  "email_cobranca, telefone, primeiro_vencimento) values (:c, 'sub_1', 'producao', 'profissional', "
                  "349, 'Alfa', '11222333000181', 'a@alfa.com.br', '5511999999999', :d)", c=c, d=HOJE)
    elif caso == "primeiro_vencimento":
        sql(dono, "update contas set primeiro_vencimento = :d where id = :c", c=c, d=HOJE)
    elif caso == "sem_data":
        sql(dono, "update contas set teste_ate = null where id = :c", c=c)
    else:
        sql(dono, "update contas set situacao = :s, atrasada_desde = :a where id = :c", c=c, s=caso,
            a=HOJE - timedelta(days=200) if caso == "atrasada" else None)
    _avisada(dono, c, HOJE - timedelta(days=1), dias_atras=30)
    r = tarefas.limpeza()["encerradas"]
    assert (r["avisadas"], r["excluidas"]) == (0, 0)
    assert r["sem_data"] == (1 if caso == "sem_data" else 0)
    assert r["em_atraso_90_dias"] == (1 if caso == "atrasada" else 0)
    assert _existe(dono, c)
    if caso != "assinatura_ativa":  # a regra pura só vê a linha da conta (assinatura de outro ambiente: só a rotina)
        assert client.get(f"{API}/eu", headers=ana["h"]).json()["conta"]["cobranca"]["exclusao_em"] is None


def test_exclusao_com_7_dias_nos_dois_relogios(client, dono, ana, ligada):
    c = ana["conta"]["id"]
    criar_contato(client, ana["h"], nome="Carla", email="carla@um.com.br")
    _encerrar(dono, c, dias=97)  # prevista = hoje − 7
    prevista = HOJE - timedelta(days=7)
    # avisada para amanhã (relógio das regras): ainda não
    _avisada(dono, c, HOJE + timedelta(days=1), dias_atras=8)
    assert tarefas.limpeza()["encerradas"]["excluidas"] == 0 and _existe(dono, c)
    # avisada para hoje, mas o aviso saiu há 6 dias pelo relógio do banco: ainda não
    sql(dono, "delete from auditoria where conta_id is null")
    _avisada(dono, c, HOJE, dias_atras=6)
    assert tarefas.limpeza()["encerradas"]["excluidas"] == 0 and _existe(dono, c)
    # 7 dias nos dois relógios: exclui
    sql(dono, "delete from auditoria where conta_id is null")
    _avisada(dono, c, HOJE, dias_atras=7)
    avisada_em = sql(dono, "select exclusao_avisada_em from contas where id = :c", c=c)[0][0]
    acessos = sql(dono, "select count(*) from registros_acesso where conta_id = :c", c=c)[0][0]
    assert acessos >= 2  # cadastro e login
    r = tarefas.limpeza()["encerradas"]
    assert (r["excluidas"], r["adiadas"]) == (1, 0)
    assert not _existe(dono, c)
    for t in ("usuarios", "contatos", "auditoria", "aceites_termos", "formularios", "emails_enviados",
              "config_envios", "perfil_permissoes"):
        assert sql(dono, f"select count(*) from {t} where conta_id = :c", c=c)[0][0] == 0, t
    # ficam os registros de acesso e o evento global, sem dado pessoal
    assert sql(dono, "select count(*) from registros_acesso where conta_id = :c", c=c)[0][0] == acessos
    ((detalhe, gravidade),) = sql(dono, "select detalhe, gravidade from auditoria where conta_id is null "
                                        "and evento = 'conta_excluida_automatica'")
    assert gravidade == "atencao"
    assert detalhe == {"conta_id": c, "situacao": "teste_expirado",
                       "encerrada_em": (HOJE - timedelta(days=97)).isoformat(),
                       "avisada_em": avisada_em.isoformat(), "exclusao_em": HOJE.isoformat(), "admins": 1}
    assert prevista < HOJE


def test_menos_de_100_dias_nunca(client, dono, ana, ligada):
    c = ana["conta"]["id"]
    _encerrar(dono, c, dias=97, criada_dias=99)
    _avisada(dono, c, HOJE, dias_atras=10)
    assert tarefas.limpeza()["encerradas"]["excluidas"] == 0 and _existe(dono, c)


def test_assinar_depois_cancela_e_novo_encerramento_avisa_de_novo(client, dono, ana, ligada):
    c = ana["conta"]["id"]
    _encerrar(dono, c, dias=97)
    _avisada(dono, c, HOJE, dias_atras=7)
    # assinou (a situação muda): nada é excluído e o aviso some
    sql(dono, "update contas set situacao = 'ativa', pago_ate = :p where id = :c", c=c, p=HOJE + timedelta(days=30))
    assert tarefas.limpeza()["encerradas"]["excluidas"] == 0 and _existe(dono, c)
    assert client.get(f"{API}/eu", headers=ana["h"]).json()["conta"]["cobranca"]["exclusao_em"] is None
    # cancelou e o período pago terminou de novo: novo encerramento, aviso de novo
    sql(dono, "delete from auditoria where conta_id is null")
    sql(dono, "update contas set situacao = 'cancelada', pago_ate = :p where id = :c", c=c,
        p=HOJE - timedelta(days=84))
    r = tarefas.limpeza()["encerradas"]
    assert (r["avisadas"], r["excluidas"]) == (1, 0)
    assert sql(dono, "select exclusao_avisada_para from contas where id = :c", c=c) == [(HOJE + timedelta(days=7),)]


def test_limite_de_20_por_dia(dono, ligada):
    _prontas(dono, 21)
    r = tarefas.limpeza()["encerradas"]
    assert (r["excluidas"], r["adiadas"]) == (20, 1)
    assert _contas(dono) == 1


def test_limite_e_do_dia_e_nao_da_rodada(dono, ligada, monkeypatch):
    """Uma rodada que caiu no meio (depois de 10 exclusões, sem o evento do dia) não libera outras 20 na próxima
    chamada; apagar à mão o evento `exclusao_automatica` de hoje faz a rotina rodar de novo, mas também não."""
    _prontas(dono, 25)
    apagar = exclusao.apagar_conta
    feitas: list[int] = []

    def cai_na_11a(s, conta_id):
        if len(feitas) == 10:
            raise SystemExit("o processo caiu")
        apagar(s, conta_id)
        feitas.append(conta_id)

    monkeypatch.setattr(exclusao, "apagar_conta", cai_na_11a)
    with pytest.raises(SystemExit):
        tarefas.limpeza()
    assert _contas(dono) == 15
    assert sql(dono, "select count(*) from auditoria where evento = 'exclusao_automatica'")[0][0] == 0
    monkeypatch.setattr(exclusao, "apagar_conta", apagar)
    r = tarefas.limpeza()["encerradas"]
    assert (r["excluidas"], r["adiadas"]) == (10, 5) and _contas(dono) == 5
    sql(dono, "delete from auditoria where conta_id is null and evento = 'exclusao_automatica'")
    r = tarefas.limpeza()["encerradas"]
    assert (r["excluidas"], r["adiadas"]) == (0, 5) and _contas(dono) == 5
    assert sql(dono, "select count(*) from auditoria where evento = 'conta_excluida_automatica'")[0][0] == 20


def test_limite_de_100_avisos_por_dia(dono, ligada):
    """Os avisos de hoje (eventos `exclusao_avisada` de qualquer conta) contam no limite de 100."""
    ((cortesia,),) = sql(dono, "insert into contas (nome, situacao) values ('Cortesia', 'cortesia') returning id")
    sql(dono, "insert into auditoria (conta_id, evento, gravidade, detalhe) "
              "select :c, 'exclusao_avisada', 'atencao', '{}' from generate_series(1, 99)", c=cortesia)
    _a_avisar(dono, 3)
    r = tarefas.limpeza()["encerradas"]
    assert (r["avisadas"], r["adiadas"]) == (1, 2)
    assert sql(dono, "select count(*) from contas where exclusao_avisada_para is not null")[0][0] == 1


def test_erro_numa_conta_nao_para_as_outras(dono, ligada, monkeypatch, caplog):
    """Um erro (permanente) num aviso ou numa exclusão: a conta fica para outro dia (`adiadas`), o log leva só o id e o
    tipo do erro, as outras seguem e a rodada termina (com o evento do dia)."""
    excluir = _prontas(dono, 3)
    avisar = _a_avisar(dono, 2)
    apagar, avisar_admins = exclusao.apagar_conta, exclusao.avisar_admins

    def apagar_com_erro(s, conta_id):
        if conta_id == excluir[0]:
            raise RuntimeError("Fulana de Tal <fulana@alfa.com.br>")
        apagar(s, conta_id)

    def avisar_com_erro(s, conta_id, *args):
        if conta_id == avisar[0]:
            raise ValueError("fulana@alfa.com.br")
        avisar_admins(s, conta_id, *args)

    monkeypatch.setattr(exclusao, "apagar_conta", apagar_com_erro)
    monkeypatch.setattr(exclusao, "avisar_admins", avisar_com_erro)
    with caplog.at_level(logging.INFO, logger="toqqi"):
        r = tarefas.limpeza()["encerradas"]
    assert (r["avisadas"], r["excluidas"], r["adiadas"]) == (1, 2, 2)
    assert [_existe(dono, i) for i in excluir] == [True, False, False]
    assert sql(dono, "select id from contas where exclusao_avisada_para is not null and id = any(:ids)",
               ids=avisar) == [(avisar[1],)]  # o aviso que falhou foi desfeito junto com a transação
    erros = [x.getMessage() for x in caplog.records if x.levelno >= logging.ERROR]
    assert any(f"conta {excluir[0]} " in m and "RuntimeError" in m for m in erros), erros
    assert any(f"conta {avisar[0]} " in m and "ValueError" in m for m in erros), erros
    assert "fulana" not in caplog.text.lower()  # nem a mensagem do erro
    assert tarefas.limpeza()["encerradas"] is None  # a rodada terminou: já rodou hoje


def test_simular_so_conta(client, dono, ana, monkeypatch):
    fixar_relogio(monkeypatch, AGORA)
    assert config().EXCLUSAO_AUTOMATICA == "simular"  # padrão do código
    c = ana["conta"]["id"]
    _encerrar(dono, c, dias=90)
    b = conta_pronta(client, "bia@beta.com.br", empresa="Beta")
    _encerrar(dono, b["conta"]["id"], dias=97)
    _avisada(dono, b["conta"]["id"], HOJE, dias_atras=7)
    caixa_memoria.clear()
    r = tarefas.limpeza()["encerradas"]
    assert r == {"modo": "simular", "avisadas": 1, "excluidas": 1, "adiadas": 0, "em_atraso_90_dias": 0,
                 "sem_data": 0}
    assert _existe(dono, b["conta"]["id"]) and not caixa_memoria
    assert sql(dono, "select exclusao_avisada_para from contas where id = :c", c=c) == [(None,)]
    assert sql(dono, "select detalhe from auditoria where conta_id is null and evento = 'exclusao_automatica'") == [
        (r,)]


def test_antes_das_9h_e_rodada_simultanea(dono, ana, monkeypatch):
    fixar_relogio(monkeypatch, datetime.combine(HOJE, time(8, 59), tzinfo=FUSO))
    _encerrar(dono, ana["conta"]["id"], dias=90)
    assert tarefas.limpeza()["encerradas"] is None
    fixar_relogio(monkeypatch, AGORA)
    with dono.connect() as conexao:
        conexao.execute(text("select pg_advisory_lock(hashtextextended('exclusao_automatica', 0))"))
        try:
            assert tarefas.limpeza()["encerradas"] is None
        finally:
            conexao.execute(text("select pg_advisory_unlock(hashtextextended('exclusao_automatica', 0))"))
            conexao.commit()
    assert sql(dono, "select count(*) from auditoria where evento = 'exclusao_automatica'")[0][0] == 0
    assert tarefas.limpeza()["encerradas"]["avisadas"] == 1


def test_asaas_fora_fica_para_amanha(client, dono, ana, ligada, monkeypatch, caplog):
    monkeypatch.setattr(config(), "ASAAS_API_KEY", CHAVE_ASAAS)  # sandbox; a rede está bloqueada nos testes
    c = ana["conta"]["id"]
    _encerrar(dono, c, dias=97, asaas_cliente_id="cus_000001", asaas_ambiente="sandbox")
    _avisada(dono, c, HOJE, dias_atras=7)
    with caplog.at_level(logging.INFO, logger="toqqi"):
        r = tarefas.limpeza()["encerradas"]
    assert (r["excluidas"], r["adiadas"]) == (0, 1) and _existe(dono, c)
    assert sql(dono, "select exclusao_avisada_para from contas where id = :c", c=c) == [(HOJE,)]  # o aviso segue
    texto = caplog.text
    assert "ana@alfa.com.br" not in texto and "Alfa" not in texto  # o log não leva dado pessoal
    assert str(c) in texto


def test_log_da_exclusao_sem_dado_pessoal(client, dono, ana, ligada, caplog):
    c = ana["conta"]["id"]
    _encerrar(dono, c, dias=97)
    _avisada(dono, c, HOJE, dias_atras=7)
    with caplog.at_level(logging.INFO, logger="toqqi"):
        assert tarefas.limpeza()["encerradas"]["excluidas"] == 1
    assert "excluída" in caplog.text and "ana@alfa.com.br" not in caplog.text and "Alfa" not in caplog.text


# ---- revisão: o aviso só vale entregue -----------------------------------------------------------------

@pytest.mark.parametrize("email", ["nenhum", "falhou", "antes_do_aviso", "outro_assunto"])
def test_aviso_que_nao_chegou_nao_vale(client, dono, ana, ligada, email):
    """Sem o e-mail do aviso aceito pelo provedor depois do aviso (nenhum, falhou, de um aviso anterior ou outro aviso
    aos administradores), com administrador ativo: não exclui, desfaz o aviso e a próxima rodada avisa de novo."""
    c = ana["conta"]["id"]
    _encerrar(dono, c, dias=97)  # prevista = hoje − 7
    _avisada(dono, c, HOJE, dias_atras=7, entregue=False)
    if email == "falhou":
        _email_do_aviso(dono, c, HOJE, situacao="falhou")
    elif email == "antes_do_aviso":
        _email_do_aviso(dono, c, HOJE, depois=False)
    elif email == "outro_assunto":
        _email_do_aviso(dono, c, HOJE, assunto="Um webhook da Toqqi foi desativado")
    r = tarefas.limpeza()["encerradas"]
    assert (r["excluidas"], r["adiadas"]) == (0, 1) and _existe(dono, c)
    assert sql(dono, "select exclusao_avisada_para, exclusao_avisada_em from contas where id = :c", c=c) == [
        (None, None)]
    assert client.get(f"{API}/eu", headers=ana["h"]).json()["conta"]["cobranca"]["exclusao_em"] is None
    sql(dono, "delete from auditoria where conta_id is null")
    r = tarefas.limpeza()["encerradas"]
    assert (r["avisadas"], r["excluidas"]) == (1, 0)
    assert sql(dono, "select exclusao_avisada_para from contas where id = :c", c=c) == [(HOJE + timedelta(days=7),)]


def test_aviso_com_falha_do_provedor_e_refeito(client, dono, ana, ligada, monkeypatch):
    c = ana["conta"]["id"]
    _encerrar(dono, c, dias=90)
    enviar = Memoria.enviar
    falhar_provedor(monkeypatch, erro_http(503))
    assert tarefas.limpeza()["encerradas"]["avisadas"] == 1
    assert sql(dono, "select situacao from emails_enviados where conta_id = :c and tipo = 'aviso'", c=c) == [
        ("falhou",)]
    # 7 dias depois, nos dois relógios: o aviso não chegou → não exclui e desfaz o aviso
    fixar_relogio(monkeypatch, sp(HOJE + timedelta(days=7), 10))
    sql(dono, "update contas set exclusao_avisada_em = exclusao_avisada_em - interval '7 days' where id = :c", c=c)
    sql(dono, "update emails_enviados set criado_em = criado_em - interval '7 days' where conta_id = :c", c=c)
    r = tarefas.limpeza()["encerradas"]
    assert (r["avisadas"], r["excluidas"], r["adiadas"]) == (0, 0, 1) and _existe(dono, c)
    # no dia seguinte, com o provedor de volta, avisa de novo: exclusão daqui a 7 dias
    monkeypatch.setattr(Memoria, "enviar", enviar)
    fixar_relogio(monkeypatch, sp(HOJE + timedelta(days=8), 10))
    r = tarefas.limpeza()["encerradas"]
    assert (r["avisadas"], r["excluidas"]) == (1, 0)
    assert sql(dono, "select exclusao_avisada_para from contas where id = :c", c=c) == [(HOJE + timedelta(days=15),)]
    assert [m.para for m in caixa_memoria if m.assunto.startswith("Sua conta no Toqqi será excluída")] == [
        "ana@alfa.com.br"]


def test_sem_administrador_ativo_exclui_depois_dos_7_dias(client, dono, ana, ligada):
    """Ninguém a avisar (o único administrador bloqueado; gestor não conta): exclui depois dos 7 dias sem o e-mail,
    com `admins: 0` no evento global."""
    c = ana["conta"]["id"]
    membro(client, ana["h"], "gil@alfa.com.br", perfil="gestor")
    sql(dono, "update usuarios set situacao = 'bloqueado' where conta_id = :c and perfil = 'admin'", c=c)
    _encerrar(dono, c, dias=97)
    _avisada(dono, c, HOJE, dias_atras=7, entregue=False)
    r = tarefas.limpeza()["encerradas"]
    assert (r["excluidas"], r["adiadas"]) == (1, 0) and not _existe(dono, c)
    ((detalhe,),) = sql(dono, "select detalhe from auditoria where conta_id is null "
                              "and evento = 'conta_excluida_automatica'")
    assert detalhe["admins"] == 0


# ---- revisão: assinaturas no Asaas que não dá para conferir --------------------------------------------

CHAVE_PRODUCAO = "$aact_prod_000MzkwODA2MWY2OGM3MWRlMDU2NWM3MzJlNzZmNGZhZGY6OjAwMDAwMDAwMDA6OiRhYWNoXzAwMDA="


@pytest.mark.parametrize("cliente,chave,excluida", [
    ("sandbox", None, False),  # sem chave: não dá para listar as assinaturas vivas
    ("producao", None, False),
    ("producao", "sandbox", False),  # chave de outro ambiente
    ("sandbox", "producao", True),  # as de sandbox são só de teste (a troca para produção já as cancela)
])
def test_asaas_sem_a_chave_do_ambiente_do_cliente(client, dono, ana, ligada, monkeypatch, caplog, cliente, chave,
                                                  excluida):
    if chave is not None:
        monkeypatch.setattr(config(), "ASAAS_API_KEY", CHAVE_ASAAS if chave == "sandbox" else CHAVE_PRODUCAO)
    c = ana["conta"]["id"]
    _encerrar(dono, c, dias=97, asaas_cliente_id="cus_000001", asaas_ambiente=cliente)
    _avisada(dono, c, HOJE, dias_atras=7)
    with caplog.at_level(logging.INFO, logger="toqqi"):
        r = tarefas.limpeza()["encerradas"]
    assert (r["excluidas"], r["adiadas"]) == ((1, 0) if excluida else (0, 1))
    assert _existe(dono, c) is not excluida
    if not excluida:
        assert sql(dono, "select exclusao_avisada_para from contas where id = :c", c=c) == [(HOJE,)]
        assert any(str(c) in x.getMessage() and x.levelno == logging.WARNING for x in caplog.records)
    assert "ana@alfa.com.br" not in caplog.text and "Alfa" not in caplog.text


# ---- revisão: EXCLUSAO_AUTOMATICA com outro valor e o log na linha de comando ----------------------------

def test_exclusao_automatica_com_outro_valor_simula(client, dono, ana, monkeypatch, caplog):
    monkeypatch.setenv("EXCLUSAO_AUTOMATICA", "desligada")
    assert Config().EXCLUSAO_AUTOMATICA == "desligada"  # a configuração aceita (antes, a API nem subia)
    fixar_relogio(monkeypatch, AGORA)
    monkeypatch.setattr(config(), "EXCLUSAO_AUTOMATICA", "desligada")
    c = ana["conta"]["id"]
    _encerrar(dono, c, dias=97)
    _avisada(dono, c, HOJE, dias_atras=7)
    b = conta_pronta(client, "bia@beta.com.br", empresa="Beta")
    _encerrar(dono, b["conta"]["id"], dias=90)
    caixa_memoria.clear()
    with caplog.at_level(logging.INFO, logger="toqqi"):
        r = tarefas.limpeza()["encerradas"]
    assert r == {"modo": "simular", "avisadas": 1, "excluidas": 1, "adiadas": 0, "em_atraso_90_dias": 0,
                 "sem_data": 0}
    assert _existe(dono, c) and not caixa_memoria
    avisos = [x for x in caplog.records if "desligada" in x.getMessage()]
    assert len(avisos) == 1 and avisos[0].levelno == logging.WARNING
    # `simular` não avisa nada no log
    caplog.clear()
    monkeypatch.setattr(config(), "EXCLUSAO_AUTOMATICA", "simular")
    sql(dono, "delete from auditoria where conta_id is null")
    with caplog.at_level(logging.INFO, logger="toqqi"):
        assert tarefas.limpeza()["encerradas"]["modo"] == "simular"
    assert not [x for x in caplog.records if x.levelno >= logging.WARNING]


def test_linha_de_comando_mostra_o_log_da_rotina(dono):
    """`python -m toqqi.tarefas limpeza` mostra os INFO da rotina (no formato da API), uma vez só cada linha."""
    codigo = textwrap.dedent("""
        import runpy, sys
        from datetime import datetime, time
        from toqqi.core import relogio
        dez = datetime.combine(relogio.hoje(), time(10), tzinfo=relogio.FUSO)
        relogio.agora = lambda: dez  # a rotina só roda a partir das 9h
        sys.argv = ["toqqi.tarefas", "limpeza"]
        runpy.run_module("toqqi.tarefas", run_name="__main__")
    """)
    r = subprocess.run([sys.executable, "-c", codigo], cwd=RAIZ_API, env=dict(os.environ), capture_output=True,
                       text=True, timeout=120)
    assert r.returncode == 0, r.stderr
    assert json.loads(r.stdout)["limpeza"]["encerradas"]["modo"] == "simular"
    linhas = [x for x in r.stderr.splitlines() if x.startswith("INFO:     toqqi - Exclusão automática (simular)")]
    assert len(linhas) == 2, r.stderr  # a contagem e o resumo, sem handler duplicado


def test_configurar_o_log_nao_duplica():
    from toqqi.core import logs

    logs.configurar()
    logs.configurar()
    toqqi = logging.getLogger("toqqi")
    (h,) = [h for h in toqqi.handlers if h.get_name() == logs.NOME]
    assert h.formatter._fmt == "%(levelname)s:     toqqi - %(message)s"
    assert toqqi.level == logging.INFO and toqqi.propagate is False

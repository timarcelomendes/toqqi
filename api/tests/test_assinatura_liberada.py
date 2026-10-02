"""Etapa 5a: envios, robô, lembretes, CSAT (disparo por evento) e IA respeitam a regra de "liberada" nas situações
novas: atrasada (até o fim do 7º dia), cancelada (até o fim do dia `pago_ate`) e teste de quem assinou (até o fim do
7º dia depois do primeiro vencimento: a carência da primeira fatura)."""
from datetime import timedelta

import pytest
from util import (
    API,
    conta_pronta,
    criar_contato,
    disparar,
    emails_para,
    evento,
    fixar_relogio,
    gerar_chave,
    ligar_envios,
    registrar_resposta,
    segunda,
    sql,
)

from toqqi import tarefas
from toqqi.modulos.assinatura.regras import MSG_AGUARDANDO, MSG_ATRASADA, MSG_CANCELADA, MSG_TESTE

SEGUNDA = segunda(11)  # na janela de envio
HOJE = SEGUNDA.date()

# (situação, colunas da conta, liberada, mensagem da pré-condição quando pausada)
CASOS = {
    "atrasada_7o_dia": ("atrasada", {"atrasada_desde": HOJE - timedelta(days=7)}, True, None),
    "atrasada_8o_dia": ("atrasada", {"atrasada_desde": HOJE - timedelta(days=8)}, False, MSG_ATRASADA),
    "cancelada_ultimo_dia": ("cancelada", {"pago_ate": HOJE, "teste_ate": SEGUNDA - timedelta(days=40)}, True, None),
    "cancelada_encerrada": ("cancelada", {"pago_ate": HOJE - timedelta(days=1), "teste_ate": SEGUNDA - timedelta(days=40)},
                            False, MSG_CANCELADA),
    "cancelada_com_teste_valendo": ("cancelada", {"pago_ate": HOJE - timedelta(days=1),  # o mais tarde dos dois
                                                  "teste_ate": SEGUNDA + timedelta(days=2)}, True, None),
    "teste_dia_do_vencimento": ("teste", {"teste_ate": SEGUNDA - timedelta(hours=1), "primeiro_vencimento": HOJE},
                                True, None),
    "teste_carencia_da_primeira_fatura": ("teste", {"teste_ate": SEGUNDA - timedelta(days=7),
                                                    "primeiro_vencimento": HOJE - timedelta(days=7)}, True, None),
    "teste_depois_da_carencia": ("teste", {"teste_ate": SEGUNDA - timedelta(days=8),
                                           "primeiro_vencimento": HOJE - timedelta(days=8)}, False, MSG_AGUARDANDO),
    "teste_expirado": ("teste_expirado", {}, False, MSG_TESTE),
}


def definir(dono, conta_id: int, situacao: str, colunas: dict) -> None:
    sets = "".join(f", {k} = :{k}" for k in colunas)
    sql(dono, f"update contas set situacao = :s{sets} where id = :c", s=situacao, c=conta_id, **colunas)


@pytest.mark.parametrize("caso", list(CASOS))
def test_envios_robo_csat_e_ia(client, dono, monkeypatch, caso):
    situacao, colunas, liberada, mensagem = CASOS[caso]
    fixar_relogio(monkeypatch, SEGUNDA)
    a = conta_pronta(client, "ana@alfa.com.br", empresa="Alfa")
    h, conta = a["h"], a["conta"]["id"]
    ligar_envios(client, h, envio_automatico=True)
    manual = criar_contato(client, h, email="manual@c.com.br")
    automatico = criar_contato(client, h, email="robo@c.com.br")
    sql(dono, "update contatos set proximo_envio = :d where id = :c", d=HOJE + timedelta(days=30), c=manual["id"])
    chave = gerar_chave(client, h)
    definir(dono, conta, situacao, colunas)

    item = client.get(f"{API}/envios/pre-condicoes", headers=h).json()["itens"][0]
    assert (item["chave"], item["ok"], item["mensagem"]) == ("assinatura", liberada, mensagem)
    # envio manual
    r = disparar(client, h, [manual["id"]])
    if liberada:
        assert r.status_code == 202 and emails_para("manual@c.com.br")
    else:
        assert r.status_code == 409 and r.json()["erro"] == {"codigo": "pre_condicao", "mensagem": mensagem,
                                                             "campos": {}}
    # robô
    assert tarefas.executar("robo")["robo"]["agendados"] == (1 if liberada else 0)
    assert bool(emails_para("robo@c.com.br")) is liberada
    # CSAT pelo disparo por evento (integração)
    r = evento(client, chave, "csat", email="entrega@c.com.br")
    assert r.status_code == (201 if liberada else 409), r.text
    # IA: a resposta só passa pela IA com a conta liberada
    rid = registrar_resposta(client, h, automatico["id"], 3, comentario="A entrega atrasou de novo").json()["id"]
    assert sql(dono, "select ia_situacao from respostas where id = :r", r=rid) == [
        ("analisada" if liberada else None,)]
    assert client.get(f"{API}/eu", headers=h).json()["conta"]["ia_ativa"] is liberada
    r = client.post(f"{API}/conta/ia/analisar-recentes", headers=h)
    assert r.status_code == (200 if liberada else 409)


@pytest.mark.parametrize("caso", ["atrasada_7o_dia", "atrasada_8o_dia", "cancelada_ultimo_dia",
                                  "cancelada_encerrada"])
def test_tarefa_da_ia_so_pega_contas_liberadas(client, dono, monkeypatch, caso):
    situacao, colunas, liberada, _ = CASOS[caso]
    fixar_relogio(monkeypatch, SEGUNDA)
    a = conta_pronta(client, "ana@alfa.com.br", empresa="Alfa")
    c = criar_contato(client, a["h"], email="p@c.com.br")
    sql(dono, "update contas set situacao = 'cortesia' where id = :c", c=a["conta"]["id"])
    rid = registrar_resposta(client, a["h"], c["id"], 3, comentario="Atrasou").json()["id"]
    sql(dono, "update respostas set ia_situacao = 'pendente', ia_temas = null where id = :r", r=rid)
    definir(dono, a["conta"]["id"], situacao, colunas)
    assert tarefas.executar("ia")["ia"]["analisadas"] == (1 if liberada else 0)
    assert sql(dono, "select ia_situacao from respostas where id = :r", r=rid) == [
        ("analisada" if liberada else "pendente",)]


def test_lembretes_respeitam_a_carencia_do_atraso(client, dono, monkeypatch):
    fixar_relogio(monkeypatch, SEGUNDA)
    a = conta_pronta(client, "ana@alfa.com.br", empresa="Alfa")
    h, conta = a["h"], a["conta"]["id"]
    sql(dono, "update contas set situacao = 'cortesia' where id = :c", c=conta)
    ligar_envios(client, h)
    c = criar_contato(client, h, email="l@c.com.br")
    assert disparar(client, h, [c["id"]]).json()["agendados"] == 1
    quinta = SEGUNDA + timedelta(days=3)  # 1º lembrete (3 dias), às 11:00
    fixar_relogio(monkeypatch, quinta)
    # fatura vencida há 8 dias: pausada, sem lembrete
    definir(dono, conta, "atrasada", {"atrasada_desde": quinta.date() - timedelta(days=8)})
    assert tarefas.executar("lembretes")["lembretes"]["contas"] == 0
    # no 7º dia ainda sai
    definir(dono, conta, "atrasada", {"atrasada_desde": quinta.date() - timedelta(days=7)})
    assert tarefas.executar("lembretes")["lembretes"] == {"contas": 1, "enviados": 1, "ignorados": 0}
    assert len(emails_para("l@c.com.br")) == 2


def test_resumo_semanal_respeita_a_liberacao(client, dono, monkeypatch):
    from util import FUSO

    from toqqi.modulos.relatorios import emails

    fixar_relogio(monkeypatch, segunda(9))
    a = conta_pronta(client, "ana@alfa.com.br", empresa="Alfa")
    conta = a["conta"]["id"]
    c = criar_contato(client, a["h"])
    sql(dono, "update contas set situacao = 'cortesia' where id = :c", c=conta)
    fixar_relogio(monkeypatch, segunda(9) - timedelta(days=3))
    registrar_resposta(client, a["h"], c["id"], 3, comentario="Atrasou")
    fixar_relogio(monkeypatch, segunda(9))
    fim_do_teste = segunda(9) - timedelta(days=40)
    definir(dono, conta, "cancelada", {"pago_ate": segunda(9).astimezone(FUSO).date() - timedelta(days=1),
                                       "teste_ate": fim_do_teste})
    assert emails.resumo() == {"contas": 0, "emails": 0}
    definir(dono, conta, "cancelada", {"pago_ate": segunda(9).astimezone(FUSO).date(), "teste_ate": fim_do_teste})
    assert emails.resumo() == {"contas": 1, "emails": 1}

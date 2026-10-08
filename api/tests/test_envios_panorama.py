"""Panorama de Envios (docs/api-envios-panorama.md): o estado do envio automático e a próxima rodada, a agenda dos
próximos 14 dias (pesquisas e lembretes; fim de semana e fim da janela empurram para o próximo dia em que sai) e
quantos responderam nos últimos 30 dias, por canal."""
from datetime import time, timedelta

import pytest
from util import (
    API,
    conta_pronta,
    criar_contato,
    data_iso,
    disparar,
    emails_para,
    fixar_relogio,
    form_padrao,
    ligar_envios,
    membro,
    segunda,
    sql,
    token_do_convite,
)

from toqqi.modelos import ConfigEnvios
from toqqi.modulos.envios.panorama import proxima_rodada


@pytest.fixture
def admin(client):
    return conta_pronta(client, "ana@alfa.com.br", empresa="Alfa Distribuidora")


def _panorama(client, h) -> dict:
    r = client.get(f"{API}/envios/panorama", headers=h)
    assert r.status_code == 200, r.text
    return r.json()


def _cfg(**campos) -> ConfigEnvios:
    c = ConfigEnvios(janela_inicio=time(8), janela_fim=time(18), so_dias_uteis=True, robo_rodou_em=None)
    for k, v in campos.items():
        setattr(c, k, v)
    return c


def test_proxima_rodada_janela_dias_uteis_e_6_horas():
    seg = segunda(10)
    assert proxima_rodada(_cfg(), seg) == seg
    assert proxima_rodada(_cfg(), seg.replace(hour=7)) == seg.replace(hour=8)
    assert proxima_rodada(_cfg(), seg.replace(hour=19)) == (seg + timedelta(days=1)).replace(hour=8)
    sexta = seg + timedelta(days=4)
    assert proxima_rodada(_cfg(), sexta.replace(hour=19)) == (seg + timedelta(days=7)).replace(hour=8)
    assert proxima_rodada(_cfg(so_dias_uteis=False), sexta.replace(hour=19)) == (sexta + timedelta(days=1)).replace(hour=8)
    sabado = seg + timedelta(days=5)
    assert proxima_rodada(_cfg(), sabado.replace(hour=11)) == (seg + timedelta(days=7)).replace(hour=8)
    # o robô espera 6 horas desde a última rodada
    assert proxima_rodada(_cfg(robo_rodou_em=seg.replace(hour=9)), seg) == seg.replace(hour=15)
    assert proxima_rodada(_cfg(robo_rodou_em=seg.replace(hour=13)), seg.replace(hour=14)) == \
        (seg + timedelta(days=1)).replace(hour=8)


def test_conta_sem_envios_e_estados(client, admin, dono):
    h = admin["h"]
    p = _panorama(client, h)
    assert p["automatico"]["estado"] == "desligado" and p["automatico"]["proxima_rodada"] is None
    assert {k: p["automatico"][k] for k in ("janela_inicio", "janela_fim", "so_dias_uteis", "intervalo_dias",
                                            "canal", "lembretes", "por_rodada")} == {
        "janela_inicio": "08:00", "janela_fim": "18:00", "so_dias_uteis": True, "intervalo_dias": 90,
        "canal": "email", "lembretes": 3, "por_rodada": 100}
    assert len(p["agenda"]) == 14 and all(d["pesquisas"] == 0 and d["lembretes"] == 0 for d in p["agenda"])
    assert p["respostas"]["enviadas"] == 0 and p["respostas"]["taxa"] is None
    assert p["respostas"]["horas_ate_metade"] is None and p["respostas"]["canais"] == []
    assert p["respostas"]["anterior"]["enviadas"] == 0
    ligar_envios(client, h)
    assert _panorama(client, h)["automatico"]["estado"] == "manual"
    ligar_envios(client, h, envio_automatico=True)
    p = _panorama(client, h)
    assert p["automatico"]["estado"] == "ligado" and p["automatico"]["proxima_rodada"] is not None
    # teste vencido: parado, sem próxima rodada
    sql(dono, "update contas set situacao = 'teste', teste_ate = now() - interval '1 day' where id = :c",
        c=admin["conta"]["id"])
    p = _panorama(client, h)
    assert p["automatico"]["estado"] == "parado" and p["automatico"]["proxima_rodada"] is None


def test_fila_e_agenda_com_fim_de_semana(client, admin, dono, monkeypatch):
    h = admin["h"]
    sql(dono, "update contas set situacao = 'cortesia' where id = :c", c=admin["conta"]["id"])
    ligar_envios(client, h, envio_automatico=True)
    seg = segunda(10)
    fixar_relogio(monkeypatch, seg)
    na_fila = [criar_contato(client, h, email=f"f{i}@c.com.br") for i in range(3)]
    criar_contato(client, h, nome="Sem canal", telefone="11987654321")  # só telefone, canal e-mail: fica fora
    inativo = criar_contato(client, h, email="inativo@c.com.br", ativo=False)
    quarta = criar_contato(client, h, email="quarta@c.com.br")
    sabado = criar_contato(client, h, email="sabado@c.com.br")
    longe = criar_contato(client, h, email="longe@c.com.br")
    for c, dias in ((quarta, 2), (sabado, 5), (longe, 20), (inativo, 1)):
        sql(dono, "update contatos set proximo_envio = :d where id = :c", d=seg.date() + timedelta(days=dias),
            c=c["id"])
    p = _panorama(client, h)
    a = p["automatico"]
    assert a["na_fila"] == len(na_fila) and a["proximo_contato"] is None
    assert a["fora_da_rodada"] == 1  # o "Sem canal" (só telefone, com o canal e-mail)
    assert a["proxima_rodada"] == seg.isoformat()
    dias = {d["dia"]: d for d in p["agenda"]}
    assert dias[data_iso(seg)]["pesquisas"] == 3
    assert dias[data_iso(seg + timedelta(days=2))]["pesquisas"] == 1
    # o do sábado sai na segunda seguinte; sábado e domingo sem envio
    assert dias[data_iso(seg + timedelta(days=5))] == {"dia": data_iso(seg + timedelta(days=5)), "pesquisas": 0,
                                                        "lembretes": 0, "sai": False}
    assert dias[data_iso(seg + timedelta(days=6))]["sai"] is False
    assert dias[data_iso(seg + timedelta(days=7))]["pesquisas"] == 1
    assert sum(d["pesquisas"] for d in p["agenda"]) == 5  # o de 20 dias e o inativo ficam fora
    # todos os dias da semana com "só dias úteis" desligado
    ligar_envios(client, h, so_dias_uteis=False)
    dias = {d["dia"]: d for d in _panorama(client, h)["agenda"]}
    assert dias[data_iso(seg + timedelta(days=5))]["pesquisas"] == 1 and dias[data_iso(seg + timedelta(days=5))]["sai"]
    # depois da janela: o de hoje vai para amanhã e a próxima rodada também
    fixar_relogio(monkeypatch, seg.replace(hour=19))
    p = _panorama(client, h)
    dias = {d["dia"]: d for d in p["agenda"]}
    assert dias[data_iso(seg)] == {"dia": data_iso(seg), "pesquisas": 0, "lembretes": 0, "sai": False}
    assert dias[data_iso(seg + timedelta(days=1))]["pesquisas"] == 3
    assert p["automatico"]["proxima_rodada"] == (seg + timedelta(days=1)).replace(hour=8).isoformat()


def test_fila_vazia_diz_quando_entra_o_proximo(client, admin, dono, monkeypatch):
    h = admin["h"]
    ligar_envios(client, h, envio_automatico=True)
    seg = segunda(10)
    fixar_relogio(monkeypatch, seg)
    c = criar_contato(client, h, email="depois@c.com.br")
    sql(dono, "update contatos set proximo_envio = :d where id = :c", d=seg.date() + timedelta(days=40), c=c["id"])
    a = _panorama(client, h)["automatico"]
    assert a["na_fila"] == 0 and a["fora_da_rodada"] == 0 and a["proximo_contato"] == data_iso(seg + timedelta(days=40))


def test_lembretes_na_agenda(client, admin, dono, monkeypatch):
    h = admin["h"]
    sql(dono, "update contas set situacao = 'cortesia' where id = :c", c=admin["conta"]["id"])
    ligar_envios(client, h)  # lembretes nos dias 3, 7 e 15
    seg = segunda(10)
    fixar_relogio(monkeypatch, seg)
    c = criar_contato(client, h, email="lembrar@c.com.br")
    disparar(client, h, [c["id"]])
    sql(dono, "update convites set criado_em = :q where contato_id = :c", q=seg, c=c["id"])
    dias = {d["dia"]: d for d in _panorama(client, h)["agenda"]}
    assert dias[data_iso(seg + timedelta(days=3))]["lembretes"] == 1  # quinta
    assert sum(d["lembretes"] for d in dias.values()) == 1  # só o próximo lembrete de cada convite
    # lembrete atrasado (devido no sábado com só dias úteis): na segunda
    sql(dono, "update convites set criado_em = :q where contato_id = :c", q=seg + timedelta(days=2), c=c["id"])
    dias = {d["dia"]: d for d in _panorama(client, h)["agenda"]}
    assert dias[data_iso(seg + timedelta(days=7))]["lembretes"] == 1
    # sem lembretes na configuração: nada
    ligar_envios(client, h, lembretes=0)
    assert sum(d["lembretes"] for d in _panorama(client, h)["agenda"]) == 0


def test_respostas_dos_ultimos_30_dias(client, admin, dono):
    h = admin["h"]
    sql(dono, "update contas set situacao = 'cortesia' where id = :c", c=admin["conta"]["id"])
    ligar_envios(client, h)
    nps = form_padrao(client, h)
    contatos = [criar_contato(client, h, email=f"r{i}@c.com.br") for i in range(5)]
    assert disparar(client, h, [c["id"] for c in contatos]).status_code == 202
    for i in (0, 1):
        token = token_do_convite(emails_para(f"r{i}@c.com.br")[0])
        r = client.post(f"{API}/publico/convites/{token}/responder", json={"respostas": {nps["perguntas"][0]["id"]: 9}})
        assert r.status_code == 201
    sql(dono, "update convites set respondido_em = criado_em + interval '6 hours' where contato_id = :c",
        c=contatos[0]["id"])
    sql(dono, "update convites set respondido_em = criado_em + interval '30 hours' where contato_id = :c",
        c=contatos[1]["id"])
    # um não saiu (erro): não conta; um é de 40 dias atrás (período anterior), respondido
    sql(dono, "update envios set situacao = 'erro', enviado_em = null where contato_id = :c and tipo = 'convite'",
        c=contatos[2]["id"])
    sql(dono, "update convites set criado_em = now() - interval '40 days', respondido_em = now() - interval '39 days'"
              " where contato_id = :c", c=contatos[3]["id"])
    r = _panorama(client, h)["respostas"]
    assert {k: r[k] for k in ("enviadas", "respondidas", "taxa", "horas_ate_metade")} == {
        "enviadas": 3, "respondidas": 2, "taxa": 67, "horas_ate_metade": 18.0}
    assert r["canais"] == [{"canal": "email", "enviadas": 3, "respondidas": 2, "taxa": 67}]
    assert {k: r["anterior"][k] for k in ("enviadas", "respondidas", "taxa")} == {
        "enviadas": 1, "respondidas": 1, "taxa": 100}


def test_permissao_e_outra_conta(client, admin):
    h = admin["h"]
    ligar_envios(client, h)
    criar_contato(client, h, email="x@c.com.br")
    consulta = membro(client, h, "caio@alfa.com.br", perfil="consulta")["h"]
    assert client.get(f"{API}/envios/panorama", headers=consulta).status_code == 200  # consulta vê os envios
    outra = conta_pronta(client, "bia@beta.com.br", empresa="Beta")
    p = _panorama(client, outra["h"])
    assert p["automatico"]["estado"] == "desligado" and p["automatico"]["na_fila"] == 0

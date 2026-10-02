"""Etapa 3a: robô, lembretes, agradecimento automático, pendentes e tarefas (CLI e rota interna)."""
import pytest
from util import (
    API,
    conta_pronta,
    criar_contato,
    disparar,
    emails_para,
    encher_contatos,
    erro_http,
    falhar_provedor,
    fixar_relogio,
    form_padrao,
    historico,
    ligar_envios,
    membro,
    responder_link,
    segunda,
    sql,
    token_do_convite,
)

from toqqi import tarefas
from toqqi.core.config import config
from toqqi.core.email import caixa_memoria


@pytest.fixture
def admin(client, dono):
    a = conta_pronta(client, "ana@alfa.com.br", empresa="Alfa")
    # cortesia: os testes andam semanas no relógio sem esbarrar no fim do teste grátis
    sql(dono, "update contas set situacao = 'cortesia' where id = :c", c=a["conta"]["id"])
    return a


def robo(monkeypatch, momento) -> dict:
    fixar_relogio(monkeypatch, momento)
    return tarefas.executar("robo")["robo"]


def lembretes(monkeypatch, momento) -> dict:
    fixar_relogio(monkeypatch, momento)
    return tarefas.executar("lembretes")["lembretes"]


# ---- robô -------------------------------------------------------------------

def test_robo_elegibilidade_e_intervalo_de_6h(client, admin, dono, monkeypatch):
    h = admin["h"]
    ligar_envios(client, h, envio_automatico=True)
    ok = [criar_contato(client, h, email=f"ok{i}@c.com.br") for i in range(3)]
    criar_contato(client, h, email=None, telefone="11911112222")                     # sem e-mail
    falhou = criar_contato(client, h, email="falhou@c.com.br")
    descanso = criar_contato(client, h, email="descanso@c.com.br")
    criar_contato(client, h, email="inativo@c.com.br", ativo=False)                  # fora da fila
    criar_contato(client, h, email="fora@c.com.br", recebe_pesquisas=False)          # saiu da lista
    criar_contato(client, h, email="desc@c.com.br")
    client.post(f"{API}/envios/descadastros", headers=h, json={"email": "desc@c.com.br"})
    futuro = criar_contato(client, h, email="futuro@c.com.br")
    sql(dono, "update contatos set falhas = 3 where id = :c", c=falhou["id"])
    sql(dono, "update contatos set ultimo_envio = now() - interval '5 days' where id = :c", c=descanso["id"])
    sql(dono, "update contatos set proximo_envio = current_date + 30 where id = :c", c=futuro["id"])

    r = robo(monkeypatch, segunda(9))
    assert r == {"contas": 1, "agendados": 3, "ignorados": 3}
    for c in ok:
        assert emails_para(c["email"])
    assert not emails_para("desc@c.com.br") and not emails_para("falhou@c.com.br")
    assert {e["origem"] for e in historico(client, h)} == {"automatico"}
    # 6 h entre rodadas
    assert robo(monkeypatch, segunda(14, 59))["contas"] == 0
    assert robo(monkeypatch, segunda(15, 1))["contas"] == 1


def test_robo_janela_dias_uteis_e_chaves(client, admin, monkeypatch):
    h = admin["h"]
    criar_contato(client, h, email="x@c.com.br")
    ligar_envios(client, h)
    assert robo(monkeypatch, segunda(11))["contas"] == 0          # envio automático desligado
    ligar_envios(client, h, envio_automatico=True, envios_ativos=False)
    assert robo(monkeypatch, segunda(11))["contas"] == 0          # chave geral desligada
    ligar_envios(client, h, envio_automatico=True)
    assert robo(monkeypatch, segunda(7, 59))["contas"] == 0       # antes da janela
    assert robo(monkeypatch, segunda(18))["contas"] == 0          # fim da janela
    assert robo(monkeypatch, segunda(11, mais_dias=5))["contas"] == 0  # sábado
    ligar_envios(client, h, so_dias_uteis=False)
    assert robo(monkeypatch, segunda(11, mais_dias=5))["agendados"] == 1


def test_robo_no_maximo_100_mais_atrasados_primeiro(client, admin, dono, monkeypatch):
    h = admin["h"]
    ligar_envios(client, h, envio_automatico=True)
    encher_contatos(dono, admin["conta"]["id"], 120)
    sql(dono, "update contatos set proximo_envio = current_date - 1 where id <= 100")
    sql(dono, "update contatos set proximo_envio = current_date - 50 where id > 115")
    r = robo(monkeypatch, segunda(9))
    assert r["agendados"] == 100 and len(caixa_memoria) >= 100
    enviados = {m.para for m in caixa_memoria}
    assert all(f"lote{i}@c{admin['conta']['id']}.com.br" in enviados for i in range(116, 121))  # atrasados
    assert all(f"lote{i}@c{admin['conta']['id']}.com.br" in enviados for i in range(101, 116))  # nunca enviados


def test_robo_para_depois_de_3_falhas(client, admin, dono, monkeypatch):
    h = admin["h"]
    ligar_envios(client, h, envio_automatico=True, descanso_dias=0)
    c = criar_contato(client, h, email="ruim@c.com.br")
    falhar_provedor(monkeypatch, erro_http(422))
    for dia in range(3):
        assert robo(monkeypatch, segunda(8, mais_dias=dia))["agendados"] == 1, dia
    assert sql(dono, "select falhas from contatos where id = :c", c=c["id"])[0][0] == 3
    assert robo(monkeypatch, segunda(8, mais_dias=3)) == {"contas": 1, "agendados": 0, "ignorados": 1}
    # envio manual que dá certo zera as falhas e volta o contato ao normal
    monkeypatch.undo()
    fixar_relogio(monkeypatch, segunda(9, mais_dias=3))
    assert disparar(client, h, [c["id"]]).json()["agendados"] == 1
    assert sql(dono, "select falhas from contatos where id = :c", c=c["id"])[0][0] == 0


def test_robo_executar_pela_tela(client, admin, monkeypatch):
    h = admin["h"]
    criar_contato(client, h, email="x@c.com.br")
    ligar_envios(client, h)
    r = client.post(f"{API}/envios/robo/executar", headers=h)
    assert r.status_code == 409 and "automático está desligado" in r.json()["erro"]["mensagem"]
    ligar_envios(client, h, envio_automatico=True)
    fixar_relogio(monkeypatch, segunda(22))  # fora da janela: a execução manual ignora
    r = client.post(f"{API}/envios/robo/executar", headers=h)
    assert r.status_code == 200 and r.json() == {"agendados": 1, "ignorados": 0}
    assert emails_para("x@c.com.br")
    g = membro(client, h, "gil@alfa.com.br", "gestor")
    assert client.post(f"{API}/envios/robo/executar", headers=g["h"]).status_code == 403
    assert client.post(f"{API}/envios/lembretes/executar", headers=g["h"]).status_code == 403


# ---- lembretes --------------------------------------------------------------

def _convite(client, h, monkeypatch, email="l@c.com.br", momento=None):
    c = criar_contato(client, h, email=email)
    fixar_relogio(monkeypatch, momento or segunda(9))
    assert disparar(client, h, [c["id"]]).json()["agendados"] == 1
    return c, emails_para(email)[-1]


def test_lembretes_3_7_15_mesmo_link(client, admin, monkeypatch):
    h = admin["h"]
    ligar_envios(client, h)
    c, convite = _convite(client, h, monkeypatch)
    token = token_do_convite(convite)
    fixar_relogio(monkeypatch, segunda(11, mais_dias=2))
    assert client.get(f"{API}/envios/lembretes/previa", headers=h).json() == {"hoje": 0, "amanha": 1}
    assert lembretes(monkeypatch, segunda(11, mais_dias=2))["enviados"] == 0
    assert lembretes(monkeypatch, segunda(9, mais_dias=3))["contas"] == 0          # antes das 10:00
    fixar_relogio(monkeypatch, segunda(10, mais_dias=3))
    assert client.get(f"{API}/envios/lembretes/previa", headers=h).json() == {"hoje": 1, "amanha": 0}
    assert lembretes(monkeypatch, segunda(10, mais_dias=3)) == {"contas": 1, "enviados": 1, "ignorados": 0}
    m = emails_para("l@c.com.br")[-1]
    assert m.assunto == "Lembrete: Alfa quer saber a sua opinião"
    assert token_do_convite(m) == token and "Ainda dá tempo" in m.texto
    assert m.cabecalhos["List-Unsubscribe-Post"] == "List-Unsubscribe=One-Click"
    # uma vez por dia
    assert lembretes(monkeypatch, segunda(15, mais_dias=3))["contas"] == 0
    assert client.post(f"{API}/envios/lembretes/executar", headers=h).json() == {"enviados": 0, "ignorados": 0}
    for dia, n in [(7, 2), (15, 3)]:
        assert lembretes(monkeypatch, segunda(11, mais_dias=dia))["enviados"] == 1
        assert historico(client, h, tipo="lembrete")[0]["origem"] == "lembrete"
    assert lembretes(monkeypatch, segunda(11, mais_dias=21))["enviados"] == 0          # já foram os 3
    assert len(emails_para("l@c.com.br")) == 4
    item = client.get(f"{API}/envios/contatos", headers=h).json()["itens"][0]
    assert item["lembretes_enviados"] == 3 and item["proximo_lembrete"] is None


def test_lembrete_atrasado_sai_um_por_dia(client, admin, monkeypatch):
    h = admin["h"]
    ligar_envios(client, h)
    _convite(client, h, monkeypatch)
    assert lembretes(monkeypatch, segunda(11, mais_dias=8))["enviados"] == 1   # 1º (devido desde o dia 3)
    r = client.post(f"{API}/envios/lembretes/executar", headers=h).json()
    assert r["enviados"] == 0                                                      # 2º só amanhã
    assert lembretes(monkeypatch, segunda(11, mais_dias=9))["enviados"] == 1


@pytest.mark.parametrize("caso", ["respondeu", "inativo", "descadastrado", "convite_mais_novo", "desligado",
                                  "velho", "sem_lembretes"])
def test_lembretes_param_quando(client, admin, monkeypatch, dono, caso):
    h = admin["h"]
    ligar_envios(client, h, descanso_dias=0)
    c, convite = _convite(client, h, monkeypatch)
    esperado_ignorados = 0
    if caso == "respondeu":
        nps = form_padrao(client, h)
        client.post(f"{API}/publico/convites/{token_do_convite(convite)}/responder",
                    json={"respostas": {nps["perguntas"][0]["id"]: 10}})
    elif caso == "inativo":
        client.patch(f"{API}/contatos/{c['id']}", headers=h, json={"ativo": False})
        esperado_ignorados = 1
    elif caso == "descadastrado":
        client.post(f"{API}/envios/descadastros", headers=h, json={"email": "l@c.com.br"})
        esperado_ignorados = 1
    elif caso == "convite_mais_novo":
        fixar_relogio(monkeypatch, segunda(10, mais_dias=1))
        disparar(client, h, [c["id"]])
    elif caso == "desligado":
        ligar_envios(client, h, envios_ativos=False)
    elif caso == "velho":
        sql(dono, "update convites set criado_em = criado_em - interval '30 days'")
    elif caso == "sem_lembretes":
        ligar_envios(client, h, lembretes=0)
    antes = len(caixa_memoria)
    r = lembretes(monkeypatch, segunda(11, mais_dias=3))
    assert r.get("enviados", 0) == 0 and r.get("ignorados", 0) == esperado_ignorados
    assert len([m for m in caixa_memoria[antes:] if m.assunto.startswith("Lembrete")]) == 0


def test_whatsapp_nao_recebe_lembrete(client, admin, monkeypatch):
    h = admin["h"]
    ligar_envios(client, h)
    c = criar_contato(client, h, email="w@c.com.br", telefone="11911112222")
    fixar_relogio(monkeypatch, segunda(9))
    client.post(f"{API}/contatos/{c['id']}/whatsapp", headers=h, json={})
    assert lembretes(monkeypatch, segunda(11, mais_dias=3))["enviados"] == 0


# ---- agradecimento ----------------------------------------------------------

@pytest.mark.parametrize("nota,trecho", [(10, "Muito obrigado pela sua nota 10"), (7, "Obrigado pela sua resposta"),
                                         (2, "Obrigado por ser sincero")])
def test_agradecimento_por_grupo(client, admin, nota, trecho):
    h = admin["h"]
    ligar_envios(client, h)
    c = criar_contato(client, h, nome="Paula Lima", email="paula@c.com.br")
    disparar(client, h, [c["id"]])
    nps = form_padrao(client, h)
    token = token_do_convite(emails_para("paula@c.com.br")[0])
    r = client.post(f"{API}/publico/convites/{token}/responder", json={"respostas": {nps["perguntas"][0]["id"]: nota}})
    assert r.status_code == 201
    m = emails_para("paula@c.com.br")[-1]
    assert m.assunto == "Alfa agradece a sua resposta"
    assert trecho in m.texto and m.texto.startswith("Olá, Paula!")
    assert "Não quero mais receber pesquisas" in m.html and m.cabecalhos["List-Unsubscribe"]
    envio = historico(client, h, tipo="agradecimento")[0]
    assert (envio["origem"], envio["situacao"]) == ("resposta", "enviado")


def test_agradecimento_csat_e_link_publico(client, admin):
    h = admin["h"]
    ligar_envios(client, h)
    csat = form_padrao(client, h, "csat")
    ligar_envios(client, h, agradecimento={"promotor": "Valeu, {nome}! Nota {nota}.", "neutro": "N", "detrator": "D"})
    criar_contato(client, h, nome="Rui", email="rui@c.com.br")
    # link público sem identificar contato: nada
    r = responder_link(client, csat["codigo_publico"], {csat["perguntas"][0]["id"]: 5})
    assert r.status_code == 201 and historico(client, h, tipo="agradecimento") == []
    # formulário que identifica o contato pelo e-mail: satisfeito → texto de promotor
    form = client.post(f"{API}/formularios", headers=h, json={"nome": "Com e-mail", "perguntas": [
        {"tipo": "csat", "titulo": "Nota?", "obrigatoria": True},
        {"tipo": "texto_curto", "titulo": "E-mail", "formato": "email"}]}).json()
    p = [x["id"] for x in form["perguntas"]]
    responder_link(client, form["codigo_publico"], {p[0]: 4, p[1]: "rui@c.com.br"})
    assert emails_para("rui@c.com.br")[-1].texto.startswith("Valeu, Rui! Nota 4.")


@pytest.mark.parametrize("ajuste", ["agradecimento_ativo", "envios_ativos", "descadastrado"])
def test_sem_agradecimento(client, admin, ajuste):
    h = admin["h"]
    ligar_envios(client, h)
    c = criar_contato(client, h, email="s@c.com.br")
    disparar(client, h, [c["id"]])
    if ajuste == "descadastrado":
        client.post(f"{API}/envios/descadastros", headers=h, json={"email": "s@c.com.br"})
    else:
        client.put(f"{API}/envios/configuracao", headers=h, json={ajuste: False})
    nps = form_padrao(client, h)
    token = token_do_convite(emails_para("s@c.com.br")[0])
    client.post(f"{API}/publico/convites/{token}/responder", json={"respostas": {nps["perguntas"][0]["id"]: 9}})
    assert len(emails_para("s@c.com.br")) == 1
    assert historico(client, h, tipo="agradecimento") == []


# ---- pendentes e tarefas ----------------------------------------------------

def test_pendentes_retomados(client, admin, dono):
    h = admin["h"]
    ligar_envios(client, h)
    c = criar_contato(client, h, email="p@c.com.br")
    sql(dono, """insert into convites (conta_id, token_hash, token_semente, formulario_id, contato_id, canal)
                 values (:a, 'h1', 'semente', (select id from formularios where padrao_nps and conta_id = :a), :c, 'email')""",
        a=admin["conta"]["id"], c=c["id"])
    sql(dono, """insert into envios (conta_id, contato_id, convite_id, canal, tipo, origem, para, criado_em)
                 select :a, :c, id, 'email', 'convite', 'manual', 'p@c.com.br', now() - interval '11 minutes'
                   from convites""", a=admin["conta"]["id"], c=c["id"])
    sql(dono, """insert into envios (conta_id, contato_id, canal, tipo, origem, para)
                 values (:a, :c, 'email', 'convite', 'manual', 'p@c.com.br')""", a=admin["conta"]["id"], c=c["id"])
    assert tarefas.executar("pendentes") == {"pendentes": 1}  # o recente fica para o processo que o criou
    situacoes = dict(sql(dono, "select id, situacao from envios order by id"))
    assert list(situacoes.values()) == ["enviado", "pendente"]
    assert emails_para("p@c.com.br")


def test_cli(capsys):
    assert tarefas.main(["xyz"]) == 2
    assert tarefas.main(["pendentes"]) == 0
    assert capsys.readouterr().out.strip() == '{"pendentes": 0}'


def test_rota_interna_de_tarefas(client, monkeypatch):
    url = f"{API}/interno/tarefas"
    monkeypatch.setattr(config(), "TAREFAS_TOKEN", "")
    assert client.post(url, headers={"X-Tarefas-Token": "qualquer"}).status_code == 404
    monkeypatch.setattr(config(), "TAREFAS_TOKEN", "segredo-das-tarefas")
    assert client.post(url).status_code == 401
    r = client.post(url, headers={"X-Tarefas-Token": "errado"})
    assert r.status_code == 401 and r.json()["erro"]["codigo"] == "token_invalido"
    r = client.post(url, headers={"X-Tarefas-Token": "segredo-das-tarefas"})
    assert r.status_code == 200
    assert list(r.json())[0] == "assinaturas"  # roda primeiro: a liberação vale antes dos envios
    assert r.json() == {"assinaturas": {"testes_expirados": 0, "contas_de_outro_ambiente": 0, "remocoes_no_asaas": 0,
                                        "eventos_reprocessados": 0, "contas_conferidas": 0},
                        "pendentes": 0, "robo": {"contas": 0, "agendados": 0, "ignorados": 0},
                        "lembretes": {"contas": 0, "enviados": 0, "ignorados": 0},
                        "webhooks": {"entregues": 0, "falharam": 0},
                        "ia": {"analisadas": 0, "falharam": 0, "limite": 0,
                               "passos": {"prontas": 0, "falharam": 0, "limite": 0}},  # etapa 5d
                        "picos": {"picos": 0, "emails": 0},
                        "resumo": {"contas": 0, "emails": 0}}

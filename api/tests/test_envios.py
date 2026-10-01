"""Etapa 3a: configurações, pré-condições, disparo manual, fila, histórico, tentar de novo e WhatsApp."""
import re
from datetime import datetime, timedelta
from urllib.parse import unquote

import httpx
import pytest
from util import (
    API,
    FUSO,
    conta_pronta,
    criar_contato,
    criar_empresa,
    criar_form,
    data_iso,
    disparar,
    emails_para,
    erro_http,
    falhar_provedor,
    fila,
    fixar_relogio,
    form_padrao,
    historico,
    ligar_envios,
    membro,
    segunda,
    sql,
    token_do_convite,
)

from toqqi.core.config import config


@pytest.fixture
def admin(client):
    return conta_pronta(client, "ana@alfa.com.br", empresa="Alfa Distribuidora")


def _eventos(client, h) -> list[dict]:
    return client.get(f"{API}/auditoria", headers=h).json()["itens"]


# ---- pré-condições ----------------------------------------------------------

def test_pre_condicoes_e_409(client, admin, dono, monkeypatch):
    h = admin["h"]
    r = client.get(f"{API}/envios/pre-condicoes", headers=h)
    assert r.status_code == 200
    d = r.json()
    assert d["pronto"] is False
    assert [i["chave"] for i in d["itens"]] == ["assinatura", "provedor", "formulario", "envios_ativos"]
    assert [i["ok"] for i in d["itens"]] == [True, True, True, False]
    faltando = d["itens"][3]
    assert faltando["mensagem"] == "Os envios estão desligados. Ligue em Configurações de envio."
    assert faltando["acao"]["rotulo"] == "Configurações de envio"
    c = criar_contato(client, h)
    r = disparar(client, h, [c["id"]])
    assert r.status_code == 409
    assert r.json()["erro"] == {"codigo": "pre_condicao", "campos": {},
                                "mensagem": "Os envios estão desligados. Ligue em Configurações de envio."}

    ligar_envios(client, h)
    assert client.get(f"{API}/envios/pre-condicoes", headers=h).json()["pronto"] is True

    # provedor console não vale em produção
    monkeypatch.setattr(config(), "EMAIL_PROVIDER", "console")
    monkeypatch.setattr(config(), "AMBIENTE", "producao")
    r = disparar(client, h, [c["id"]])
    assert r.status_code == 409
    assert r.json()["erro"]["mensagem"] == "O envio de e-mails ainda não foi configurado na plataforma."
    monkeypatch.setattr(config(), "AMBIENTE", "desenvolvimento")
    assert client.get(f"{API}/envios/pre-condicoes", headers=h).json()["pronto"] is True
    monkeypatch.setattr(config(), "EMAIL_PROVIDER", "zeptomail")
    monkeypatch.setattr(config(), "ZEPTOMAIL_TOKEN", "")
    assert client.get(f"{API}/envios/pre-condicoes", headers=h).json()["itens"][1]["ok"] is False
    monkeypatch.setattr(config(), "EMAIL_PROVIDER", "memory")

    # formulário desativado
    nps = form_padrao(client, h)
    sql(dono, "update formularios set ativo = false where id = :f", f=nps["id"])
    r = disparar(client, h, [c["id"]])
    assert r.json()["erro"]["mensagem"] == "Escolha o formulário usado nos convites."
    sql(dono, "update formularios set ativo = true where id = :f", f=nps["id"])

    # teste vencido vem primeiro
    sql(dono, "update contas set situacao = 'teste', teste_ate = now() - interval '1 day' where id = :c",
        c=admin["conta"]["id"])
    d = client.get(f"{API}/envios/pre-condicoes", headers=h).json()
    assert d["itens"][0] == {"chave": "assinatura", "ok": False,
                             "mensagem": "O período de teste acabou. Assine um plano para voltar a enviar.",
                             "acao": {"rotulo": "Assinatura", "rota": "/assinatura"}}
    r = disparar(client, h, [c["id"]])
    assert r.status_code == 409 and "período de teste acabou" in r.json()["erro"]["mensagem"]
    sql(dono, "update contas set situacao = 'ativa' where id = :c", c=admin["conta"]["id"])
    assert disparar(client, h, [c["id"]]).status_code == 202


# ---- configuração -----------------------------------------------------------

def test_configuracao_padroes(client, admin):
    h = admin["h"]
    cfg = client.get(f"{API}/envios/configuracao", headers=h).json()
    nps = form_padrao(client, h)
    assert cfg["formulario_id"] == nps["id"]
    assert (cfg["envios_ativos"], cfg["envio_automatico"]) == (False, False)
    assert (cfg["intervalo_dias"], cfg["descanso_dias"], cfg["lembretes"]) == (90, 30, 3)
    assert cfg["dias_lembretes"] == [3, 7, 15]
    assert (cfg["janela_inicio"], cfg["janela_fim"], cfg["so_dias_uteis"]) == ("08:00", "18:00", True)
    assert cfg["responder_para"] is None and cfg["remetente_nome"] is None
    assert cfg["assunto_convite"] == "{empresa} quer saber a sua opinião"
    assert cfg["texto_convite"].startswith("Olá, {nome}!\n\n")
    assert "{link}" in cfg["texto_whatsapp"]
    assert cfg["agradecimento_ativo"] is True
    assert set(cfg["agradecimento"]) == {"promotor", "neutro", "detrator"}


@pytest.mark.parametrize("corpo,campo", [
    ({"intervalo_dias": 10}, "intervalo_dias"),
    ({"intervalo_dias": 400}, "intervalo_dias"),
    ({"descanso_dias": 181}, "descanso_dias"),
    ({"lembretes": 4}, "lembretes"),
    ({"dias_lembretes": [7, 3, 15]}, "dias_lembretes"),
    ({"dias_lembretes": [3, 7]}, "dias_lembretes"),
    ({"dias_lembretes": [3, 7, 31]}, "dias_lembretes.2"),
    ({"janela_fim": "07:00"}, "janela_fim"),
    ({"janela_inicio": "8h"}, "janela_inicio"),
    ({"texto_whatsapp": "Olá, {nome}!"}, "texto_whatsapp"),
    ({"assunto_convite": "x" * 151}, "assunto_convite"),
    ({"assunto_convite": "linha 1\nlinha 2"}, "assunto_convite"),
    ({"texto_convite": "x" * 2001}, "texto_convite"),
    ({"formulario_id": 99999}, "formulario_id"),
    ({"responder_para": "nao-e-email"}, "responder_para"),
    ({"agradecimento": {"promotor": "a", "neutro": "", "detrator": "c"}}, "agradecimento.neutro"),
])
def test_configuracao_validacao(client, admin, corpo, campo):
    r = client.put(f"{API}/envios/configuracao", headers=admin["h"], json=corpo)
    assert r.status_code == 422, r.text
    assert campo in r.json()["erro"]["campos"], r.json()


def test_configuracao_salva_parcial_audita_e_permissoes(client, admin, dono):
    h = admin["h"]
    csat = form_padrao(client, h, "csat")
    r = client.put(f"{API}/envios/configuracao", headers=h, json={
        "lembretes": 2, "janela_inicio": "09:30", "responder_para": "Sac@Alfa.com.br", "remetente_nome": "Time Alfa",
        "formulario_id": csat["id"]})
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["lembretes"] == 2 and d["dias_lembretes"] == [3, 7]  # prazos acompanham a quantidade
    assert d["janela_inicio"] == "09:30" and d["responder_para"] == "sac@alfa.com.br"
    assert d["formulario_id"] == csat["id"] and d["intervalo_dias"] == 90
    d = client.put(f"{API}/envios/configuracao", headers=h, json={"lembretes": 0}).json()
    assert d["dias_lembretes"] == []
    d = client.put(f"{API}/envios/configuracao", headers=h, json={"responder_para": None}).json()
    assert d["responder_para"] is None and d["remetente_nome"] == "Time Alfa"
    evento = next(e for e in _eventos(client, h) if e["evento"] == "config_envios")
    assert evento["rotulo"] == "Configurações de envio alteradas"
    # formulário de outra conta não serve
    b = conta_pronta(client, "bia@beta.com.br", empresa="Beta")
    r = client.put(f"{API}/envios/configuracao", headers=h, json={"formulario_id": form_padrao(client, b["h"])["id"]})
    assert r.status_code == 422
    # gestor lê, mas não grava
    g = membro(client, h, "gil@alfa.com.br", "gestor")
    assert client.get(f"{API}/envios/configuracao", headers=g["h"]).status_code == 200
    assert client.put(f"{API}/envios/configuracao", headers=g["h"], json={"lembretes": 1}).status_code == 403
    assert client.post(f"{API}/envios/configuracao/teste", headers=g["h"]).status_code == 403


def test_email_de_teste(client, admin):
    h = admin["h"]
    r = client.post(f"{API}/envios/configuracao/teste", headers=h)
    assert r.status_code == 200
    assert r.json() == {"mensagem": "Enviamos um exemplo para ana@alfa.com.br."}
    [m] = emails_para("ana@alfa.com.br")[-1:]
    nps = form_padrao(client, h)
    assert f"/f/{nps['codigo_publico']}?canal=link&amp;nota=10" in m.html
    assert m.assunto == "Alfa Distribuidora quer saber a sua opinião"
    assert historico(client, h) == []  # não entra no histórico


# ---- conteúdo do e-mail -----------------------------------------------------

def test_disparo_manual_email_nps(client, admin):
    h = admin["h"]
    ligar_envios(client, h, responder_para="sac@alfa.com.br")
    e = criar_empresa(client, h, "Mercado Bom Preço")
    c = criar_contato(client, h, nome="Maria Silva", email="maria@cliente.com.br", empresa_id=e["id"])
    r = disparar(client, h, [c["id"]])
    assert r.status_code == 202, r.text
    assert r.json() == {"agendados": 1, "ignorados": []}
    [m] = emails_para("maria@cliente.com.br")
    assert m.assunto == "Alfa Distribuidora quer saber a sua opinião"
    assert m.remetente_nome == "Alfa Distribuidora" and m.responder_para == "sac@alfa.com.br"
    token = token_do_convite(m)
    # 11 botões 0–10, cores por faixa, rótulos
    notas = re.findall(rf'/r/{re.escape(token)}\?nota=(\d+)"[^>]*background:(#[0-9a-f]{{6}})', m.html)
    assert [int(n) for n, _ in notas] == list(range(11))
    assert {cor for n, cor in notas if int(n) <= 6} == {"#dc2626"}
    assert {cor for n, cor in notas if int(n) in (7, 8)} == {"#d97706"}
    assert {cor for n, cor in notas if int(n) >= 9} == {"#16a34a"}
    assert "Nada provável" in m.html and "Muito provável" in m.html
    assert "Olá, Maria!" in m.html and "Olá, Maria!" in m.texto and f"/r/{token}" in m.texto
    # rodapé e cabeçalhos de descadastro
    assert "Você recebeu esta pesquisa porque é cliente de Alfa Distribuidora." in m.html
    sair = re.search(r'href="(http://app\.teste/sair/[\w.-]+)"', m.html).group(1)
    assert "Não quero mais receber pesquisas" in m.html
    token_sair = sair.rsplit("/", 1)[1]
    assert m.cabecalhos["List-Unsubscribe"] == f"<{config().API_PUBLIC_URL}/api/v1/publico/descadastro/{token_sair}>"
    assert m.cabecalhos["List-Unsubscribe-Post"] == "List-Unsubscribe=One-Click"
    # o link funciona
    assert client.get(f"{API}/publico/convites/{token}").status_code == 200
    # histórico, fila e contato
    [envio] = historico(client, h)
    assert (envio["tipo"], envio["canal"], envio["origem"], envio["situacao"]) == ("convite", "email", "manual", "enviado")
    assert envio["contato"] == {"id": c["id"], "nome": "Maria Silva"} and envio["para"] == "maria@cliente.com.br"
    assert envio["usuario"]["id"] == admin["usuario"]["id"] and envio["erro"] is None
    item = fila(client, h)[c["id"]]
    assert item["situacao"] == "aguardando" and item["enviando"] is False
    assert item["ultimo_envio"] is not None and item["lembretes_enviados"] == 0
    detalhe = client.get(f"{API}/contatos/{c['id']}", headers=h).json()
    assert detalhe["situacao"] == "aguardando" and detalhe["proximo_envio"] == item["proximo_envio"]
    evento = next(x for x in _eventos(client, h) if x["evento"] == "envio_manual")
    assert evento["detalhe"]["quantidade"] == 1


def test_botoes_csat_e_personalizado(client, admin):
    h = admin["h"]
    csat = form_padrao(client, h, "csat")
    ligar_envios(client, h, formulario_id=csat["id"])
    c = criar_contato(client, h, email="joao@cliente.com.br")
    disparar(client, h, [c["id"]])
    [m] = emails_para("joao@cliente.com.br")
    assert re.findall(r"\?nota=(\d+)", m.html) == ["1", "2", "3", "4", "5"]
    livre = criar_form(client, h, [{"tipo": "texto_curto", "titulo": "Sugestão"}], nome="Livre")
    ligar_envios(client, h, formulario_id=livre["id"])
    c2 = criar_contato(client, h, email="lia@cliente.com.br")
    disparar(client, h, [c2["id"]])
    [m] = emails_para("lia@cliente.com.br")
    assert "?nota=" not in m.html and "Responder pesquisa" in m.html


def test_nome_vazio_remove_virgula(client, admin, dono):
    h = admin["h"]
    ligar_envios(client, h)
    c = criar_contato(client, h, nome="Ana", email="x@cliente.com.br")
    sql(dono, "update contatos set nome = '' where id = :c", c=c["id"])
    disparar(client, h, [c["id"]])
    [m] = emails_para("x@cliente.com.br")
    assert m.texto.startswith("Olá!\n\nSua opinião ajuda a Alfa Distribuidora")


# ---- motivos para ignorar ---------------------------------------------------

def test_ignorados_e_descanso(client, admin):
    h = admin["h"]
    ligar_envios(client, h)
    ok = criar_contato(client, h, nome="Ok", email="ok@c.com.br")
    inativo = criar_contato(client, h, nome="Inativo", email="in@c.com.br", ativo=False)
    sem_email = criar_contato(client, h, nome="Sem Email", email=None, telefone="11987654321")
    fora = criar_contato(client, h, nome="Fora", email="fora@c.com.br", recebe_pesquisas=False)
    desc = criar_contato(client, h, nome="Desc", email="desc@c.com.br")
    assert client.post(f"{API}/envios/descadastros", headers=h, json={"email": "DESC@c.com.br"}).status_code == 201
    r = disparar(client, h, [ok["id"], inativo["id"], sem_email["id"], fora["id"], desc["id"], 99999])
    assert r.status_code == 202
    assert r.json()["agendados"] == 1
    assert {i["contato_id"]: i["motivo"] for i in r.json()["ignorados"]} == {
        inativo["id"]: "Contato inativo", sem_email["id"]: "Sem e-mail",
        fora["id"]: "Saiu da lista", desc["id"]: "Saiu da lista"}
    assert r.json()["ignorados"][0]["nome"] == "Inativo"
    # descanso: recebeu hoje → pula, a menos de ignorar_descanso
    r = disparar(client, h, [ok["id"]])
    assert r.json() == {"agendados": 0, "ignorados": [
        {"contato_id": ok["id"], "nome": "Ok", "motivo": "Recebeu uma pesquisa hoje (descanso de 30 dias)"}]}
    assert fila(client, h)[ok["id"]]["descanso_ate"] is not None
    r = disparar(client, h, [ok["id"]], ignorar_descanso=True)
    assert r.json()["agendados"] == 1
    assert len(emails_para("ok@c.com.br")) == 2


def test_descanso_conta_dias_e_desliga_com_zero(client, admin, monkeypatch):
    h = admin["h"]
    ligar_envios(client, h)
    c = criar_contato(client, h, email="d@c.com.br")
    fixar_relogio(monkeypatch, segunda(10))
    disparar(client, h, [c["id"]])
    fixar_relogio(monkeypatch, segunda(10, mais_dias=5))
    r = disparar(client, h, [c["id"]]).json()
    assert r["ignorados"][0]["motivo"] == "Recebeu uma pesquisa há 5 dias (descanso de 30 dias)"
    ligar_envios(client, h, descanso_dias=0)
    assert fila(client, h)[c["id"]]["descanso_ate"] is None
    assert disparar(client, h, [c["id"]]).json()["agendados"] == 1


def test_disparo_validacao(client, admin):
    h = admin["h"]
    ligar_envios(client, h)
    r = client.post(f"{API}/envios/disparar", headers=h, json={"contato_ids": list(range(1, 502))})
    assert r.status_code == 422 and "contato_ids" in r.json()["erro"]["campos"]
    for corpo in [{}, {"contato_ids": [1], "toda_fila": True}, {"contato_ids": []}]:
        assert client.post(f"{API}/envios/disparar", headers=h, json=corpo).status_code == 422, corpo
    consulta = membro(client, h, "caio@alfa.com.br", "consulta")
    r = client.post(f"{API}/envios/disparar", headers=consulta["h"], json={"contato_ids": [1]})
    assert r.status_code == 403
    assert client.get(f"{API}/envios/contatos", headers=consulta["h"]).status_code == 200


def test_toda_a_fila_com_filtros(client, admin):
    h = admin["h"]
    ligar_envios(client, h)
    g = client.post(f"{API}/cadastros/grupos", headers=h, json={"nome": "Rede"}).json()
    e = criar_empresa(client, h, "Atacado", grupo_id=g["id"])
    a = criar_contato(client, h, nome="A", email="a@c.com.br", empresa_id=e["id"])
    criar_contato(client, h, nome="B", email="b@c.com.br")
    ja = criar_contato(client, h, nome="Já", email="ja@c.com.br", empresa_id=e["id"])
    disparar(client, h, [ja["id"]])
    r = client.post(f"{API}/envios/disparar", headers=h, json={"toda_fila": True, "filtros": {"grupo_id": g["id"]}})
    assert r.json() == {"agendados": 1, "ignorados": []}
    assert emails_para("a@c.com.br") and not emails_para("b@c.com.br")
    r = client.post(f"{API}/envios/disparar", headers=h, json={"toda_fila": True})
    assert r.json()["agendados"] == 1 and emails_para("b@c.com.br")
    assert all(x["situacao"] == "aguardando" for x in fila(client, h).values())
    assert a["id"] in fila(client, h, situacao="aguardando", grupo_id=g["id"])


# ---- fila: situação, intervalo e filtros ------------------------------------

def test_situacao_intervalo_e_proximo_envio(client, admin, dono, monkeypatch):
    h = admin["h"]
    sql(dono, "update contas set situacao = 'cortesia' where id = :c", c=admin["conta"]["id"])
    ligar_envios(client, h, intervalo_dias=60)
    c = criar_contato(client, h, email="p@c.com.br")
    assert fila(client, h)[c["id"]]["situacao"] == "na_fila"
    inicio = segunda(10)
    fixar_relogio(monkeypatch, inicio)
    disparar(client, h, [c["id"]])
    item = fila(client, h)[c["id"]]
    assert item["situacao"] == "aguardando"
    assert item["proximo_envio"] == data_iso(inicio + timedelta(days=60))
    assert item["descanso_ate"] == data_iso(inicio + timedelta(days=30))
    assert item["proximo_lembrete"] == data_iso(inicio + timedelta(days=3))
    # passa o maior prazo de lembrete + 7 (22 dias) sem resposta
    fixar_relogio(monkeypatch, inicio + timedelta(days=23))
    item = fila(client, h)[c["id"]]
    assert item["situacao"] == "aguardando_intervalo" and item["proximo_lembrete"] is None
    fixar_relogio(monkeypatch, inicio + timedelta(days=60))
    assert fila(client, h)[c["id"]]["situacao"] == "na_fila"
    # filtros de data
    alvo = data_iso(inicio + timedelta(days=60))
    assert c["id"] in fila(client, h, proximo_de=alvo, proximo_ate=alvo)
    assert c["id"] not in fila(client, h, proximo_ate=data_iso(inicio))
    assert c["id"] in fila(client, h, ultimo_de=data_iso(inicio), ultimo_ate=data_iso(inicio))
    r = client.get(f"{API}/envios/contatos", headers=h, params={"proximo_de": "31/12/2026"})
    assert r.status_code == 422


def test_respondeu_e_resumo(client, admin):
    h = admin["h"]
    ligar_envios(client, h)
    nps = form_padrao(client, h)
    c1 = criar_contato(client, h, email="r1@c.com.br")
    c2 = criar_contato(client, h, email="r2@c.com.br")
    c3 = criar_contato(client, h, email="r3@c.com.br")
    criar_contato(client, h, email="r4@c.com.br", ativo=False)
    criar_contato(client, h, email="r5@c.com.br", recebe_pesquisas=False)
    disparar(client, h, [c1["id"], c2["id"]])
    token = token_do_convite(emails_para("r1@c.com.br")[0])
    r = client.post(f"{API}/publico/convites/{token}/responder", json={"respostas": {nps["perguntas"][0]["id"]: 9}})
    assert r.status_code == 201
    assert fila(client, h)[c1["id"]]["situacao"] == "respondeu"
    assert client.get(f"{API}/contatos/{c1['id']}", headers=h).json()["situacao"] == "respondeu"
    resumo = client.get(f"{API}/envios/resumo", headers=h).json()
    assert resumo == {"na_fila": 1, "aguardando": 1, "responderam": 1, "com_erro": 0, "saiu_da_lista": 1,
                      "lembretes_hoje": 0, "enviados_30d": 3}  # 2 convites + 1 agradecimento
    # inativos só aparecem quando pedidos
    assert len(fila(client, h)) == 4
    assert len(fila(client, h, mostrar_inativos="true")) == 5
    assert len(fila(client, h, situacao="inativo")) == 1
    assert list(fila(client, h, situacao="na_fila")) == [c3["id"]]


def test_ordem_mais_atrasado_primeiro_e_busca(client, admin, dono):
    h = admin["h"]
    a = criar_contato(client, h, nome="Atrasado", email="at@c.com.br")
    n = criar_contato(client, h, nome="Novo", email="no@c.com.br", telefone="11955554444")
    f = criar_contato(client, h, nome="Futuro", email="fu@c.com.br")
    sql(dono, "update contatos set proximo_envio = current_date - 10 where id = :c", c=a["id"])
    sql(dono, "update contatos set proximo_envio = current_date + 10 where id = :c", c=f["id"])
    r = client.get(f"{API}/envios/contatos", headers=h).json()
    assert [x["id"] for x in r["itens"]] == [n["id"], a["id"], f["id"]]
    assert r["itens"][2]["situacao"] == "aguardando_intervalo"
    assert list(fila(client, h, busca="5555-4444")) == [n["id"]]
    assert list(fila(client, h, busca="futuro")) == [f["id"]]
    assert fila(client, h, grupo_id="", situacao="")  # vazios = sem filtro


# ---- erros, histórico e tentar de novo --------------------------------------

@pytest.mark.parametrize("erro,mensagem", [
    (erro_http(422), "O endereço de e-mail não existe ou recusou a mensagem."),
    (erro_http(429), "Limite de envio do provedor atingido; tentaremos de novo."),
    (erro_http(503), "O provedor de e-mail está fora do ar; tentaremos de novo."),
    (httpx.ConnectTimeout("tempo esgotado"), "O provedor de e-mail está fora do ar; tentaremos de novo."),
])
def test_erro_do_provedor_em_linguagem_simples(client, admin, monkeypatch, dono, erro, mensagem):
    h = admin["h"]
    ligar_envios(client, h)
    c = criar_contato(client, h, email="erro@c.com.br")
    falhar_provedor(monkeypatch, erro)
    assert disparar(client, h, [c["id"]]).status_code == 202
    [e] = historico(client, h)
    assert e["situacao"] == "erro" and e["erro"] == mensagem and e["pode_tentar_de_novo"] is True
    item = fila(client, h)[c["id"]]
    assert item["situacao"] == "nao_saiu" and item["ultimo_erro"] == mensagem
    assert item["proximo_envio"] is None and item["ultimo_envio"] is None
    assert sql(dono, "select falhas from contatos where id = :c", c=c["id"])[0][0] == 1
    assert "detalhe técnico" not in str(historico(client, h))


def test_tentar_de_novo(client, admin, monkeypatch, dono):
    h = admin["h"]
    ligar_envios(client, h)
    c = criar_contato(client, h, email="t@c.com.br")
    outro = criar_contato(client, h, email="o@c.com.br")
    falhar_provedor(monkeypatch, erro_http(422), para="t@c.com.br")
    disparar(client, h, [c["id"], outro["id"]])
    [erro] = historico(client, h, situacao="erro")
    ok = historico(client, h, situacao="enviado")[0]
    assert client.post(f"{API}/envios/{ok['id']}/tentar-de-novo", headers=h).status_code == 409
    assert client.post(f"{API}/envios/99999/tentar-de-novo", headers=h).status_code == 404
    # contato corrigiu o e-mail e o provedor voltou
    monkeypatch.undo()
    client.patch(f"{API}/contatos/{c['id']}", headers=h, json={"email": "t.certo@c.com.br"})
    r = client.post(f"{API}/envios/{erro['id']}/tentar-de-novo", headers=h)
    assert r.status_code == 202
    assert emails_para("t.certo@c.com.br")
    novo = historico(client, h, contato_id=c["id"])
    assert [x["situacao"] for x in novo] == ["enviado", "erro"]
    assert novo[1]["pode_tentar_de_novo"] is False
    assert client.post(f"{API}/envios/{erro['id']}/tentar-de-novo", headers=h).status_code == 409
    assert fila(client, h)[c["id"]]["situacao"] == "aguardando"
    assert sql(dono, "select falhas from contatos where id = :c", c=c["id"])[0][0] == 0
    # erro de quem não pode mais receber
    falhar_provedor(monkeypatch, erro_http(422))
    c3 = criar_contato(client, h, email="c3@c.com.br")
    disparar(client, h, [c3["id"]])
    [e3] = historico(client, h, contato_id=c3["id"])
    client.patch(f"{API}/contatos/{c3['id']}", headers=h, json={"ativo": False})
    assert historico(client, h, contato_id=c3["id"])[0]["pode_tentar_de_novo"] is False
    r = client.post(f"{API}/envios/{e3['id']}/tentar-de-novo", headers=h)
    assert r.status_code == 409 and r.json()["erro"]["codigo"] == "nao_pode_receber"


def test_historico_filtros(client, admin, monkeypatch):
    h = admin["h"]
    ligar_envios(client, h)
    a = criar_contato(client, h, nome="Alice", email="alice@c.com.br", telefone="11911112222")
    b = criar_contato(client, h, nome="Bruno", email="bruno@c.com.br")
    disparar(client, h, [a["id"], b["id"]])
    client.post(f"{API}/contatos/{a['id']}/whatsapp", headers=h, json={})
    assert len(historico(client, h)) == 3
    assert [x["canal"] for x in historico(client, h, canal="whatsapp")] == ["whatsapp"]
    assert len(historico(client, h, tipo="convite")) == 3 and historico(client, h, tipo="lembrete") == []
    assert [x["contato"]["nome"] for x in historico(client, h, busca="bruno")] == ["Bruno"]
    assert len(historico(client, h, contato_id=a["id"])) == 2
    assert len(historico(client, h, situacao="aberto_no_whatsapp")) == 1
    hoje = data_iso(datetime.now(FUSO))
    assert len(historico(client, h, de=hoje, ate=hoje)) == 3
    assert historico(client, h, de="2020-01-01", ate="2020-01-02") == []
    assert client.get(f"{API}/envios/historico", headers=h, params={"tipo": "outro"}).status_code == 422
    primeiro = historico(client, h)[0]
    assert primeiro["canal"] == "whatsapp"  # mais novo primeiro


# ---- WhatsApp ---------------------------------------------------------------

def test_whatsapp(client, admin, dono):
    h = admin["h"]
    e = criar_empresa(client, h, "Mercado Bom Preço")
    c = criar_contato(client, h, nome="Carlos Souza", email="carlos@c.com.br", telefone="(11) 98765-4321",
                      empresa_id=e["id"])
    # não exige envios ligados nem provedor
    r = client.post(f"{API}/contatos/{c['id']}/whatsapp", headers=h, json={})
    assert r.status_code == 201, r.text
    d = r.json()
    assert d["url"].startswith("https://wa.me/5511987654321?text=")
    assert unquote(d["url"].split("?text=", 1)[1]) == d["mensagem"]
    assert d["mensagem"] == f"Olá, Carlos! Aqui é da Alfa Distribuidora. Pode responder uma pesquisa rápida? " \
                            f"Leva 1 minuto: {d['link']}"
    token = d["link"].rsplit("/", 1)[1]
    assert client.get(f"{API}/publico/convites/{token}").status_code == 200
    [envio] = historico(client, h)
    assert (envio["canal"], envio["situacao"], envio["para"]) == ("whatsapp", "aberto_no_whatsapp", "5511987654321")
    item = fila(client, h)[c["id"]]
    assert item["situacao"] == "aguardando" and item["proximo_envio"] and item["descanso_ate"]
    assert item["proximo_lembrete"] is None  # WhatsApp não tem lembrete por e-mail
    # conta para o descanso do e-mail
    ligar_envios(client, h)
    r = disparar(client, h, [c["id"]]).json()
    assert r["agendados"] == 0 and "descanso" in r["ignorados"][0]["motivo"]
    # resposta pelo WhatsApp grava o canal
    nps = form_padrao(client, h)
    client.post(f"{API}/publico/convites/{token}/responder", json={"respostas": {nps["perguntas"][0]["id"]: 8}})
    assert sql(dono, "select canal from respostas")[0][0] == "whatsapp"
    # texto personalizado com {empresa_cliente}
    ligar_envios(client, h, texto_whatsapp="Oi {nome}, da {empresa_cliente}: {link}")
    d = client.post(f"{API}/contatos/{c['id']}/whatsapp", headers=h).json()
    assert d["mensagem"].startswith("Oi Carlos, da Mercado Bom Preço: http://app.teste/r/")


def test_whatsapp_regras(client, admin, dono):
    h = admin["h"]
    sem_tel = criar_contato(client, h, email="s@c.com.br")
    r = client.post(f"{API}/contatos/{sem_tel['id']}/whatsapp", headers=h, json={})
    assert r.status_code == 422 and r.json()["erro"]["mensagem"] == "Este contato não tem telefone."
    inativo = criar_contato(client, h, email="i@c.com.br", telefone="11911112222", ativo=False)
    assert client.post(f"{API}/contatos/{inativo['id']}/whatsapp", headers=h, json={}).status_code == 409
    desc = criar_contato(client, h, email="d@c.com.br", telefone="11911113333")
    client.post(f"{API}/envios/descadastros", headers=h, json={"email": "d@c.com.br"})
    r = client.post(f"{API}/contatos/{desc['id']}/whatsapp", headers=h, json={})
    assert r.status_code == 409 and r.json()["erro"]["codigo"] == "saiu_da_lista"
    ok = criar_contato(client, h, email=None, telefone="11911114444")
    csat = form_padrao(client, h, "csat")
    assert client.post(f"{API}/contatos/{ok['id']}/whatsapp", headers=h,
                       json={"formulario_id": csat["id"]}).status_code == 201
    assert client.post(f"{API}/contatos/99999/whatsapp", headers=h, json={}).status_code == 404
    consulta = membro(client, h, "caio@alfa.com.br", "consulta")
    assert client.post(f"{API}/contatos/{ok['id']}/whatsapp", headers=consulta["h"], json={}).status_code == 403
    sql(dono, "update contas set situacao = 'teste_expirado' where id = :c", c=admin["conta"]["id"])
    r = client.post(f"{API}/contatos/{ok['id']}/whatsapp", headers=h, json={})
    assert r.status_code == 409 and r.json()["erro"]["codigo"] == "pre_condicao"

"""Etapa 5e: registro de e-mails enviados (pesquisas e e-mails do sistema, enviado e falhou, falha ao gravar não
derruba, sem conta não grava), GET /auditoria/emails (filtros, busca sem acento, período, `falhas_7_dias`, permissão,
isolamento) e a tarefa `limpeza`."""
import logging
from datetime import timedelta

import pytest
from sqlalchemy import text
from util import (
    API,
    cadastrar,
    conta_pronta,
    criar_contato,
    disparar,
    emails_enviados,
    emails_para,
    erro_http,
    falhar_provedor,
    form_padrao,
    historico,
    ligar_envios,
    membro,
    sql,
    token_do_convite,
)

from toqqi import tarefas
from toqqi.core import email, relogio
from toqqi.core.avisos import avisar_admins
from toqqi.core.db import em_conta
from toqqi.core.email import MSG_ENDERECO, MSG_FORA_DO_AR, TIPOS, Mensagem, caixa_memoria
from toqqi.modulos.auditoria import emails as registro

pytestmark = pytest.mark.usefixtures("relogio_estavel")
CAMPOS_ITEM = {"id", "tipo", "tipo_rotulo", "destinatario", "assunto", "situacao", "erro", "criado_em"}
INSERIR = ("insert into emails_enviados (conta_id, tipo, destinatario, assunto, situacao, erro, criado_em) "
           "values (:c, :tipo, :para, :assunto, :situacao, :erro, now() - make_interval(days => :dias, mins => :mins))")


@pytest.fixture
def admin(client):
    return conta_pronta(client, "ana@alfa.com.br", empresa="Alfa")


def _pagina(client, h, **filtros):
    return client.get(f"{API}/auditoria/emails", headers=h, params=filtros)


def _inserir(dono, conta_id: int, dias: int = 0, tipo: str = "convite", para: str = "cliente@c.com.br",
             assunto: str = "Alfa quer saber a sua opinião", situacao: str = "enviado", erro: str | None = None,
             mins: int = 0) -> None:
    sql(dono, INSERIR, c=conta_id, tipo=tipo, para=para, assunto=assunto, situacao=situacao,
        erro=erro if situacao == "falhou" else None, dias=dias, mins=mins)


def _linhas(dono, conta_id: int | None = None) -> list[tuple]:
    filtro = "where conta_id = :c" if conta_id else ""
    return sql(dono, f"select tipo, destinatario, assunto, situacao, erro from emails_enviados {filtro} order by id",
               c=conta_id)


# ---- registro ----------------------------------------------------------------------------------

def test_cadastro_ja_registra_a_confirmacao(client, admin, dono):
    assert _linhas(dono) == [("confirmacao", "ana@alfa.com.br", "Confirme seu e-mail no Toqqi", "enviado", None)]
    [item] = emails_enviados(client, admin["h"])
    assert set(item) == CAMPOS_ITEM
    assert (item["tipo"], item["tipo_rotulo"], item["destinatario"], item["erro"]) == (
        "confirmacao", "Confirmação de e-mail", "ana@alfa.com.br", None)
    # a tabela não guarda nada do corpo
    colunas = {c for (c,) in sql(dono, "select column_name from information_schema.columns "
                                       "where table_name = 'emails_enviados'")}
    assert colunas == {"id", "conta_id", "tipo", "destinatario", "assunto", "situacao", "erro", "criado_em"}


def test_pesquisas_enviadas_e_com_falha(client, admin, dono, monkeypatch):
    h, c = admin["h"], admin["conta"]["id"]
    ligar_envios(client, h)
    ok = criar_contato(client, h, nome="Paula Lima", email="paula@c.com.br")
    ruim = criar_contato(client, h, nome="Rui", email="rui@c.com.br")
    falhar_provedor(monkeypatch, erro_http(422), para="rui@c.com.br")
    assert disparar(client, h, [ok["id"], ruim["id"]]).status_code == 202
    assert client.post(f"{API}/envios/configuracao/teste", headers=h).status_code == 200
    # agradecimento depois da resposta
    nps = form_padrao(client, h)
    token = token_do_convite(emails_para("paula@c.com.br")[0])
    client.post(f"{API}/publico/convites/{token}/responder", json={"respostas": {nps["perguntas"][0]["id"]: 10}})
    linhas = _linhas(dono, c)[1:]  # sem a confirmação do cadastro
    assert sorted(linhas) == sorted([
        ("convite", "paula@c.com.br", "Alfa quer saber a sua opinião", "enviado", None),
        ("convite", "rui@c.com.br", "Alfa quer saber a sua opinião", "falhou", MSG_ENDERECO),
        ("teste", "ana@alfa.com.br", "Alfa quer saber a sua opinião", "enviado", None),
        ("agradecimento", "paula@c.com.br", "Alfa agradece a sua resposta", "enviado", None),
    ])
    # o histórico de envios continua com o texto simples do erro (nada do corpo do provedor no registro)
    assert {e["para"]: e["erro"] for e in historico(client, h, tipo="convite")}["rui@c.com.br"] == MSG_ENDERECO
    assert "detalhe técnico" not in str(sql(dono, "select * from emails_enviados"))
    pagina = _pagina(client, h).json()
    assert pagina["falhas_7_dias"] == 1 and pagina["total"] == 5
    assert pagina["itens"][0]["tipo"] == "agradecimento"  # mais novos primeiro
    assert [i["tipo_rotulo"] for i in emails_enviados(client, h, tipo="teste")] == ["E-mail de teste"]
    assert [i["destinatario"] for i in emails_enviados(client, h, situacao="falhou")] == ["rui@c.com.br"]


def test_emails_do_sistema(client, admin, dono, monkeypatch):
    c = admin["conta"]["id"]
    # redefinir a senha
    assert client.post(f"{API}/auth/esqueci-senha", json={"email": "ana@alfa.com.br"}).status_code == 200
    # cadastro com um e-mail que já existe: o aviso "você já tem uma conta" entra na conta de quem já existe
    cadastrar(client, "ana@alfa.com.br", empresa="Outra")
    # aviso aos administradores
    with em_conta(c) as s:
        avisar_admins(s, c, "Um webhook da Toqqi foi desativado", ["Teste."])
    # e-mail do sistema que falha: entra como falhou, com o texto simples, e o fluxo segue
    falhar_provedor(monkeypatch, erro_http(500))
    assert client.post(f"{API}/auth/esqueci-senha", json={"email": "ana@alfa.com.br"}).status_code == 200
    assert _linhas(dono, c)[1:] == [
        ("senha", "ana@alfa.com.br", "Redefina sua senha do Toqqi", "enviado", None),
        ("confirmacao", "ana@alfa.com.br", "Você já tem uma conta no Toqqi", "enviado", None),
        ("aviso", "ana@alfa.com.br", "Um webhook da Toqqi foi desativado", "enviado", None),
        ("senha", "ana@alfa.com.br", "Redefina sua senha do Toqqi", "falhou", MSG_FORA_DO_AR),
    ]
    assert sql(dono, "select count(*) from contas")[0][0] == 1  # o cadastro repetido não criou conta


def test_pedido_de_acesso_e_reenvio_entram_na_conta(client, admin, dono):
    h, c = admin["h"], admin["conta"]["id"]
    assert client.put(f"{API}/conta/seguranca", headers=h, json={"sessao_minutos": 480, "dominios": ["alfa.com.br"]}
                      ).status_code == 200
    r = client.post(f"{API}/auth/pedir-acesso", json={"nome": "Bia", "email": "bia@alfa.com.br", "senha": "Senha@123"})
    assert r.status_code == 200, r.text
    assert client.post(f"{API}/auth/reenviar-confirmacao", json={"email": "bia@alfa.com.br"}).status_code == 200
    assert [(t, p) for t, p, *_ in _linhas(dono, c)][1:] == [("confirmacao", "bia@alfa.com.br")] * 2


def test_sem_conta_ou_tipo_nao_grava(dono, caplog):
    email.enviar("solto@c.com.br", "Sem conta", ["Oi."])
    email.enviar("solto@c.com.br", "Sem tipo", ["Oi."], conta_id=1)
    email.enviar_mensagem(Mensagem(para="solto@c.com.br", assunto="Pesquisa", texto="t", html="<p>t</p>"))
    assert len(caixa_memoria) == 3 and _linhas(dono) == []
    # tipo desconhecido: não grava, e o erro vai só para o log
    with caplog.at_level(logging.ERROR, logger="toqqi.email"):
        email.registrar_envio(1, "newsletter", "solto@c.com.br", "Assunto")
    assert _linhas(dono) == [] and "Falha ao registrar o e-mail enviado" in caplog.text
    assert "solto@c.com.br" not in caplog.text


def test_falha_ao_gravar_nao_derruba_o_envio(client, admin, dono, monkeypatch, caplog):
    h, c = admin["h"], admin["conta"]["id"]

    def quebrado(_conta_id):
        raise RuntimeError("banco fora do ar")

    monkeypatch.setattr(email, "em_conta", quebrado)
    ligar_envios(client, h)
    contato = criar_contato(client, h, email="paula@c.com.br")
    with caplog.at_level(logging.ERROR, logger="toqqi.email"):
        assert client.post(f"{API}/envios/configuracao/teste", headers=h).status_code == 200
        assert disparar(client, h, [contato["id"]]).status_code == 202
        assert client.post(f"{API}/auth/esqueci-senha", json={"email": "ana@alfa.com.br"}).status_code == 200
    assert len(emails_para("ana@alfa.com.br")) == 3 and len(emails_para("paula@c.com.br")) == 1
    assert [e["situacao"] for e in historico(client, h)] == ["enviado"]
    assert _linhas(dono, c) == [("confirmacao", "ana@alfa.com.br", "Confirme seu e-mail no Toqqi", "enviado", None)]
    assert caplog.text.count("Falha ao registrar o e-mail enviado") == 3


def test_assunto_cortado_em_300(dono, admin):
    email.registrar_envio(admin["conta"]["id"], "aviso", "ana@alfa.com.br", "x" * 400, "y" * 600)
    assunto, erro = sql(dono, "select assunto, erro from emails_enviados where tipo = 'aviso'")[0]
    assert len(assunto) == 300 and len(erro) == 500


# ---- GET /auditoria/emails ------------------------------------------------------------------------

def test_lista_filtros_busca_e_periodo(client, admin, dono):
    h, c = admin["h"], admin["conta"]["id"]
    sql(dono, "delete from emails_enviados")
    _inserir(dono, c, 0, "convite", "joao@cliente.com.br", "Alfa quer saber a sua opinião", mins=1)
    _inserir(dono, c, 1, "lembrete", "MARIA@cliente.com.br", "Lembrete: sua opinião é importante")
    _inserir(dono, c, 2, "senha", "ana@alfa.com.br", "Redefina sua senha do Toqqi", "falhou", MSG_FORA_DO_AR)
    _inserir(dono, c, 6, "aviso", "ana@alfa.com.br", "Ação: revisão", "falhou", MSG_ENDERECO)
    _inserir(dono, c, 8, "convite", "jose@cliente.com.br", "Pesquisa de satisfação", "falhou", MSG_ENDERECO)
    _inserir(dono, c, 40, "convite", "antigo@cliente.com.br", "Velho")
    hoje = relogio.hoje()
    p = _pagina(client, h).json()
    assert set(p) == {"itens", "total", "pagina", "por_pagina", "falhas_7_dias", "periodo"}
    assert p["periodo"] == {"de": (hoje - timedelta(days=29)).isoformat(), "ate": hoje.isoformat()}
    assert p["total"] == 5 and p["falhas_7_dias"] == 2  # a falha de 8 dias atrás não conta
    assert [i["destinatario"] for i in p["itens"]] == ["joao@cliente.com.br", "MARIA@cliente.com.br",
                                                       "ana@alfa.com.br", "ana@alfa.com.br", "jose@cliente.com.br"]
    assert p["itens"][2]["erro"] == MSG_FORA_DO_AR and p["itens"][0]["erro"] is None
    # filtros
    assert [i["tipo"] for i in emails_enviados(client, h, tipo="convite")] == ["convite", "convite"]
    assert len(emails_enviados(client, h, situacao="falhou")) == 3
    assert len(emails_enviados(client, h, situacao="falhou", de=(hoje - timedelta(days=6)).isoformat(),
                                ate=hoje.isoformat())) == 2  # "Ver só as falhas"
    # busca no destinatário e no assunto, sem acento e sem diferenciar maiúsculas
    assert [i["destinatario"] for i in emails_enviados(client, h, busca="maria")] == ["MARIA@cliente.com.br"]
    assert [i["destinatario"] for i in emails_enviados(client, h, busca="OPINIAO")] == [
        "joao@cliente.com.br", "MARIA@cliente.com.br"]
    assert [i["tipo"] for i in emails_enviados(client, h, busca="acao: REVISAO")] == ["aviso"]
    assert [i["tipo"] for i in emails_enviados(client, h, busca="satisfação")] == ["convite"]
    assert emails_enviados(client, h, busca="100%_") == []  # curingas do LIKE valem como texto
    # período: até 90 dias; os mais antigos aparecem pedindo o período
    assert [i["destinatario"] for i in emails_enviados(client, h, de=(hoje - timedelta(days=45)).isoformat(),
                                                        ate=(hoje - timedelta(days=30)).isoformat())] == [
        "antigo@cliente.com.br"]
    assert len(emails_enviados(client, h, de=(hoje - timedelta(days=89)).isoformat())) == 6
    # paginação
    p = _pagina(client, h, por_pagina=2, pagina=2).json()
    assert (p["total"], p["pagina"], p["por_pagina"], len(p["itens"])) == (5, 2, 2, 2)
    assert p["itens"][0]["destinatario"] == "ana@alfa.com.br"


@pytest.mark.parametrize("filtros,campo", [
    ({"de": "2026-13-01"}, "de"),
    ({"de": "1999-12-31"}, "de"),
    ({"situacao": "entregue"}, "situacao"),
    ({"tipo": "newsletter"}, "tipo"),
    ({"busca": "x" * 101}, "busca"),
    ({"por_pagina": 500}, "por_pagina"),
])
def test_filtros_invalidos(client, admin, filtros, campo):
    r = _pagina(client, admin["h"], **filtros)
    assert r.status_code == 422 and campo in r.json()["erro"]["campos"], r.text


def test_periodo_invalido(client, admin):
    h = admin["h"]
    hoje = relogio.hoje()
    r = _pagina(client, h, de=(hoje - timedelta(days=90)).isoformat(), ate=hoje.isoformat())  # 91 dias
    assert r.status_code == 422 and r.json()["erro"]["campos"] == {"de": "O período pode ter no máximo 90 dias."}
    r = _pagina(client, h, de=hoje.isoformat(), ate=(hoje - timedelta(days=1)).isoformat())
    assert r.status_code == 422 and "de" in r.json()["erro"]["campos"]
    assert _pagina(client, h, de="", ate="", situacao="", tipo="", busca="").status_code == 200  # vazios = sem filtro


def test_permissao_e_isolamento(client, admin, dono, app_engine):
    h = admin["h"]
    gestor = membro(client, h, "gil@alfa.com.br", "gestor")
    assert _pagina(client, gestor["h"]).status_code == 403
    assert client.get(f"{API}/auditoria/emails").status_code == 401
    b = conta_pronta(client, "bia@beta.com.br", empresa="Beta")
    _inserir(dono, b["conta"]["id"], 0, "aviso", "bia@beta.com.br", "Só da Beta", "falhou", MSG_ENDERECO)
    assert [i["destinatario"] for i in emails_enviados(client, h)] == ["ana@alfa.com.br"]
    assert _pagina(client, h).json()["falhas_7_dias"] == 0
    assert {i["destinatario"] for i in emails_enviados(client, b["h"])} == {"bia@beta.com.br"}
    # SQL direto: sem contexto não vê nada; com a conta A não vê nem mexe nas linhas de B
    with app_engine.connect() as conexao:
        assert conexao.execute(text("select count(*) from emails_enviados")).scalar() == 0
    with app_engine.begin() as conexao:
        conexao.execute(text("select set_config('app.conta_id', :c, true)"), {"c": str(admin["conta"]["id"])})
        assert conexao.execute(text("select count(*) from emails_enviados")).scalar() == 1
        assert conexao.execute(text("delete from emails_enviados where conta_id = :b"),
                               {"b": b["conta"]["id"]}).rowcount == 0
    assert sql(dono, "select count(*) from emails_enviados where conta_id = :b", b=b["conta"]["id"])[0][0] == 2


# ---- limpeza ------------------------------------------------------------------------------------

def test_tarefa_limpeza(client, admin, dono, monkeypatch):
    c = admin["conta"]["id"]
    b = conta_pronta(client, "bia@beta.com.br", empresa="Beta")
    sql(dono, "delete from emails_enviados")
    for conta in (c, b["conta"]["id"]):
        for dias in (91, 95, 200):
            _inserir(dono, conta, dias)
        _inserir(dono, conta, 89)
    _inserir(dono, c, 90, mins=-5)  # 89 dias e 23h55: fica
    monkeypatch.setattr(registro, "LOTE_LIMPEZA", 2)  # vários lotes
    assert tarefas.executar("limpeza") == {"limpeza": {"emails_apagados": 6}}
    assert sql(dono, "select count(*) from emails_enviados")[0][0] == 3
    assert tarefas.executar("limpeza") == {"limpeza": {"emails_apagados": 0}}
    assert tarefas.main(["limpeza"]) == 0


def test_limpeza_e_a_ultima_do_tudo():
    assert tarefas.TAREFAS[-2:] == ("limpeza", "tudo")
    assert list(tarefas.executar("tudo"))[-1] == "limpeza"


def test_tipos_e_rotulos():
    assert TIPOS == {
        "convite": "Convite de pesquisa", "lembrete": "Lembrete", "agradecimento": "Agradecimento",
        "teste": "E-mail de teste", "confirmacao": "Confirmação de e-mail", "senha": "Redefinição de senha",
        "boas_vindas": "Boas-vindas", "alerta_risco": "Alerta de risco", "resumo_semanal": "Resumo semanal",
        "pico": "Pico de reclamações", "indicacao": "Nova indicação", "aviso": "Aviso aos administradores",
        "cobranca": "Cobrança",
    }

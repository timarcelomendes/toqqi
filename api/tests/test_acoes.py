"""Etapa 4a: planos de ação (ação automática, alerta de risco, quadro, lista, criar, mover, concluir, excluir,
configuração e permissões)."""
from datetime import timedelta

import pytest
from sqlalchemy.exc import IntegrityError
from util import (
    API,
    conta_pronta,
    criar_contato,
    criar_empresa,
    criar_form,
    criar_responsavel,
    emails_enviados,
    emails_para,
    form_padrao,
    link_pesquisa,
    lista_respostas,
    membro,
    quadro,
    registrar_resposta,
    responder_convite,
    responder_link,
    sql,
)

from toqqi.core import relogio
from toqqi.core.db import em_conta
from toqqi.core.email import caixa_memoria
from toqqi.modelos import Contato, Formulario
from toqqi.modulos.respostas import eventos
from toqqi.modulos.respostas.registro import gravar_resposta, variaveis

pytestmark = pytest.mark.usefixtures("relogio_estavel")


def hoje():
    return relogio.hoje()


@pytest.fixture
def admin(client):
    return conta_pronta(client, "ana@alfa.com.br", empresa="Alfa Distribuidora")


@pytest.fixture
def cliente(client, admin):
    """Empresa com responsável (com e-mail) e um contato com e-mail e telefone."""
    h = admin["h"]
    rita = criar_responsavel(client, h, "Rita Gomes", email="rita@alfa.com.br", foto_url="https://x.com/r.png")
    e = criar_empresa(client, h, "Atacado Norte", responsavel_id=rita["id"])
    c = criar_contato(client, h, nome="Paula Lima", email="paula@norte.com.br", telefone="11988887777",
                      empresa_id=e["id"])
    return {"h": h, "rita": rita, "empresa": e, "contato": c}


def _acao_da_ultima_resposta(client, h) -> dict | None:
    r = lista_respostas(client, h)["itens"][0]
    return client.get(f"{API}/acoes/{r['acao']['id']}", headers=h).json() if r["acao"] else None


def _criar(client, h, **campos) -> dict:
    r = client.post(f"{API}/acoes", headers=h, json={"titulo": "Ação", **campos})
    assert r.status_code == 201, r.text
    return r.json()


# ---- ação automática --------------------------------------------------------

@pytest.mark.parametrize("nota,prioridade,dias,rotulo", [
    (0, "alta", 2, "Detrator"), (6, "alta", 2, "Detrator"), (7, "media", 5, "Neutro"), (8, "media", 5, "Neutro"),
    (9, None, None, None), (10, None, None, None),
])
def test_acao_automatica_nps(client, cliente, nota, prioridade, dias, rotulo):
    h = cliente["h"]
    responder_convite(client, h, cliente["contato"]["id"], nota, comentario="O frete atrasou",
                      contexto={"pedido": "4521", "rota": "Sul", "motorista": "Zé", "filial": "Campinas"})
    a = _acao_da_ultima_resposta(client, h)
    if prioridade is None:
        assert a is None
        return
    assert a["titulo"] == f"[{rotulo} NPS {nota}] Ação requerida: Atacado Norte"
    assert (a["prioridade"], a["prazo"], a["situacao"], a["origem"]) == (
        prioridade, (hoje() + timedelta(days=dias)).isoformat(), "a_fazer", "automatica")
    assert (a["grupo"], a["tipo_nota"], a["nota"]) == (rotulo.lower(), "nps", nota)
    assert a["responsavel"] == {"id": cliente["rita"]["id"], "nome": "Rita Gomes", "email": "rita@alfa.com.br",
                                "foto_url": "https://x.com/r.png"}
    assert a["empresa"] == {"id": cliente["empresa"]["id"], "nome": "Atacado Norte"}
    assert a["contato"] == {"id": cliente["contato"]["id"], "nome": "Paula Lima"}
    # o contato só pelo nome (a ação já leva ao cadastro): nada de e-mail ou telefone na descrição
    assert a["descricao"] == ("Comentário do cliente: O frete atrasou\nContato: Paula Lima\n"
                              "Pedido: 4521\nRota: Sul\nMotorista: Zé\nFilial: Campinas")
    assert a["resposta"]["nota"] == nota and a["resposta"]["comentario"] == "O frete atrasou"
    assert a["criado_por"] is None and a["concluida_em"] is None


def test_promotor_so_com_configuracao_e_prazos_configurados(client, cliente):
    h = cliente["h"]
    r = client.put(f"{API}/acoes/configuracao", headers=h,
                   json={"acao_promotor": True, "prazo_promotor": 10, "prazo_detrator": 1})
    assert r.json() == {"prazo_detrator": 1, "prazo_neutro": 5, "prazo_promotor": 10, "acao_promotor": True}
    responder_convite(client, h, cliente["contato"]["id"], 10)
    a = _acao_da_ultima_resposta(client, h)
    assert a["titulo"] == "[Promotor NPS 10] Ação requerida: Atacado Norte"
    assert (a["prioridade"], a["prazo"]) == ("baixa", (hoje() + timedelta(days=10)).isoformat())
    assert a["descricao"].startswith("Comentário do cliente: (sem comentário)\n")
    registrar_resposta(client, h, cliente["contato"]["id"], 1)
    assert _acao_da_ultima_resposta(client, h)["prazo"] == (hoje() + timedelta(days=1)).isoformat()


@pytest.mark.parametrize("nota,cria", [(1, True), (2, True), (3, False), (4, False), (5, False)])
def test_acao_automatica_csat(client, cliente, nota, cria):
    h = cliente["h"]
    csat = form_padrao(client, h, "csat")
    responder_convite(client, h, cliente["contato"]["id"], nota, formulario=csat, assunto="a entrega do pedido 77")
    a = _acao_da_ultima_resposta(client, h)
    if not cria:
        assert a is None
        return
    assert a["titulo"] == f"[CSAT {nota}] Cliente insatisfeito: a entrega do pedido 77"
    assert (a["prioridade"], a["prazo"], a["grupo"], a["tipo_nota"]) == (
        "alta", (hoje() + timedelta(days=2)).isoformat(), "insatisfeito", "csat")


def test_alvo_e_assunto_sem_cadastro(client, admin):
    h = admin["h"]
    # contato sem empresa: o alvo é o contato
    c = criar_contato(client, h, nome="Júlia Sá", email="julia@x.com.br")
    registrar_resposta(client, h, c["id"], 5)
    assert _acao_da_ultima_resposta(client, h)["titulo"] == "[Detrator NPS 5] Ação requerida: Júlia Sá"
    # CSAT sem assunto no convite: o assunto é o alvo
    csat = form_padrao(client, h, "csat")
    responder_convite(client, h, c["id"], 1, formulario=csat)
    a = _acao_da_ultima_resposta(client, h)
    assert a["titulo"] == "[CSAT 1] Cliente insatisfeito: Júlia Sá" and a["responsavel"] is None
    # link público sem identificação
    nps = form_padrao(client, h)
    responder_link(client, nps["codigo_publico"], {nps["perguntas"][0]["id"]: 2})
    a = _acao_da_ultima_resposta(client, h)
    assert a["titulo"] == "[Detrator NPS 2] Ação requerida: cliente sem cadastro"
    assert a["descricao"] == "Comentário do cliente: (sem comentário)"
    assert a["empresa"] is None and a["contato"] is None


def test_uma_acao_automatica_por_resposta(client, cliente, dono):
    h = cliente["h"]
    registrar_resposta(client, h, cliente["contato"]["id"], 3)
    (rid, conta), = sql(dono, "select resposta_id, conta_id from acoes")
    with pytest.raises(IntegrityError):
        sql(dono, "insert into acoes (conta_id, resposta_id, titulo, prioridade, origem) "
                  "values (:c, :r, 'x', 'alta', 'automatica')", c=conta, r=rid)
    # manual ligada à mesma resposta pode
    _criar(client, h, resposta_id=rid)
    assert sql(dono, "select count(*) from acoes where resposta_id = :r", r=rid)[0][0] == 2


def test_titulo_longo_e_cortado(client, admin):
    h = admin["h"]
    e = criar_empresa(client, h, "E" * 190)
    c = criar_contato(client, h, empresa_id=e["id"])
    registrar_resposta(client, h, c["id"], 0, comentario="x" * 4000)
    a = _acao_da_ultima_resposta(client, h)
    assert len(a["titulo"]) == 200 and a["titulo"].endswith("…")
    assert len(a["descricao"]) == 4000


# ---- alerta de risco --------------------------------------------------------

def test_alerta_ao_responsavel(client, cliente):
    h = cliente["h"]
    responder_convite(client, h, cliente["contato"]["id"], 2, comentario="Produto veio quebrado")
    a = _acao_da_ultima_resposta(client, h)
    m, = emails_para("rita@alfa.com.br")
    assert m.assunto == "Alerta de risco: Atacado Norte deu nota 2"
    # etapa 5e: entra no registro de e-mails enviados da conta
    assert [(e["tipo"], e["tipo_rotulo"], e["assunto"], e["situacao"])
            for e in emails_enviados(client, h, tipo="alerta_risco")] == [
        ("alerta_risco", "Alerta de risco", m.assunto, "enviado")]
    assert "Atacado Norte deu nota 2 e precisa de atenção." in m.texto
    assert "Nota: 2 · Categoria: Detrator (NPS)" in m.texto
    assert "Comentário: Produto veio quebrado" in m.texto
    assert "Contato: Paula Lima\n" in m.texto
    assert "paula@norte.com.br" not in m.texto and "98888" not in m.texto
    assert f"Tratar no Toqqi: http://app.teste/planos-de-acao/{a['id']}" in m.texto
    assert f"http://app.teste/planos-de-acao/{a['id']}" in m.html
    # neutro (prioridade média) não alerta; CSAT insatisfeito alerta
    responder_convite(client, h, cliente["contato"]["id"], 7)
    assert len(emails_para("rita@alfa.com.br")) == 1
    responder_convite(client, h, cliente["contato"]["id"], 1, formulario=form_padrao(client, h, "csat"))
    assert emails_para("rita@alfa.com.br")[-1].assunto == "Alerta de risco: Atacado Norte deu nota 1"


def test_sem_email_do_responsavel_nao_alerta(client, admin):
    h = admin["h"]
    sem_email = criar_responsavel(client, h, "Beto")
    e = criar_empresa(client, h, "Mercado Sul", responsavel_id=sem_email["id"])
    c = criar_contato(client, h, email="c@sul.com.br", empresa_id=e["id"])
    caixa_memoria.clear()
    registrar_resposta(client, h, c["id"], 0)
    assert caixa_memoria == []
    assert _acao_da_ultima_resposta(client, h)["responsavel"]["nome"] == "Beto"


def test_alerta_so_depois_do_commit(client, cliente, monkeypatch, dono):
    """Se a transação falha depois do gancho, nada é gravado e o alerta não sai."""
    h = cliente["h"]

    def falhar(s, r):
        raise RuntimeError("falha depois da ação")

    monkeypatch.setattr(eventos, "GANCHOS", [*eventos.GANCHOS, falhar])
    caixa_memoria.clear()
    with pytest.raises(RuntimeError):
        registrar_resposta(client, h, cliente["contato"]["id"], 0)
    assert caixa_memoria == []
    assert sql(dono, "select count(*) from acoes")[0][0] == 0
    assert sql(dono, "select count(*) from respostas")[0][0] == 0


def test_sem_coletor_nao_envia(client, cliente):
    """Quem grava resposta sem `coletar_alertas()` cria a ação, mas o alerta não sai."""
    h = cliente["h"]
    conta_id = client.get(f"{API}/eu", headers=h).json()["conta"]["id"]
    caixa_memoria.clear()
    with em_conta(conta_id) as s:
        f = s.query(Formulario).filter(Formulario.padrao_nps.is_(True)).one()
        contato = s.get(Contato, cliente["contato"]["id"])
        gravar_resposta(s, f, {f.perguntas[0]["id"]: 1}, "link", variaveis("Alfa"), contato=contato)
    assert caixa_memoria == []
    assert _acao_da_ultima_resposta(client, h)["prioridade"] == "alta"


@pytest.mark.parametrize("ambiente,sai", [("producao", False), ("desenvolvimento", True)])
def test_alerta_so_com_provedor_de_email_configurado(client, cliente, monkeypatch, capsys, ambiente, sai):
    """Mesma regra dos envios de pesquisa: o `console` não conta em produção (o comentário e os dados do cliente
    iriam parar no log). A ação é criada do mesmo jeito."""
    from toqqi.core.config import config

    monkeypatch.setattr(config(), "EMAIL_PROVIDER", "console")
    monkeypatch.setattr(config(), "AMBIENTE", ambiente)
    capsys.readouterr()
    registrar_resposta(client, cliente["h"], cliente["contato"]["id"], 0, comentario="Comentário sigiloso")
    saida = capsys.readouterr().out
    assert ("Alerta de risco: Atacado Norte deu nota 0" in saida) is sai
    assert ("Comentário sigiloso" in saida) is sai
    a = _acao_da_ultima_resposta(client, cliente["h"])
    assert a["prioridade"] == "alta" and a["responsavel"]["nome"] == "Rita Gomes"


# ---- quadro -----------------------------------------------------------------

def test_quadro_ordem_selos_e_totais(client, cliente):
    h = cliente["h"]
    d = lambda n: (hoje() + timedelta(days=n)).isoformat()  # noqa: E731
    sem_prazo = _criar(client, h, titulo="Sem prazo", prioridade="alta")
    amanha = _criar(client, h, titulo="Amanhã", prazo=d(1))
    vencida_baixa = _criar(client, h, titulo="Vencida baixa", prazo=d(-1), prioridade="baixa")
    hoje_media = _criar(client, h, titulo="Hoje média", prazo=d(0))
    hoje_alta = _criar(client, h, titulo="Hoje alta", prazo=d(0), prioridade="alta")
    vencida_antiga = _criar(client, h, titulo="Vencida antiga", prazo=d(-5), prioridade="baixa")
    longe = _criar(client, h, titulo="Longe", prazo=d(30))
    andamento = _criar(client, h, titulo="Andamento vencida", prazo=d(-2))
    client.patch(f"{API}/acoes/{andamento['id']}", headers=h, json={"situacao": "em_andamento"})
    q = quadro(client, h)
    a_fazer = q["colunas"]["a_fazer"]
    assert [x["titulo"] for x in a_fazer] == ["Vencida antiga", "Vencida baixa", "Hoje alta", "Hoje média",
                                              "Amanhã", "Longe", "Sem prazo"]
    selos = {x["titulo"]: x["prazo_selo"] for x in a_fazer}
    assert selos == {"Vencida antiga": "vencido", "Vencida baixa": "vencido", "Hoje alta": "hoje",
                     "Hoje média": "hoje", "Amanhã": "amanha", "Longe": None, "Sem prazo": None}
    assert [x["titulo"] for x in q["colunas"]["em_andamento"]] == ["Andamento vencida"]
    assert q["totais"] == {"a_fazer": 7, "em_andamento": 1, "concluida": 0, "vencidas": 3}
    so_vencidas = quadro(client, h, so_vencidas="true")
    assert [x["titulo"] for x in so_vencidas["colunas"]["a_fazer"]] == ["Vencida antiga", "Vencida baixa"]
    assert so_vencidas["totais"]["vencidas"] == 3
    assert {sem_prazo["id"], amanha["id"], vencida_baixa["id"], hoje_media["id"], hoje_alta["id"],
            vencida_antiga["id"], longe["id"]} == {x["id"] for x in a_fazer}


def test_quadro_mostra_15_concluidas_e_lista_todas(client, cliente):
    h = cliente["h"]
    ids = []
    for i in range(17):
        a = _criar(client, h, titulo=f"Concluída {i}", responsavel_id=cliente["rita"]["id"])
        r = client.patch(f"{API}/acoes/{a['id']}", headers=h, json={"situacao": "concluida", "resolucao": "Feito"})
        assert r.status_code == 200, r.text
        ids.append(a["id"])
    q = quadro(client, h)
    assert [x["id"] for x in q["colunas"]["concluida"]] == list(reversed(ids))[:15]
    assert q["totais"]["concluida"] == 17
    r = client.get(f"{API}/acoes", headers=h, params={"situacao": "concluida", "por_pagina": 10, "pagina": 2})
    d = r.json()
    assert d["total"] == 17 and [x["id"] for x in d["itens"]] == list(reversed(ids))[10:]


# ---- mover e concluir -------------------------------------------------------

def test_mover_e_concluir(client, cliente):
    h = cliente["h"]
    a = _criar(client, h, titulo="Ligar para a Paula")
    url = f"{API}/acoes/{a['id']}"
    assert a["responsavel"] is None and a["iniciada_em"] is None
    x = client.patch(url, headers=h, json={"situacao": "em_andamento"}).json()
    assert x["situacao"] == "em_andamento" and x["iniciada_em"] and x["atualizada_em"] > a["atualizada_em"]
    iniciada = x["iniciada_em"]

    r = client.patch(url, headers=h, json={"situacao": "concluida"})
    assert r.status_code == 422
    assert r.json()["erro"]["campos"] == {"responsavel_id": "Escolha o responsável antes de concluir.",
                                          "resolucao": "Conte o que foi feito para concluir."}
    r = client.patch(url, headers=h, json={"situacao": "concluida", "resolucao": "  "})
    assert set(r.json()["erro"]["campos"]) == {"responsavel_id", "resolucao"}
    r = client.patch(url, headers=h, json={"situacao": "concluida", "responsavel_id": cliente["rita"]["id"]})
    assert r.json()["erro"]["campos"] == {"resolucao": "Conte o que foi feito para concluir."}
    assert client.get(url, headers=h).json()["situacao"] == "em_andamento"  # nada mudou
    r = client.patch(url, headers=h, json={"situacao": "concluida", "resolucao": "Liguei e combinamos a troca",
                                           "responsavel_id": cliente["rita"]["id"]})
    assert r.status_code == 200, r.text
    x = r.json()
    assert x["situacao"] == "concluida" and x["concluida_em"]
    assert x["concluida_por"] == {"id": cliente_usuario(client, h), "nome": "Pessoa"}
    assert x["prazo_selo"] is None
    # já concluída: tirar o responsável não pode
    r = client.patch(url, headers=h, json={"responsavel_id": None})
    assert r.status_code == 422 and "responsavel_id" in r.json()["erro"]["campos"]
    # reabrir limpa a conclusão e mantém o início
    x = client.patch(url, headers=h, json={"situacao": "a_fazer"}).json()
    assert (x["concluida_em"], x["concluida_por"], x["iniciada_em"]) == (None, None, iniciada)
    x = client.patch(url, headers=h, json={"situacao": "em_andamento"}).json()
    assert x["iniciada_em"] == iniciada
    # direto de a fazer para concluída também vale (com os dois campos)
    b = _criar(client, h, titulo="Outra", empresa_id=cliente["empresa"]["id"])
    assert b["responsavel"]["id"] == cliente["rita"]["id"]  # responsável da empresa
    x = client.patch(f"{API}/acoes/{b['id']}", headers=h, json={"situacao": "concluida", "resolucao": "ok"}).json()
    assert x["situacao"] == "concluida" and x["iniciada_em"] is None


def cliente_usuario(client, h) -> int:
    return client.get(f"{API}/eu", headers=h).json()["usuario"]["id"]


def test_editar_campos_e_limpar(client, cliente):
    h = cliente["h"]
    a = _criar(client, h, titulo="Visitar", descricao="Levar amostras", prazo=hoje().isoformat(),
               empresa_id=cliente["empresa"]["id"], prioridade="baixa")
    url = f"{API}/acoes/{a['id']}"
    x = client.patch(url, headers=h, json={"titulo": "  Visitar o cliente  ", "prioridade": "alta",
                                           "resolucao": "Em contato"}).json()
    assert (x["titulo"], x["prioridade"], x["resolucao"]) == ("Visitar o cliente", "alta", "Em contato")
    x = client.patch(url, headers=h, json={"descricao": None, "prazo": None, "empresa_id": None,
                                           "responsavel_id": None, "titulo": None}).json()
    assert (x["descricao"], x["prazo"], x["empresa"], x["responsavel"], x["titulo"]) == (
        "", None, None, None, "Visitar o cliente")
    for corpo, campo in [({"titulo": ""}, "titulo"), ({"titulo": "x" * 201}, "titulo"),
                         ({"prioridade": "urgente"}, "prioridade"), ({"situacao": "feita"}, "situacao"),
                         ({"responsavel_id": 9999}, "responsavel_id"), ({"empresa_id": 9999}, "empresa_id"),
                         ({"descricao": "x" * 4001}, "descricao"), ({"prazo": "31/12/2026"}, "prazo")]:
        r = client.patch(url, headers=h, json=corpo)
        assert r.status_code == 422 and campo in r.json()["erro"]["campos"], corpo
    assert client.patch(f"{API}/acoes/9999", headers=h, json={"titulo": "x"}).status_code == 404


# ---- criar, listar, excluir ---------------------------------------------------

def test_criar_manual(client, cliente):
    h = cliente["h"]
    resposta = registrar_resposta(client, h, cliente["contato"]["id"], 6).json()
    a = _criar(client, h, titulo="Ligar e entender", resposta_id=resposta["id"], prazo="2026-12-01")
    assert (a["origem"], a["prioridade"], a["situacao"]) == ("manual", "media", "a_fazer")
    assert a["empresa"]["id"] == cliente["empresa"]["id"]  # da resposta
    assert a["contato"]["id"] == cliente["contato"]["id"]
    assert a["responsavel"]["id"] == cliente["rita"]["id"]  # da empresa
    assert (a["grupo"], a["tipo_nota"], a["nota"]) == ("detrator", "nps", 6)
    assert a["criado_por"]["id"] == cliente_usuario(client, h)
    assert a["resposta"]["id"] == resposta["id"] and a["resposta"]["grupo"] == "detrator"
    outro = criar_responsavel(client, h, "Beto")
    b = _criar(client, h, titulo="Com outro", empresa_id=cliente["empresa"]["id"], responsavel_id=outro["id"])
    assert b["responsavel"]["id"] == outro["id"]
    solta = _criar(client, h, titulo="Solta")
    assert (solta["empresa"], solta["contato"], solta["responsavel"], solta["resposta"], solta["grupo"]) == (
        None, None, None, None, None)
    for corpo, campo in [({"titulo": "   "}, "titulo"), ({"empresa_id": 999}, "empresa_id"),
                         ({"contato_id": 999}, "contato_id"), ({"resposta_id": 999}, "resposta_id"),
                         ({"responsavel_id": 999}, "responsavel_id"), ({"prioridade": "x"}, "prioridade")]:
        r = client.post(f"{API}/acoes", headers=h, json={"titulo": "Ok", **corpo})
        assert r.status_code == 422 and campo in r.json()["erro"]["campos"], corpo
    assert client.post(f"{API}/acoes", headers=h, json={}).status_code == 422


def test_lista_e_filtros(client, admin):
    h = admin["h"]
    g = client.post(f"{API}/cadastros/grupos", headers=h, json={"nome": "Rede Leste"}).json()
    rita = criar_responsavel(client, h, "Rita")
    e1 = criar_empresa(client, h, "Atacado Norte", grupo_id=g["id"], responsavel_id=rita["id"])
    e2 = criar_empresa(client, h, "Mercado Sul")
    c1 = criar_contato(client, h, nome="Paula", empresa_id=e1["id"])
    c2 = criar_contato(client, h, nome="Marcos", empresa_id=e2["id"])
    registrar_resposta(client, h, c1["id"], 2)    # automática, detrator, empresa 1, responsável Rita
    registrar_resposta(client, h, c2["id"], 7)    # automática, neutro, empresa 2, sem responsável
    responder_convite(client, h, c2["id"], 1, formulario=form_padrao(client, h, "csat"))  # CSAT
    _criar(client, h, titulo="Revisar tabela de preços", prazo=(hoje() - timedelta(days=1)).isoformat())

    def titulos(**f):
        r = client.get(f"{API}/acoes", headers=h, params=f)
        assert r.status_code == 200, r.text
        return sorted(x["titulo"] for x in r.json()["itens"])

    assert len(titulos()) == 4
    assert titulos(categoria="detrator") == ["[Detrator NPS 2] Ação requerida: Atacado Norte"]
    assert titulos(tipo_nota="csat") == ["[CSAT 1] Cliente insatisfeito: Mercado Sul"]
    assert titulos(responsavel_id=rita["id"]) == ["[Detrator NPS 2] Ação requerida: Atacado Norte"]
    assert len(titulos(responsavel_id=0)) == 3
    assert titulos(empresa_id=e2["id"]) == ["[CSAT 1] Cliente insatisfeito: Mercado Sul",
                                            "[Neutro NPS 7] Ação requerida: Mercado Sul"]
    assert titulos(grupo_id=g["id"]) == ["[Detrator NPS 2] Ação requerida: Atacado Norte"]
    assert titulos(busca="preços") == ["Revisar tabela de preços"]
    assert titulos(busca="paula") == ["[Detrator NPS 2] Ação requerida: Atacado Norte"]  # nome do contato
    assert titulos(busca="sul") == ["[CSAT 1] Cliente insatisfeito: Mercado Sul",
                                    "[Neutro NPS 7] Ação requerida: Mercado Sul"]
    assert titulos(so_vencidas="true") == ["Revisar tabela de preços"]
    assert len(titulos(de=hoje().isoformat(), ate=hoje().isoformat())) == 4
    assert titulos(ate=(hoje() - timedelta(days=1)).isoformat()) == []
    assert titulos(situacao="em_andamento") == []
    assert client.get(f"{API}/acoes", headers=h, params={"situacao": "x"}).status_code == 422
    assert client.get(f"{API}/acoes/quadro", headers=h, params={"de": "ontem"}).status_code == 422


def test_excluir_e_permissoes(client, cliente):
    h = cliente["h"]
    consulta = membro(client, h, "caio@alfa.com.br", "consulta")
    gestor = membro(client, h, "gil@alfa.com.br", "gestor")
    hc, hg = consulta["h"], gestor["h"]
    # consulta cria e move, mas não exclui
    a = _criar(client, hc, titulo="Criada pela consulta")
    assert a["criado_por"]["nome"] == "Membro consulta"
    assert client.patch(f"{API}/acoes/{a['id']}", headers=hc, json={"situacao": "em_andamento"}).status_code == 200
    assert client.get(f"{API}/acoes/quadro", headers=hc).status_code == 200
    assert client.get(f"{API}/acoes/configuracao", headers=hc).status_code == 200
    assert client.delete(f"{API}/acoes/{a['id']}", headers=hc).status_code == 403
    assert client.put(f"{API}/acoes/configuracao", headers=hg, json={"prazo_neutro": 3}).status_code == 403
    assert client.delete(f"{API}/acoes/{a['id']}", headers=hg).status_code == 204
    assert client.get(f"{API}/acoes/{a['id']}", headers=h).status_code == 404
    assert client.delete(f"{API}/acoes/{a['id']}", headers=hg).status_code == 404
    ev = next(i for i in client.get(f"{API}/auditoria", headers=h).json()["itens"] if i["evento"] == "acao_excluida")
    assert ev["detalhe"] == {"acao_id": a["id"], "titulo": "Criada pela consulta"}
    assert ev["usuario"]["nome"] == "Membro gestor" and ev["rotulo"] == "Plano de ação excluído"
    # sem acoes.ver
    client.put(f"{API}/equipe/permissoes", headers=h, json={"gestor": [], "consulta": []})
    assert client.get(f"{API}/acoes/quadro", headers=hc).status_code == 403
    assert client.post(f"{API}/acoes", headers=hc, json={"titulo": "x"}).status_code == 403


def test_configuracao(client, admin):
    h = admin["h"]
    assert client.get(f"{API}/acoes/configuracao", headers=h).json() == {
        "prazo_detrator": 2, "prazo_neutro": 5, "prazo_promotor": 7, "acao_promotor": False}
    for corpo in ({"prazo_detrator": 0}, {"prazo_neutro": 91}, {"prazo_promotor": "x"}):
        r = client.put(f"{API}/acoes/configuracao", headers=h, json=corpo)
        assert r.status_code == 422, corpo
    r = client.put(f"{API}/acoes/configuracao", headers=h, json={"prazo_neutro": 90})
    assert r.json()["prazo_neutro"] == 90 and r.json()["prazo_detrator"] == 2
    r = client.put(f"{API}/acoes/configuracao", headers=h, json={"prazo_detrator": 0})
    assert r.json()["erro"]["campos"] == {"prazo_detrator": "Use um prazo de 1 a 90 dias."}
    client.put(f"{API}/acoes/configuracao", headers=h, json={"prazo_neutro": 90})  # sem mudança: sem auditoria
    eventos_ = [i for i in client.get(f"{API}/auditoria", headers=h).json()["itens"] if i["evento"] == "config_acoes"]
    assert len(eventos_) == 1 and eventos_[0]["detalhe"] == {"campos": ["prazo_neutro"]}
    c = criar_contato(client, h)
    registrar_resposta(client, h, c["id"], 8)
    assert _acao_da_ultima_resposta(client, h)["prazo"] == (hoje() + timedelta(days=90)).isoformat()


def test_link_direto_e_formulario_personalizado(client, admin):
    h = admin["h"]
    assert client.get(f"{API}/acoes/12345", headers=h).status_code == 404
    f = criar_form(client, h, [{"tipo": "comentario", "titulo": "Diga", "obrigatoria": True}])
    responder_link(client, f["codigo_publico"], {f["perguntas"][0]["id"]: "Péssimo"})
    assert quadro(client, h)["totais"]["a_fazer"] == 0  # sem nota, sem ação
    token = link_pesquisa(client, h, criar_contato(client, h)["id"], formulario_id=f["id"])
    assert token


def test_excluir_cadastros_mantem_acoes(client, cliente):
    """Usuário, contato, empresa e responsável excluídos: as ações ficam, sem a referência (SET NULL)."""
    h = cliente["h"]
    gestor = membro(client, h, "gil@alfa.com.br", "gestor")
    resposta = registrar_resposta(client, gestor["h"], cliente["contato"]["id"], 3).json()
    client.patch(f"{API}/respostas/{resposta['id']}", headers=gestor["h"], json={"o_que_faltou": "Retorno"})
    a = _criar(client, gestor["h"], titulo="Manual", responsavel_id=cliente["rita"]["id"])
    client.patch(f"{API}/acoes/{a['id']}", headers=gestor["h"], json={"situacao": "concluida", "resolucao": "ok"})
    assert client.delete(f"{API}/equipe/{gestor['usuario']['id']}", headers=h).status_code == 204
    r = client.get(f"{API}/respostas/{resposta['id']}", headers=h).json()
    assert r["registrada_por"] is None and r["analisada_por"] is None
    x = client.get(f"{API}/acoes/{a['id']}", headers=h).json()
    assert (x["criado_por"], x["concluida_por"], x["situacao"]) == (None, None, "concluida")
    automatica = resposta["acao"]["id"]
    assert client.delete(f"{API}/responsaveis/{cliente['rita']['id']}", headers=h).status_code == 204
    assert client.delete(f"{API}/contatos/{cliente['contato']['id']}", headers=h).status_code == 204  # e as respostas
    assert client.delete(f"{API}/empresas/{cliente['empresa']['id']}", headers=h).status_code == 204
    x = client.get(f"{API}/acoes/{automatica}", headers=h).json()
    assert (x["responsavel"], x["contato"], x["empresa"], x["resposta"]) == (None, None, None, None)
    assert x["titulo"] == "[Detrator NPS 3] Ação requerida: Atacado Norte" and x["nota"] == 3


def test_alerta_tambem_pelo_link_publico(client, cliente):
    """O link público identifica o contato pelo e-mail informado; a ação alta alerta o responsável."""
    h = cliente["h"]
    f = criar_form(client, h, [{"tipo": "nps", "titulo": "Nota", "obrigatoria": True},
                               {"tipo": "texto_curto", "titulo": "Seu e-mail", "formato": "email"}])
    p = [x["id"] for x in f["perguntas"]]
    caixa_memoria.clear()
    assert responder_link(client, f["codigo_publico"], {p[0]: 4, p[1]: "paula@norte.com.br"}).status_code == 201
    m, = emails_para("rita@alfa.com.br")
    assert m.assunto == "Alerta de risco: Atacado Norte deu nota 4"
    a = _acao_da_ultima_resposta(client, h)
    assert a["descricao"].startswith("Comentário do cliente: (sem comentário)\nContato: Paula Lima")


def test_openapi_gera(client):
    r = client.get(f"{API}/openapi.json")
    assert r.status_code == 200
    caminhos = r.json()["paths"]
    for caminho in ("/api/v1/respostas", "/api/v1/respostas/{resposta_id}", "/api/v1/respostas.csv",
                    "/api/v1/respostas/temas", "/api/v1/acoes/quadro", "/api/v1/acoes/configuracao",
                    "/api/v1/acoes/{acao_id}", "/api/v1/painel", "/api/v1/painel/exportar.csv"):
        assert caminho in caminhos, caminho

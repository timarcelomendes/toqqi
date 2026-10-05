"""Etapa 5h, visão do negócio (docs/api-etapa-5h.md §5): GET /plataforma/visao (superadmin; 403 para os outros) com
os totais por situação (com `pausada`), pagantes e receita só das assinaturas ativas do ambiente atual do Asaas, novas
em 7 e 30 dias, a conversão do teste (contas de 60 a 15 dias atrás que criaram assinatura, mesmo cancelada), os testes
acabando em 7 dias (sem quem já assinou), a lista das contas (uso, ativação, IA do mês, assinatura) sem nomes de
contatos e sem N+1 (o número de consultas não muda com o de contas)."""
from datetime import datetime, time, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import event
from util import API, CHAVE_ASAAS, conta_pronta, criar_contato, ligar_envios, link_pesquisa, membro, sql, superadmin

from toqqi.core import relogio
from toqqi.core.config import config
from toqqi.core.db import engine
from toqqi.modulos.plataforma import visao as visao_mod

HOJE = datetime.now(relogio.FUSO).date()


def _ao_meio_dia(dias: int) -> datetime:
    return datetime.combine(HOJE + timedelta(days=dias), time(12), tzinfo=relogio.FUSO)


def _conta(client, dono, email: str, empresa: str, situacao: str = "teste", criada_dias: int = 1,
           teste_dias: int | None = 14, **campos) -> dict:
    """Conta cadastrada pelo site e ajustada no banco: situação, criada há `criada_dias` dias e teste até o meio-dia
    de hoje + `teste_dias` (None = sem teste)."""
    a = conta_pronta(client, email, empresa=empresa)
    cid = a["conta"]["id"]
    teste_ate = _ao_meio_dia(teste_dias) if teste_dias is not None else None
    sql(dono, "update contas set situacao = :s, criada_em = now() - make_interval(days => :d), teste_ate = :t "
              "where id = :c", s=situacao, d=criada_dias, t=teste_ate, c=cid)
    for coluna, valor in campos.items():
        sql(dono, f"update contas set {coluna} = :v where id = :c", v=valor, c=cid)
    return {**a, "id": cid}


def _assinatura(dono, conta_id: int, valor: str, plano: str = "profissional", ambiente: str = "sandbox",
                situacao: str = "ativa") -> None:
    sql(dono, """insert into assinaturas (conta_id, asaas_id, ambiente, plano, valor, situacao, razao_social,
                 documento, email_cobranca, telefone, primeiro_vencimento, cancelada_em)
                 values (:c, :a, :amb, :p, :v, :s, 'Razão Ltda', '11222333000181', 'fin@x.com.br', '5511987654321',
                         current_date, case when :s = 'cancelada' then now() end)""",
        c=conta_id, a=f"sub_{conta_id}_{ambiente}_{situacao}", amb=ambiente, p=plano, v=valor, s=situacao)


@pytest.fixture
def sandbox(monkeypatch):
    """A chave do Asaas de sandbox: o ambiente atual é `sandbox`."""
    monkeypatch.setattr(config(), "ASAAS_API_KEY", CHAVE_ASAAS)


@pytest.fixture
def cenario(client, dono, sandbox):
    root = superadmin(client)
    sql(dono, "update contas set situacao = 'cortesia', teste_ate = null, criada_em = now() - interval '200 days' "
              "where id = :c", c=root["conta"]["id"])
    alfa = _conta(client, dono, "ana@alfa.com.br", "Alfa", teste_dias=3, criada_dias=11)
    h = alfa["h"]
    c1 = criar_contato(client, h, nome="Carlos Souza", email="carlos@cliente.com.br")
    criar_contato(client, h, nome="Débora Lima", email="debora@cliente.com.br")
    c3 = criar_contato(client, h, nome="Élio Inativo", email="elio@cliente.com.br")
    sql(dono, "update contatos set ativo = false where id = :c", c=c3["id"])
    ligar_envios(client, h)
    for _ in range(2):
        link_pesquisa(client, h, c1["id"])
    link_pesquisa(client, h, c3["id"])
    sql(dono, "update convites set criado_em = now() - interval '40 days' where contato_id = :c", c=c3["id"])
    sql(dono, "insert into envios (conta_id, contato_id, canal, tipo, origem, situacao, para) "
              "values (:a, :c, 'email', 'convite', 'manual', 'enviado', 'carlos@cliente.com.br')",
        a=alfa["id"], c=c1["id"])
    r = client.post(f"{API}/respostas", headers=h, json={"contato_id": c1["id"], "nota": 9})
    assert r.status_code == 201, r.text
    r = client.post(f"{API}/respostas", headers=h, json={"contato_id": c1["id"], "nota": 4})
    assert r.status_code == 201, r.text
    sql(dono, "update respostas set criada_em = now() - interval '45 days' where id = :r", r=r.json()["id"])
    sql(dono, "insert into ia_uso_mensal (conta_id, mes, analises) values (:c, :m, 7), (:c, :antes, 50)",
        c=alfa["id"], m=HOJE.replace(day=1), antes=(HOJE.replace(day=1) - timedelta(days=1)).replace(day=1))
    membro(client, h, "bruno@alfa.com.br", perfil="admin")  # o administrador mais antigo continua sendo a Ana

    beta = _conta(client, dono, "bia@beta.com.br", "Beta", teste_dias=10, criada_dias=4)
    gama = _conta(client, dono, "gui@gama.com.br", "Gama", teste_dias=2, criada_dias=12)
    _assinatura(dono, gama["id"], "149.00", plano="essencial")  # assinou no teste: fora de "testes acabando"
    delta = _conta(client, dono, "davi@delta.com.br", "Delta", situacao="ativa", teste_dias=-20, criada_dias=40)
    _assinatura(dono, delta["id"], "349.00")
    eta = _conta(client, dono, "eva@eta.com.br", "Eta", situacao="atrasada", teste_dias=-30, criada_dias=50,
                 atrasada_desde=HOJE - timedelta(days=3))
    _assinatura(dono, eta["id"], "149.00", plano="essencial")
    teta = _conta(client, dono, "teo@teta.com.br", "Teta", situacao="atrasada", teste_dias=-60, criada_dias=90,
                  atrasada_desde=HOJE - timedelta(days=20))
    _assinatura(dono, teta["id"], "799.00", plano="empresa")
    iota = _conta(client, dono, "ivo@iota.com.br", "Iota", situacao="teste_expirado", teste_dias=-5, criada_dias=20)
    kapa = _conta(client, dono, "kai@kapa.com.br", "Kapa", situacao="cancelada", teste_dias=-10, criada_dias=30)
    _assinatura(dono, kapa["id"], "349.00", situacao="cancelada")  # assinou e cancelou: conta na conversão
    lam = _conta(client, dono, "lia@lambda.com.br", "Lambda", situacao="ativa", teste_dias=-40, criada_dias=70)
    _assinatura(dono, lam["id"], "999.00", ambiente="producao")  # de outro ambiente: não conta
    return {"root": root, "alfa": alfa, "beta": beta, "gama": gama, "delta": delta, "eta": eta, "teta": teta,
            "iota": iota, "kapa": kapa, "lambda": lam}


def _visao(client, h) -> dict:
    r = client.get(f"{API}/plataforma/visao", headers=h)
    assert r.status_code == 200, r.text
    return r.json()


def test_totais_receita_e_novas(client, cenario):
    v = _visao(client, cenario["root"]["h"])
    assert set(v) == {"gerado_em", "totais", "conversao", "testes_acabando", "contas", "origens", "teste"}  # origens: 5i; teste: melhoria 9
    assert v["totais"] == {
        "contas": 10,
        "por_situacao": {"teste": 3, "teste_expirado": 1, "ativa": 2, "atrasada": 1, "pausada": 1, "cancelada": 1,
                         "cortesia": 1},
        "pagantes": 4,  # Gama, Delta, Eta e Teta (a de produção, da Lambda, não conta com a chave de sandbox)
        "receita_mensal": 1446.0,  # 149 + 349 + 149 + 799
        "ambiente": "sandbox",
        "novas_7d": 1,  # Beta
        "novas_30d": 4,  # Alfa, Beta, Gama e Iota (a Kapa, criada há 30 dias, já passou)
    }


def test_receita_sem_chave_vale_todos_os_ambientes(client, cenario, monkeypatch):
    monkeypatch.setattr(config(), "ASAAS_API_KEY", "")
    t = _visao(client, cenario["root"]["h"])["totais"]
    assert (t["pagantes"], t["receita_mensal"], t["ambiente"]) == (5, 2445.0, None)


def test_receita_e_decimal_no_servico(cenario):
    assert visao_mod.visao()["totais"]["receita_mensal"] == Decimal("1446.00")


def test_conversao_do_teste(client, cenario, dono):
    # janela: criadas entre 60 e 15 dias atrás, com teste. Delta (40, assinou), Eta (50, assinou), Iota (20, não),
    # Kapa (30, assinou e cancelou). Fora: Alfa (11), Gama (12), Beta (4), Lambda (70), Teta (90), Toqqi (cortesia).
    # Uma cortesia criada pela Plataforma dentro da janela (sem teste) não entra.
    sql(dono, "insert into contas (nome, situacao, criada_em, teste_ate) values ('Cortesia', 'cortesia', "
              "now() - interval '30 days', null)")
    c = _visao(client, cenario["root"]["h"])["conversao"]
    assert c == {"de": (HOJE - timedelta(days=60)).isoformat(), "ate": (HOJE - timedelta(days=15)).isoformat(),
                 "contas": 4, "assinaram": 3, "taxa": 0.75}


def test_conversao_sem_contas_no_periodo(client, dono):
    root = superadmin(client)
    c = _visao(client, root["h"])["conversao"]
    assert (c["contas"], c["assinaram"], c["taxa"]) == (0, 0, None)


def test_testes_acabando(client, cenario, dono):
    v = _visao(client, cenario["root"]["h"])
    alfa = cenario["alfa"]
    ultimo_acesso = sql(dono, "select max(ultimo_acesso) from usuarios where conta_id = :c", c=alfa["id"])[0][0]
    (item,) = v["testes_acabando"]  # Beta (10 dias) e Gama (assinou no teste) ficam de fora
    assert set(item) == {"id", "nome", "email", "teste_ate", "dias", "ultimo_acesso", "ativacao"}
    assert {k: item[k] for k in ("id", "nome", "email", "dias", "ativacao")} == {
        "id": alfa["id"], "nome": "Alfa", "email": "ana@alfa.com.br", "dias": 3,
        "ativacao": {"contatos": True, "envios_ligados": True, "primeiro_envio": True, "primeira_resposta": True}}
    assert datetime.fromisoformat(item["teste_ate"]) == _ao_meio_dia(3)
    assert datetime.fromisoformat(item["ultimo_acesso"]) == ultimo_acesso
    # o fim do teste hoje (meio-dia que ainda não passou, ou amanhã cedo) também entra, com 0 ou 1 dia
    sql(dono, "update contas set teste_ate = now() + interval '1 hour' where id = :c", c=cenario["beta"]["id"])
    nomes = [(x["nome"], x["dias"]) for x in _visao(client, cenario["root"]["h"])["testes_acabando"]]
    assert nomes[0][0] == "Beta" and nomes[0][1] in (0, 1) and nomes[1] == ("Alfa", 3)


def test_lista_das_contas(client, cenario):
    v = _visao(client, cenario["root"]["h"])
    contas = {c["nome"]: c for c in v["contas"]}
    assert [c["nome"] for c in v["contas"]] == ["Beta", "Alfa", "Gama", "Iota", "Kapa", "Delta", "Eta", "Lambda",
                                                "Teta", "Toqqi"]  # das mais novas às mais antigas
    alfa = contas["Alfa"]
    assert set(alfa) == {"id", "nome", "situacao", "plano", "criada_em", "teste_ate", "ultimo_acesso", "usuarios",
                         "admin_email", "contatos_ativos", "convites_30d", "respostas_30d", "respostas_total",
                         "ativacao", "ia_analises_mes", "assinatura", "origem"}
    assert {k: alfa[k] for k in ("situacao", "plano", "usuarios", "admin_email", "contatos_ativos", "convites_30d",
                                 "respostas_30d", "respostas_total", "ia_analises_mes", "assinatura")} == {
        "situacao": "teste", "plano": "profissional", "usuarios": 2, "admin_email": "ana@alfa.com.br",
        "contatos_ativos": 2, "convites_30d": 2, "respostas_30d": 1, "respostas_total": 2, "ia_analises_mes": 7,
        "assinatura": None}
    assert alfa["ativacao"] == {"contatos": True, "envios_ligados": True, "primeiro_envio": True,
                                "primeira_resposta": True}
    assert contas["Beta"]["ativacao"] == {"contatos": False, "envios_ligados": False, "primeiro_envio": False,
                                          "primeira_resposta": False}
    assert (contas["Beta"]["contatos_ativos"], contas["Beta"]["respostas_total"], contas["Beta"]["ia_analises_mes"],
            contas["Beta"]["usuarios"]) == (0, 0, 0, 1)
    assert contas["Teta"]["situacao"] == "pausada" and contas["Eta"]["situacao"] == "atrasada"
    assert contas["Delta"]["assinatura"] == {"plano": "profissional", "valor": 349.0}
    assert contas["Lambda"]["assinatura"] is None  # a de produção não existe para a chave de sandbox
    assert contas["Kapa"]["assinatura"] is None and contas["Toqqi"]["situacao"] == "cortesia"
    assert contas["Toqqi"]["admin_email"] == "root@toqqi.com" and contas["Toqqi"]["teste_ate"] is None


def test_sem_dados_de_contatos(client, cenario):
    texto = client.get(f"{API}/plataforma/visao", headers=cenario["root"]["h"]).text
    for dado in ("Carlos", "Débora", "Élio", "@cliente.com.br"):
        assert dado not in texto


def test_sem_n_mais_1(client, cenario):
    consultas: list[str] = []

    def contar(_c, _cur, instrucao, *_a):
        consultas.append(instrucao)

    event.listen(engine(), "before_cursor_execute", contar)
    try:
        visao_mod.visao()
        antes = len(consultas)
        for i in range(4):
            a = conta_pronta(client, f"nova{i}@omega{i}.com.br", empresa=f"Ômega {i}")
            criar_contato(client, a["h"])
        consultas.clear()
        v = visao_mod.visao()
        assert len(v["contas"]) == 14
        assert len(consultas) == antes
    finally:
        event.remove(engine(), "before_cursor_execute", contar)


def test_so_superadmin(client, cenario):
    for h in (cenario["alfa"]["h"],):
        r = client.get(f"{API}/plataforma/visao", headers=h)
        assert r.status_code == 403 and r.json()["erro"]["codigo"] == "sem_permissao"
    assert client.get(f"{API}/plataforma/visao").status_code == 401


def test_situacao_exibida():
    from toqqi.modelos import Conta

    agora = datetime.now(relogio.FUSO)
    na_carencia = Conta(situacao="atrasada", atrasada_desde=HOJE - timedelta(days=7))
    passou = Conta(situacao="atrasada", atrasada_desde=HOJE - timedelta(days=8))
    assert visao_mod.situacao_exibida(na_carencia, agora) == "atrasada"
    assert visao_mod.situacao_exibida(passou, agora) == "pausada"
    assert visao_mod.situacao_exibida(Conta(situacao="ativa"), agora) == "ativa"


def test_tempo_do_teste_ate_a_primeira_resposta(client, cenario, dono):
    """Melhoria 9: janela de 90 a 14 dias — Delta (40), Eta (50), Iota (20), Kapa (30) e Lambda (70). Iota responde
    no 3º dia, Delta no 10º; a de Eta foi importada (não conta)."""
    from util import form_padrao, inserir_resposta

    def resposta(conta: dict, dias: int, origem: str = "pesquisa") -> None:
        f = form_padrao(client, conta["h"])["id"]
        rid = inserir_resposta(dono, conta["id"], f, None, 9, HOJE)
        sql(dono, "update respostas set origem = :o, criada_em = (select criada_em from contas where id = :c) "
                  "+ make_interval(days => :d) where id = :r", o=origem, c=conta["id"], d=dias, r=rid)

    resposta(cenario["iota"], 3)
    resposta(cenario["delta"], 10)
    resposta(cenario["eta"], 1, origem="importacao")
    t = _visao(client, cenario["root"]["h"])["teste"]
    assert (t["contas"], t["chegaram"], t["ate_7_dias"], t["ate_14_dias"], t["mediana_dias"]) == (5, 2, 1, 2, 6.5)
    # chegaram: Delta (assinou) e Iota (não) → 50%; sem resposta: Eta e Kapa assinaram, Lambda (outro ambiente) não
    assert (t["conversao_com_resposta"], t["conversao_sem_resposta"]) == (0.5, 0.6667)
    assert t["de"] == (HOJE - timedelta(days=90)).isoformat()

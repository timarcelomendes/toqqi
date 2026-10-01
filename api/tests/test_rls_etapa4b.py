"""Etapa 4b: isolamento entre contas (RLS) nas tabelas novas (uso da IA, alertas de pico, resumos semanais), nas
rotas da IA e dos relatórios e nas tarefas que passam por todas as contas."""
from datetime import datetime, time, timedelta

import pytest
from sqlalchemy import text
from sqlalchemy.exc import ProgrammingError
from util import (
    API,
    FUSO,
    conta_pronta,
    criar_contato,
    criar_empresa,
    criar_responsavel,
    fixar_relogio,
    form_padrao,
    lista_respostas,
    registrar_resposta,
    segunda,
    sql,
)

from toqqi import tarefas
from toqqi.core import relogio
from toqqi.core.email import caixa_memoria
from toqqi.modulos.formularios.validacao import grupo_da_nota

TABELAS = ["ia_uso_mensal", "alertas_pico", "resumos_semanais"]
pytestmark = pytest.mark.usefixtures("relogio_estavel")


def _como(c, conta_id: int) -> None:
    c.execute(text("select set_config('app.conta_id', :c, true)"), {"c": str(conta_id)})


def _resposta(dono, x: dict, quando: datetime, nota: int, comentario: str, temas: list[str]) -> int:
    (rid,), = sql(dono, """
        insert into respostas (conta_id, formulario_id, contato_id, empresa_id, canal, origem, nota, tipo_nota, grupo,
                               comentario, comentario_cliente, temas, respondida_em)
        values (:conta, :f, :c, :e, 'manual', 'manual', :n, 'nps', :g, :com, :com, :temas, :quando) returning id
    """, conta=x["conta"]["id"], f=x["nps"], c=x["contato"]["id"], e=(x["contato"].get("empresa") or {}).get("id"),
        n=nota, g=grupo_da_nota("nps", nota), com=comentario, temas=temas, quando=quando)
    return rid


@pytest.fixture
def ab(client, dono):
    a = conta_pronta(client, "ana@alfa.com.br", empresa="Alfa")
    b = conta_pronta(client, "bia@beta.com.br", empresa="Beta")
    hb = b["h"]
    b["nps"] = form_padrao(client, hb)["id"]
    rb = criar_responsavel(client, hb, "Resp B")
    eb = criar_empresa(client, hb, "Empresa B", responsavel_id=rb["id"], valor_mensal="900.00")
    cb = criar_contato(client, hb, nome="Contato B", email="cb@b.com.br", empresa_id=eb["id"])
    b.update(resp=rb, empresa=eb, contato=cb)
    # resposta à mão com comentário: a IA (provedor de testes) analisa depois do commit e conta no uso do mês de B
    r = registrar_resposta(client, hb, cb["id"], 2, comentario="A entrega atrasou de novo")
    assert r.status_code == 201, r.text
    b["resposta"] = r.json()["id"]
    sql(dono, """update respostas set contexto = '{"motorista": "Motorista B"}' where id = :r""", r=b["resposta"])
    # pico de prazo em B: 3 reclamações nos últimos 7 dias
    hoje = relogio.hoje()
    for dias in (1, 2, 3):
        _resposta(dono, b, datetime.combine(hoje - timedelta(days=dias), time(12), tzinfo=FUSO), 1, "Atrasou",
                  ["prazo_entrega"])
    sql(dono, "insert into alertas_pico (conta_id, tema, reclamacoes, media_anterior, destinatarios) "
              "values (:b, 'prazo_entrega', 4, 0, 1)", b=b["conta"]["id"])
    sql(dono, "insert into resumos_semanais (conta_id, semana, destinatarios) values (:b, :s, 1)",
        b=b["conta"]["id"], s=hoje - timedelta(days=hoje.weekday() + 7))
    assert sql(dono, "select analises from ia_uso_mensal where conta_id = :b", b=b["conta"]["id"]) == [(1,)]
    return a, b


def test_tabelas_novas_tem_rls_forcado(dono):
    linhas = sql(dono, """
        select c.relname, c.relrowsecurity, c.relforcerowsecurity,
               (select count(*) from pg_policy p where p.polrelid = c.oid)
          from pg_class c where c.relname = any(:t)
    """, t=TABELAS)
    assert {x[0] for x in linhas} == set(TABELAS)
    for nome, rls, forcado, politicas in linhas:
        assert rls and forcado and politicas == 1, nome


def test_sql_sem_contexto_e_com_outra_conta(ab, app_engine, dono):
    a, b = ab
    for t in TABELAS:
        assert sql(dono, f"select count(*) from {t} where conta_id = :b", b=b["conta"]["id"])[0][0] == 1, t
    with app_engine.connect() as c:
        for t in TABELAS:
            assert c.execute(text(f"select count(*) from {t}")).scalar() == 0, t
    with app_engine.begin() as c:
        _como(c, a["conta"]["id"])
        for t in TABELAS:
            assert c.execute(text(f"select count(*) from {t}")).scalar() == 0, t
            assert c.execute(text(f"delete from {t}")).rowcount == 0, t
        assert c.execute(text("update ia_uso_mensal set analises = 0")).rowcount == 0
        assert c.execute(text("update alertas_pico set detectado_em = now() - interval '30 days'")).rowcount == 0
        assert c.execute(text("update resumos_semanais set enviado_em = null")).rowcount == 0
    for comando in (
        "insert into ia_uso_mensal (conta_id, mes, analises) values (:b, date_trunc('month', now())::date, 999)",
        "insert into alertas_pico (conta_id, tema, reclamacoes, media_anterior) values (:b, 'atendimento', 3, 0)",
        "insert into resumos_semanais (conta_id, semana) values (:b, date_trunc('week', now())::date)",
    ):
        with pytest.raises(ProgrammingError, match="row-level security"):
            with app_engine.begin() as c:
                _como(c, a["conta"]["id"])
                c.execute(text(comando), {"b": b["conta"]["id"]})
    assert sql(dono, "select analises from ia_uso_mensal where conta_id = :b", b=b["conta"]["id"]) == [(1,)]
    assert sql(dono, "select count(*) from alertas_pico")[0][0] == 1


def test_api_de_a_nao_ve_nem_mexe_em_b(client, ab, dono):
    a, b = ab
    h, hb = a["h"], b["h"]
    # IA: o uso e as pendentes são da conta
    ia_a = client.get(f"{API}/conta/ia", headers=h).json()
    assert (ia_a["analises"], ia_a["pendentes"], ia_a["falharam_no_mes"]) == (0, 0, 0)
    assert client.get(f"{API}/conta/ia", headers=hb).json()["analises"] == 1
    sql(dono, "update respostas set ia_situacao = null, ia_temas = null, ia_sentimento = null, ia_resumo = null "
              "where id = :r", r=b["resposta"])
    assert client.post(f"{API}/conta/ia/analisar-recentes", headers=h).json()["marcadas"] == 0
    assert sql(dono, "select ia_situacao from respostas where id = :r", r=b["resposta"]) == [(None,)]
    assert client.post(f"{API}/conta/ia/analisar-recentes", headers=hb).json()["marcadas"] == 4
    assert client.put(f"{API}/conta/ia", headers=h, json={"analise_respostas": False}).status_code == 200
    assert sql(dono, "select count(*) from respostas where ia_situacao = 'pendente'")[0][0] == 4  # as de B seguem
    # filtros novos das respostas
    for filtro in ({"sentimento": "negativo"}, {"reclamacao": "true"}, {"motorista": "Motorista B"}):
        assert lista_respostas(client, h, **filtro)["total"] == 0, filtro
    assert lista_respostas(client, hb, motorista="motorista b")["total"] == 1
    # painel e relatórios de A não veem B
    assert client.get(f"{API}/painel", headers=h).json()["picos"] == []
    assert [p["tema"] for p in client.get(f"{API}/painel", headers=hb).json()["picos"]] == ["prazo_entrega"]
    r = client.get(f"{API}/relatorios/empresas", headers=h).json()
    assert r["resumo"]["empresas"] == 0 and r["itens"] == [] and r["matriz"]["pontos"] == []
    assert r["resumo"]["receita"]["total"] == 0
    g = client.get(f"{API}/relatorios/grupos", headers=h).json()
    assert g["segmentos"] == g["grupos"] == g["prioridades"] == []
    t = client.get(f"{API}/relatorios/temas", headers=h).json()
    assert t["ia"]["com_comentario"] == 0 and t["picos"] == [] and all(x["mencoes"] == 0 for x in t["temas"])
    e = client.get(f"{API}/relatorios/entregas", headers=h).json()
    assert e["itens"] == [] and e["sem_valor"] == 0
    assert client.get(f"{API}/relatorios/responsaveis", headers=h).json()["itens"] == []
    o = client.get(f"{API}/relatorios/operacao", headers=h).json()
    assert o["taxa_resposta"]["convidados"] == 0 and o["sem_resposta"]["total"] == 0
    assert o["acoes"]["abertas"] == 0
    for url in (f"/relatorios/historico/{b['empresa']['id']}", f"/relatorios/historico/{b['empresa']['id']}.csv",
                f"/relatorios/responsaveis/{b['resp']['id']}/empresas"):
        assert client.get(f"{API}{url}", headers=h).status_code == 404, url
    for url in ("/relatorios/empresas.csv", "/relatorios/entregas.csv", "/relatorios/responsaveis.csv",
                "/relatorios/operacao/sem-resposta.csv"):
        assert client.get(f"{API}{url}", headers=h).content.decode("utf-8-sig").count("\r\n") == 1, url
    # B vê os seus
    hist = client.get(f"{API}/relatorios/historico/{b['empresa']['id']}", headers=hb).json()
    assert hist["total"] == 4 and {x["contato"]["nome"] for x in hist["linha_do_tempo"]} == {"Contato B"}
    assert client.get(f"{API}/relatorios/empresas", headers=hb).json()["resumo"]["receita"]["total"] == 900.0


def test_tarefas_de_uma_conta_nao_olham_a_outra(client, dono, monkeypatch):
    fixar_relogio(monkeypatch, segunda(9))  # segunda, 9h: resume a semana anterior
    hoje = relogio.hoje()
    contas = []
    for email, nome in (("ana@alfa.com.br", "Alfa"), ("bia@beta.com.br", "Beta")):
        x = conta_pronta(client, email, empresa=nome)
        sql(dono, "update contas set situacao = 'cortesia' where id = :c", c=x["conta"]["id"])
        x["nps"] = form_padrao(client, x["h"])["id"]
        x["contato"] = criar_contato(client, x["h"], nome=f"Cliente {nome}")
        for dias in (1, 2, 3):  # pico de prazo nas duas (3 reclamações, nenhuma antes) e respostas na semana
            _resposta(dono, x, datetime.combine(hoje - timedelta(days=dias), time(12), tzinfo=FUSO), 2,
                      f"Atrasou ({nome})", ["prazo_entrega"])
        contas.append(x)
    a, b = contas
    ida, idb = a["conta"]["id"], b["conta"]["id"]
    # B já foi alertada de prazo há 2 dias e já teve o resumo desta semana; uma resposta de B espera a IA
    sql(dono, "insert into alertas_pico (conta_id, tema, reclamacoes, media_anterior, detectado_em) "
              "values (:b, 'prazo_entrega', 3, 0, :q)", b=idb, q=relogio.agora() - timedelta(days=2))
    sql(dono, "insert into resumos_semanais (conta_id, semana) values (:b, :s)", b=idb, s=hoje - timedelta(days=7))
    sql(dono, "update respostas set ia_situacao = 'pendente' where conta_id = :b", b=idb)
    caixa_memoria.clear()
    assert tarefas.executar("ia")["ia"] == {"analisadas": 3, "falharam": 0, "limite": 0}
    assert sql(dono, "select conta_id, analises from ia_uso_mensal") == [(idb, 3)]
    assert tarefas.executar("picos")["picos"] == {"picos": 1, "emails": 1}  # só A
    assert tarefas.executar("resumo")["resumo"] == {"contas": 1, "emails": 1}  # só A
    assert [m.para for m in caixa_memoria] == ["ana@alfa.com.br", "ana@alfa.com.br"]
    assert all("Cliente Alfa" in m.texto and "Beta" not in m.texto for m in caixa_memoria)
    assert sql(dono, "select conta_id, count(*) from alertas_pico group by conta_id order by conta_id") == [
        (ida, 1), (idb, 1)]
    assert sql(dono, "select conta_id, destinatarios from resumos_semanais order by conta_id") == [(ida, 1), (idb, 0)]


def test_excluir_conta_leva_as_tabelas_novas(client, ab, dono):
    a, b = ab
    root = conta_pronta(client, "root@toqqi.com", empresa="Toqqi")
    sql(dono, "insert into alertas_pico (conta_id, tema, reclamacoes, media_anterior) values (:a, 'atendimento', 3, 0)",
        a=a["conta"]["id"])
    r = client.request("DELETE", f"{API}/plataforma/contas/{b['conta']['id']}", headers=root["h"],
                       json={"confirmar_nome": "Beta"})
    assert r.status_code == 204, r.text
    for t in TABELAS:
        assert sql(dono, f"select count(*) from {t} where conta_id = :b", b=b["conta"]["id"])[0][0] == 0, t
    assert sql(dono, "select count(*) from alertas_pico where conta_id = :a", a=a["conta"]["id"])[0][0] == 1

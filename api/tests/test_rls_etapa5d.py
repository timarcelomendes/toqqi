"""Etapa 5d: isolamento entre contas (RLS) em `ia_pareceres`, a chave composta do usuário que gerou, as rotas de uma
conta sem ver a outra (inclusive os passos das ações e a espera de 30 s) e a exclusão da conta pela plataforma."""
import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError, ProgrammingError
from util import API, acao, conta_pronta, criar_contato, estado_ia, form_padrao, gerar_ia, inserir_resposta, sql

from toqqi.core import relogio

pytestmark = pytest.mark.usefixtures("relogio_estavel")
TABELAS = ["ia_pareceres"]


def _como(c, conta_id: int) -> None:
    c.execute(text("select set_config('app.conta_id', :c, true)"), {"c": str(conta_id)})


@pytest.fixture
def ab(client, dono):
    """A e B com respostas; B gerou o resumo do painel e tem uma ação com passos."""
    a = conta_pronta(client, "ana@alfa.com.br", empresa="Alfa")
    b = conta_pronta(client, "bia@beta.com.br", empresa="Beta")
    for x in (a, b):
        inserir_resposta(dono, x["conta"]["id"], form_padrao(client, x["h"])["id"], None, 9, relogio.hoje(),
                         comentario="Tudo certo")
    r = gerar_ia(client, b["h"])
    assert r.status_code == 200, r.text
    contato = criar_contato(client, b["h"], nome="Bruno")
    r = client.post(f"{API}/respostas", headers=b["h"], json={"contato_id": contato["id"], "nota": 2,
                                                             "comentario": "Atrasou"})
    assert r.status_code == 201, r.text
    b["acao_id"] = sql(dono, "select id from acoes where conta_id = :b", b=b["conta"]["id"])[0][0]
    return a, b


def test_tabela_nova_tem_rls_forcado(dono):
    linhas = sql(dono, """
        select c.relname, c.relrowsecurity, c.relforcerowsecurity, array_agg(p.polname order by p.polname)
          from pg_class c join pg_policy p on p.polrelid = c.oid
         where c.relname = any(:t) group by 1, 2, 3
    """, t=TABELAS)
    assert {x[0]: x[1:] for x in linhas} == {t: (True, True, ["isolamento_conta"]) for t in TABELAS}


def test_sql_sem_contexto_e_com_outra_conta(ab, app_engine, dono):
    a, b = ab
    idb = b["conta"]["id"]
    assert sql(dono, "select count(*) from ia_pareceres where conta_id = :b", b=idb)[0][0] == 1
    with app_engine.connect() as c:
        assert c.execute(text("select count(*) from ia_pareceres")).scalar() == 0
    with app_engine.begin() as c:
        _como(c, a["conta"]["id"])
        assert c.execute(text("select count(*) from ia_pareceres")).scalar() == 0
        assert c.execute(text("update ia_pareceres set conteudo = '{}'")).rowcount == 0
        assert c.execute(text("delete from ia_pareceres")).rowcount == 0
        # os passos das ações de B também não aparecem nem mudam
        assert c.execute(text("update acoes set ia_passos_situacao = null")).rowcount == 0
    assert sql(dono, "select ia_passos_situacao from acoes where id = :a", a=b["acao_id"]) == [("pronta",)]
    with pytest.raises(ProgrammingError, match="row-level security"):
        with app_engine.begin() as c:
            _como(c, a["conta"]["id"])
            c.execute(text("insert into ia_pareceres (conta_id, tipo, chave, filtros, conteudo, modelo, estilo) "
                           "values (:b, 'painel', 'x', '{}', '{}', 'rapido', 'objetiva')"), {"b": idb})
    with app_engine.begin() as c:
        _como(c, idb)
        assert c.execute(text("select count(*) from ia_pareceres")).scalar() == 1


def test_chave_composta_do_usuario_que_gerou(ab, app_engine):
    """Na conta B (contexto dela), o parecer não pode apontar para um usuário de A."""
    a, b = ab
    with pytest.raises(IntegrityError):
        with app_engine.begin() as c:
            _como(c, b["conta"]["id"])
            c.execute(text("insert into ia_pareceres (tipo, chave, filtros, conteudo, modelo, estilo, gerado_por) "
                           "values ('relatorios', 'y', '{}', '{}', 'rapido', 'objetiva', :u)"),
                      {"u": a["usuario"]["id"]})


def test_rotas_nao_veem_a_outra_conta(client, ab, dono):
    a, b = ab
    r = estado_ia(client, a["h"]).json()
    assert r["item"] is None and r["pode_gerar_em"] is None  # a espera de 30 s de B não vale para A
    assert gerar_ia(client, a["h"]).status_code == 200
    assert sql(dono, "select conta_id, count(*) from ia_pareceres group by conta_id order by conta_id") == [
        (a["conta"]["id"], 1), (b["conta"]["id"], 1)]
    assert client.get(f"{API}/acoes/{b['acao_id']}", headers=a["h"]).status_code == 404
    assert acao(client, b["h"], b["acao_id"])["ia_passos_situacao"] == "pronta"
    # desligar os passos em A não mexe nas ações de B
    assert client.put(f"{API}/conta/ia", headers=a["h"], json={"passos_acoes": False}).status_code == 200
    assert sql(dono, "select ia_passos_situacao from acoes where id = :a", a=b["acao_id"]) == [("pronta",)]


def test_excluir_conta_apaga_os_pareceres(client, ab, dono):
    a, b = ab
    root = conta_pronta(client, "root@toqqi.com", empresa="Toqqi")
    assert gerar_ia(client, a["h"]).status_code == 200
    r = client.request("DELETE", f"{API}/plataforma/contas/{b['conta']['id']}", headers=root["h"],
                       json={"confirmar_nome": "Beta"})
    assert r.status_code == 204, r.text
    assert sql(dono, "select conta_id from ia_pareceres") == [(a["conta"]["id"],)]

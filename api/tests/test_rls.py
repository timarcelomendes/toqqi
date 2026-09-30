"""Isolamento entre contas garantido pelo RLS do PostgreSQL."""
import pytest
from sqlalchemy import text
from sqlalchemy.exc import ProgrammingError
from util import conta_pronta, membro

API = "/api/v1"


@pytest.fixture
def duas_contas(client):
    a = conta_pronta(client, "ana@alfa.com.br", empresa="Alfa")
    b = conta_pronta(client, "bia@beta.com.br", empresa="Beta")
    return a, b


def test_papel_da_app_nao_tem_privilegios_especiais(app_engine):
    with app_engine.connect() as c:
        su, bypass = c.execute(text(
            "select rolsuper, rolbypassrls from pg_roles where rolname = current_user")).one()
        dono_tabela = c.execute(text("select tableowner from pg_tables where tablename = 'usuarios'")).scalar()
        atual = c.execute(text("select current_user")).scalar()
    assert (su, bypass) == (False, False)
    assert dono_tabela != atual


def test_sql_direto_sem_contexto_nao_ve_nada(client, duas_contas, app_engine):
    with app_engine.connect() as c:
        for tabela in ["contas", "usuarios", "sessoes", "tokens_uso_unico", "perfil_permissoes", "auditoria"]:
            assert c.execute(text(f"select count(*) from {tabela}")).scalar() == 0, tabela


def test_sql_direto_com_contexto_ve_so_a_propria_conta(client, duas_contas, app_engine):
    a, b = duas_contas
    with app_engine.begin() as c:
        c.execute(text("select set_config('app.conta_id', :c, true)"), {"c": str(a["conta"]["id"])})
        emails = c.execute(text("select email from usuarios")).scalars().all()
        assert emails == ["ana@alfa.com.br"]
        assert c.execute(text("select count(*) from contas")).scalar() == 1


def test_nao_consegue_gravar_em_outra_conta(client, duas_contas, app_engine):
    a, b = duas_contas
    with pytest.raises(ProgrammingError, match="row-level security"):
        with app_engine.begin() as c:
            c.execute(text("select set_config('app.conta_id', :c, true)"), {"c": str(a["conta"]["id"])})
            c.execute(text("insert into auditoria (conta_id, evento, gravidade) values (:b, 'x', 'info')"),
                      {"b": b["conta"]["id"]})


def test_usuario_de_a_nao_ve_nem_altera_usuarios_de_b(client, duas_contas):
    a, b = duas_contas
    id_b = b["usuario"]["id"]
    lista = client.get(f"{API}/equipe", headers=a["h"]).json()
    assert [u["email"] for u in lista] == ["ana@alfa.com.br"]
    assert client.patch(f"{API}/equipe/{id_b}", headers=a["h"], json={"nome": "Hacker"}).status_code == 404
    assert client.patch(f"{API}/equipe/{id_b}", headers=a["h"], json={"situacao": "bloqueado"}).status_code == 404
    assert client.delete(f"{API}/equipe/{id_b}", headers=a["h"]).status_code == 404
    assert client.post(f"{API}/equipe/{id_b}/reenviar-confirmacao", headers=a["h"]).status_code == 404
    # B continua intacta
    assert client.get(f"{API}/eu", headers=b["h"]).json()["usuario"]["nome"] == "Pessoa"


def test_usuario_de_a_nao_encerra_sessao_de_b(client, duas_contas):
    a, b = duas_contas
    sessao_b = client.get(f"{API}/eu/sessoes", headers=b["h"]).json()[0]["id"]
    assert client.delete(f"{API}/eu/sessoes/{sessao_b}", headers=a["h"]).status_code == 404
    assert client.get(f"{API}/eu", headers=b["h"]).status_code == 200


def test_auditoria_e_permissoes_isoladas(client, duas_contas):
    a, b = duas_contas
    itens_a = client.get(f"{API}/auditoria", headers=a["h"]).json()["itens"]
    assert itens_a and all(i["detalhe"].get("email") != "bia@beta.com.br" for i in itens_a)
    # alterar a matriz de A não mexe na de B
    client.put(f"{API}/equipe/permissoes", headers=a["h"], json={"gestor": [], "consulta": []})
    assert client.get(f"{API}/equipe/permissoes", headers=b["h"]).json()["gestor"] != []


def test_token_com_conta_trocada_e_rejeitado(client, duas_contas):
    """Mesmo forjando cid de outra conta no token, a sessão não aparece (RLS) → 401."""
    import jwt

    a, b = duas_contas
    p = jwt.decode(a["token"], options={"verify_signature": False})
    p["cid"] = b["conta"]["id"]
    forjado = jwt.encode(p, "segredo-de-teste-com-tamanho-suficiente", algorithm="HS256")
    r = client.get(f"{API}/eu", headers={"Authorization": f"Bearer {forjado}"})
    assert r.status_code == 401
    assert r.json()["erro"]["codigo"] == "sessao_invalida"


def test_membro_criado_fica_na_conta_do_admin(client, duas_contas):
    a, _ = duas_contas
    m = membro(client, a["h"], "caio@alfa.com.br")
    assert m["conta"]["id"] == a["conta"]["id"]

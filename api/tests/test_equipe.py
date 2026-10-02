"""Equipe: permissões, proteção do último admin e de si mesmo, bloqueio."""
from util import conta_pronta, entrar, membro

from toqqi.core.permissoes import PADRAO, SOMENTE_ADMIN, TODAS

API = "/api/v1"


def test_consulta_recebe_403_na_equipe(client):
    a = conta_pronta(client, "ana@alfa.com.br")
    c = membro(client, a["h"], "caio@alfa.com.br", "consulta")
    assert sorted(c["permissoes"]) == sorted(PADRAO["consulta"])
    for metodo, rota in [("get", "/equipe"), ("get", "/equipe/permissoes"), ("get", "/auditoria"),
                         ("get", "/conta/seguranca"), ("post", f"/equipe/{a['usuario']['id']}/reenviar-confirmacao")]:
        r = getattr(client, metodo)(f"{API}{rota}", headers=c["h"])
        assert r.status_code == 403, rota
        assert r.json()["erro"]["codigo"] == "sem_permissao"
    assert client.get(f"{API}/eu", headers=c["h"]).status_code == 200  # continua logado


def test_gestor_nao_tem_permissoes_exclusivas_do_admin(client):
    a = conta_pronta(client, "ana@alfa.com.br")
    g = membro(client, a["h"], "gil@alfa.com.br", "gestor")
    assert not SOMENTE_ADMIN & set(g["permissoes"])
    assert set(g["permissoes"]) == set(TODAS) - SOMENTE_ADMIN
    assert client.get(f"{API}/equipe", headers=g["h"]).status_code == 403


def test_matriz_personalizada_vale_na_hora(client):
    a = conta_pronta(client, "ana@alfa.com.br")
    c = membro(client, a["h"], "caio@alfa.com.br", "consulta")
    r = client.put(f"{API}/equipe/permissoes", headers=a["h"],
                   json={"gestor": PADRAO["gestor"], "consulta": ["painel.ver", "contatos.editar"]})
    assert r.status_code == 200
    assert r.json()["consulta"] == ["painel.ver", "contatos.editar"]
    # o mesmo token já enxerga a mudança
    assert client.get(f"{API}/eu", headers=c["h"]).json()["permissoes"] == ["painel.ver", "contatos.editar"]
    cat = client.get(f"{API}/equipe/permissoes", headers=a["h"]).json()["catalogo"]
    assert len(cat) == 23 and all({"chave", "rotulo", "grupo", "somente_admin"} == set(x) for x in cat)


def test_put_permissoes_rejeita_exclusivas_e_desconhecidas(client):
    a = conta_pronta(client, "ana@alfa.com.br")
    r = client.put(f"{API}/equipe/permissoes", headers=a["h"],
                   json={"gestor": ["painel.ver", "equipe.gerenciar"], "consulta": ["inventada.ver"]})
    assert r.status_code == 422
    campos = r.json()["erro"]["campos"]
    assert "equipe.gerenciar" in campos["gestor"] and "inventada.ver" in campos["consulta"]


def test_mudanca_de_perfil_vale_na_hora(client):
    a = conta_pronta(client, "ana@alfa.com.br")
    c = membro(client, a["h"], "caio@alfa.com.br", "consulta")
    assert client.get(f"{API}/equipe", headers=c["h"]).status_code == 403
    client.patch(f"{API}/equipe/{c['usuario']['id']}", headers=a["h"], json={"perfil": "admin"})
    assert client.get(f"{API}/equipe", headers=c["h"]).status_code == 200


def test_criar_membro_e_email_em_uso(client):
    a = conta_pronta(client, "ana@alfa.com.br")
    conta_pronta(client, "bia@beta.com.br")
    r = client.post(f"{API}/equipe", headers=a["h"],
                    json={"nome": "Caio", "email": "caio@alfa.com.br", "perfil": "gestor", "senha": "Senha@123",
                          "cargo": "Vendas"})
    assert r.status_code == 201
    u = r.json()
    assert (u["situacao"], u["email_confirmado"], u["cargo"]) == ("ativo", True, "Vendas")
    for email in ["caio@alfa.com.br", "BIA@beta.com.br"]:  # mesma conta e outra conta
        r = client.post(f"{API}/equipe", headers=a["h"],
                        json={"nome": "Xavier", "email": email, "perfil": "gestor", "senha": "Senha@123"})
        assert r.status_code == 409 and r.json()["erro"]["codigo"] == "email_em_uso"


def test_bloquear_derruba_sessao_na_hora(client):
    a = conta_pronta(client, "ana@alfa.com.br")
    c = membro(client, a["h"], "caio@alfa.com.br")
    r = client.patch(f"{API}/equipe/{c['usuario']['id']}", headers=a["h"], json={"situacao": "bloqueado"})
    assert r.status_code == 200 and r.json()["situacao"] == "bloqueado"
    r = client.get(f"{API}/eu", headers=c["h"])
    assert r.status_code == 401 and r.json()["erro"]["codigo"] == "sessao_invalida"
    r = entrar(client, "caio@alfa.com.br")
    assert r.status_code == 403 and r.json()["erro"]["codigo"] == "acesso_bloqueado"
    # desbloquear: volta a entrar
    client.patch(f"{API}/equipe/{c['usuario']['id']}", headers=a["h"], json={"situacao": "ativo"})
    assert entrar(client, "caio@alfa.com.br").status_code == 200


def test_bloqueio_direto_no_banco_tambem_derruba(client, dono):
    """Mesmo sem revogar a sessão, usuário não-ativo é recusado em toda requisição."""
    from util import sql

    a = conta_pronta(client, "ana@alfa.com.br")
    c = membro(client, a["h"], "caio@alfa.com.br")
    sql(dono, "update usuarios set situacao = 'bloqueado' where email = 'caio@alfa.com.br'")
    assert client.get(f"{API}/eu", headers=c["h"]).status_code == 401


def test_ultimo_admin_protegido(client):
    a = conta_pronta(client, "ana@alfa.com.br")
    eu = a["usuario"]["id"]
    for corpo in [{"perfil": "gestor"}, {"situacao": "bloqueado"}]:
        r = client.patch(f"{API}/equipe/{eu}", headers=a["h"], json=corpo)
        assert r.status_code == 409 and r.json()["erro"]["codigo"] == "ultimo_admin"
    r = client.delete(f"{API}/equipe/{eu}", headers=a["h"])
    assert r.status_code == 409 and r.json()["erro"]["codigo"] == "ultimo_admin"


def test_nao_pode_mudar_a_si_mesmo(client):
    a = conta_pronta(client, "ana@alfa.com.br")
    membro(client, a["h"], "outro@alfa.com.br", "admin")  # agora há outro admin
    eu = a["usuario"]["id"]
    for corpo in [{"perfil": "consulta"}, {"situacao": "bloqueado"}]:
        r = client.patch(f"{API}/equipe/{eu}", headers=a["h"], json=corpo)
        assert r.status_code == 409 and r.json()["erro"]["codigo"] == "nao_pode_si_mesmo"
    r = client.delete(f"{API}/equipe/{eu}", headers=a["h"])
    assert r.status_code == 409 and r.json()["erro"]["codigo"] == "nao_pode_si_mesmo"
    # mudar o próprio nome pode, e reenviar o mesmo perfil não é mudança
    r = client.patch(f"{API}/equipe/{eu}", headers=a["h"], json={"nome": "Ana S.", "perfil": "admin"})
    assert r.status_code == 200 and r.json()["nome"] == "Ana S."


def test_excluir_membro(client):
    a = conta_pronta(client, "ana@alfa.com.br")
    c = membro(client, a["h"], "caio@alfa.com.br")
    assert client.delete(f"{API}/equipe/{c['usuario']['id']}", headers=a["h"]).status_code == 204
    assert client.get(f"{API}/eu", headers=c["h"]).status_code == 401
    assert [u["email"] for u in client.get(f"{API}/equipe", headers=a["h"]).json()] == ["ana@alfa.com.br"]
    eventos = [i["evento"] for i in client.get(f"{API}/auditoria", headers=a["h"]).json()["itens"]]
    assert "usuario_excluido" in eventos and "login_ok" in eventos  # histórico do excluído continua

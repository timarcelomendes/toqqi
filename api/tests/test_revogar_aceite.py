"""Retirar o aceite dos Termos de uso e da Política de privacidade: POST /eu/aceite/revogar, situação em /eu, sessões
encerradas, aceitar de novo, auditoria, RLS, limite e migração 0011 (descer e subir)."""
import pytest
from alembic.config import Config as AlembicConfig
from conftest import OWNER_URL
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from util import API, auth, conta_pronta, entrar, membro, sql

from alembic import command
from toqqi.core.auditoria import ROTULOS
from toqqi.core.db import RAIZ_API
from toqqi.core.rate_limit import limiter
from toqqi.modulos.acesso import termos

UA = "Mozilla/5.0 (Windows NT 10.0) Chrome/120.0 Safari/537.36"
V = termos.VERSAO_DOCUMENTOS  # a versão atual
MSG = "Aceite retirado. Para voltar a usar o Toqqi, entre de novo e aceite os termos."


def _aceite(client, h) -> dict:
    r = client.get(f"{API}/eu", headers=h)
    assert r.status_code == 200, r.text
    return r.json()["usuario"]["aceite"]


def _aceitar(client, h):
    return client.post(f"{API}/eu/aceite", headers={**h, "User-Agent": UA}, json={"versao": V})


def _revogar(client, h, corpo=None, ua: str | None = "Navegador da retirada"):
    headers = {**h, "User-Agent": ua} if ua else h
    return client.post(f"{API}/eu/aceite/revogar", headers=headers,
                       json={"confirmar": True} if corpo is None else corpo)


def _nova_sessao(client, email: str) -> dict:
    r = entrar(client, email)
    assert r.status_code == 200, r.text
    return auth(r.json()["token"])


@pytest.fixture
def admin(client):
    return conta_pronta(client, "ana@alfa.com.br", empresa="Alfa")


@pytest.fixture
def gestor(client, admin):
    return membro(client, admin["h"], "gil@alfa.com.br", "gestor")


def test_revogar_deixa_pendente_e_encerra_todas_as_sessoes(client, admin, dono):
    outra = _nova_sessao(client, "ana@alfa.com.br")  # outro aparelho
    antes = _aceite(client, admin["h"])
    assert antes["pendente"] is False and antes["revogado_em"] is None

    r = _revogar(client, admin["h"])
    assert r.status_code == 200, r.text
    assert r.json() == {"mensagem": MSG}

    # a sessão atual e a outra deixam de valer
    for h in (admin["h"], outra):
        r = client.get(f"{API}/eu", headers=h)
        assert r.status_code == 401 and r.json()["erro"]["codigo"] == "sessao_invalida"
    assert sql(dono, "select count(*) from sessoes where usuario_id = :u and revogada_em is null",
               u=admin["usuario"]["id"])[0][0] == 0

    # entrando de novo: pendente, com a data da retirada
    r = entrar(client, "ana@alfa.com.br")
    assert r.status_code == 200
    a_entrar = r.json()["usuario"]["aceite"]
    a = _aceite(client, auth(r.json()["token"]))
    assert a == a_entrar
    assert (a["versao_aceita"], a["aceito_em"], a["pendente"]) == (None, None, True)
    assert a["revogado_em"]

    # a linha antiga fica, com a retirada
    (linha,) = sql(dono, "select origem, revogado_em, revogado_ip, revogado_agente, ip from aceites_termos "
                         "where usuario_id = :u", u=admin["usuario"]["id"])
    assert linha.origem == "cadastro" and linha.revogado_em is not None
    assert (linha.revogado_ip, linha.revogado_agente) == ("testclient", "Navegador da retirada")


def test_revogar_marca_todas_as_linhas_em_vigor(client, admin, dono, monkeypatch):
    monkeypatch.setattr(termos, "VERSAO_DOCUMENTOS", V + 1)
    assert client.post(f"{API}/eu/aceite", headers=admin["h"], json={"versao": V + 1}).status_code == 200
    assert _revogar(client, admin["h"]).status_code == 200
    linhas = sql(dono, "select versao, revogado_em is not null from aceites_termos where usuario_id = :u "
                       "order by versao", u=admin["usuario"]["id"])
    assert [tuple(x) for x in linhas] == [(V, True), (V + 1, True)]
    (aud,) = sql(dono, "select detalhe, gravidade, usuario_id, conta_id from auditoria "
                       "where evento = 'termos_revogados'")
    assert aud.detalhe == {"versao": V + 1}
    assert (aud.usuario_id, aud.conta_id) == (admin["usuario"]["id"], admin["conta"]["id"])


def test_aceitar_de_novo_cria_linha_nova(client, gestor, dono):
    gid = gestor["usuario"]["id"]
    assert _aceitar(client, gestor["h"]).status_code == 200
    assert _revogar(client, gestor["h"]).status_code == 200
    h = _nova_sessao(client, "gil@alfa.com.br")
    r = _aceitar(client, h)
    assert r.status_code == 200, r.text
    corpo = r.json()
    assert corpo["versao_aceita"] == V and corpo["pendente"] is False and corpo["revogado_em"] is None
    assert _aceite(client, h) == corpo
    linhas = sql(dono, "select versao, origem, revogado_em is not null as revogada from aceites_termos "
                       "where usuario_id = :u order by id", u=gid)
    assert [tuple(x) for x in linhas] == [(V, "tela", True), (V, "tela", False)]  # o histórico fica inteiro
    eventos = sql(dono, "select evento from auditoria where usuario_id = :u and evento like 'termos_%' order by id",
                  u=gid)
    assert [e for (e,) in eventos] == ["termos_aceitos", "termos_revogados", "termos_aceitos"]
    # aceitar outra vez continua idempotente
    assert _aceitar(client, h).json() == corpo
    assert sql(dono, "select count(*) from aceites_termos where usuario_id = :u", u=gid)[0][0] == 2


def test_revogado_em_some_quando_ha_aceite_posterior(client, gestor, dono):
    """A retirada mais recente só aparece se for depois do último aceite em vigor."""
    assert _aceitar(client, gestor["h"]).status_code == 200
    assert _revogar(client, gestor["h"]).status_code == 200
    h = _nova_sessao(client, "gil@alfa.com.br")
    revogado = _aceite(client, h)["revogado_em"]
    assert revogado
    assert _aceitar(client, h).status_code == 200
    assert _aceite(client, h)["revogado_em"] is None
    # retirar de novo: a data nova aparece
    assert _revogar(client, h).status_code == 200
    a = _aceite(client, _nova_sessao(client, "gil@alfa.com.br"))
    assert a["pendente"] is True and a["revogado_em"] and a["revogado_em"] >= revogado
    assert sql(dono, "select count(*) from aceites_termos where usuario_id = :u and revogado_em is not null",
               u=gestor["usuario"]["id"])[0][0] == 2


def test_sem_aceite_em_vigor_409(client, admin, gestor, dono):
    r = _revogar(client, gestor["h"])  # nunca aceitou
    assert r.status_code == 409
    assert r.json()["erro"] == {"codigo": "sem_aceite", "mensagem": "Você não tem um aceite em vigor para retirar.",
                                "campos": {}}
    # a sessão continua valendo e nada foi auditado
    assert client.get(f"{API}/eu", headers=gestor["h"]).status_code == 200
    assert sql(dono, "select count(*) from auditoria where evento = 'termos_revogados'")[0][0] == 0
    # já retirado: 409 também
    assert _revogar(client, admin["h"]).status_code == 200
    h = _nova_sessao(client, "ana@alfa.com.br")
    assert _revogar(client, h).json()["erro"]["codigo"] == "sem_aceite"


def test_sem_confirmar_422(client, admin, dono):
    for corpo in ({}, {"confirmar": False}, {"confirmar": None}, {"confirmar": "true"}, {"confirmar": "yes"},
                  {"confirmar": 1}):
        r = _revogar(client, admin["h"], corpo=corpo)
        assert r.status_code == 422, (corpo, r.text)
        assert r.json()["erro"]["codigo"] == "dados_invalidos"
        campos = r.json()["erro"]["campos"]
        assert list(campos) == ["confirmar"], corpo
        if corpo.get("confirmar") in (None, False):  # texto e número: a mensagem padrão de "verdadeiro ou falso"
            assert campos == {"confirmar": "Confirme que quer retirar o aceite."}, corpo
    assert _aceite(client, admin["h"])["pendente"] is False
    assert sql(dono, "select count(*) from aceites_termos where revogado_em is not null")[0][0] == 0


def test_sem_login_401(client):
    r = client.post(f"{API}/eu/aceite/revogar", json={"confirmar": True})
    assert r.status_code == 401 and r.json()["erro"]["codigo"] == "sessao_invalida"


def test_rotulo_da_auditoria(client, admin):
    assert ROTULOS["termos_revogados"] == "Retirou o aceite dos termos e da política de privacidade"


def test_superadmin_tambem_revoga(client):
    root = conta_pronta(client, "root@toqqi.com", empresa="Toqqi")
    assert _revogar(client, root["h"]).status_code == 200
    assert client.get(f"{API}/eu", headers=root["h"]).status_code == 401


def test_revogar_nao_afeta_outros_usuarios(client, admin, gestor):
    assert _aceitar(client, gestor["h"]).status_code == 200
    assert _revogar(client, gestor["h"]).status_code == 200
    assert client.get(f"{API}/eu", headers=admin["h"]).status_code == 200
    assert _aceite(client, admin["h"])["pendente"] is False


def test_rls_retirada_nao_cruza_contas(client, admin, app_engine):
    bia = conta_pronta(client, "bia@beta.com.br", empresa="Beta")
    assert _revogar(client, bia["h"]).status_code == 200
    ida, idb = admin["conta"]["id"], bia["conta"]["id"]
    with app_engine.begin() as c:
        c.execute(text("select set_config('app.conta_id', :c, true)"), {"c": str(ida)})
        assert c.execute(text("select count(*) from aceites_termos where revogado_em is not null")).scalar() == 0
        # tentar marcar a retirada nas linhas da outra conta não alcança nada
        assert c.execute(text("update aceites_termos set revogado_em = now() where conta_id = :b"),
                         {"b": idb}).rowcount == 0
    with app_engine.begin() as c:
        c.execute(text("select set_config('app.conta_id', :c, true)"), {"c": str(idb)})
        assert c.execute(text("select count(*) from aceites_termos where revogado_em is not null")).scalar() == 1


def test_indice_unico_parcial(admin, dono):
    u, c = admin["usuario"]["id"], admin["conta"]["id"]
    inserir = ("insert into aceites_termos (conta_id, usuario_id, usuario_email, usuario_nome, versao, origem) "
               "values (:c, :u, 'ana@alfa.com.br', 'Ana', :v, 'tela')")
    with pytest.raises(IntegrityError):  # duas linhas em vigor da mesma versão: não
        sql(dono, inserir, c=c, u=u, v=V)
    sql(dono, "update aceites_termos set revogado_em = now() where usuario_id = :u", u=u)
    sql(dono, inserir, c=c, u=u, v=V)  # com a anterior revogada: sim
    with pytest.raises(IntegrityError):  # o navegador da retirada também é cortado em 400
        sql(dono, "update aceites_termos set revogado_agente = repeat('x', 401) where usuario_id = :u", u=u)


def test_limite_20_por_minuto_por_usuario(client, admin, gestor):
    limiter.enabled = True
    limiter.reset()
    try:
        # sem aceite em vigor o gestor recebe 409, mas cada chamada conta no limite
        codigos = [_revogar(client, gestor["h"]).status_code for _ in range(21)]
        assert codigos == [409] * 20 + [429]
        assert _revogar(client, admin["h"]).status_code == 200  # o limite é por usuário (mesmo IP)
    finally:
        limiter.enabled = False
        limiter.reset()


def _alembic() -> AlembicConfig:
    cfg = AlembicConfig(str(RAIZ_API / "alembic.ini"))
    cfg.set_main_option("script_location", str(RAIZ_API / "alembic"))
    cfg.attributes["url"] = OWNER_URL
    return cfg


def _colunas(dono) -> set[str]:
    return {c for (c,) in sql(dono, "select column_name from information_schema.columns "
                                    "where table_schema = 'public' and table_name = 'aceites_termos'")}


COLUNAS = {"revogado_em", "revogado_ip", "revogado_agente"}


def test_descer_e_subir_a_0011(client, gestor, dono):
    gid = gestor["usuario"]["id"]
    assert _aceitar(client, gestor["h"]).status_code == 200
    assert _revogar(client, gestor["h"]).status_code == 200
    h = _nova_sessao(client, "gil@alfa.com.br")
    assert _aceitar(client, h).status_code == 200
    assert sql(dono, "select count(*) from aceites_termos where usuario_id = :u", u=gid)[0][0] == 2
    cfg = _alembic()
    command.downgrade(cfg, "0010_aceites")
    try:
        assert not COLUNAS & _colunas(dono)
        # a linha revogada duplicada sai; fica a que estava em vigor (a mais nova) e o aceite do cadastro do admin
        linhas = sql(dono, "select id, usuario_id from aceites_termos order by id")
        assert len(linhas) == 2 and [x.usuario_id for x in linhas].count(gid) == 1
        assert sql(dono, "select count(*) from pg_constraint "
                         "where conname = 'aceites_termos_usuario_id_versao_key'")[0][0] == 1
    finally:
        command.upgrade(cfg, "head")
    assert COLUNAS <= _colunas(dono)
    a = _aceite(client, h)
    assert a["pendente"] is False and a["revogado_em"] is None
    # o papel da aplicação continua gravando a tabela (permissões da tabela inteira)
    assert _revogar(client, h).status_code == 200


def test_quem_retirou_nao_recebe_os_emails_do_toqqi(client, admin, gestor, dono):
    from toqqi.core.db import em_conta
    from toqqi.modulos.relatorios.emails import destinatarios

    conta_id = sql(dono, "select conta_id from usuarios where email = 'ana@alfa.com.br'")[0][0]

    def para():
        with em_conta(conta_id) as s:
            return sorted(destinatarios(s, "recebe_resumo_semanal"))

    antes = para()
    assert "ana@alfa.com.br" in antes
    assert _revogar(client, admin["h"]).status_code == 200
    assert "ana@alfa.com.br" not in para()
    # quem nunca viu a tela de aceite (o gestor, se não aceitou) não muda
    assert [e for e in para() if e != "ana@alfa.com.br"] == [e for e in antes if e != "ana@alfa.com.br"]
    # aceitou de novo: volta a receber
    h = _nova_sessao(client, "ana@alfa.com.br")
    assert _aceitar(client, h).status_code == 200
    assert para() == antes

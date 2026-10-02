"""Migração 0010 (crescimento): restrições do banco nas tabelas novas, a coluna `convites.indicacoes_feitas`, eventos
novos dos webhooks, permissões semeadas nas contas que já existiam; descer para a 0009 (tudo desfeito) e subir de
novo."""
import pytest
from alembic.config import Config as AlembicConfig
from conftest import OWNER_URL
from sqlalchemy.exc import IntegrityError
from util import API, conta_pronta, criar_contato, criar_empresa, membro, sql

from alembic import command
from toqqi.core.db import RAIZ_API

TABELAS = {"config_crescimento", "indicacoes", "ofertas"}
NOVAS = {("gestor", "crescimento.ver"), ("gestor", "crescimento.tratar"), ("consulta", "crescimento.ver")}
INDICACAO = ("insert into indicacoes (conta_id, origem, nome, telefone, email, situacao, valor_mensal, motivo) "
             "values (:c, :origem, :nome, :tel, :email, :situacao, :valor, :motivo)")
OFERTA = ("insert into ofertas (conta_id, empresa_id, lista, canal, texto, resultado, valor, resultado_em) "
          "values (:c, :e, :lista, :canal, :texto, :resultado, :valor, :quando)")


def _alembic() -> AlembicConfig:
    cfg = AlembicConfig(str(RAIZ_API / "alembic.ini"))
    cfg.set_main_option("script_location", str(RAIZ_API / "alembic"))
    cfg.attributes["url"] = OWNER_URL
    return cfg


def _tabelas(dono) -> set[str]:
    return {t for (t,) in sql(dono, "select tablename from pg_tables where schemaname = 'public'")}


def _coluna_dos_convites(dono) -> list[tuple]:
    return sql(dono, "select data_type, is_nullable, column_default from information_schema.columns "
                     "where table_name = 'convites' and column_name = 'indicacoes_feitas'")


def _permissoes(dono, conta_id: int) -> set[tuple[str, str]]:
    return set(sql(dono, "select perfil, permissao from perfil_permissoes where conta_id = :c "
                         "and permissao like 'crescimento.%'", c=conta_id))


@pytest.fixture
def conta(client):
    return conta_pronta(client, "ana@alfa.com.br", empresa="Alfa")


def _indicacao(dono, conta_id: int, **campos) -> None:
    valores = {"origem": "manual", "nome": "João", "tel": "5511987654321", "email": None, "situacao": "nova",
               "valor": None, "motivo": None, **campos}
    sql(dono, INDICACAO, c=conta_id, **valores)


@pytest.mark.parametrize("campos", [
    {"tel": None, "email": None},  # telefone ou e-mail
    {"tel": "11987654321"},  # sem o 55
    {"tel": "55119876a4321"},
    {"nome": "J"}, {"nome": "x" * 121},
    {"origem": "importacao"}, {"situacao": "perdida"},
    {"valor": 100},  # valor só com 'cliente'
    {"situacao": "cliente", "valor": -1},
    {"motivo": "Preço"},  # motivo só com 'nao_avancou'
    {"situacao": "nao_avancou", "motivo": ""},
    {"situacao": "nao_avancou", "motivo": "x" * 301},
])
def test_restricoes_das_indicacoes(conta, dono, campos):
    with pytest.raises(IntegrityError):
        _indicacao(dono, conta["conta"]["id"], **campos)


def test_indicacoes_validas_no_banco(conta, dono):
    c = conta["conta"]["id"]
    _indicacao(dono, c)
    _indicacao(dono, c, tel=None, email="joao@x.com.br", situacao="cliente", valor=0)
    _indicacao(dono, c, situacao="cliente")  # o valor é exigido pela API, não pelo banco
    _indicacao(dono, c, situacao="nao_avancou", motivo="Preço")
    assert sql(dono, "select count(*) from indicacoes")[0][0] == 4
    # sem linha de configuração: os padrões; a linha nova nasce com os mesmos DEFAULTs
    sql(dono, "insert into config_crescimento (conta_id) values (:c)", c=c)
    assert sql(dono, "select indicacoes_ativas, titulo_convite, recompensa from config_crescimento") == \
        [(False, "Que bom que você gostou!", None)]
    for coluna, valor in (("titulo_convite", ""), ("texto_convite", "x" * 501), ("recompensa", ""),
                          ("texto_oferta", "x" * 1001)):
        with pytest.raises(IntegrityError):
            sql(dono, f"update config_crescimento set {coluna} = :v", v=valor)


@pytest.mark.parametrize("campos", [
    {"lista": "todas"}, {"canal": "sms"}, {"texto": ""}, {"texto": "x" * 2001},
    {"resultado": "talvez", "quando": "2026-10-01"},
    {"resultado": "recusou", "valor": 10, "quando": "2026-10-01"},  # valor só com 'aceitou'
    {"resultado": "aceitou", "valor": -1, "quando": "2026-10-01"},
    {"resultado": "aceitou"},  # resultado sem data
    {"quando": "2026-10-01"},  # data sem resultado
])
def test_restricoes_das_ofertas(client, conta, dono, campos):
    e = criar_empresa(client, conta["h"], "Mercado")
    valores = {"lista": "promotores", "canal": "whatsapp", "texto": "Oi", "resultado": None, "valor": None,
               "quando": None, **campos}
    with pytest.raises(IntegrityError):
        sql(dono, OFERTA, c=conta["conta"]["id"], e=e["id"], **valores)


def test_eventos_novos_nos_webhooks(conta, dono):
    c = conta["conta"]["id"]
    sql(dono, "insert into webhooks (conta_id, url, eventos, segredo_cifrado, segredo_prefixo) values "
              "(:c, 'https://x.com.br/a', array['indicacao.criada','indicacao.atualizada'], 'x', 'x')", c=c)
    with pytest.raises(IntegrityError):
        sql(dono, "insert into webhooks (conta_id, url, eventos, segredo_cifrado, segredo_prefixo) values "
                  "(:c, 'https://x.com.br/b', array['indicacao.apagada'], 'x', 'x')", c=c)


def test_contas_novas_ganham_as_permissoes_padrao(conta, dono):
    assert _permissoes(dono, conta["conta"]["id"]) == NOVAS


def test_convites_contam_as_indicacoes_feitas(client, conta, dono):
    assert _coluna_dos_convites(dono) == [("integer", "NO", "0")]
    contato = criar_contato(client, conta["h"], nome="Ana", email="ana@mercado.com.br")
    assert client.post(f"{API}/contatos/{contato['id']}/link-pesquisa", headers=conta["h"], json={}).status_code == 201
    assert sql(dono, "select indicacoes_feitas from convites") == [(0,)]  # convite novo nasce com 0
    with pytest.raises(IntegrityError):
        sql(dono, "update convites set indicacoes_feitas = -1")


def test_descer_e_subir_a_0010(client, conta, dono):
    h, c = conta["h"], conta["conta"]["id"]
    outra = conta_pronta(client, "bia@beta.com.br", empresa="Beta")
    # consulta da Alfa sem "ver" (tirada pelo administrador) ganha de novo na subida: a migração semeia o padrão
    sql(dono, "delete from perfil_permissoes where conta_id = :c and permissao = 'crescimento.ver' "
              "and perfil = 'consulta'", c=c)
    e = criar_empresa(client, h, "Mercado")
    contato = criar_contato(client, h, nome="Ana", email="ana@mercado.com.br", empresa_id=e["id"])
    assert client.post(f"{API}/crescimento/indicacoes", headers=h, json={
        "nome": "João", "email": "joao@x.com.br", "indicador_contato_id": contato["id"]}).status_code == 201
    assert client.post(f"{API}/crescimento/ofertas", headers=h, json={
        "empresa_id": e["id"], "lista": "promotores", "texto": "Oi"}).status_code == 201
    assert client.put(f"{API}/crescimento/configuracao", headers=h, json={"indicacoes_ativas": True}).status_code == 200
    for eventos in (["indicacao.criada"], ["resposta.criada", "indicacao.atualizada"]):
        sql(dono, "insert into webhooks (conta_id, url, eventos, segredo_cifrado, segredo_prefixo) values "
                  "(:c, 'https://x.com.br/a', :ev, 'x', 'x')", c=c, ev=eventos)
    (w,), = sql(dono, "select id from webhooks where 'indicacao.criada' = any(eventos)")
    sql(dono, "insert into webhook_entregas (conta_id, webhook_id, evento, corpo) values "
              "(:c, :w, 'indicacao.criada', '{}')", c=c, w=w)

    link = client.post(f"{API}/contatos/{contato['id']}/link-pesquisa", headers=h, json={})
    assert link.status_code == 201
    sql(dono, "update convites set indicacoes_feitas = 2")

    cfg = _alembic()
    command.downgrade(cfg, "0011_revogacao_aceite")
    try:
        assert not TABELAS & _tabelas(dono)
        assert _coluna_dos_convites(dono) == [] and sql(dono, "select count(*) from convites")[0][0] == 1
        assert _permissoes(dono, c) == set() and _permissoes(dono, outra["conta"]["id"]) == set()
        assert sql(dono, "select eventos from webhooks") == [(["resposta.criada"],)]  # o só de indicação sumiu
        assert sql(dono, "select count(*) from webhook_entregas")[0][0] == 0
        with pytest.raises(IntegrityError):
            sql(dono, "update webhooks set eventos = array['resposta.criada','indicacao.criada']")
        assert sql(dono, "select count(*) from perfil_permissoes where conta_id = :c", c=c)[0][0] > 0  # o resto fica
    finally:
        command.upgrade(cfg, "head")
    assert TABELAS <= _tabelas(dono)
    assert _coluna_dos_convites(dono) == [("integer", "NO", "0")]
    assert sql(dono, "select indicacoes_feitas from convites") == [(0,)]  # o convite que já existia começa do 0
    # as contas que já existiam ganham as permissões novas (gestor: ver e tratar; consulta: ver)
    assert _permissoes(dono, c) == NOVAS and _permissoes(dono, outra["conta"]["id"]) == NOVAS
    # e a aplicação volta a usar tudo (permissões do papel da aplicação nas tabelas novas)
    gestor = membro(client, h, "gil@alfa.com.br", "gestor")
    assert client.get(f"{API}/crescimento/indicacoes", headers=gestor["h"]).json()["total"] == 0
    assert client.post(f"{API}/crescimento/indicacoes", headers=gestor["h"],
                       json={"nome": "Maria", "email": "maria@x.com.br"}).status_code == 201
    assert client.get(f"{API}/crescimento/configuracao", headers=h).json()["indicacoes_ativas"] is False

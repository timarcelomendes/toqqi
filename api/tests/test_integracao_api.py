"""Etapa 3b: chave de integração e disparo por evento (POST /integracao/pesquisas e /integracao/csat)."""
import hashlib
from datetime import timedelta

import pytest
from sqlalchemy import text
from util import (
    API,
    conta_pronta,
    criar_contato,
    criar_empresa,
    definir_plano,
    emails_para,
    encher_contatos,
    evento,
    fixar_relogio,
    form_padrao,
    gerar_chave,
    ligar_envios,
    membro,
    segunda,
    sql,
    token_do_convite,
)

from toqqi.core.rate_limit import limiter


@pytest.fixture
def admin(client, dono):
    a = conta_pronta(client, "ana@alfa.com.br", empresa="Alfa Distribuidora")
    sql(dono, "update contas set situacao = 'cortesia' where id = :c", c=a["conta"]["id"])
    return a


@pytest.fixture
def chave(client, admin):
    ligar_envios(client, admin["h"])
    return gerar_chave(client, admin["h"])


def _convite(dono, convite_id: int):
    return sql(dono, "select evento, referencia, contexto, canal, formulario_id, assunto from convites where id = :i",
               i=convite_id)[0]


# ---- chave ------------------------------------------------------------------

def test_chave_mostrada_uma_vez_e_trocada(client, admin, dono):
    h = admin["h"]
    assert client.get(f"{API}/integracoes/chave", headers=h).json() == {
        "existe": False, "prefixo": None, "criada_em": None, "ultimo_uso": None}
    r = client.post(f"{API}/integracoes/chave", headers=h)
    assert r.status_code == 201
    primeira = r.json()["chave"]
    assert primeira.startswith("tq_live_") and len(primeira) == 48
    assert r.json()["prefixo"] == primeira[:12] + "…"
    # só o hash fica no banco
    (hash_, prefixo), = sql(dono, "select hash, prefixo from integracao_chaves")
    assert hash_ == hashlib.sha256(primeira.encode()).hexdigest() and primeira not in prefixo
    vista = client.get(f"{API}/integracoes/chave", headers=h).json()
    assert vista["existe"] is True and vista["prefixo"] == prefixo and vista["ultimo_uso"] is None
    assert "chave" not in vista

    # as duas formas de mandar a chave
    r = client.get(f"{API}/integracao/teste", headers={"X-Api-Key": primeira})
    assert r.status_code == 200 and r.json() == {"conta": "Alfa Distribuidora", "ok": True}
    assert client.get(f"{API}/integracao/teste", headers={"Authorization": f"Bearer {primeira}"}).status_code == 200
    assert client.get(f"{API}/integracoes/chave", headers=h).json()["ultimo_uso"] is not None

    # gerar outra derruba a anterior na hora
    segunda_chave = gerar_chave(client, h)
    r = client.get(f"{API}/integracao/teste", headers={"X-Api-Key": primeira})
    assert r.status_code == 401
    assert r.json()["erro"] == {"codigo": "chave_invalida", "campos": {},
                                "mensagem": "Chave de integração inválida ou revogada."}
    assert client.get(f"{API}/integracao/teste", headers={"X-Api-Key": segunda_chave}).status_code == 200

    assert client.delete(f"{API}/integracoes/chave", headers=h).status_code == 204
    assert client.get(f"{API}/integracao/teste", headers={"X-Api-Key": segunda_chave}).status_code == 401
    assert client.get(f"{API}/integracoes/chave", headers=h).json()["existe"] is False

    eventos = client.get(f"{API}/auditoria", headers=h).json()["itens"]
    gerada = [e for e in eventos if e["evento"] == "chave_gerada"]
    assert len(gerada) == 1 and gerada[0]["gravidade"] == "atencao"
    # etapa 5f: a segunda é "gerada de novo", com o começo da anterior
    (regerada,) = [e for e in eventos if e["evento"] == "chave_regerada"]
    assert regerada["gravidade"] == "atencao" and regerada["detalhe"]["prefixo_anterior"] == primeira[:12] + "…"
    assert all(primeira not in str(e) and segunda_chave not in str(e) for e in eventos)
    assert any(e["evento"] == "chave_revogada" for e in eventos)


@pytest.mark.parametrize("cabecalhos", [{}, {"X-Api-Key": "qualquer"}, {"X-Api-Key": "tq_live_" + "a" * 40},
                                        {"Authorization": "Bearer tq_live_" + "b" * 40}])
def test_chave_invalida(client, admin, cabecalhos):
    gerar_chave(client, admin["h"])
    r = client.get(f"{API}/integracao/teste", headers=cabecalhos)
    assert r.status_code == 401 and r.json()["erro"]["codigo"] == "chave_invalida"


def test_chave_so_admin(client, admin):
    gestor = membro(client, admin["h"], "gil@alfa.com.br", perfil="gestor")
    for metodo in ("get", "post", "delete"):
        assert getattr(client, metodo)(f"{API}/integracoes/chave", headers=gestor["h"]).status_code == 403
    # a sessão de usuário não vale nas rotas da chave
    assert client.get(f"{API}/integracao/teste", headers=admin["h"]).status_code == 401


def test_limite_de_120_por_minuto_por_chave(client, admin):
    chave = gerar_chave(client, admin["h"])
    outra = conta_pronta(client, "bia@beta.com.br", empresa="Beta")
    chave_b = gerar_chave(client, outra["h"])
    limiter.enabled = True
    limiter.reset()
    try:
        for _ in range(120):
            assert client.get(f"{API}/integracao/teste", headers={"X-Api-Key": chave}).status_code == 200
        r = client.get(f"{API}/integracao/teste", headers={"X-Api-Key": chave})
        assert r.status_code == 429 and r.json()["erro"]["codigo"] == "muitas_tentativas"
        assert client.get(f"{API}/integracao/teste", headers={"X-Api-Key": chave_b}).status_code == 200
    finally:
        limiter.enabled = False
        limiter.reset()


# ---- disparo por evento -----------------------------------------------------

def test_evento_cria_contato_e_empresa_e_guarda_o_contexto(client, admin, chave, dono):
    h = admin["h"]
    r = evento(client, chave, email="joao@cliente.com.br", nome="João Lima", codigo_externo="C-77",
               empresa={"nome": "Mercado Bom Preço", "codigo_externo": "E-1"}, evento="pedido_entregue",
               referencia="1234", contexto={"pedido": "1234", "motorista": "Zé", "rota": "Sul"})
    assert r.status_code == 201, r.text
    d = r.json()
    assert d["situacao"] == "enviado" and d["canal"] == "email" and d["mensagem"] == "Pesquisa enviada por e-mail."
    assert d["link"].startswith("http://app.teste/r/") and d["convite_id"] and d["contato_id"]
    c = client.get(f"{API}/contatos/{d['contato_id']}", headers=h).json()
    assert (c["nome"], c["email"], c["codigo_externo"]) == ("João Lima", "joao@cliente.com.br", "C-77")
    assert c["empresa"]["nome"] == "Mercado Bom Preço"
    convite = _convite(dono, d["convite_id"])
    assert convite.evento == "pedido_entregue" and convite.referencia == "1234" and convite.canal == "email"
    assert convite.contexto == {"pedido": "1234", "motorista": "Zé", "rota": "Sul"}
    assert convite.formulario_id == form_padrao(client, h, "csat")["id"]   # com referência, padrão CSAT
    # o e-mail saiu com o mesmo link
    m = emails_para("joao@cliente.com.br")[-1]
    assert d["link"].endswith(token_do_convite(m))

    # a resposta herda o contexto do convite
    r = client.post(f"{API}/publico/convites/{token_do_convite(m)}/responder",
                    json={"respostas": {form_padrao(client, h, "csat")["perguntas"][0]["id"]: 5}})
    assert r.status_code == 201, r.text
    (contexto, referencia), = sql(dono, "select contexto, referencia from respostas")
    assert contexto["motorista"] == "Zé" and referencia == "1234"

    # outro evento do mesmo contato (pelo código externo) e da mesma empresa: nada duplicado
    sql(dono, "update contatos set ultimo_envio = null")
    r = evento(client, chave, email="outro@cliente.com.br", codigo_externo="C-77",
               empresa={"nome": "Outro nome", "codigo_externo": "E-1"})
    assert r.json()["contato_id"] == d["contato_id"]
    assert sql(dono, "select count(*) from contatos")[0][0] == 1
    assert sql(dono, "select count(*) from empresas")[0][0] == 1
    assert _convite(dono, r.json()["convite_id"]).formulario_id == form_padrao(client, h, "nps")["id"]


def test_evento_acha_contato_por_email_e_telefone(client, admin, chave, dono):
    h = admin["h"]
    por_email = criar_contato(client, h, email="maria@cliente.com.br")
    por_tel = criar_contato(client, h, email=None, telefone="11987654321")
    empresa = criar_empresa(client, h, "Atacado Sul", documento="11.222.333/0001-81")
    r = evento(client, chave, email="MARIA@cliente.com.br", enviar=False)
    assert r.json()["contato_id"] == por_email["id"]
    # celular sem o nono dígito, como o WhatsApp às vezes informa; empresa achada pelo CNPJ
    r = evento(client, chave, telefone="551187654321", enviar=False, empresa={"documento": "11222333000181"})
    assert r.json()["contato_id"] == por_tel["id"]
    assert client.get(f"{API}/contatos/{por_tel['id']}", headers=h).json()["empresa"]["id"] == empresa["id"]
    assert sql(dono, "select count(*) from contatos")[0][0] == 2


def test_idempotencia_por_24_horas(client, admin, chave, dono, monkeypatch):
    agora = segunda(11)
    fixar_relogio(monkeypatch, agora)
    r1 = evento(client, chave, email="joao@cliente.com.br", id_evento="pedido-1234")
    r2 = evento(client, chave, email="joao@cliente.com.br", id_evento="pedido-1234")
    assert (r1.status_code, r2.status_code) == (201, 200)
    assert r1.json() == r2.json()
    assert sql(dono, "select count(*) from convites")[0][0] == 1
    assert len(emails_para("joao@cliente.com.br")) == 1
    # outro id é outro evento
    r3 = evento(client, chave, email="joao@cliente.com.br", id_evento="pedido-1235", ignorar_descanso=True)
    assert r3.status_code == 201 and r3.json()["convite_id"] != r1.json()["convite_id"]
    # passou 24 h: vale de novo
    fixar_relogio(monkeypatch, agora + timedelta(hours=24, minutes=1))
    r4 = evento(client, chave, email="joao@cliente.com.br", id_evento="pedido-1234", ignorar_descanso=True)
    assert r4.status_code == 201 and r4.json()["convite_id"] not in (r1.json()["convite_id"], r3.json()["convite_id"])


def test_canal_sem_whatsapp(client, admin, chave):
    h = admin["h"]
    so_tel = criar_contato(client, h, email=None, telefone="11911112222")
    r = evento(client, chave, telefone="11911112222")                         # auto: sem e-mail → link
    assert r.status_code == 201
    assert (r.json()["situacao"], r.json()["canal"]) == ("link_gerado", "link") and r.json()["link"]
    assert r.json()["contato_id"] == so_tel["id"]
    r = evento(client, chave, email="x@cliente.com.br", enviar=False)         # enviar: false → só o link
    assert r.json()["situacao"] == "link_gerado" and not emails_para("x@cliente.com.br")
    r = evento(client, chave, email="y@cliente.com.br", canal="link")
    assert r.json()["situacao"] == "link_gerado"
    r = evento(client, chave, telefone="11911112222", canal="email")
    assert r.json() == {"situacao": "sem_canal", "convite_id": None, "link": None, "canal": None,
                        "contato_id": so_tel["id"], "mensagem": "O contato não tem e-mail."}
    r = evento(client, chave, email="z@cliente.com.br", canal="whatsapp")
    assert r.json()["situacao"] == "sem_canal" and "WhatsApp" in r.json()["mensagem"]


def test_ignorados(client, admin, chave, dono):
    h = admin["h"]
    criar_contato(client, h, email="inativo@cliente.com.br", ativo=False)
    criar_contato(client, h, email="fora@cliente.com.br", recebe_pesquisas=False)
    criar_contato(client, h, email="saiu@cliente.com.br")
    client.post(f"{API}/envios/descadastros", headers=h, json={"email": "saiu@cliente.com.br"})
    descanso = criar_contato(client, h, email="descanso@cliente.com.br")
    sql(dono, "update contatos set ultimo_envio = now() - interval '5 days' where id = :c", c=descanso["id"])

    def situacao(email, **extra):
        r = evento(client, chave, email=email, **extra)
        assert r.status_code == 201, r.text
        return r.json()

    d = situacao("inativo@cliente.com.br")
    assert (d["situacao"], d["convite_id"], d["link"]) == ("ignorado_inativo", None, None)
    assert situacao("fora@cliente.com.br")["situacao"] == "ignorado_descadastrado"
    assert situacao("saiu@cliente.com.br", enviar=False)["situacao"] == "ignorado_descadastrado"
    d = situacao("descanso@cliente.com.br")
    assert d["situacao"] == "ignorado_descanso" and d["mensagem"] == \
        "O contato recebeu uma pesquisa há 5 dias (descanso de 30 dias)."
    assert situacao("descanso@cliente.com.br", ignorar_descanso=True)["situacao"] == "enviado"
    assert not emails_para("saiu@cliente.com.br") and not emails_para("inativo@cliente.com.br")


def test_pre_condicoes_e_validacao(client, admin, dono):
    h = admin["h"]
    chave = gerar_chave(client, h)
    # envios desligados: e-mail não sai, mas o link (que não usa e-mail) sai
    r = evento(client, chave, email="joao@cliente.com.br")
    assert r.status_code == 409 and r.json()["erro"]["codigo"] == "pre_condicao"
    assert sql(dono, "select count(*) from contatos")[0][0] == 0           # nada ficou pela metade
    assert evento(client, chave, email="joao@cliente.com.br", enviar=False).status_code == 201
    # assinatura vale sempre
    sql(dono, "update contas set situacao = 'teste', teste_ate = now() - interval '1 day' where id = :c",
        c=admin["conta"]["id"])
    r = evento(client, chave, email="joao@cliente.com.br", enviar=False)
    assert r.status_code == 409 and "período de teste acabou" in r.json()["erro"]["mensagem"]
    sql(dono, "update contas set situacao = 'cortesia' where id = :c", c=admin["conta"]["id"])

    r = evento(client, chave, nome="Sem contato")
    assert r.status_code == 422 and set(r.json()["erro"]["campos"]) == {"email", "telefone"}
    for corpo, campo in [({"email": "nao-e-email"}, "email"), ({"telefone": "123"}, "telefone"),
                         ({"email": "a@b.com.br", "evento": "x" * 61}, "evento"),
                         ({"email": "a@b.com.br", "canal": "sms"}, "canal"),
                         ({"email": "a@b.com.br", "formulario_id": 999999}, "formulario_id"),
                         ({"email": "a@b.com.br", "empresa": {"documento": "123"}}, "empresa.documento")]:
        r = evento(client, chave, **corpo)
        assert r.status_code == 422 and campo in r.json()["erro"]["campos"], (corpo, r.text)


def test_limite_do_plano(client, admin, chave, dono):
    definir_plano(dono, admin["conta"]["id"], "essencial")
    encher_contatos(dono, admin["conta"]["id"], 300)
    r = evento(client, chave, email="novo@cliente.com.br")
    assert r.status_code == 402 and r.json()["erro"]["codigo"] == "limite_do_plano"
    # contato que já existe continua recebendo
    r = evento(client, chave, email="lote1@c%s.com.br" % admin["conta"]["id"])
    assert r.status_code == 201 and r.json()["situacao"] == "enviado"


def test_csat_compativel_com_o_rakiti(client, admin, chave, dono):
    h = admin["h"]
    r = evento(client, chave, "csat", email="joao@cliente.com.br", enviar_email=False, assunto="a entrega de ontem")
    assert r.status_code == 201 and r.json()["situacao"] == "link_gerado"
    convite = _convite(dono, r.json()["convite_id"])
    assert convite.formulario_id == form_padrao(client, h, "csat")["id"] and convite.assunto == "a entrega de ontem"
    r = evento(client, chave, "csat", email="joao@cliente.com.br", enviar_email=True)
    assert r.json()["situacao"] == "enviado"


def test_isolamento_entre_contas(client, admin, chave, dono):
    b = conta_pronta(client, "bia@beta.com.br", empresa="Beta")
    so_em_b = criar_contato(client, b["h"], email="joao@cliente.com.br", codigo_externo="C-1")
    r = evento(client, chave, email="joao@cliente.com.br", codigo_externo="C-1")
    assert r.status_code == 201 and r.json()["contato_id"] != so_em_b["id"]
    contas = sql(dono, "select conta_id from contatos order by id")
    assert [c for c, in contas] == [b["conta"]["id"], admin["conta"]["id"]]
    assert sql(dono, "select count(*) from convites where conta_id = :c", c=b["conta"]["id"])[0][0] == 0


def test_tabelas_novas_tem_rls_forcado(dono, app_engine):
    with dono.connect() as c:
        linhas = c.execute(text("""
            select relname, relrowsecurity, relforcerowsecurity from pg_class
             where relname in ('integracao_chaves','webhooks','webhook_entregas','whatsapp_contas','whatsapp_uso',
                               'eventos_idempotencia')""")).all()
    assert len(linhas) == 6 and all(r and f for _, r, f in linhas)
    with app_engine.connect() as c:  # papel da aplicação, sem contexto: não enxerga nada
        assert c.execute(text("select count(*) from integracao_chaves")).scalar() == 0


"""Zona de risco (etapa 5f): GET = o que o POST apaga, cada opção tabela por tabela, CSAT sem contato (e sem empresa em
Recomeçar), convites sem contato ainda respondem, descadastros intactos, `ultima_nota`, outra conta intacta, tudo ou
nada (falha no meio, tempo esgotado), APAGAR, 409, gestor 403, auditoria e nenhum webhook nem e-mail."""
import pytest
from sqlalchemy import text
from util import (
    API,
    conta_pronta,
    criar_contato,
    criar_empresa,
    form_padrao,
    gerar_chave,
    membro,
    registrar_resposta,
    responder_convite,
    sql,
)

from toqqi.core.db import em_conta
from toqqi.core.email import caixa_memoria
from toqqi.modulos.dados import zona
from toqqi.modulos.respostas.convites import novo_convite

TABELAS = ("respostas", "contatos", "empresas", "convites", "envios", "acoes", "indicacoes", "ofertas",
           "descadastros", "importacoes", "eventos_idempotencia", "emails_enviados", "ia_pareceres", "alertas_pico",
           "webhook_entregas", "usuarios", "formularios", "responsaveis", "grupos", "auditoria")


def _contagem(dono, conta_id: int) -> dict:
    return {t: sql(dono, f"select count(*) from {t} where conta_id = :c", c=conta_id)[0][0] for t in TABELAS}


def _zona(client, h, opcao: str, confirmacao: str | None = "APAGAR"):
    return client.post(f"{API}/conta/zona-de-risco", headers=h, json={"opcao": opcao, "confirmacao": confirmacao})


@pytest.fixture
def cenario(client, dono):
    """Conta com empresas, contatos, respostas NPS (convite, à mão, arquivada), CSAT, convite de CSAT sem contato,
    ação, indicação, oferta, descadastro, parecer da IA, pico e entrega de webhook; e uma outra conta."""
    a = conta_pronta(client, "ana@alfa.com.br", empresa="Alfa")
    h, c = a["h"], a["conta"]["id"]
    e1 = criar_empresa(client, h, "Mercado Um")
    c1 = criar_contato(client, h, nome="Carla Um", email="carla@um.com.br", empresa_id=e1["id"])
    c2 = criar_contato(client, h, nome="Davi Dois", email="davi@dois.com.br", empresa_id=e1["id"])
    c3 = criar_contato(client, h, nome="Eva Tres", email="eva@tres.com.br")
    csat = form_padrao(client, h, "csat")
    responder_convite(client, h, c1["id"], 9)                        # NPS de C1 (mais antiga)
    responder_convite(client, h, c1["id"], 4, formulario=csat)       # CSAT de C1 (a mais recente)
    responder_convite(client, h, c2["id"], 3, formulario=csat)       # CSAT de C2 (mais antiga)
    responder_convite(client, h, c2["id"], 2, comentario="Demorou")  # NPS de C2 (detrator: ação automática)
    r = registrar_resposta(client, h, c3["id"], 10)                  # NPS à mão de C3
    assert r.status_code == 201, r.text
    arquivar = registrar_resposta(client, h, c3["id"], 7).json()["id"]
    assert client.post(f"{API}/respostas/{arquivar}/arquivar", headers=h).status_code in (200, 204)
    # convite de CSAT sem contato (link da integração), da empresa E1
    with em_conta(c) as s:
        _, token_sem_contato = novo_convite(s, csat["id"], canal="link_manual", empresa_id=e1["id"])
    nps_c2 = sql(dono, "select id from respostas where conta_id = :c and contato_id = :k and tipo_nota = 'nps'",
                 c=c, k=c2["id"])[0][0]
    sql(dono, "insert into indicacoes (conta_id, origem, nome, telefone, indicador_contato_id, indicador_empresa_id, "
              "resposta_id) values (:c, 'manual', 'Fulano', '5511999998888', :k, :e, :r)",
        c=c, k=c1["id"], e=e1["id"], r=nps_c2)
    sql(dono, "insert into ofertas (conta_id, empresa_id, contato_id, lista, texto) "
              "values (:c, :e, :k, 'promotores', 'Oferta especial')", c=c, e=e1["id"], k=c1["id"])
    sql(dono, "insert into descadastros (conta_id, email, origem) values (:c, 'saiu@um.com.br', 'manual')", c=c)
    sql(dono, "insert into ia_pareceres (conta_id, tipo, chave, filtros, conteudo, modelo, estilo) "
              "values (:c, 'painel', 'x', '{}', '{}', 'rapido', 'objetiva')", c=c)
    sql(dono, "insert into alertas_pico (conta_id, tema, reclamacoes, media_anterior) values (:c, 'atendimento', 5, 1)",
        c=c)
    sql(dono, "insert into envios (conta_id, contato_id, canal, tipo, origem, situacao, para) "
              "values (:c, :k, 'email', 'convite', 'manual', 'enviado', 'carla@um.com.br')", c=c, k=c1["id"])
    sql(dono, "insert into emails_enviados (conta_id, tipo, destinatario, assunto, situacao) values "
              "(:c, 'convite', 'carla@um.com.br', 'Pesquisa', 'enviado'), "
              "(:c, 'senha', 'ana@alfa.com.br', 'Senha', 'enviado')", c=c)
    sql(dono, "insert into eventos_idempotencia (conta_id, id_evento, resposta, expira) "
              "values (:c, 'pedido-1', '{}', now() + interval '1 day')", c=c)
    # webhook com uma entrega na fila
    w = client.post(f"{API}/integracoes/webhooks", headers=h,
                    json={"url": "https://erp.cliente.com.br/ganchos", "eventos": ["resposta.criada"]})
    assert w.status_code == 201, w.text
    sql(dono, "insert into webhook_entregas (conta_id, webhook_id, evento, corpo, status) "
              "values (:c, :w, 'resposta.criada', '{}', 'falhou')", c=c, w=w.json()["id"])
    gerar_chave(client, h)
    # outra conta
    b = conta_pronta(client, "bia@beta.com.br", empresa="Beta")
    cb = criar_contato(client, b["h"], nome="Bruno Beta", email="bruno@beta.com.br")
    responder_convite(client, b["h"], cb["id"], 8)
    return {"a": a, "h": h, "c": c, "e1": e1, "c1": c1, "c2": c2, "c3": c3, "token": token_sem_contato, "b": b,
            "csat": csat}


def test_get_contagens_e_mantidos(client, dono, cenario):
    c = cenario["c"]
    r = client.get(f"{API}/conta/zona-de-risco", headers=cenario["h"])
    assert r.status_code == 200, r.text
    corpo = r.json()
    acoes_nps = sql(dono, "select count(*) from acoes a join respostas r on r.id = a.resposta_id "
                          "where a.conta_id = :c and r.tipo_nota = 'nps'", c=c)[0][0]
    acoes = sql(dono, "select count(*) from acoes where conta_id = :c", c=c)[0][0]
    assert acoes_nps >= 1
    assert corpo["opcoes"]["respostas"] == {"respostas": 4, "acoes_sem_vinculo": acoes_nps}
    assert corpo["opcoes"]["contatos"] == {"contatos": 3, "respostas": 4, "convites": 4, "envios": 1,
                                           "csat_sem_contato": 2}
    assert corpo["opcoes"]["tudo"] == {**corpo["opcoes"]["contatos"], "empresas": 1, "acoes": acoes,
                                       "indicacoes": 1, "ofertas": 1}
    assert corpo["mantidos"] == {"csat": 2, "descadastros": 1, "usuarios": 1, "formularios": 2}


def test_respostas(client, dono, cenario):
    h, c = cenario["h"], cenario["c"]
    antes = _contagem(dono, c)
    outra = _contagem(dono, cenario["b"]["conta"]["id"])
    previsto = client.get(f"{API}/conta/zona-de-risco", headers=h).json()["opcoes"]["respostas"]
    emails = len(caixa_memoria)
    r = _zona(client, h, "respostas")
    assert r.status_code == 200, r.text
    corpo = r.json()
    assert corpo["opcao"] == "respostas" and corpo["apagados"] == previsto
    assert corpo["mantidos"] == {"csat": 2, "descadastros": 1, "usuarios": 1, "formularios": 2}
    depois = _contagem(dono, c)
    assert depois["respostas"] == antes["respostas"] - 4 == 2
    assert sql(dono, "select count(*) from respostas where conta_id = :c and tipo_nota is distinct from 'csat'",
               c=c)[0][0] == 0
    for t in ("contatos", "empresas", "convites", "envios", "acoes", "indicacoes", "ofertas", "descadastros",
              "importacoes", "eventos_idempotencia", "emails_enviados"):
        assert depois[t] == antes[t], t
    assert (depois["ia_pareceres"], depois["alertas_pico"], depois["webhook_entregas"]) == (0, 0, 0)
    # ações e indicações perdem o vínculo; convites continuam
    assert sql(dono, "select count(*) from acoes where conta_id = :c and resposta_id is not null", c=c)[0][0] == 0
    assert sql(dono, "select resposta_id from indicacoes where conta_id = :c", c=c) == [(None,)]
    # ultima_nota: C1 fica com a CSAT (era a mais recente), C2 passa à CSAT, C3 (só NPS) fica vazia
    notas = dict(sql(dono, "select id, ultima_nota from contatos where conta_id = :c", c=c))
    assert notas == {cenario["c1"]["id"]: 4, cenario["c2"]["id"]: 3, cenario["c3"]["id"]: None}
    # outra conta intacta; nada de e-mail nem webhook
    assert _contagem(dono, cenario["b"]["conta"]["id"]) == outra
    assert len(caixa_memoria) == emails
    aud = sql(dono, "select gravidade, detalhe, usuario_id from auditoria where conta_id = :c and evento = 'zona_risco'",
              c=c)
    assert aud == [("atencao", {"opcao": "respostas", "apagados": previsto, "mantidos": corpo["mantidos"]},
                    cenario["a"]["usuario"]["id"])]


def test_contatos(client, dono, cenario):
    h, c = cenario["h"], cenario["c"]
    antes = _contagem(dono, c)
    previsto = client.get(f"{API}/conta/zona-de-risco", headers=h).json()["opcoes"]["contatos"]
    r = _zona(client, h, "contatos", "apagar")
    assert r.status_code == 200, r.text
    assert r.json()["apagados"] == previsto
    depois = _contagem(dono, c)
    assert (depois["contatos"], depois["envios"], depois["importacoes"], depois["eventos_idempotencia"]) == (0, 0, 0, 0)
    # as CSAT ficam, sem contato e ainda com a empresa; o convite sem contato fica
    assert sql(dono, "select tipo_nota, contato_id, empresa_id is not null from respostas where conta_id = :c",
               c=c) == [("csat", None, True), ("csat", None, True)]
    assert sql(dono, "select contato_id from convites where conta_id = :c", c=c) == [(None,)]
    # e-mails de convite saem; os do sistema ficam
    assert {t for (t,) in sql(dono, "select tipo from emails_enviados where conta_id = :c", c=c)} == {
        "confirmacao", "senha"}
    # ações, ofertas e indicações perdem o contato
    assert {k for (k,) in sql(dono, "select contato_id from acoes where conta_id = :c", c=c)} == {None}
    assert sql(dono, "select contato_id from ofertas where conta_id = :c", c=c) == [(None,)]
    assert sql(dono, "select indicador_contato_id from indicacoes where conta_id = :c", c=c) == [(None,)]
    for t in ("empresas", "acoes", "ofertas", "indicacoes", "descadastros", "usuarios", "formularios"):
        assert depois[t] == antes[t], t
    # o convite sem contato ainda responde
    respostas = {cenario["csat"]["perguntas"][0]["id"]: 5}
    r = client.post(f"{API}/publico/convites/{cenario['token']}/responder", json={"respostas": respostas})
    assert r.status_code == 201, r.text


def test_tudo(client, dono, cenario):
    h, c = cenario["h"], cenario["c"]
    antes = _contagem(dono, c)
    previsto = client.get(f"{API}/conta/zona-de-risco", headers=h).json()["opcoes"]["tudo"]
    r = _zona(client, h, "tudo", " APAGAR ")
    assert r.status_code == 200, r.text
    assert r.json()["apagados"] == previsto
    depois = _contagem(dono, c)
    for t in ("contatos", "empresas", "envios", "acoes", "indicacoes", "ofertas", "ia_pareceres", "alertas_pico",
              "webhook_entregas"):
        assert depois[t] == 0, t
    # CSAT e convite sem contato ficam sem empresa
    assert sql(dono, "select contato_id, empresa_id from respostas where conta_id = :c", c=c) == [(None, None)] * 2
    assert sql(dono, "select contato_id, empresa_id from convites where conta_id = :c", c=c) == [(None, None)]
    for t in ("descadastros", "usuarios", "formularios", "responsaveis", "grupos"):
        assert depois[t] == antes[t], t
    assert sql(dono, "select count(*) from webhooks where conta_id = :c", c=c)[0][0] == 1
    assert sql(dono, "select count(*) from integracao_chaves where conta_id = :c", c=c)[0][0] == 1
    # tudo zerado: as contagens do GET também
    corpo = client.get(f"{API}/conta/zona-de-risco", headers=h).json()
    assert all(v == 0 for v in corpo["opcoes"]["tudo"].values())


@pytest.mark.parametrize("confirmacao", [None, "", "APAGA", "apagar tudo", "A P A G A R"])
def test_confirmacao_errada(client, dono, cenario, confirmacao):
    antes = _contagem(dono, cenario["c"])
    r = _zona(client, cenario["h"], "tudo", confirmacao)
    assert r.status_code == 422, r.text
    assert r.json()["erro"]["campos"] == {"confirmacao": "Digite APAGAR para confirmar."}
    assert _contagem(dono, cenario["c"]) == antes


def test_opcao_invalida(client, cenario):
    r = _zona(client, cenario["h"], "empresas")
    assert r.status_code == 422 and "opcao" in r.json()["erro"]["campos"]


def test_gestor_nao_pode(client, cenario):
    g = membro(client, cenario["h"], "gil@alfa.com.br", perfil="gestor")
    assert client.get(f"{API}/conta/zona-de-risco", headers=g["h"]).status_code == 403
    assert _zona(client, g["h"], "respostas").status_code == 403


def test_outra_em_andamento_409(client, dono, cenario):
    antes = _contagem(dono, cenario["c"])
    with dono.connect() as conexao:
        conexao.execute(text("select pg_advisory_xact_lock(hashtextextended(:k, 0))"),
                        {"k": f"zona_risco:{cenario['c']}"})
        r = _zona(client, cenario["h"], "tudo")
        conexao.rollback()
    assert r.status_code == 409 and r.json()["erro"]["codigo"] == "zona_em_andamento"
    assert _contagem(dono, cenario["c"]) == antes


def test_falha_no_meio_nada_muda(client, dono, cenario, monkeypatch):
    antes = _contagem(dono, cenario["c"])

    def quebrar(*_a, **_k):
        raise RuntimeError("falha forçada")

    monkeypatch.setattr(zona, "_apagar_empresas", quebrar)
    with pytest.raises(RuntimeError):
        _zona(client, cenario["h"], "tudo")
    assert _contagem(dono, cenario["c"]) == antes


def test_tempo_esgotado_503(client, dono, cenario, monkeypatch):
    antes = _contagem(dono, cenario["c"])
    original = zona._apagar_derivados

    def devagar(s, c):
        s.execute(text("select pg_sleep(1)"))
        original(s, c)

    monkeypatch.setattr(zona, "TEMPO_MAXIMO", "100ms")
    monkeypatch.setattr(zona, "_apagar_derivados", devagar)
    r = _zona(client, cenario["h"], "tudo")
    assert r.status_code == 503, r.text
    assert r.json()["erro"] == {"codigo": "zona_indisponivel", "campos": {},
                                "mensagem": "Não deu para apagar agora e nada foi apagado. Tente de novo em alguns "
                                            "minutos."}
    assert _contagem(dono, cenario["c"]) == antes


def test_limite_por_hora(client, cenario):
    from toqqi.core.rate_limit import limiter

    limiter.enabled = True
    limiter.reset()
    try:
        codigos = [_zona(client, cenario["h"], "respostas", "errado").status_code for _ in range(6)]
    finally:
        limiter.enabled = False
        limiter.reset()
    assert codigos == [422] * 5 + [429]

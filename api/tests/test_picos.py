"""Etapa 4b: reclamação por tema (com e sem IA), picos (limiares 3 e 2×, média com zero), picos no painel, alerta
por e-mail uma vez a cada 7 dias, destinatários e preferências."""
import threading
from datetime import date, datetime, time, timedelta

import pytest
from util import (
    API,
    FUSO,
    conta_pronta,
    criar_contato,
    criar_empresa,
    emails_para,
    fixar_relogio,
    form_padrao,
    membro,
    registrar_resposta,
    sql,
)

from toqqi import tarefas
from toqqi.core import relogio
from toqqi.core.config import config
from toqqi.core.email import caixa_memoria
from toqqi.modulos.formularios.validacao import grupo_da_nota
from toqqi.modulos.relatorios import emails

pytestmark = pytest.mark.usefixtures("relogio_estavel")


@pytest.fixture
def conta(client, dono):
    a = conta_pronta(client, "ana@alfa.com.br", empresa="Alfa Distribuidora")
    sql(dono, "update contas set situacao = 'cortesia' where id = :c", c=a["conta"]["id"])
    h = a["h"]
    a["nps"] = form_padrao(client, h)["id"]
    a["csat"] = form_padrao(client, h, "csat")["id"]
    a["empresa"] = criar_empresa(client, h, "Mercado Bom Preço")
    a["inativa"] = criar_empresa(client, h, "Loja Fechada", ativa=False)
    a["contato"] = criar_contato(client, h, nome="Paula Lima", empresa_id=a["empresa"]["id"])
    a["sem_empresa"] = criar_contato(client, h, nome="Rui Sem Empresa")
    a["da_inativa"] = criar_contato(client, h, nome="Cid", empresa_id=a["inativa"]["id"])
    return a


def resposta(dono, a, dias_atras: int, nota: int, temas: list[str], tipo: str = "nps", contato: dict | None = None,
             comentario: str = "", arquivada: bool = False, ia_temas: list | None = None, resumo: str | None = None,
             hoje: date | None = None) -> int:
    """Resposta gravada direto no banco (data, temas e análise da IA sob controle)."""
    import json

    contato = contato or a["contato"]
    quando = datetime.combine((hoje or relogio.hoje()) - timedelta(days=dias_atras), time(12), tzinfo=FUSO)
    (rid,), = sql(dono, """
        insert into respostas (conta_id, formulario_id, contato_id, empresa_id, canal, origem, nota, tipo_nota, grupo,
                               comentario, comentario_cliente, temas, respondida_em, arquivada, ia_situacao, ia_temas,
                               ia_sentimento, ia_resumo)
        values (:conta, :f, :c, :e, 'manual', 'manual', :n, :t, :g, :com, :com, :temas, :quando, :arq, :sit,
                cast(:ia_temas as jsonb), :sent, :resumo)
        returning id
    """, conta=a["conta"]["id"], f=a[tipo], c=contato["id"], e=(contato.get("empresa") or {}).get("id"), n=nota,
        t=tipo, g=grupo_da_nota(tipo, nota), com=comentario, temas=temas, quando=quando, arq=arquivada,
        sit="analisada" if ia_temas is not None else None,
        ia_temas=json.dumps(ia_temas) if ia_temas is not None else None,
        sent="negativo" if ia_temas is not None else None, resumo=resumo)
    return rid


def _picos(client, a) -> list[dict]:
    r = client.get(f"{API}/painel", headers=a["h"])
    assert r.status_code == 200, r.text
    return r.json()["picos"]


# ---- reclamação ---------------------------------------------------------------------

def test_reclamacao_com_e_sem_ia(client, conta, dono):
    a = conta
    # sem IA: vale a nota (detrator/insatisfeito = reclamação; promotor/satisfeito = elogio)
    r1 = resposta(dono, a, 1, 3, ["prazo_entrega", "preco_condicoes"])
    r2 = resposta(dono, a, 1, 2, ["atendimento"], tipo="csat")
    r3 = resposta(dono, a, 1, 9, ["atendimento"])
    r4 = resposta(dono, a, 1, 7, ["atendimento"])
    # com IA: vale o sentimento de cada tema citado; tema que a IA não citou (marcado à mão) vale pela nota
    r5 = resposta(dono, a, 1, 2, ["prazo_entrega", "produto_avarias", "atendimento"],
                  ia_temas=[{"tema": "prazo_entrega", "sentimento": "positivo"},
                            {"tema": "produto_avarias", "sentimento": "negativo"}])
    r6 = resposta(dono, a, 1, 10, ["atendimento", "comunicacao"],
                  ia_temas=[{"tema": "atendimento", "sentimento": "negativo"},
                            {"tema": "comunicacao", "sentimento": "neutro"}])
    linhas = dict((rid, (rec, elo)) for rid, rec, elo in sql(
        dono, "select id, temas_reclamacao, temas_elogio from respostas"))
    assert linhas[r1] == (["prazo_entrega", "preco_condicoes"], [])
    assert linhas[r2] == (["atendimento"], [])
    assert linhas[r3] == ([], ["atendimento"])
    assert linhas[r4] == ([], [])
    assert linhas[r5] == (["produto_avarias", "atendimento"], ["prazo_entrega"])
    assert linhas[r6] == (["atendimento"], [])
    # a análise da IA chegando muda a classificação na hora (coluna gerada)
    sql(dono, """update respostas set ia_situacao = 'analisada',
                 ia_temas = '[{"tema": "prazo_entrega", "sentimento": "positivo"}]' where id = :r""", r=r1)
    assert sql(dono, "select temas_reclamacao from respostas where id = :r", r=r1)[0][0] == ["preco_condicoes"]


# ---- pico -----------------------------------------------------------------------------

def test_limiares_do_pico(client, conta, dono):
    a = conta
    hoje = relogio.hoje()
    # prazo: 3 nos últimos 7 dias (hoje e os 6 anteriores) e nenhuma antes → pico, média 0,0
    for d in (0, 3, 6):
        resposta(dono, a, d, 2, ["prazo_entrega"])
    resposta(dono, a, 35, 2, ["prazo_entrega"])  # fora das 4 semanas anteriores
    # atendimento: só 2 → não é pico
    for d in (1, 2):
        resposta(dono, a, d, 2, ["atendimento"])
    # preço: 4 contra 9 antes (média 2,3: o dobro é 4,6) → não é pico
    for d in (1, 2, 3, 4):
        resposta(dono, a, d, 2, ["preco_condicoes"])
    for d in (7, 10, 14, 15, 20, 21, 28, 30, 34):
        resposta(dono, a, d, 2, ["preco_condicoes"])
    # produto: 5 contra 10 antes (média 2,5: o dobro é 5) → pico; CSAT conta; promotor não reclama
    for d, tipo, nota in ((0, "nps", 0), (1, "nps", 6), (2, "csat", 1), (3, "csat", 2), (4, "nps", 5),
                          (5, "nps", 10)):
        resposta(dono, a, d, nota, ["produto_avarias"], tipo=tipo)
    for d in (8, 9, 11, 12, 13, 16, 17, 18, 19, 22):
        resposta(dono, a, d, 1, ["produto_avarias"])
    # não contam: arquivada, empresa inativa
    for d in (0, 1, 2):
        resposta(dono, a, d, 0, ["sistema_pedidos"], arquivada=True)
        resposta(dono, a, d, 0, ["sistema_pedidos"], contato=a["da_inativa"])
    # sem empresa conta
    for d in (0, 1, 2):
        resposta(dono, a, d, 0, ["comunicacao"], contato=a["sem_empresa"])
    assert _picos(client, a) == [
        {"tema": "produto_avarias", "rotulo": "Produto e avarias", "reclamacoes": 5, "media_anterior": 2.5,
         "de": (hoje - timedelta(days=6)).isoformat(), "ate": hoje.isoformat()},
        {"tema": "prazo_entrega", "rotulo": "Prazo e entrega", "reclamacoes": 3, "media_anterior": 0.0,
         "de": (hoje - timedelta(days=6)).isoformat(), "ate": hoje.isoformat()},
        {"tema": "comunicacao", "rotulo": "Comunicação", "reclamacoes": 3, "media_anterior": 0.0,
         "de": (hoje - timedelta(days=6)).isoformat(), "ate": hoje.isoformat()},
    ]
    # o filtro da tela não muda os picos
    g = client.post(f"{API}/cadastros/grupos", headers=a["h"], json={"nome": "Rede"}).json()
    p = client.get(f"{API}/painel", headers=a["h"], params={"grupo_id": g["id"], "de": "2020-01-01",
                                                             "ate": "2020-01-31"}).json()
    assert [x["tema"] for x in p["picos"]] == ["produto_avarias", "prazo_entrega", "comunicacao"]


def test_dia_de_sao_paulo_na_janela(client, conta, dono):
    """A janela é de dias em São Paulo: 23:30 de 7 dias atrás fica nas semanas anteriores."""
    a = conta
    for d in (0, 1, 2):
        resposta(dono, a, d, 2, ["prazo_entrega"])
    rid = resposta(dono, a, 7, 2, ["prazo_entrega"])
    limite = datetime.combine(relogio.hoje() - timedelta(days=7), time(23, 30), tzinfo=FUSO)
    sql(dono, "update respostas set respondida_em = :q where id = :r", q=limite, r=rid)
    assert _picos(client, a)[0]["media_anterior"] == 0.3  # 1 ÷ 4 → 0,25 → 0,3 (meio para cima)
    sql(dono, "update respostas set respondida_em = :q where id = :r", q=limite + timedelta(hours=1), r=rid)
    assert _picos(client, a)[0]["reclamacoes"] == 4 and _picos(client, a)[0]["media_anterior"] == 0.0


# ---- alerta por e-mail ----------------------------------------------------------------------

def _pico_de_prazo(dono, a, hoje=None):
    for d, comentario, resumo in ((0, "A entrega atrasou três dias", "Reclama do atraso na entrega"),
                                  (1, "x" * 300, None), (2, "", None), (3, "Motorista grosseiro", None),
                                  (4, "Frete caro", None), (5, "Atrasou de novo", None)):
        resposta(dono, a, d, 2, ["prazo_entrega"], comentario=comentario, hoje=hoje, resumo=resumo,
                 ia_temas=[{"tema": "prazo_entrega", "sentimento": "negativo"}] if resumo else None)


def test_alerta_de_pico_uma_vez_a_cada_7_dias(client, conta, dono, monkeypatch):
    a = conta
    hoje = relogio.hoje()
    _pico_de_prazo(dono, a)
    caixa_memoria.clear()
    assert tarefas.executar("picos")["picos"] == {"picos": 1, "emails": 1}
    m, = emails_para("ana@alfa.com.br")
    assert m.assunto == "Pico de reclamações: Prazo e entrega"
    assert ("Nos últimos 7 dias, 6 respostas reclamaram de prazo e entrega. Nas 4 semanas anteriores, a média era "
            "de 0,0 por semana.") in m.texto
    linhas = m.texto.split("\n\n")
    exemplos = linhas[linhas.index("RECLAMAÇÕES RECENTES") + 1:][:5]
    assert exemplos[0] == "Mercado Bom Preço · nota 2 · Reclama do atraso na entrega"  # resumo da IA
    assert exemplos[1] == "Mercado Bom Preço · nota 2 · " + "x" * 199 + "…"  # comentário cortado em 200
    assert exemplos[2] == "Mercado Bom Preço · nota 2"  # sem texto
    assert len(exemplos) == 5 and "Atrasou de novo" not in m.texto  # até 5, mais recentes primeiro
    link = (f"http://app.teste/respostas?tema=prazo_entrega&amp;reclamacao=true&amp;so_ativos=true&amp;"
            f"de={(hoje - timedelta(days=6)).isoformat()}&amp;ate={hoje.isoformat()}")
    assert link in m.html and "Ver as respostas" in m.html
    assert ("Você recebe este e-mail porque acompanha o painel da Alfa Distribuidora. Para parar, desligue em "
            '<a href="http://app.teste/minha-conta"') in m.html
    (reclamacoes, media, enviado, destinatarios), = sql(
        dono, "select reclamacoes, media_anterior, enviado_em, destinatarios from alertas_pico")
    assert (reclamacoes, float(media), destinatarios) == (6, 0.0, 1) and enviado is not None
    # mesma rodada de novo, ou daqui a 6 dias: não repete
    assert tarefas.executar("picos")["picos"] == {"picos": 0, "emails": 0}
    fixar_relogio(monkeypatch, relogio.agora() + timedelta(days=6))
    _pico_de_prazo(dono, a, hoje=relogio.hoje())
    assert tarefas.executar("picos")["picos"] == {"picos": 0, "emails": 0}
    # passados 7 dias, alerta de novo
    fixar_relogio(monkeypatch, relogio.agora() + timedelta(days=2))
    _pico_de_prazo(dono, a, hoje=relogio.hoje())
    assert tarefas.executar("picos")["picos"]["picos"] == 1
    assert sql(dono, "select count(*) from alertas_pico")[0][0] == 2


def test_duas_rodadas_ao_mesmo_tempo_nao_duplicam(client, conta, dono):
    a = conta
    _pico_de_prazo(dono, a)
    resultados = []
    tarefas_ = [threading.Thread(target=lambda: resultados.append(emails.picos_conta(a["conta"]["id"])))
                for _ in range(3)]
    for t in tarefas_:
        t.start()
    for t in tarefas_:
        t.join(30)
    assert sorted(r["picos"] for r in resultados) == [0, 0, 1]
    assert sql(dono, "select count(*) from alertas_pico")[0][0] == 1


def test_destinatarios_e_preferencias(client, conta, dono):
    a = conta
    h = a["h"]
    gestor = membro(client, h, "gil@alfa.com.br", "gestor")
    membro(client, h, "caio@alfa.com.br", "consulta")
    membro(client, h, "bia@alfa.com.br", "consulta")
    membro(client, h, "rui@alfa.com.br", "gestor")
    membro(client, h, "eva@alfa.com.br", "gestor")
    client.patch(f"{API}/eu", headers=gestor["h"], json={"recebe_alertas": False})  # desligou o alerta
    sql(dono, "update usuarios set email_confirmado = false where email = 'rui@alfa.com.br'")
    sql(dono, "update usuarios set situacao = 'bloqueado' where email = 'eva@alfa.com.br'")
    sql(dono, "delete from perfil_permissoes where perfil = 'consulta' and permissao = 'painel.ver'")
    sql(dono, "update usuarios set perfil = 'gestor' where email = 'bia@alfa.com.br'")
    _pico_de_prazo(dono, a)
    caixa_memoria.clear()
    assert tarefas.executar("picos")["picos"] == {"picos": 1, "emails": 2}
    assert sorted(m.para for m in caixa_memoria) == ["ana@alfa.com.br", "bia@alfa.com.br"]
    assert sql(dono, "select destinatarios from alertas_pico")[0][0] == 2
    # o resumo semanal usa a outra preferência
    from toqqi.core.db import em_conta

    with em_conta(a["conta"]["id"]) as s:
        assert emails.destinatarios(s, "recebe_resumo_semanal") == [
            "ana@alfa.com.br", "gil@alfa.com.br", "bia@alfa.com.br"]


@pytest.mark.parametrize("ajuste", ["sem_provedor", "assinatura_vencida"])
def test_sem_provedor_ou_assinatura_nao_alerta(client, conta, dono, monkeypatch, ajuste):
    a = conta
    _pico_de_prazo(dono, a)
    if ajuste == "sem_provedor":
        monkeypatch.setattr(config(), "EMAIL_PROVIDER", "console")
        monkeypatch.setattr(config(), "AMBIENTE", "producao")
    else:
        # cancelada, com o período pago e o teste já acabados (o mais tarde dos dois vale)
        sql(dono, "update contas set situacao = 'cancelada', teste_ate = now() - interval '30 days' where id = :c",
            c=a["conta"]["id"])
    caixa_memoria.clear()
    assert tarefas.executar("picos")["picos"] == {"picos": 0, "emails": 0}
    assert sql(dono, "select count(*) from alertas_pico")[0][0] == 0
    assert caixa_memoria == []


def test_reclamacao_pela_ia_conta_no_pico(client, conta, dono):
    """Respostas novas analisadas pela IA (provedor de testes: sentimento pela nota) entram no pico."""
    a = conta
    for _ in range(3):
        registrar_resposta(client, a["h"], a["contato"]["id"], 1, comentario="O site caiu de novo")
    assert [x["tema"] for x in _picos(client, a)] == ["sistema_pedidos"]

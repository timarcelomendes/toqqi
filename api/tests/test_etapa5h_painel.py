"""Etapa 5h §2 (docs/api-etapa-5h.md): o painel ganha `tom.ia_ligada` e `tom.sem_analise` (o bloco do tom sabe se
oferece "Analisar agora") e `atencao.detratores_sem_plano` (quantos planos `POST /acoes/detratores` criaria agora,
com os mesmos filtros)."""
from datetime import timedelta

import pytest
from test_painel import Dados, _painel
from util import (
    API,
    conta_pronta,
    criar_contato,
    criar_empresa,
    criar_responsavel,
    form_padrao,
    sem_passos,
    sql,
)

from toqqi.core.config import config

pytestmark = pytest.mark.usefixtures("relogio_estavel")


@pytest.fixture
def cena(client, dono, relogio_estavel):
    """Detratores nos últimos 90 dias (e um de 200 dias atrás), com e sem plano aberto, com e sem empresa."""
    hoje = relogio_estavel
    a = conta_pronta(client, "ana@alfa.com.br", empresa="Alfa Distribuidora")
    h = a["h"]
    sem_passos(dono, a["conta"]["id"])
    g1 = client.post(f"{API}/cadastros/grupos", headers=h, json={"nome": "Rede Leste"}).json()
    rita = criar_responsavel(client, h, "Rita Gomes", email="rita@alfa.com.br")
    e = {
        "norte": criar_empresa(client, h, "Atacado Norte", grupo_id=g1["id"], responsavel_id=rita["id"]),
        "sul": criar_empresa(client, h, "Mercado Sul", grupo_id=g1["id"]),
        "padaria": criar_empresa(client, h, "Padaria Leste", ativa=False),
        "loja": criar_empresa(client, h, "Loja Oeste"),
        "bazar": criar_empresa(client, h, "Bazar Centro"),
        "feira": criar_empresa(client, h, "Feira Norte"),
        "antiga": criar_empresa(client, h, "Casa Antiga"),
    }
    c = {k: criar_contato(client, h, nome=f"Contato {v['nome']}", empresa_id=v["id"]) for k, v in e.items()}
    c["sem1"] = criar_contato(client, h, nome="Ciro Seis")
    c["sem2"] = criar_contato(client, h, nome="Célia Sete")
    d = Dados(dono, a["conta"]["id"], form_padrao(client, h)["id"], form_padrao(client, h, "csat")["id"])

    def dia(n: int) -> str:
        return (hoje - timedelta(days=n)).isoformat()

    r = {
        "norte_antes": d.resposta(c["norte"], 5, dia(10), comentario="Atrasou"),
        "norte": d.resposta(c["norte"], 3, dia(5), comentario="Frete caro"),  # a mais recente da empresa
        "sul": d.resposta(c["sul"], 2, dia(20), comentario="Produto quebrado"),
        "sul_promotor": d.resposta(c["sul"], 10, dia(2), comentario="Agora melhorou"),
        "padaria": d.resposta(c["padaria"], 0, dia(3), comentario="Péssimo"),  # empresa inativa
        "loja": d.resposta(c["loja"], 6, dia(8), comentario="Demorou"),  # tem plano aberto
        "bazar": d.resposta(c["bazar"], 4, dia(12), comentario="Sem retorno"),  # o plano dela está concluído
        "sem1": d.resposta(c["sem1"], 1, dia(6), comentario="Horrível"),  # contato sem empresa
        "sem2": d.resposta(c["sem2"], 2, dia(7)),  # contato sem empresa com plano aberto
        "anonima": d.resposta(None, 0, dia(1), comentario="Sem identificação"),  # fica de fora
        "feira_csat": d.resposta(c["feira"], 1, dia(4), tipo="csat", comentario="Ruim"),  # CSAT não conta
        "feira_arquivada": d.resposta(c["feira"], 0, dia(4), arquivada=True),  # arquivada não conta
        "antiga": d.resposta(c["antiga"], 5, dia(200), comentario="Faz tempo"),  # fora dos 90 dias
    }
    d.acao("Plano da loja", e["loja"])
    d.acao("Plano do bazar", e["bazar"], situacao="concluida")
    (acao_sem2,), = sql(dono, "insert into acoes (conta_id, contato_id, titulo, prioridade, situacao, origem) "
                              "values (:c, :ct, 'Plano da Célia', 'media', 'em_andamento', 'manual') returning id",
                        c=a["conta"]["id"], ct=c["sem2"]["id"])
    return {"a": a, "h": h, "g1": g1, "rita": rita, "e": e, "c": c, "r": r, "hoje": hoje, "dados": d,
            "noventa": {"de": dia(89), "ate": hoje.isoformat()}}


def _sem_plano(client, h, **filtros) -> int:
    return _painel(client, h, **filtros)["atencao"]["detratores_sem_plano"]


# ---- detratores sem plano ---------------------------------------------------------------

def test_detratores_sem_plano_por_filtro(client, cena):
    h, noventa = cena["h"], cena["noventa"]
    # Atacado Norte, Mercado Sul, Bazar Centro (plano concluído) e Ciro (sem empresa); a Loja Oeste e a Célia têm
    # plano aberto; a Padaria Leste é inativa; a anônima, o CSAT e a arquivada não contam; a Casa Antiga é de 200 dias
    assert _sem_plano(client, h, **noventa) == 4
    assert _sem_plano(client, h, so_ativos="false", **noventa) == 5
    assert _sem_plano(client, h, grupo_id=cena["g1"]["id"], **noventa) == 2  # sem empresa fica fora do grupo
    assert _sem_plano(client, h) == 5  # todo o histórico: + Casa Antiga
    assert _sem_plano(client, h, de=noventa["ate"], ate=noventa["ate"]) == 0
    # um plano em andamento também conta como aberto
    cena["dados"].acao("Plano do norte", cena["e"]["norte"], situacao="em_andamento")
    assert _sem_plano(client, h, **noventa) == 3


def test_detratores_sem_plano_e_isolado_por_conta(client, cena, dono):
    b = conta_pronta(client, "bia@beta.com.br", empresa="Beta")
    hb = b["h"]
    db = Dados(dono, b["conta"]["id"], form_padrao(client, hb)["id"], form_padrao(client, hb, "csat")["id"])
    eb = criar_empresa(client, hb, "Empresa B")
    cb = criar_contato(client, hb, empresa_id=eb["id"])
    db.resposta(cb, 0, (cena["hoje"] - timedelta(days=1)).isoformat())
    assert _sem_plano(client, hb, **cena["noventa"]) == 1
    assert _sem_plano(client, cena["h"], **cena["noventa"]) == 4
    # um plano aberto de B não esconde a empresa de A (e vice-versa)
    db.acao("Plano de B", eb)
    assert _sem_plano(client, hb, **cena["noventa"]) == 0
    assert _sem_plano(client, cena["h"], **cena["noventa"]) == 4


# ---- tom: ia_ligada e sem_analise -------------------------------------------------------------

def test_tom_sem_analise(client, cena, dono):
    h, r, noventa = cena["h"], cena["r"], cena["noventa"]
    t = _painel(client, h, **noventa)["tom"]
    # com comentário de 3+ letras, NPS e CSAT, só ativas, não arquivadas, no período: Atrasou, Frete caro, Produto
    # quebrado, Agora melhorou, Demorou, Sem retorno, Horrível, Sem identificação, Ruim (CSAT)
    assert (t["ia_ligada"], t["sem_analise"], t["com_comentario"], t["analisados"], t["pendentes"]) == (
        True, 9, 9, 0, 0)

    def situacao(chave: str, valor: str, sentimento: str | None = None) -> None:
        sql(dono, "update respostas set ia_situacao = :s, ia_sentimento = :t where id = :r", s=valor, t=sentimento,
            r=r[chave])

    situacao("norte", "analisada", "negativo")  # analisada: sai
    situacao("sul", "pendente")  # na fila: sai
    situacao("loja", "falhou")  # falhou: continua sem análise
    situacao("bazar", "limite")  # limite: continua sem análise
    sql(dono, "update respostas set comentario = 'ok', comentario_cliente = 'ok' where id = :r", r=r["sem1"])
    t = _painel(client, h, **noventa)["tom"]
    assert (t["sem_analise"], t["analisados"], t["pendentes"], t["com_comentario"]) == (6, 1, 1, 9)  # "ok": curto
    assert _painel(client, h, so_ativos="false", **noventa)["tom"]["sem_analise"] == 7  # + Péssimo (inativa)
    assert _painel(client, h)["tom"]["sem_analise"] == 7  # todo o histórico: + Faz tempo
    assert _painel(client, h, grupo_id=cena["g1"]["id"], **noventa)["tom"]["sem_analise"] == 2  # Atrasou, Agora...


@pytest.mark.parametrize("caso,ligada", [("padrao", True), ("desligada_na_conta", False),
                                         ("sem_ia_na_plataforma", False), ("conta_nao_liberada", True)])
def test_tom_ia_ligada(client, cena, dono, monkeypatch, caso, ligada):
    h = cena["h"]
    if caso == "desligada_na_conta":
        assert client.put(f"{API}/conta/ia", headers=h, json={"analise_respostas": False}).status_code == 200
    elif caso == "sem_ia_na_plataforma":
        monkeypatch.setattr(config(), "IA_PROVEDOR", "desligado")
    elif caso == "conta_nao_liberada":  # ia_ligada não olha a assinatura (o "Analisar agora" é que avisa)
        sql(dono, "update contas set teste_ate = now() - interval '1 day' where id = :c", c=cena["a"]["conta"]["id"])
    t = _painel(client, h, **cena["noventa"])["tom"]
    assert t["ia_ligada"] is ligada
    assert t["sem_analise"] == 9  # a contagem não depende da IA estar ligada

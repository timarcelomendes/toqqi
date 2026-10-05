"""Etapa 5h §2 (docs/api-etapa-5h.md): `POST /acoes/detratores` (acoes.tratar), com os filtros do painel. Para cada
empresa (ou contato sem empresa) com detrator no filtro e sem ação aberta, uma ação a partir da resposta de detrator
mais recente, com o título, a prioridade, o prazo, o responsável e a descrição da automática; origem `manual`,
`criado_por` = quem pediu, passos da IA como hoje; até 100 por chamada (as mais urgentes primeiro) com `restantes`;
uma transação só; auditoria `acoes_detratores_criadas`. Usa o cenário de `test_etapa5h_painel.py`."""
from datetime import timedelta

import pytest
import test_etapa5h_painel
from util import API, conta_pronta, emails_para, form_padrao, membro, sql

from toqqi.core import relogio

cena = test_etapa5h_painel.cena  # a mesma fixture
pytestmark = pytest.mark.usefixtures("relogio_estavel")
CAMPOS = ("titulo", "prioridade", "prazo", "situacao", "origem", "criado_por", "resposta_id", "empresa_id",
          "contato_id", "responsavel_id", "grupo", "tipo_nota", "nota", "descricao")


def _criar(client, h, **filtros):
    return client.post(f"{API}/acoes/detratores", headers=h, json=filtros)


def _acoes(dono, conta_id: int, origem: str = "manual") -> list[dict]:
    linhas = sql(dono, f"select {', '.join(CAMPOS)} from acoes where conta_id = :c and origem = :o and titulo like '[%' "
                       "order by id", c=conta_id, o=origem)
    return [dict(zip(CAMPOS, x, strict=True)) for x in linhas]


def _sem_plano(client, h, **filtros) -> int:
    r = client.get(f"{API}/painel", headers=h, params=filtros)
    assert r.status_code == 200, r.text
    return r.json()["atencao"]["detratores_sem_plano"]


def _eventos(dono, conta_id: int) -> list:
    return [x[0] for x in sql(dono, "select detalhe from auditoria where conta_id = :c and "
                                    "evento = 'acoes_detratores_criadas' order by id", c=conta_id)]


def test_um_plano_por_empresa_na_ordem_de_urgencia(client, cena, dono):
    h, conta, r, e, c = cena["h"], cena["a"]["conta"]["id"], cena["r"], cena["e"], cena["c"]
    usuario = cena["a"]["usuario"]["id"]
    assert client.put(f"{API}/acoes/configuracao", headers=h, json={"prazo_detrator": 3}).status_code == 200
    antes = len(emails_para("rita@alfa.com.br"))
    resultado = _criar(client, h, **cena["noventa"])
    assert resultado.status_code == 200, resultado.text
    assert resultado.json() == {"criadas": 4, "restantes": 0}
    prazo = relogio.hoje() + timedelta(days=3)
    comum = {"prioridade": "alta", "prazo": prazo, "situacao": "a_fazer", "origem": "manual", "criado_por": usuario,
             "grupo": "detrator", "tipo_nota": "nps"}
    # menor nota primeiro: Ciro (1), Mercado Sul (2), Atacado Norte (3, a mais recente das duas), Bazar Centro (4)
    assert _acoes(dono, conta) == [
        {**comum, "titulo": "[Detrator NPS 1] Ação requerida: Ciro Seis", "resposta_id": r["sem1"], "empresa_id": None,
         "contato_id": c["sem1"]["id"], "responsavel_id": None, "nota": 1,
         "descricao": "Comentário do cliente: Horrível\nContato: Ciro Seis"},
        {**comum, "titulo": "[Detrator NPS 2] Ação requerida: Mercado Sul", "resposta_id": r["sul"],
         "empresa_id": e["sul"]["id"], "contato_id": c["sul"]["id"], "responsavel_id": None, "nota": 2,
         "descricao": "Comentário do cliente: Produto quebrado\nContato: Contato Mercado Sul"},
        {**comum, "titulo": "[Detrator NPS 3] Ação requerida: Atacado Norte", "resposta_id": r["norte"],
         "empresa_id": e["norte"]["id"], "contato_id": c["norte"]["id"], "responsavel_id": cena["rita"]["id"],
         "nota": 3, "descricao": "Comentário do cliente: Frete caro\nContato: Contato Atacado Norte"},
        {**comum, "titulo": "[Detrator NPS 4] Ação requerida: Bazar Centro", "resposta_id": r["bazar"],
         "empresa_id": e["bazar"]["id"], "contato_id": c["bazar"]["id"], "responsavel_id": None, "nota": 4,
         "descricao": "Comentário do cliente: Sem retorno\nContato: Contato Bazar Centro"},
    ]
    # pela API: a ação mostra quem criou e a resposta de origem
    norte = next(a for a in client.get(f"{API}/acoes", headers=h).json()["itens"]
                 if a["titulo"].endswith("Atacado Norte"))
    assert norte["criado_por"] == {"id": usuario, "nome": cena["a"]["usuario"]["nome"]}
    assert norte["resposta"]["id"] == r["norte"] and norte["prazo_selo"] is None
    assert norte["responsavel"]["nome"] == "Rita Gomes"
    # sem "Alerta de risco" (são respostas que já estavam lá)
    assert len(emails_para("rita@alfa.com.br")) == antes
    assert _eventos(dono, conta) == [{"criadas": 4}]
    ev = next(i for i in client.get(f"{API}/auditoria", headers=h).json()["itens"]
              if i["evento"] == "acoes_detratores_criadas")
    assert (ev["rotulo"], ev["grupo"]) == ("Planos de ação criados para os detratores sem plano", "dados")
    # sem duplicar: de novo, nada; o painel não conta mais nenhum
    assert _sem_plano(client, h, **cena["noventa"]) == 0
    assert _criar(client, h, **cena["noventa"]).json() == {"criadas": 0, "restantes": 0}
    assert len(_acoes(dono, conta)) == 4 and len(_eventos(dono, conta)) == 1


def test_filtros_do_painel(client, cena, dono):
    h, conta, noventa, e = cena["h"], cena["a"]["conta"]["id"], cena["noventa"], cena["e"]

    def empresas() -> list:
        return [x["empresa_id"] for x in _acoes(dono, conta)]

    assert _criar(client, h, grupo_id=cena["g1"]["id"], **noventa).json() == {"criadas": 2, "restantes": 0}
    assert empresas() == [e["sul"]["id"], e["norte"]["id"]]
    # todas as empresas (inclusive a inativa): a Padaria Leste (0) vem primeiro
    assert _criar(client, h, so_ativos=False, **noventa).json() == {"criadas": 3, "restantes": 0}
    assert empresas()[2:] == [e["padaria"]["id"], None, e["bazar"]["id"]]
    # sem corpo: todo o histórico, só ativas (a Casa Antiga, de 200 dias)
    r = client.post(f"{API}/acoes/detratores", headers=h)
    assert r.status_code == 200 and r.json() == {"criadas": 1, "restantes": 0}
    assert empresas()[-1] == e["antiga"]["id"]
    # período sem detrator
    assert _criar(client, h, de=noventa["ate"], ate=noventa["ate"]).json() == {"criadas": 0, "restantes": 0}
    # período invertido
    r = _criar(client, h, de=noventa["ate"], ate=noventa["de"])
    assert r.status_code == 422 and "de" in r.json()["erro"]["campos"]


def test_ate_100_por_chamada_e_restantes(client, dono):
    a = conta_pronta(client, "caio@gama.com.br", empresa="Gama")
    h, conta = a["h"], a["conta"]["id"]
    sql(dono, "update contas set ia_passos_acoes = false where id = :c", c=conta)
    nps = form_padrao(client, h)["id"]
    sql(dono, "insert into empresas (conta_id, nome) select :c, 'Empresa ' || lpad(g::text, 3, '0') "
              "from generate_series(1, 102) g", c=conta)
    # 100 com nota 2 e as 2 últimas com nota 6 (menos urgentes): ficam para a próxima chamada
    sql(dono, """
        insert into respostas (conta_id, formulario_id, empresa_id, canal, origem, nota, tipo_nota, grupo, comentario,
                               comentario_cliente, respondida_em)
        select :c, :f, e.id, 'importacao', 'importacao', case when e.nome > 'Empresa 100' then 6 else 2 end, 'nps',
               'detrator', '', '', now() - interval '1 day'
          from empresas e where e.conta_id = :c
    """, c=conta, f=nps)
    assert _sem_plano(client, h) == 102
    assert _criar(client, h).json() == {"criadas": 100, "restantes": 2}
    assert {x["nota"] for x in _acoes(dono, conta)} == {2}
    assert _sem_plano(client, h) == 2
    assert _criar(client, h).json() == {"criadas": 2, "restantes": 0}
    assert [x["nota"] for x in _acoes(dono, conta)][-2:] == [6, 6]
    assert _eventos(dono, conta) == [{"criadas": 100}, {"criadas": 2}]


def test_duas_chamadas_ao_mesmo_tempo_nao_duplicam(client, cena, dono, monkeypatch):
    import threading
    import time

    from fastapi.testclient import TestClient

    from toqqi.modulos.acoes import detratores

    montar = detratores.montar_acao

    def devagar(*a, **k):
        time.sleep(0.2)  # alarga a janela entre achar quem não tem plano e gravar
        return montar(*a, **k)

    monkeypatch.setattr(detratores, "montar_acao", devagar)
    resultados = []

    def criar():
        with TestClient(client.app) as outro:
            resultados.append(outro.post(f"{API}/acoes/detratores", headers=cena["h"], json=cena["noventa"]))

    tarefas = [threading.Thread(target=criar) for _ in range(2)]
    for t in tarefas:
        t.start()
    for t in tarefas:
        t.join(30)
    assert sorted(r.json()["criadas"] for r in resultados) == [0, 4], [r.text for r in resultados]
    assert len(_acoes(dono, cena["a"]["conta"]["id"])) == 4


def test_passos_da_ia_como_hoje(client, cena, dono):
    h, conta = cena["h"], cena["a"]["conta"]["id"]
    sql(dono, "update contas set ia_passos_acoes = true where id = :c", c=conta)
    assert _criar(client, h, **cena["noventa"]).json()["criadas"] == 4
    # sugeridos logo depois do commit (provedor de testes), a partir do comentário de cada resposta
    passos = sql(dono, "select ia_passos_situacao, ia_passos from acoes where conta_id = :c and origem = 'manual' "
                       "and titulo like '[%' order by id", c=conta)
    assert [x[0] for x in passos] == ["pronta"] * 4
    assert "Horrível" in passos[0][1][0]


def test_permissao(client, cena, dono):
    h = cena["h"]
    consulta = membro(client, h, "caio@alfa.com.br", "consulta")  # consulta trata planos de ação por padrão
    assert _criar(client, consulta["h"], **cena["noventa"]).json() == {"criadas": 4, "restantes": 0}
    perms = client.get(f"{API}/equipe/permissoes", headers=h).json()
    sem_tratar = [p for p in perms["consulta"] if p != "acoes.tratar"]
    r = client.put(f"{API}/equipe/permissoes", headers=h, json={"gestor": perms["gestor"], "consulta": sem_tratar})
    assert r.status_code == 200, r.text
    r = _criar(client, consulta["h"])
    assert r.status_code == 403 and r.json()["erro"]["codigo"] == "sem_permissao"
    assert client.post(f"{API}/acoes/detratores").status_code == 401
    assert sql(dono, "select criado_por from acoes where origem = 'manual' and titulo like '[%' group by criado_por") == [
        (consulta["usuario"]["id"],)]


def test_uma_conta_nao_cria_na_outra(client, cena, dono):
    b = conta_pronta(client, "bia@beta.com.br", empresa="Beta")
    hb = b["h"]
    sql(dono, "update contas set ia_passos_acoes = false where id = :c", c=b["conta"]["id"])
    db = test_etapa5h_painel.Dados(dono, b["conta"]["id"], form_padrao(client, hb)["id"],
                                   form_padrao(client, hb, "csat")["id"])
    eb = client.post(f"{API}/empresas", headers=hb, json={"nome": "Empresa B"}).json()
    cb = client.post(f"{API}/contatos", headers=hb, json={"nome": "Bento", "email": "bento@b.com.br",
                                                          "empresa_id": eb["id"]}).json()
    db.resposta(cb, 0, (cena["hoje"] - timedelta(days=1)).isoformat())
    assert _criar(client, cena["h"], **cena["noventa"]).json() == {"criadas": 4, "restantes": 0}
    assert _acoes(dono, b["conta"]["id"]) == []
    assert _sem_plano(client, hb, **cena["noventa"]) == 1
    assert _criar(client, hb, **cena["noventa"]).json() == {"criadas": 1, "restantes": 0}
    assert [x["empresa_id"] for x in _acoes(dono, b["conta"]["id"])] == [eb["id"]]
    assert len(_acoes(dono, cena["a"]["conta"]["id"])) == 4
    # a empresa de B com plano não muda a contagem de A, e A não vê a ação de B
    assert all(not x["titulo"].endswith("Empresa B") for x in client.get(f"{API}/acoes", headers=cena["h"]).json()["itens"])

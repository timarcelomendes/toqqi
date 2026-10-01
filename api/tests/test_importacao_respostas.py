"""Etapa 4a: importação de respostas antigas (modelo, análise com tipo, regras por linha, atualizar ou manter,
tudo ou nada, sem efeitos de resposta nova)."""
import json
from datetime import datetime, timedelta
from time import perf_counter

import pytest
from util import (
    API,
    FUSO,
    conta_pronta,
    criar_contato,
    criar_empresa,
    criar_responsavel,
    emails_para,
    form_padrao,
    historico,
    ligar_envios,
    lista_respostas,
    membro,
    quadro,
    registrar_resposta,
    sql,
)

from toqqi import tarefas
from toqqi.core import relogio
from toqqi.modulos.importacao.respostas import interpretar_nota

pytestmark = pytest.mark.usefixtures("relogio_estavel")


@pytest.fixture
def admin(client):
    return conta_pronta(client, "ana@alfa.com.br", empresa="Alfa Distribuidora")


def _csv(linhas: list[list[str]]) -> bytes:
    return "\r\n".join(";".join(x) for x in linhas).encode("utf-8-sig")


def analisar(client, h, linhas, tipo: str | None = "respostas", nome: str = "historico.csv"):
    dados = {"tipo": tipo} if tipo else {}
    return client.post(f"{API}/importacao/analisar", headers=h, files={"arquivo": (nome, _csv(linhas))}, data=dados)


def _ok(client, h, linhas, **kw) -> dict:
    r = analisar(client, h, linhas, **kw)
    assert r.status_code == 200, r.text
    return r.json()


def _corpo(d: dict, **extra) -> dict:
    return {"mapeamento": d["mapeamento_sugerido"], **extra}


@pytest.mark.parametrize("valor,nota", [("9", 9), ("9,0", 9), ("9.0", 9), (" 10 ", 10), ("0", 0), ("7,00", 7)])
def test_nota_inteira(valor, nota):
    assert interpretar_nota(valor) == nota


@pytest.mark.parametrize("valor", ["8,7", "9.5", "11", "-1", "dez", "", "1e"])
def test_nota_recusada(valor):
    with pytest.raises(ValueError, match="A nota precisa ser um número inteiro de 0 a 10."):
        interpretar_nota(valor)


def test_modelo_e_analise(client, admin):
    h = admin["h"]
    r = client.get(f"{API}/importacao/modelo?tipo=respostas", headers=h)
    assert r.status_code == 200 and r.content.startswith(b"\xef\xbb\xbf")
    assert 'filename="modelo-respostas.csv"' in r.headers["content-disposition"]
    linhas = r.content.decode("utf-8-sig").strip().split("\r\n")
    assert linhas[0] == "email;empresa;data;nota;comentario" and len(linhas) == 2
    assert client.get(f"{API}/importacao/modelo?tipo=outro", headers=h).status_code == 422

    d = _ok(client, h, [["E-mail", "Razão Social", "Data_Resposta", "NPS", "Observação"],
                        ["a@x.com.br", "X", "01/02/2025", "9", "ok"]])
    assert d["tipo"] == "respostas"
    assert d["mapeamento_sugerido"] == {"E-mail": "email", "Razão Social": "empresa", "Data_Resposta": "data",
                                        "NPS": "nota", "Observação": "comentario"}
    assert d["campos"] == [
        {"chave": "email", "rotulo": "E-mail do contato", "obrigatorio": True},
        {"chave": "data", "rotulo": "Data da resposta", "obrigatorio": True},
        {"chave": "nota", "rotulo": "Nota (0 a 10)", "obrigatorio": True},
        {"chave": "empresa", "rotulo": "Empresa", "obrigatorio": False},
        {"chave": "comentario", "rotulo": "Comentário", "obrigatorio": False},
    ]
    for cabecalho, campo in [("email_cliente", "email"), ("dt", "data"), ("nota_nps", "nota"), ("score", "nota"),
                             ("motivo", "comentario"), ("Comentário", "comentario"), ("obs", "comentario"),
                             ("cliente", "empresa")]:
        d = _ok(client, h, [[cabecalho], ["x"]])
        assert d["mapeamento_sugerido"] == {cabecalho: campo}, cabecalho
    # sem tipo: contatos, como antes
    d = _ok(client, h, [["nome", "email"], ["A", "a@x.com.br"]], tipo=None)
    assert d["tipo"] == "contatos" and d["campos"][0]["chave"] == "nome"
    assert analisar(client, h, [["a"], ["b"]], tipo="pedidos").status_code == 422


def test_regras_por_linha_e_tudo_ou_nada(client, admin, dono):
    h = admin["h"]
    hoje = relogio.hoje()
    norte = criar_empresa(client, h, "Atacado Norte")
    paula = criar_contato(client, h, nome="Paula", email="paula@norte.com.br", empresa_id=norte["id"])
    criar_contato(client, h, nome="Marcos", email="marcos@x.com.br")
    amanha = (hoje + timedelta(days=1)).strftime("%d/%m/%Y")
    linhas = [
        ["email", "empresa", "data", "nota", "comentario"],
        ["paula@norte.com.br", "Atacado Norte", "10/01/2025", "9,0", "Entrega no prazo"],   # 2 ok
        ["PAULA@norte.com.br", "", "2025-02-10", "3", "Frete caro"],                        # 3 ok
        ["marcos@x.com.br", "Outra Empresa", "15/03/2025", "7", ""],                        # 4 ok + aviso
        ["paula@norte.com.br", "", "10/01/2025", "5", ""],                                  # 5 repetida
        ["ninguem@x.com.br", "", "10/01/2025", "5", ""],                                    # 6 sem contato
        ["paula@norte.com.br", "", "31/02/2025", "5", ""],                                  # 7 data inválida
        ["paula@norte.com.br", "", amanha, "5", ""],                                        # 8 futura
        ["paula@norte.com.br", "", "11/01/2025", "8,7", ""],                                # 9 nota decimal
        ["paula@norte.com.br", "", "12/01/2025", "", ""],                                   # 10 sem nota
        ["", "", "", "11", "x" * 4001],                                                     # 11 vários
        ["nao-e-email", "", "12/01/2025", "5", ""],                                         # 12 e-mail inválido
        ["paula@norte.com.br", "", "05/03/1925", "5", ""],                                  # 13 ano errado
    ]
    d = _ok(client, h, linhas)
    c = client.post(f"{API}/importacao/{d['id']}/conferir", headers=h, json=_corpo(d)).json()
    assert (c["prontas"], c["com_problema"], c["novos"], c["atualizados"]) == (3, 9, 3, 0)
    motivos = {p["linha"]: p["motivo"] for p in c["problemas"]}
    assert motivos[5] == "Linha repetida (mesmo contato e data)."
    assert motivos[6] == "Contato não encontrado: cadastre ou importe os contatos antes."
    assert motivos[7] == "Data inválida (use dd/mm/aaaa ou aaaa-mm-dd)."
    assert motivos[8] == "A data não pode ser no futuro."
    assert motivos[9] == "A nota precisa ser um número inteiro de 0 a 10."
    assert motivos[10] == "Nota em branco."
    assert motivos[11] == ("E-mail em branco. Data em branco. A nota precisa ser um número inteiro de 0 a 10. "
                           "O comentário passa de 4000 caracteres.")
    assert motivos[12] == "E-mail inválido."
    assert motivos[13] == "Data antes de 2000: confira o ano."
    assert c["avisos"] == ["Em 1 linha a empresa da planilha é diferente da empresa do contato; vale a empresa do "
                           "contato (linha 4)."]
    # com problema e sem ignorar: nada é gravado (e a análise continua valendo)
    r = client.post(f"{API}/importacao/{d['id']}/importar", headers=h, json=_corpo(d))
    assert r.status_code == 422 and r.json()["erro"]["codigo"] == "importacao_com_problema"
    assert lista_respostas(client, h)["total"] == 0
    r = client.post(f"{API}/importacao/{d['id']}/importar", headers=h, json=_corpo(d, ignorar_com_problema=True))
    assert r.status_code == 200, r.text
    assert r.json()["novos"] == 3 and r.json()["atualizados"] == 0 and r.json()["ignorados"] == 9
    assert len(r.json()["problemas"]) == 9

    itens = {(x["contato"]["nome"], x["nota"]): x for x in lista_respostas(client, h)["itens"]}
    assert set(itens) == {("Paula", 9), ("Paula", 3), ("Marcos", 7)}
    p9 = itens[("Paula", 9)]
    assert (p9["origem"], p9["canal"], p9["tipo_nota"], p9["grupo"], p9["temas"]) == (
        "importacao", "importacao", "nps", "promotor", ["prazo_entrega"])
    assert datetime.fromisoformat(p9["data"]) == datetime(2025, 1, 10, 12, tzinfo=FUSO)
    assert p9["respostas"] == {form_padrao(client, h)["perguntas"][0]["id"]: 9}
    assert p9["empresa"]["id"] == norte["id"] and p9["acao"] is None
    assert itens[("Marcos", 7)]["empresa"] is None  # vale a empresa do contato (nenhuma)
    assert itens[("Paula", 3)]["temas"] == ["prazo_entrega", "preco_condicoes"]  # "frete" e "caro"
    # última nota = a da resposta mais recente (10/02 → 3)
    assert client.get(f"{API}/contatos/{paula['id']}", headers=h).json()["ultima_nota"] == 3
    ev = next(i for i in client.get(f"{API}/auditoria", headers=h).json()["itens"]
              if i["evento"] == "importacao_respostas")
    assert ev["detalhe"]["novos"] == 3 and ev["detalhe"]["atualizados"] == 0
    assert ev["rotulo"] == "Planilha de respostas antigas importada"
    assert client.post(f"{API}/importacao/{d['id']}/importar", headers=h, json=_corpo(d)).status_code == 404


def test_atualizar_ou_manter_existentes(client, admin):
    h = admin["h"]
    c = criar_contato(client, h, nome="Paula", email="paula@x.com.br")
    primeira = [["email", "data", "nota", "comentario"], ["paula@x.com.br", "10/01/2025", "9", "Ótimo"],
                ["paula@x.com.br", "11/01/2025", "8", ""]]
    d = _ok(client, h, primeira)
    assert client.post(f"{API}/importacao/{d['id']}/importar", headers=h, json=_corpo(d)).json()["novos"] == 2
    # resposta registrada à mão na mesma data não conta como "já importada"
    registrar_resposta(client, h, c["id"], 6, data="2025-01-12")
    segunda = [["email", "data", "nota", "comentario"], ["paula@x.com.br", "2025-01-10", "2", "Frete atrasou"],
               ["paula@x.com.br", "12/01/2025", "4", ""], ["paula@x.com.br", "13/01/2025", "10", ""]]
    d = _ok(client, h, segunda)
    c1 = client.post(f"{API}/importacao/{d['id']}/conferir", headers=h, json=_corpo(d)).json()
    assert (c1["novos"], c1["atualizados"]) == (2, 0)
    assert c1["avisos"] == ["1 resposta já importada será mantida como está (ligue \"Atualizar as que já "
                            "existem\" para trocar a nota e o comentário)."]
    c2 = client.post(f"{API}/importacao/{d['id']}/conferir", headers=h,
                     json=_corpo(d, atualizar_existentes=True)).json()
    assert (c2["novos"], c2["atualizados"], c2["avisos"]) == (2, 1, [])
    # manter: conta em ignorados
    r = client.post(f"{API}/importacao/{d['id']}/importar", headers=h, json=_corpo(d)).json()
    assert r == {"novos": 2, "atualizados": 0, "ignorados": 1, "problemas": []}
    dia10 = next(x for x in lista_respostas(client, h)["itens"] if x["comentario"] == "Ótimo")
    assert dia10["nota"] == 9
    # atualizar: nota, comentário, grupo e temas
    d = _ok(client, h, segunda[:2])
    r = client.post(f"{API}/importacao/{d['id']}/importar", headers=h, json=_corpo(d, atualizar_existentes=True))
    assert r.json() == {"novos": 0, "atualizados": 1, "ignorados": 0, "problemas": []}
    x = client.get(f"{API}/respostas/{dia10['id']}", headers=h).json()
    assert (x["nota"], x["grupo"], x["comentario"], x["temas"]) == (2, "detrator", "Frete atrasou",
                                                                   ["prazo_entrega"])
    assert x["respostas"] == {form_padrao(client, h)["perguntas"][0]["id"]: 2}
    assert lista_respostas(client, h, origem="importacao")["total"] == 4
    assert client.get(f"{API}/contatos/{c['id']}", headers=h).json()["ultima_nota"] == 10  # 13/01


def test_importada_nao_tem_efeitos_de_resposta_nova(client, admin, destino, dono):
    h = admin["h"]
    ligar_envios(client, h)
    client.post(f"{API}/integracoes/webhooks", headers=h,
                json={"url": "https://erp.cliente.com.br/x", "eventos": ["resposta.criada"]})
    rita = criar_responsavel(client, h, "Rita", email="rita@alfa.com.br")
    e = criar_empresa(client, h, "Atacado Norte", responsavel_id=rita["id"])
    c = criar_contato(client, h, email="paula@norte.com.br", empresa_id=e["id"])
    antes = client.get(f"{API}/contatos/{c['id']}", headers=h).json()
    d = _ok(client, h, [["email", "data", "nota"], ["paula@norte.com.br", "10/01/2025", "0"]])
    assert client.post(f"{API}/importacao/{d['id']}/importar", headers=h, json=_corpo(d)).status_code == 200
    assert quadro(client, h)["totais"]["a_fazer"] == 0           # sem ação
    assert emails_para("rita@alfa.com.br") == []                 # sem alerta
    assert emails_para("paula@norte.com.br") == [] and historico(client, h) == []  # sem agradecimento
    assert destino.recebidos == []                               # sem webhook
    assert sql(dono, "select count(*) from webhook_entregas")[0][0] == 0
    depois = client.get(f"{API}/contatos/{c['id']}", headers=h).json()
    assert depois["proximo_envio"] == antes["proximo_envio"] and depois["situacao"] == antes["situacao"]
    assert depois["ultima_nota"] == 0
    assert json.dumps(lista_respostas(client, h)["itens"][0]["acao"]) == "null"


def test_mapeamento_e_permissoes(client, admin):
    h = admin["h"]
    d = _ok(client, h, [["email", "data", "nota", "obs"], ["a@x.com.br", "10/01/2025", "9", ""]])
    r = client.post(f"{API}/importacao/{d['id']}/conferir", headers=h, json={"mapeamento": {"email": "email"}})
    assert r.status_code == 422
    assert r.json()["erro"]["campos"] == {"mapeamento": "Escolha as colunas obrigatórias: Data da resposta, "
                                                        "Nota (0 a 10)."}
    r = client.post(f"{API}/importacao/{d['id']}/conferir", headers=h,
                    json={"mapeamento": {"email": "email", "data": "data", "nota": "nota", "obs": "nota"}})
    assert r.status_code == 422 and "mapeamento.obs" in r.json()["erro"]["campos"]
    r = client.post(f"{API}/importacao/{d['id']}/conferir", headers=h,
                    json={"mapeamento": {"email": "email", "data": "data", "nota": "nota", "obs": "nome"}})
    assert r.json()["erro"]["campos"] == {"mapeamento.obs": "Campo desconhecido."}
    # chave e grupo_id não se aplicam às respostas
    r = client.post(f"{API}/importacao/{d['id']}/conferir", headers=h,
                    json={**_corpo(d), "chave": "telefone", "grupo_id": 999})
    assert r.status_code == 200 and r.json()["com_problema"] == 1  # o contato não existe
    consulta = membro(client, h, "caio@alfa.com.br", "consulta")
    assert analisar(client, consulta["h"], [["email"], ["a"]]).status_code == 403
    assert client.get(f"{API}/importacao/modelo?tipo=respostas", headers=consulta["h"]).status_code == 403


def test_importacao_grande_em_lote(client, admin, dono):
    """20.000 linhas (o máximo da planilha) entram numa transação, em lote."""
    h = admin["h"]
    from util import definir_plano, encher_contatos

    definir_plano(dono, admin["conta"]["id"], "empresa")
    encher_contatos(dono, admin["conta"]["id"], 2000)
    linhas = [["email", "data", "nota", "comentario"]]
    for i in range(20000):
        n = i % 2000 + 1
        dia = (datetime(2024, 1, 1) + timedelta(days=i // 2000)).strftime("%d/%m/%Y")
        linhas.append([f"lote{n}@c{admin['conta']['id']}.com.br", dia, str(i % 11), "Entrega atrasou" if i % 2 else ""])
    inicio = perf_counter()
    d = _ok(client, h, linhas)
    analise = perf_counter() - inicio
    r = client.post(f"{API}/importacao/{d['id']}/importar", headers=h, json=_corpo(d))
    print(f"\nImportação de 20.000 respostas: análise {analise * 1000:.0f} ms, "
          f"importar {(perf_counter() - inicio - analise) * 1000:.0f} ms")
    assert r.status_code == 200, r.text
    assert r.json()["novos"] == 20000
    assert sql(dono, "select count(*) from respostas where origem = 'importacao'")[0][0] == 20000
    assert sql(dono, "select count(*) from respostas where temas = '{prazo_entrega}'")[0][0] == 10000
    assert sql(dono, "select count(*) from contatos where ultima_nota is not null")[0][0] == 2000


# ---- rodada de revisão --------------------------------------------------------

def _importar(client, h, linhas, **corpo) -> dict:
    d = _ok(client, h, linhas)
    r = client.post(f"{API}/importacao/{d['id']}/importar", headers=h, json=_corpo(d, **corpo))
    assert r.status_code == 200, r.text
    return r.json()


def test_atualizar_so_troca_o_comentario_quando_a_planilha_traz_um(client, admin):
    """Ao atualizar, comentário em branco (ou coluna não ligada) não apaga o comentário nem os temas; preenchido,
    troca o comentário e refaz os temas, salvo os temas escolhidos à mão na análise."""
    h = admin["h"]
    criar_contato(client, h, nome="Paula", email="paula@x.com.br")
    criar_contato(client, h, nome="Marcos", email="marcos@x.com.br")
    cab = ["email", "data", "nota", "comentario"]
    _importar(client, h, [cab, ["paula@x.com.br", "10/01/2025", "9", "Entrega rápida | preço bom"],
                          ["marcos@x.com.br", "10/01/2025", "8", "Frete caro"]])
    ids = {x["contato"]["nome"]: x["id"] for x in lista_respostas(client, h)["itens"]}
    r = client.patch(f"{API}/respostas/{ids['Marcos']}", headers=h, json={"temas": ["sistema_pedidos"]})
    assert r.status_code == 200 and r.json()["temas_manuais"] is True

    def ver(nome: str) -> tuple:
        x = client.get(f"{API}/respostas/{ids[nome]}", headers=h).json()
        return x["nota"], x["grupo"], x["comentario"], x["temas"]

    # comentário em branco na planilha: só a nota (e o grupo) mudam
    r = _importar(client, h, [cab, ["paula@x.com.br", "10/01/2025", "3", ""],
                              ["marcos@x.com.br", "2025-01-10", "2", "   "]], atualizar_existentes=True)
    assert (r["novos"], r["atualizados"]) == (0, 2)
    assert ver("Paula") == (3, "detrator", "Entrega rápida | preço bom", ["prazo_entrega", "preco_condicoes"])
    assert ver("Marcos") == (2, "detrator", "Frete caro", ["sistema_pedidos"])
    # coluna de comentário não ligada: idem
    d = _ok(client, h, [["email", "data", "nota", "obs"], ["paula@x.com.br", "10/01/2025", "10", "Outro texto"]])
    corpo = {"mapeamento": {"email": "email", "data": "data", "nota": "nota", "obs": None},
             "atualizar_existentes": True}
    r = client.post(f"{API}/importacao/{d['id']}/importar", headers=h, json=corpo)
    assert r.status_code == 200 and r.json()["atualizados"] == 1, r.text
    assert ver("Paula") == (10, "promotor", "Entrega rápida | preço bom", ["prazo_entrega", "preco_condicoes"])
    # comentário preenchido: troca o comentário; os temas são refeitos, menos os escolhidos à mão
    r = _importar(client, h, [cab, ["paula@x.com.br", "10/01/2025", "6", "Atendimento | ruim"],
                              ["marcos@x.com.br", "10/01/2025", "7", "Atendimento | ruim"]], atualizar_existentes=True)
    assert r["atualizados"] == 2
    assert ver("Paula") == (6, "detrator", "Atendimento | ruim", ["atendimento"])
    assert ver("Marcos") == (7, "neutro", "Atendimento | ruim", ["sistema_pedidos"])
    # o painel mostra o comentário importado como está
    p = client.get(f"{API}/painel", headers=h).json()
    assert [x["comentario"] for x in p["comentarios"]] == ["Atendimento | ruim", "Atendimento | ruim"]


def test_mesma_data_pelo_dia_de_sao_paulo(client, admin, dono):
    """A data de uma resposta já importada é o dia em São Paulo: 23:30 de 10/01 (02:30 de 11/01 em UTC) é 10/01;
    00:30 de 11/01 (03:30 em UTC) é 11/01."""
    h = admin["h"]
    criar_contato(client, h, nome="Paula", email="paula@x.com.br")
    cab = ["email", "data", "nota"]
    _importar(client, h, [cab, ["paula@x.com.br", "10/01/2025", "9"]])
    for momento, mesma_data in (("2025-01-10 23:30-03", "10/01/2025"), ("2025-01-11 00:30-03", "11/01/2025")):
        sql(dono, "update respostas set respondida_em = :m", m=momento)
        for dia in ("10/01/2025", "11/01/2025"):
            d = _ok(client, h, [cab, ["paula@x.com.br", dia, "2"]])
            c = client.post(f"{API}/importacao/{d['id']}/conferir", headers=h,
                            json=_corpo(d, atualizar_existentes=True)).json()
            esperado = (0, 1) if dia == mesma_data else (1, 0)
            assert (c["novos"], c["atualizados"]) == esperado, (momento, dia)


def test_importar_sem_formulario_padrao_de_nps(client, admin, dono):
    h = admin["h"]
    criar_contato(client, h, email="paula@x.com.br")
    nps = form_padrao(client, h)
    d = _ok(client, h, [["email", "data", "nota"], ["paula@x.com.br", "10/01/2025", "9"]])
    sql(dono, "update formularios set padrao_nps = false")
    r = client.post(f"{API}/importacao/{d['id']}/importar", headers=h, json=_corpo(d))
    assert r.status_code == 409 and r.json()["erro"]["codigo"] == "sem_formulario_nps"
    assert r.json()["erro"]["mensagem"] == ("Escolha um formulário padrão de NPS em Formulários antes de importar "
                                            "respostas.")
    assert lista_respostas(client, h)["total"] == 0
    # a análise continua valendo: com o padrão de volta, importa
    assert client.post(f"{API}/formularios/{nps['id']}/padrao", headers=h, json={"uso": "nps"}).status_code == 200
    r = client.post(f"{API}/importacao/{d['id']}/importar", headers=h, json=_corpo(d))
    assert r.status_code == 200 and r.json()["novos"] == 1


def test_duas_importacoes_ao_mesmo_tempo_nao_duplicam(client, admin, monkeypatch):
    """A mesma planilha enviada duas vezes e importada ao mesmo tempo: a trava por conta faz a segunda esperar a
    primeira terminar e encontrar as respostas já importadas (sem a trava, as duas gravariam tudo)."""
    import threading
    import time

    from fastapi.testclient import TestClient

    from toqqi.modulos.importacao import respostas as importacao_respostas

    h = admin["h"]
    criar_contato(client, h, nome="Paula", email="paula@x.com.br")
    linhas = [["email", "data", "nota"], ["paula@x.com.br", "10/01/2025", "9"], ["paula@x.com.br", "11/01/2025", "3"]]
    analises = [_ok(client, h, linhas), _ok(client, h, linhas)]
    planejar = importacao_respostas.planejar

    def devagar(*a, **k):
        plano = planejar(*a, **k)
        time.sleep(0.5)  # alarga a janela entre conferir o que já existe e gravar
        return plano

    monkeypatch.setattr(importacao_respostas, "planejar", devagar)
    resultados = []

    def importar(d):
        with TestClient(client.app) as outro:
            resultados.append(outro.post(f"{API}/importacao/{d['id']}/importar", headers=h, json=_corpo(d)))

    tarefas = [threading.Thread(target=importar, args=(d,)) for d in analises]
    for t in tarefas:
        t.start()
    for t in tarefas:
        t.join(30)
    assert [r.status_code for r in resultados] == [200, 200], [r.text for r in resultados]
    assert sorted((r.json()["novos"], r.json()["ignorados"]) for r in resultados) == [(0, 2), (2, 0)]
    assert lista_respostas(client, h)["total"] == 2



def test_reimportar_com_comentario_novo_refaz_a_analise_da_ia(client, admin):
    """A análise da IA descrevia o comentário antigo: com comentário novo na reimportação, volta para pendente (IA da
    conta ativa) ou é apagada (IA desligada)."""
    h = admin["h"]
    criar_contato(client, h, nome="Paula", email="paula@x.com.br")
    cab = ["email", "data", "nota", "comentario"]
    dia = (relogio.hoje() - timedelta(days=5)).strftime("%d/%m/%Y")
    _importar(client, h, [cab, ["paula@x.com.br", dia, "2", "O frete ficou caro demais"]])
    rid = lista_respostas(client, h)["itens"][0]["id"]
    assert client.post(f"{API}/conta/ia/analisar-recentes", headers=h).json()["marcadas"] == 1
    assert tarefas.executar("ia")["ia"]["analisadas"] == 1

    def ver() -> dict:
        return client.get(f"{API}/respostas/{rid}", headers=h).json()

    assert (ver()["ia"]["situacao"], ver()["ia"]["sentimento"]) == ("analisada", "negativo")
    # mesmo comentário: a análise fica
    _importar(client, h, [cab, ["paula@x.com.br", dia, "3", "O frete ficou caro demais"]], atualizar_existentes=True)
    assert ver()["ia"]["situacao"] == "analisada"
    # comentário novo: volta para a fila, sem a análise antiga
    _importar(client, h, [cab, ["paula@x.com.br", dia, "10", "Vendedor muito atencioso, adorei"]],
              atualizar_existentes=True)
    x = ver()
    assert (x["ia"]["situacao"], x["ia"]["sentimento"], x["ia"]["resumo"], x["ia"]["temas"]) == (
        "pendente", None, None, None)
    assert x["temas"] == ["atendimento"]
    assert tarefas.executar("ia")["ia"]["analisadas"] == 1
    assert (ver()["ia"]["sentimento"], ver()["ia"]["resumo"]) == ("positivo", "Vendedor muito atencioso, adorei")
    # IA desligada na conta: o comentário novo apaga a análise
    assert client.put(f"{API}/conta/ia", headers=h, json={"analise_respostas": False}).status_code == 200
    _importar(client, h, [cab, ["paula@x.com.br", dia, "4", "Atrasou"]], atualizar_existentes=True)
    assert ver()["ia"] is None

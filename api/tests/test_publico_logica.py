"""Etapa 5l (docs/api-etapa-5l.md §4.3 e §4.4): a página pública com a lógica — o envio só vale no caminho (pular e
escondidos), obrigatória só no caminho, valor inválido fora do caminho ignorado, o final escolhido (`final_id`,
`html_final`, `botao_final`) ou o padrão, `formulario_versao`, `max_selecoes`, o formulário público com o HTML
renderizado e escapado, conteúdo que nunca vira resposta — e as telas internas (resultados, CSV, detalhe e exportação)
sem os blocos de conteúdo e com "…" no lugar das citações."""
import csv
import io
import zipfile

import pytest
from util import API, conta_pronta, criar_contato, link_pesquisa, responder_link, sql

from toqqi.modulos.imagens import servico as imagens

NPS = {"id": "p_nota", "tipo": "nps", "titulo": "De 0 a 10, quanto recomendaria a {empresa}?", "obrigatoria": True}


def _se(fonte, op, valor=None) -> dict:
    return {"juncao": "todas", "condicoes": [{"fonte": fonte, "op": op, **({} if valor is None else {"valor": valor})}]}


@pytest.fixture
def admin(client):
    return conta_pronta(client, "ana@alfa.com.br", empresa="Alfa & Cia")


def _form(client, h, perguntas, finais=None, **extra) -> dict:
    r = client.post(f"{API}/formularios", headers=h,
                    json={"nome": "Lógica", "perguntas": perguntas, "finais": finais or [], **extra})
    assert r.status_code == 201, r.text
    return r.json()


def _respostas(client, h, f) -> list[dict]:
    return client.get(f"{API}/formularios/{f['id']}/respostas", headers=h).json()["itens"]


def _pular_cliente() -> list[dict]:
    """É cliente? Não → fim. Detratores veem "O que faltou?" (obrigatória); promotores, o elogio."""
    return [
        {"id": "p_cliente", "tipo": "sim_nao", "titulo": "É cliente?", "obrigatoria": True,
         "logica": {"pular": [{"se": _se("p_cliente", "igual", False), "para": "fim"}]}},
        NPS,
        {"id": "p_faltou", "tipo": "comentario", "titulo": "O que faltou?", "obrigatoria": True,
         "logica": {"mostrar_se": _se("p_nota", "grupo_e", ["detrator"])}},
        {"id": "p_elogio", "tipo": "comentario", "titulo": "Do que gostou?",
         "logica": {"mostrar_se": _se("p_nota", "grupo_e", ["promotor"])}},
        {"id": "p_dia", "tipo": "data", "titulo": "Quando foi a entrega?"},
    ]


def test_envio_com_pular_e_escondidos(client, admin):
    h = admin["h"]
    # a nota principal não pode ficar de fora: perguntas antes dela não pulam
    r = client.post(f"{API}/formularios", headers=h, json={"nome": "X", "perguntas": _pular_cliente()})
    assert r.status_code == 422
    perguntas = [NPS, *_pular_cliente()[0:1], *_pular_cliente()[2:]]  # nota, É cliente?, faltou, elogio, dia
    f = _form(client, h, perguntas)
    codigo = f["codigo_publico"]
    # não é cliente: vai para o fim; o resto (até obrigatória e valor inválido) fica de fora e é descartado
    r = responder_link(client, codigo, {"p_nota": 3, "p_cliente": False, "p_faltou": "fora", "p_dia": "31/12/2025",
                                        "p_x": "id desconhecido"})
    assert r.status_code == 201, r.text
    assert _respostas(client, h, f)[0]["respostas"] == {"p_nota": 3, "p_cliente": False}
    # é cliente e detrator: "O que faltou?" é cobrada; o elogio (escondido) é descartado sem erro
    r = responder_link(client, codigo, {"p_nota": 3, "p_cliente": True, "p_elogio": "x" * 5000})
    assert r.status_code == 422 and r.json()["erro"]["campos"] == {"p_faltou": "Responda esta pergunta."}
    r = responder_link(client, codigo, {"p_nota": 3, "p_cliente": True, "p_faltou": "Prazo", "p_elogio": "fora",
                                        "p_dia": "2026-01-02"})
    assert r.status_code == 201
    assert _respostas(client, h, f)[0]["respostas"] == {"p_nota": 3, "p_cliente": True, "p_faltou": "Prazo",
                                                        "p_dia": "2026-01-02"}
    # valor inválido no caminho continua dando erro
    r = responder_link(client, codigo, {"p_nota": 10, "p_cliente": True, "p_dia": "ontem"})
    assert r.status_code == 422 and set(r.json()["erro"]["campos"]) == {"p_dia"}
    # obrigatória pulada não é cobrada (É cliente? é obrigatória e está no caminho)
    r = responder_link(client, codigo, {"p_nota": 9})
    assert r.status_code == 422 and r.json()["erro"]["campos"] == {"p_cliente": "Responda esta pergunta."}


def test_final_escolhido_e_final_padrao(client, admin):
    h = admin["h"]
    finais = [
        {"nome": "Promotores", "titulo": "Valeu, {empresa}!",
         "html": '<p>Avalie a {empresa} &amp; conte para {{p_nota}} amigos.</p><img src="https://evil.com/x.png">',
         "botao": {"texto": "Avaliar no Google", "url": "https://g.page/r/abc/review"},
         "mostrar_se": _se("p_nota", "grupo_e", ["promotor"])},
        {"nome": "Detratores", "titulo": "Obrigado pela sinceridade",
         "mostrar_se": _se("p_nota", "grupo_e", ["detrator"])},
    ]
    f = _form(client, h, [NPS, {"id": "p_c", "tipo": "comentario", "titulo": "Por quê?"}], finais,
              tema={"titulo_final": "Muito obrigado!", "texto_final": "Até logo, {empresa}."})
    promo, detr = f["finais"]
    r = responder_link(client, f["codigo_publico"], {"p_nota": 10})
    assert r.status_code == 201
    assert r.json() == {"titulo_final": "Valeu, Alfa & Cia!", "texto_final": "", "final_id": promo["id"],
                        "html_final": "<p>Avalie a Alfa &amp; Cia &amp; conte para {{p_nota}} amigos.</p>",
                        "botao_final": {"texto": "Avaliar no Google", "url": "https://g.page/r/abc/review"},
                        "edicao": None}
    r = responder_link(client, f["codigo_publico"], {"p_nota": 2})
    assert r.json() == {"titulo_final": "Obrigado pela sinceridade", "texto_final": "", "final_id": detr["id"],
                        "html_final": "", "botao_final": None, "edicao": None}
    # neutro: nenhum final da lista vale → o padrão do tema
    r = responder_link(client, f["codigo_publico"], {"p_nota": 7})
    assert r.json() == {"titulo_final": "Muito obrigado!", "texto_final": "Até logo, Alfa & Cia.", "final_id": None,
                        "html_final": None, "botao_final": None, "edicao": None}
    # a mesma resposta repetida (mesmo IP) responde igual, com o mesmo final
    r1 = responder_link(client, f["codigo_publico"], {"p_nota": 9}, ip="203.0.113.9")
    r2 = responder_link(client, f["codigo_publico"], {"p_nota": 9}, ip="203.0.113.9")
    assert r1.json() == r2.json() and r1.json()["final_id"] == promo["id"]


def test_formulario_sem_finais_como_antes(client, admin):
    f = _form(client, admin["h"], [NPS])
    r = responder_link(client, f["codigo_publico"], {"p_nota": 10})
    assert r.json() == {"titulo_final": "Obrigado!", "final_id": None, "html_final": None, "botao_final": None,
                        "texto_final": "Sua resposta foi registrada. Ela ajuda a Alfa & Cia a melhorar a cada dia.",
                        "edicao": None}


def test_convite_com_final_versao_e_indicacao(client, admin, dono):
    h = admin["h"]
    finais = [{"nome": "Promotores", "titulo": "Oba, {nome}!", "mostrar_se": _se("p_nota", "grupo_e", ["promotor"])}]
    f = _form(client, h, [NPS], finais)
    client.patch(f"{API}/formularios/{f['id']}", headers=h, json={"descricao": "não publica"})
    f = client.patch(f"{API}/formularios/{f['id']}", headers=h,
                     json={"perguntas": [NPS], "finais": finais}).json()  # versão 2 (final sem id ganha outro)
    assert f["versao"] == 2
    c = criar_contato(client, h, nome="Paula Lima")
    token = link_pesquisa(client, h, c["id"], formulario_id=f["id"])
    r = client.post(f"{API}/publico/convites/{token}/responder", json={"respostas": {"p_nota": 10}})
    assert r.status_code == 201, r.text
    d = r.json()
    assert (d["titulo_final"], d["texto_final"], d["final_id"]) == ("Oba, Paula!", "", f["finais"][0]["id"])
    assert "indicacao" in d and "depoimento" in d
    assert sql(dono, "select formulario_versao from respostas") == [(2,)]
    # pelo link público também
    responder_link(client, f["codigo_publico"], {"p_nota": 3})
    assert sorted(x[0] for x in sql(dono, "select formulario_versao from respostas")) == [2, 2]


def test_max_selecoes(client, admin):
    multipla = {"id": "p_m", "tipo": "escolha_multipla", "titulo": "Motivos", "opcoes": ["A", "B", "C"],
                "max_selecoes": 2}
    f = _form(client, admin["h"], [NPS, multipla])
    r = responder_link(client, f["codigo_publico"], {"p_nota": 8, "p_m": ["A", "B", "C"]})
    assert r.status_code == 422 and r.json()["erro"]["campos"] == {"p_m": "Escolha no máximo 2 opções."}
    assert responder_link(client, f["codigo_publico"], {"p_nota": 8, "p_m": ["C", "A", "A"]}).status_code == 201
    assert _respostas(client, admin["h"], f)[0]["respostas"]["p_m"] == ["A", "C"]


def test_formulario_publico_com_logica_e_html(client, admin):
    h = admin["h"]
    img = client.post(f"{API}/formularios", headers=h, json={"nome": "tmp"}).json()
    url = client.post(f"{API}/formularios/{img['id']}/imagens", headers=h,
                      files={"arquivo": ("i.png", b"\x89PNG\r\n\x1a\n" + b"\0" * 32, "image/png")}).json()["url"]
    conteudo = {"id": "c_1", "tipo": "conteudo", "titulo": "Nome interno",
                "html": f'<h2>Olá, {{nome}}!</h2><p>A {{empresa}} quer saber. {{{{p_nota}}}}</p><img src="{url}">',
                "logica": {"mostrar_se": _se("p_nota", "grupo_e", ["promotor"])}}
    pergunta = {"id": "p_c", "tipo": "comentario", "titulo": "Por que {{p_nota}}, {nome}?",
                "descricao": "Pedido {referencia}", "placeholder": "Escreva aqui",
                "logica": {"pular": [{"se": _se("p_c", "respondida"), "para": "fim"}]}}
    finais = [{"nome": "F", "titulo": "Fim", "html": "<p>segredo do final</p>"}]
    f = _form(client, h, [NPS, conteudo, pergunta], finais)
    d = client.get(f"{API}/publico/formularios/{f['codigo_publico']}?referencia=<b>NF \"9\"</b>").json()
    form = d["formulario"]
    assert form["prefixo_imagens"] == d["prefixo_imagens"] == imagens.prefixo_publico()
    assert form["tem_finais"] is True and d["tem_finais"] is True
    assert "finais" not in form and "segredo do final" not in str(d)
    p0, c1, p2 = form["perguntas"]
    assert p0["titulo"] == "De 0 a 10, quanto recomendaria a Alfa & Cia?"
    assert c1["titulo"] == "" and c1["logica"]["mostrar_se"]["condicoes"][0]["op"] == "grupo_e"
    assert c1["html"] == f'<h2>Olá!</h2><p>A Alfa &amp; Cia quer saber. {{{{p_nota}}}}</p><img src="{url}">'
    assert p2["titulo"] == "Por que {{p_nota}}?" and p2["placeholder"] == "Escreva aqui"
    assert p2["descricao"] == 'Pedido <b>NF "9"</b>'  # texto puro: quem escapa é o site (interpolação)
    assert p2["logica"]["pular"][0]["para"] == "fim"
    # com a referência no HTML, o valor entra escapado
    conteudo["html"] = "<p>Pedido {referencia}</p>"
    client.patch(f"{API}/formularios/{f['id']}", headers=h, json={"perguntas": [NPS, conteudo, pergunta]})
    d = client.get(f"{API}/publico/formularios/{f['codigo_publico']}?referencia=<b>NF \"9\"</b>").json()
    assert d["formulario"]["perguntas"][1]["html"] == "<p>Pedido &lt;b&gt;NF &quot;9&quot;&lt;/b&gt;</p>"
    # convite também leva o prefixo e o tem_finais; sem finais, tem_finais é falso
    c = criar_contato(client, h, nome="Rosa Maria")
    token = link_pesquisa(client, h, c["id"], formulario_id=f["id"])
    conv = client.get(f"{API}/publico/convites/{token}").json()
    assert conv["formulario"]["perguntas"][1]["html"] == "<p>Pedido</p>" and conv["tem_finais"] is True
    assert conv["ja_respondido"] is False and conv["prefixo_imagens"] == imagens.prefixo_publico()
    sem = _form(client, h, [NPS])
    assert client.get(f"{API}/publico/formularios/{sem['codigo_publico']}").json()["formulario"]["tem_finais"] is False


def test_conteudo_nunca_vira_resposta(client, admin):
    conteudo = {"id": "c_1", "tipo": "conteudo", "html": "<p>Leia</p>"}
    f = _form(client, admin["h"], [conteudo, NPS])
    r = responder_link(client, f["codigo_publico"], {"c_1": "resposta", "p_nota": 9})
    assert r.status_code == 201
    assert _respostas(client, admin["h"], f)[0]["respostas"] == {"p_nota": 9}
    r = responder_link(client, f["codigo_publico"], {"c_1": "só o conteúdo"})
    assert r.status_code == 422 and r.json()["erro"]["campos"] == {"p_nota": "Responda esta pergunta."}


def test_telas_internas_pulam_conteudo_e_trocam_citacoes(client, admin):
    h = admin["h"]
    perguntas = [NPS, {"id": "c_1", "tipo": "conteudo", "html": "<p>Bloco</p>"},
                 {"id": "p_c", "tipo": "comentario", "titulo": "Por que {{p_nota}}?"},
                 {"tipo": "quebra_pagina"}, {"id": "p_s", "tipo": "sim_nao", "titulo": "Voltaria a {{x}}?"}]
    f = _form(client, h, perguntas)
    assert f["perguntas_total"] == 3
    assert responder_link(client, f["codigo_publico"], {"p_nota": 9, "p_c": "Bom", "p_s": True}).status_code == 201
    res = client.get(f"{API}/formularios/{f['id']}/resultados", headers=h).json()
    assert [(p["id"], p["titulo"]) for p in res["perguntas"]] == [
        ("p_nota", "De 0 a 10, quanto recomendaria a {empresa}?"), ("p_c", "Por que …?"), ("p_s", "Voltaria a …?")]
    linhas = list(csv.reader(io.StringIO(client.get(f"{API}/formularios/{f['id']}/respostas.csv", headers=h)
                                         .content.decode("utf-8-sig")), delimiter=";"))
    assert linhas[0][-3:] == ["De 0 a 10, quanto recomendaria a Alfa & Cia?", "Por que …?", "Voltaria a …?"]
    item = _respostas(client, h, f)[0]
    assert item["comentario"] == "Por que …? Bom | Voltaria a …? Sim"  # resumo
    detalhe = client.get(f"{API}/respostas/{item['id']}", headers=h).json()
    assert [(p["id"], p["titulo"], p["resposta"]) for p in detalhe["perguntas"]] == [
        ("p_nota", "De 0 a 10, quanto recomendaria a Alfa & Cia?", "9"), ("p_c", "Por que …?", "Bom"),
        ("p_s", "Voltaria a …?", "Sim")]
    zf = zipfile.ZipFile(io.BytesIO(client.get(f"{API}/conta/exportacao.zip", headers=h).content))
    planilha = list(csv.reader(io.StringIO(zf.read("respostas-perguntas.csv").decode("utf-8-sig")), delimiter=";"))
    deste = [linha[2:4] for linha in planilha[1:] if linha[1] == "Lógica"]
    assert deste == [["p_nota", "De 0 a 10, quanto recomendaria a Alfa & Cia?"], ["p_c", "Por que …?"],
                     ["p_s", "Voltaria a …?"]]
    formularios_csv = list(csv.reader(io.StringIO(zf.read("formularios.csv").decode("utf-8-sig")), delimiter=";"))
    assert formularios_csv[0][-1] == "Finais (JSON)"

"""Etapa 5l (docs/api-etapa-5l.md §1, §2.6, §4.2 e §4.6): formato novo do formulário — validação de cada regra (chaves e
mensagens), limites, formato antigo na entrada, ids gerados, campos novos, finais —, rascunho (rev, problemas, igual ao
publicado), publicar, descartar, PATCH que publica direto, duplicar, permissões e imagens dos blocos de conteúdo."""
import pytest
from util import API, caminho_imagem, conta_pronta, form_padrao, membro, png, sql

from toqqi.modulos.imagens import servico as imagens

NPS = {"id": "p_nota", "tipo": "nps", "titulo": "Quanto recomendaria?", "obrigatoria": True}
CSAT = {"id": "p_csat", "tipo": "csat", "titulo": "Como foi?", "obrigatoria": True}
COMENTARIO = {"id": "p_coment", "tipo": "comentario", "titulo": "Por quê?"}
CONTEUDO = {"id": "c_aviso", "tipo": "conteudo", "html": "<p>Aviso</p>"}
MSG_GRANDE = "Este conteúdo está grande demais (máx. 20.000 caracteres)."


@pytest.fixture
def admin(client):
    return conta_pronta(client, "ana@alfa.com.br", empresa="Alfa Distribuidora")


def _se(fonte, op, valor=None, juncao="todas", **extra) -> dict:
    cond = {"fonte": fonte, "op": op, **({} if valor is None else {"valor": valor}), **extra}
    return {"juncao": juncao, "condicoes": [cond]}


def _com(item: dict, **logica) -> dict:
    return {**item, "logica": logica}


def _criar(client, h, perguntas, finais=None, **extra):
    corpo = {"nome": "Pesquisa v2", "perguntas": perguntas, **extra}
    if finais is not None:
        corpo["finais"] = finais
    return client.post(f"{API}/formularios", headers=h, json=corpo)


def _erro(client, h, perguntas, finais=None) -> dict:
    r = _criar(client, h, perguntas, finais)
    assert r.status_code == 422, r.text
    assert r.json()["erro"]["codigo"] == "dados_invalidos"
    return r.json()["erro"]["campos"]


def _ok(client, h, perguntas, finais=None, **extra) -> dict:
    r = _criar(client, h, perguntas, finais, **extra)
    assert r.status_code == 201, r.text
    return r.json()


def _put(client, h, f: dict, rev: int, **doc):
    return client.put(f"{API}/formularios/{f['id']}/rascunho", headers=h, json={"rev": rev, **doc})


def _obter(client, h, f: dict) -> dict:
    r = client.get(f"{API}/formularios/{f['id']}", headers=h)
    assert r.status_code == 200, r.text
    return r.json()


def _eventos(client, h, evento: str) -> list[dict]:
    return [i for i in client.get(f"{API}/auditoria", headers=h).json()["itens"] if i["evento"] == evento]


# ---- §2.6 regras de validação ----------------------------------------------------------------------

def test_fonte_das_condicoes(client, admin):
    h = admin["h"]
    depois = _com(COMENTARIO, mostrar_se=_se("p_nota", "respondida"))
    assert _erro(client, h, [depois, NPS]) == {
        "perguntas.0.logica": "A condição 1 usa uma pergunta que vem depois desta."}
    sumiu = _com(COMENTARIO, mostrar_se=_se("p_nao_existe", "respondida"))
    assert _erro(client, h, [NPS, sumiu]) == {
        "perguntas.1.logica": "A condição 1 usa uma pergunta que não existe mais."}
    bloco = _com(COMENTARIO, mostrar_se=_se("c_aviso", "respondida"))
    assert _erro(client, h, [NPS, CONTEUDO, bloco]) == {
        "perguntas.2.logica": "A condição 1 usa um bloco de conteúdo (só perguntas servem de condição)."}
    propria = _com(COMENTARIO, mostrar_se=_se("p_coment", "respondida"))
    assert "esta mesma pergunta" in _erro(client, h, [NPS, propria])["perguntas.1.logica"]
    # pular: a fonte pode ser a própria pergunta (ou uma anterior), nunca uma posterior
    regra = {"se": _se("p_coment", "nao_respondida"), "para": "fim"}
    f = _ok(client, h, [NPS, _com(COMENTARIO, pular=[regra]), {"tipo": "sim_nao", "titulo": "Volta?"}])
    assert f["perguntas"][1]["logica"]["pular"][0]["para"] == "fim"
    regra_depois = {"se": _se("p_sim", "respondida"), "para": "fim"}
    assert _erro(client, h, [NPS, _com(COMENTARIO, pular=[regra_depois]),
                             {"id": "p_sim", "tipo": "sim_nao", "titulo": "Volta?"}]) == {
        "perguntas.1.logica": "Na regra 1, a condição 1 usa uma pergunta que vem depois desta."}
    # finais: qualquer pergunta serve
    final = {"nome": "Fim", "titulo": "Obrigado", "mostrar_se": _se("p_coment", "respondida")}
    assert _ok(client, h, [NPS, COMENTARIO], [final])["finais"][0]["mostrar_se"]["condicoes"][0]["fonte"] == "p_coment"


@pytest.mark.parametrize("fonte,cond,mensagem", [
    (NPS, {"op": "contem", "valor": "x"}, "A condição 1 usa uma comparação que não vale para este tipo de pergunta."),
    (NPS, {"op": "menor", "valor": 11}, "A condição 1 precisa de um número inteiro de 0 a 10."),
    (NPS, {"op": "igual", "valor": 7.5}, "A condição 1 precisa de um número inteiro de 0 a 10."),
    (NPS, {"op": "entre", "valor": [8, 3]},
     "A condição 1 precisa de dois números de 0 a 10, o primeiro menor ou igual ao segundo."),
    (NPS, {"op": "grupo_e", "valor": ["satisfeito"]}, "A condição 1 precisa de grupos válidos: detrator, neutro, "
                                                       "promotor."),
    (NPS, {"op": "grupo_e", "valor": []}, "A condição 1 precisa de grupos válidos: detrator, neutro, promotor."),
    ({"id": "p_esc", "tipo": "escala", "titulo": "E", "min": 1, "max": 7}, {"op": "grupo_e", "valor": ["neutro"]},
     "A condição 1 usa uma comparação que não vale para este tipo de pergunta."),
    ({"id": "p_esc", "tipo": "escala", "titulo": "E", "min": 1, "max": 7}, {"op": "igual", "valor": 0},
     "A condição 1 precisa de um número inteiro de 1 a 7."),
    ({"id": "p_uma", "tipo": "escolha_unica", "titulo": "U", "opcoes": ["Preço", "Prazo"]},
     {"op": "um_de", "valor": ["Preço", "Mix"]}, "A condição 1 usa a opção 'Mix', que não existe mais."),
    ({"id": "p_uma", "tipo": "escolha_unica", "titulo": "U", "opcoes": ["Preço", "Prazo"]},
     {"op": "inclui_algum", "valor": ["Preço"]}, "A condição 1 usa uma comparação que não vale para este tipo de "
                                                  "pergunta."),
    ({"id": "p_mult", "tipo": "escolha_multipla", "titulo": "M", "opcoes": ["A", "B"]},
     {"op": "inclui_todos", "valor": []}, "A condição 1 precisa de pelo menos uma opção."),
    ({"id": "p_sn", "tipo": "sim_nao", "titulo": "S"}, {"op": "igual", "valor": "sim"},
     "A condição 1 precisa de Sim ou Não."),
    ({"id": "p_sn", "tipo": "sim_nao", "titulo": "S"}, {"op": "diferente", "valor": True},
     "A condição 1 usa uma comparação que não vale para este tipo de pergunta."),
    ({"id": "p_txt", "tipo": "comentario", "titulo": "T"}, {"op": "contem", "valor": "  "},
     "A condição 1 precisa de um texto de 1 a 200 caracteres."),
    ({"id": "p_txt", "tipo": "texto_curto", "titulo": "T", "formato": "numero"}, {"op": "contem", "valor": "1"},
     "A condição 1 usa uma comparação que não vale para este tipo de pergunta."),
    ({"id": "p_txt", "tipo": "texto_curto", "titulo": "T", "formato": "numero"}, {"op": "maior", "valor": "dez"},
     "A condição 1 precisa de um número."),
    ({"id": "p_dt", "tipo": "data", "titulo": "D"}, {"op": "menor", "valor": "2026-02-30"},
     "A condição 1 precisa de uma data válida (AAAA-MM-DD)."),
    ({"id": "p_dt", "tipo": "data", "titulo": "D"}, {"op": "entre", "valor": ["2026-03-01", "2026-01-01"]},
     "A condição 1 precisa de duas datas válidas, a primeira antes da segunda (ou igual)."),
    (NPS, {"op": None}, "Escolha a comparação da condição 1."),
])
def test_operador_e_valor(client, admin, fonte, cond, mensagem):
    item = _com(COMENTARIO, mostrar_se={"juncao": "todas", "condicoes": [{"fonte": fonte["id"], **cond}]})
    perguntas = [fonte, item] if fonte is NPS else [NPS, fonte, item]
    campos = _erro(client, admin["h"], perguntas)
    assert campos == {f"perguntas.{len(perguntas) - 1}.logica": mensagem}


def test_valores_validos_normalizados(client, admin):
    multipla = {"id": "p_mult", "tipo": "escolha_multipla", "titulo": "M", "opcoes": ["A", "B", "C"]}
    texto = {"id": "p_txt", "tipo": "texto_curto", "titulo": "T", "formato": "numero"}
    data = {"id": "p_dt", "tipo": "data", "titulo": "D"}
    itens = [NPS, multipla, texto, data,
             _com(COMENTARIO, mostrar_se={"juncao": "qualquer", "condicoes": [
                 {"fonte": "p_nota", "op": "grupo_e", "valor": ["promotor", "detrator", "promotor"]},
                 {"fonte": "p_nota", "op": "entre", "valor": [0.0, 6]},
                 {"fonte": "p_mult", "op": "inclui_algum", "valor": [" B ", "A", "B"]},
                 {"fonte": "p_txt", "op": "entre", "valor": [1.5, 2]},
                 {"fonte": "p_dt", "op": "maior_igual", "valor": "2026-01-31"},
                 {"fonte": "p_nota", "op": "respondida", "valor": 99},
             ]})]
    f = _ok(client, admin["h"], itens)
    conds = f["perguntas"][4]["logica"]["mostrar_se"]["condicoes"]
    assert f["perguntas"][4]["logica"]["mostrar_se"]["juncao"] == "qualquer"
    assert [c.get("valor") for c in conds] == [["detrator", "promotor"], [0, 6], ["B", "A"], [1.5, 2], "2026-01-31",
                                              None]
    assert "valor" not in conds[5]  # respondida não leva valor (o que veio é ignorado e removido)


def test_regras_de_pular(client, admin):
    h = admin["h"]
    q = {"id": "q1", "tipo": "quebra_pagina", "titulo": ""}
    sim = {"id": "p_sim", "tipo": "sim_nao", "titulo": "É cliente?"}

    def com_regra(para):
        return _com(sim, pular=[{"se": _se("p_sim", "igual", False), "para": para}])

    assert _erro(client, h, [NPS, COMENTARIO, com_regra("p_coment")]) == {
        "perguntas.2.logica": "A regra 1 manda para uma pergunta que vem antes desta (só dá para pular para frente)."}
    assert _erro(client, h, [NPS, com_regra("q1"), q, COMENTARIO]) == {
        "perguntas.1.logica": "A regra 1 manda para uma quebra de página; escolha uma pergunta ou o fim."}
    assert _erro(client, h, [NPS, com_regra("p_sumiu"), COMENTARIO]) == {
        "perguntas.1.logica": "A regra 1 manda para um item que não existe mais."}
    assert _erro(client, h, [NPS, com_regra(None), COMENTARIO]) == {
        "perguntas.1.logica": "Escolha para onde a regra 1 manda."}
    assert _erro(client, h, [NPS, _com(sim, pular=[{"se": None, "para": "fim"}])]) == {
        "perguntas.1.logica": "Adicione pelo menos uma condição à regra 1."}
    # conteúdo não pula
    assert _erro(client, h, [NPS, _com(CONTEUDO, pular=[{"se": _se("p_nota", "respondida"), "para": "fim"}])]) == {
        "perguntas.1.logica": "Blocos de conteúdo não podem pular; a regra fica na pergunta."}
    # ids das regras: r_ + 6 quando faltam; repetidos ganham outro
    regras = [{"id": "r_igual", "se": _se("p_sim", "igual", False), "para": "p_coment"},
              {"id": "r_igual", "se": _se("p_sim", "igual", True), "para": "fim"},
              {"se": _se("p_sim", "nao_respondida"), "para": "fim"}]
    f = _ok(client, h, [NPS, _com(sim, pular=regras), q, COMENTARIO])
    ids = [r["id"] for r in f["perguntas"][1]["logica"]["pular"]]
    assert ids[0] == "r_igual" and len(set(ids)) == 3 and all(i.startswith("r_") and len(i) == 8 for i in ids[1:])
    # pular para um bloco de conteúdo posterior vale
    assert _ok(client, h, [NPS, com_regra("c_aviso"), COMENTARIO, CONTEUDO])["perguntas"][1]["logica"]["pular"]


def test_nota_principal(client, admin):
    h = admin["h"]
    assert _erro(client, h, [COMENTARIO, _com(NPS, mostrar_se=_se("p_coment", "respondida"))]) == {
        "perguntas.1.logica": "A nota principal sempre aparece; tire a condição dela."}
    antes = _com(COMENTARIO, pular=[{"se": _se("p_coment", "respondida"), "para": "fim"}])
    assert _erro(client, h, [antes, NPS]) == {"perguntas.0.logica": "Perguntas antes da nota principal não podem "
                                                                     "pular (a nota principal não pode ficar de fora)."}
    # condição (mostrar_se) antes da nota principal pode; a principal é a 1ª nps, senão a 1ª csat/estrelas
    sim = {"id": "p_sim", "tipo": "sim_nao", "titulo": "É cliente?"}
    f = _ok(client, h, [sim, _com(COMENTARIO, mostrar_se=_se("p_sim", "igual", True)), CSAT,
                        _com({"id": "p_x", "tipo": "comentario", "titulo": "X"},
                             pular=[{"se": _se("p_csat", "menor", 3), "para": "fim"}])])
    assert f["tipo_principal"] == "csat"


def test_conteudo(client, admin):
    h = admin["h"]
    assert _erro(client, h, [NPS, {**CONTEUDO, "html": "<p> </p><script>x</script>"}]) == {
        "perguntas.1.html": "Escreva o conteúdo do bloco."}
    assert _erro(client, h, [NPS, {**CONTEUDO, "html": "<p>x</p>" * 2501}]) == {"perguntas.1.html": MSG_GRANDE}
    assert _erro(client, h, [NPS, {**CONTEUDO, "html": "<!-- -->" * 6251}]) == {"perguntas.1.html": MSG_GRANDE}
    assert _erro(client, h, [NPS, {**CONTEUDO, "titulo": "n" * 121}]) == {
        "perguntas.1.titulo": "Use no máximo 120 caracteres."}
    f = _ok(client, h, [NPS, {**CONTEUDO, "titulo": " Aviso LGPD ", "html": '<p onclick="x">Oi</p>', "modo": "html",
                              "obrigatoria": True, "descricao": "cai", "opcoes": ["cai"]}])
    assert f["perguntas"][1] == {"id": "c_aviso", "tipo": "conteudo", "titulo": "Aviso LGPD", "html": "<p>Oi</p>",
                                 "modo": "html", "obrigatoria": False}
    assert _ok(client, h, [NPS, {**CONTEUDO, "modo": "outro"}])["perguntas"][1]["modo"] == "visual"
    assert f["perguntas_total"] == 1  # só perguntas


def test_finais(client, admin):
    h = admin["h"]
    finais = [{"nome": "", "titulo": "", "html": "<p>x</p>", "botao": {"texto": "", "url": "http://site.com"}},
              {"nome": "n" * 61, "titulo": "Ok"}]
    assert _erro(client, h, [NPS], finais) == {
        "finais.0.nome": "Dê um nome ao final (só a sua equipe vê).", "finais.0.titulo": "Escreva o título do final.",
        "finais.0.botao.texto": "Escreva o texto do botão.",
        "finais.0.botao.url": "Use um endereço https:// (até 500 caracteres).",
        "finais.1.nome": "Use no máximo 60 caracteres."}
    assert _erro(client, h, [NPS], [{"nome": "A", "titulo": "B", "mostrar_se": _se("p_sumiu", "respondida")}]) == {
        "finais.0.mostrar_se": "A condição 1 usa uma pergunta que não existe mais."}
    assert _erro(client, h, [NPS], [{"nome": "A", "titulo": "B", "botao": {"texto": "Ir", "url": "https:// x"}}]) == {
        "finais.0.botao.url": "Use um endereço https:// (até 500 caracteres)."}
    f = _ok(client, h, [NPS], [
        {"id": "f_promo", "nome": " Promotores ", "titulo": "Valeu, {empresa}!",
         "html": '<p>Oi</p><img src="https://evil.com/x.png">', "botao": {"texto": "Avaliar", "url": "https://g.co/x"},
         "mostrar_se": _se("p_nota", "grupo_e", ["promotor"])},
        {"id": "f_promo", "nome": "Resto", "titulo": "Obrigado", "html": "<p></p>", "botao": {"texto": "", "url": ""}},
    ])
    a, b = f["finais"]
    assert a == {"id": "f_promo", "nome": "Promotores", "titulo": "Valeu, {empresa}!", "html": "<p>Oi</p>",
                 "botao": {"texto": "Avaliar", "url": "https://g.co/x"},
                 "mostrar_se": {"juncao": "todas", "condicoes": [{"fonte": "p_nota", "op": "grupo_e",
                                                                  "valor": ["promotor"]}]}}
    assert b["id"].startswith("f_") and b["id"] != "f_promo" and len(b["id"]) == 8
    assert (b["html"], b["botao"], b["mostrar_se"]) == ("", None, None)


def test_limites(client, admin):
    h = admin["h"]
    assert _erro(client, h, [{"tipo": "sim_nao", "titulo": f"P{i}"} for i in range(61)]) == {
        "perguntas": "Use no máximo 60 perguntas."}
    assert _erro(client, h, [NPS] + [{"tipo": "conteudo", "html": "<p>x</p>"} for _ in range(31)]) == {
        "perguntas": "Use no máximo 30 blocos de conteúdo."}
    assert "perguntas" in _erro(client, h, [{"tipo": "quebra_pagina"} for _ in range(121)])
    muitas = {"juncao": "todas", "condicoes": [{"fonte": "p_nota", "op": "respondida"}] * 11}
    assert _erro(client, h, [NPS, _com(COMENTARIO, mostrar_se=muitas)]) == {
        "perguntas.1.logica": "Use no máximo 10 condições em cada grupo."}
    regras = [{"se": _se("p_nota", "respondida"), "para": "fim"}] * 11
    assert _erro(client, h, [NPS, _com(COMENTARIO, pular=regras)]) == {
        "perguntas.1.logica": "Use no máximo 10 regras em cada pergunta."}
    assert _erro(client, h, [NPS], [{"nome": f"F{i}", "titulo": "T"} for i in range(11)]) == {
        "finais": "Use no máximo 10 finais."}


def test_formato_antigo_na_entrada(client, admin):
    h = admin["h"]
    antigo = {"tipo": "grupo", "grupos": ["neutro", "detrator"]}
    f = _ok(client, h, [NPS, {**COMENTARIO, "condicao": antigo}])
    assert f["perguntas"][1]["logica"]["mostrar_se"] == _se("p_nota", "grupo_e", ["detrator", "neutro"])
    assert "condicao" not in f["perguntas"][1]
    # com logica.mostrar_se, a condição antiga é ignorada
    novo = _se("p_nota", "maior_igual", 9)
    f = _ok(client, h, [NPS, {**_com(COMENTARIO, mostrar_se=novo), "condicao": antigo}])
    assert f["perguntas"][1]["logica"]["mostrar_se"] == novo
    # sem nota principal antes: a mensagem e a chave de antes
    assert _erro(client, h, [{**COMENTARIO, "condicao": antigo}, NPS]) == {
        "perguntas.0.condicao": "A condição só pode ser usada em perguntas depois da nota principal."}
    assert _erro(client, h, [NPS, {**COMENTARIO, "condicao": {"tipo": "nota", "operador": "<", "valor": 6}}]) == {
        "perguntas.1.condicao": "Operador inválido."}
    # a quebra de página nunca tem lógica
    q = _ok(client, h, [NPS, {"tipo": "quebra_pagina", "condicao": antigo,
                              "logica": {"mostrar_se": _se("p_nota", "respondida")}}, COMENTARIO])
    assert "logica" not in q["perguntas"][1]


def test_campos_novos(client, admin):
    h = admin["h"]
    unica = {"tipo": "escolha_unica", "titulo": "U", "opcoes": ["A", "B", "C"], "aleatorizar": True,
             "exibicao": "lista"}
    multipla = {"tipo": "escolha_multipla", "titulo": "M", "opcoes": ["A", "B", "C"], "aleatorizar": False,
                "max_selecoes": 2}
    curto = {"tipo": "texto_curto", "titulo": "Nome", "placeholder": " Ex.: Ana "}
    f = _ok(client, h, [NPS, unica, multipla, curto, {"tipo": "comentario", "titulo": "C", "placeholder": ""}])
    p = f["perguntas"]
    assert (p[1]["aleatorizar"], p[1]["exibicao"]) == (True, "lista")
    assert "aleatorizar" not in p[2] and p[2]["max_selecoes"] == 2
    assert p[3]["placeholder"] == "Ex.: Ana" and "placeholder" not in p[4]
    padrao = _ok(client, h, [{**unica, "aleatorizar": False, "exibicao": "botoes"}])["perguntas"][0]
    assert "aleatorizar" not in padrao and "exibicao" not in padrao
    assert _erro(client, h, [{**multipla, "max_selecoes": 4}]) == {
        "perguntas.0.max_selecoes": "O máximo de opções precisa ficar entre 2 e 3."}
    assert _erro(client, h, [{**multipla, "max_selecoes": "dois"}]) == {
        "perguntas.0.max_selecoes": "Informe um número inteiro."}
    assert _erro(client, h, [{**unica, "exibicao": "grade"}]) == {"perguntas.0.exibicao": "Opção inválida."}
    assert _erro(client, h, [{**curto, "placeholder": "x" * 121}]) == {
        "perguntas.0.placeholder": "Use no máximo 120 caracteres."}
    assert _erro(client, h, [{**unica, "aleatorizar": "sim"}]) == {
        "perguntas.0.aleatorizar": "Informe verdadeiro ou falso."}


def test_ids_gerados_nao_repetem_os_que_vieram(client, admin):
    f = _ok(client, admin["h"], [{"tipo": "nps", "titulo": "N"}, {"id": "p_fixo1", "tipo": "comentario",
                                                                  "titulo": "C"}])
    assert f["perguntas"][0]["id"].startswith("p_") and f["perguntas"][1]["id"] == "p_fixo1"
    assert "perguntas.1.id" in _erro(client, admin["h"], [{**NPS, "id": "p 1"}, {**COMENTARIO, "id": "x" * 33}])


# ---- rascunho, publicar e descartar ----------------------------------------------------------------

def test_formulario_novo_publicado_e_campos_do_get(client, admin):
    h = admin["h"]
    f = _ok(client, h, [NPS, COMENTARIO])
    assert (f["versao"], f["rascunho"], f["rascunho_rev"], f["tem_rascunho"], f["finais"]) == (1, None, 0, False, [])
    assert f["publicado_em"] and f["publicado_por_nome"] == admin["usuario"]["nome"]
    assert f["prefixo_imagens"] == imagens.prefixo_publico()
    lista = {x["id"]: x for x in client.get(f"{API}/formularios", headers=h).json()}
    item = lista[f["id"]]
    assert (item["tem_rascunho"], item["versao"], item["perguntas_total"]) == (False, 1, 2)
    assert item["publicado_em"] and "rascunho" not in item and "perguntas" not in item
    # os padrões da conta (semeados) também nascem publicados
    padrao = form_padrao(client, h)
    assert padrao["versao"] == 1 and padrao["publicado_em"]


def test_rascunho_salva_com_problemas_e_conflito(client, admin):
    h = admin["h"]
    gil = membro(client, h, "gil@alfa.com.br", "gestor")
    f = _ok(client, h, [NPS, COMENTARIO])
    doc = {"perguntas": [NPS, {**COMENTARIO, "titulo": ""}, {"tipo": "sim_nao", "titulo": "Novo"}],
           "tema": {**f["tema"], "cor": "#00FF00"}, "finais": [{"nome": "Promo", "titulo": "Oba"}]}
    r = _put(client, gil["h"], f, 0, **doc)
    assert r.status_code == 200, r.text
    corpo = r.json()
    assert corpo["rev"] == 1 and corpo["salvo_em"] and corpo["tem_rascunho"] is True
    assert corpo["problemas"] == {"perguntas.1.titulo": "Escreva o título da pergunta."}
    assert corpo["avisos"] == {}
    novo = corpo["rascunho"]["perguntas"][2]
    assert novo["id"].startswith("p_") and corpo["rascunho"]["finais"][0]["id"].startswith("f_")
    assert corpo["rascunho"]["tema"]["cor"] == "#00ff00"
    # o GET traz o rascunho (com quem salvou) e o publicado continua igual
    g = _obter(client, h, f)
    assert g["rascunho_rev"] == 1 and g["tem_rascunho"] is True and g["versao"] == 1
    assert g["rascunho"]["perguntas"] == corpo["rascunho"]["perguntas"]
    assert g["rascunho"]["salvo_por_nome"] == "Membro gestor" and g["rascunho"]["salvo_em"]
    assert [p["titulo"] for p in g["perguntas"]] == ["Quanto recomendaria?", "Por quê?"]
    # outra aba com o rev velho: 409 com quem e quando salvou
    r = _put(client, h, f, 0, **doc)
    assert r.status_code == 409
    erro = r.json()["erro"]
    assert erro["codigo"] == "rascunho_desatualizado" and erro["rev"] == 1
    assert erro["salvo_por_nome"] == "Membro gestor" and erro["salvo_em"] == g["rascunho"]["salvo_em"]
    # só o estrutural dá 422
    r = _put(client, h, f, 1, perguntas=[NPS, {"tipo": "matriz", "titulo": "X"}])
    assert r.status_code == 422 and r.json()["erro"]["campos"] == {"perguntas.1.tipo": "Tipo de pergunta inválido."}
    r = _put(client, h, f, 1, perguntas=[NPS, {**COMENTARIO, "titulo": "t" * 301}])
    assert r.status_code == 422
    assert r.json()["erro"]["campos"] == {"perguntas.1.titulo": "Use no máximo 300 caracteres."}
    assert _obter(client, h, f)["rascunho_rev"] == 1  # nada gravado


def test_rascunho_guarda_o_que_a_pessoa_fez(client, admin):
    """No rascunho, a lógica com problema, a condição incompleta e as quebras de página ficam como estão."""
    h = admin["h"]
    f = _ok(client, h, [NPS, COMENTARIO])
    perguntas = [{"tipo": "quebra_pagina"}, NPS,
                 _com(COMENTARIO, mostrar_se={"juncao": "todas", "condicoes": [{"fonte": None, "op": None}]}),
                 {"id": "p_sim", "tipo": "sim_nao", "titulo": "S",
                  "logica": {"pular": [{"se": _se("p_sim", "igual", True), "para": "p_nota"}]}},
                 {"tipo": "escolha_unica", "titulo": "U", "opcoes": ["A", "A"]}, {"tipo": "quebra_pagina"}]
    corpo = _put(client, h, f, 0, perguntas=perguntas, finais=[{"nome": "", "titulo": "T"}]).json()
    assert corpo["problemas"] == {
        "perguntas.2.logica": "Escolha a pergunta da condição 1.",
        "perguntas.3.logica": "A regra 1 manda para uma pergunta que vem antes desta (só dá para pular para frente).",
        "perguntas.4.opcoes": "Há opções repetidas.",
        "finais.0.nome": "Dê um nome ao final (só a sua equipe vê)."}
    salvo = corpo["rascunho"]["perguntas"]
    assert [p["tipo"] for p in salvo][0] == "quebra_pagina" and salvo[-1]["tipo"] == "quebra_pagina"
    assert salvo[2]["logica"]["mostrar_se"]["condicoes"] == [{"fonte": None, "op": None, "valor": None}]
    assert salvo[3]["logica"]["pular"][0]["para"] == "p_nota" and salvo[4]["opcoes"] == ["A", "A"]
    # publicar com problemas: 422 com os campos (as quebras do começo e do fim sairiam)
    r = client.post(f"{API}/formularios/{f['id']}/publicar", headers=h, json={"rev": corpo["rev"]})
    assert r.status_code == 422
    assert r.json()["erro"]["campos"] == corpo["problemas"]


def test_rascunho_igual_ao_publicado_vira_nulo_e_avisos_de_citacao(client, admin):
    h = admin["h"]
    f = _ok(client, h, [NPS, COMENTARIO])
    publicado = {"perguntas": f["perguntas"], "tema": f["tema"], "finais": f["finais"]}
    corpo = _put(client, h, f, 0, **publicado).json()
    assert (corpo["rev"], corpo["tem_rascunho"], corpo["problemas"]) == (1, False, {})
    assert _obter(client, h, f)["rascunho"] is None
    # citação de pergunta posterior ou inexistente: aviso (não bloqueia publicar)
    perguntas = [{**NPS, "titulo": "Sobre {{p_coment}}, quanto recomendaria?"},
                 {**COMENTARIO, "descricao": "Você deu {{p_nota}}."},
                 {**CONTEUDO, "html": "<p>{{p_sumiu}} {{c_aviso}}</p>"}]
    finais = [{"nome": "F", "titulo": "Nota {{p_nota}} e {{p_nenhuma}}"}]
    corpo = _put(client, h, f, 1, perguntas=perguntas, finais=finais).json()
    aviso = "A citação {{%s}} não aponta para uma pergunta anterior; ela vai sair vazia."
    assert corpo["problemas"] == corpo["avisos"] == {
        "perguntas.0.titulo": aviso % "p_coment", "perguntas.2.html": aviso % "p_sumiu",
        "finais.0.titulo": "A citação {{p_nenhuma}} não aponta para uma pergunta do formulário; ela vai sair vazia."}
    r = client.post(f"{API}/formularios/{f['id']}/publicar", headers=h, json={"rev": corpo["rev"]})
    assert r.status_code == 200, r.text
    assert r.json()["perguntas"][0]["titulo"] == "Sobre {{p_coment}}, quanto recomendaria?"


def test_publicar(client, admin, dono):
    h = admin["h"]
    f = _ok(client, h, [NPS, COMENTARIO])
    r = client.post(f"{API}/formularios/{f['id']}/publicar", headers=h, json={"rev": 0})
    assert r.status_code == 409 and r.json()["erro"] == {
        "codigo": "sem_rascunho", "mensagem": "Não há alterações para publicar.", "campos": {}}
    novo = [NPS, _com(COMENTARIO, mostrar_se=_se("p_nota", "grupo_e", ["detrator"])), CONTEUDO]
    finais = [{"nome": "Promotores", "titulo": "Valeu!", "mostrar_se": _se("p_nota", "grupo_e", ["promotor"])}]
    rev = _put(client, h, f, 0, perguntas=novo, finais=finais).json()["rev"]
    r = client.post(f"{API}/formularios/{f['id']}/publicar", headers=h, json={"rev": rev - 1})
    assert r.status_code == 409 and r.json()["erro"]["codigo"] == "rascunho_desatualizado"
    r = client.post(f"{API}/formularios/{f['id']}/publicar", headers=h, json={"rev": rev})
    assert r.status_code == 200, r.text
    p = r.json()
    assert (p["versao"], p["rascunho"], p["tem_rascunho"], p["rascunho_rev"]) == (2, None, False, rev + 1)
    assert [x["tipo"] for x in p["perguntas"]] == ["nps", "comentario", "conteudo"] and len(p["finais"]) == 1
    assert p["perguntas_total"] == 2 and p["publicado_por_nome"] == admin["usuario"]["nome"]
    [evento] = _eventos(client, h, "formulario_publicado")
    assert evento["rotulo"] == "Formulário publicado" and evento["gravidade"] == "info"
    assert evento["grupo"] == "configuracoes"
    assert evento["detalhe"] == {"formulario": {"id": f["id"], "nome": "Pesquisa v2"}, "versao": 2, "perguntas": 2,
                                 "finais": 1}
    # o publicado agora é o novo (a página pública já vê)
    publico = client.get(f"{API}/publico/formularios/{f['codigo_publico']}").json()["formulario"]
    assert [x["tipo"] for x in publico["perguntas"]] == ["nps", "comentario", "conteudo"]


def test_publicar_formulario_padrao_mantem_o_tipo(client, admin):
    h = admin["h"]
    nps = form_padrao(client, h)
    corpo = _put(client, h, nps, 0, perguntas=[CSAT]).json()
    assert corpo["problemas"] == {"perguntas": "Este é o formulário padrão de NPS: a nota principal precisa continuar "
                                               "sendo NPS."}
    r = client.post(f"{API}/formularios/{nps['id']}/publicar", headers=h, json={"rev": corpo["rev"]})
    assert r.status_code == 409 and r.json()["erro"]["codigo"] == "formulario_padrao"
    assert _obter(client, h, nps)["versao"] == 1


def test_descartar(client, admin):
    h = admin["h"]
    f = _ok(client, h, [NPS, COMENTARIO])
    rev = _put(client, h, f, 0, perguntas=[NPS]).json()["rev"]
    assert client.delete(f"{API}/formularios/{f['id']}/rascunho", headers=h).status_code == 204
    g = _obter(client, h, f)
    assert (g["rascunho"], g["rascunho_rev"], g["versao"], len(g["perguntas"])) == (None, rev + 1, 1, 2)
    assert _eventos(client, h, "formulario_publicado") == []  # descartar não audita
    assert client.delete(f"{API}/formularios/{f['id']}/rascunho", headers=h).status_code == 204  # sem rascunho: ok
    assert client.delete(f"{API}/formularios/999999/rascunho", headers=h).status_code == 404


def test_patch_publica_direto_e_mantem_o_rascunho(client, admin):
    h = admin["h"]
    f = _ok(client, h, [NPS, COMENTARIO])
    rev = _put(client, h, f, 0, perguntas=[NPS, {"tipo": "sim_nao", "titulo": "Rascunho"}]).json()["rev"]
    r = client.patch(f"{API}/formularios/{f['id']}", headers=h,
                     json={"perguntas": [NPS, {**COMENTARIO, "titulo": "Publicado direto"}],
                           "finais": [{"nome": "F", "titulo": "Obrigado"}]})
    assert r.status_code == 200, r.text
    p = r.json()
    assert p["versao"] == 2 and p["perguntas"][1]["titulo"] == "Publicado direto" and len(p["finais"]) == 1
    # o rascunho fica; o rev sobe (o editor aberto em outra aba recebe 409 e recarrega)
    assert p["rascunho"]["perguntas"][1]["titulo"] == "Rascunho" and p["rascunho_rev"] == rev + 1
    assert _put(client, h, f, rev, perguntas=[NPS]).status_code == 409
    assert [e["detalhe"]["versao"] for e in _eventos(client, h, "formulario_publicado")] == [2]
    # só o tema: valida o documento inteiro (os finais seguem válidos) e publica de novo
    p = client.patch(f"{API}/formularios/{f['id']}", headers=h, json={"tema": {"cor": "#123456"}}).json()
    assert p["versao"] == 3 and p["tema"]["cor"] == "#123456" and p["finais"][0]["titulo"] == "Obrigado"
    # nome, ativo e público não publicam
    p = client.patch(f"{API}/formularios/{f['id']}", headers=h, json={"nome": "Novo nome", "publico": False}).json()
    assert p["versao"] == 3 and p["nome"] == "Novo nome"
    # finais que citam uma pergunta tirada no PATCH: 422
    client.patch(f"{API}/formularios/{f['id']}", headers=h,
                 json={"finais": [{"nome": "F", "titulo": "T", "mostrar_se": _se("p_coment", "respondida")}]})
    r = client.patch(f"{API}/formularios/{f['id']}", headers=h, json={"perguntas": [NPS]})
    assert r.status_code == 422 and r.json()["erro"]["campos"] == {
        "finais.0.mostrar_se": "A condição 1 usa uma pergunta que não existe mais."}


def test_duplicar_copia_rascunho_e_imagens(client, admin, dono):
    h = admin["h"]
    f = _ok(client, h, [NPS, COMENTARIO])
    logo = client.post(f"{API}/formularios/{f['id']}/logo", headers=h,
                       files={"arquivo": ("l.png", png(1), "image/png")}).json()["logo_url"]
    img = client.post(f"{API}/formularios/{f['id']}/imagens", headers=h,
                      files={"arquivo": ("i.png", png(2), "image/png")}).json()["url"]
    no_ar = [NPS, {**CONTEUDO, "html": f'<p>Oi</p><img src="{img}">'}]
    client.patch(f"{API}/formularios/{f['id']}", headers=h, json={"perguntas": no_ar, "tema": {"logo_url": logo}})
    atual = _obter(client, h, f)  # o PATCH publicou: o rev subiu
    r = _put(client, h, atual, atual["rascunho_rev"],
             perguntas=[*no_ar, {"tipo": "sim_nao", "titulo": "Só no rascunho"}])
    assert r.status_code == 200, r.text
    r = client.post(f"{API}/formularios/{f['id']}/duplicar", headers=h)
    assert r.status_code == 201, r.text
    d = r.json()
    assert d["versao"] == 1 and d["rascunho"]["perguntas"][-1]["titulo"] == "Só no rascunho"
    logo_d, img_d = d["tema"]["logo_url"], d["perguntas"][1]["html"].split('src="')[1].split('"')[0]
    assert logo_d != logo and img_d != img and img_d in d["rascunho"]["perguntas"][1]["html"]
    assert client.get(caminho_imagem(logo_d)).content == png(1)
    assert client.get(caminho_imagem(img_d)).content == png(2)
    usos = dict(sql(dono, "select chave, uso from imagens where formulario_id = :f", f=d["id"]))
    assert sorted(usos.values()) == ["conteudo_formulario", "logo_formulario"]
    # descartar o rascunho do original não mexe nas imagens da cópia
    assert client.delete(f"{API}/formularios/{f['id']}/rascunho", headers=h).status_code == 204
    assert client.get(caminho_imagem(img_d)).status_code == 200


def test_permissoes(client, admin):
    h = admin["h"]
    consulta = membro(client, h, "caio@alfa.com.br", "consulta")
    f = _ok(client, h, [NPS])
    hc = consulta["h"]
    assert client.get(f"{API}/formularios/{f['id']}", headers=hc).status_code == 200
    assert _put(client, hc, f, 0, perguntas=[NPS]).status_code == 403
    assert client.post(f"{API}/formularios/{f['id']}/publicar", headers=hc, json={"rev": 0}).status_code == 403
    assert client.delete(f"{API}/formularios/{f['id']}/rascunho", headers=hc).status_code == 403
    assert client.post(f"{API}/formularios/{f['id']}/imagens", headers=hc,
                       files={"arquivo": ("i.png", png(), "image/png")}).status_code == 403
    assert _put(client, {}, f, 0, perguntas=[NPS]).status_code == 401
    # outra conta não acha o formulário
    b = conta_pronta(client, "bia@beta.com.br", empresa="Beta")
    assert _put(client, b["h"], f, 0, perguntas=[NPS]).status_code == 404
    assert client.post(f"{API}/formularios/{f['id']}/publicar", headers=b["h"], json={"rev": 0}).status_code == 404
    assert client.post(f"{API}/formularios/{f['id']}/imagens", headers=b["h"],
                       files={"arquivo": ("i.png", png(), "image/png")}).status_code == 404


def test_modelos_novos(client, admin):
    h = admin["h"]
    ms = {m["chave"]: m for m in client.get(f"{API}/formularios/modelos", headers=h).json()}
    seg = ms["nps_segmentos"]
    assert seg["nome"] == "NPS com acompanhamento e finais por segmento"
    nota = seg["perguntas"][0]["id"]
    assert [p["titulo"] for p in seg["perguntas"][1:]] == [
        "O que podemos melhorar?", "O que você mais valoriza na {empresa}?",
        "Podemos entrar em contato para entender melhor?"]
    assert [p["logica"]["mostrar_se"]["condicoes"][0]["valor"] for p in seg["perguntas"][1:]] == [
        ["detrator", "neutro"], ["promotor"], ["detrator"]]
    assert all(p["logica"]["mostrar_se"]["condicoes"][0]["fonte"] == nota for p in seg["perguntas"][1:])
    assert [(f["nome"], f["titulo"], f["botao"]) for f in seg["finais"]] == [
        ("Promotores", "Obrigado por recomendar a {empresa}!", None), ("Detratores", "Obrigado pela sinceridade", None)]
    assert "Vamos usar o que você contou para melhorar." in seg["finais"][1]["html"]
    ces = ms["ces_atendimento"]
    assert ces["nome"] == "Esforço do cliente (CES)" and [p["tipo"] for p in ces["perguntas"]] == [
        "escala", "comentario", "csat"]
    assert (ces["perguntas"][0]["min"], ces["perguntas"][0]["max"]) == (1, 7)
    assert ces["perguntas"][1]["logica"]["mostrar_se"]["condicoes"][0] == {
        "fonte": ces["perguntas"][0]["id"], "op": "menor_igual", "valor": 3}
    motivo = ms["csat_motivo"]
    assert motivo["nome"] == "CSAT com motivo" and [p["tipo"] for p in motivo["perguntas"]] == [
        "csat", "escolha_multipla", "escolha_multipla", "comentario"]
    assert motivo["perguntas"][1]["opcoes"] != motivo["perguntas"][2]["opcoes"]
    # criar pelo modelo traz as perguntas e os finais, com os ids ligados
    f = _ok(client, h, None, modelo="nps_segmentos")
    assert len(f["perguntas"]) == 4 and len(f["finais"]) == 2
    assert f["finais"][0]["mostrar_se"]["condicoes"][0]["fonte"] == f["perguntas"][0]["id"]
    # os modelos antigos já vêm no formato novo
    entrega = ms["pos_entrega"]["perguntas"]
    assert all("condicao" not in p for m in ms.values() for p in m["perguntas"])
    assert entrega[3]["logica"]["mostrar_se"]["condicoes"][0]["valor"] == ["satisfeito"]


# ---- imagens dos blocos de conteúdo ------------------------------------------------------------

def _imagem(client, h, f, conteudo: bytes = None, nome: str = "foto.png", tipo: str = "image/png"):
    return client.post(f"{API}/formularios/{f['id']}/imagens", headers=h,
                       files={"arquivo": (nome, png() if conteudo is None else conteudo, tipo)})


def test_enviar_imagem(client, admin, dono):
    h = admin["h"]
    f = _ok(client, h, [NPS])
    r = _imagem(client, h, f, png(3), nome="pasta/Banner.png")
    assert r.status_code == 201, r.text
    assert set(r.json()) == {"url", "largura", "altura"} and (r.json()["largura"], r.json()["altura"]) == (1, 1)
    url = r.json()["url"]
    assert url.startswith(imagens.prefixo_publico()) and client.get(caminho_imagem(url)).content == png(3)
    assert sql(dono, "select uso, formulario_id, nome from imagens where chave = :k",
               k=url.rsplit("/", 1)[1]) == [("conteudo_formulario", f["id"], "Banner.png")]
    r = _imagem(client, h, f, b"GIF89a....", nome="x.gif", tipo="image/gif")
    assert r.status_code == 422 and r.json()["erro"]["campos"] == {"arquivo": "Use uma imagem PNG ou JPG de até 1 MB."}
    grande = png() + b"\0" * (1024 * 1024)
    assert _imagem(client, h, f, grande).status_code == 422
    assert _imagem(client, h, f, b"\x89PNG\r\n\x1a\n" + b"\0" * (3 * 1024 * 1024)).status_code == 413
    assert _imagem(client, h, {"id": 999999}).status_code == 404


def test_limite_de_imagens_por_formulario(client, admin, monkeypatch):
    monkeypatch.setattr(imagens, "LIMITE_POR_FORMULARIO", 2)
    h = admin["h"]
    f = _ok(client, h, [NPS])
    assert _imagem(client, h, f).status_code == 201
    assert client.post(f"{API}/formularios/{f['id']}/logo", headers=h,
                       files={"arquivo": ("l.png", png(1), "image/png")}).status_code == 200
    r = _imagem(client, h, f)
    assert r.status_code == 409 and r.json()["erro"]["codigo"] == "limite_imagens"
    # descartar limpa as que ninguém cita e libera espaço
    assert client.delete(f"{API}/formularios/{f['id']}/rascunho", headers=h).status_code == 204
    assert _imagem(client, h, f).status_code == 201


def test_limpeza_ao_publicar_e_ao_descartar(client, admin, dono):
    h = admin["h"]
    f = _ok(client, h, [NPS])
    a, b, c = (_imagem(client, h, f, png(i)).json()["url"] for i in (1, 2, 3))
    rev = _put(client, h, f, 0, perguntas=[NPS, {**CONTEUDO, "html": f'<img src="{a}"><img src="{b}">'}]).json()["rev"]
    # salvar o rascunho não apaga nada (desfazer ainda acha a imagem)
    assert all(client.get(caminho_imagem(u)).status_code == 200 for u in (a, b, c))
    # publicar: sai só a que ninguém cita
    assert client.post(f"{API}/formularios/{f['id']}/publicar", headers=h, json={"rev": rev}).status_code == 200
    assert [client.get(caminho_imagem(u)).status_code for u in (a, b, c)] == [200, 200, 404]
    # rascunho sem a imagem b e com uma nova d; descartar: d sai, b fica (está no publicado)
    d = _imagem(client, h, f, png(4)).json()["url"]
    _put(client, h, f, rev + 1, perguntas=[NPS, {**CONTEUDO, "html": f'<img src="{a}"><img src="{d}">'}])
    assert client.delete(f"{API}/formularios/{f['id']}/rascunho", headers=h).status_code == 204
    assert [client.get(caminho_imagem(u)).status_code for u in (a, b, d)] == [200, 200, 404]
    # imagem de um formulário usada no HTML de outro não sai
    outro = _ok(client, h, [NPS, {**CONTEUDO, "html": f'<img src="{b}">'}])
    client.patch(f"{API}/formularios/{f['id']}", headers=h, json={"perguntas": [NPS]})
    assert [client.get(caminho_imagem(u)).status_code for u in (a, b)] == [404, 200]
    # excluir o formulário leva as imagens dele
    assert client.delete(f"{API}/formularios/{f['id']}", headers=h).status_code == 204
    assert client.get(caminho_imagem(b)).status_code == 404
    assert outro["perguntas"][1]["html"] == f'<img src="{b}">'


def test_banco_de_imagens_em_uso_num_formulario(client, admin):
    h = admin["h"]
    img = client.post(f"{API}/imagens", headers=h, files={"arquivo": ("b.png", png(5), "image/png")}).json()
    f = _ok(client, h, [NPS])
    _put(client, h, f, 0, perguntas=[NPS, {**CONTEUDO, "html": f'<p>Oi</p><img src="{img["url"]}">'}])
    assert client.get(f"{API}/imagens", headers=h).json()["itens"][0]["em_uso"] is True
    r = client.delete(f"{API}/imagens/{img['id']}", headers=h)
    assert r.status_code == 409 and r.json()["erro"] == {
        "codigo": "imagem_em_uso", "campos": {},
        "mensagem": "Esta imagem está no formulário “Pesquisa v2”. Tire a imagem do formulário antes de excluir."}
    # publicar e descartar não apagam imagem do banco
    client.delete(f"{API}/formularios/{f['id']}/rascunho", headers=h)
    assert client.get(f"{API}/imagens", headers=h).json()["itens"][0]["em_uso"] is False
    assert client.delete(f"{API}/imagens/{img['id']}", headers=h).status_code == 204


def test_corpo_grande_demais(client, admin):
    h = admin["h"]
    f = _ok(client, h, [NPS])
    enorme = [{"tipo": "comentario", "titulo": "x" * 300, "descricao": "y" * 1000}] * 1000
    r = _put(client, h, f, 0, perguntas=enorme)
    assert r.status_code == 413 and r.json()["erro"]["codigo"] == "pedido_grande_demais"
    r = client.patch(f"{API}/formularios/{f['id']}", headers=h, json={"perguntas": enorme})
    assert r.status_code == 413
    assert _criar(client, h, enorme).status_code == 413


def test_normalizar_finais_sozinho():
    from toqqi.modulos.formularios.validacao import normalizar_finais

    perguntas = [{**NPS, "descricao": None, "min": 0, "max": 10, "rotulo_min": None, "rotulo_max": None}]
    finais, problemas = normalizar_finais([{"nome": "", "titulo": "T"}], perguntas, estrito=False)
    assert finais[0]["id"].startswith("f_")
    assert problemas == {"finais.0.nome": "Dê um nome ao final (só a sua equipe vê)."}
    with pytest.raises(Exception) as erro:
        normalizar_finais([{"nome": "", "titulo": "T"}], perguntas)
    assert erro.value.campos == {"finais.0.nome": "Dê um nome ao final (só a sua equipe vê)."}

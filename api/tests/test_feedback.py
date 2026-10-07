"""Feedback (docs/api-feedback.md): quem usa o Toqqi relata erros, dá ideias, pede melhorias e elogia; a equipe Toqqi
responde em Plataforma › Feedback."""
import json

from util import conta_pronta, membro, sql, superadmin

from toqqi import tarefas
from toqqi.core.email import caixa_memoria
from toqqi.modulos.feedback import regras, servico

API = "/api/v1"
PNG = (b"\x89PNG\r\n\x1a\n" + (13).to_bytes(4, "big") + b"IHDR" + (1280).to_bytes(4, "big") + (800).to_bytes(4, "big")
       + b"\x08\x02\x00\x00\x00" + b"\x00" * 4 + b"resto")
JPG = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00" + b"\x00" * 64


def _enviar(client, h, imagens=(), **campos):
    dados = {"tipo": "erro", "texto": "O botão Salvar não responde.", **campos}
    arquivos = [("imagens", (nome, conteudo, tipo)) for nome, conteudo, tipo in imagens]
    return client.post(f"{API}/feedback", headers=h, data=dados, files=arquivos or None)


def _criar(client, h, **campos):
    r = _enviar(client, h, **campos)
    assert r.status_code == 201, r.text
    return r.json()


def _emails(para=None):
    return [m for m in caixa_memoria if para is None or m.para == para]


def _plataforma(client, root, **params):
    r = client.get(f"{API}/plataforma/feedback", headers=root["h"], params=params)
    assert r.status_code == 200, r.text
    return r.json()


# ---- enviar --------------------------------------------------------------------------------------------------------

def test_enviar_erro_com_imagens_e_contexto_avisa_a_equipe(client, dono):
    root = superadmin(client)
    a = conta_pronta(client, "ana@alfa.com.br", empresa="Alfa Ltda")
    caixa_memoria.clear()
    diagnostico = {"erros": [{"quando": "2026-10-06T21:00:00.000Z", "tipo": "TypeError",
                              "mensagem": "falhou para ana@alfa.com.br no pedido 12345678", "local": "/contatos/12?x=1"}],
                   "pedidos": [{"quando": "2026-10-06T21:00:01Z", "metodo": "POST", "caminho": "/contatos?token=abc",
                                "status": 500, "codigo": "erro_interno", "request_id": "abc123"},
                               {"metodo": "TRACE", "caminho": "/x", "status": 500}, "lixo"]}
    r = _enviar(client, a["h"], impacto="bloqueia", pagina="/formularios/7?aba=1#x", pagina_titulo="Formulário",
                tela="1280x800", versao_site="abc1234", diagnostico=json.dumps(diagnostico),
                imagens=[("print.png", PNG, "image/png"), ("foto.jpg", JPG, "image/jpeg")])
    assert r.status_code == 201, r.text
    f = r.json()
    assert f["tipo"] == "erro" and f["situacao"] == "recebido" and f["impacto"] == "bloqueia"
    assert f["pagina"] == "/formularios/7" and f["pagina_titulo"] == "Formulário"
    assert not f["autoriza_depoimento"] and "diagnostico" not in f and "nota_interna" not in f
    [m] = f["mensagens"]
    assert m["autor"] == "usuario" and m["texto"] == "O botão Salvar não responde." and m["situacao"] is None
    assert [(i["tipo"], i["largura"], i["altura"], i["nome"]) for i in m["imagens"]] == [
        ("image/png", 1280, 800, "print.png"), ("image/jpeg", None, None, "foto.jpg")]

    linha = sql(dono, "select navegador, tela, versao_site, diagnostico from feedbacks where id = :i", i=f["id"])[0]
    assert linha[0] == "testclient" and linha[1] == "1280x800" and linha[2] == "abc1234"
    diag = linha[3]
    assert diag["erros"] == [{"quando": "2026-10-06T21:00:00.000Z", "tipo": "TypeError",
                              "mensagem": "falhou para … no pedido …", "local": "/contatos/12"}]
    assert diag["pedidos"] == [{"quando": "2026-10-06T21:00:01Z", "metodo": "POST", "caminho": "/contatos",
                                "status": 500, "codigo": "erro_interno", "request_id": "abc123"}]

    [aviso] = _emails("root@toqqi.com")
    assert aviso.assunto == "[Impede o trabalho] Feedback novo: Erro de Pessoa, Alfa Ltda"
    assert "ana@alfa.com.br" in aviso.texto and "relatou um erro" in aviso.texto
    assert "O botão Salvar não responde." in aviso.texto and "Impacto: Impede o trabalho." in aviso.texto
    assert "Tela: Formulário (/formularios/7)." in aviso.texto and "2 imagens anexadas." in aviso.texto
    assert f"http://app.teste/plataforma/feedback/{f['id']}" in aviso.texto
    # o aviso à equipe não entra no registro de e-mails da conta
    assert sql(dono, "select count(*) from emails_enviados where assunto like '%eedback%'")[0][0] == 0
    assert root["usuario"]["email"] == "root@toqqi.com"


def test_sem_detalhes_tecnicos_nao_guarda_navegador_tela_nem_diagnostico(client, dono):
    a = conta_pronta(client, "ana@alfa.com.br")
    f = _criar(client, a["h"], tipo="sugestao", texto="Exportar em PDF", detalhes="false", tela="1280x800",
               versao_site="abc", diagnostico=json.dumps({"erros": [{"tipo": "X"}]}), pagina="/relatorios/empresas",
               impacto="bloqueia")
    assert f["impacto"] is None  # só erro tem impacto
    assert sql(dono, "select navegador, tela, versao_site, diagnostico, pagina from feedbacks")[0] == (
        None, None, None, None, "/relatorios/empresas")


def test_validacoes_do_envio(client):
    a = conta_pronta(client, "ana@alfa.com.br")
    casos = [
        ({"tipo": "reclamacao"}, (), "tipo"),
        ({"texto": "   \n  "}, (), "texto"),
        ({"texto": "x" * 5001}, (), "texto"),
        ({"impacto": "muito"}, (), "impacto"),
        ({}, [("a.png", PNG, "image/png")] * 4, "imagens"),
        ({}, [("a.gif", b"GIF89a....", "image/gif")], "imagens"),
        ({}, [("a.png", PNG + b"0" * (1024 * 1024), "image/png")], "imagens"),
        ({}, [("a.png", b"<svg onload=alert(1)>", "image/png")], "imagens"),
    ]
    for campos, imagens, campo in casos:
        r = _enviar(client, a["h"], imagens=imagens, **campos)
        assert r.status_code == 422, (campos, r.text)
        assert campo in r.json()["erro"]["campos"], (campos, r.json())
    assert client.get(f"{API}/feedback", headers=a["h"]).json()["itens"] == []
    assert _enviar(client, {}).status_code == 401


def test_contexto_fora_do_formato_some_calado():
    assert regras.limpar_pagina("https://outro.site/x") is None
    assert regras.limpar_pagina("//evil.com") is None
    assert regras.limpar_pagina("/a b/c?d") == "/ab/c"
    assert regras.limpar_tela("1280x800; drop") is None
    assert regras.limpar_versao("abc 123") is None
    assert regras.limpar_diagnostico("{nao é json") is None
    assert regras.limpar_diagnostico(json.dumps({"erros": [{"tipo": ""}], "pedidos": []})) is None
    muitos = {"erros": [{"tipo": "E", "mensagem": "m" * 300} for _ in range(40)],
              "pedidos": [{"metodo": "GET", "caminho": "/x/" + "y" * 180, "status": 500} for _ in range(40)]}
    limpo = regras.limpar_diagnostico(json.dumps(muitos))
    assert len(limpo["erros"]) <= 10 and len(limpo["pedidos"]) <= 10
    assert len(json.dumps(limpo, ensure_ascii=False).encode()) <= regras.MAX_DIAGNOSTICO_BYTES
    assert regras.limpar_texto("  oi\r\n\x00tudo​ bem\n\n\n\n\nfim  ") == "oi\ntudo bem\n\n\nfim"


# ---- quem vê o quê -------------------------------------------------------------------------------------------------

def test_cada_um_ve_so_os_proprios_e_as_imagens_sao_privadas(client):
    a = conta_pronta(client, "ana@alfa.com.br")
    gil = membro(client, a["h"], "gil@alfa.com.br", "gestor")
    b = conta_pronta(client, "bia@beta.com.br")
    f = _criar(client, a["h"], imagens=[("print.png", PNG, "image/png")])
    img = f["mensagens"][0]["imagens"][0]["id"]

    r = client.get(f"{API}/feedback/{f['id']}/imagens/{img}", headers=a["h"])
    assert r.status_code == 200 and r.content == PNG and r.headers["content-type"] == "image/png"
    assert r.headers["cache-control"] == "private, max-age=3600" and r.headers["x-content-type-options"] == "nosniff"
    for outro in (gil, b):  # mesmo administrador da conta não vê o feedback de outra pessoa
        assert client.get(f"{API}/feedback/{f['id']}", headers=outro["h"]).status_code == 404
        assert client.get(f"{API}/feedback/{f['id']}/imagens/{img}", headers=outro["h"]).status_code == 404
        assert client.post(f"{API}/feedback/{f['id']}/mensagens", headers=outro["h"],
                           data={"texto": "oi"}).status_code == 404
        assert client.get(f"{API}/feedback", headers=outro["h"]).json() == {"itens": [], "novidades": 0}
    assert client.get(f"{API}/feedback/{f['id']}/imagens/999", headers=a["h"]).status_code == 404
    # a plataforma é só da equipe Toqqi
    for rota in ("", "/contagem", f"/{f['id']}", f"/{f['id']}/imagens/{img}"):
        assert client.get(f"{API}/plataforma/feedback{rota}", headers=a["h"]).status_code == 403
    assert client.post(f"{API}/plataforma/feedback/{f['id']}/mensagens", headers=a["h"],
                       json={"texto": "x"}).status_code == 403


def test_lista_do_usuario_com_trecho_contagens_e_ordem(client):
    a = conta_pronta(client, "ana@alfa.com.br")
    f1 = _criar(client, a["h"], tipo="sugestao", texto="Uma ideia " + "longa " * 60)
    f2 = _criar(client, a["h"], tipo="elogio", texto="Adorei o Início!", autoriza_depoimento="true",
                imagens=[("a.png", PNG, "image/png")])
    r = client.post(f"{API}/feedback/{f1['id']}/mensagens", headers=a["h"], data={"texto": "Mais um detalhe"},
                    files=[("imagens", ("b.png", PNG, "image/png"))])
    assert r.status_code == 201, r.text
    lista = client.get(f"{API}/feedback", headers=a["h"]).json()
    assert [i["id"] for i in lista["itens"]] == [f1["id"], f2["id"]]  # atividade mais recente primeiro
    primeiro = lista["itens"][0]
    assert primeiro["trecho"].startswith("Uma ideia longa") and primeiro["trecho"].endswith("…")
    assert len(primeiro["trecho"]) == regras.MAX_TRECHO
    assert (primeiro["mensagens"], primeiro["imagens"], primeiro["novidade"]) == (2, 1, False)
    assert lista["itens"][1]["autoriza_depoimento"] is True and lista["novidades"] == 0


# ---- conversa com a equipe ------------------------------------------------------------------------------------------

def test_conversa_completa_com_avisos_e_marcas_de_leitura(client, dono):
    root = superadmin(client)
    a = conta_pronta(client, "ana@alfa.com.br", empresa="Alfa Ltda")
    f = _criar(client, a["h"], tipo="melhoria", texto="O filtro de período podia lembrar a escolha.")
    fid = f["id"]
    assert _plataforma(client, root)["contagem"] == {"atencao": 1, "abertos": 1}
    [item] = _plataforma(client, root)["itens"]
    assert item["atencao"] is True and item["conta_nome"] == "Alfa Ltda" and item["autor_email"] == "ana@alfa.com.br"

    # a equipe abre: deixa de pedir atenção
    d = client.get(f"{API}/plataforma/feedback/{fid}", headers=root["h"]).json()
    assert d["conta"]["nome"] == "Alfa Ltda" and d["autor"]["email"] == "ana@alfa.com.br"
    assert d["contexto"]["navegador"] == "testclient" and d["nota_interna"] == ""
    assert client.get(f"{API}/plataforma/feedback/contagem", headers=root["h"]).json() == {"atencao": 0, "abertos": 1}

    # resposta com situação nova: e-mail para a Ana (registrado na conta) e novidade para ela
    caixa_memoria.clear()
    r = client.post(f"{API}/plataforma/feedback/{fid}/mensagens", headers=root["h"],
                    json={"texto": "Boa ideia!\n\nVai entrar na próxima versão.", "situacao": "planejado"})
    assert r.status_code == 201, r.text
    assert r.json()["situacao"] == "planejado"
    assert [(m["autor"], m["autor_nome"], m["situacao"]) for m in r.json()["mensagens"]] == [
        ("usuario", "Pessoa", None), ("equipe", "Pessoa", "planejado")]
    [m] = _emails("ana@alfa.com.br")
    assert m.assunto == "A equipe Toqqi respondeu seu feedback"
    assert "respondeu a melhoria que você pediu em" in m.texto and "Vai entrar na próxima versão." in m.texto
    assert "Situação do seu feedback: Planejado." in m.texto and f"http://app.teste/feedback/{fid}" in m.texto
    assert sql(dono, "select destinatario, assunto from emails_enviados where tipo = 'feedback'") == [
        ("ana@alfa.com.br", "A equipe Toqqi respondeu seu feedback")]
    assert client.get(f"{API}/feedback/novidades", headers=a["h"]).json() == {"novidades": 1}
    assert client.get(f"{API}/feedback", headers=a["h"]).json()["itens"][0]["novidade"] is True

    # a Ana abre a conversa: a novidade some
    d = client.get(f"{API}/feedback/{fid}", headers=a["h"]).json()
    assert d["mensagens"][1]["texto"] == "Boa ideia!\n\nVai entrar na próxima versão."
    assert client.get(f"{API}/feedback/novidades", headers=a["h"]).json() == {"novidades": 0}

    # a Ana responde: a equipe estava em dia, então recebe aviso; a segunda mensagem seguida não avisa de novo
    caixa_memoria.clear()
    client.post(f"{API}/feedback/{fid}/mensagens", headers=a["h"], data={"texto": "Obrigada!"})
    client.post(f"{API}/feedback/{fid}/mensagens", headers=a["h"], data={"texto": "Ah, e no celular também."})
    [aviso] = _emails("root@toqqi.com")
    assert aviso.assunto == f"Nova mensagem no feedback #{fid} de Pessoa, Alfa Ltda" and "Obrigada!" in aviso.texto
    assert client.get(f"{API}/plataforma/feedback/contagem", headers=root["h"]).json()["atencao"] == 1

    # mudar só a situação: entra na conversa, vira novidade, sem e-mail; nota interna só a equipe vê
    caixa_memoria.clear()
    r = client.patch(f"{API}/plataforma/feedback/{fid}", headers=root["h"],
                     json={"situacao": "concluido", "nota_interna": "  Entrou na versão 2.3  "})
    assert r.status_code == 200, r.text
    assert r.json()["nota_interna"] == "Entrou na versão 2.3" and r.json()["mensagens"][-1]["texto"] == ""
    assert r.json()["mensagens"][-1]["situacao"] == "concluido" and caixa_memoria == []
    d = client.get(f"{API}/feedback/{fid}", headers=a["h"]).json()
    assert d["situacao"] == "concluido" and "nota_interna" not in d
    # mesma situação de novo e nada para dizer: 422; só a nota não mexe na conversa
    r = client.post(f"{API}/plataforma/feedback/{fid}/mensagens", headers=root["h"], json={"situacao": "concluido"})
    assert r.status_code == 422 and "texto" in r.json()["erro"]["campos"]
    n = len(client.patch(f"{API}/plataforma/feedback/{fid}", headers=root["h"], json={"nota_interna": "x"}).json()["mensagens"])
    assert n == len(d["mensagens"])
    assert client.patch(f"{API}/plataforma/feedback/{fid}", headers=root["h"],
                        json={"situacao": "arquivado"}).status_code == 422
    assert client.get(f"{API}/plataforma/feedback/999", headers=root["h"]).status_code == 404


def test_filtros_e_busca_da_plataforma(client):
    root = superadmin(client)
    a = conta_pronta(client, "ana@alfa.com.br", empresa="Alfa Ltda")
    b = conta_pronta(client, "bia@beta.com.br", empresa="Beta SA")
    e1 = _criar(client, a["h"], texto="Tela branca ao importar 100%_ok")
    s1 = _criar(client, b["h"], tipo="sugestao", texto="Integração com o Slack")
    el = _criar(client, b["h"], tipo="elogio", texto="Muito bom")
    client.patch(f"{API}/plataforma/feedback/{el['id']}", headers=root["h"], json={"situacao": "encerrado"})

    def ids(**p):
        return [i["id"] for i in _plataforma(client, root, **p)["itens"]]

    assert ids() == [s1["id"], e1["id"]]  # abertos, atividade mais recente primeiro
    assert ids(situacao="todos") == [el["id"], s1["id"], e1["id"]]
    assert ids(situacao="encerrados") == [el["id"]] and ids(situacao="concluidos") == []
    assert ids(tipo="sugestao") == [s1["id"]]
    assert ids(busca="beta", situacao="todos") == [el["id"], s1["id"]]
    assert ids(busca="bia@beta") == [s1["id"]]
    assert ids(busca="SLACK") == [s1["id"]]
    assert ids(busca="100%_") == [e1["id"]]  # % e _ são texto, não curinga
    assert ids(busca="100%x") == []
    assert client.get(f"{API}/plataforma/feedback", headers=root["h"], params={"situacao": "x"}).status_code == 422


def test_elogio_autoriza_e_retira_o_depoimento(client):
    a = conta_pronta(client, "ana@alfa.com.br")
    el = _criar(client, a["h"], tipo="elogio", texto="O Toqqi mudou nosso atendimento.", autoriza_depoimento="true")
    assert el["autoriza_depoimento"] is True
    r = client.patch(f"{API}/feedback/{el['id']}", headers=a["h"], json={"autoriza_depoimento": False})
    assert r.status_code == 200 and r.json()["autoriza_depoimento"] is False
    erro = _criar(client, a["h"], autoriza_depoimento="true")
    assert erro["autoriza_depoimento"] is False  # só elogio
    r = client.patch(f"{API}/feedback/{erro['id']}", headers=a["h"], json={"autoriza_depoimento": True})
    assert r.status_code == 409 and r.json()["erro"]["codigo"] == "nao_e_elogio"


def test_resposta_nao_vai_por_email_a_quem_saiu_ou_retirou_o_aceite(client, dono):
    root = superadmin(client)
    a = conta_pronta(client, "ana@alfa.com.br")
    gil = membro(client, a["h"], "gil@alfa.com.br", "gestor")
    f_gil = _criar(client, gil["h"])
    f_ana = _criar(client, a["h"])
    # Ana retirou o aceite (e não aceitou de novo)
    assert sql(dono, "update aceites_termos set revogado_em = now() where usuario_id = :u", u=a["usuario"]["id"]) == 1
    # Gil sai da conta
    assert client.delete(f"{API}/equipe/{gil['usuario']['id']}", headers=a["h"]).status_code in (200, 204)
    caixa_memoria.clear()
    for f in (f_gil, f_ana):
        r = client.post(f"{API}/plataforma/feedback/{f['id']}/mensagens", headers=root["h"], json={"texto": "Resolvido."})
        assert r.status_code == 201, r.text
    assert caixa_memoria == []
    d = client.get(f"{API}/plataforma/feedback/{f_gil['id']}", headers=root["h"]).json()
    assert d["autor"] is None and d["mensagens"][0]["autor_nome"] is None


def test_limites_de_imagens_e_mensagens(client, monkeypatch):
    a = conta_pronta(client, "ana@alfa.com.br")
    tres = [("a.png", PNG, "image/png")] * 3
    f = _criar(client, a["h"], imagens=tres)
    for _ in range(3):
        assert client.post(f"{API}/feedback/{f['id']}/mensagens", headers=a["h"],
                           files=[("imagens", t) for t in tres]).status_code == 201
    r = client.post(f"{API}/feedback/{f['id']}/mensagens", headers=a["h"], files=[("imagens", tres[0])])
    assert r.status_code == 409 and r.json()["erro"]["codigo"] == "limite_imagens"
    r = client.post(f"{API}/feedback/{f['id']}/mensagens", headers=a["h"], data={"texto": " "})
    assert r.status_code == 422
    monkeypatch.setattr(regras, "MAX_MENSAGENS", 4)  # já são 4: o relato e as 3 respostas com imagens
    r = client.post(f"{API}/feedback/{f['id']}/mensagens", headers=a["h"], data={"texto": "mais uma"})
    assert r.status_code == 409 and r.json()["erro"]["codigo"] == "limite_mensagens"


def test_limpeza_apaga_imagens_dos_concluidos_antigos(client, dono):
    a = conta_pronta(client, "ana@alfa.com.br")
    velho = _criar(client, a["h"], imagens=[("a.png", PNG, "image/png")])
    aberto = _criar(client, a["h"], imagens=[("a.png", PNG, "image/png")])
    recente = _criar(client, a["h"], imagens=[("a.png", PNG, "image/png")])
    sql(dono, "update feedbacks set situacao = 'concluido', atualizado_em = now() - interval '181 days' where id = :i",
        i=velho["id"])
    sql(dono, "update feedbacks set atualizado_em = now() - interval '400 days' where id = :i", i=aberto["id"])
    sql(dono, "update feedbacks set situacao = 'encerrado', atualizado_em = now() - interval '179 days' where id = :i",
        i=recente["id"])
    assert tarefas.limpeza()["feedback_imagens_apagadas"] == 1
    assert sorted(x for x, in sql(dono, "select feedback_id from feedback_imagens")) == sorted([aberto["id"], recente["id"]])
    assert len(sql(dono, "select id from feedback_mensagens where feedback_id = :i", i=velho["id"])) == 1  # a conversa fica
    assert servico.limpar_imagens_antigas() == 0


def test_excluir_a_conta_leva_os_feedbacks(client, dono):
    root = superadmin(client)
    a = conta_pronta(client, "ana@alfa.com.br", empresa="Alfa Ltda")
    f = _criar(client, a["h"], imagens=[("a.png", PNG, "image/png")])
    assert client.post(f"{API}/plataforma/feedback/{f['id']}/mensagens", headers=root["h"],
                       json={"texto": "Oi"}).status_code == 201
    r = client.request("DELETE", f"{API}/plataforma/contas/{a['conta']['id']}", headers=root["h"],
                       json={"confirmar_nome": "Alfa Ltda"})
    assert r.status_code == 204, r.text
    for tabela in ("feedbacks", "feedback_mensagens", "feedback_imagens"):
        assert sql(dono, f"select count(*) from {tabela}")[0][0] == 0


def test_tabelas_com_rls_forcado(dono, app_engine):
    from sqlalchemy import text

    with dono.connect() as c:
        linhas = c.execute(text("select relname, relrowsecurity, relforcerowsecurity from pg_class where relname in "
                                "('feedbacks','feedback_mensagens','feedback_imagens')")).all()
    assert len(linhas) == 3 and all(r and f for _, r, f in linhas)
    with app_engine.connect() as c:  # papel da aplicação, sem contexto: não enxerga nada
        assert c.execute(text("select count(*) from feedbacks")).scalar() == 0


def test_sem_superadmin_confirmado_ninguem_recebe(client):
    a = conta_pronta(client, "ana@alfa.com.br")
    caixa_memoria.clear()
    assert _criar(client, a["h"])["id"]
    assert caixa_memoria == []  # sem superadmin confirmado: só o log avisa

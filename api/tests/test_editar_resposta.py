"""O cliente pode mudar a resposta (docs/api-editar-resposta.md): opção do formulário, convite reaberto e link público
com a chave, prazo de 7 dias e os efeitos (plano de ação, webhook, depoimento, última nota)."""
import json

from util import (
    conta_pronta,
    criar_contato,
    criar_empresa,
    criar_responsavel,
    form_padrao,
    link_pesquisa,
    responder_link,
    sql,
)

from toqqi.core.email import caixa_memoria

API = "/api/v1"
URL_WEBHOOK = "https://erp.cliente.com.br/toqqi"


def _preparar(client, editar=True):
    a = conta_pronta(client, "ana@alfa.com.br", empresa="Alfa Ltda")
    h = a["h"]
    rita = criar_responsavel(client, h, "Rita Gomes", email="rita@alfa.com.br")
    empresa = criar_empresa(client, h, "Mercado Bom Preço", responsavel_id=rita["id"])
    contato = criar_contato(client, h, nome="Bia Souza", email="bia@bompreco.com.br", empresa_id=empresa["id"])
    f = form_padrao(client, h)
    if editar:
        r = client.patch(f"{API}/formularios/{f['id']}", headers=h, json={"permite_editar": True})
        assert r.status_code == 200 and r.json()["permite_editar"] is True, r.text
    nota, comentario = f["perguntas"][0]["id"], f["perguntas"][1]["id"]
    return a, h, f, contato, nota, comentario


def _responder(client, token, respostas):
    return client.post(f"{API}/publico/convites/{token}/responder", json={"respostas": respostas})


def test_sem_a_opcao_o_convite_continua_ja_respondido(client):
    _, h, f, contato, nota, _ = _preparar(client, editar=False)
    assert f["permite_editar"] is False
    token = link_pesquisa(client, h, contato["id"], formulario_id=f["id"])
    r = _responder(client, token, {nota: 7})
    assert r.status_code == 201 and r.json()["edicao"] is None
    pagina = client.get(f"{API}/publico/convites/{token}").json()
    assert pagina["ja_respondido"] is True and pagina["edicao"] is None
    r = _responder(client, token, {nota: 9})
    assert r.status_code == 409 and r.json()["erro"]["codigo"] == "ja_respondido"


def test_convite_reaberto_vem_preenchido_e_a_mudanca_troca_a_mesma_resposta(client, dono):
    _, h, f, contato, nota, comentario = _preparar(client)
    token = link_pesquisa(client, h, contato["id"], formulario_id=f["id"])
    caixa_memoria.clear()
    r = _responder(client, token, {nota: 3, comentario: "Entrega atrasou"})
    assert r.status_code == 201
    assert r.json()["edicao"]["ate"]
    [rid] = [x for x, in sql(dono, "select id from respostas")]
    [(acao_id, nota_acao)] = sql(dono, "select id, nota from acoes where resposta_id = :r", r=rid)
    assert nota_acao == 3
    assert any(m.assunto.startswith("Alerta de risco") for m in caixa_memoria)

    pagina = client.get(f"{API}/publico/convites/{token}").json()
    assert pagina["ja_respondido"] is True
    assert pagina["edicao"]["respostas"] == {nota: 3, comentario: "Entrega atrasou"}
    criada, ate = sql(dono, "select criada_em, criada_em + interval '7 days' from respostas where id = :r", r=rid)[0]
    assert pagina["edicao"]["respondida_em"][:19] == criada.isoformat()[:19]
    assert pagina["edicao"]["ate"][:19] == ate.isoformat()[:19]

    caixa_memoria.clear()
    r = _responder(client, token, {nota: 9, comentario: "Resolveram rápido, obrigado!"})
    assert r.status_code == 201, r.text
    assert r.json()["titulo_final"] and r.json()["edicao"]["ate"]
    linhas = sql(dono, "select id, nota, grupo, comentario_cliente, edicoes, editada_em is not null from respostas")
    assert linhas == [(rid, 9, "promotor", "Resolveram rápido, obrigado!", 1, True)]
    assert sql(dono, "select ultima_nota from contatos where id = :c", c=contato["id"])[0][0] == 9
    # o plano fica aberto, com a nota nova marcada; sem agradecimento nem alerta de novo
    assert sql(dono, "select situacao, nota, nota_editada, nota_editada_em is not null from acoes") == [
        ("a_fazer", 3, 9, True)]
    assert not any(m.assunto.startswith("Alerta de risco") for m in caixa_memoria)
    acao = client.get(f"{API}/acoes/{acao_id}", headers=h).json()
    assert (acao["nota"], acao["nota_editada"]) == (3, 9) and acao["nota_editada_em"]
    resposta = client.get(f"{API}/respostas/{rid}", headers=h).json()
    assert resposta["edicoes"] == 1 and resposta["editada_em"] and resposta["nota"] == 9

    # voltou para a nota do plano: a marca sai
    r = _responder(client, token, {nota: 3})
    assert r.status_code == 201
    assert sql(dono, "select nota_editada, nota_editada_em from acoes") == [(None, None)]
    assert sql(dono, "select edicoes, comentario_cliente from respostas") == [(2, "")]


def test_a_nota_nova_pede_o_plano_que_nao_existia(client, dono):
    _, h, f, contato, nota, comentario = _preparar(client)
    token = link_pesquisa(client, h, contato["id"], formulario_id=f["id"])
    assert _responder(client, token, {nota: 10}).status_code == 201
    assert sql(dono, "select count(*) from acoes")[0][0] == 0
    caixa_memoria.clear()
    assert _responder(client, token, {nota: 2, comentario: "Mudei de ideia"}).status_code == 201
    assert sql(dono, "select nota, grupo, prioridade, nota_editada from acoes") == [(2, "detrator", "alta", None)]
    assert any(m.para == "rita@alfa.com.br" and m.assunto.startswith("Alerta de risco") for m in caixa_memoria)


def test_prazo_de_7_dias_e_resposta_arquivada(client, dono):
    _, h, f, contato, nota, _ = _preparar(client)
    token = link_pesquisa(client, h, contato["id"], formulario_id=f["id"])
    assert _responder(client, token, {nota: 6}).status_code == 201
    sql(dono, "update respostas set criada_em = now() - interval '7 days 1 minute'")
    pagina = client.get(f"{API}/publico/convites/{token}").json()
    assert pagina["ja_respondido"] is True and pagina["edicao"] is None
    r = _responder(client, token, {nota: 9})
    assert r.status_code == 409 and r.json()["erro"]["codigo"] == "ja_respondido"
    # dentro do prazo, mas arquivada pela equipe: não muda
    sql(dono, "update respostas set criada_em = now() - interval '6 days', arquivada = true, arquivada_em = now()")
    assert client.get(f"{API}/publico/convites/{token}").json()["edicao"] is None
    assert _responder(client, token, {nota: 9}).status_code == 409
    # desligar a opção também fecha a edição
    sql(dono, "update respostas set arquivada = false, arquivada_em = null")
    assert client.get(f"{API}/publico/convites/{token}").json()["edicao"] is not None
    client.patch(f"{API}/formularios/{f['id']}", headers=h, json={"permite_editar": False})
    assert _responder(client, token, {nota: 9}).status_code == 409
    assert sql(dono, "select nota, edicoes from respostas") == [(6, 0)]


def test_link_publico_muda_so_com_a_chave_devolvida(client, dono):
    _, h, f, _, nota, comentario = _preparar(client)
    r = responder_link(client, f["codigo_publico"], {nota: 4})
    assert r.status_code == 201, r.text
    chave = r.json()["edicao"]["chave"]
    rid = int(chave.split(".")[0])
    assert r.json()["edicao"]["ate"]
    assert len(sql(dono, "select edicao_hash from respostas where id = :r", r=rid)[0][0]) == 64

    def editar(chave_usada, respostas, codigo=None):
        return client.post(f"{API}/publico/formularios/{codigo or f['codigo_publico']}/editar",
                           json={"chave": chave_usada, "respostas": respostas})

    r = editar(chave, {nota: 8, comentario: "Melhorou"})
    assert r.status_code == 200, r.text
    assert r.json()["edicao"] == {"chave": chave, "ate": r.json()["edicao"]["ate"]}
    assert sql(dono, "select count(*), max(nota), max(edicoes) from respostas") == [(1, 8, 1)]
    for errada in (f"{rid}.outra", f"{rid + 1}.{chave.split('.', 1)[1]}", "sem-ponto", f"x.{chave}"):
        r = editar(errada, {nota: 1})
        assert r.status_code == 409 and r.json()["erro"]["codigo"] == "edicao_indisponivel", errada
    # a chave de um formulário não serve no outro
    outro = client.post(f"{API}/formularios/{f['id']}/duplicar", headers=h).json()
    assert outro["permite_editar"] is True
    assert editar(chave, {nota: 1}, codigo=outro["codigo_publico"]).status_code == 409
    # prazo vencido
    sql(dono, "update respostas set criada_em = now() - interval '8 days'")
    assert editar(chave, {nota: 1}).status_code == 409
    # sem a opção, o envio nem devolve chave
    client.patch(f"{API}/formularios/{f['id']}", headers=h, json={"permite_editar": False})
    r = responder_link(client, f["codigo_publico"], {nota: 10})
    assert r.status_code == 201 and r.json()["edicao"] is None
    assert sql(dono, "select max(nota) from respostas where edicoes = 1")[0][0] == 8


def test_link_publico_envio_repetido_volta_sem_chave(client, dono):
    # a mesma resposta do mesmo IP, há pouco, não é gravada de novo; num tablet de balcão ela pode ser de outra pessoa
    _, _, f, _, nota, _ = _preparar(client)
    r1 = responder_link(client, f["codigo_publico"], {nota: 6}, ip="203.0.113.20")
    r2 = responder_link(client, f["codigo_publico"], {nota: 6}, ip="203.0.113.20")
    assert r1.status_code == r2.status_code == 201
    assert r1.json()["edicao"]["chave"] and r2.json()["edicao"] is None
    assert sql(dono, "select count(*) from respostas")[0][0] == 1


def test_webhook_resposta_atualizada_com_a_nota_anterior(client, dono, destino):
    _, h, f, contato, nota, comentario = _preparar(client)
    w = client.post(f"{API}/integracoes/webhooks", headers=h,
                    json={"url": URL_WEBHOOK, "eventos": ["resposta.criada", "resposta.atualizada"]})
    assert w.status_code == 201, w.text
    token = link_pesquisa(client, h, contato["id"], formulario_id=f["id"])
    _responder(client, token, {nota: 5})
    _responder(client, token, {nota: 7, comentario: "Agora sim"})
    eventos = sql(dono, "select evento, corpo from webhook_entregas order by criado_em, evento")
    assert [e for e, _ in eventos] == ["resposta.criada", "resposta.atualizada"]
    corpo = eventos[1][1] if isinstance(eventos[1][1], dict) else json.loads(eventos[1][1])
    dados = corpo["dados"]
    assert dados["nota"] == 7 and dados["nota_anterior"] == 5 and dados["edicoes"] == 1 and dados["editada_em"]
    assert dados["contato"]["email"] == "bia@bompreco.com.br"


def test_depoimento_autorizado_volta_a_pendente_quando_o_comentario_muda(client, dono):
    _, h, f, contato, nota, comentario = _preparar(client)
    token = link_pesquisa(client, h, contato["id"], formulario_id=f["id"])
    _responder(client, token, {nota: 10, comentario: "Excelente"})
    sql(dono, "update respostas set depoimento_em = now(), depoimento_situacao = 'aprovado'")
    _responder(client, token, {nota: 10, comentario: "Excelente"})  # nada mudou no texto
    assert sql(dono, "select depoimento_situacao from respostas")[0][0] == "aprovado"
    _responder(client, token, {nota: 10, comentario: "Excelente, mas o preço subiu"})
    assert sql(dono, "select depoimento_situacao from respostas")[0][0] == "pendente"


def test_opcao_no_formulario(client):
    _, h, f, *_ = _preparar(client, editar=False)
    assert client.get(f"{API}/formularios/{f['id']}", headers=h).json()["permite_editar"] is False
    r = client.patch(f"{API}/formularios/{f['id']}", headers=h, json={"permite_editar": True})
    assert r.status_code == 200 and r.json()["permite_editar"] is True
    lista = client.get(f"{API}/formularios", headers=h).json()
    assert next(x for x in lista if x["id"] == f["id"])["permite_editar"] is True

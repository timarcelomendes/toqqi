"""Etapa 5c: indicações — o convite de indicação na tela final da pesquisa (só com as regras de §2), a indicação pela
página pública (validações, limite de 3 tentativas aceitas, repetida sem revelar, resposta arquivada e formulário fora
do ar, responsável, e-mail, webhook, log, corpo grande demais), a lista (filtros, busca sem acento, resumo), a indicação
registrada à mão, as regras do PATCH, a exclusão (LGPD, com as entregas de webhook), o CSV e as entradas estranhas
(ids fora do bigint, NUL, controles bidirecionais, texto enorme, e-mail que não é texto)."""
import csv
import io
import json
import logging
from datetime import timedelta

import pytest
from util import (
    API,
    conta_pronta,
    convite_respondido,
    criar_contato,
    criar_empresa,
    criar_responsavel,
    emails_para,
    form_padrao,
    indicacoes,
    indicar,
    ligar_indicacoes,
    link_pesquisa,
    membro,
    responder_link,
    sql,
)

from toqqi.core import relogio
from toqqi.core.email import caixa_memoria

pytestmark = pytest.mark.usefixtures("relogio_estavel")
URL_WEBHOOK = "https://erp.cliente.com.br/toqqi"


@pytest.fixture
def alfa(client):
    """Conta com as indicações ligadas; Mercado Bom Preço (responsável Rita, com e-mail) e a contato Ana Souza."""
    a = conta_pronta(client, "ana@alfa.com.br", empresa="Alfa Distribuidora")
    h = a["h"]
    ligar_indicacoes(client, h)
    rita = criar_responsavel(client, h, "Rita Gomes", email="rita@alfa.com.br")
    empresa = criar_empresa(client, h, "Mercado Bom Preço", responsavel_id=rita["id"])
    contato = criar_contato(client, h, nome="Ana Souza", email="ana@bompreco.com.br", empresa_id=empresa["id"])
    a.update(rita=rita, empresa=empresa, contato=contato)
    return a


def _webhook(client, h, eventos) -> dict:
    r = client.post(f"{API}/integracoes/webhooks", headers=h, json={"url": URL_WEBHOOK, "eventos": eventos})
    assert r.status_code == 201, r.text
    return r.json()


# ---- convite de indicação na tela final ---------------------------------------------------------

@pytest.mark.parametrize("uso,nota,aparece", [
    ("nps", 10, True), ("nps", 9, True), ("nps", 8, False), ("nps", 0, False),
    ("csat", 5, True), ("csat", 4, False), ("csat", 1, False),
])
def test_cartao_so_para_promotor_ou_csat_5(client, alfa, uso, nota, aparece):
    _, r = convite_respondido(client, alfa["h"], alfa["contato"]["id"], nota,
                              formulario=form_padrao(client, alfa["h"], uso))
    assert ("indicacao" in r) and (r["indicacao"] is not None) is aparece
    if aparece:
        assert r["indicacao"] == {
            "titulo": "Que bom que você gostou!",
            "texto": "Conhece outra empresa que ganharia com a Alfa Distribuidora? Indique e a gente entra em contato "
                     "com cuidado.",
            "recompensa": None,
        }
    assert r["titulo_final"]  # o resto da tela final continua igual


def test_cartao_desligado_conta_pausada_e_link_publico(client, alfa, dono):
    h = alfa["h"]
    # link público do formulário: não tem a quem atribuir
    nps = form_padrao(client, h)
    r = responder_link(client, nps["codigo_publico"], {nps["perguntas"][0]["id"]: 10})
    assert r.status_code == 201 and r.json().get("indicacao") is None
    # conta pausada (teste expirado): não liberada
    sql(dono, "update contas set situacao = 'teste_expirado' where id = :c", c=alfa["conta"]["id"])
    assert convite_respondido(client, h, alfa["contato"]["id"], 10)[1]["indicacao"] is None
    sql(dono, "update contas set situacao = 'ativa' where id = :c", c=alfa["conta"]["id"])
    assert convite_respondido(client, h, alfa["contato"]["id"], 10)[1]["indicacao"] is not None
    # indicações desligadas
    ligar_indicacoes(client, h, indicacoes_ativas=False)
    assert convite_respondido(client, h, alfa["contato"]["id"], 10)[1]["indicacao"] is None


def test_variaveis_do_cartao(client, alfa):
    h = alfa["h"]
    ligar_indicacoes(client, h, titulo_convite="Obrigado, {nome}!", texto_convite="Indique alguém para a {empresa}.",
                     recompensa="Se virar cliente da {empresa}, {nome} ganha 10% no próximo pedido.")
    _, r = convite_respondido(client, h, alfa["contato"]["id"], 10)
    assert r["indicacao"] == {"titulo": "Obrigado, Ana!", "texto": "Indique alguém para a Alfa Distribuidora.",
                              "recompensa": "Se virar cliente da Alfa Distribuidora, Ana ganha 10% no próximo pedido."}


# ---- indicação pela página pública --------------------------------------------------------------

def test_indicacao_publica_cria_com_responsavel_email_e_webhook(client, alfa, dono, destino):
    h = alfa["h"]
    _webhook(client, h, ["indicacao.criada"])
    token, _ = convite_respondido(client, h, alfa["contato"]["id"], 10)
    caixa_memoria.clear()
    r = indicar(client, token, nome="  João \x00da\nSilva ", email="Joao@PadariaReal.com.br",
                observacao="Compra toda semana.\r\nLigar de manhã.\x07", pode_identificar=False)
    assert r.status_code == 201, r.text
    assert r.json() == {"mensagem": "Obrigado pela indicação!"}

    lista = indicacoes(client, h)
    item, = lista["itens"]
    assert item["nome"] == "João da Silva" and item["empresa"] == "Padaria Real"
    assert item["telefone"] == "5511987654321" and item["email"] == "joao@padariareal.com.br"
    assert item["observacao"] == "Compra toda semana.\nLigar de manhã."
    assert item["origem"] == "pesquisa" and item["situacao"] == "nova" and item["pode_identificar"] is False
    assert item["indicador"] == {"contato": {"id": alfa["contato"]["id"], "nome": "Ana Souza"},
                                 "empresa": {"id": alfa["empresa"]["id"], "nome": "Mercado Bom Preço"}}
    assert item["responsavel"] == {"id": alfa["rita"]["id"], "nome": "Rita Gomes"}
    assert item["valor_mensal"] is None and item["motivo"] is None
    convite, resposta = sql(dono, "select convite_id, resposta_id from indicacoes")[0]
    assert convite is not None and resposta is not None

    m, = emails_para("rita@alfa.com.br")
    assert m.assunto == "Nova indicação de Mercado Bom Preço: João da Silva, Padaria Real"
    # etapa 5e: entra no registro de e-mails enviados da conta, sem o nome de quem foi indicado no assunto (excluir a
    # indicação a pedido da pessoa não pode deixar o nome dela no registro)
    assert sql(dono, "select tipo, destinatario, assunto, situacao from emails_enviados where tipo = 'indicacao'") == [
        ("indicacao", "rita@alfa.com.br", "Nova indicação", "enviado")]
    assert "Mercado Bom Preço (Ana Souza) indicou João da Silva (Padaria Real)." in m.texto
    assert "WhatsApp ou telefone: (11) 98765-4321" in m.texto and "E-mail: joao@padariareal.com.br" in m.texto
    assert "Observação: Compra toda semana." in m.texto
    assert "não diga à pessoa quem fez a indicação" in m.texto
    assert "Ver indicações no Toqqi: http://app.teste/crescimento/indicacoes" in m.texto
    assert len(caixa_memoria) == 1

    rec, = destino.recebidos
    corpo = json.loads(rec["corpo"])
    assert rec["cabecalhos"]["X-Toqqi-Evento"] == "indicacao.criada" and corpo["evento"] == "indicacao.criada"
    assert corpo["dados"]["id"] == item["id"] and corpo["dados"]["nome"] == "João da Silva"
    assert corpo["dados"]["responsavel"] == {"id": alfa["rita"]["id"], "nome": "Rita Gomes"}


@pytest.mark.parametrize("campos,erros", [
    ({"nome": "J"}, {"nome"}),
    ({"nome": "x" * 121}, {"nome"}),
    ({"nome": "  "}, {"nome"}),
    ({"empresa": "x" * 121}, {"empresa"}),
    ({"telefone": "(11) 1234-5678"}, {"telefone"}),  # fixo começando com 1
    ({"telefone": "(01) 98765-4321"}, {"telefone"}),
    ({"telefone": "12345"}, {"telefone"}),
    ({"email": "joao@"}, {"email"}),
    ({"telefone": None, "email": None}, {"telefone", "email"}),
    ({"telefone": "", "email": " "}, {"telefone", "email"}),
    ({"observacao": "x" * 501}, {"observacao"}),
    ({"confirmo": False}, {"confirmo"}),
    ({"confirmo": None}, {"confirmo"}),
])
def test_validacoes_da_indicacao_publica(client, alfa, dono, campos, erros):
    token, _ = convite_respondido(client, alfa["h"], alfa["contato"]["id"], 10)
    r = indicar(client, token, **campos)
    assert r.status_code == 422, r.text
    assert set(r.json()["erro"]["campos"]) == erros
    assert sql(dono, "select count(*) from indicacoes")[0][0] == 0


def test_sem_confirmacao_e_campos_opcionais(client, alfa):
    token, _ = convite_respondido(client, alfa["h"], alfa["contato"]["id"], 9)
    corpo = {"nome": "Bia", "email": "bia@x.com.br"}
    r = client.post(f"{API}/publico/convites/{token}/indicacoes", json=corpo)
    assert r.status_code == 422 and set(r.json()["erro"]["campos"]) == {"confirmo"}
    r = client.post(f"{API}/publico/convites/{token}/indicacoes", json={**corpo, "confirmo": True})
    assert r.status_code == 201
    item, = indicacoes(client, alfa["h"])["itens"]
    assert (item["empresa"], item["telefone"], item["observacao"], item["pode_identificar"]) == (None, None, None, True)
    # fixo também vale
    assert indicar(client, token, nome="Caio", telefone="(21) 3456-7890").status_code == 201
    assert indicacoes(client, alfa["h"])["itens"][0]["telefone"] == "552134567890"


def test_limite_de_3_por_convite(client, alfa):
    h = alfa["h"]
    token, _ = convite_respondido(client, h, alfa["contato"]["id"], 10)
    for i in range(3):
        assert indicar(client, token, telefone=f"(11) 98765-432{i}").status_code == 201
    r = indicar(client, token, telefone="(11) 98765-4329")
    assert r.status_code == 409
    assert r.json()["erro"] == {"codigo": "limite_indicacoes", "mensagem": "Você já fez 3 indicações. Obrigado!",
                                "campos": {}}
    # outro convite (outra pesquisa) tem o próprio limite
    outro, _ = convite_respondido(client, h, alfa["contato"]["id"], 10)
    assert indicar(client, outro, telefone="(11) 98765-4329").status_code == 201
    assert indicacoes(client, h)["total"] == 4


def test_repetida_aberta_responde_igual_sem_criar(client, alfa, destino):
    h = alfa["h"]
    _webhook(client, h, ["indicacao.criada"])
    t1, _ = convite_respondido(client, h, alfa["contato"]["id"], 10)
    t2, _ = convite_respondido(client, h, alfa["contato"]["id"], 10)
    t3, _ = convite_respondido(client, h, alfa["contato"]["id"], 10)
    assert indicar(client, t1, telefone="11987654321", email="joao@padaria.com.br").status_code == 201
    caixa_memoria.clear()
    # mesmo telefone (com e sem o nono dígito, com máscara) ou mesmo e-mail (maiúsculas) de uma indicação aberta
    for campos in ({"telefone": "(11) 98765-4321", "email": None}, {"telefone": None, "email": "JOAO@padaria.com.br"},
                   {"telefone": "+55 11 8765-4321", "email": None}):
        r = indicar(client, t2, nome="Outro Nome", **campos)
        assert r.status_code == 201 and r.json() == {"mensagem": "Obrigado pela indicação!"}
    assert indicacoes(client, h)["total"] == 1
    assert caixa_memoria == [] and len(destino.recebidos) == 1
    # a repetida gasta a vaga do convite como uma nova: a 4ª tentativa é 409, com número novo ou não
    r = indicar(client, t2, telefone="(11) 91111-1111")
    assert r.status_code == 409 and r.json()["erro"]["codigo"] == "limite_indicacoes"
    # depois de fechada (virou cliente), o mesmo telefone vira uma indicação nova
    primeira = indicacoes(client, h, busca="João")["itens"][-1]
    r = client.patch(f"{API}/crescimento/indicacoes/{primeira['id']}", headers=h,
                     json={"situacao": "cliente", "valor_mensal": "1200.00"})
    assert r.status_code == 200, r.text
    assert indicar(client, t3, telefone="(11) 98765-4321").status_code == 201
    assert indicacoes(client, h)["total"] == 2


def test_toda_tentativa_aceita_gasta_vaga(client, alfa, dono):
    """201/201/201/409 com números novos e com um número que já está no funil: a resposta não revela o funil. Erro de
    validação e convite sem direito não gastam vaga; a conta fica em `convites.indicacoes_feitas`."""
    h, c = alfa["h"], alfa["contato"]["id"]
    ja, _ = convite_respondido(client, h, c, 10)
    assert indicar(client, ja, telefone="(11) 98765-4321").status_code == 201  # o número já no funil
    novos, _ = convite_respondido(client, h, c, 10)
    repetidos, _ = convite_respondido(client, h, c, 10)
    assert indicar(client, novos, telefone="12345").status_code == 422  # não gasta vaga
    assert indicar(client, novos, telefone=None, email=None).status_code == 422
    seq_novos = [indicar(client, novos, telefone=f"(11) 97777-000{i}").status_code for i in range(4)]
    seq_repetidos = [indicar(client, repetidos, telefone="(11) 98765-4321").status_code for _ in range(4)]
    assert seq_novos == seq_repetidos == [201, 201, 201, 409]
    assert indicacoes(client, h)["total"] == 4  # 1 + 3 novas; as repetidas não criam
    assert sql(dono, "select indicacoes_feitas from convites order by id") == [(1,), (3,), (3,)]
    # sem direito (nota 8): 409 indisponível, sem gastar vaga
    sem, _ = convite_respondido(client, h, c, 8)
    assert indicar(client, sem).json()["erro"]["codigo"] == "indicacao_indisponivel"
    assert sql(dono, "select indicacoes_feitas from convites order by id desc limit 1") == [(0,)]


@pytest.mark.parametrize("caso", ["nota_8", "csat_4", "sem_resposta", "desligadas", "pausada"])
def test_indicacao_sem_direito(client, alfa, dono, caso):
    h, c = alfa["h"], alfa["contato"]["id"]
    if caso == "nota_8":
        token, _ = convite_respondido(client, h, c, 8)
    elif caso == "csat_4":
        token, _ = convite_respondido(client, h, c, 4, formulario=form_padrao(client, h, "csat"))
    elif caso == "sem_resposta":
        token = link_pesquisa(client, h, c, formulario_id=form_padrao(client, h)["id"])
    else:
        token, _ = convite_respondido(client, h, c, 10)
        if caso == "desligadas":
            ligar_indicacoes(client, h, indicacoes_ativas=False)
        else:
            sql(dono, "update contas set situacao = 'teste_expirado' where id = :c", c=alfa["conta"]["id"])
    r = indicar(client, token)
    assert r.status_code == 409
    assert r.json()["erro"]["codigo"] == "indicacao_indisponivel"
    assert sql(dono, "select count(*) from indicacoes")[0][0] == 0


def test_token_invalido(client, alfa):
    r = indicar(client, "token-que-nao-existe")
    assert r.status_code == 404 and r.json()["erro"]["codigo"] == "link_invalido"


@pytest.mark.parametrize("caso", ["resposta_arquivada", "formulario_desativado", "formulario_arquivado"])
def test_resposta_arquivada_ou_formulario_indisponivel(client, alfa, dono, caso):
    """Depois da resposta: arquivá-la ou tirar o formulário do ar fecha também o convite de indicação."""
    token, r = convite_respondido(client, alfa["h"], alfa["contato"]["id"], 10)
    assert r["indicacao"] is not None
    if caso == "resposta_arquivada":
        sql(dono, "update respostas set arquivada = true, arquivada_em = now()")
    else:
        coluna = "ativo = false" if caso == "formulario_desativado" else "arquivado = true"
        sql(dono, f"update formularios set {coluna} where id = (select formulario_id from convites)")
    r = indicar(client, token)
    assert r.status_code == 409 and r.json()["erro"]["codigo"] == "indicacao_indisponivel"
    assert sql(dono, "select count(*) from indicacoes")[0][0] == 0
    assert sql(dono, "select indicacoes_feitas from convites") == [(0,)]


@pytest.mark.parametrize("email", [5, 5.5, True, ["joao@padaria.com.br"], {"email": "joao@padaria.com.br"}])
def test_email_que_nao_e_texto(client, alfa, email):
    """Sem token válido nenhum, um e-mail que não é texto era AttributeError (500); agora é 422 no campo."""
    msg = "Informe um e-mail válido, como nome@empresa.com.br."
    assert indicar(client, "token-qualquer", email=email).json()["erro"]["campos"] == {"email": msg}
    token, _ = convite_respondido(client, alfa["h"], alfa["contato"]["id"], 10)
    r = indicar(client, token, email=email)
    assert r.status_code == 422 and r.json()["erro"]["campos"] == {"email": msg}
    # o mesmo tipo (EmailOpcional) nas rotas com login
    r = client.post(f"{API}/contatos", headers=alfa["h"], json={"nome": "Caio", "email": email})
    assert r.status_code == 422 and r.json()["erro"]["campos"] == {"email": msg}


def test_texto_enorme_recusado_antes_de_limpar(client, alfa, monkeypatch):
    """A limpeza percorre o texto inteiro: texto com mais de 4× o máximo é recusado antes (um POST com campos de 10 MB
    prendia a API). Até 4×, limpa e mede depois (espaços e controles que somem não contam)."""
    from toqqi.modulos.crescimento import esquemas

    limpos = []
    original = esquemas.limpar

    def medir(v, linhas=False):
        limpos.append(len(v))
        return original(v, linhas)

    monkeypatch.setattr(esquemas, "limpar", medir)
    h = alfa["h"]
    r = client.post(f"{API}/crescimento/indicacoes", headers=h, json={
        "nome": "x" * 1_000_000, "empresa": " " * 481, "observacao": "\x00" * 3_000_000, "email": "a@x.com.br"})
    assert r.status_code == 422
    assert r.json()["erro"]["campos"] == {"nome": "Use de 2 a 120 caracteres.",
                                          "empresa": "Use no máximo 120 caracteres.",
                                          "observacao": "Use no máximo 500 caracteres."}
    assert limpos == []  # nada disso passou pela limpeza
    # no limite de 4× (480 para o nome): limpa e vale pelo tamanho limpo
    r = client.post(f"{API}/crescimento/indicacoes", headers=h,
                    json={"nome": "Ana" + " " * 473 + "Lima", "email": "a@x.com.br"})
    assert r.status_code == 201 and r.json()["nome"] == "Ana Lima" and max(limpos) == 480
    r = client.post(f"{API}/crescimento/indicacoes", headers=h,
                    json={"nome": "Ana" + " " * 474 + "Lima", "email": "b@x.com.br"})
    assert r.status_code == 422 and set(r.json()["erro"]["campos"]) == {"nome"}


def test_corpo_grande_demais_na_indicacao_publica(client, alfa, dono):
    """A rota pública de indicação recusa corpo acima de 20 KB (413), pelo Content-Length ou contando o que chega."""
    token, _ = convite_respondido(client, alfa["h"], alfa["contato"]["id"], 10)
    erro = {"codigo": "pedido_grande_demais", "mensagem": "Os dados enviados passam do tamanho permitido.",
            "campos": {}}
    r = indicar(client, token, observacao="x" * 25_000)
    assert r.status_code == 413 and r.json()["erro"] == erro

    def em_pedacos():  # sem Content-Length (Transfer-Encoding: chunked)
        yield b'{"nome": "Joao Silva", "telefone": "11987654321", "confirmo": true, "observacao": "'
        for _ in range(25):
            yield b"x" * 1024
        yield b'"}'

    r = client.post(f"{API}/publico/convites/{token}/indicacoes", content=em_pedacos(),
                    headers={"Content-Type": "application/json"})
    assert r.status_code == 413 and r.json()["erro"] == erro
    assert sql(dono, "select count(*) from indicacoes")[0][0] == 0
    assert sql(dono, "select indicacoes_feitas from convites") == [(0,)]
    # perto do limite (e muito acima do que a tela manda) ainda é lido; a validação de sempre responde
    r = indicar(client, token, observacao="x" * 19_000)
    assert r.status_code == 422 and set(r.json()["erro"]["campos"]) == {"observacao"}
    assert indicar(client, token).status_code == 201
    # o limite é só desta rota: responder a pesquisa com um comentário de 25 KB não é 413
    f = form_padrao(client, alfa["h"])
    outro = link_pesquisa(client, alfa["h"], alfa["contato"]["id"], formulario_id=f["id"])
    r = client.post(f"{API}/publico/convites/{outro}/responder",
                    json={"respostas": {f["perguntas"][0]["id"]: 10, f["perguntas"][1]["id"]: "x" * 25_000}})
    assert r.status_code in (201, 422) and r.json().get("erro", {}).get("codigo") != "pedido_grande_demais"


def test_controles_bidirecionais_somem(client, alfa):
    """LRM, RLM, ALM, LRE…RLO e LRI…PDI disfarçam nomes no e-mail e no CSV: somem dos textos (o ZWJ dos emojis fica)."""
    h = alfa["h"]
    token, _ = convite_respondido(client, h, alfa["contato"]["id"], 10)
    caixa_memoria.clear()
    r = indicar(client, token, nome="Jo\u202eão\u200e Silva\u2069", empresa="\u2066Padaria\u200f Real\u061c",
                observacao="Linha\u202a 1\nLinha\u202d 2 👩\u200d💻")
    assert r.status_code == 201, r.text
    item, = indicacoes(client, h)["itens"]
    assert (item["nome"], item["empresa"], item["observacao"]) == ("João Silva", "Padaria Real",
                                                                   "Linha 1\nLinha 2 👩\u200d💻")
    m, = caixa_memoria
    csv_ = client.get(f"{API}/crescimento/indicacoes.csv", headers=h).content.decode("utf-8")
    for texto in (m.assunto, m.texto, csv_):
        assert not any(ch in texto for ch in "\u061c\u200e\u200f\u202a\u202b\u202c\u202d\u202e\u2066\u2067\u2068\u2069")
    assert "João Silva" in m.assunto and "João Silva" in csv_
    # só controles: vazio
    r = indicar(client, token, nome="\u202e\u200f\u2066", telefone="(11) 91111-2222")
    assert r.status_code == 422 and r.json()["erro"]["campos"] == {"nome": "Informe o nome de quem você indica."}


def test_ids_fora_do_bigint_e_busca_com_nul(client, alfa, lista):
    """Ids fora de 1..2^63−1 no caminho, no corpo e nos filtros são 422 de validação (antes: erro do banco, 500); a
    busca perde os controles (o NUL o banco nem aceita)."""
    h, grande = alfa["h"], 2**63
    for metodo, caminho, corpo, campo in (
        ("patch", f"/crescimento/indicacoes/{grande}", {"situacao": "nova"}, "indicacao_id"),
        ("patch", "/crescimento/indicacoes/0", {"situacao": "nova"}, "indicacao_id"),
        ("delete", f"/crescimento/indicacoes/{grande}", None, "indicacao_id"),
        ("patch", f"/crescimento/ofertas/{grande}", {"resultado": "recusou"}, "oferta_id"),
        ("post", "/crescimento/indicacoes", {"nome": "Rui", "email": "r@x.com.br", "responsavel_id": grande},
         "responsavel_id"),
        ("post", "/crescimento/indicacoes", {"nome": "Rui", "email": "r@x.com.br", "indicador_contato_id": grande},
         "indicador_contato_id"),
        ("post", "/crescimento/indicacoes", {"nome": "Rui", "email": "r@x.com.br", "indicador_empresa_id": -1},
         "indicador_empresa_id"),
        ("patch", f"/crescimento/indicacoes/{lista['joao']}", {"responsavel_id": grande}, "responsavel_id"),
        ("post", "/crescimento/ofertas", {"empresa_id": grande, "lista": "promotores", "texto": "Oi"}, "empresa_id"),
    ):
        kw = {"json": corpo} if corpo is not None else {}
        r = getattr(client, metodo)(f"{API}{caminho}", headers=h, **kw)
        assert r.status_code == 422, (metodo, caminho, r.text)
        assert set(r.json()["erro"]["campos"]) == {campo}, (metodo, caminho, r.text)
    for caminho, filtros, campo in (
        ("indicacoes", {"responsavel_id": grande}, "responsavel_id"),
        ("indicacoes.csv", {"responsavel_id": grande}, "responsavel_id"),
        ("indicacoes", {"responsavel_id": -1}, "responsavel_id"),
        ("oportunidades", {"grupo_id": grande}, "grupo_id"),
        ("oportunidades", {"grupo_id": 0}, "grupo_id"),
        ("oportunidades.csv", {"responsavel_id": grande}, "responsavel_id"),
    ):
        r = client.get(f"{API}/crescimento/{caminho}", headers=h, params=filtros)
        assert r.status_code == 422 and set(r.json()["erro"]["campos"]) == {campo}, (caminho, filtros, r.text)
    assert client.get(f"{API}/crescimento/oportunidades", headers=h, params={"responsavel_id": 0}).status_code == 200
    # busca com NUL e outros controles: limpa (e não erro do banco)
    assert [x["id"] for x in indicacoes(client, h, busca="joao\x00")["itens"]] == [lista["joao"]]
    assert indicacoes(client, h, busca="\x00\x07")["total"] == 5  # só controles = sem busca
    r = client.get(f"{API}/crescimento/indicacoes.csv", headers=h, params={"busca": "maria\x00"})
    assert r.status_code == 200 and "Maria Antônia" in r.content.decode("utf-8")
    assert client.get(f"{API}/crescimento/indicacoes", headers=h, params={"busca": "x" * 101}).status_code == 422


def test_consultas_com_a_conta_explicita(client, alfa):
    """Além do RLS, a conferência de repetida e a busca dos administradores do aviso filtram a conta: mesmo numa
    transação que enxerga todas as contas (modo sistema), nada vem da outra."""
    from toqqi.core.db import modo_sistema
    from toqqi.modelos import Indicacao
    from toqqi.modulos.crescimento import indicacoes as servico

    b = conta_pronta(client, "bia@beta.com.br", empresa="Beta")
    r = client.post(f"{API}/crescimento/indicacoes", headers=b["h"], json={"nome": "Na Beta",
                                                                           "telefone": "(11) 98765-4321"})
    assert r.status_code == 201
    r = client.post(f"{API}/crescimento/indicacoes", headers=alfa["h"], json={"nome": "Na Alfa",
                                                                              "email": "na@alfa.com.br"})
    assert r.status_code == 201 and r.json()["responsavel"] is None
    with modo_sistema() as s:
        assert servico._repetida_aberta(s, b["conta"]["id"], "5511987654321", None)
        assert not servico._repetida_aberta(s, alfa["conta"]["id"], "5511987654321", None)
        assert servico._repetida_aberta(s, alfa["conta"]["id"], None, "na@alfa.com.br")
        with servico.coletar_avisos() as avisos:
            servico._coletar_aviso(s, s.get(Indicacao, r.json()["id"]))
    assert [a.para for a in avisos] == ["ana@alfa.com.br"]  # o administrador da Beta não recebe


def test_sem_responsavel_avisa_os_administradores_confirmados(client, alfa, dono):
    h = alfa["h"]
    sem = criar_empresa(client, h, "Sem Dono")
    c = criar_contato(client, h, nome="Caio", email="caio@semdono.com.br", empresa_id=sem["id"])
    membro(client, h, "beto@alfa.com.br", "admin")
    membro(client, h, "gil@alfa.com.br", "gestor")
    sql(dono, "update usuarios set email_confirmado = true where email = 'beto@alfa.com.br'")
    sql(dono, "update usuarios set email_confirmado = false where email = 'gil@alfa.com.br'")
    membro(client, h, "dani@alfa.com.br", "admin")
    sql(dono, "update usuarios set email_confirmado = false where email = 'dani@alfa.com.br'")
    token, _ = convite_respondido(client, h, c["id"], 10)
    caixa_memoria.clear()
    assert indicar(client, token).status_code == 201
    assert sorted(m.para for m in caixa_memoria) == ["ana@alfa.com.br", "beto@alfa.com.br"]
    assert all(m.assunto == "Nova indicação de Sem Dono: João Silva, Padaria Real" for m in caixa_memoria)
    assert "A indicação está sem responsável" in caixa_memoria[0].texto
    assert indicacoes(client, h)["itens"][0]["responsavel"] is None
    # responsável sem e-mail: também vai para os administradores
    beto = criar_responsavel(client, h, "Beto Lima")
    client.patch(f"{API}/empresas/{sem['id']}", headers=h, json={"responsavel_id": beto["id"]})
    token, _ = convite_respondido(client, h, c["id"], 10)
    caixa_memoria.clear()
    assert indicar(client, token, telefone="(11) 92222-3333").status_code == 201
    assert sorted(m.para for m in caixa_memoria) == ["ana@alfa.com.br", "beto@alfa.com.br"]
    assert indicacoes(client, h)["itens"][0]["responsavel"] == {"id": beto["id"], "nome": "Beto Lima"}


def test_nada_vai_para_o_log(client, alfa, caplog, capsys, monkeypatch):
    """Nem com o provedor de e-mail falhando nem com o `console` em produção (que não conta como configurado)."""
    from toqqi.core.config import config
    from toqqi.core.email import Memoria

    def falhar(self, m):
        raise RuntimeError("provedor fora do ar")

    h = alfa["h"]
    t1, _ = convite_respondido(client, h, alfa["contato"]["id"], 10)
    t2, _ = convite_respondido(client, h, alfa["contato"]["id"], 10)
    capsys.readouterr()
    with caplog.at_level(logging.DEBUG):
        monkeypatch.setattr(Memoria, "enviar", falhar)
        assert indicar(client, t1, nome="Zuleica Sigilosa", email="zuleica@segredo.com.br",
                       observacao="Observação sigilosa").status_code == 201
        assert indicar(client, t1, nome="Z", email="zuleica@segredo").status_code == 422
        monkeypatch.setattr(config(), "EMAIL_PROVIDER", "console")
        monkeypatch.setattr(config(), "AMBIENTE", "producao")
        assert indicar(client, t2, nome="Zuleica Sigilosa", telefone="(31) 99876-5432",
                       observacao="Observação sigilosa").status_code == 201
    saida = caplog.text + capsys.readouterr().out
    assert "Falha ao enviar e-mail 'Nova indicação'" in caplog.text
    assert "aviso(s) de indicação não enviado(s)" in caplog.text
    for dado in ("Zuleica", "zuleica@segredo", "sigilosa", "98765", "99876"):
        assert dado not in saida


def test_aviso_so_depois_do_commit(client, alfa, monkeypatch):
    """Se a gravação falha depois de decidir o aviso, nada é gravado e o e-mail não sai."""
    from toqqi.modulos.crescimento import indicacoes as servico

    def falhar(s, evento, dados):
        raise RuntimeError("falha depois do aviso")

    token, _ = convite_respondido(client, alfa["h"], alfa["contato"]["id"], 10)
    monkeypatch.setattr(servico, "enfileirar", falhar)
    caixa_memoria.clear()
    with pytest.raises(RuntimeError):
        indicar(client, token)
    assert caixa_memoria == []
    assert indicacoes(client, alfa["h"])["total"] == 0


def test_indicacao_de_outra_conta_nao_aparece(client, alfa):
    token, _ = convite_respondido(client, alfa["h"], alfa["contato"]["id"], 10)
    assert indicar(client, token).status_code == 201
    b = conta_pronta(client, "bia@beta.com.br", empresa="Beta")
    assert indicacoes(client, b["h"])["total"] == 0
    i = indicacoes(client, alfa["h"])["itens"][0]
    assert client.patch(f"{API}/crescimento/indicacoes/{i['id']}", headers=b["h"],
                        json={"situacao": "em_contato"}).status_code == 404
    assert client.delete(f"{API}/crescimento/indicacoes/{i['id']}", headers=b["h"]).status_code == 404
    # o mesmo telefone na outra conta não é repetida
    ligar_indicacoes(client, b["h"])
    cb = criar_contato(client, b["h"], nome="Bruno", email="bruno@cliente.com.br")
    tb, _ = convite_respondido(client, b["h"], cb["id"], 10)
    assert indicar(client, tb).status_code == 201
    assert indicacoes(client, b["h"])["total"] == 1


# ---- lista, filtros, resumo e CSV --------------------------------------------------------------

@pytest.fixture
def lista(client, alfa, dono):
    """Cinco indicações à mão, com datas, situações e responsáveis diferentes."""
    h = alfa["h"]
    beto = criar_responsavel(client, h, "Beto Lima")
    hoje = relogio.hoje()

    def nova(nome, dias, **campos) -> dict:
        corpo = {"nome": nome, "telefone": None, "email": None, **campos}
        r = client.post(f"{API}/crescimento/indicacoes", headers=h, json=corpo)
        assert r.status_code == 201, r.text
        quando = relogio.agora() - timedelta(days=dias)
        sql(dono, "update indicacoes set criada_em = :q where id = :i", q=quando, i=r.json()["id"])
        return r.json()

    itens = {
        "joao": nova("João Conceição", 1, empresa="Padaria Real", telefone="11987654321",
                     indicador_empresa_id=alfa["empresa"]["id"]),
        "maria": nova("Maria Antônia", 5, empresa="Açougue São José", email="maria@acougue.com.br",
                      responsavel_id=beto["id"]),
        "pedro": nova("Pedro Lima", 20, email="pedro@x.com.br", indicador_empresa_id=alfa["empresa"]["id"]),
        "lia": nova("Lia Duarte", 40, telefone="21987650000", responsavel_id=beto["id"]),
        "velha": nova("Velha Indicação", 200, email="velha@x.com.br"),
    }

    def patch(nome, corpo):
        return client.patch(f"{API}/crescimento/indicacoes/{itens[nome]['id']}", headers=h, json=corpo)

    assert patch("maria", {"situacao": "cliente", "valor_mensal": "1500.50"}).status_code == 200
    assert patch("pedro", {"situacao": "em_contato"}).status_code == 200
    assert patch("lia", {"situacao": "cliente", "valor_mensal": 800}).status_code == 200
    assert patch("velha", {"situacao": "nao_avancou", "motivo": "Já tem fornecedor"}).status_code == 200
    return {"beto": beto, "hoje": hoje, **{k: v["id"] for k, v in itens.items()}}


def _ids(r: dict) -> list[int]:
    return [x["id"] for x in r["itens"]]


def test_lista_filtros_e_resumo(client, alfa, lista):
    h, hoje = alfa["h"], lista["hoje"]
    tudo = indicacoes(client, h)
    assert _ids(tudo) == [lista[k] for k in ("joao", "maria", "pedro", "lia", "velha")]  # mais novas primeiro
    assert tudo["total"] == 5 and (tudo["pagina"], tudo["por_pagina"]) == (1, 200)
    assert tudo["resumo"] == {"novas": 1, "em_contato": 1, "clientes": 2, "nao_avancou": 1, "receita_mensal": 2300.5}
    joao = tudo["itens"][0]
    assert joao["responsavel"] == {"id": alfa["rita"]["id"], "nome": "Rita Gomes"}  # o da empresa de quem indicou
    assert joao["indicador"] == {"contato": None, "empresa": {"id": alfa["empresa"]["id"], "nome": "Mercado Bom Preço"}}

    assert _ids(indicacoes(client, h, situacao="cliente")) == [lista["maria"], lista["lia"]]
    r = indicacoes(client, h, responsavel_id=lista["beto"]["id"])
    assert _ids(r) == [lista["maria"], lista["lia"]]
    assert r["resumo"] == {"novas": 0, "em_contato": 0, "clientes": 2, "nao_avancou": 0, "receita_mensal": 2300.5}
    assert _ids(indicacoes(client, h, responsavel_id=0)) == [lista["velha"]]
    # período (dias de São Paulo): os últimos 30 dias; o resumo segue o período, não a situação nem a busca
    r = indicacoes(client, h, de=(hoje - timedelta(days=29)).isoformat(), ate=hoje.isoformat(), situacao="nova")
    assert _ids(r) == [lista["joao"]]
    assert r["resumo"] == {"novas": 1, "em_contato": 1, "clientes": 1, "nao_avancou": 0, "receita_mensal": 1500.5}
    # busca sem acento e sem diferenciar maiúsculas: nome, empresa, e-mail e telefone
    assert _ids(indicacoes(client, h, busca="joao conceicao")) == [lista["joao"]]
    assert _ids(indicacoes(client, h, busca="ACOUGUE sao")) == [lista["maria"]]
    assert _ids(indicacoes(client, h, busca="maria@")) == [lista["maria"]]
    assert _ids(indicacoes(client, h, busca="9876-5432")) == [lista["joao"]]
    assert _ids(indicacoes(client, h, busca="%")) == []
    # paginação
    r = client.get(f"{API}/crescimento/indicacoes", headers=h, params={"por_pagina": 2, "pagina": 2}).json()
    assert _ids(r) == [lista["pedro"], lista["lia"]] and r["total"] == 5
    # período invertido
    r = client.get(f"{API}/crescimento/indicacoes", headers=h, params={"de": "2026-10-10", "ate": "2026-10-01"})
    assert r.status_code == 422


def test_patch_regras_de_valor_e_motivo(client, alfa, lista, dono, destino):
    h = alfa["h"]
    w = _webhook(client, h, ["indicacao.atualizada"])
    url = f"{API}/crescimento/indicacoes/{lista['joao']}"
    # 'cliente' pede o valor
    r = client.patch(url, headers=h, json={"situacao": "cliente"})
    assert r.status_code == 422 and set(r.json()["erro"]["campos"]) == {"valor_mensal"}
    r = client.patch(url, headers=h, json={"situacao": "cliente", "valor_mensal": -1})
    assert r.status_code == 422 and set(r.json()["erro"]["campos"]) == {"valor_mensal"}
    r = client.patch(url, headers=h, json={"situacao": "cliente", "valor_mensal": "2.000,00"})
    assert r.status_code == 422
    r = client.patch(url, headers=h, json={"situacao": "cliente", "valor_mensal": 0})
    assert r.status_code == 200 and (r.json()["situacao"], r.json()["valor_mensal"]) == ("cliente", 0)
    r = client.patch(url, headers=h, json={"valor_mensal": "990.90"})  # só o valor de quem já é cliente
    assert r.status_code == 200 and r.json()["valor_mensal"] == 990.9
    r = client.patch(url, headers=h, json={"valor_mensal": None})
    assert r.status_code == 422
    # outra situação limpa o valor; motivo só em 'nao_avancou'
    r = client.patch(url, headers=h, json={"situacao": "em_contato", "motivo": "ignorado"})
    assert r.status_code == 200 and (r.json()["valor_mensal"], r.json()["motivo"]) == (None, None)
    r = client.patch(url, headers=h, json={"situacao": "nao_avancou", "motivo": " Preço\nalto ", "valor_mensal": 5})
    assert r.status_code == 200 and (r.json()["motivo"], r.json()["valor_mensal"]) == ("Preço\nalto", None)
    r = client.patch(url, headers=h, json={"motivo": "x" * 301})
    assert r.status_code == 422 and set(r.json()["erro"]["campos"]) == {"motivo"}
    r = client.patch(url, headers=h, json={"situacao": "nova"})
    assert r.status_code == 200 and r.json()["motivo"] is None
    r = client.patch(url, headers=h, json={"situacao": "perdida"})
    assert r.status_code == 422
    # null na situação não muda; responsável troca e limpa
    r = client.patch(url, headers=h, json={"situacao": None, "responsavel_id": lista["beto"]["id"]})
    assert r.status_code == 200 and r.json()["situacao"] == "nova"
    assert r.json()["responsavel"] == {"id": lista["beto"]["id"], "nome": "Beto Lima"}
    assert client.patch(url, headers=h, json={"responsavel_id": None}).json()["responsavel"] is None
    r = client.patch(url, headers=h, json={"responsavel_id": 999999})
    assert r.status_code == 422 and set(r.json()["erro"]["campos"]) == {"responsavel_id"}
    assert client.patch(f"{API}/crescimento/indicacoes/999999", headers=h, json={}).status_code == 404

    # webhook só quando a situação muda (cliente, valor, em_contato, nao_avancou, nova = 4 mudanças)
    eventos = [json.loads(x["corpo"]) for x in destino.recebidos]
    assert [e["evento"] for e in eventos] == ["indicacao.atualizada"] * 4
    assert [(e["dados"]["situacao_anterior"], e["dados"]["situacao"]) for e in eventos] == [
        ("nova", "cliente"), ("cliente", "em_contato"), ("em_contato", "nao_avancou"), ("nao_avancou", "nova")]
    assert w["eventos"] == ["indicacao.atualizada"]
    # auditoria da situação, sem dados pessoais
    detalhes = [d for (d,) in sql(dono, "select detalhe from auditoria where evento = 'indicacao_atualizada' "
                                        "and detalhe->>'indicacao_id' = :i order by id", i=str(lista["joao"]))]
    assert [(d["de"], d["para"]) for d in detalhes] == [
        ("nova", "cliente"), ("cliente", "em_contato"), ("em_contato", "nao_avancou"), ("nao_avancou", "nova")]
    assert all(set(d) == {"indicacao_id", "de", "para"} for d in detalhes)
    usuario, = {u for (u,) in sql(dono, "select atualizada_por from indicacoes where id = :i", i=lista["joao"])}
    assert usuario == alfa["usuario"]["id"]


def test_excluir_a_pedido_da_pessoa(client, alfa, lista, dono):
    h = alfa["h"]
    r = client.delete(f"{API}/crescimento/indicacoes/{lista['maria']}", headers=h)
    assert r.status_code == 204 and r.content == b""
    assert client.delete(f"{API}/crescimento/indicacoes/{lista['maria']}", headers=h).status_code == 404
    assert lista["maria"] not in _ids(indicacoes(client, h))
    detalhe, = [d for (d,) in sql(dono, "select detalhe from auditoria where evento = 'indicacao_excluida'")]
    assert detalhe == {"indicacao_id": lista["maria"], "origem": "manual", "situacao": "cliente"}
    texto = json.dumps(sql(dono, "select evento, detalhe from auditoria where evento like 'indicacao%'"),
                       default=str, ensure_ascii=False)
    for dado in ("Maria", "maria@", "Açougue", "98765", "Já tem fornecedor"):
        assert dado not in texto


def test_excluir_esquece_as_entregas_de_webhook(client, alfa, dono, destino):
    """LGPD: na transação da exclusão, as entregas pendentes da indicação somem (não saem mais) e as já terminadas
    (entregue e desistida) ficam no histórico com o corpo sem os dados da pessoa; as de outra indicação não mudam."""
    from toqqi.modulos.integracoes import webhooks

    h = alfa["h"]
    w = _webhook(client, h, ["indicacao.criada", "indicacao.atualizada"])

    def nova(nome, email, telefone) -> int:
        r = client.post(f"{API}/crescimento/indicacoes", headers=h, json={
            "nome": nome, "email": email, "telefone": telefone, "observacao": f"Observação de {nome}"})
        assert r.status_code == 201, r.text
        return r.json()["id"]

    def mudar(i, situacao):
        r = client.patch(f"{API}/crescimento/indicacoes/{i}", headers=h, json={"situacao": situacao})
        assert r.status_code == 200, r.text

    x = nova("Zuleica Sigilosa", "zuleica@segredo.com.br", "(31) 99876-5432")  # entregue
    destino.status = 500
    mudar(x, "em_contato")  # o destino falhou: pendente...
    sql(dono, "update webhook_entregas set status = 'falhou' where evento = 'indicacao.atualizada'")  # ...desistida
    mudar(x, "nova")  # pendente
    y = nova("Yara Outra", "yara@outra.com.br", "(21) 91234-5678")  # pendente, de outra indicação
    da = "select status, corpo from webhook_entregas where corpo->'dados'->>'id' = :i order by criado_em"
    assert [st for st, _ in sql(dono, da, i=str(x))] == ["ok", "falhou", "pendente"]
    de_y = sql(dono, da, i=str(y))

    assert client.delete(f"{API}/crescimento/indicacoes/{x}", headers=h).status_code == 204
    restantes = sql(dono, da, i=str(x))
    assert [st for st, _ in restantes] == ["ok", "falhou"]  # a pendente sumiu; o histórico fica
    for _, corpo in restantes:
        assert set(corpo) == {"id", "evento", "criado_em", "conta", "dados"}
        assert corpo["dados"] == {"id": x, "excluido": True} and corpo["evento"].startswith("indicacao.")
    assert sql(dono, da, i=str(y)) == de_y  # a outra indicação não muda
    texto = json.dumps([c for (c,) in sql(dono, "select corpo from webhook_entregas")], ensure_ascii=False)
    for dado in ("Zuleica", "zuleica@segredo", "99876", "Observação de Zuleica"):
        assert dado not in texto
    assert "Yara" in texto
    historico = client.get(f"{API}/integracoes/webhooks/{w['id']}/entregas", headers=h).json()
    assert len(historico) == 3  # as duas terminadas da excluída e a pendente da outra

    # na próxima rodada só sai a da outra indicação
    destino.status, enviados = 200, len(destino.recebidos)
    sql(dono, "update webhook_entregas set proxima_tentativa = :t where status = 'pendente'",
        t=relogio.agora() - timedelta(minutes=1))
    assert webhooks.entregar_devidas() == {"entregues": 1, "falharam": 0}
    novo, = destino.recebidos[enviados:]
    assert json.loads(novo["corpo"])["dados"]["id"] == y


def test_entrega_esquecida_durante_a_tentativa(client, alfa, dono, destino, monkeypatch, caplog):
    """A exclusão pode apagar uma entrega pendente enquanto o POST dela está em andamento: a tentativa termina sem
    gravar o resultado (e sem erro no log)."""
    from toqqi.core import rede

    _webhook(client, alfa["h"], ["indicacao.criada"])

    def apagar_no_meio(*args, **kwargs):
        sql(dono, "delete from webhook_entregas")  # como `esquecer_entregas` numa exclusão ao mesmo tempo
        return destino(*args, **kwargs)

    monkeypatch.setattr(rede, "enviar_post", apagar_no_meio)
    with caplog.at_level(logging.INFO):
        r = client.post(f"{API}/crescimento/indicacoes", headers=alfa["h"],
                        json={"nome": "Rui Prado", "email": "rui@x.com.br"})
    assert r.status_code == 201 and len(destino.recebidos) == 1
    assert "Falha ao entregar" not in caplog.text
    assert sql(dono, "select count(*) from webhook_entregas")[0][0] == 0


def test_csv_com_os_filtros_da_lista(client, alfa, lista):
    h = alfa["h"]
    r = client.get(f"{API}/crescimento/indicacoes.csv", headers=h, params={"situacao": "cliente"})
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/csv")
    assert r.headers["content-disposition"] == f'attachment; filename="indicacoes-{lista["hoje"].isoformat()}.csv"'
    texto = r.content.decode("utf-8")
    assert texto.startswith("﻿")
    linhas = list(csv.reader(io.StringIO(texto.lstrip("﻿")), delimiter=";"))
    assert linhas[0] == ["Data", "Nome", "Empresa", "Telefone", "E-mail", "Observação", "Indicada por (empresa)",
                         "Indicada por (contato)", "Pode dizer quem indicou", "Origem", "Responsável", "Situação",
                         "Valor mensal", "Motivo", "Atualizada em"]
    assert [x[1] for x in linhas[1:]] == ["Maria Antônia", "Lia Duarte"]
    maria, lia = linhas[1:]
    assert maria[2] == "Açougue São José" and maria[4] == "maria@acougue.com.br" and maria[12] == "1500,50"
    assert maria[9] == "Registrada à mão" and maria[10] == "Beto Lima" and maria[11] == "Virou cliente"
    assert lia[3] == "(21) 98765-0000" and lia[12] == "800,00"
    tudo = client.get(f"{API}/crescimento/indicacoes.csv", headers=h).content.decode("utf-8")
    assert len(list(csv.reader(io.StringIO(tudo.lstrip("﻿")), delimiter=";"))) == 6


def test_csv_protege_contra_formula(client, alfa):
    h = alfa["h"]
    r = client.post(f"{API}/crescimento/indicacoes", headers=h,
                    json={"nome": "=HYPERLINK(1)", "empresa": "+Empresa", "email": "x@x.com.br"})
    assert r.status_code == 201
    linha = list(csv.reader(io.StringIO(client.get(f"{API}/crescimento/indicacoes.csv", headers=h)
                                        .content.decode("utf-8").lstrip("﻿")), delimiter=";"))[1]
    assert linha[1] == "'=HYPERLINK(1)" and linha[2] == "'+Empresa"


# ---- indicação registrada à mão ------------------------------------------------------------------

def test_registrar_a_mao(client, alfa, dono, destino):
    h = alfa["h"]
    _webhook(client, h, ["indicacao.criada", "indicacao.atualizada"])
    caixa_memoria.clear()
    # pelo contato: a empresa é a do contato e o responsável, o da empresa
    r = client.post(f"{API}/crescimento/indicacoes", headers=h, json={
        "nome": "Rui Prado", "empresa": "Prado & Filhos", "telefone": "(11) 3333-4444",
        "indicador_contato_id": alfa["contato"]["id"], "observacao": "Veio por telefone"})
    assert r.status_code == 201, r.text
    item = r.json()
    assert item["origem"] == "manual" and item["situacao"] == "nova" and item["telefone"] == "551133334444"
    assert item["indicador"] == {"contato": {"id": alfa["contato"]["id"], "nome": "Ana Souza"},
                                 "empresa": {"id": alfa["empresa"]["id"], "nome": "Mercado Bom Preço"}}
    assert item["responsavel"] == {"id": alfa["rita"]["id"], "nome": "Rita Gomes"} and item["pode_identificar"]
    assert caixa_memoria == []  # quem registrou já sabe: sem e-mail
    corpo, = [json.loads(x["corpo"]) for x in destino.recebidos]
    assert corpo["evento"] == "indicacao.criada" and corpo["dados"]["origem"] == "manual"
    detalhe, usuario = sql(dono, "select detalhe, usuario_id from auditoria where evento = 'indicacao_registrada'")[0]
    assert detalhe == {"indicacao_id": item["id"]} and usuario == alfa["usuario"]["id"]
    assert sql(dono, "select criada_por from indicacoes where id = :i", i=item["id"]) == [(alfa["usuario"]["id"],)]
    # responsável escolhido vale mais que o da empresa; sem indicador nenhum também pode
    beto = criar_responsavel(client, h, "Beto Lima")
    r = client.post(f"{API}/crescimento/indicacoes", headers=h, json={
        "nome": "Sem Indicador", "email": "sem@x.com.br", "indicador_empresa_id": alfa["empresa"]["id"],
        "responsavel_id": beto["id"], "pode_identificar": False})
    assert r.status_code == 201 and r.json()["responsavel"]["id"] == beto["id"] and not r.json()["pode_identificar"]
    r = client.post(f"{API}/crescimento/indicacoes", headers=h, json={"nome": "Só Nome", "email": "so@x.com.br"})
    assert r.status_code == 201 and r.json()["indicador"] == {"contato": None, "empresa": None}
    assert r.json()["responsavel"] is None


@pytest.mark.parametrize("corpo,erros", [
    ({"nome": "Rui"}, {"telefone", "email"}),
    ({"nome": "R", "email": "r@x.com.br"}, {"nome"}),
    ({"nome": "Rui", "email": "r@x.com.br", "indicador_contato_id": 999999}, {"indicador_contato_id"}),
    ({"nome": "Rui", "email": "r@x.com.br", "indicador_empresa_id": 999999}, {"indicador_empresa_id"}),
    ({"nome": "Rui", "email": "r@x.com.br", "responsavel_id": 999999}, {"responsavel_id"}),
    ({"nome": "Rui", "telefone": "123"}, {"telefone"}),
])
def test_registrar_a_mao_validacoes(client, alfa, corpo, erros):
    r = client.post(f"{API}/crescimento/indicacoes", headers=alfa["h"], json=corpo)
    assert r.status_code == 422 and set(r.json()["erro"]["campos"]) == erros, r.text


def test_apagar_contato_empresa_e_resposta_nao_apaga_a_indicacao(client, alfa, dono):
    h = alfa["h"]
    token, _ = convite_respondido(client, h, alfa["contato"]["id"], 10)
    assert indicar(client, token).status_code == 201
    sql(dono, "delete from respostas")
    sql(dono, "delete from convites")
    sql(dono, "delete from contatos")
    sql(dono, "delete from empresas")
    item, = indicacoes(client, h)["itens"]
    assert item["nome"] == "João Silva" and item["indicador"] == {"contato": None, "empresa": None}
    assert sql(dono, "select convite_id, resposta_id, indicador_contato_id, indicador_empresa_id from indicacoes") \
        == [(None, None, None, None)]

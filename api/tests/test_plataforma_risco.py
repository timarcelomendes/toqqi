"""Risco das contas em Plataforma › Contas (docs/api-plataforma-risco.md): os sinais, os pontos, os níveis e as contas
da equipe sem nota."""
import pytest
from util import API, cadastrar, conta_pronta, criar_form, form_padrao, sql, superadmin

from toqqi.core.email import MSG_ENDERECO
from toqqi.modulos.plataforma import risco
from toqqi.modulos.whatsapp.graph import MSG_NUMERO


def _contas(client, h) -> dict:
    r = client.get(f"{API}/plataforma/contas", headers=h)
    assert r.status_code == 200, r.text
    return {c["nome"]: c for c in r.json()}


def _sinais(conta: dict) -> dict:
    return {s["tipo"]: s for s in conta["risco"]["sinais"]}


@pytest.fixture
def root(client):
    return superadmin(client)


# ---- regras puras --------------------------------------------------------------

@pytest.mark.parametrize(("nome", "esperado"), [
    ("asdf", True), ("Teste", True), ("EMPRESA TESTE", True), ("Empresa", True), ("xx", True), ("1234", True),
    ("zzzz", True), ("Minha empresa", True), ("Test Corp", True),
    ("Distribuidora Aurora", False), ("Padaria do João", False), ("Testa & Filhos", False), ("Abcam Brasil", False),
])
def test_nome_de_teste(nome, esperado):
    assert risco.nome_de_teste(nome) is esperado


def test_nome_normal_e_dominio_temporario():
    assert risco.nome_normal("Distribuidora  Aurora LTDA.") == risco.nome_normal("distribuidora aurora") == (
        "distribuidora aurora")
    assert risco.nome_normal("Café São Jorge S/A") == "cafe sao jorge"
    assert risco.dominio_temporario("mailinator.com") and risco.dominio_temporario("abc.mailinator.com")
    assert not risco.dominio_temporario("notmailinator.com") and not risco.dominio_temporario("gmail.com")


def test_trecho_sensivel():
    aberta = lambda titulo, **extra: {"tipo": "texto_curto", "titulo": titulo, **extra}  # noqa: E731
    assert risco.trecho_sensivel([aberta("Digite a senha do seu banco")]) == ("senha", "Digite a senha do seu banco")
    assert risco.trecho_sensivel([{"tipo": "comentario", "titulo": "Confirme",
                                   "descricao": "Informe o número do cartão"}]) == ("cartao", "Confirme")
    assert risco.trecho_sensivel([aberta("Seus dados bancários")])[0] == "banco"
    assert risco.trecho_sensivel([aberta("Qual o código de verificação que você recebeu?")])[0] == "codigo"
    # nota, escolha ou sim/não falando de senha não pedem a senha
    assert risco.trecho_sensivel([{"tipo": "nps", "titulo": "Foi fácil trocar a senha?"},
                                  {"tipo": "sim_nao", "titulo": "Você lembra a senha?"}]) is None
    # bloco de texto conta quando o formulário tem uma pergunta aberta para a pessoa digitar
    bloco = {"tipo": "conteudo", "html": "<p>Para confirmar, informe sua <b>senha</b> abaixo.</p>"}
    assert risco.trecho_sensivel([bloco, aberta("Resposta")]) == ("senha", "Para confirmar, informe sua senha abaixo.")
    assert risco.trecho_sensivel([bloco, {"tipo": "nps", "titulo": "Nota"}]) is None
    longo = risco.trecho_sensivel([aberta("Senha " + "x" * 200)])[1]
    assert len(longo) == risco.MAX_TRECHO and longo.endswith("…")
    assert risco.trecho_sensivel([aberta("O que achou do atendimento?")]) is None


# ---- pela API --------------------------------------------------------------------

def test_conta_limpa_e_conta_da_equipe(client, root):
    conta_pronta(client, "ana@alfa.com.br", empresa="Alfa Distribuidora")
    contas = _contas(client, root["h"])
    assert contas["Alfa Distribuidora"]["risco"] == {"pontos": 0, "nivel": "baixo", "sinais": []}
    assert contas["Toqqi"]["risco"] is None  # a conta da equipe não leva nota


def test_cadastro_suspeito(client, root, dono):
    cadastrar(client, "zz@mailinator.com", empresa="asdf")  # nunca confirmou o e-mail
    sql(dono, "update contas set criada_em = now() - interval '3 days' where nome = 'asdf'")
    cadastrar(client, "novo@yopmail.com", empresa="Mercado Bom")  # cadastro de agora: ainda pode confirmar
    conta_pronta(client, "joao@gmail.com", empresa="Padaria do João")
    contas = _contas(client, root["h"])
    asdf = contas["asdf"]["risco"]
    assert (asdf["pontos"], asdf["nivel"]) == (70, "alto")
    assert [(s["tipo"], s["pontos"]) for s in asdf["sinais"]] == [
        ("email_temporario", 40), ("email_nao_confirmado", 15), ("nome_de_teste", 15)]
    assert asdf["sinais"][0]["dominio"] == "mailinator.com" and asdf["sinais"][1]["dias"] == 3
    novo = contas["Mercado Bom"]["risco"]
    assert (novo["pontos"], novo["nivel"], [s["tipo"] for s in novo["sinais"]]) == (40, "medio", ["email_temporario"])
    joao = contas["Padaria do João"]["risco"]
    assert joao == {"pontos": 10, "nivel": "baixo",
                    "sinais": [{"tipo": "email_pessoal", "pontos": 10, "dominio": "gmail.com"}]}


def test_repetidos_entre_contas(client, root, dono):
    a = conta_pronta(client, "ana@aurora.com.br", empresa="Distribuidora Aurora Ltda")
    b = conta_pronta(client, "bia@aurora.com.br", empresa="Distribuidora Aurora")
    conta_pronta(client, "caio@outra.com.br", empresa="Outra")
    for d in (a, b, root):  # a conta da equipe com os mesmos dados não entra na comparação
        sql(dono, "update contas set documento = '12345678000190', telefone = '5511987654321' where id = :c",
            c=d["conta"]["id"])
    contas = _contas(client, root["h"])
    for nome, outra in (("Distribuidora Aurora Ltda", b), ("Distribuidora Aurora", a)):
        r = contas[nome]["risco"]
        sinais = _sinais(contas[nome])
        assert (r["pontos"], r["nivel"]) == (75, "alto")
        citada = {"contas": [{"id": outra["conta"]["id"], "nome": outra["conta"]["nome"]}], "total": 1}
        assert sinais["documento_repetido"] == {"tipo": "documento_repetido", "pontos": 30, "documento": "cnpj",
                                                **citada}
        assert sinais["telefone_repetido"] == {"tipo": "telefone_repetido", "pontos": 20, **citada}
        assert sinais["dominio_repetido"] == {"tipo": "dominio_repetido", "pontos": 10, "dominio": "aurora.com.br",
                                              **citada}
        assert sinais["nome_repetido"] == {"tipo": "nome_repetido", "pontos": 15, **citada}
    assert contas["Outra"]["risco"]["sinais"] == []
    # o telefone do cadastro (com máscara e sem o 55) também é comparado
    sql(dono, "update contas set documento = null, telefone = null where id = :c", c=b["conta"]["id"])
    sql(dono, "update usuarios set telefone = '(11) 98765-4321' where email = 'bia@aurora.com.br'")
    assert set(_sinais(_contas(client, root["h"])["Distribuidora Aurora"])) == {
        "telefone_repetido", "dominio_repetido", "nome_repetido"}


def _enviar(dono, conta_id: int, n: int, situacao: str = "enviado", prefixo: str = "c", erro: str | None = None,
            dias: int = 5, canal: str = "email") -> None:
    sql(dono, "insert into envios (conta_id, canal, tipo, origem, situacao, para, erro, criado_em, enviado_em) "
              "select :c, :canal, 'convite', 'manual', :s, :p || g || '@lista.com.br', :e, now() - make_interval(days => :d), "
              "case when :s = 'erro' then null else now() - make_interval(days => :d) end from generate_series(1, :n) g",
        c=conta_id, canal=canal, s=situacao, p=prefixo, e=erro, d=dias, n=n)


def test_lista_comprada(client, root, dono):
    beta = conta_pronta(client, "ana@beta.com.br", empresa="Beta Atacado")
    cid, h = beta["conta"]["id"], beta["h"]
    f = form_padrao(client, h)
    # 150 convites que saíram há 5 dias, 1 respondido
    sql(dono, "insert into convites (conta_id, token_hash, formulario_id, canal, criado_em, respondido_em) "
              "select :c, md5('beta' || g), :f, 'email', now() - interval '5 days', "
              "case when g = 1 then now() - interval '4 days' end from generate_series(1, 150) g", c=cid, f=f["id"])
    sql(dono, "insert into envios (conta_id, convite_id, canal, tipo, origem, situacao, para, criado_em, enviado_em) "
              "select conta_id, id, 'email', 'convite', 'manual', 'enviado', 'c' || id || '@lista.com.br', criado_em, "
              "criado_em from convites where conta_id = :c", c=cid)
    _enviar(dono, cid, 20, "erro", prefixo="x", erro=MSG_ENDERECO)  # 20 de 170 tentativas: endereço que não existe
    sql(dono, "insert into descadastros (conta_id, email, origem) "
              "select :c, 's' || g || '@lista.com.br', case when g % 2 = 0 then 'link' else 'um_clique' end "
              "from generate_series(1, 9) g", c=cid)  # 9 de 150: 6%
    sql(dono, "insert into descadastros (conta_id, email, origem) "
              "select :c, 'm' || g || '@lista.com.br', 'manual' from generate_series(1, 10) g", c=cid)  # não contam
    conta = _contas(client, root["h"])["Beta Atacado"]
    sinais = _sinais(conta)
    assert (conta["risco"]["pontos"], conta["risco"]["nivel"]) == (65, "alto")
    assert sinais["descadastros"] == {"tipo": "descadastros", "pontos": 35, "saidas": 9, "destinatarios": 150,
                                      "taxa": 6}
    assert sinais["invalidos"] == {"tipo": "invalidos", "pontos": 15, "invalidos": 20, "tentativas": 170, "taxa": 12}
    assert sinais["sem_respostas"] == {"tipo": "sem_respostas", "pontos": 15, "convites": 150, "respostas": 1}
    assert "volume_inicio" not in sinais  # 150 envios: abaixo dos 500 da conta nova

    # faixas: 3% de saídas e 25% de inválidos (WhatsApp sem número) mudam os pontos
    sql(dono, "delete from descadastros where conta_id = :c and email like 's%' and email not in "
              "('s1@lista.com.br', 's2@lista.com.br', 's3@lista.com.br', 's4@lista.com.br', 's5@lista.com.br')",
        c=cid)
    _enviar(dono, cid, 30, "erro", prefixo="w", erro=MSG_NUMERO, canal="whatsapp")
    sinais = _sinais(_contas(client, root["h"])["Beta Atacado"])
    assert (sinais["descadastros"]["pontos"], sinais["descadastros"]["taxa"]) == (20, 3)
    assert (sinais["invalidos"]["pontos"], sinais["invalidos"]["invalidos"], sinais["invalidos"]["tentativas"]) == (
        30, 50, 200)

    # mais de 30 dias atrás não conta
    sql(dono, "update envios set criado_em = criado_em - interval '40 days', "
              "enviado_em = enviado_em - interval '40 days' where conta_id = :c", c=cid)
    sql(dono, "update convites set criado_em = criado_em - interval '40 days' where conta_id = :c", c=cid)
    sql(dono, "update descadastros set criado_em = criado_em - interval '40 days' where conta_id = :c", c=cid)
    assert _contas(client, root["h"])["Beta Atacado"]["risco"]["sinais"] == []


def test_pouco_volume_nao_acusa_e_conta_nova_com_muito_envio(client, root, dono):
    gama = conta_pronta(client, "ana@gama.com.br", empresa="Gama Bebidas")
    cid = gama["conta"]["id"]
    _enviar(dono, cid, 20, dias=1)
    sql(dono, "insert into descadastros (conta_id, email, origem) "
              "select :c, 's' || g || '@lista.com.br', 'link' from generate_series(1, 5) g", c=cid)
    _enviar(dono, cid, 9, "erro", prefixo="x", erro=MSG_ENDERECO, dias=1)
    # 20 destinatários e 29 tentativas: pouco para julgar (5 saídas e 9 inválidos não viram sinal)
    assert _contas(client, root["h"])["Gama Bebidas"]["risco"]["sinais"] == []
    _enviar(dono, cid, 500, prefixo="v", dias=1)
    sinais = _sinais(_contas(client, root["h"])["Gama Bebidas"])
    assert sinais["volume_inicio"] == {"tipo": "volume_inicio", "pontos": 10, "dias": 0, "envios": 520}
    sql(dono, "update contas set criada_em = now() - interval '20 days' where id = :c", c=cid)
    assert "volume_inicio" not in _sinais(_contas(client, root["h"])["Gama Bebidas"])


def test_formulario_pedindo_senha_e_estorno(client, root, dono):
    golpe = conta_pronta(client, "ana@delta.com.br", empresa="Delta Serviços")
    h = golpe["h"]
    criar_form(client, h, [{"tipo": "texto_curto", "titulo": "Sugestão"}], nome="Normal")
    f = criar_form(client, h, [{"tipo": "texto_curto", "titulo": "Para validar, digite a senha do seu banco"}],
                   nome="Atualização cadastral")
    conta = _contas(client, root["h"])["Delta Serviços"]
    assert (conta["risco"]["pontos"], conta["risco"]["nivel"]) == (60, "alto")
    assert conta["risco"]["sinais"] == [{
        "tipo": "formulario_sensivel", "pontos": 60, "formulario": {"id": f["id"], "nome": "Atualização cadastral"},
        "termo": "senha", "trecho": "Para validar, digite a senha do seu banco"}]
    # arquivado não conta
    sql(dono, "update formularios set arquivado = true where id = :f", f=f["id"])
    assert _contas(client, root["h"])["Delta Serviços"]["risco"]["sinais"] == []

    sql(dono, "insert into cobrancas (conta_id, asaas_id, valor, vencimento, situacao) "
              "values (:c, 'pay_estorno_1', 149, current_date - 10, 'estornada'), "
              "(:c, 'pay_estorno_2', 149, current_date - 40, 'estornada'), "
              "(:c, 'pay_ok', 149, current_date - 70, 'paga')", c=golpe["conta"]["id"])
    sinais = _contas(client, root["h"])["Delta Serviços"]["risco"]["sinais"]
    assert [(s["tipo"], s["pontos"], s["quantas"]) for s in sinais] == [("estorno", 25, 2)]
    assert sinais[0]["ultima_em"]


def test_nota_para_em_100(client, root, dono):
    cadastrar(client, "x@mailinator.com", empresa="teste")
    sql(dono, "update contas set criada_em = now() - interval '5 days', documento = '11144477735' "
              "where nome = 'teste'")
    cadastrar(client, "y@mailinator.com", empresa="Teste")
    sql(dono, "update contas set criada_em = now() - interval '5 days', documento = '11144477735' "
              "where nome = 'Teste'")
    contas = _contas(client, root["h"])
    r = contas["teste"]["risco"]
    # temporário 40 + não confirmado 15 + nome de teste 15 + CPF repetido 30 = 100 (nome de teste não repete)
    assert (r["pontos"], r["nivel"]) == (100, "alto")
    assert _sinais(contas["teste"])["documento_repetido"]["documento"] == "cpf"
    assert "nome_repetido" not in _sinais(contas["teste"])

"""Cadastro, confirmação, entrada, redefinição de senha e sessões."""
from datetime import datetime, timedelta, timezone

from util import SENHA, auth, cadastrar, conta_pronta, entrar, sql, token_do_email

from toqqi.core.email import caixa_memoria

API = "/api/v1"


def test_cadastro_cria_conta_em_teste_e_exige_confirmacao(client, dono):
    r = cadastrar(client, "Ana@Alfa.com.br", empresa="Alfa Ltda")
    assert "mensagem" in r.json()
    assert len(caixa_memoria) == 1 and caixa_memoria[0].para == "ana@alfa.com.br"
    assert "http://app.teste/confirmar-email?token=" in caixa_memoria[0].texto

    r = entrar(client, "ana@alfa.com.br")
    assert r.status_code == 403 and r.json()["erro"]["codigo"] == "email_nao_confirmado"

    (conta,) = sql(dono, "select situacao, teste_ate, termos_versao, termos_ip from contas")
    assert conta.situacao == "teste"
    assert conta.termos_versao == "2026-10" and conta.termos_ip
    faltam = conta.teste_ate - datetime.now(timezone.utc)
    assert timedelta(days=13, hours=23) < faltam <= timedelta(days=14)


def test_confirmacao_e_entrada(client):
    cadastrar(client, "ana@alfa.com.br")
    token = token_do_email("ana@alfa.com.br", "confirmar-email")
    r = client.post(f"{API}/auth/confirmar-email", json={"token": token})
    assert r.status_code == 200
    r = entrar(client, "ANA@alfa.com.br", ua="Mozilla/5.0 (Windows NT 10.0) Chrome/120.0 Safari/537.36")
    assert r.status_code == 200
    s = r.json()
    assert set(s) == {"token", "expira_em", "usuario", "conta", "permissoes"}
    assert s["usuario"]["perfil"] == "admin" and s["usuario"]["email_confirmado"] is True
    assert s["usuario"]["superadmin"] is False
    assert "equipe.gerenciar" in s["permissoes"]
    # sessão padrão: 60 minutos da conta
    expira = datetime.fromisoformat(s["expira_em"])
    assert timedelta(minutes=59) < expira - datetime.now(timezone.utc) <= timedelta(minutes=60)
    sessoes = client.get(f"{API}/eu/sessoes", headers=auth(s["token"])).json()
    assert sessoes[0]["aparelho"] == "Chrome no Windows" and sessoes[0]["atual"] is True


def test_link_de_confirmacao_invalido(client):
    r = client.post(f"{API}/auth/confirmar-email", json={"token": "nao-existe"})
    assert r.status_code == 400 and r.json()["erro"]["codigo"] == "link_invalido"


def test_lembrar_dura_30_dias(client):
    conta_pronta(client, "ana@alfa.com.br")
    s = entrar(client, "ana@alfa.com.br", lembrar=True).json()
    expira = datetime.fromisoformat(s["expira_em"])
    assert expira - datetime.now(timezone.utc) > timedelta(days=29)


def test_cadastro_exige_aceite_dos_termos(client):
    r = client.post(f"{API}/auth/cadastro", json={
        "empresa": "Alfa", "nome": "Ana", "email": "ana@alfa.com.br", "senha": SENHA, "aceite_termos": False})
    assert r.status_code == 422
    assert "termos" in r.json()["erro"]["campos"]["aceite_termos"]


def test_cadastro_com_email_existente_nao_revela_nem_cria(client, dono):
    r1 = cadastrar(client, "ana@alfa.com.br", empresa="Alfa")
    r2 = cadastrar(client, "ANA@alfa.com.br", empresa="Outra")
    assert r1.status_code == r2.status_code == 201
    assert r1.json() == r2.json()
    assert sql(dono, "select count(*) from contas")[0][0] == 1
    assert sql(dono, "select count(*) from usuarios")[0][0] == 1
    assert caixa_memoria[-1].assunto == "Você já tem uma conta no Toqqi"
    assert "token=" not in caixa_memoria[-1].texto


def test_senha_errada_e_email_desconhecido_respondem_igual(client, dono):
    conta_pronta(client, "ana@alfa.com.br")
    errada = entrar(client, "ana@alfa.com.br", "Errada@123")
    desconhecido = entrar(client, "ninguem@alfa.com.br", "Errada@123")
    assert errada.status_code == desconhecido.status_code == 401
    assert errada.json() == desconhecido.json()
    assert errada.json()["erro"] == {"codigo": "credenciais_invalidas", "mensagem": "E-mail ou senha incorretos.",
                                     "campos": {}}
    falhas = [d for (d,) in sql(dono, "select detalhe from auditoria where evento = 'login_falhou'")]
    assert falhas == [{"email": "ana@alfa.com.br"}]  # e-mail desconhecido não é gravado


def test_estado_da_conta_so_aparece_com_senha_certa(client):
    cadastrar(client, "ana@alfa.com.br")  # não confirmado
    r = entrar(client, "ana@alfa.com.br", "Errada@123")
    assert r.status_code == 401 and r.json()["erro"]["codigo"] == "credenciais_invalidas"
    r = entrar(client, "ana@alfa.com.br")
    assert r.json()["erro"]["codigo"] == "email_nao_confirmado"


def test_respostas_sem_enumeracao(client):
    conta_pronta(client, "ana@alfa.com.br")
    caixa_memoria.clear()
    for rota in ("esqueci-senha", "reenviar-confirmacao"):
        existe = client.post(f"{API}/auth/{rota}", json={"email": "ana@alfa.com.br"})
        nao_existe = client.post(f"{API}/auth/{rota}", json={"email": "zzz@alfa.com.br"})
        assert existe.status_code == nao_existe.status_code == 200
        assert existe.json() == nao_existe.json()
    # só o usuário existente recebe o link de redefinição; já confirmado não recebe reenvio
    assert [m.para for m in caixa_memoria] == ["ana@alfa.com.br"]


def test_reenviar_confirmacao_manda_novo_link(client):
    cadastrar(client, "ana@alfa.com.br")
    caixa_memoria.clear()
    client.post(f"{API}/auth/reenviar-confirmacao", json={"email": "ana@alfa.com.br"})
    token = token_do_email("ana@alfa.com.br", "confirmar-email")
    assert client.post(f"{API}/auth/confirmar-email", json={"token": token}).status_code == 200


def test_redefinir_senha_uso_unico_e_encerra_sessoes(client, dono):
    s = conta_pronta(client, "ana@alfa.com.br")
    client.post(f"{API}/auth/esqueci-senha", json={"email": "ana@alfa.com.br"})
    token = token_do_email("ana@alfa.com.br", "redefinir-senha")

    fraca = client.post(f"{API}/auth/redefinir-senha", json={"token": token, "senha": "fraca"})
    assert fraca.status_code == 422 and "senha" in fraca.json()["erro"]["campos"]

    r = client.post(f"{API}/auth/redefinir-senha", json={"token": token, "senha": "Nova#Senha9"})
    assert r.status_code == 200
    assert client.get(f"{API}/eu", headers=s["h"]).status_code == 401  # sessão antiga caiu
    r = client.post(f"{API}/auth/redefinir-senha", json={"token": token, "senha": "Outra#Senha9"})
    assert r.status_code == 400 and r.json()["erro"]["codigo"] == "link_invalido"
    assert entrar(client, "ana@alfa.com.br", SENHA).status_code == 401
    assert entrar(client, "ana@alfa.com.br", "Nova#Senha9").status_code == 200
    assert sql(dono, "select count(*) from auditoria where evento='senha_redefinida'")[0][0] == 1


def test_link_de_redefinicao_antigo_perde_validade(client, dono):
    conta_pronta(client, "ana@alfa.com.br")
    client.post(f"{API}/auth/esqueci-senha", json={"email": "ana@alfa.com.br"})
    antigo = token_do_email("ana@alfa.com.br", "redefinir-senha")
    client.post(f"{API}/auth/esqueci-senha", json={"email": "ana@alfa.com.br"})
    novo = token_do_email("ana@alfa.com.br", "redefinir-senha")
    assert client.post(f"{API}/auth/redefinir-senha",
                       json={"token": antigo, "senha": "Nova#Senha9"}).status_code == 400
    # expirado (30 min)
    sql(dono, "update tokens_uso_unico set expira_em = now() - interval '1 second'")
    assert client.post(f"{API}/auth/redefinir-senha",
                       json={"token": novo, "senha": "Nova#Senha9"}).status_code == 400


def test_sair_e_encerrar_sessao_derrubam_o_token(client):
    conta_pronta(client, "ana@alfa.com.br")
    s1 = auth(entrar(client, "ana@alfa.com.br").json()["token"])
    s2 = auth(entrar(client, "ana@alfa.com.br").json()["token"])
    s3 = auth(entrar(client, "ana@alfa.com.br").json()["token"])

    assert client.post(f"{API}/auth/sair", headers=s1).status_code == 204
    r = client.get(f"{API}/eu", headers=s1)
    assert r.status_code == 401 and r.json()["erro"]["codigo"] == "sessao_invalida"

    id_s3 = next(x["id"] for x in client.get(f"{API}/eu/sessoes", headers=s3).json() if x["atual"])
    assert client.delete(f"{API}/eu/sessoes/{id_s3}", headers=s2).status_code == 204
    assert client.get(f"{API}/eu", headers=s3).status_code == 401

    assert client.post(f"{API}/eu/sessoes/encerrar-outras", headers=s2).status_code == 204
    atuais = client.get(f"{API}/eu/sessoes", headers=s2).json()
    assert len(atuais) == 1 and atuais[0]["atual"]


def test_sessao_expirada_e_token_invalido(client, dono):
    s = conta_pronta(client, "ana@alfa.com.br")
    sql(dono, "update sessoes set expira_em = now() - interval '1 second'")
    r = client.get(f"{API}/eu", headers=s["h"])
    assert r.status_code == 401 and "expirou" in r.json()["erro"]["mensagem"]
    assert client.get(f"{API}/eu", headers=auth("lixo")).status_code == 401
    assert client.get(f"{API}/eu").json()["erro"]["codigo"] == "sessao_invalida"


def test_trocar_senha_encerra_outras_sessoes(client):
    s = conta_pronta(client, "ana@alfa.com.br")
    outra = auth(entrar(client, "ana@alfa.com.br").json()["token"])
    r = client.post(f"{API}/eu/senha", headers=s["h"], json={"senha_atual": "Errada@1", "senha_nova": "Nova#Senha9"})
    assert r.status_code == 422 and "senha_atual" in r.json()["erro"]["campos"]
    r = client.post(f"{API}/eu/senha", headers=s["h"], json={"senha_atual": SENHA, "senha_nova": "Nova#Senha9"})
    assert r.status_code == 200
    assert client.get(f"{API}/eu", headers=s["h"]).status_code == 200
    assert client.get(f"{API}/eu", headers=outra).status_code == 401
    assert entrar(client, "ana@alfa.com.br", "Nova#Senha9").status_code == 200


def test_alterar_eu(client):
    s = conta_pronta(client, "ana@alfa.com.br")
    r = client.patch(f"{API}/eu", headers=s["h"], json={"nome": "  Ana Souza ", "cargo": "Diretora"})
    assert r.status_code == 200
    assert r.json()["nome"] == "Ana Souza" and r.json()["cargo"] == "Diretora"
    assert client.get(f"{API}/eu", headers=s["h"]).json()["usuario"]["nome"] == "Ana Souza"


def test_regras_senha(client):
    r = client.get(f"{API}/auth/regras-senha")
    assert r.json() == {"minimo": 8, "maximo": 70, "exige": ["maiuscula", "numero", "simbolo"]}
    for senha in ["Curta@1", "semmaiuscula@1", "SemNumero@", "SemSimbolo1", "A1@" + "x" * 68]:
        r = client.post(f"{API}/auth/cadastro", json={
            "empresa": "Alfa", "nome": "Ana", "email": "ana@alfa.com.br", "senha": senha, "aceite_termos": True})
        assert r.status_code == 422, senha
        assert r.json()["erro"]["campos"]["senha"].startswith("A senha precisa ter")

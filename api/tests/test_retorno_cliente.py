"""Melhoria 4, retorno ao cliente: depois de concluído, o plano de ação pode avisar o contato do que foi feito, uma
vez, por e-mail (fila de envios, tipo `retorno`, registro de e-mails enviados). Recusa ação aberta, contato sem e-mail
ou descadastrado e o segundo aviso; pede `acoes.tratar`."""
import pytest
from util import API, conta_pronta, criar_contato, criar_responsavel, ligar_envios, membro, sql

from toqqi.core.email import caixa_memoria

TEXTO = "Olá, {nome}! Você nos contou que a entrega atrasou. Trocamos de transportadora nesta semana. Obrigado!"


@pytest.fixture
def cenario(client):
    a = conta_pronta(client, "ana@alfa.com.br", empresa="Alfa")
    h = a["h"]
    ligar_envios(client, h)
    contato = criar_contato(client, h, nome="Paula Lima", email="paula@cliente.com.br")
    rita = criar_responsavel(client, h)
    acao = client.post(f"{API}/acoes", headers=h, json={"titulo": "Entrega atrasada", "contato_id": contato["id"],
                                                        "responsavel_id": rita["id"]})
    assert acao.status_code == 201, acao.text
    return {**a, "contato": contato, "acao": acao.json(), "rita": rita}


def _retorno(client, h, acao_id, texto=TEXTO):
    return client.post(f"{API}/acoes/{acao_id}/retorno", headers=h, json={"texto": texto})


def _concluir(client, h, acao_id):
    r = client.patch(f"{API}/acoes/{acao_id}", headers=h, json={"situacao": "concluida", "resolucao": "Trocamos"})
    assert r.status_code == 200, r.text


def test_avisa_uma_vez_depois_de_concluida(client, dono, cenario):
    h, aid = cenario["h"], cenario["acao"]["id"]
    assert _retorno(client, h, aid).json()["erro"]["codigo"] == "nao_concluida"
    _concluir(client, h, aid)
    assert _retorno(client, h, aid, "curto").status_code == 422
    antes = len(caixa_memoria)
    r = _retorno(client, h, aid)
    assert r.status_code == 200, r.text
    assert r.json()["retorno_em"] and r.json()["retorno_texto"] == TEXTO
    m = caixa_memoria[antes]
    assert m.para == "paula@cliente.com.br" and m.assunto == "Alfa: o que fizemos com a sua opinião"
    assert "Olá, Paula! Você nos contou" in m.texto and "Não quero mais receber pesquisas" in m.texto
    assert _retorno(client, h, aid).json()["erro"]["codigo"] == "ja_enviado"
    assert len(caixa_memoria) == antes + 1
    (tipo, situacao), = sql(dono, "select tipo, situacao from envios where acao_id = :a", a=aid)
    assert (tipo, situacao) == ("retorno", "enviado")
    assert sql(dono, "select count(*) from emails_enviados where tipo = 'retorno'")[0][0] == 1
    eventos = {e for (e,) in sql(dono, "select evento from auditoria")}
    assert "envio_retorno" in eventos


def test_sem_email_descadastrado_e_permissao(client, dono, cenario):
    h = cenario["h"]
    sem_email = criar_contato(client, h, nome="Sem Email", email=None, telefone="11987654321")
    a2 = client.post(f"{API}/acoes", headers=h, json={"titulo": "X", "contato_id": sem_email["id"],
                                                      "responsavel_id": cenario["rita"]["id"]}).json()
    _concluir(client, h, a2["id"])
    assert _retorno(client, h, a2["id"]).json()["erro"]["codigo"] == "sem_email"
    aid = cenario["acao"]["id"]
    _concluir(client, h, aid)
    sql(dono, "update contatos set recebe_pesquisas = false where id = :c", c=cenario["contato"]["id"])
    assert _retorno(client, h, aid).json()["erro"]["codigo"] == "descadastrado"
    consulta = membro(client, h, "leo@alfa.com.br", perfil="consulta")
    sql(dono, "delete from perfil_permissoes where conta_id = :c and perfil = 'consulta' and permissao = 'acoes.tratar'",
        c=cenario["conta"]["id"])
    assert _retorno(client, consulta["h"], aid).status_code == 403

"""Melhoria 5, prova social: o pedido de depoimento e o link de avaliação na tela final (só promotor, com comentário,
ligado na conta liberada), a autorização pela página pública (uma vez), a lista em Crescimento › Depoimentos com o
resumo, aprovar/ocultar (auditado) e as permissões."""
import pytest
from util import API, conta_pronta, criar_contato, criar_empresa, form_padrao, link_pesquisa, membro, sql

pytestmark = pytest.mark.usefixtures("relogio_estavel")
GOOGLE = "https://g.page/r/mercado-alfa/review"


@pytest.fixture
def alfa(client):
    a = conta_pronta(client, "ana@alfa.com.br", empresa="Alfa Distribuidora")
    h = a["h"]
    r = client.put(f"{API}/crescimento/configuracao", headers=h, json={"depoimentos_ativos": True, "link_avaliacao": GOOGLE})
    assert r.status_code == 200, r.text
    empresa = criar_empresa(client, h, "Mercado Bom Preço")
    contato = criar_contato(client, h, nome="Ana Souza", email="ana@bompreco.com.br", empresa_id=empresa["id"])
    return {**a, "contato": contato, "form": form_padrao(client, h)}


def _responder(client, a, nota: int, comentario: str = "") -> tuple[str, dict]:
    f = a["form"]
    token = link_pesquisa(client, a["h"], a["contato"]["id"], formulario_id=f["id"])
    respostas = {f["perguntas"][0]["id"]: nota}
    texto = next((p for p in f["perguntas"][1:] if p["tipo"] in ("texto", "texto_longo", "comentario")), None)
    if comentario and texto:
        respostas[texto["id"]] = comentario
    r = client.post(f"{API}/publico/convites/{token}/responder", json={"respostas": respostas})
    assert r.status_code == 201, r.text
    return token, r.json()


def test_tela_final_e_autorizacao(client, dono, alfa):
    h = alfa["h"]
    token, r = _responder(client, alfa, 10, "Entrega sempre no prazo, recomendo!")
    assert r["depoimento"] == {"pedir": True, "avaliar_url": GOOGLE, "avaliar_rotulo": "Avaliar a Alfa Distribuidora"}
    _, r = _responder(client, alfa, 10)  # sem comentário: só o link de avaliação
    assert r["depoimento"]["pedir"] is False and r["depoimento"]["avaliar_url"] == GOOGLE
    t8, r = _responder(client, alfa, 8, "Bom")  # neutro: nada
    assert r["depoimento"] is None
    assert client.post(f"{API}/publico/convites/{t8}/depoimento").status_code == 409

    assert client.post(f"{API}/publico/convites/{token}/depoimento").status_code == 200
    assert client.post(f"{API}/publico/convites/{token}/depoimento").json()["mensagem"].startswith("Obrigado")

    lista = client.get(f"{API}/crescimento/depoimentos", headers=h).json()
    assert lista["total"] == 1 and lista["resumo"] == {"pendente": 1, "aprovado": 0, "oculto": 0}
    d = lista["itens"][0]
    assert (d["comentario"], d["assinatura"], d["situacao"], d["nota"]) == (
        "Entrega sempre no prazo, recomendo!", "Ana, Mercado Bom Preço", "pendente", 10)

    r = client.patch(f"{API}/crescimento/depoimentos/{d['resposta_id']}", headers=h, json={"situacao": "aprovado"})
    assert r.status_code == 200 and r.json()["situacao"] == "aprovado"
    assert client.get(f"{API}/crescimento/depoimentos", headers=h, params={"situacao": "aprovado"}).json()["total"] == 1
    assert sql(dono, "select count(*) from auditoria where evento = 'depoimento_alterado'")[0][0] == 1
    assert client.patch(f"{API}/crescimento/depoimentos/999999", headers=h, json={"situacao": "oculto"}).status_code == 404


def test_desligado_conta_parada_e_link_invalido(client, dono, alfa):
    h = alfa["h"]
    assert client.put(f"{API}/crescimento/configuracao", headers=h,
                      json={"link_avaliacao": "http://inseguro.com"}).status_code == 422
    r = client.put(f"{API}/crescimento/configuracao", headers=h, json={"depoimentos_ativos": False, "link_avaliacao": ""})
    assert (r.json()["depoimentos_ativos"], r.json()["link_avaliacao"]) == (False, None)
    token, r = _responder(client, alfa, 10, "Ótimo")
    assert r["depoimento"] is None
    assert client.post(f"{API}/publico/convites/{token}/depoimento").status_code == 409

    client.put(f"{API}/crescimento/configuracao", headers=h, json={"depoimentos_ativos": True})
    sql(dono, "update contas set situacao = 'teste_expirado' where id = :c", c=alfa["conta"]["id"])
    assert _responder(client, alfa, 10, "Ótimo")[1]["depoimento"] is None


def test_permissoes(client, alfa):
    consulta = membro(client, alfa["h"], "leo@alfa.com.br", perfil="consulta")
    r = client.get(f"{API}/crescimento/depoimentos", headers=consulta["h"])
    assert r.status_code in (200, 403)
    assert client.patch(f"{API}/crescimento/depoimentos/1", headers=consulta["h"],
                        json={"situacao": "aprovado"}).status_code == 403

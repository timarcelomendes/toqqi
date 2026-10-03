"""WhatsApp, "responda SAIR" (etapa 5f): variações aceitas e recusadas (mensagem inteira normalizada, até 40
caracteres), resposta de botão (do modelo e interativo) e o modelo sem SAIR no corpo nem no rodapé → 422."""
import pytest
from util import (
    API,
    PNID,
    _mudanca,
    aviso_meta,
    aviso_mensagem,
    conectar_whatsapp,
    conta_pronta,
    criar_contato,
    modelo_meta,
    sql,
)

from toqqi.modulos.whatsapp.webhook import pede_para_sair

ACEITAS = ["sair", "SAIR", "  Sáir! ", "Sair da lista", "sair da lista.", "Quero sair", "PARAR", "pare", "Stop",
           "cancelar", "Descadastrar", "Não quero mais", "nao quero mais receber", "NÃO QUERO MAIS RECEBER!!!",
           "sair\n", "quero   sair", "Não quero receber", "NÃO QUERO RECEBER.", "não quero receber mais",
           "Nao quero receber mais!"]
RECUSADAS = ["Oi, tudo bem?", "sair agora", "quero sair dessa lista", "não", "parar de receber", "sairá", "sai",
             "stop " * 10, "", "   ", "Não quero mais receber essas mensagens", "Não quero receber essa pesquisa",
             "não quero"]


@pytest.mark.parametrize("texto", ACEITAS)
def test_variacoes_aceitas(texto):
    assert pede_para_sair(texto) is True


@pytest.mark.parametrize("texto", [*RECUSADAS, None, 123])
def test_variacoes_recusadas(texto):
    assert pede_para_sair(texto) is False


@pytest.fixture
def admin(client, dono, meta):
    a = conta_pronta(client, "ana@alfa.com.br", empresa="Alfa Distribuidora")
    sql(dono, "update contas set situacao = 'cortesia' where id = :c", c=a["conta"]["id"])
    assert conectar_whatsapp(client, a["h"]).status_code == 200
    criar_contato(client, a["h"], nome="João", email=None, telefone="11987654321")
    return a


def _botao(de: str, tipo: str, texto: str) -> dict:
    m = {"from": de, "id": "wamid.botao", "timestamp": "1700000000", "type": tipo}
    if tipo == "button":
        m["button"] = {"text": texto, "payload": "sair"}
    else:
        m["interactive"] = {"type": "button_reply", "button_reply": {"id": "sair", "title": texto}}
    return _mudanca(PNID, {"messages": [m]})


def test_mensagem_qualquer_e_ignorada_sem_resposta(client, admin, meta, dono):
    antes = len(meta.mensagens)
    assert aviso_meta(client, aviso_mensagem("5511987654321", "Quero sair dessa pesquisa, obrigado")).status_code == 200
    assert sql(dono, "select count(*) from descadastros")[0][0] == 0
    assert len(meta.mensagens) == antes


@pytest.mark.parametrize("texto", ["Não quero mais receber", "quero sair"])
def test_frase_descadastra(client, admin, meta, dono, texto):
    assert aviso_meta(client, aviso_mensagem("5511987654321", texto)).status_code == 200
    assert sql(dono, "select telefone, origem from descadastros") == [("5511987654321", "whatsapp")]
    assert meta.mensagens[-1]["text"]["body"].startswith("Pronto!")


@pytest.mark.parametrize("tipo,texto", [("button", "Sair"), ("interactive", "Não quero mais receber"),
                                        ("button", "Responder"),
                                        ("button", modelo_meta()["components"][2]["buttons"][0]["text"])])
def test_resposta_de_botao(client, admin, meta, dono, tipo, texto):
    """Inclusive o botão de resposta rápida "Não quero receber" do modelo de teste."""
    assert aviso_meta(client, _botao("5511987654321", tipo, texto)).status_code == 200
    esperado = 0 if texto == "Responder" else 1
    assert sql(dono, "select count(*) from descadastros")[0][0] == esperado


@pytest.mark.parametrize("componentes,aceito", [
    # SAIR no rodapé (o modelo sugerido) ou no corpo, qualquer caixa
    ([{"type": "BODY", "text": "Olá, {{1}}! A {{2}} quer saber como foi {{3}}."},
      {"type": "FOOTER", "text": "Para não receber mais pesquisas, responda SAIR."}], True),
    ([{"type": "BODY", "text": "Olá, {{1}}! A {{2}} quer saber como foi {{3}}. Para parar, responda sair."}], True),
    # sem a palavra inteira
    ([{"type": "BODY", "text": "Olá, {{1}}! A {{2}} quer saber como foi {{3}}."},
      {"type": "FOOTER", "text": "Responda PARAR para não receber mais."}], False),
    ([{"type": "BODY", "text": "Olá, {{1}}! A {{2}} quer saber como foi {{3}}. O resultado sairá em breve."}], False),
])
def test_modelo_precisa_de_sair(client, dono, meta, componentes, aceito):
    a = conta_pronta(client, "bia@beta.com.br", empresa="Beta")
    botao = {"type": "BUTTONS", "buttons": [{"type": "URL", "text": "Responder", "url": "http://app.teste/r/{{1}}"}]}
    meta.modelos = [modelo_meta(components=[*componentes, botao])]
    r = conectar_whatsapp(client, a["h"])
    if aceito:
        assert r.status_code == 200, r.text
    else:
        assert r.status_code == 422, r.text
        assert r.json()["erro"]["campos"]["modelo_nome"] == (
            "O modelo precisa dizer como parar de receber, por exemplo no rodapé: “Para não receber mais pesquisas, "
            "responda SAIR.”")
        assert client.get(f"{API}/integracoes/whatsapp", headers=a["h"]).json()["conectado"] is False

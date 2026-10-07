"""WhatsApp, "responda SAIR" (etapa 5f): variações aceitas e recusadas (mensagem inteira normalizada, até 40
caracteres), resposta de botão (do modelo e interativo) e o modelo sem SAIR no corpo nem no rodapé → 422. E o VOLTAR
(docs/api-voltar-a-receber.md): só com o telefone fora da lista, e volta em todos os canais."""
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

from toqqi.modulos.whatsapp.webhook import pede_para_sair, pede_para_voltar

ACEITAS = ["sair", "SAIR", "  Sáir! ", "Sair da lista", "sair da lista.", "Quero sair", "PARAR", "pare", "Stop",
           "cancelar", "Descadastrar", "Não quero mais", "nao quero mais receber", "NÃO QUERO MAIS RECEBER!!!",
           "sair\n", "quero   sair", "Não quero receber", "NÃO QUERO RECEBER.", "não quero receber mais",
           "Nao quero receber mais!"]
RECUSADAS = ["Oi, tudo bem?", "sair agora", "quero sair dessa lista", "não", "parar de receber", "sairá", "sai",
             "stop " * 10, "", "   ", "Não quero mais receber essas mensagens", "Não quero receber essa pesquisa",
             "não quero"]


ACEITAS_VOLTAR = ["voltar", "VOLTAR", " Voltar! ", "Quero voltar", "voltar a receber", "Quero voltar a receber.",
                  "quero receber", "Quero receber de novo", "receber novamente"]
RECUSADAS_VOLTAR = ["volta", "voltei", "vou voltar a comprar", "quero receber o boleto", "receber", "sim", "",
                    "voltar " * 10]


@pytest.mark.parametrize("texto", ACEITAS)
def test_variacoes_aceitas(texto):
    assert pede_para_sair(texto) is True
    assert pede_para_voltar(texto) is False


@pytest.mark.parametrize("texto", ACEITAS_VOLTAR)
def test_variacoes_aceitas_voltar(texto):
    assert pede_para_voltar(texto) is True
    assert pede_para_sair(texto) is False


@pytest.mark.parametrize("texto", [*RECUSADAS_VOLTAR, None, 123])
def test_variacoes_recusadas_voltar(texto):
    assert pede_para_voltar(texto) is False


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


def test_voltar_pelo_whatsapp(client, admin, meta, dono):
    # sem estar fora da lista, VOLTAR é uma mensagem qualquer: sem resposta
    antes = len(meta.mensagens)
    assert aviso_meta(client, aviso_mensagem("5511987654321", "voltar")).status_code == 200
    assert len(meta.mensagens) == antes
    aviso_meta(client, aviso_mensagem("5511987654321", "sair"))
    assert meta.mensagens[-1]["text"]["body"] == ("Pronto! Você não vai mais receber pesquisas da Alfa Distribuidora. "
                                                  "Se mudar de ideia, responda VOLTAR.")
    assert sql(dono, "select count(*) from descadastros")[0][0] == 1
    # o WhatsApp manda o celular sem o nono dígito
    assert aviso_meta(client, aviso_mensagem("551187654321", "Quero voltar")).status_code == 200
    assert sql(dono, "select count(*) from descadastros")[0][0] == 0
    assert meta.mensagens[-1]["text"]["body"] == ("Pronto! Você volta a receber as pesquisas da Alfa Distribuidora. "
                                                  "Para parar, responda SAIR.")
    assert meta.mensagens[-1]["to"] == "551187654321"
    assert sql(dono, "select detalhe->>'origem', detalhe->>'telefone' from auditoria "
                     "where evento = 'descadastro_desfeito'") == [("whatsapp", "***4321")]
    # de novo: já recebe, sem resposta
    antes = len(meta.mensagens)
    aviso_meta(client, aviso_mensagem("5511987654321", "voltar"))
    assert len(meta.mensagens) == antes


def test_voltar_pelo_whatsapp_tira_tambem_o_email_do_mesmo_contato(client, admin, meta, dono):
    h = admin["h"]
    criar_contato(client, h, nome="Bia", email="bia@cliente.com.br", telefone="11976543210")
    # saiu pelo link do e-mail; o telefone dela não está na lista
    r = client.post(f"{API}/envios/descadastros", headers=h, json={"email": "bia@cliente.com.br"})
    assert r.status_code == 201, r.text
    aviso_meta(client, aviso_mensagem("5511976543210", "VOLTAR"))
    assert sql(dono, "select count(*) from descadastros")[0][0] == 0
    assert meta.mensagens[-1]["text"]["body"].startswith("Pronto! Você volta a receber")

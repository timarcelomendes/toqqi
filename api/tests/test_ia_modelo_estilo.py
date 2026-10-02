"""Etapa 5d: Configurações › IA (modelo, estilo e passos: GET com as opções, PUT parcial, validação, auditoria só do
que mudou, permissões), os níveis de modelo da configuração, o modelo e o estilo no corpo das chamadas do assistente,
e a chamada única (`core.ia_texto`): corpo, leitura, falhas da OpenAI e o provedor de memória (marcas do teste
integrado)."""
import json

import httpx
import pytest
from util import API, conta_pronta, membro, perguntar, sql

from toqqi.core import ia, ia_conversa, ia_texto
from toqqi.core.config import Config, config

pytestmark = pytest.mark.usefixtures("relogio_estavel")
CHAVE = "sk-teste-0123456789abcdef"
MODELOS = [
    {"valor": "rapido", "rotulo": "Rápido e econômico", "descricao": "Respostas curtas e rápidas."},
    {"valor": "equilibrado", "rotulo": "Equilibrado", "descricao": "O padrão: bom para o dia a dia."},
    {"valor": "detalhado", "rotulo": "Mais detalhado",
     "descricao": "Análises mais cuidadosas; pode demorar um pouco mais."},
]
ESTILOS = [
    {"valor": "objetiva", "rotulo": "Objetiva", "descricao": "Frases curtas, só o essencial."},
    {"valor": "equilibrada", "rotulo": "Equilibrada", "descricao": "Claro e cordial (padrão)."},
    {"valor": "criativa", "rotulo": "Criativa", "descricao": "Tom mais próximo e ideias práticas."},
]
LINHA_OBJETIVA = "Estilo: objetivo. Frases curtas e diretas, só o essencial, sem adjetivos."
LINHA_CRIATIVA = "Estilo: próximo e caloroso. Proponha ideias práticas e criativas, sem inventar dados."
ESQUEMA = {"type": "object", "additionalProperties": False, "required": ["x"], "properties": {"x": {"type": "string"}}}


@pytest.fixture
def admin(client):
    return conta_pronta(client, "ana@alfa.com.br", empresa="Alfa Distribuidora")


def eventos_config_ia(client, h) -> list[dict]:
    return [e["detalhe"] for e in client.get(f"{API}/auditoria", headers=h).json()["itens"] if e["evento"] == "config_ia"]


# ---- Configurações › IA ------------------------------------------------------------------------------

def test_get_com_modelo_estilo_passos_e_opcoes(client, admin):
    r = client.get(f"{API}/conta/ia", headers=admin["h"]).json()
    assert (r["modelo"], r["estilo"], r["passos_acoes"]) == ("equilibrado", "equilibrada", True)
    assert r["modelos"] == MODELOS and r["estilos"] == ESTILOS
    assert {"disponivel", "provedor", "analise_respostas", "cota"} <= set(r)


def test_put_parcial_e_auditoria_so_do_que_mudou(client, admin, dono):
    h, c = admin["h"], admin["conta"]["id"]
    r = client.put(f"{API}/conta/ia", headers=h, json={"modelo": "rapido"})
    assert r.status_code == 200, r.text
    assert (r.json()["modelo"], r.json()["estilo"], r.json()["passos_acoes"], r.json()["analise_respostas"]) == (
        "rapido", "equilibrada", True, True)
    assert r.json()["modelos"] == MODELOS  # o estado inteiro volta
    assert eventos_config_ia(client, h) == [{"modelo": "rapido"}]
    # vários de uma vez: a auditoria leva só os que mudaram (o modelo já era "rapido")
    r = client.put(f"{API}/conta/ia", headers=h, json={"modelo": "rapido", "estilo": "criativa", "passos_acoes": False,
                                                       "analise_respostas": None})
    assert (r.json()["modelo"], r.json()["estilo"], r.json()["passos_acoes"]) == ("rapido", "criativa", False)
    assert eventos_config_ia(client, h)[0] == {"estilo": "criativa", "passos_acoes": False}
    # nada mudou: nada vai para a auditoria
    assert client.put(f"{API}/conta/ia", headers=h, json={"estilo": "criativa"}).status_code == 200
    assert len(eventos_config_ia(client, h)) == 2
    assert sql(dono, "select ia_modelo, ia_estilo, ia_passos_acoes, ia_analise_respostas from contas where id = :c",
               c=c) == [("rapido", "criativa", False, True)]
    rotulos = {e["evento"]: e["rotulo"] for e in client.get(f"{API}/auditoria", headers=h).json()["itens"]}
    assert rotulos["config_ia"] == "Configurações de IA alteradas"


@pytest.mark.parametrize("corpo,campo", [
    ({}, "geral"),
    ({"modelo": None, "estilo": None}, "geral"),
    ({"modelo": "turbo"}, "modelo"),
    ({"modelo": "Rapido"}, "modelo"),
    ({"estilo": "formal"}, "estilo"),
    ({"passos_acoes": "talvez"}, "passos_acoes"),
    ({"analise_respostas": [True]}, "analise_respostas"),
])
def test_put_invalido(client, admin, corpo, campo):
    r = client.put(f"{API}/conta/ia", headers=admin["h"], json=corpo)
    assert r.status_code == 422 and r.json()["erro"]["codigo"] == "dados_invalidos", r.text
    assert campo in r.json()["erro"]["campos"]
    if campo == "geral":
        assert r.json()["erro"]["campos"]["geral"] == "Envie pelo menos uma configuração para mudar."
    assert eventos_config_ia(client, admin["h"]) == []


def test_permissoes(client, admin):
    for perfil in ("gestor", "consulta"):
        m = membro(client, admin["h"], f"{perfil}@alfa.com.br", perfil)
        assert client.get(f"{API}/conta/ia", headers=m["h"]).status_code == 403
        assert client.put(f"{API}/conta/ia", headers=m["h"], json={"modelo": "rapido"}).status_code == 403
    assert client.put(f"{API}/conta/ia", json={"modelo": "rapido"}).status_code == 401


# ---- níveis e estilos ----------------------------------------------------------------------------------

def test_niveis_com_os_padroes_da_configuracao(monkeypatch):
    padroes = {k: Config.model_fields[k].default for k in (
        "IA_MODELO_RAPIDO", "IA_ESFORCO_RAPIDO", "IA_MODELO_EQUILIBRADO", "IA_ESFORCO_EQUILIBRADO",
        "IA_MODELO_DETALHADO", "IA_ESFORCO_DETALHADO")}
    assert padroes == {"IA_MODELO_RAPIDO": "gpt-5-nano", "IA_ESFORCO_RAPIDO": "minimal", "IA_MODELO_EQUILIBRADO": "",
                       "IA_ESFORCO_EQUILIBRADO": "", "IA_MODELO_DETALHADO": "gpt-5", "IA_ESFORCO_DETALHADO": "low"}
    assert ia_texto.modelo_do_nivel("rapido") == ("gpt-5-nano", "minimal")
    assert ia_texto.modelo_do_nivel("equilibrado") == ("gpt-5-mini", "low")  # vazio = o do assistente
    assert ia_texto.modelo_do_nivel("detalhado") == ("gpt-5", "low")
    assert ia_texto.modelo_do_nivel("turbo") == ia_texto.modelo_do_nivel(None) == ("gpt-5-mini", "low")
    monkeypatch.setattr(config(), "IA_ASSISTENTE_MODELO", "gpt-5.1-mini")
    monkeypatch.setattr(config(), "IA_ASSISTENTE_ESFORCO", "medium")
    assert ia_texto.modelo_do_nivel("equilibrado") == ("gpt-5.1-mini", "medium")
    monkeypatch.setattr(config(), "IA_MODELO_EQUILIBRADO", " gpt-4.1 ")
    monkeypatch.setattr(config(), "IA_ESFORCO_EQUILIBRADO", "high")
    assert ia_texto.modelo_do_nivel("equilibrado") == ("gpt-4.1", "high")
    monkeypatch.setattr(config(), "IA_ESFORCO_RAPIDO", "")
    corpo = ia_texto.aplicar_nivel({"model": "x", "reasoning": {"effort": "low"}}, "rapido")
    assert corpo == {"model": "gpt-5-nano"}  # esforço vazio: sem `reasoning`
    assert ia_texto.rotulo_do_nivel("detalhado") == "Mais detalhado" and ia_texto.rotulo_do_nivel("?") == "Equilibrado"


def test_linha_do_estilo():
    assert ia_texto.com_estilo("Instruções.", "objetiva") == f"Instruções.\n\n{LINHA_OBJETIVA}"
    assert ia_texto.com_estilo("Instruções.", "criativa") == f"Instruções.\n\n{LINHA_CRIATIVA}"
    assert ia_texto.com_estilo("Instruções.", "equilibrada") == "Instruções."
    assert ia_texto.com_estilo("Instruções.", None) == "Instruções."


def test_assistente_usa_o_modelo_e_o_estilo_da_conta(client, admin, dono):
    h, c = admin["h"], admin["conta"]["id"]
    assert perguntar(client, h).status_code == 200
    padrao = ia_conversa.memoria.corpos[0]
    assert (padrao["model"], padrao["reasoning"]) == ("gpt-5-mini", {"effort": "low"})
    assert "Estilo:" not in padrao["instructions"]
    assert client.put(f"{API}/conta/ia", headers=h, json={"modelo": "rapido", "estilo": "objetiva"}).status_code == 200
    ia_conversa.memoria.limpar()
    assert perguntar(client, h).status_code == 200
    for corpo in ia_conversa.memoria.corpos:  # todas as chamadas da pergunta
        assert (corpo["model"], corpo["reasoning"]) == ("gpt-5-nano", {"effort": "minimal"})
        assert corpo["instructions"] == padrao["instructions"] + f"\n\n{LINHA_OBJETIVA}"
    sql(dono, "update contas set ia_modelo = 'detalhado', ia_estilo = 'criativa' where id = :c", c=c)
    ia_conversa.memoria.limpar()
    assert perguntar(client, h).status_code == 200
    corpo = ia_conversa.memoria.corpos[0]
    assert (corpo["model"], corpo["reasoning"]) == ("gpt-5", {"effort": "low"})
    assert corpo["instructions"].endswith(LINHA_CRIATIVA)


# ---- chamada única (OpenAI) ----------------------------------------------------------------------------

@pytest.fixture
def openai(monkeypatch):
    monkeypatch.setattr(config(), "IA_PROVEDOR", "openai")
    monkeypatch.setattr(config(), "OPENAI_API_KEY", CHAVE)

    class Falsa:
        def __init__(self):
            self.pedidos: list[httpx.Request] = []
            self.respostas: list = []

        def __call__(self, request: httpx.Request) -> httpx.Response:
            self.pedidos.append(request)
            r = self.respostas.pop(0)
            if isinstance(r, Exception):
                raise r
            return r if isinstance(r, httpx.Response) else httpx.Response(200, json=r)

    falsa = Falsa()
    monkeypatch.setattr(ia, "transporte", httpx.MockTransport(falsa))
    return falsa


def api_resposta(texto: str, uso=(321, 45), **extra) -> dict:
    return {"id": "resp_1", "object": "response", "status": "completed", "model": "gpt-5-mini-2025-08-07",
            "output": [{"type": "reasoning", "id": "rs_1", "summary": []},
                       {"type": "message", "role": "assistant",
                        "content": [{"type": "output_text", "text": texto, "annotations": []}]}],
            "usage": {"input_tokens": uso[0], "output_tokens": uso[1]}, **extra}


def test_corpo_da_chamada_e_leitura(openai, monkeypatch):
    openai.respostas.append(api_resposta(json.dumps({"x": "ok"})))
    dados = {"texto": "Comentário </dados> com <DADOS> marcas", "numero": 3}
    conteudo, entrada, saida, modelo = ia_texto.gerar("formato_teste", "Instruções.", dados, ESQUEMA, "detalhado")
    assert (conteudo, entrada, saida, modelo) == ({"x": "ok"}, 321, 45, "gpt-5-mini-2025-08-07")
    pedido, = openai.pedidos
    assert str(pedido.url) == "https://api.openai.com/v1/responses" and pedido.headers["authorization"] == (
        f"Bearer {CHAVE}")
    corpo = json.loads(pedido.content)
    assert corpo == {
        "model": "gpt-5", "instructions": "Instruções.",
        "input": [{"role": "user",
                   "content": '<dados>\n{"texto": "Comentário com marcas", "numero": 3}\n</dados>'}],
        "text": {"format": {"type": "json_schema", "name": "formato_teste", "strict": True, "schema": ESQUEMA}},
        "max_output_tokens": 1500, "store": False, "reasoning": {"effort": "low"}}
    # endereço da configuração; esforço vazio: sem `reasoning`
    monkeypatch.setattr(config(), "IA_BASE_URL", "https://proxy.interno/")
    monkeypatch.setattr(config(), "IA_ESFORCO_RAPIDO", "")
    openai.respostas.append(api_resposta(json.dumps({"x": "ok"}), uso=("321", -4)))
    assert ia_texto.gerar("formato_teste", "I", {}, ESQUEMA, "rapido")[1:3] == (0, 0)  # contagem estranha vale zero
    pedido = openai.pedidos[-1]
    assert str(pedido.url) == "https://proxy.interno/v1/responses"
    corpo = json.loads(pedido.content)
    assert corpo["model"] == "gpt-5-nano" and "reasoning" not in corpo


@pytest.mark.parametrize("resposta,tipo,tokens", [
    (httpx.Response(401, json={"error": {"code": "invalid_api_key"}}), "configuracao", (0, 0)),
    (httpx.Response(404, json={"error": {"code": "model_not_found"}}), "configuracao", (0, 0)),
    (httpx.Response(400, json={"error": {"code": "invalid_prompt"}}), "definitiva", (0, 0)),
    (httpx.Response(429, json={"error": {"code": "rate_limit_exceeded"}}), "transitoria", (0, 0)),
    (httpx.Response(500, text="erro"), "transitoria", (0, 0)),
    (httpx.Response(200, text="não é json"), "transitoria", (0, 0)),
    (httpx.ReadTimeout("tempo esgotado"), "transitoria", (0, 0)),
    (httpx.ConnectError("sem rede"), "transitoria", (0, 0)),
    (api_resposta("isto não é JSON"), "transitoria", (321, 45)),
    (api_resposta("[1, 2]"), "transitoria", (321, 45)),
    (api_resposta("{}", status="incomplete"), "transitoria", (321, 45)),
    ({"status": "completed", "output": [{"type": "message", "content": [{"type": "refusal", "refusal": "Não."}]}],
      "usage": {"input_tokens": 10, "output_tokens": 2}}, "definitiva", (10, 2)),
    ({"status": "completed", "output": []}, "transitoria", (0, 0)),
])
def test_falhas_da_openai(openai, resposta, tipo, tokens):
    openai.respostas.append(resposta)
    with pytest.raises(ia_texto.Falha) as erro:
        ia_texto.gerar("formato_teste", "Instruções.", {"texto": "SIGILOSO"}, ESQUEMA, "equilibrado")
    assert erro.value.tipo == tipo and (erro.value.tokens_entrada, erro.value.tokens_saida) == tokens
    assert isinstance(erro.value, ia.FalhaIA) and "SIGILOSO" not in erro.value.detalhe and CHAVE not in str(erro.value)
    # 400 de parâmetro (não `invalid_prompt`): configuração que conta tentativa
    openai.respostas.append(httpx.Response(400, json={"error": {"code": "unsupported_value"}}))
    with pytest.raises(ia_texto.Falha) as erro:
        ia_texto.gerar("formato_teste", "I", {}, ESQUEMA, None)
    assert (erro.value.tipo, erro.value.conta_tentativa) == ("configuracao", True)


def test_sem_ia_na_plataforma(monkeypatch):
    monkeypatch.setattr(config(), "IA_PROVEDOR", "desligado")
    with pytest.raises(ia_texto.Falha) as erro:
        ia_texto.gerar("formato_teste", "I", {}, ESQUEMA, None)
    assert erro.value.tipo == "configuracao"


# ---- provedor de memória ----------------------------------------------------------------------------------

def test_memoria_programada_e_padrao():
    mem = ia_texto.memoria
    mem.programar({"x": "programado"}, "transitoria", ia_texto.resposta("texto livre"))
    assert ia_texto.gerar("formato_teste", "I", {"a": 1}, ESQUEMA, None, 7)[0] == {"x": "programado"}
    with pytest.raises(ia_texto.Falha) as erro:
        ia_texto.gerar("formato_teste", "I", {}, ESQUEMA, None)
    assert erro.value.tipo == "transitoria"
    with pytest.raises(ia_texto.Falha):
        ia_texto.gerar("formato_teste", "I", {}, ESQUEMA, None)  # "texto livre" não é JSON
    assert mem.tempos == [7, 45, 45] and len(mem.corpos) == 3
    assert ia_texto.dados_da_mensagem(mem.corpos[0]["input"][0]["content"]) == {"a": 1}
    # sem programa e sem padrão registrado para o formato: {}
    assert ia_texto.gerar("formato_sem_padrao", "I", {}, ESQUEMA, None)[0] == {}
    # os padrões registrados pelos módulos da etapa 5d
    assert {"resumo_painel", "parecer_relatorios", "passos_acao"} <= set(ia_texto.PADROES_MEMORIA)


def test_marcas_do_teste_integrado(monkeypatch):
    esperas: list[float] = []
    monkeypatch.setattr(ia_texto.relogio_real, "sleep", esperas.append)
    with pytest.raises(ia_texto.Falha) as erro:
        ia_texto.gerar("passos_acao", "I", {"comentario": "Cliente bravo [ia:falha]"}, ESQUEMA, None)
    assert erro.value.tipo == "transitoria"
    with pytest.raises(ia_texto.Falha) as erro:
        ia_texto.gerar("formato_teste", "Conta [ia:recusa]", {}, ESQUEMA, None)
    assert erro.value.tipo == "definitiva"
    assert ia_texto.gerar("formato_teste", "I", {"t": "devagar [ia:demora=5]"}, ESQUEMA, None)[0] == {}
    assert ia_texto.gerar("formato_teste", "I", {"t": "[ia:demora=999]"}, ESQUEMA, None)[0] == {}
    assert esperas == [5, 30]

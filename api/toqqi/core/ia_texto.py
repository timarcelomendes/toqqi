"""Chamada única com formato fixo (etapa 5d) — o resumo do painel, o parecer dos relatórios e os passos das ações — e
os níveis de modelo e estilos da conta (Configurações › IA), usados também pelo assistente (`core.ia_conversa`).

`gerar(nome_formato, instrucoes, dados, esquema, nivel, tempo_limite)`: `POST {IA_BASE_URL}/v1/responses` com
`model` e `reasoning` do nível (`modelo_do_nivel`), `instructions`, `input` (uma mensagem do usuário com o JSON dos
dados entre <dados> e </dados>; as marcas que aparecerem dentro dos textos saem, para um comentário não fechar os
dados), `text.format` (JSON Schema estrito), `max_output_tokens` 1500 e `store: false`, sem SDK e sem seguir
redirecionamento (como o adaptador da 4b, `core.ia`, de onde vêm o `transporte` e a classificação dos erros HTTP).
Devolve (conteúdo, tokens de entrada, tokens de saída, modelo): o conteúdo é o objeto JSON devolvido, como veio — os
limites e a limpeza do texto ficam com quem chamou. Tempo padrão: 45 s.

Falhas (`Falha`, um `ia.FalhaIA` que leva os tokens já gastos): as do adaptador da 4b (`ia._erro_http`: 401/403/404
configuração; os outros 4xx, menos 408/409/429, configuração com tentativa; 429, 5xx, 408 e 409 transitória; 400
`invalid_prompt` definitiva), rede e tempo esgotado (transitória), `refusal` (definitiva), resposta incompleta, sem
texto, JSON inválido ou que não é um objeto (transitória). O log nunca leva os dados, o texto nem a chave.

Níveis (§5.2): rapido = IA_MODELO_RAPIDO / IA_ESFORCO_RAPIDO; equilibrado = IA_MODELO_EQUILIBRADO /
IA_ESFORCO_EQUILIBRADO (vazios = IA_ASSISTENTE_MODELO / IA_ASSISTENTE_ESFORCO); detalhado = IA_MODELO_DETALHADO /
IA_ESFORCO_DETALHADO. Esforço vazio = não manda `reasoning`; modelo vazio = o do assistente; nível desconhecido vale
como equilibrado. Cada nível gasta `analises` da cota do plano por geração (resumo, parecer) ou pergunta ao
assistente (`analises_do_nivel`): 1 no rápido e no equilibrado, 2 no mais detalhado (decisão de 03/10: o gpt-5 custa
à Toqqi umas 5 vezes o gpt-5-mini). Estilos (§5.3): uma linha a mais no fim das instruções (nenhuma no equilibrado).

Provedor `memoria` (testes e teste integrado), como o do assistente: `memoria.programar(...)` enfileira as próximas
saídas — um dict (o conteúdo, que vira o texto JSON da resposta), uma resposta inteira (dict com `output`, ex.:
`resposta("não é JSON")`), uma falha (tipo em texto, `ia.FalhaIA` ou exceção do httpx) ou outra exceção (sobe como
veio) — e `memoria.corpos` guarda o que foi enviado (`memoria.tempos`, o tempo limite de cada chamada). Sem programa,
responde pelo padrão registrado para o formato (`PADROES_MEMORIA`, montado a partir dos números recebidos). Para o
teste integrado (a API em outro processo, sem como chamar `programar`), marcas no texto enviado (instruções ou dados,
ex.: num comentário de cliente ou no nome da conta): `[ia:falha]` = falha transitória, `[ia:recusa]` = a IA recusa e
`[ia:demora=N]` = responde depois de N segundos (até 30).
"""
import copy
import itertools
import json
import re
import time as relogio_real
from collections.abc import Callable
from dataclasses import dataclass, field

import httpx

from toqqi.core import ia
from toqqi.core.config import config

TEMPO_LIMITE = 45  # segundos por chamada
MAX_SAIDA = 1500
TOKENS_MEMORIA = (200, 50)  # (entrada, saída) de cada chamada ao provedor de memória
_MARCAS = re.compile(r"<\s*/?\s*dados\s*>", re.IGNORECASE)


# ---- níveis de modelo e estilos (§5.2 e §5.3) -------------------------------------------------

@dataclass(frozen=True)
class Opcao:
    valor: str
    rotulo: str
    descricao: str


@dataclass(frozen=True)
class Nivel(Opcao):
    """Um nível de modelo, com as análises da cota do plano que cada geração ou pergunta gasta nele."""
    analises: int = 1


MODELOS = (
    Nivel("rapido", "Rápido", "Respostas curtas e rápidas. Gasta 1 análise da cota.", analises=1),
    Nivel("equilibrado", "Equilibrado", "O padrão: bom para o dia a dia. Gasta 1 análise da cota.", analises=1),
    Nivel("detalhado", "Mais detalhado", "Análises mais cuidadosas; pode demorar mais. Gasta 2 análises da cota.",
          analises=2),
)
ESTILOS = (
    Opcao("objetiva", "Objetiva", "Frases curtas, só o essencial."),
    Opcao("equilibrada", "Equilibrada", "Claro e cordial (padrão)."),
    Opcao("criativa", "Criativa", "Tom mais próximo e ideias práticas."),
)
NIVEIS = tuple(o.valor for o in MODELOS)
VALORES_ESTILO = tuple(o.valor for o in ESTILOS)
NIVEL_PADRAO = "equilibrado"
ESTILO_PADRAO = "equilibrada"
LINHAS_ESTILO = {
    "objetiva": "Estilo: objetivo. Frases curtas e diretas, só o essencial, sem adjetivos.",
    "criativa": "Estilo: próximo e caloroso. Proponha ideias práticas e criativas, sem inventar dados.",
}


def nivel_valido(nivel: str | None) -> str:
    return nivel if nivel in NIVEIS else NIVEL_PADRAO


def modelo_do_nivel(nivel: str | None) -> tuple[str, str]:
    """(modelo, esforço) do nível; esforço vazio = não manda `reasoning`."""
    cfg = config()
    assistente = cfg.IA_ASSISTENTE_MODELO.strip()
    nivel = nivel_valido(nivel)
    if nivel == "rapido":
        return cfg.IA_MODELO_RAPIDO.strip() or assistente, cfg.IA_ESFORCO_RAPIDO.strip()
    if nivel == "detalhado":
        return cfg.IA_MODELO_DETALHADO.strip() or assistente, cfg.IA_ESFORCO_DETALHADO.strip()
    return (cfg.IA_MODELO_EQUILIBRADO.strip() or assistente,
            cfg.IA_ESFORCO_EQUILIBRADO.strip() or cfg.IA_ASSISTENTE_ESFORCO.strip())


def aplicar_nivel(corpo: dict, nivel: str | None) -> dict:
    """Põe no corpo da chamada o `model` e o `reasoning` do nível (sem esforço, tira o `reasoning`)."""
    modelo, esforco = modelo_do_nivel(nivel)
    corpo["model"] = modelo
    corpo.pop("reasoning", None)
    if esforco:
        corpo["reasoning"] = {"effort": esforco}
    return corpo


def com_estilo(instrucoes: str, estilo: str | None) -> str:
    """As instruções com a linha do estilo no fim (o equilibrado, ou um estilo desconhecido, não muda nada)."""
    linha = LINHAS_ESTILO.get(estilo or "")
    return f"{instrucoes}\n\n{linha}" if linha else instrucoes


def rotulo_do_nivel(nivel: str | None) -> str:
    return next(o.rotulo for o in MODELOS if o.valor == nivel_valido(nivel))


def analises_do_nivel(nivel: str | None) -> int:
    """Análises da cota do plano que uma geração (resumo, parecer) ou uma pergunta ao assistente gasta no nível."""
    return next(o.analises for o in MODELOS if o.valor == nivel_valido(nivel))


def opcoes_json(opcoes: tuple[Opcao, ...]) -> list[dict]:
    """As opções como a tela recebe (GET /conta/ia); os níveis de modelo levam também `analises`."""
    return [{"valor": o.valor, "rotulo": o.rotulo, "descricao": o.descricao,
             **({"analises": o.analises} if isinstance(o, Nivel) else {})} for o in opcoes]


# ---- corpo da chamada ---------------------------------------------------------------------------

def _sem_marcas(valor):
    if isinstance(valor, str):
        return " ".join(ia.tirar_marcas(valor, _MARCAS).split()) if _MARCAS.search(valor) else valor
    if isinstance(valor, dict):
        return {k: _sem_marcas(v) for k, v in valor.items()}
    if isinstance(valor, (list, tuple)):
        return [_sem_marcas(v) for v in valor]
    return valor


def mensagem(dados: dict) -> str:
    """O conteúdo da mensagem do usuário: o JSON dos dados entre <dados> e </dados>."""
    return "<dados>\n" + json.dumps(_sem_marcas(dados), ensure_ascii=False, default=str) + "\n</dados>"


def dados_da_mensagem(texto: str) -> dict:
    """O inverso de `mensagem` (provedor de memória e testes)."""
    miolo = texto.strip().removeprefix("<dados>").removesuffix("</dados>")
    return json.loads(miolo)


def corpo_da_chamada(nome_formato: str, instrucoes: str, dados: dict, esquema: dict, nivel: str | None) -> dict:
    corpo = {
        "model": "",
        "instructions": instrucoes,
        "input": [{"role": "user", "content": mensagem(dados)}],
        "text": {"format": {"type": "json_schema", "name": nome_formato, "strict": True, "schema": esquema}},
        "max_output_tokens": MAX_SAIDA,
        "store": False,
    }
    return aplicar_nivel(corpo, nivel)


# ---- falhas e leitura ---------------------------------------------------------------------------

class Falha(ia.FalhaIA):
    """Falha da chamada (tipos de `ia.FalhaIA`), com os tokens já gastos: uma resposta inútil (recusa, incompleta, JSON
    inválido) também é cobrada."""

    def __init__(self, tipo: str, detalhe: str, conta_tentativa: bool = False, tokens: tuple[int, int] = (0, 0)):
        super().__init__(tipo, detalhe, conta_tentativa)
        self.tokens_entrada, self.tokens_saida = tokens


def _ler(dados: dict, modelo_pedido: str) -> tuple[dict, int, int, str]:
    uso = dados.get("usage") if isinstance(dados.get("usage"), dict) else {}
    tokens = (ia._contagem(uso.get("input_tokens")), ia._contagem(uso.get("output_tokens")))

    def falha(tipo: str, detalhe: str) -> Falha:
        return Falha(tipo, detalhe, tokens=tokens)

    status = dados.get("status")
    if status == "incomplete":
        raise falha("transitoria", "resposta incompleta")
    if status in ("failed", "cancelled"):
        raise falha("transitoria", f"resposta {status}")
    texto = None
    for item in dados.get("output") or []:
        if not isinstance(item, dict) or item.get("type") != "message":
            continue
        partes = [p for p in item.get("content") or [] if isinstance(p, dict)]
        if any(p.get("type") == "refusal" for p in partes):
            raise falha("definitiva", "a IA recusou o pedido")
        textos = [p["text"] for p in partes if p.get("type") == "output_text" and isinstance(p.get("text"), str)]
        if textos:
            texto = "".join(textos)
    if texto is None:
        raise falha("transitoria", "resposta sem texto")
    try:
        conteudo = json.loads(texto)
    except ValueError:
        raise falha("transitoria", "JSON inválido") from None
    if not isinstance(conteudo, dict):
        raise falha("transitoria", "resposta fora do formato combinado")
    modelo = dados.get("model") if isinstance(dados.get("model"), str) else modelo_pedido
    return conteudo, tokens[0], tokens[1], " ".join(ia.sem_controle(modelo).split())[:100]


def _openai(corpo: dict, tempo_limite: float) -> dict:
    cfg = config()
    try:
        with httpx.Client(timeout=tempo_limite, follow_redirects=False, transport=ia.transporte) as c:
            r = c.post(f"{cfg.IA_BASE_URL.rstrip('/')}/v1/responses", json=corpo,
                       headers={"Authorization": f"Bearer {cfg.OPENAI_API_KEY.strip()}"})
    except httpx.TimeoutException:
        raise ia.FalhaIA("transitoria", "tempo esgotado") from None
    except httpx.HTTPError as e:
        raise ia.FalhaIA("transitoria", f"falha de rede ({type(e).__name__})") from None
    if r.status_code >= 400:
        raise ia._erro_http(r)
    try:
        dados = r.json()
    except ValueError:
        raise ia.FalhaIA("transitoria", "resposta que não é JSON") from None
    if not isinstance(dados, dict):
        raise ia.FalhaIA("transitoria", "resposta que não é um objeto JSON")
    return dados


def _provedor() -> Callable[[dict, float], dict]:
    if config().IA_PROVEDOR == "memoria":
        return memoria.responder
    if not ia.disponivel():
        raise Falha("configuracao", "IA desligada ou sem chave")
    return _openai


def gerar(nome_formato: str, instrucoes: str, dados: dict, esquema: dict, nivel: str | None,
          tempo_limite: float = TEMPO_LIMITE) -> tuple[dict, int, int, str]:
    """Uma chamada: (conteúdo, tokens de entrada, tokens de saída, modelo). Levanta `Falha`; outra exceção (do
    provedor de memória programado) sobe como veio."""
    chamar = _provedor()
    corpo = corpo_da_chamada(nome_formato, instrucoes, dados, esquema, nivel)
    try:
        resposta_ = chamar(corpo, tempo_limite)
    except Falha:
        raise
    except ia.FalhaIA as falha:
        raise Falha(falha.tipo, falha.detalhe, falha.conta_tentativa) from None
    return _ler(resposta_, corpo["model"])


# ---- memória (testes e teste integrado) ---------------------------------------------------------

_ids = itertools.count(1)
_DEMORA = re.compile(r"\[ia:demora=(\d{1,3})\]")
MAX_DEMORA = 30
PADROES_MEMORIA: dict[str, Callable[[dict], dict]] = {}  # nome do formato → conteúdo a partir dos dados


def resposta(conteudo: dict | str, uso: tuple[int, int] = TOKENS_MEMORIA, **extra) -> dict:
    """Resposta inteira da Responses API com uma mensagem: `conteudo` dict vira o texto JSON; texto vai como está."""
    texto = conteudo if isinstance(conteudo, str) else json.dumps(conteudo, ensure_ascii=False)
    n = next(_ids)
    return {"id": f"resp_mem_{n}", "object": "response", "status": "completed", "model": "memoria",
            "output": [{"type": "message", "id": f"msg_mem_{n}", "role": "assistant", "status": "completed",
                        "content": [{"type": "output_text", "text": texto, "annotations": []}]}],
            "usage": {"input_tokens": uso[0], "output_tokens": uso[1]}, **extra}


def recusa(texto: str = "Não posso ajudar com isso.") -> dict:
    n = next(_ids)
    return {"id": f"resp_mem_{n}", "object": "response", "status": "completed", "model": "memoria",
            "output": [{"type": "message", "id": f"msg_mem_{n}", "role": "assistant", "status": "completed",
                        "content": [{"type": "refusal", "refusal": texto}]}],
            "usage": {"input_tokens": TOKENS_MEMORIA[0], "output_tokens": 5}}


@dataclass
class Memoria:
    """Provedor dos testes: `programar` as próximas saídas; `corpos` = o que foi enviado; `tempos` = o tempo limite de
    cada chamada."""
    corpos: list[dict] = field(default_factory=list)
    tempos: list[float] = field(default_factory=list)
    programa: list = field(default_factory=list)

    def programar(self, *saidas) -> None:
        self.programa.extend(saidas)

    def limpar(self) -> None:
        self.corpos.clear()
        self.tempos.clear()
        self.programa.clear()

    def responder(self, corpo: dict, tempo_limite: float) -> dict:
        self.corpos.append(copy.deepcopy(corpo))
        self.tempos.append(tempo_limite)
        saida = self.programa.pop(0) if self.programa else _padrao(corpo)
        if isinstance(saida, str):
            raise ia.FalhaIA(saida, f"falha programada ({saida})")
        if isinstance(saida, ia.FalhaIA):
            raise saida
        if isinstance(saida, httpx.HTTPError):  # como o adaptador da OpenAI trata
            raise ia.FalhaIA("transitoria", "tempo esgotado" if isinstance(saida, httpx.TimeoutException)
                             else f"falha de rede ({type(saida).__name__})")
        if isinstance(saida, BaseException):
            raise saida
        if isinstance(saida, dict) and "output" in saida:
            return saida
        return resposta(saida)


memoria = Memoria()


def _padrao(corpo: dict) -> dict:
    """Sem programa: as marcas do teste integrado e, depois, o padrão do formato (montado a partir dos dados)."""
    texto = "\n".join([corpo.get("instructions") or ""] + [
        i.get("content") for i in corpo.get("input") or [] if isinstance(i, dict) and isinstance(i.get("content"), str)])
    demora = _DEMORA.search(texto)
    if demora:
        relogio_real.sleep(min(int(demora.group(1)), MAX_DEMORA))
    if "[ia:falha]" in texto:
        raise ia.FalhaIA("transitoria", "falha pedida pelo texto ([ia:falha])")
    if "[ia:recusa]" in texto:
        return recusa()
    nome = ((corpo.get("text") or {}).get("format") or {}).get("name")
    padrao = PADROES_MEMORIA.get(nome)
    if padrao is None:
        return {}
    entrada = next((i.get("content") for i in corpo.get("input") or [] if isinstance(i, dict)), "")
    return padrao(dados_da_mensagem(entrada))

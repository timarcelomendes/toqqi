"""Conversa com a IA usando ferramentas (assistente, etapa 5b): OpenAI Responses API por httpx, sem SDK, como o
adaptador da 4b (`core.ia`, de onde vêm o `transporte`, a classificação dos erros HTTP e a disponibilidade).

Cada chamada: `POST {IA_BASE_URL}/v1/responses` com `model` e `reasoning` do nível da conta (etapa 5d,
`ia_texto.modelo_do_nivel`: o equilibrado, padrão, usa IA_ASSISTENTE_MODELO e IA_ASSISTENTE_ESFORCO; esforço vazio =
não manda `reasoning`), `instructions`, `input` (o histórico como mensagens {role, content} e a pergunta), `tools`
(funções em modo estrito), `tool_choice`, `parallel_tool_calls: true`, `text.format` (JSON Schema estrito),
`max_output_tokens: 2000`, `store: false` e `include: ["reasoning.encrypted_content"]`: a OpenAI não guarda nada e o
raciocínio volta cifrado para seguir no laço.

Laço: se a saída traz itens `function_call` ({call_id, name, arguments}), cada um é executado por `executar(nome,
argumentos)` (um dict; problema de uso já vem como {"erro": …}), e o `input` ganha TODOS os itens da saída, como
vieram (inclusive os `reasoning`, com o conteúdo cifrado), mais um {"type": "function_call_output", call_id, output:
"<json>"} por chamada; e chama de novo. Até 4 consultas por pergunta: atingidas as 4, as chamadas seguintes já vão
com `tool_choice: "none"` (se ainda vier alguma consulta, a saída dela é um erro pedindo para responder com o que já
tem); no máximo 5 chamadas, e a última sempre vai com `tool_choice: "none"`. Termina com uma `message` com
`output_text` (o JSON do formato) ou com `refusal` (`Resultado.recusa`).

Tempo: 30 s por chamada e 60 s no total. Falhas (`Falha`, com as consultas e os tokens até ali): as do adaptador
da 4b (`ia._erro_http`: 401/403/404, outros 4xx, 429, 5xx), rede, tempo, `status` incompleto, texto que não é o
JSON do formato, ou nenhuma resposta até a última chamada. Qualquer outra exceção (inesperada, ex.: de uma
ferramenta) sobe como veio, com o andamento até ali (consultas e tokens) em `erro.andamento`, para quem chamou somar
os tokens já gastos.

Provedor `memoria` (testes e teste integrado): `memoria.programar(...)` enfileira as próximas saídas — um item
(`chamada(...)`, `final(...)`, `mensagem(...)`, `recusa(...)`), uma lista de itens (chamadas em paralelo), uma resposta
inteira (dict com `output`) ou uma falha (tipo em texto, `ia.FalhaIA` ou exceção do httpx) — e `memoria.corpos`
guarda o que foi enviado. Sem programa, responde por um padrão simples de palavras (`_padrao`). `desligado` (ou
`openai` sem chave) → indisponível.
"""
import contextlib
import copy
import itertools
import json
import re
import time as relogio_real
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date, timedelta

import httpx

from toqqi.core import ia, ia_texto, relogio
from toqqi.core.config import config
from toqqi.core.texto import sem_acento

TEMPO_CHAMADA = 30  # segundos por chamada
TEMPO_TOTAL = 60  # segundos por pergunta
MAX_CONSULTAS = 4
MAX_CHAMADAS = 5
MAX_SAIDA = 2000
NOME_FORMATO = "resposta_assistente"
LIMITE_CONSULTAS = "Limite de consultas desta pergunta atingido. Responda com o que já tem."

Executar = Callable[[str, dict], dict]


@dataclass
class Resultado:
    resposta: str = ""
    sugestoes: list[str] = field(default_factory=list)
    atalhos: list[str] = field(default_factory=list)
    recusa: bool = False
    consultas: int = 0
    chamadas: int = 0
    tokens_entrada: int = 0
    tokens_saida: int = 0


class Falha(Exception):
    """A conversa não chegou a uma resposta. `tipo`: configuracao | transitoria | definitiva (como `ia.FalhaIA`);
    `detalhe` nunca leva a pergunta, a resposta, os dados nem a chave."""

    def __init__(self, tipo: str, detalhe: str, andamento: Resultado | None = None):
        super().__init__(detalhe)
        andamento = andamento or Resultado()
        self.tipo = tipo
        self.detalhe = detalhe
        self.consultas = andamento.consultas
        self.chamadas = andamento.chamadas
        self.tokens_entrada = andamento.tokens_entrada
        self.tokens_saida = andamento.tokens_saida


# ---- corpo da chamada -------------------------------------------------------------------

def corpo_da_chamada(instrucoes: str, entrada: list, ferramentas: list[dict], esquema: dict,
                     tool_choice: str, nivel: str | None = None) -> dict:
    corpo = {
        "model": "",
        "instructions": instrucoes,
        "input": entrada,
        "tools": ferramentas,
        "tool_choice": tool_choice,
        "parallel_tool_calls": True,
        "text": {"format": {"type": "json_schema", "name": NOME_FORMATO, "strict": True, "schema": esquema}},
        "max_output_tokens": MAX_SAIDA,
        "store": False,
        "include": ["reasoning.encrypted_content"],
    }
    return ia_texto.aplicar_nivel(corpo, nivel)  # model e reasoning do nível da conta (sem nível: equilibrado)


# ---- OpenAI ---------------------------------------------------------------------------------

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


# ---- leitura da saída -----------------------------------------------------------------------

def _itens(dados: dict) -> list[dict]:
    status = dados.get("status")
    if status == "incomplete":
        raise ia.FalhaIA("transitoria", "resposta incompleta")
    if status in ("failed", "cancelled"):
        raise ia.FalhaIA("transitoria", f"resposta {status}")
    saida = dados.get("output")
    if not isinstance(saida, list):
        raise ia.FalhaIA("transitoria", "resposta sem saída")
    return [item for item in saida if isinstance(item, dict)]


def _mensagem(itens: list[dict]) -> tuple[bool, str | None]:
    """(recusou, texto da última mensagem)."""
    recusou, texto = False, None
    for item in itens:
        if item.get("type") != "message":
            continue
        partes = [p for p in item.get("content") or [] if isinstance(p, dict)]
        recusou = recusou or any(p.get("type") == "refusal" for p in partes)
        textos = [p["text"] for p in partes if p.get("type") == "output_text" and isinstance(p.get("text"), str)]
        if textos:
            texto = "".join(textos)
    return recusou, texto


def _formato(texto: str) -> tuple[str, list[str], list[str]]:
    """{resposta, sugestoes, atalhos} do texto da mensagem; fora do formato → falha transitória."""
    try:
        dados = json.loads(texto)
    except ValueError:
        raise ia.FalhaIA("transitoria", "JSON inválido") from None
    if not isinstance(dados, dict) or not isinstance(dados.get("resposta"), str) \
            or not isinstance(dados.get("sugestoes"), list) or not isinstance(dados.get("atalhos"), list):
        raise ia.FalhaIA("transitoria", "resposta fora do formato combinado")
    return (dados["resposta"], [s for s in dados["sugestoes"] if isinstance(s, str)],
            [a for a in dados["atalhos"] if isinstance(a, str)])


def _consultar(executar: Executar, item: dict) -> dict:
    try:
        argumentos = json.loads(item.get("arguments") or "{}")
    except (TypeError, ValueError):
        return {"erro": "Argumentos inválidos."}
    if not isinstance(argumentos, dict) or not isinstance(item.get("name"), str):
        return {"erro": "Argumentos inválidos."}
    return executar(item["name"], argumentos)


# ---- conversa ---------------------------------------------------------------------------------

def conversar(instrucoes: str, mensagens: list[dict], pergunta: str, ferramentas: list[dict], esquema: dict,
              executar: Executar, nivel: str | None = None) -> Resultado:
    """Uma pergunta (com o histórico em `mensagens`, já no formato {role, content}), no nível de modelo da conta.
    Levanta `Falha`; outra exceção sobe com `andamento` (o `Resultado` até ali, com os tokens já gastos)."""
    chamar = _provedor()
    entrada: list = [*mensagens, {"role": "user", "content": pergunta}]
    andamento = Resultado()
    inicio = relogio_real.monotonic()
    try:
        for n in range(1, MAX_CHAMADAS + 1):
            restante = TEMPO_TOTAL - (relogio_real.monotonic() - inicio)
            if restante <= 0:
                raise ia.FalhaIA("transitoria", "tempo total esgotado")
            ultima = n == MAX_CHAMADAS
            sem_consultas = ultima or andamento.consultas >= MAX_CONSULTAS  # já usou as 4: agora é responder
            corpo = corpo_da_chamada(instrucoes, entrada, ferramentas, esquema, "none" if sem_consultas else "auto",
                                     nivel)
            dados = chamar(corpo, min(TEMPO_CHAMADA, restante))
            andamento.chamadas += 1
            uso = dados.get("usage") if isinstance(dados.get("usage"), dict) else {}
            andamento.tokens_entrada += ia._contagem(uso.get("input_tokens"))
            andamento.tokens_saida += ia._contagem(uso.get("output_tokens"))
            itens = _itens(dados)
            funcoes = [item for item in itens if item.get("type") == "function_call"]
            if funcoes and not ultima:
                entrada.extend(itens)  # todos, como vieram (os `reasoning` levam o raciocínio cifrado)
                for item in funcoes:
                    andamento.consultas += 1
                    saida = (_consultar(executar, item) if andamento.consultas <= MAX_CONSULTAS
                             else {"erro": LIMITE_CONSULTAS})
                    entrada.append({"type": "function_call_output", "call_id": item.get("call_id"),
                                    "output": json.dumps(saida, ensure_ascii=False, default=str)})
                continue
            recusou, texto = _mensagem(itens)
            if recusou:
                andamento.recusa = True
                return andamento
            if texto is None:
                raise ia.FalhaIA("transitoria", "resposta sem texto")
            andamento.resposta, andamento.sugestoes, andamento.atalhos = _formato(texto)
            return andamento
        raise ia.FalhaIA("transitoria", "sem resposta depois da última chamada")  # não chega aqui
    except ia.FalhaIA as falha:
        raise Falha(falha.tipo, falha.detalhe, andamento) from None
    except Exception as erro:  # inesperada: sobe como veio, levando os tokens já gastos
        with contextlib.suppress(AttributeError):
            erro.andamento = andamento
        raise


# ---- memória (testes e teste integrado) --------------------------------------------------------

_ids = itertools.count(1)
TOKENS_MEMORIA = (100, 20)  # (entrada, saída) de cada chamada ao provedor de memória


def chamada(ferramenta: str, /, **argumentos) -> dict:
    """Item `function_call` (como a OpenAI devolve) da `ferramenta` com os `argumentos`."""
    n = next(_ids)
    return {"type": "function_call", "id": f"fc_mem_{n}", "call_id": f"call_mem_{n}", "name": ferramenta,
            "arguments": json.dumps(argumentos, ensure_ascii=False), "status": "completed"}


def mensagem(texto: str) -> dict:
    """Item `message` com `output_text` (texto livre)."""
    return {"type": "message", "id": f"msg_mem_{next(_ids)}", "role": "assistant", "status": "completed",
            "content": [{"type": "output_text", "text": texto, "annotations": []}]}


def final(resposta: str, sugestoes=(), atalhos=()) -> dict:
    """Item `message` com o JSON do formato (resposta final)."""
    return mensagem(json.dumps({"resposta": resposta, "sugestoes": list(sugestoes), "atalhos": list(atalhos)},
                               ensure_ascii=False))


def recusa(texto: str = "Não posso ajudar com isso.") -> dict:
    return {"type": "message", "id": f"msg_mem_{next(_ids)}", "role": "assistant", "status": "completed",
            "content": [{"type": "refusal", "refusal": texto}]}


@dataclass
class Memoria:
    """Provedor dos testes: `programar` as próximas saídas; `corpos` = o que foi enviado; `tempos` = tempo limite de
    cada chamada. Cada resposta traz um item `reasoning` (com conteúdo "cifrado") antes dos itens programados."""
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
        n = next(_ids)
        return {"id": f"resp_mem_{n}", "object": "response", "status": "completed", "model": "memoria",
                "output": [{"type": "reasoning", "id": f"rs_mem_{n}", "summary": [],
                            "encrypted_content": f"raciocinio-cifrado-{n}"},
                           *(saida if isinstance(saida, list) else [saida])],
                "usage": {"input_tokens": TOKENS_MEMORIA[0], "output_tokens": TOKENS_MEMORIA[1]}}


memoria = Memoria()


# ---- padrão por palavras (memória sem programa) ---------------------------------------------

_EMPRESA = re.compile(
    r"\b(?:do cliente|da cliente|da empresa|do|da)\s+(?P<nome>[^?!.,;:\n]+?)"
    r"(?=\s+(?:nos?|nas?|em|neste|nesta|deste|desta|este|esta|desde|entre|durante|at[ée]|de\s+\d|[úu]ltim[oa]s?|"
    r"hoje|ontem)\b|[?!.,;:\n]|$)", re.IGNORECASE)
_NAO_EMPRESA = {"mes", "ano", "dia", "semana", "trimestre", "semestre", "periodo", "cliente", "clientes", "empresa",
                "empresas"}
_SUGESTOES = ("O que os detratores disseram?", "Quais temas mais aparecem nas notas baixas?",
              "Quais clientes têm o NPS mais baixo?")


def _normal(texto: str) -> str:
    return " ".join(re.sub(r"[^a-z0-9]+", " ", sem_acento((texto or "").lower())).split())


def _br(iso: str | None) -> str:
    return date.fromisoformat(iso).strftime("%d/%m/%Y") if iso else "?"


def _periodo_da_pergunta(q: str, hoje: date) -> tuple[str | None, str | None]:
    """ "últimos N dias", "este mês" e "este ano"; o resto fica com o padrão da ferramenta (últimos 30 dias)."""
    achado = re.search(r"\bultimos? (\d{1,4}) dias?\b", q)
    if achado:
        return (hoje - timedelta(days=int(achado.group(1)) - 1)).isoformat(), hoje.isoformat()
    if re.search(r"\b(?:este|esse|neste|nesse) mes\b", q):
        return hoje.replace(day=1).isoformat(), hoje.isoformat()
    if re.search(r"\b(?:este|esse|neste|nesse) ano\b", q):
        return hoje.replace(month=1, day=1).isoformat(), hoje.isoformat()
    return None, None


def _empresa_da_pergunta(pergunta: str) -> str | None:
    for achado in _EMPRESA.finditer(pergunta):
        nome = " ".join(achado.group("nome").split())
        primeira = (_normal(nome).split() or [""])[0]
        if primeira and primeira not in _NAO_EMPRESA and not primeira.startswith("ultim"):
            return nome
    return None


def _consultas_feitas(entrada: list) -> dict:
    """{nome da ferramenta: saída (a última)} das consultas já feitas nesta pergunta."""
    nomes = {i.get("call_id"): i.get("name") for i in entrada
             if isinstance(i, dict) and i.get("type") == "function_call"}
    feitas = {}
    for item in entrada:
        if isinstance(item, dict) and item.get("type") == "function_call_output":
            try:
                feitas[nomes.get(item.get("call_id"))] = json.loads(item.get("output") or "null")
            except ValueError:
                feitas[nomes.get(item.get("call_id"))] = None
    return feitas


def _padrao(corpo: dict) -> dict:
    """Ajuda → buscar_ajuda; "NPS" → buscar_empresas (com "do cliente X"/"da X") e indicadores (ou ranking_empresas
    com "mais baixo"/"mais alto"); "comentário"/"detrator" → comentarios. Responde com os números das ferramentas."""
    entrada = corpo.get("input") or []
    pergunta = next((i.get("content") for i in reversed(entrada)
                     if isinstance(i, dict) and i.get("role") == "user" and isinstance(i.get("content"), str)), "")
    q = _normal(pergunta)
    feitas = _consultas_feitas(entrada)
    pode_consultar = corpo.get("tool_choice") != "none"
    proxima = _proximo_passo(pergunta, q, feitas)
    if isinstance(proxima, tuple):
        if pode_consultar:
            return chamada(proxima[0], **proxima[1])
        return final("Não consegui consultar os dados agora. Tente perguntar de outro jeito.", _SUGESTOES)
    return proxima


def _proximo_passo(pergunta: str, q: str, feitas: dict) -> dict | tuple[str, dict]:
    hoje = relogio.hoje()
    for saida in feitas.values():
        if isinstance(saida, dict) and isinstance(saida.get("erro"), str):
            return final(saida["erro"], _SUGESTOES)
    palavras = set(q.split())
    quer_comentarios = any(p.startswith(("comentari", "detrator", "disseram", "reclama")) for p in palavras)
    quer_numeros = "nps" in palavras or "csat" in palavras
    if not quer_comentarios and not quer_numeros:
        if "buscar_ajuda" in feitas:
            return _final_ajuda(feitas["buscar_ajuda"])
        return "buscar_ajuda", {"termo": pergunta[:200]}
    de, ate = _periodo_da_pergunta(q, hoje)
    empresa_id = None
    nome = _empresa_da_pergunta(pergunta)
    if nome:
        if "buscar_empresas" not in feitas:
            return "buscar_empresas", {"nome": nome}
        empresas = (feitas["buscar_empresas"] or {}).get("empresas") or []
        exatas = [e for e in empresas if _normal(e.get("nome")) == _normal(nome)]
        if not empresas:
            return final(f"Não encontrei nenhuma empresa com \"{nome}\" no nome.", _SUGESTOES, ["relatorios"])
        if len(empresas) > 1 and len(exatas) != 1:
            nomes = ", ".join(e["nome"] for e in empresas[:5])
            return final(f"Encontrei mais de uma empresa parecida: {nomes}. De qual delas você quer saber?",
                         [f"Qual o NPS da {e['nome']}?"[:80] for e in empresas[:3]])
        empresa_id = (exatas or empresas)[0]["id"]
    if quer_comentarios:
        if "comentarios" not in feitas:
            grupo = "detratores" if "detrator" in q else "todos"
            return "comentarios", {"empresa_id": empresa_id, "grupo": grupo, "de": de, "ate": ate, "limite": 5}
        return _final_comentarios(feitas["comentarios"])
    ordem = ("menor" if re.search(r"\b(?:mais baix|menor|pior)", q)
             else "maior" if re.search(r"\b(?:mais alt|maior|melhor)", q) else None)
    if ordem and empresa_id is None:
        if "ranking_empresas" not in feitas:
            return "ranking_empresas", {"ordem": ordem, "de": de, "ate": ate, "limite": 5}
        return _final_ranking(feitas["ranking_empresas"])
    if "indicadores" not in feitas:
        return "indicadores", {"empresa_id": empresa_id, "de": de, "ate": ate}
    return _final_indicadores(feitas["indicadores"])


def _periodo_texto(periodo: dict | None) -> str:
    periodo = periodo or {}
    return f"de {_br(periodo.get('de'))} a {_br(periodo.get('ate'))}"


def _final_indicadores(r: dict) -> dict:
    nome = f" da {r['empresa']['nome']}" if r.get("empresa") else ""
    nps, csat, anterior = r["nps"], r["csat"], r["anterior"]
    periodo = _periodo_texto(r.get("periodo"))
    if nps["valor"] is None:
        linhas = [f"Não há respostas de NPS{nome} {periodo}."]
    else:
        linhas = [f"O NPS{nome} {periodo} foi {nps['valor']}, com {nps['total']} respostas: "
                  f"{nps['promotores']} promotores, {nps['neutros']} neutros e {nps['detratores']} detratores."]
    if csat["total"]:
        linhas.append(f"CSAT: {csat['percentual']}% de satisfeitos ({csat['total']} respostas).")
    if anterior["nps"]["valor"] is not None:
        variacao = r.get("variacao")
        linhas.append(f"No período anterior ({_periodo_texto(anterior.get('periodo'))}) o NPS foi "
                      f"{anterior['nps']['valor']}, com {anterior['nps']['total']} respostas"
                      + (f"; variação de {variacao:+d} pontos." if isinstance(variacao, int) else "."))
    if r.get("amostra_pequena") and nps["total"]:
        linhas.append("Amostra pequena: menos de 20 respostas de NPS.")
    return final("\n".join(linhas), _SUGESTOES, ["relatorios" if r.get("empresa") else "inicio"])


def _final_ranking(r: dict) -> dict:
    itens = r.get("empresas") or []
    if not itens:
        return final(f"Nenhuma empresa teve {r.get('minimo_respostas', 3)} ou mais respostas de NPS "
                     f"{_periodo_texto(r.get('periodo'))}.", _SUGESTOES, ["relatorios"])
    linhas = [f"Empresas com {r.get('minimo_respostas', 3)} ou mais respostas de NPS "
              f"{_periodo_texto(r.get('periodo'))}:"]
    linhas += [f"- {e['nome']}: NPS {e['nps']} ({e['respostas']} respostas)" for e in itens]
    return final("\n".join(linhas), _SUGESTOES, ["relatorios"])


def _final_comentarios(r: dict) -> dict:
    itens = r.get("comentarios") or []
    periodo = _periodo_texto(r.get("periodo"))
    if not itens:
        return final(f"Não encontrei comentários {periodo}.", _SUGESTOES, ["respostas"])
    linhas = [f"Comentários mais recentes {periodo}:"]
    for c in itens:
        empresa = f" ({c['empresa']})" if c.get("empresa") else ""
        linhas.append(f"- {_br(c['data'])}, nota {c['nota']}{empresa}: {c['texto']}")
    return final("\n".join(linhas), _SUGESTOES, ["respostas"])


def _final_ajuda(r: dict) -> dict:
    secoes = (r or {}).get("secoes") or []
    if not secoes:
        return final("Não encontrei esse assunto na Ajuda. Veja os tópicos na tela Ajuda.",
                     ("Como importo meus contatos?",), ["ajuda"])
    s = secoes[0]
    atalhos = [a for a in (s.get("atalho"), "ajuda") if a]
    return final(f"{s['titulo']} ({s['topico']}):\n{ia.cortar(s['texto'], 1500)}",
                 [f"Mais sobre {x['titulo']}"[:80] for x in secoes[1:3]] or ["Como importo meus contatos?"], atalhos)

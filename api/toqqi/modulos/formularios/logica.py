"""Lógica dos formulários (etapa 5l, docs/api-etapa-5l.md §2): o mesmo motor do site (`web/src/pesquisa/logica.ts`).

Sem banco e sem dependências: a API usa ao receber a resposta (caminho, obrigatórias só no caminho e o final) e os dois
motores passam pelos mesmos casos (`docs/casos-logica-5l.json`).

- Item: pergunta, bloco `conteudo` ou `quebra_pagina`. `logica.mostrar_se` (grupo) esconde o item; `logica.pular`
  (regras, só perguntas) é avaliado depois do item e vale a 1ª regra verdadeira (`para` = id posterior ou "fim").
- Grupo: {juncao: "todas" | "qualquer", condicoes: [{fonte, op, valor}]}; null/ausente vale como verdadeiro (e o
  grupo sem condições também: o publicado nunca tem, a validação recusa).
- Sem resposta: fonte não respondida, fora do caminho (escondida ou pulada) ou com valor inválido para o tipo. Aí só
  `nao_respondida` é verdadeira; todo outro operador é falso (inclusive `diferente`, `nenhum_de`, `nao_contem` e
  `nao_inclui_nenhum`).
- Texto compara com `norm` (sem acento, minúsculas, espaços juntos); texto de número com `numero_do_texto`
  ("1.250,5" → 1250.5); data "AAAA-MM-DD" compara como texto.
"""
import math
import re
import unicodedata
from datetime import date
from typing import Any

TIPOS_PERGUNTA = ("nps", "csat", "estrelas", "escala", "texto_curto", "comentario", "escolha_unica",
                  "escolha_multipla", "sim_nao", "data")
TIPOS_NOTA = ("nps", "csat", "estrelas", "escala")
GRUPOS = {"nps": ("detrator", "neutro", "promotor"), "csat": ("insatisfeito", "neutro", "satisfeito"),
          "estrelas": ("insatisfeito", "neutro", "satisfeito")}
FIM = "fim"
JUNCOES = ("todas", "qualquer")
SEM_VALOR = ("respondida", "nao_respondida")
COMPARACOES = ("igual", "diferente", "menor", "menor_igual", "maior", "maior_igual", "entre")
OPERADORES_TEXTO = ("contem", "nao_contem", "igual", "diferente", "comeca_com", "termina_com")
# citação de uma resposta anterior (§2.7) num título, descrição ou HTML
RE_CITACAO = re.compile(r"\{\{([A-Za-z0-9_-]{1,32})\}\}")
_RE_DATA = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}")
_RE_NUMERO = re.compile(r"[+-]?([0-9]+(\.[0-9]*)?|\.[0-9]+)")
_RE_ESPACOS = re.compile(r"\s+")


def respondivel(tipo: Any) -> bool:
    """Pergunta que recebe resposta (não é bloco de conteúdo nem quebra de página)."""
    return tipo in TIPOS_PERGUNTA


# ---- normalização -------------------------------------------------------------------------

def norm(s: Any) -> str:
    """NFD, sem marcas combinantes, minúsculas, aparado e com os espaços juntos (§2.1)."""
    t = unicodedata.normalize("NFD", str(s))
    t = "".join(c for c in t if unicodedata.category(c) != "Mn").lower().strip()
    return _RE_ESPACOS.sub(" ", t)


def numero_do_texto(s: Any) -> float | None:
    """Texto de número (§2.1): com vírgula, tira os pontos e troca a vírgula por ponto ("1.250,5" → 1250.5); sem
    vírgula, usa como está ("12.5" → 12.5). Número de verdade passa direto. None se não for número."""
    if isinstance(s, bool):
        return None
    if isinstance(s, (int, float)):
        return float(s) if math.isfinite(s) else None
    if not isinstance(s, str):
        return None
    t = s.strip()
    if "," in t:
        t = t.replace(".", "").replace(",", ".")
    return float(t) if _RE_NUMERO.fullmatch(t) else None


def faixa(item: dict) -> tuple[int, int]:
    """Faixa da nota: NPS 0–10, CSAT e estrelas 1–5, escala do item (padrão 1–5)."""
    tipo = item.get("tipo")
    if tipo == "nps":
        return 0, 10
    if tipo in ("csat", "estrelas"):
        return 1, 5
    mn, mx = item.get("min", 1), item.get("max", 5)
    return (mn if isinstance(mn, int) else 1), (mx if isinstance(mx, int) else 5)


def grupo_da_nota(tipo: str | None, nota: int | None) -> str | None:
    """NPS: 0–6 detrator, 7–8 neutro, 9–10 promotor. CSAT e estrelas: 1–2 insatisfeito, 3 neutro, 4–5 satisfeito."""
    if tipo is None or nota is None or tipo not in GRUPOS:
        return None
    if tipo == "nps":
        return "detrator" if nota <= 6 else "neutro" if nota <= 8 else "promotor"
    return "insatisfeito" if nota <= 2 else "neutro" if nota == 3 else "satisfeito"


def _inteiro(v: Any) -> int | None:
    if isinstance(v, bool):
        return None
    if isinstance(v, int):
        return v
    if isinstance(v, float) and v.is_integer():
        return int(v)
    return None


def _numero(v: Any) -> float | None:
    if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v):
        return None
    return float(v)


def _data(v: Any) -> bool:
    if not isinstance(v, str) or not _RE_DATA.fullmatch(v):
        return False
    try:
        date.fromisoformat(v)
    except ValueError:
        return False
    return True


def e_numero(item: dict) -> bool:
    return item.get("tipo") == "texto_curto" and item.get("formato") == "numero"


def operadores(item: dict) -> tuple[str, ...]:
    """Operadores que valem para a pergunta-fonte (§2.2)."""
    tipo = item.get("tipo")
    if tipo in TIPOS_NOTA:
        return COMPARACOES + (("grupo_e",) if tipo in GRUPOS else ()) + SEM_VALOR
    if tipo == "escolha_unica":
        return ("um_de", "nenhum_de") + SEM_VALOR
    if tipo == "escolha_multipla":
        return ("inclui_algum", "inclui_todos", "nao_inclui_nenhum") + SEM_VALOR
    if tipo == "sim_nao":
        return ("igual",) + SEM_VALOR
    if tipo == "data":
        return COMPARACOES + SEM_VALOR
    if e_numero(item):
        return COMPARACOES + SEM_VALOR
    if tipo in ("texto_curto", "comentario"):
        return OPERADORES_TEXTO + SEM_VALOR
    return SEM_VALOR


def valor_respondido(item: dict, valor: Any) -> bool:
    """O valor conta como resposta da pergunta? (vazio ou inválido para o tipo = sem resposta, §2.3)"""
    tipo = item.get("tipo")
    opcoes = item.get("opcoes") if isinstance(item.get("opcoes"), list) else None
    if valor is None:
        return False
    if tipo in TIPOS_NOTA:
        n = _inteiro(valor)
        if n is None:
            return False
        mn, mx = faixa(item)
        return mn <= n <= mx
    if tipo in ("texto_curto", "comentario"):
        return isinstance(valor, str) and bool(valor.strip())
    if tipo == "escolha_unica":
        return isinstance(valor, str) and bool(valor) and (opcoes is None or valor in opcoes)
    if tipo == "escolha_multipla":
        return (isinstance(valor, list) and bool(valor) and all(isinstance(x, str) for x in valor)
                and (opcoes is None or all(x in opcoes for x in valor)))
    if tipo == "sim_nao":
        return isinstance(valor, bool)
    if tipo == "data":
        return _data(valor)
    return False


# ---- avaliação ------------------------------------------------------------------------------

def _comparar(op: str, x, alvo) -> bool:
    """x e alvo do mesmo tipo (números ou datas em texto); `entre` recebe [a, b]."""
    if op == "entre":
        return isinstance(alvo, (list, tuple)) and len(alvo) == 2 and alvo[0] <= x <= alvo[1]
    if op == "igual":
        return x == alvo
    if op == "diferente":
        return x != alvo
    if op == "menor":
        return x < alvo
    if op == "menor_igual":
        return x <= alvo
    if op == "maior":
        return x > alvo
    if op == "maior_igual":
        return x >= alvo
    return False


def _avaliar_numero(op: str, x: float, valor) -> bool:
    if op == "entre":
        if not isinstance(valor, (list, tuple)) or len(valor) != 2:
            return False
        a, b = _numero(valor[0]), _numero(valor[1])
        return a is not None and b is not None and _comparar(op, x, [a, b])
    alvo = _numero(valor)
    return alvo is not None and _comparar(op, x, alvo)


def _avaliar_data(op: str, x: str, valor) -> bool:
    if op == "entre":
        return (isinstance(valor, (list, tuple)) and len(valor) == 2 and all(isinstance(v, str) for v in valor)
                and _comparar(op, x, list(valor)))
    return isinstance(valor, str) and _comparar(op, x, valor)


def _avaliar_texto(op: str, x: str, valor) -> bool:
    if not isinstance(valor, str):
        return False
    a, b = norm(x), norm(valor)
    if op == "contem":
        return b in a
    if op == "nao_contem":
        return b not in a
    if op == "igual":
        return a == b
    if op == "diferente":
        return a != b
    if op == "comeca_com":
        return a.startswith(b)
    if op == "termina_com":
        return a.endswith(b)
    return False


def _lista(valor) -> list | None:
    return list(valor) if isinstance(valor, list) and valor else None


def avaliar_condicao(condicao: dict, valores: dict, itens_por_id: dict) -> bool:
    """Uma condição com as respostas de `valores` (só as de itens já no caminho)."""
    if not isinstance(condicao, dict):
        return False
    op = condicao.get("op")
    fonte = itens_por_id.get(condicao.get("fonte"))
    x = valores.get(condicao.get("fonte")) if fonte is not None else None
    respondida = fonte is not None and respondivel(fonte.get("tipo")) and valor_respondido(fonte, x)
    if op == "respondida":
        return respondida
    if op == "nao_respondida":
        return not respondida
    if not respondida or op not in operadores(fonte):
        return False
    valor = condicao.get("valor")
    tipo = fonte["tipo"]
    if tipo in TIPOS_NOTA:
        nota = _inteiro(x)
        if op == "grupo_e":
            grupos = _lista(valor)
            return grupos is not None and grupo_da_nota(tipo, nota) in grupos
        return _avaliar_numero(op, float(nota), valor)
    if tipo == "escolha_unica":
        opcoes = _lista(valor)
        return opcoes is not None and ((x in opcoes) if op == "um_de" else (x not in opcoes))
    if tipo == "escolha_multipla":
        opcoes = _lista(valor)
        if opcoes is None:
            return False
        if op == "inclui_algum":
            return any(o in x for o in opcoes)
        if op == "inclui_todos":
            return all(o in x for o in opcoes)
        return not any(o in x for o in opcoes)
    if tipo == "sim_nao":
        return isinstance(valor, bool) and x is valor
    if tipo == "data":
        return _avaliar_data(op, x, valor)
    if e_numero(fonte):
        n = numero_do_texto(x)
        return n is not None and _avaliar_numero(op, n, valor)
    return _avaliar_texto(op, x, valor)


def avaliar_grupo(grupo: dict | None, valores: dict, itens_por_id: dict) -> bool:
    """Grupo null/ausente (ou sem condições) é verdadeiro; `todas` = E, `qualquer` = OU."""
    if not isinstance(grupo, dict):
        return True
    condicoes = grupo.get("condicoes")
    if not isinstance(condicoes, list) or not condicoes:
        return True
    resultados = (avaliar_condicao(c, valores, itens_por_id) for c in condicoes)
    return any(resultados) if grupo.get("juncao") == "qualquer" else all(resultados)


def _logica(item: dict) -> dict:
    logica = item.get("logica")
    return logica if isinstance(logica, dict) else {}


def _por_id(itens: list[dict]) -> dict:
    return {it["id"]: it for it in itens if isinstance(it, dict) and isinstance(it.get("id"), str)}


def caminho(itens: list[dict], respostas: dict | None) -> list[str]:
    """Ids dos itens que a pessoa vê, em ordem, sem as quebras de página (§2.4). Só para frente, em uma passada."""
    respostas = respostas if isinstance(respostas, dict) else {}
    por_id = _por_id(itens)
    indice = {it["id"]: i for i, it in enumerate(itens) if isinstance(it, dict) and isinstance(it.get("id"), str)}
    vistos: list[str] = []
    valores: dict = {}
    i = 0
    while i < len(itens):
        it = itens[i]
        if not isinstance(it, dict) or it.get("tipo") == "quebra_pagina" or not isinstance(it.get("id"), str):
            i += 1
            continue
        logica = _logica(it)
        if not avaliar_grupo(logica.get("mostrar_se"), valores, por_id):
            i += 1  # escondido: não entra, nem dispara regras
            continue
        vistos.append(it["id"])
        if respondivel(it.get("tipo")) and it["id"] in respostas:
            valores[it["id"]] = respostas[it["id"]]
        destino = None
        regras = logica.get("pular")
        for regra in regras if isinstance(regras, list) else []:
            if isinstance(regra, dict) and avaliar_grupo(regra.get("se"), valores, por_id):
                destino = regra.get("para")
                break
        if destino == FIM:
            break
        alvo = indice.get(destino) if isinstance(destino, str) else None
        i = alvo if alvo is not None and alvo > i else i + 1
    return vistos


def valores_do_caminho(itens: list[dict], respostas: dict | None) -> dict:
    """As respostas das perguntas que estão no caminho (as de fora são descartadas)."""
    respostas = respostas if isinstance(respostas, dict) else {}
    por_id = _por_id(itens)
    return {pid: respostas[pid] for pid in caminho(itens, respostas)
            if pid in respostas and respondivel(por_id[pid].get("tipo"))}


def escolher_final(finais: list[dict] | None, itens: list[dict], respostas: dict | None) -> str | None:
    """Id do 1º final cujo `mostrar_se` vale com as respostas do caminho (§2.5); None = final padrão do tema."""
    valores = valores_do_caminho(itens, respostas)
    por_id = _por_id(itens)
    for final in finais or []:
        if isinstance(final, dict) and avaliar_grupo(final.get("mostrar_se"), valores, por_id):
            return final.get("id")
    return None


# ---- formato antigo e textos ----------------------------------------------------------------

def converter_condicao_legada(condicao: Any, id_principal: str | None) -> dict | None:
    """`condicao` da etapa 2 → `logica.mostrar_se` com a fonte na nota principal (§2.8); None se não der."""
    if not isinstance(condicao, dict) or not id_principal:
        return None
    if condicao.get("tipo") == "grupo":
        grupos = condicao.get("grupos")
        if not isinstance(grupos, list):
            return None
        return {"juncao": "todas", "condicoes": [{"fonte": id_principal, "op": "grupo_e", "valor": list(grupos)}]}
    if condicao.get("tipo") == "nota":
        op = {"<=": "menor_igual", ">=": "maior_igual"}.get(condicao.get("operador"))
        if op is None:
            return None
        return {"juncao": "todas", "condicoes": [{"fonte": id_principal, "op": op, "valor": condicao.get("valor")}]}
    return None


def sem_citacoes(texto: str | None, troca: str = "…") -> str | None:
    """O texto com cada citação `{{ID}}` trocada (telas internas: "…"; e-mail, antes de qualquer resposta: "")."""
    if not texto or "{{" not in texto:
        return texto
    return RE_CITACAO.sub(troca, texto)


ROTULOS_OPERADOR = {
    "igual": "é", "diferente": "não é", "menor": "é menor que", "menor_igual": "é no máximo", "maior": "é maior que",
    "maior_igual": "é pelo menos", "entre": "está entre", "grupo_e": "é", "respondida": "foi respondida",
    "nao_respondida": "não foi respondida", "um_de": "é uma de", "nenhum_de": "não é nenhuma de",
    "inclui_algum": "inclui alguma de", "inclui_todos": "inclui todas", "nao_inclui_nenhum": "não inclui nenhuma de",
    "contem": "contém", "nao_contem": "não contém", "comeca_com": "começa com", "termina_com": "termina com",
}
_ROTULOS_DATA = {"menor": "é antes de", "maior": "é depois de", "menor_igual": "é até", "maior_igual": "é a partir de"}
_ROTULOS_FONTE = {"nps": "NPS", "csat": "CSAT"}


def _juntar(itens: list[str], conector: str) -> str:
    return itens[0] if len(itens) == 1 else ", ".join(itens[:-1]) + f" {conector} " + itens[-1]


def _valor_legivel(fonte: dict, valor) -> str:
    if isinstance(valor, bool):
        return "Sim" if valor else "Não"
    if isinstance(valor, str) and _data(valor):
        a, m, d = valor.split("-")
        return f"{d}/{m}/{a}"
    if isinstance(valor, str) and fonte.get("tipo") in ("texto_curto", "comentario"):
        return f"“{valor}”"
    return str(valor)


def descrever_condicao(condicao: dict, itens_por_id: dict) -> str:
    fonte = itens_por_id.get(condicao.get("fonte")) or {}
    titulo = sem_citacoes(str(fonte.get("titulo") or ""), "…") or "?"
    nome = _ROTULOS_FONTE.get(fonte.get("tipo")) or f"“{titulo[:60]}”"
    op = condicao.get("op")
    rotulo = (_ROTULOS_DATA.get(op) if fonte.get("tipo") == "data" else None) or ROTULOS_OPERADOR.get(op, str(op))
    if op in SEM_VALOR:
        return f"{nome} {rotulo}"
    valor = condicao.get("valor")
    if op == "entre" and isinstance(valor, list) and len(valor) == 2:
        return f"{nome} {rotulo} {_valor_legivel(fonte, valor[0])} e {_valor_legivel(fonte, valor[1])}"
    if isinstance(valor, list):
        partes = [_valor_legivel(fonte, v) for v in valor] or ["?"]
        return f"{nome} {rotulo} {_juntar(partes, 'e' if op == 'inclui_todos' else 'ou')}"
    return f"{nome} {rotulo} {_valor_legivel(fonte, valor)}"


def descrever_grupo(grupo: dict | None, itens: list[dict]) -> str:
    """A condição em português, para mensagens e Ajuda: "NPS é detrator ou neutro"."""
    if not isinstance(grupo, dict) or not grupo.get("condicoes"):
        return "Sempre"
    por_id = _por_id(itens)
    partes = [descrever_condicao(c, por_id) for c in grupo["condicoes"] if isinstance(c, dict)]
    return (" ou " if grupo.get("juncao") == "qualquer" else " e ").join(partes)

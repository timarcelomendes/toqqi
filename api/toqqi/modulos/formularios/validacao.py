"""Normalização e validação do documento do formulário (perguntas, tema e finais), nota principal e lógica.

Etapa 5l (docs/api-etapa-5l.md §1–§2): itens (perguntas, blocos `conteudo` e quebras de página), lógica
(`mostrar_se` e `pular`), finais, campos novos (aleatorizar, exibicao, max_selecoes, placeholder) e o formato antigo
(`condicao`, convertido para `logica.mostrar_se` na entrada; a saída nunca tem `condicao`).

`normalizar_documento(perguntas, tema, finais, estrito)` devolve (documento, problemas):
- estrito (criar, PATCH, publicar e modelos): qualquer erro vira 422 `dados_invalidos` com `campos`;
- rascunho (estrito=False): grava mesmo com problemas. Só o estrutural dá 422 — formato (listas, objetos, tipos dos
  valores), tipo de item desconhecido, id inválido ou repetido, textos e HTML acima do tamanho e mais de 120 itens. O
  resto (títulos vazios, opções, faixas, lógica, finais, limites de quantidade) volta em `problemas`, com as mesmas
  chaves, sem mudar o que a pessoa fez; mais os avisos de citação (não bloqueiam publicar).
Chaves: `perguntas.<i>.<campo>`, `perguntas.<i>.logica` (a mensagem diz qual condição ou regra), `finais.<i>.<campo>`
ou `finais.<i>.mostrar_se`, `tema.<campo>` e `perguntas` (geral, ex.: limite).

O HTML (blocos de conteúdo e finais) sai sempre limpo (`core.html_seguro`); ids que faltam são gerados (`p_`, `r_` e
`f_` + 6). No modo estrito, as quebras de página no começo, no fim e repetidas saem (no rascunho ficam como estão).
"""
import re
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlsplit

from toqqi.core.errors import AppError
from toqqi.core.html_seguro import MAX_ENTRADA, MAX_HTML, MSG_GRANDE, limpar_html, sem_conteudo
from toqqi.modulos.formularios import logica
from toqqi.modulos.formularios.logica import (  # noqa: F401 (reexportados: quem usa importa daqui)
    TIPOS_NOTA,
    TIPOS_PERGUNTA,
    faixa,
    grupo_da_nota,
    respondivel,
)
from toqqi.modulos.formularios.modelos import TEMA_PADRAO, gerar_id
from toqqi.modulos.imagens.servico import url_aceita_no_tema

MAX_PERGUNTAS = 60
MAX_CONTEUDOS = 30
MAX_ITENS = 120
MAX_CONDICOES = 10
MAX_REGRAS = 10
MAX_FINAIS = 10
MAX_OPCOES = 30
TIPOS = (*TIPOS_PERGUNTA, "conteudo", "quebra_pagina")
FORMATOS = ("texto", "email", "telefone", "numero")
GRUPOS = {"nps": logica.GRUPOS["nps"], "csat": logica.GRUPOS["csat"]}
MODOS = ("uma_por_vez", "paginas")
MODOS_CONTEUDO = ("visual", "html")
EXIBICOES = ("botoes", "lista")
LIMITE_TEXTO = {"texto_curto": 300, "comentario": 4000}
MSG_NOTA_PRINCIPAL = "A nota principal sempre aparece; tire a condição dela."
MSG_ANTES_DA_PRINCIPAL = "Perguntas antes da nota principal não podem pular (a nota principal não pode ficar de fora)."
MSG_CONDICAO_ANTIGA = "A condição só pode ser usada em perguntas depois da nota principal."
MSG_URL = "Use um endereço https:// (até 500 caracteres)."
_RE_ID = re.compile(r"[A-Za-z0-9_-]{1,32}")
_RE_COR = re.compile(r"#[0-9a-fA-F]{6}")


def erro_perguntas(campos: dict[str, str]) -> AppError:
    return AppError(422, "dados_invalidos", "Confira as perguntas destacadas.", campos)


def _texto(v: Any) -> str:
    return v.replace("\x00", "").strip() if isinstance(v, str) else ""


_inteiro = logica._inteiro


# ---- nota principal ---------------------------------------------------------

def indice_principal(perguntas: list[dict]) -> int | None:
    """1ª pergunta nps; senão a 1ª csat/estrelas; senão nenhuma."""
    for i, p in enumerate(perguntas):
        if p.get("tipo") == "nps":
            return i
    for i, p in enumerate(perguntas):
        if p.get("tipo") in ("csat", "estrelas"):
            return i
    return None


def pergunta_principal(perguntas: list[dict]) -> dict | None:
    i = indice_principal(perguntas)
    return perguntas[i] if i is not None else None


def tipo_nota_de(pergunta: dict | None) -> str | None:
    if pergunta is None:
        return None
    return "nps" if pergunta["tipo"] == "nps" else "csat"


def tipo_principal(perguntas: list[dict]) -> str:
    return tipo_nota_de(pergunta_principal(perguntas)) or "personalizado"


def perguntas_respondiveis(perguntas: list[dict]) -> list[dict]:
    """Só as perguntas (sem blocos de conteúdo nem quebras de página)."""
    return [p for p in perguntas if respondivel(p.get("tipo"))]


# ---- coletor de erros ---------------------------------------------------------

@dataclass
class Coletor:
    """`estruturais` sempre viram 422; `problemas` viram 422 no modo estrito e voltam no rascunho; `avisos` (citações)
    nunca bloqueiam. Uma mensagem por chave (a primeira)."""
    estruturais: dict[str, str] = field(default_factory=dict)
    problemas: dict[str, str] = field(default_factory=dict)
    avisos: dict[str, str] = field(default_factory=dict)

    def estrutural(self, chave: str, msg: str) -> None:
        self.estruturais.setdefault(chave, msg)

    def problema(self, chave: str, msg: str) -> None:
        self.problemas.setdefault(chave, msg)

    def aviso(self, chave: str, msg: str) -> None:
        self.avisos.setdefault(chave, msg)

    def todos(self) -> dict[str, str]:
        """Problemas e avisos juntos (o problema vale mais que o aviso na mesma chave)."""
        return {**self.avisos, **self.problemas}


def _mensagem(campos: dict[str, str]) -> str:
    prefixos = {c.split(".", 1)[0] for c in campos}
    if prefixos == {"tema"}:
        return "Confira o tema."
    if prefixos == {"finais"}:
        return "Confira os finais destacados."
    if prefixos <= {"perguntas"}:
        return "Confira as perguntas destacadas."
    return "Confira os campos destacados."


def erro_documento(campos: dict[str, str]) -> AppError:
    return AppError(422, "dados_invalidos", _mensagem(campos), campos)


# ---- itens --------------------------------------------------------------------

def _novo_id(prefixo: str, usados: set[str]) -> str:
    novo = gerar_id(prefixo)
    while novo in usados:
        novo = gerar_id(prefixo)
    usados.add(novo)
    return novo


def _tamanho(c: Coletor, chave: str, valor: str, maximo: int) -> None:
    if len(valor) > maximo:
        c.estrutural(chave, f"Use no máximo {maximo} caracteres.")


def _opcional(c: Coletor, bruta: dict, campo: str, chave: str, maximo: int) -> str | None:
    if bruta.get(campo) is not None and not isinstance(bruta.get(campo), str):
        c.estrutural(chave, "Formato inválido.")
    v = _texto(bruta.get(campo))
    _tamanho(c, chave, v, maximo)
    return v or None


def _bool(c: Coletor, bruta: dict, campo: str, chave: str) -> bool:
    v = bruta.get(campo, False)
    if v is None:
        return False
    if not isinstance(v, bool):
        c.estrutural(chave, "Informe verdadeiro ou falso.")
        return False
    return v


def _html(c: Coletor, bruto: Any, chave: str) -> str:
    """HTML limpo (§3). Acima de 50.000 caracteres recebidos ou 20.000 depois da limpeza: estrutural."""
    if bruto is None:
        return ""
    if not isinstance(bruto, str):
        c.estrutural(chave, "Formato inválido.")
        return ""
    if len(bruto) > MAX_ENTRADA:
        c.estrutural(chave, MSG_GRANDE)
        return ""
    limpo = limpar_html(bruto)
    if len(limpo) > MAX_HTML:
        c.estrutural(chave, MSG_GRANDE)
    return limpo


def _nota(c: Coletor, bruta: dict, p: dict, k: str) -> None:
    if p["tipo"] == "escala":
        mn, mx = bruta.get("min", 1), bruta.get("max", 5)
        mn_i, mx_i = _inteiro(mn), _inteiro(mx)
        if mn_i is None:
            c.estrutural(f"{k}.min", "O mínimo da escala deve ser 0 ou 1.")
        elif mn_i not in (0, 1):
            c.problema(f"{k}.min", "O mínimo da escala deve ser 0 ou 1.")
        if mx_i is None:
            c.estrutural(f"{k}.max", "O máximo da escala deve ficar entre 2 e 10.")
        elif not 2 <= mx_i <= 10:
            c.problema(f"{k}.max", "O máximo da escala deve ficar entre 2 e 10.")
        p["min"], p["max"] = mn_i, mx_i
    else:
        p["min"], p["max"] = faixa(p)
    for r in ("rotulo_min", "rotulo_max"):
        p[r] = _opcional(c, bruta, r, f"{k}.{r}", 60)


def _opcoes(c: Coletor, bruta: dict, p: dict, k: str) -> None:
    opcoes = bruta.get("opcoes")
    chave = f"{k}.opcoes"
    if opcoes is None:
        c.problema(chave, "Informe as opções.")
        p["opcoes"] = []
    elif not isinstance(opcoes, list) or any(not isinstance(o, str) for o in opcoes):
        c.estrutural(chave, "Informe as opções.")
        p["opcoes"] = []
    else:
        limpas = [_texto(o) for o in opcoes]
        if any(len(o) > 200 for o in limpas):
            c.estrutural(chave, "Cada opção pode ter no máximo 200 caracteres.")
        elif any(not o for o in limpas):
            c.problema(chave, "Preencha todas as opções.")
        elif len({o.lower() for o in limpas}) != len(limpas):
            c.problema(chave, "Há opções repetidas.")
        elif not 2 <= len(limpas) <= MAX_OPCOES:
            c.problema(chave, f"Use de 2 a {MAX_OPCOES} opções.")
        p["opcoes"] = limpas
    if _bool(c, bruta, "aleatorizar", f"{k}.aleatorizar"):
        p["aleatorizar"] = True
    if p["tipo"] == "escolha_unica":
        exibicao = bruta.get("exibicao") or "botoes"
        if exibicao not in EXIBICOES:
            c.estrutural(f"{k}.exibicao", "Opção inválida.")
        elif exibicao == "lista":
            p["exibicao"] = "lista"
        return
    maximo = bruta.get("max_selecoes")
    if maximo is None:
        return
    m = _inteiro(maximo)
    if m is None:
        c.estrutural(f"{k}.max_selecoes", "Informe um número inteiro.")
        return
    n = len(p["opcoes"])
    if not 2 <= m <= max(n, 2):
        c.problema(f"{k}.max_selecoes", f"O máximo de opções precisa ficar entre 2 e {max(n, 2)}.")
    p["max_selecoes"] = m


def _item(c: Coletor, bruta: Any, i: int, ids: set[str], reservados: set[str]) -> dict | None:
    """Um item com os campos do tipo (os outros caem). None se nem o tipo der para entender. `ids`: os já usados;
    `reservados`: os que vieram na entrada (um id gerado não repete nenhum dos dois)."""
    k = f"perguntas.{i}"
    if not isinstance(bruta, dict):
        c.estrutural(k, "Formato inválido.")
        return None
    tipo = bruta.get("tipo")
    if tipo not in TIPOS:
        c.estrutural(f"{k}.tipo", "Tipo de pergunta inválido.")
        return None
    pid = bruta.get("id")
    if pid in (None, ""):
        pid = _novo_id("p_", ids | reservados)
    elif not isinstance(pid, str) or not _RE_ID.fullmatch(pid):
        c.estrutural(f"{k}.id", "Identificador inválido.")
        pid = _novo_id("p_", ids | reservados)
    elif pid in ids:
        c.estrutural(f"{k}.id", "Identificador repetido.")
    ids.add(pid)
    p: dict[str, Any] = {"id": pid, "tipo": tipo}
    if bruta.get("titulo") is not None and not isinstance(bruta.get("titulo"), str):
        c.estrutural(f"{k}.titulo", "Formato inválido.")
    titulo = _texto(bruta.get("titulo"))
    if tipo == "conteudo":
        _tamanho(c, f"{k}.titulo", titulo, 120)
        p["titulo"] = titulo
        p["html"] = _html(c, bruta.get("html"), f"{k}.html")
        if not c.estruturais.get(f"{k}.html") and sem_conteudo(p["html"]):
            c.problema(f"{k}.html", "Escreva o conteúdo do bloco.")
        p["modo"] = bruta.get("modo") if bruta.get("modo") in MODOS_CONTEUDO else "visual"
        p["obrigatoria"] = False
        return p
    _tamanho(c, f"{k}.titulo", titulo, 300)
    if tipo != "quebra_pagina" and not titulo:
        c.problema(f"{k}.titulo", "Escreva o título da pergunta.")
    p["titulo"] = titulo
    p["descricao"] = _opcional(c, bruta, "descricao", f"{k}.descricao", 1000)
    obrigatoria = _bool(c, bruta, "obrigatoria", f"{k}.obrigatoria")
    p["obrigatoria"] = obrigatoria and tipo != "quebra_pagina"
    if tipo in TIPOS_NOTA:
        _nota(c, bruta, p, k)
    elif tipo == "texto_curto":
        formato = bruta.get("formato") or "texto"
        if formato not in FORMATOS:
            c.estrutural(f"{k}.formato", "Formato inválido.")
            formato = "texto"
        p["formato"] = formato
    elif tipo in ("escolha_unica", "escolha_multipla"):
        _opcoes(c, bruta, p, k)
    if tipo in ("texto_curto", "comentario"):
        placeholder = _opcional(c, bruta, "placeholder", f"{k}.placeholder", 120)
        if placeholder:
            p["placeholder"] = placeholder
    return p


# ---- lógica: estrutura ----------------------------------------------------------

def _valor_estrutura(v: Any) -> bool:
    """Valor de condição aceitável na estrutura: nulo, sim/não, número, texto de até 200 ou lista curta deles."""
    if v is None or isinstance(v, bool):
        return True
    if isinstance(v, (int, float)):
        return logica._numero(v) is not None
    if isinstance(v, str):
        return len(v) <= 200
    if isinstance(v, list):
        return len(v) <= MAX_OPCOES and all(
            (isinstance(x, str) and len(x) <= 200) or (isinstance(x, (int, float)) and not isinstance(x, bool)
                                                        and logica._numero(x) is not None) for x in v)
    return False


def _grupo_estrutura(c: Coletor, bruto: Any, chave: str) -> dict | None:
    """Grupo {juncao, condicoes} só com os campos conhecidos; None = sem condição."""
    if bruto is None:
        return None
    if not isinstance(bruto, dict):
        c.estrutural(chave, "Formato inválido.")
        return None
    juncao = bruto.get("juncao") or "todas"
    condicoes = bruto.get("condicoes") or []
    if juncao not in logica.JUNCOES or not isinstance(condicoes, list):
        c.estrutural(chave, "Formato inválido.")
        return None
    saida = []
    for bruta in condicoes:
        fonte, op = (bruta.get("fonte"), bruta.get("op")) if isinstance(bruta, dict) else (None, None)
        if (not isinstance(bruta, dict) or not isinstance(fonte, (str, type(None)))
                or not isinstance(op, (str, type(None))) or not _valor_estrutura(bruta.get("valor"))):
            c.estrutural(chave, "Condição inválida.")
            continue
        cond: dict[str, Any] = {"fonte": fonte or None, "op": op or None}
        if op not in logica.SEM_VALOR:
            valor = bruta.get("valor")
            cond["valor"] = valor.strip() if isinstance(valor, str) else valor
        saida.append(cond)
    return {"juncao": juncao, "condicoes": saida}


def _regras_estrutura(c: Coletor, bruto: Any, chave: str, ids_regras: set[str]) -> list[dict]:
    if bruto is None:
        return []
    if not isinstance(bruto, list):
        c.estrutural(chave, "Formato inválido.")
        return []
    regras = []
    for bruta in bruto:
        if not isinstance(bruta, dict) or not isinstance(bruta.get("para"), (str, type(None))):
            c.estrutural(chave, "Regra inválida.")
            continue
        rid = bruta.get("id")
        if not isinstance(rid, str) or not _RE_ID.fullmatch(rid) or rid in ids_regras:
            rid = _novo_id("r_", ids_regras)  # id de regra é interno: faltando, inválido ou repetido, ganha outro
        ids_regras.add(rid)
        regras.append({"id": rid, "se": _grupo_estrutura(c, bruta.get("se"), chave), "para": bruta.get("para") or None})
    return regras


def _logica_estrutura(c: Coletor, bruta: dict, p: dict, i: int, ids_regras: set[str]) -> None:
    """Lê `logica` (e a `condicao` antiga, guardada à parte para converter depois)."""
    chave = f"perguntas.{i}.logica"
    bruto = bruta.get("logica")
    if p["tipo"] == "quebra_pagina":
        return  # quebra de página não tem lógica
    if bruto is not None and not isinstance(bruto, dict):
        c.estrutural(chave, "Formato inválido.")
        return
    bruto = bruto or {}
    mostrar_se = _grupo_estrutura(c, bruto.get("mostrar_se"), chave)
    pular = _regras_estrutura(c, bruto.get("pular"), chave, ids_regras)
    if mostrar_se is not None or pular:
        p["logica"] = {"mostrar_se": mostrar_se, "pular": pular}
    if mostrar_se is None and bruta.get("condicao") is not None:
        p["_condicao"] = bruta["condicao"]


# ---- lógica: validação --------------------------------------------------------

def _rotulo(n: int, regra: int | None) -> str:
    return f"Na regra {regra}, a condição {n}" if regra else f"A condição {n}"


def _escolha(n: int, regra: int | None, o_que: str) -> str:
    return f"Na regra {regra}, escolha {o_que} da condição {n}." if regra else f"Escolha {o_que} da condição {n}."


def _valor_nota(fonte: dict, op: str, valor: Any, rotulo: str) -> tuple[Any, str | None]:
    mn, mx = faixa(fonte)
    if op == "grupo_e":
        validos = logica.GRUPOS[fonte["tipo"]]
        if not isinstance(valor, list) or not valor or any(g not in validos for g in valor):
            return valor, f"{rotulo} precisa de grupos válidos: {', '.join(validos)}."
        return [g for g in validos if g in valor], None
    if op == "entre":
        par = [_inteiro(x) for x in valor] if isinstance(valor, list) and len(valor) == 2 else [None, None]
        if None in par or not mn <= par[0] <= par[1] <= mx:
            return valor, f"{rotulo} precisa de dois números de {mn} a {mx}, o primeiro menor ou igual ao segundo."
        return par, None
    n = _inteiro(valor)
    if n is None or not mn <= n <= mx:
        return valor, f"{rotulo} precisa de um número inteiro de {mn} a {mx}."
    return n, None


def _valor_numero(op: str, valor: Any, rotulo: str) -> tuple[Any, str | None]:
    if op == "entre":
        par = [logica._numero(x) for x in valor] if isinstance(valor, list) and len(valor) == 2 else [None, None]
        if None in par or par[0] > par[1]:
            return valor, f"{rotulo} precisa de dois números, o primeiro menor ou igual ao segundo."
        return list(valor), None
    if logica._numero(valor) is None:
        return valor, f"{rotulo} precisa de um número."
    return valor, None


def _valor_data(op: str, valor: Any, rotulo: str) -> tuple[Any, str | None]:
    if op == "entre":
        if (not isinstance(valor, list) or len(valor) != 2 or not all(logica._data(x) for x in valor)
                or valor[0] > valor[1]):
            return valor, f"{rotulo} precisa de duas datas válidas, a primeira antes da segunda (ou igual)."
        return valor, None
    if not logica._data(valor):
        return valor, f"{rotulo} precisa de uma data válida (AAAA-MM-DD)."
    return valor, None


def _valor_opcoes(fonte: dict, valor: Any, rotulo: str) -> tuple[Any, str | None]:
    if not isinstance(valor, list) or not valor or not all(isinstance(x, str) for x in valor):
        return valor, f"{rotulo} precisa de pelo menos uma opção."
    limpas = list(dict.fromkeys(x.strip() for x in valor))
    for x in limpas:
        if x not in fonte.get("opcoes", []):
            return valor, f"{rotulo} usa a opção '{x}', que não existe mais."
    return limpas, None


def _valor_da_condicao(fonte: dict, op: str, valor: Any, rotulo: str) -> tuple[Any, str | None]:
    """(valor normalizado, mensagem de erro ou None) conforme o tipo da fonte e o operador (§2.2)."""
    tipo = fonte["tipo"]
    if tipo in TIPOS_NOTA:
        return _valor_nota(fonte, op, valor, rotulo)
    if tipo in ("escolha_unica", "escolha_multipla"):
        return _valor_opcoes(fonte, valor, rotulo)
    if tipo == "sim_nao":
        return (valor, None) if isinstance(valor, bool) else (valor, f"{rotulo} precisa de Sim ou Não.")
    if tipo == "data":
        return _valor_data(op, valor, rotulo)
    if logica.e_numero(fonte):
        return _valor_numero(op, valor, rotulo)
    if not isinstance(valor, str) or not 1 <= len(valor.strip()) <= 200:
        return valor, f"{rotulo} precisa de um texto de 1 a 200 caracteres."
    return valor.strip(), None


def _validar_grupo(c: Coletor, grupo: dict, chave: str, itens: list[dict], indice: dict, pos: int | None,
                   modo: str, regra: int | None = None) -> None:
    """Valida (e normaliza no lugar) as condições. `modo`: mostrar_se (fonte antes do item), pular (antes ou o
    próprio item) ou final (qualquer pergunta)."""
    condicoes = grupo["condicoes"]
    if not condicoes:
        c.problema(chave, f"Adicione pelo menos uma condição à regra {regra}." if regra
                   else "Adicione pelo menos uma condição.")
    if len(condicoes) > MAX_CONDICOES:
        c.problema(chave, f"Use no máximo {MAX_CONDICOES} condições em cada grupo.")
    for n, cond in enumerate(condicoes, 1):
        rotulo = _rotulo(n, regra)
        if not cond["fonte"]:
            c.problema(chave, _escolha(n, regra, "a pergunta"))
            continue
        j = indice.get(cond["fonte"])
        if j is None:
            c.problema(chave, f"{rotulo} usa uma pergunta que não existe mais.")
            continue
        fonte = itens[j]
        if fonte["tipo"] == "conteudo":
            c.problema(chave, f"{rotulo} usa um bloco de conteúdo (só perguntas servem de condição).")
            continue
        if fonte["tipo"] == "quebra_pagina":
            c.problema(chave, f"{rotulo} usa uma quebra de página (só perguntas servem de condição).")
            continue
        if modo == "mostrar_se" and j == pos:
            c.problema(chave, f"{rotulo} usa esta mesma pergunta (só as anteriores servem de condição).")
            continue
        if modo in ("mostrar_se", "pular") and j > pos:
            c.problema(chave, f"{rotulo} usa uma pergunta que vem depois desta.")
            continue
        op = cond["op"]
        if not op:
            c.problema(chave, _escolha(n, regra, "a comparação"))
            continue
        if op not in logica.operadores(fonte):
            c.problema(chave, f"{rotulo} usa uma comparação que não vale para este tipo de pergunta.")
            continue
        if op in logica.SEM_VALOR:
            cond.pop("valor", None)
            continue
        valor, erro = _valor_da_condicao(fonte, op, cond.get("valor"), rotulo)
        if erro:
            c.problema(chave, erro)
        else:
            cond["valor"] = valor


def _converter_legado(c: Coletor, itens: list[dict], ip: int | None) -> None:
    """`condicao` antiga → `logica.mostrar_se` na nota principal, com as mensagens e a chave de antes (§2.8)."""
    principal = itens[ip] if ip is not None else None
    for i, p in enumerate(itens):
        cond = p.pop("_condicao", None)
        if cond is None:
            continue
        k = f"perguntas.{i}.condicao"
        if principal is None or i <= ip:
            c.problema(k, MSG_CONDICAO_ANTIGA)
            continue
        if not isinstance(cond, dict) or cond.get("tipo") not in ("grupo", "nota"):
            c.problema(k, "Condição inválida.")
            continue
        if cond["tipo"] == "grupo":
            validos = GRUPOS[tipo_nota_de(principal)]
            grupos = cond.get("grupos")
            if not isinstance(grupos, list) or not grupos or any(g not in validos for g in grupos):
                c.problema(k, "Escolha grupos válidos: " + ", ".join(validos) + ".")
                continue
            cond = {"tipo": "grupo", "grupos": [g for g in validos if g in grupos]}
        else:
            mn, mx = faixa(principal)
            valor = _inteiro(cond.get("valor"))
            if cond.get("operador") not in ("<=", ">="):
                c.problema(k, "Operador inválido.")
                continue
            if valor is None or not mn <= valor <= mx:
                c.problema(k, f"A nota da condição deve ficar entre {mn} e {mx}.")
                continue
            cond = {"tipo": "nota", "operador": cond["operador"], "valor": valor}
        mostrar_se = logica.converter_condicao_legada(cond, principal["id"])
        p["logica"] = {"mostrar_se": mostrar_se, "pular": (p.get("logica") or {}).get("pular") or []}


def _validar_logica(c: Coletor, itens: list[dict]) -> None:
    indice = {p["id"]: i for i, p in enumerate(itens)}
    ip = indice_principal(itens)
    for i, p in enumerate(itens):
        lg = p.get("logica")
        if not lg:
            continue
        k = f"perguntas.{i}.logica"
        if lg["mostrar_se"] is not None:
            if i == ip:
                c.problema(k, MSG_NOTA_PRINCIPAL)
            else:
                _validar_grupo(c, lg["mostrar_se"], k, itens, indice, i, "mostrar_se")
        if not lg["pular"]:
            continue
        if p["tipo"] == "conteudo":
            c.problema(k, "Blocos de conteúdo não podem pular; a regra fica na pergunta.")
        elif ip is not None and i < ip:
            c.problema(k, MSG_ANTES_DA_PRINCIPAL)
        if len(lg["pular"]) > MAX_REGRAS:
            c.problema(k, f"Use no máximo {MAX_REGRAS} regras em cada pergunta.")
        for r, regra in enumerate(lg["pular"], 1):
            if regra["se"] is None:
                c.problema(k, f"Adicione pelo menos uma condição à regra {r}.")
            else:
                _validar_grupo(c, regra["se"], k, itens, indice, i, "pular", r)
            para = regra["para"]
            j = indice.get(para)
            if para == logica.FIM:
                continue
            if not para:
                c.problema(k, f"Escolha para onde a regra {r} manda.")
            elif j is None:
                c.problema(k, f"A regra {r} manda para um item que não existe mais.")
            elif j <= i:
                c.problema(k, f"A regra {r} manda para uma pergunta que vem antes desta "
                              "(só dá para pular para frente).")
            elif itens[j]["tipo"] == "quebra_pagina":
                c.problema(k, f"A regra {r} manda para uma quebra de página; escolha uma pergunta ou o fim.")


def _avisar_citacoes(c: Coletor, texto: str | None, chave: str, validos: set[str], msg: str) -> None:
    for pid in logica.RE_CITACAO.findall(texto or ""):
        if pid not in validos:
            c.aviso(chave, msg.format(pid="{{" + pid + "}}"))
            return


def _citacoes(c: Coletor, itens: list[dict], finais: list[dict]) -> None:
    """Avisos (§2.7): citação que não aponta para uma pergunta anterior (nos finais, para uma pergunta) sai vazia."""
    anteriores: set[str] = set()
    msg = "A citação {pid} não aponta para uma pergunta anterior; ela vai sair vazia."
    for i, p in enumerate(itens):
        campos = ("html",) if p["tipo"] == "conteudo" else ("titulo", "descricao")
        for campo in campos:
            _avisar_citacoes(c, p.get(campo), f"perguntas.{i}.{campo}", anteriores, msg)
        if respondivel(p["tipo"]):
            anteriores.add(p["id"])
    msg_final = "A citação {pid} não aponta para uma pergunta do formulário; ela vai sair vazia."
    for j, f in enumerate(finais):
        for campo in ("titulo", "html"):
            _avisar_citacoes(c, f.get(campo), f"finais.{j}.{campo}", anteriores, msg_final)


def _limites(c: Coletor, itens: list[dict]) -> None:
    if sum(1 for p in itens if respondivel(p["tipo"])) > MAX_PERGUNTAS:
        c.problema("perguntas", f"Use no máximo {MAX_PERGUNTAS} perguntas.")
    if sum(1 for p in itens if p["tipo"] == "conteudo") > MAX_CONTEUDOS:
        c.problema("perguntas", f"Use no máximo {MAX_CONTEUDOS} blocos de conteúdo.")


def _limpar_quebras(perguntas: list[dict]) -> list[dict]:
    saida: list[dict] = []
    for p in perguntas:
        if p["tipo"] == "quebra_pagina" and (not saida or saida[-1]["tipo"] == "quebra_pagina"):
            continue
        saida.append(p)
    while saida and saida[-1]["tipo"] == "quebra_pagina":
        saida.pop()
    return saida


def _itens(c: Coletor, entrada: Any, ids_regras: set[str]) -> list[dict]:
    if not isinstance(entrada, list):
        c.estrutural("perguntas", "Informe uma lista de perguntas.")
        return []
    if len(entrada) > MAX_ITENS:
        c.estrutural("perguntas", f"Use no máximo {MAX_ITENS} itens (perguntas, blocos de conteúdo e quebras).")
        return []
    # os ids que vieram ficam reservados antes de gerar os que faltam (um gerado nunca repete um que vem depois)
    ids: set[str] = set()
    reservados = {b.get("id") for b in entrada if isinstance(b, dict) and isinstance(b.get("id"), str)}
    itens = []
    for i, bruta in enumerate(entrada):
        p = _item(c, bruta, i, ids, reservados)
        if p is None:
            continue
        _logica_estrutura(c, bruta, p, i, ids_regras)
        itens.append(p)
    return itens


# ---- finais -------------------------------------------------------------------

def _botao(c: Coletor, bruto: Any, k: str) -> dict | None:
    if bruto is None:
        return None
    if not isinstance(bruto, dict):
        c.estrutural(f"{k}.botao", "Formato inválido.")
        return None
    texto = _opcional(c, bruto, "texto", f"{k}.botao.texto", 40) or ""
    url = _opcional(c, bruto, "url", f"{k}.botao.url", 500) or ""
    if not texto and not url:
        return None
    if not texto:
        c.problema(f"{k}.botao.texto", "Escreva o texto do botão.")
    if not url_https(url):
        c.problema(f"{k}.botao.url", MSG_URL)
    return {"texto": texto, "url": url}


def url_https(url: str) -> bool:
    """Endereço https://, com domínio, sem espaços nem caracteres de controle, até 500."""
    if not url or len(url) > 500 or not url.startswith("https://") or any(ch.isspace() or ord(ch) < 32 for ch in url):
        return False
    try:
        partes = urlsplit(url)
    except ValueError:
        return False
    return partes.scheme == "https" and bool(partes.hostname)


def _finais(c: Coletor, entrada: Any, itens: list[dict]) -> list[dict]:
    if entrada is None:
        return []
    if not isinstance(entrada, list):
        c.estrutural("finais", "Informe uma lista de finais.")
        return []
    if len(entrada) > MAX_FINAIS:
        c.problema("finais", f"Use no máximo {MAX_FINAIS} finais.")
    ids: set[str] = set()
    indice = {p["id"]: i for i, p in enumerate(itens)}
    saida = []
    for j, bruto in enumerate(entrada):
        k = f"finais.{j}"
        if not isinstance(bruto, dict):
            c.estrutural(k, "Formato inválido.")
            continue
        fid = bruto.get("id")
        if not isinstance(fid, str) or not _RE_ID.fullmatch(fid) or fid in ids:
            fid = _novo_id("f_", ids)  # id de final é interno: faltando, inválido ou repetido, ganha outro
        ids.add(fid)
        nome = _opcional(c, bruto, "nome", f"{k}.nome", 60) or ""
        if not nome:
            c.problema(f"{k}.nome", "Dê um nome ao final (só a sua equipe vê).")
        titulo = _opcional(c, bruto, "titulo", f"{k}.titulo", 120) or ""
        if not titulo:
            c.problema(f"{k}.titulo", "Escreva o título do final.")
        html = _html(c, bruto.get("html"), f"{k}.html")
        final = {"id": fid, "nome": nome, "titulo": titulo, "html": "" if sem_conteudo(html) else html,
                 "botao": _botao(c, bruto.get("botao"), k),
                 "mostrar_se": _grupo_estrutura(c, bruto.get("mostrar_se"), f"{k}.mostrar_se")}
        if final["mostrar_se"] is not None:
            _validar_grupo(c, final["mostrar_se"], f"{k}.mostrar_se", itens, indice, None, "final")
        saida.append(final)
    return saida


# ---- tema ---------------------------------------------------------------------

_LIMITES_TEMA = {"titulo_abertura": 120, "texto_abertura": 1000, "texto_botao": 40,
                 "titulo_final": 120, "texto_final": 1000}


def _tema(c: Coletor, entrada: Any, base: dict | None) -> dict:
    """Tema sobre a base (o publicado, ou o padrão): só as chaves conhecidas. Cor e logo inválidos são problema (no
    rascunho fica o valor da base); modo inválido e textos longos, estrutural."""
    tema = {**TEMA_PADRAO, **{k: v for k, v in (base or {}).items() if k in TEMA_PADRAO}}
    if entrada is None:
        return tema
    if not isinstance(entrada, dict):
        c.estrutural("tema", "Formato inválido.")
        return tema
    for chave, valor in entrada.items():
        if chave not in TEMA_PADRAO:
            continue
        if chave == "cor":
            if not isinstance(valor, str) or not _RE_COR.fullmatch(valor):
                c.problema("tema.cor", "Use uma cor no formato #rrggbb.")
            else:
                tema["cor"] = valor.lower()
        elif chave == "modo":
            if valor not in MODOS:
                c.estrutural("tema.modo", "Opção inválida.")
            else:
                tema["modo"] = valor
        elif chave == "logo_url":
            # https://... ou a URL de uma imagem enviada à plataforma (POST /formularios/{id}/logo)
            v = _texto(valor)
            if v and (len(v) > 500 or not url_aceita_no_tema(v)):
                c.problema("tema.logo_url", MSG_URL)
            else:
                tema["logo_url"] = v or None
        else:
            if valor is not None and not isinstance(valor, str):
                c.estrutural(f"tema.{chave}", "Formato inválido.")
                continue
            v = _texto(valor)
            if len(v) > _LIMITES_TEMA[chave]:
                c.estrutural(f"tema.{chave}", f"Use no máximo {_LIMITES_TEMA[chave]} caracteres.")
            if chave in ("texto_botao", "titulo_final", "texto_final") and not v:
                v = TEMA_PADRAO[chave]
            tema[chave] = v or None
    return tema


def normalizar_tema(entrada: Any, base: dict | None = None) -> dict:
    """Tema validado (estrito): qualquer erro → 422 com `tema.<campo>`."""
    c = Coletor()
    tema = _tema(c, entrada, base)
    campos = {**c.problemas, **c.estruturais}
    if campos:
        raise AppError(422, "dados_invalidos", "Confira o tema.", campos)
    return tema


# ---- documento ------------------------------------------------------------------

def _sem_logica_vazia(itens: list[dict]) -> None:
    for p in itens:
        lg = p.get("logica")
        if lg is not None and lg["mostrar_se"] is None and not lg["pular"]:
            del p["logica"]


def analisar_documento(perguntas: Any, tema: Any, finais: Any, estrito: bool,
                       base_tema: dict | None = None) -> tuple[dict, Coletor]:
    """O documento normalizado e o coletor (estruturais, problemas e avisos), sem levantar erro."""
    c = Coletor()
    ids_regras: set[str] = set()
    itens = _itens(c, perguntas, ids_regras)
    if not c.estruturais:
        _converter_legado(c, itens, indice_principal(itens))
        _validar_logica(c, itens)
        _limites(c, itens)
    for p in itens:
        p.pop("_condicao", None)
    _sem_logica_vazia(itens)
    lista_finais = _finais(c, finais, itens) if not c.estruturais else []
    _citacoes(c, itens, lista_finais)
    doc = {"perguntas": _limpar_quebras(itens) if estrito else itens,
           "tema": _tema(c, tema, base_tema), "finais": lista_finais}
    return doc, c


def normalizar_documento(perguntas: Any, tema: Any, finais: Any, estrito: bool,
                         base_tema: dict | None = None) -> tuple[dict, dict[str, str]]:
    """(documento, problemas). Estrutural → 422 sempre; no modo estrito, também os problemas. `problemas` traz os
    avisos de citação junto (só no rascunho)."""
    doc, c = analisar_documento(perguntas, tema, finais, estrito, base_tema)
    if c.estruturais or (estrito and c.problemas):
        raise erro_documento({**c.problemas, **c.estruturais} if estrito else c.estruturais)
    return doc, ({} if estrito else c.todos())


def normalizar_perguntas(entrada: Any) -> list[dict]:
    """Só as perguntas (sem finais), no modo estrito: devolve as perguntas limpas (ids gerados quando faltam) ou
    levanta 422 com campos perguntas.<i>.<campo>."""
    return normalizar_documento(entrada, None, None, estrito=True)[0]["perguntas"]


def normalizar_finais(entrada: Any, perguntas: list[dict], estrito: bool = True) -> tuple[list[dict], dict[str, str]]:
    """Os finais de um formulário cujas perguntas (já normalizadas) são `perguntas`: (finais, problemas), como em
    `normalizar_documento`."""
    doc, problemas = normalizar_documento(perguntas, None, entrada, estrito)
    return doc["finais"], {k: v for k, v in problemas.items() if k.startswith("finais")}

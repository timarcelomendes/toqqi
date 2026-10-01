"""Normalização e validação de perguntas e tema; nota principal, grupos e lógica condicional."""
import re
from typing import Any

from toqqi.core.errors import AppError
from toqqi.modulos.formularios.modelos import TEMA_PADRAO, gerar_id_pergunta
from toqqi.modulos.imagens.servico import url_aceita_no_tema

MAX_PERGUNTAS = 60
TIPOS = ("nps", "csat", "estrelas", "escala", "texto_curto", "comentario", "escolha_unica", "escolha_multipla",
         "sim_nao", "data", "quebra_pagina")
TIPOS_NOTA = ("nps", "csat", "estrelas", "escala")
FORMATOS = ("texto", "email", "telefone", "numero")
GRUPOS = {"nps": ("detrator", "neutro", "promotor"), "csat": ("insatisfeito", "neutro", "satisfeito")}
MODOS = ("uma_por_vez", "paginas")
LIMITE_TEXTO = {"texto_curto": 300, "comentario": 4000}
_RE_ID = re.compile(r"^[A-Za-z0-9_-]{1,32}$")
_RE_COR = re.compile(r"^#[0-9a-fA-F]{6}$")


def erro_perguntas(campos: dict[str, str]) -> AppError:
    return AppError(422, "dados_invalidos", "Confira as perguntas destacadas.", campos)


def _texto(v: Any) -> str:
    return v.strip() if isinstance(v, str) else ""


def _inteiro(v: Any) -> int | None:
    if isinstance(v, bool):
        return None
    if isinstance(v, int):
        return v
    if isinstance(v, float) and v.is_integer():
        return int(v)
    return None


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


def faixa(p: dict) -> tuple[int, int]:
    if p["tipo"] == "nps":
        return 0, 10
    if p["tipo"] in ("csat", "estrelas"):
        return 1, 5
    return p.get("min", 1), p.get("max", 5)


def grupo_da_nota(tipo_nota: str | None, nota: int | None) -> str | None:
    if tipo_nota is None or nota is None:
        return None
    if tipo_nota == "nps":
        return "detrator" if nota <= 6 else "neutro" if nota <= 8 else "promotor"
    return "insatisfeito" if nota <= 2 else "neutro" if nota == 3 else "satisfeito"


def visivel(p: dict, principal: dict | None, valor_principal: int | None) -> bool:
    c = p.get("condicao")
    if not c:
        return True
    if principal is None or valor_principal is None:
        return False
    if c["tipo"] == "grupo":
        return grupo_da_nota(tipo_nota_de(principal), valor_principal) in c["grupos"]
    if c["operador"] == "<=":
        return valor_principal <= c["valor"]
    return valor_principal >= c["valor"]


# ---- perguntas --------------------------------------------------------------

def _limpar_quebras(perguntas: list[dict]) -> list[dict]:
    saida: list[dict] = []
    for p in perguntas:
        if p["tipo"] == "quebra_pagina" and (not saida or saida[-1]["tipo"] == "quebra_pagina"):
            continue
        saida.append(p)
    while saida and saida[-1]["tipo"] == "quebra_pagina":
        saida.pop()
    return saida


def normalizar_perguntas(entrada: Any) -> list[dict]:
    """Devolve as perguntas limpas (ids gerados quando faltam) ou levanta 422 com campos perguntas.<i>.<campo>."""
    if not isinstance(entrada, list):
        raise erro_perguntas({"perguntas": "Informe uma lista de perguntas."})
    if len(entrada) > MAX_PERGUNTAS * 2:
        raise erro_perguntas({"perguntas": f"Use no máximo {MAX_PERGUNTAS} perguntas."})
    campos: dict[str, str] = {}
    saida: list[dict] = []
    ids: set[str] = set()

    for i, bruta in enumerate(entrada):
        k = f"perguntas.{i}"
        if not isinstance(bruta, dict):
            campos[k] = "Formato inválido."
            continue
        tipo = bruta.get("tipo")
        if tipo not in TIPOS:
            campos[f"{k}.tipo"] = "Tipo de pergunta inválido."
            continue
        p: dict[str, Any] = {}
        pid = bruta.get("id")
        if pid in (None, ""):
            pid = gerar_id_pergunta()
            while pid in ids:
                pid = gerar_id_pergunta()
        elif not isinstance(pid, str) or not _RE_ID.match(pid):
            campos[f"{k}.id"] = "Identificador inválido."
        elif pid in ids:
            campos[f"{k}.id"] = "Identificador repetido."
        ids.add(pid if isinstance(pid, str) else "")
        p["id"] = pid
        p["tipo"] = tipo

        titulo = _texto(bruta.get("titulo"))
        if tipo != "quebra_pagina" and not titulo:
            campos[f"{k}.titulo"] = "Escreva o título da pergunta."
        elif len(titulo) > 300:
            campos[f"{k}.titulo"] = "Use no máximo 300 caracteres."
        p["titulo"] = titulo
        descricao = _texto(bruta.get("descricao"))
        if len(descricao) > 1000:
            campos[f"{k}.descricao"] = "Use no máximo 1000 caracteres."
        p["descricao"] = descricao or None
        obrig = bruta.get("obrigatoria", False)
        if not isinstance(obrig, bool):
            campos[f"{k}.obrigatoria"] = "Informe verdadeiro ou falso."
        p["obrigatoria"] = bool(obrig) and tipo != "quebra_pagina"

        if tipo in TIPOS_NOTA:
            if tipo == "escala":
                mn = bruta.get("min", 1)
                mx = bruta.get("max", 5)
                mn_i, mx_i = _inteiro(mn), _inteiro(mx)
                if mn_i not in (0, 1):
                    campos[f"{k}.min"] = "O mínimo da escala deve ser 0 ou 1."
                if mx_i is None or not 2 <= mx_i <= 10:
                    campos[f"{k}.max"] = "O máximo da escala deve ficar entre 2 e 10."
                p["min"], p["max"] = mn_i, mx_i
            else:
                p["min"], p["max"] = faixa(p)
            for r in ("rotulo_min", "rotulo_max"):
                rot = _texto(bruta.get(r))
                if len(rot) > 60:
                    campos[f"{k}.{r}"] = "Use no máximo 60 caracteres."
                p[r] = rot or None
        elif tipo == "texto_curto":
            formato = bruta.get("formato") or "texto"
            if formato not in FORMATOS:
                campos[f"{k}.formato"] = "Formato inválido."
            p["formato"] = formato
        elif tipo in ("escolha_unica", "escolha_multipla"):
            opcoes = bruta.get("opcoes")
            if not isinstance(opcoes, list):
                campos[f"{k}.opcoes"] = "Informe as opções."
            else:
                limpas = [_texto(o) if isinstance(o, str) else None for o in opcoes]
                if any(not o for o in limpas):
                    campos[f"{k}.opcoes"] = "Preencha todas as opções."
                elif any(len(o) > 200 for o in limpas):
                    campos[f"{k}.opcoes"] = "Cada opção pode ter no máximo 200 caracteres."
                elif len({o.lower() for o in limpas}) != len(limpas):
                    campos[f"{k}.opcoes"] = "Há opções repetidas."
                elif not 2 <= len(limpas) <= 30:
                    campos[f"{k}.opcoes"] = "Use de 2 a 30 opções."
                p["opcoes"] = limpas
        if "condicao" in bruta and bruta["condicao"] is not None and tipo != "quebra_pagina":
            p["condicao"] = bruta["condicao"]
        saida.append(p)

    if campos:
        raise erro_perguntas(campos)
    if sum(1 for p in saida if p["tipo"] != "quebra_pagina") > MAX_PERGUNTAS:
        raise erro_perguntas({"perguntas": f"Use no máximo {MAX_PERGUNTAS} perguntas."})

    # Condições: só depois da nota principal e coerentes com ela.
    ip = indice_principal(saida)
    principal = saida[ip] if ip is not None else None
    for i, p in enumerate(saida):
        c = p.get("condicao")
        if c is None:
            continue
        k = f"perguntas.{i}.condicao"
        if principal is None or i <= ip:
            campos[k] = "A condição só pode ser usada em perguntas depois da nota principal."
            continue
        if not isinstance(c, dict) or c.get("tipo") not in ("grupo", "nota"):
            campos[k] = "Condição inválida."
            continue
        if c["tipo"] == "grupo":
            validos = GRUPOS[tipo_nota_de(principal)]
            grupos = c.get("grupos")
            if not isinstance(grupos, list) or not grupos or any(g not in validos for g in grupos):
                campos[k] = "Escolha grupos válidos: " + ", ".join(validos) + "."
                continue
            p["condicao"] = {"tipo": "grupo", "grupos": [g for g in validos if g in grupos]}
        else:
            mn, mx = faixa(principal)
            valor = _inteiro(c.get("valor"))
            if c.get("operador") not in ("<=", ">="):
                campos[k] = "Operador inválido."
            elif valor is None or not mn <= valor <= mx:
                campos[k] = f"A nota da condição deve ficar entre {mn} e {mx}."
            else:
                p["condicao"] = {"tipo": "nota", "operador": c["operador"], "valor": valor}
    if campos:
        raise erro_perguntas(campos)
    return _limpar_quebras(saida)


# ---- tema -------------------------------------------------------------------

_LIMITES_TEMA = {"titulo_abertura": 120, "texto_abertura": 1000, "texto_botao": 40,
                 "titulo_final": 120, "texto_final": 1000}


def normalizar_tema(entrada: Any, base: dict | None = None) -> dict:
    if entrada is None:
        entrada = {}
    if not isinstance(entrada, dict):
        raise AppError(422, "dados_invalidos", "Confira o tema.", {"tema": "Formato inválido."})
    tema = {**TEMA_PADRAO, **(base or {})}
    campos: dict[str, str] = {}
    for chave, valor in entrada.items():
        if chave not in TEMA_PADRAO:
            continue
        if chave == "cor":
            if not isinstance(valor, str) or not _RE_COR.match(valor):
                campos["tema.cor"] = "Use uma cor no formato #rrggbb."
            else:
                tema["cor"] = valor.lower()
        elif chave == "modo":
            if valor not in MODOS:
                campos["tema.modo"] = "Opção inválida."
            else:
                tema["modo"] = valor
        elif chave == "logo_url":
            # https://... ou a URL de uma imagem enviada à plataforma (POST /formularios/{id}/logo)
            v = _texto(valor)
            if v and (len(v) > 500 or not url_aceita_no_tema(v)):
                campos["tema.logo_url"] = "Use um endereço https:// (até 500 caracteres)."
            tema["logo_url"] = v or None
        else:
            v = _texto(valor)
            if len(v) > _LIMITES_TEMA[chave]:
                campos[f"tema.{chave}"] = f"Use no máximo {_LIMITES_TEMA[chave]} caracteres."
            if chave in ("texto_botao", "titulo_final", "texto_final") and not v:
                v = TEMA_PADRAO[chave]
            tema[chave] = v or None
    if campos:
        raise AppError(422, "dados_invalidos", "Confira o tema.", campos)
    return tema

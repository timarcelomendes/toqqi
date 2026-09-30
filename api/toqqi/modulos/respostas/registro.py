"""Validação das respostas de um formulário, variáveis nos textos e gravação da resposta."""
import copy
import re
from datetime import date
from typing import Any

from email_validator import EmailNotValidError, validate_email
from sqlalchemy import select
from sqlalchemy.orm import Session

from toqqi.core.errors import AppError
from toqqi.core.texto import so_digitos
from toqqi.modelos import Contato, Formulario, Resposta
from toqqi.modulos.formularios.validacao import (
    LIMITE_TEXTO,
    TIPOS_NOTA,
    faixa,
    grupo_da_nota,
    pergunta_principal,
    tipo_nota_de,
    visivel,
)
from toqqi.modulos.respostas.eventos import ao_registrar_resposta

ASSUNTO_PADRAO = "o nosso atendimento"
MAX_RESUMO = 2000
VARIAVEIS = ("empresa", "nome", "assunto", "referencia")


# ---- variáveis --------------------------------------------------------------

def variaveis(empresa: str, nome_contato: str | None = None, assunto: str | None = None,
              referencia: str | None = None) -> dict:
    primeiro = (nome_contato or "").strip().split(" ")[0] if nome_contato else ""
    return {"empresa": empresa or "", "nome": primeiro, "assunto": assunto or ASSUNTO_PADRAO,
            "referencia": referencia or ""}


def renderizar(texto: str | None, v: dict) -> str | None:
    """Troca {empresa} {nome} {assunto} {referencia}. Variável vazia some junto com o espaço antes;
    {nome} vazio também leva a vírgula: "Olá, {nome}!" → "Olá!"."""
    if not texto or "{" not in texto:
        return texto
    for chave in VARIAVEIS:
        marca = "{" + chave + "}"
        if marca not in texto:
            continue
        valor = v.get(chave) or ""
        if valor:
            texto = texto.replace(marca, valor)
            continue
        if chave == "nome":
            texto = re.sub(r",\s*\{nome\}", "", texto)
            inicio = texto.startswith(marca)
            texto = re.sub(r"^\{nome\}\s*[,!]?\s*", "", texto)
            if inicio and texto:
                texto = texto[0].upper() + texto[1:]
        texto = re.sub(r"\s*" + re.escape(marca), "", texto)
    return re.sub(r" {2,}", " ", texto).strip()


def formulario_publico(f: Formulario, v: dict) -> dict:
    perguntas = copy.deepcopy(f.perguntas)
    for p in perguntas:
        p["titulo"] = renderizar(p.get("titulo"), v)
        p["descricao"] = renderizar(p.get("descricao"), v)
    tema = {k: renderizar(x, v) if isinstance(x, str) else x for k, x in (f.tema or {}).items()}
    return {"nome": f.nome, "perguntas": perguntas, "tema": tema}


def texto_final(f: Formulario, v: dict) -> dict:
    tema = f.tema or {}
    return {"titulo_final": renderizar(tema.get("titulo_final") or "Obrigado!", v),
            "texto_final": renderizar(tema.get("texto_final") or "", v)}


# ---- validação --------------------------------------------------------------

def _vazio(v: Any) -> bool:
    return v is None or (isinstance(v, str) and not v.strip()) or (isinstance(v, list) and not v)


def _valor(p: dict, v: Any) -> Any:
    tipo = p["tipo"]
    if tipo in TIPOS_NOTA:
        if isinstance(v, str) and v.strip().isdigit():
            v = int(v.strip())
        if isinstance(v, bool) or not isinstance(v, int):
            raise ValueError("Escolha uma nota.")
        mn, mx = faixa(p)
        if not mn <= v <= mx:
            raise ValueError(f"Escolha uma nota de {mn} a {mx}.")
        return v
    if tipo in ("texto_curto", "comentario"):
        if not isinstance(v, str):
            raise ValueError("Resposta inválida.")
        v = v.strip()
        if len(v) > LIMITE_TEXTO[tipo]:
            raise ValueError(f"Use no máximo {LIMITE_TEXTO[tipo]} caracteres.")
        formato = p.get("formato", "texto")
        if tipo == "texto_curto" and formato == "email":
            try:
                validate_email(v, check_deliverability=False)
            except EmailNotValidError:
                raise ValueError("Informe um e-mail válido.")
            v = v.lower()
        elif tipo == "texto_curto" and formato == "telefone":
            if len(so_digitos(v)) < 8:
                raise ValueError("Informe um telefone válido.")
        elif tipo == "texto_curto" and formato == "numero":
            try:
                float(v.replace(".", "").replace(",", ".") if "," in v else v)
            except ValueError:
                raise ValueError("Informe um número.")
        return v
    if tipo == "escolha_unica":
        if v not in p.get("opcoes", []):
            raise ValueError("Escolha uma das opções.")
        return v
    if tipo == "escolha_multipla":
        if not isinstance(v, list) or any(x not in p.get("opcoes", []) for x in v):
            raise ValueError("Escolha entre as opções.")
        return [o for o in p["opcoes"] if o in v]
    if tipo == "sim_nao":
        if not isinstance(v, bool):
            raise ValueError("Responda sim ou não.")
        return v
    if tipo == "data":
        try:
            if not isinstance(v, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", v):
                raise ValueError
            date.fromisoformat(v)
        except ValueError:
            raise ValueError("Informe uma data no formato AAAA-MM-DD.")
        return v
    raise ValueError("Resposta inválida.")


def validar_respostas(perguntas: list[dict], brutas: Any) -> tuple[dict, int | None, str | None, str | None]:
    """Devolve (respostas limpas, nota, tipo_nota, grupo). Respostas de perguntas escondidas pela
    lógica são descartadas. Levanta 422 com campos por id de pergunta."""
    if not isinstance(brutas, dict):
        raise AppError(422, "dados_invalidos", "Confira as respostas.", {"respostas": "Formato inválido."})
    principal = pergunta_principal(perguntas)
    campos: dict[str, str] = {}
    valores: dict[str, Any] = {}
    reais = [p for p in perguntas if p["tipo"] != "quebra_pagina"]
    for p in reais:
        v = brutas.get(p["id"])
        if _vazio(v):
            continue
        try:
            valores[p["id"]] = _valor(p, v)
        except ValueError as e:
            campos[p["id"]] = str(e)
    nota = valores.get(principal["id"]) if principal else None
    limpas: dict[str, Any] = {}
    for p in reais:
        if not visivel(p, principal, nota):
            campos.pop(p["id"], None)
            continue
        if p["id"] in valores:
            limpas[p["id"]] = valores[p["id"]]
        elif p.get("obrigatoria") and p["id"] not in campos:
            campos[p["id"]] = "Responda esta pergunta."
    if campos:
        raise AppError(422, "dados_invalidos", "Confira as respostas destacadas.", campos)
    if not limpas:
        raise AppError(422, "dados_invalidos", "Responda pelo menos uma pergunta.")
    tipo_nota = tipo_nota_de(principal) if nota is not None else None
    return limpas, nota, tipo_nota, grupo_da_nota(tipo_nota, nota)


def formatar_valor(v: Any) -> str:
    if isinstance(v, bool):
        return "Sim" if v else "Não"
    if isinstance(v, list):
        return ", ".join(str(x) for x in v)
    if isinstance(v, str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", v):
        a, m, d = v.split("-")
        return f"{d}/{m}/{a}"
    return str(v)


def resumo(perguntas: list[dict], respostas: dict, v: dict) -> str:
    """ "Pergunta: resposta | ..." sem a nota principal, até 2000 caracteres."""
    principal = pergunta_principal(perguntas)
    partes = []
    for p in perguntas:
        if p["tipo"] == "quebra_pagina" or p is principal or p["id"] not in respostas:
            continue
        titulo = renderizar(p["titulo"], v).strip()
        # "Pergunta?: resposta" fica estranho; pontuação no fim dispensa os dois-pontos
        sep = " " if titulo.endswith(("?", "!", ":", ".")) else ": "
        partes.append((titulo, f"{titulo}{sep}{formatar_valor(respostas[p['id']])}", formatar_valor(respostas[p["id"]])))
    # uma única resposta extra (o caso comum: "o que pesou na nota?") vira só o texto do cliente
    texto = partes[0][2] if len(partes) == 1 else " | ".join(parte for _, parte, _ in partes)
    return texto if len(texto) <= MAX_RESUMO else texto[:MAX_RESUMO - 1] + "…"


def email_informado(perguntas: list[dict], respostas: dict) -> str | None:
    for p in perguntas:
        if p["tipo"] == "texto_curto" and p.get("formato") == "email" and respostas.get(p["id"]):
            return respostas[p["id"]]
    return None


# ---- gravação ---------------------------------------------------------------

def gravar_resposta(
    s: Session,
    f: Formulario,
    brutas: Any,
    canal: str,
    v: dict,
    contato: Contato | None = None,
    empresa_id: int | None = None,
    convite_id: int | None = None,
    contexto: dict | None = None,
    referencia: str | None = None,
    ip_hash: str | None = None,
    respostas_validadas: tuple | None = None,
) -> Resposta:
    """Valida, grava e chama o ponto único `ao_registrar_resposta`. Deve rodar dentro de em_conta."""
    limpas, nota, tipo_nota, grupo = respostas_validadas or validar_respostas(f.perguntas, brutas)
    if contato is None:
        email = email_informado(f.perguntas, limpas)
        if email:
            contato = s.scalar(select(Contato).where(Contato.email == email))
    if contato is not None and empresa_id is None:
        empresa_id = contato.empresa_id
    r = Resposta(
        formulario_id=f.id, convite_id=convite_id, contato_id=contato.id if contato else None,
        empresa_id=empresa_id, canal=canal, nota=nota, tipo_nota=tipo_nota, grupo=grupo,
        comentario=resumo(f.perguntas, limpas, v), respostas=limpas, contexto=contexto or {},
        referencia=referencia or None, ip_hash=ip_hash,
    )
    s.add(r)
    if contato is not None and nota is not None:
        contato.ultima_nota = nota
    s.flush()
    ao_registrar_resposta(s, r)
    return r

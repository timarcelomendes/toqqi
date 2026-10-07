"""Regras do feedback (docs/api-feedback.md §2): tipos, situações, limites e a limpeza do que chega do site.

Nada aqui vai ao banco. O texto de quem escreve fica como foi escrito (só sem caracteres de controle, com as quebras de
linha normalizadas e sem espaços nas pontas); o contexto da tela e o diagnóstico passam por uma limpeza rígida: o que
não estiver no formato esperado sai calado (são detalhes de apoio, nunca motivo para recusar o feedback).
"""
import json
import re
import unicodedata

from toqqi.core import erros
from toqqi.core.errors import AppError

TIPOS = {"erro": "Erro", "sugestao": "Sugestão", "melhoria": "Melhoria", "elogio": "Elogio"}
SITUACOES = {"recebido": "Recebido", "em_analise": "Em análise", "planejado": "Planejado", "concluido": "Concluído",
             "encerrado": "Encerrado"}
ABERTAS = ("recebido", "em_analise", "planejado")
IMPACTOS = {"bloqueia": "Impede o trabalho", "atrapalha": "Atrapalha, mas dá para seguir", "detalhe": "É um detalhe"}

MAX_TEXTO = 5000
MAX_NOTA = 5000
MAX_MENSAGENS = 200          # mensagens por feedback (as da equipe contam)
MAX_IMAGENS_MENSAGEM = 3
MAX_IMAGENS_FEEDBACK = 12
LIMITE_IMAGEM = 1024 * 1024  # 1 MB, como o banco de imagens
MAX_PAGINA = 200
MAX_TITULO = 120
MAX_NAVEGADOR = 400
MAX_VERSAO = 40
MAX_DIAGNOSTICO_ITENS = 10
MAX_DIAGNOSTICO_BYTES = 8000
MAX_TRECHO = 160

MSG_TIPO = "Escolha o tipo: erro, sugestão, melhoria ou elogio."
MSG_TEXTO = "Escreva o que você quer contar."
MSG_TEXTO_LONGO = f"Use até {MAX_TEXTO:,} caracteres.".replace(",", ".")
MSG_IMPACTO = "Escolha uma das opções de impacto."
MSG_IMAGENS = "Use imagens PNG ou JPG de até 1 MB."
MSG_QUANTAS = f"Envie até {MAX_IMAGENS_MENSAGEM} imagens por mensagem."
MSG_SITUACAO = "Escolha uma situação válida."
MSG_NOTA = f"Use até {MAX_NOTA:,} caracteres.".replace(",", ".")

_RE_TELA = re.compile(r"[1-9][0-9]{1,4}x[1-9][0-9]{1,4}")
_RE_VERSAO = re.compile(r"[0-9A-Za-z._-]{1,40}")
_RE_CODIGO = re.compile(r"[a-z][a-z0-9_]{0,59}")
_RE_REQUEST_ID = re.compile(r"[A-Za-z0-9_-]{1,64}")
_RE_QUANDO = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?(?:Z|[+-]\d{2}:?\d{2})?")
_METODOS = ("GET", "POST", "PUT", "PATCH", "DELETE")


# ---- texto de quem escreve ---------------------------------------------------------------------------------------

def _sem_controles(texto: str, manter: str = "") -> str:
    """Tira os caracteres de controle (menos os de `manter`), os invisíveis de formatação e os substitutos soltos."""
    return "".join(c for c in texto if c in manter or unicodedata.category(c) not in ("Cc", "Cf", "Cs"))


def limpar_texto(valor: object) -> str:
    """O texto como foi escrito: quebras de linha normalizadas (\\n), sem controles (menos \\n e \\t), sem espaços nas
    pontas e com no máximo duas linhas em branco seguidas."""
    if not isinstance(valor, str):
        return ""
    t = valor.replace("\r\n", "\n").replace("\r", "\n")
    t = _sem_controles(t, "\n\t")
    t = re.sub(r"\n{4,}", "\n\n\n", t)
    return t.strip()


def validar_texto(valor: object, obrigatorio: bool = True, campo: str = "texto") -> str:
    texto = limpar_texto(valor)
    if obrigatorio and not texto:
        raise AppError(422, "dados_invalidos", MSG_TEXTO, {campo: MSG_TEXTO})
    if len(texto) > MAX_TEXTO:
        raise AppError(422, "dados_invalidos", MSG_TEXTO_LONGO, {campo: MSG_TEXTO_LONGO})
    return texto


def validar_tipo(valor: object) -> str:
    if valor not in TIPOS:
        raise AppError(422, "dados_invalidos", MSG_TIPO, {"tipo": MSG_TIPO})
    return str(valor)


def validar_impacto(tipo: str, valor: object) -> str | None:
    """Só o erro tem impacto (opcional); nos outros tipos o valor é ignorado."""
    if tipo != "erro" or valor in (None, ""):
        return None
    if valor not in IMPACTOS:
        raise AppError(422, "dados_invalidos", MSG_IMPACTO, {"impacto": MSG_IMPACTO})
    return str(valor)


def validar_situacao(valor: object) -> str:
    if valor not in SITUACOES:
        raise AppError(422, "dados_invalidos", MSG_SITUACAO, {"situacao": MSG_SITUACAO})
    return str(valor)


def validar_nota(valor: object) -> str:
    nota = limpar_texto(valor)
    if len(nota) > MAX_NOTA:
        raise AppError(422, "dados_invalidos", MSG_NOTA, {"nota_interna": MSG_NOTA})
    return nota


def trecho(texto: str, maximo: int = MAX_TRECHO) -> str:
    """O começo do texto numa linha só (lista e assunto dos e-mails)."""
    t = " ".join(texto.split())
    return t if len(t) <= maximo else t[: maximo - 1].rstrip() + "…"


# ---- contexto da tela ----------------------------------------------------------------------------------------------

def _uma_linha(valor: object, maximo: int) -> str | None:
    if not isinstance(valor, str):
        return None
    t = " ".join(_sem_controles(valor).split())[:maximo].strip()
    return t or None


def limpar_pagina(valor: object) -> str | None:
    """O caminho da tela no site (começa com /), sem query nem hash, até 200 caracteres; o resto vira None."""
    t = _uma_linha(valor, 2000)
    if not t or not t.startswith("/") or t.startswith("//"):
        return None
    t = re.split(r"[?#]", t, maxsplit=1)[0].replace(" ", "")
    return t[:MAX_PAGINA] or None


def limpar_titulo(valor: object) -> str | None:
    return _uma_linha(valor, MAX_TITULO)


def limpar_tela(valor: object) -> str | None:
    """"1280x900" (largura x altura da janela); outro formato vira None."""
    return valor if isinstance(valor, str) and _RE_TELA.fullmatch(valor) else None


def limpar_versao(valor: object) -> str | None:
    return valor if isinstance(valor, str) and _RE_VERSAO.fullmatch(valor) else None


def limpar_navegador(valor: object) -> str | None:
    return _uma_linha(valor, MAX_NAVEGADOR)


def _quando(valor: object) -> str | None:
    return valor if isinstance(valor, str) and len(valor) <= 40 and _RE_QUANDO.fullmatch(valor) else None


def _erro_do_site(item: object) -> dict | None:
    if not isinstance(item, dict):
        return None
    tipo = erros.limpar(item.get("tipo"), erros.MAX_TIPO) if isinstance(item.get("tipo"), str) else ""
    if not tipo:
        return None
    return {"quando": _quando(item.get("quando")), "tipo": tipo,
            "mensagem": erros.limpar(item.get("mensagem"), erros.MAX_MENSAGEM) if isinstance(item.get("mensagem"), str) else "",
            "local": limpar_pagina(item.get("local")) or ""}


def _pedido_que_falhou(item: object) -> dict | None:
    if not isinstance(item, dict):
        return None
    metodo, status, caminho = item.get("metodo"), item.get("status"), item.get("caminho")
    if metodo not in _METODOS or isinstance(status, bool) or not isinstance(status, int) or not 0 <= status <= 599:
        return None
    caminho = erros.limpar(re.split(r"[?#]", caminho, maxsplit=1)[0], erros.MAX_LOCAL) if isinstance(caminho, str) else ""
    if not caminho.startswith("/"):
        return None
    codigo, rid = item.get("codigo"), item.get("request_id")
    return {"quando": _quando(item.get("quando")), "metodo": metodo, "caminho": caminho, "status": status,
            "codigo": codigo if isinstance(codigo, str) and _RE_CODIGO.fullmatch(codigo) else None,
            "request_id": rid if isinstance(rid, str) and _RE_REQUEST_ID.fullmatch(rid) else None}


def limpar_diagnostico(valor: object) -> dict | None:
    """O diagnóstico que o site manda (JSON em texto): até 10 erros do site {quando, tipo, mensagem, local} e 10
    pedidos à API que falharam {quando, metodo, caminho, status, codigo, request_id}, os textos pela limpeza do aviso de
    erros (`core.erros.limpar`: sem e-mails, números longos, tokens nem textos entre aspas). JSON inválido, item fora do
    formato ou nada aproveitável: sai (None quando não sobra nada). O resultado cabe em 8 KB."""
    if not isinstance(valor, str) or not valor.strip() or len(valor) > 64 * 1024:
        return None
    try:
        bruto = json.loads(valor)
    except ValueError:
        return None
    if not isinstance(bruto, dict):
        return None
    listas = {}
    for chave, limpar_item in (("erros", _erro_do_site), ("pedidos", _pedido_que_falhou)):
        itens = bruto.get(chave)
        if isinstance(itens, list):
            limpos = [x for x in (limpar_item(i) for i in itens[-MAX_DIAGNOSTICO_ITENS:]) if x]
            if limpos:
                listas[chave] = limpos
    if not listas:
        return None
    while len(json.dumps(listas, ensure_ascii=False).encode()) > MAX_DIAGNOSTICO_BYTES:
        maior = max(listas, key=lambda k: len(listas[k]))
        listas[maior] = listas[maior][1:]  # sai o mais antigo da lista maior
        if not listas[maior]:
            del listas[maior]
    return listas or None

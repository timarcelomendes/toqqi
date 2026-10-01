"""Logs sem dados de clientes vindos de erros do banco.

O PostgreSQL põe valores das linhas na mensagem de erro (o DETAIL de uma CHECK traz "Failing row contains (...)", o
de um UNIQUE traz "Key (email)=(...)") e o SQLAlchemy repete essa mensagem no texto da exceção; `hide_parameters`
(nos engines) esconde só os parâmetros da consulta. `instalar()` troca a fábrica de registros do `logging`: todo
registro com um erro do banco na cadeia da exceção (causa ou contexto) sai com o traceback de sempre (arquivos,
linhas e funções), mas com a mensagem de cada erro do banco trocada por um resumo sem dados (`descrever_erro`:
classe, SQLSTATE e os nomes da restrição, tabela e coluna). Erros do banco passados como argumento da mensagem
também viram o resumo. Vale para qualquer logger (aplicação, tarefas, uvicorn).
"""
import logging
import traceback

import psycopg
from sqlalchemy.exc import StatementError

_CAUSA = "\nThe above exception was the direct cause of the following exception:\n\n"
_CONTEXTO = "\nDuring handling of the above exception, another exception occurred:\n\n"
_instalado = False


def do_banco(e: object) -> bool:
    return isinstance(e, (StatementError, psycopg.Error))


def descrever_erro(e: BaseException) -> str:
    """Resumo sem dados: classe do erro, SQLSTATE e os nomes que o banco informa (restrição, tabela, coluna)."""
    orig = getattr(e, "orig", None) or e
    partes = [type(orig).__name__]
    codigo = getattr(orig, "sqlstate", None)
    if codigo:
        partes.append(f"SQLSTATE {codigo}")
    diag = getattr(orig, "diag", None)
    for campo, rotulo in (("constraint_name", "restrição"), ("table_name", "tabela"), ("column_name", "coluna")):
        valor = getattr(diag, campo, None) if diag is not None else None
        if valor:
            partes.append(f"{rotulo} {valor}")
    return ", ".join(partes)


def _cadeia(exc: BaseException) -> list[tuple[BaseException, str | None]]:
    """[(exceção, separador impresso depois dela)], da registrada para as mais antigas, como o Python percorre."""
    itens: list[tuple[BaseException, str | None]] = []
    vistos: set[int] = set()
    e: BaseException | None = exc
    separador = None
    while e is not None and id(e) not in vistos:
        vistos.add(id(e))
        itens.append((e, separador))
        if e.__cause__ is not None:
            e, separador = e.__cause__, _CAUSA
        elif e.__context__ is not None and not e.__suppress_context__:
            e, separador = e.__context__, _CONTEXTO
        else:
            e = None
    return itens


def _nome(tipo: type) -> str:
    return tipo.__qualname__ if tipo.__module__ == "builtins" else f"{tipo.__module__}.{tipo.__qualname__}"


def formatar(exc: BaseException) -> str:
    """O traceback como o Python imprime, com a mensagem de cada erro do banco trocada pelo resumo sem dados."""
    partes = []
    for e, separador in reversed(_cadeia(exc)):
        if e.__traceback__ is not None:
            partes.append("Traceback (most recent call last):\n")
            partes.extend(traceback.format_tb(e.__traceback__))
        if do_banco(e):
            partes.append(f"{_nome(type(e))}: {descrever_erro(e)}\n")
        else:
            partes.extend(traceback.format_exception_only(type(e), e))
        if separador:
            partes.append(separador)
    return "".join(partes).rstrip("\n")


def instalar() -> None:
    """Liga a limpeza em todos os registros de log do processo (uma vez)."""
    global _instalado
    if _instalado:
        return
    anterior = logging.getLogRecordFactory()

    def fabrica(*args, **kwargs) -> logging.LogRecord:
        registro = anterior(*args, **kwargs)
        exc = registro.exc_info[1] if registro.exc_info else None
        if exc is not None and any(do_banco(e) for e, _ in _cadeia(exc)):
            registro.exc_text = formatar(exc)
            registro.exc_info = None  # quem formata usa o texto pronto acima
        if isinstance(registro.args, tuple) and any(do_banco(a) for a in registro.args):
            registro.args = tuple(descrever_erro(a) if do_banco(a) else a for a in registro.args)
        return registro

    logging.setLogRecordFactory(fabrica)
    _instalado = True

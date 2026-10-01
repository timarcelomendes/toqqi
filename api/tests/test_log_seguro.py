"""Erros do banco no log sem dados de clientes: o engine esconde os parâmetros (`hide_parameters`) e
`core.log_seguro` troca a mensagem do erro do banco (que pode trazer valores) por um resumo sem dados."""
import logging

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from toqqi.core.db import engine
from toqqi.core.log_seguro import descrever_erro, formatar


DADO = "SEGREDO" + "-DO-CLIENTE"  # montado aqui: a linha que falha (e aparece no traceback) não traz o texto


def _erro_com_dado() -> DBAPIError:
    with engine().connect() as c:
        try:
            c.execute(text("select cast(:v as integer)"), {"v": DADO})
        except DBAPIError as e:
            return e
    raise AssertionError("o banco deveria recusar")


def test_mensagem_do_erro_do_banco_sem_dados(dono):
    e = _erro_com_dado()
    assert "SEGREDO" in str(e.orig)  # o PostgreSQL põe o valor na mensagem...
    assert "SEGREDO" not in str(e).replace(str(e.orig), "")  # ...e o engine não repete os parâmetros
    assert descrever_erro(e) == "InvalidTextRepresentation, SQLSTATE 22P02"
    assert "SEGREDO" not in formatar(e) and "Traceback" in formatar(e)


@pytest.mark.parametrize("como", ["exception", "argumento"])
def test_log_com_erro_do_banco_sai_sem_dados(dono, caplog, como):
    log = logging.getLogger("toqqi.teste")
    e = _erro_com_dado()
    with caplog.at_level(logging.ERROR, logger="toqqi.teste"):
        if como == "exception":
            try:
                raise RuntimeError("falhou ao gravar") from e
            except RuntimeError:
                log.exception("Erro ao gravar")
        else:
            log.error("Erro ao gravar: %s", e)
    assert "SEGREDO" not in caplog.text and "22P02" in caplog.text

"""Filtros de período (datas AAAA-MM-DD no fuso de São Paulo).

Datas de filtro só valem de 2000 a 2100: fora disso a conta do fim do dia (`ate` + 1 dia) ou do período anterior
estoura o calendário. Use `DataFiltro` nos modelos de filtro (query) e `data_filtro` nas rotas que recebem texto.
"""
from datetime import date, datetime, time, timedelta
from typing import Annotated
from zoneinfo import ZoneInfo

from pydantic import AfterValidator, BeforeValidator
from pydantic_core import PydanticCustomError

from toqqi.core.errors import AppError

FUSO = ZoneInfo("America/Sao_Paulo")
ANO_MINIMO, ANO_MAXIMO = 2000, 2100
MSG_FORMATO = "Informe uma data no formato AAAA-MM-DD."
MSG_FAIXA = "Use uma data entre 01/01/2000 e 31/12/2100."


def data_valida(d: date) -> bool:
    return ANO_MINIMO <= d.year <= ANO_MAXIMO


def _conferir_faixa(d: date | None) -> date | None:
    if d is not None and not data_valida(d):
        raise PydanticCustomError("toqqi_data", MSG_FAIXA)
    return d


def _vazio_none(v):
    return None if v == "" else v


# data opcional de filtro (query): vazio = sem filtro; fora de 2000–2100 = 422 com a mensagem acima
DataFiltro = Annotated[date | None, BeforeValidator(_vazio_none), AfterValidator(_conferir_faixa)]


def data_filtro(v: str | None, campo: str) -> date | None:
    if not v:
        return None
    try:
        d = date.fromisoformat(v)
    except ValueError:
        raise AppError(422, "dados_invalidos", "Confira os filtros.", {campo: MSG_FORMATO})
    if not data_valida(d):
        raise AppError(422, "dados_invalidos", "Confira os filtros.", {campo: MSG_FAIXA})
    return d


def limites(de: str | None, ate: str | None) -> tuple[datetime | None, datetime | None]:
    """(início do dia `de`, início do dia seguinte a `ate`), cada um None se não informado."""
    d1, d2 = data_filtro(de, "de"), data_filtro(ate, "ate")
    return (datetime.combine(d1, time.min, tzinfo=FUSO) if d1 else None,
            datetime.combine(d2 + timedelta(days=1), time.min, tzinfo=FUSO) if d2 else None)


def periodo(coluna, de: str | None, ate: str | None) -> list:
    """Condições SQL para coluna timestamptz entre o início de `de` e o fim de `ate`."""
    inicio, fim = limites(de, ate)
    filtros = []
    if inicio:
        filtros.append(coluna >= inicio)
    if fim:
        filtros.append(coluna < fim)
    return filtros


def inicio_do_dia(d: date) -> datetime:
    return datetime.combine(d, time.min, tzinfo=FUSO)


def entre_datas(coluna, de: date | None, ate: date | None) -> list:
    """Como `periodo`, com datas já interpretadas: do início de `de` ao fim de `ate` (dias de São Paulo)."""
    filtros = []
    if de:
        filtros.append(coluna >= inicio_do_dia(de))
    if ate:
        filtros.append(coluna < inicio_do_dia(ate + timedelta(days=1)))
    return filtros

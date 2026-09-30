"""Filtros de período (datas AAAA-MM-DD no fuso de São Paulo)."""
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from toqqi.core.errors import AppError

FUSO = ZoneInfo("America/Sao_Paulo")


def data_filtro(v: str | None, campo: str) -> date | None:
    if not v:
        return None
    try:
        return date.fromisoformat(v)
    except ValueError:
        raise AppError(422, "dados_invalidos", "Confira os filtros.",
                       {campo: "Informe uma data no formato AAAA-MM-DD."})


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

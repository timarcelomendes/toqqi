from datetime import date
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query

from toqqi.core.deps import Contexto, requer
from toqqi.core.errors import AppError
from toqqi.modulos.auditoria import servico

router = APIRouter(prefix="/auditoria", tags=["auditoria"])


def _data(v: str | None, campo: str) -> date | None:
    """Aceita vazio (sem filtro) ou AAAA-MM-DD."""
    if not v:
        return None
    try:
        return date.fromisoformat(v)
    except ValueError:
        raise AppError(422, "dados_invalidos", "Confira os filtros.",
                       {campo: "Informe uma data no formato AAAA-MM-DD."})


@router.get("")
def listar(
    de: Annotated[str | None, Query()] = None,
    ate: Annotated[str | None, Query()] = None,
    gravidade: Annotated[Literal["", "info", "sucesso", "atencao", "erro"] | None, Query()] = None,
    busca: Annotated[str | None, Query(max_length=100)] = None,
    pagina: Annotated[int, Query(ge=1, le=100000)] = 1,
    ctx: Contexto = Depends(requer("auditoria.ver")),
):
    return servico.listar(
        ctx, _data(de, "de"), _data(ate, "ate"), gravidade or None, (busca or "").strip() or None, pagina
    )

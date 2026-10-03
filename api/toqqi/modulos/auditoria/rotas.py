from datetime import date
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query

from toqqi.core.auditoria import GRUPOS, grupos_json
from toqqi.core.deps import Contexto, requer
from toqqi.core.filtros import data_filtro
from toqqi.core.paginacao import Pagina, pagina
from toqqi.modulos.auditoria import emails, servico

router = APIRouter(prefix="/auditoria", tags=["auditoria"])
VER = requer("auditoria.ver")


def _data(v: str | None, campo: str) -> date | None:
    """Aceita vazio (sem filtro) ou AAAA-MM-DD de 2000 a 2100."""
    return data_filtro(v, campo)


@router.get("")
def listar(
    de: Annotated[str | None, Query()] = None,
    ate: Annotated[str | None, Query()] = None,
    gravidade: Annotated[Literal["", "info", "sucesso", "atencao", "erro"] | None, Query()] = None,
    busca: Annotated[str | None, Query(max_length=100)] = None,
    pagina: Annotated[int, Query(ge=1, le=100000)] = 1,
    grupo: Annotated[Literal[("", *GRUPOS)] | None, Query()] = None,  # type: ignore[valid-type]
    ctx: Contexto = Depends(VER),
):
    return servico.listar(
        ctx, _data(de, "de"), _data(ate, "ate"), gravidade or None, (busca or "").strip() or None, pagina,
        grupo or None,
    )


@router.get("/grupos")
def grupos(ctx: Contexto = Depends(VER)):
    """Os grupos dos eventos, na ordem da tela: [{chave, rotulo}] (etapa 5f)."""
    return grupos_json()


@router.get("/emails")
def emails_enviados(filtros: Annotated[emails.FiltrosEmails, Query()], pg: Pagina = Depends(pagina),
                    ctx: Contexto = Depends(VER)):
    """E-mails enviados (etapa 5e): página com `falhas_7_dias` e o período usado."""
    return emails.listar(ctx, filtros, pg)

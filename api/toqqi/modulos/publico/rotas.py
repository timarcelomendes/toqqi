from typing import Annotated

from fastapi import APIRouter, Query, Request

from toqqi.core.rate_limit import LIMITE_PUBLICO_ABRIR, LIMITE_RESPONDER_CONVITE, LIMITE_RESPONDER_LINK, limiter
from toqqi.modulos.publico import servico
from toqqi.modulos.publico.esquemas import ResponderIn, ResponderLinkIn

router = APIRouter(prefix="/publico", tags=["publico"])


def _ip(request: Request) -> str | None:
    return request.client.host if request.client else None


@router.get("/convites/{token}")
@limiter.limit(LIMITE_PUBLICO_ABRIR)
def abrir_convite(request: Request, token: str):
    return servico.abrir_convite(token)


@router.post("/convites/{token}/responder", status_code=201)
@limiter.limit(LIMITE_RESPONDER_CONVITE)
def responder_convite(request: Request, token: str, dados: ResponderIn):
    return servico.responder_convite(token, dados.respostas, _ip(request))


@router.get("/formularios/{codigo}")
@limiter.limit(LIMITE_PUBLICO_ABRIR)
def abrir_formulario(request: Request, codigo: str,
                     referencia: Annotated[str | None, Query(max_length=120)] = None):
    return servico.abrir_formulario(codigo, referencia)


@router.post("/formularios/{codigo}/responder", status_code=201)
@limiter.limit(LIMITE_RESPONDER_LINK)
def responder_formulario(request: Request, codigo: str, dados: ResponderLinkIn):
    return servico.responder_formulario(codigo, dados, _ip(request))

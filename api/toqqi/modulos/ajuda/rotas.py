from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from toqqi.core.deps import Contexto, requer
from toqqi.modulos.ajuda import servico

router = APIRouter(prefix="/ajuda", tags=["ajuda"])


@router.get("")
def ajuda(_: Contexto = Depends(requer())):
    """O conteúdo da Ajuda como está ({versao, jornadas, topicos}), para qualquer usuário logado."""
    return JSONResponse(servico.carregar(), headers={"Cache-Control": "private, max-age=300"})

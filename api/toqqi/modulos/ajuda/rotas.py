from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from toqqi.core.deps import Contexto, requer
from toqqi.modulos.ajuda import servico

router = APIRouter(prefix="/ajuda", tags=["ajuda"])


@router.get("")
def ajuda(_: Contexto = Depends(requer())):
    """O conteúdo da Ajuda ({versao, jornadas, topicos}), com as marcas dos parâmetros trocadas pelos valores de hoje,
    para qualquer usuário logado. Cache de 60 s no navegador (um parâmetro mudado aparece logo)."""
    return JSONResponse(servico.conteudo(), headers={"Cache-Control": "private, max-age=60"})

import uuid
from typing import Literal

from fastapi import APIRouter, Depends, File, Response, UploadFile

from toqqi.core.deps import Contexto, requer
from toqqi.modulos.importacao import servico
from toqqi.modulos.importacao.esquemas import ConferirIn, ImportarIn
from toqqi.modulos.importacao.planilha import MAX_BYTES

router = APIRouter(prefix="/importacao", tags=["importacao"])
USAR = requer("importacao.usar")


@router.get("/modelo")
def modelo(tipo: Literal["contatos"] = "contatos", ctx: Contexto = Depends(USAR)):
    return Response(servico.modelo_csv(), media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": 'attachment; filename="modelo-contatos.csv"'})


@router.post("/analisar")
def analisar(arquivo: UploadFile = File(...), ctx: Contexto = Depends(USAR)):
    conteudo = arquivo.file.read(MAX_BYTES + 1)
    return servico.analisar(ctx, arquivo.filename or "", conteudo)


@router.post("/{imp_id}/conferir")
def conferir(imp_id: uuid.UUID, dados: ConferirIn, ctx: Contexto = Depends(USAR)):
    return servico.conferir(ctx, imp_id, dados)


@router.post("/{imp_id}/importar")
def importar(imp_id: uuid.UUID, dados: ImportarIn, ctx: Contexto = Depends(USAR)):
    return servico.importar(ctx, imp_id, dados)

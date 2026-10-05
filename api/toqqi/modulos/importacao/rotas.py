import uuid
from typing import Literal

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, Response, UploadFile

from toqqi.core.deps import Contexto, requer
from toqqi.modulos.ia.servico import processar_conta
from toqqi.modulos.importacao import servico
from toqqi.modulos.importacao.esquemas import ConferirIn, ImportarIn
from toqqi.modulos.importacao.planilha import MAX_BYTES

router = APIRouter(prefix="/importacao", tags=["importacao"])
USAR = requer("importacao.usar")
Tipo = Literal["contatos", "respostas"]


@router.get("/modelo")
def modelo(tipo: Tipo = "contatos", ctx: Contexto = Depends(USAR)):
    return Response(servico.modelo_csv(tipo), media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="modelo-{tipo}.csv"'})


@router.post("/analisar")
def analisar(arquivo: UploadFile = File(...), tipo: Tipo = Form("contatos"), ctx: Contexto = Depends(USAR)):
    conteudo = arquivo.file.read(MAX_BYTES + 1)
    return servico.analisar(ctx, arquivo.filename or "", conteudo, tipo)


@router.post("/{imp_id}/conferir")
def conferir(imp_id: uuid.UUID, dados: ConferirIn, ctx: Contexto = Depends(USAR)):
    return servico.conferir(ctx, imp_id, dados)


@router.post("/{imp_id}/importar")
def importar(imp_id: uuid.UUID, dados: ImportarIn, tarefas: BackgroundTasks, ctx: Contexto = Depends(USAR)):
    resultado = servico.importar(ctx, imp_id, dados)
    if resultado.get("ia_marcadas"):  # etapa 5h: a fila da IA desta conta já, depois do commit
        tarefas.add_task(processar_conta, ctx.conta_id)
    return resultado

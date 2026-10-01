import json
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, Query, Request, Response
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import PlainTextResponse

from toqqi.core.deps import Contexto, requer, requer_admin
from toqqi.core.errors import AppError
from toqqi.modulos.integracoes.webhooks import coletar_entregas
from toqqi.modulos.whatsapp import servico, webhook
from toqqi.modulos.whatsapp.esquemas import AlterarIn, ConectarIn, TesteIn

router = APIRouter(prefix="/integracoes/whatsapp", tags=["integracoes"])
router_publico = APIRouter(prefix="/publico/whatsapp", tags=["publico"])


@router.get("")
def ver(ctx: Contexto = Depends(requer("envios.ver"))):
    return servico.ver(ctx)


@router.put("")
def conectar(dados: ConectarIn, ctx: Contexto = Depends(requer_admin)):
    return servico.conectar(ctx, dados)


@router.patch("")
def alterar(dados: AlterarIn, ctx: Contexto = Depends(requer_admin)):
    return servico.alterar(ctx, dados)


@router.delete("", status_code=204)
def desconectar(ctx: Contexto = Depends(requer_admin)):
    servico.desconectar(ctx)
    return Response(status_code=204)


@router.post("/teste")
def teste(dados: TesteIn, ctx: Contexto = Depends(requer_admin)):
    return servico.testar(ctx, dados.telefone)


# ---- webhook da Meta ----------------------------------------------------------

@router_publico.get("/webhook", response_class=PlainTextResponse)
def verificar(modo: Annotated[str | None, Query(alias="hub.mode")] = None,
              token: Annotated[str | None, Query(alias="hub.verify_token")] = None,
              challenge: Annotated[str | None, Query(alias="hub.challenge", max_length=200)] = None):
    return webhook.desafio(modo, token, challenge)


@router_publico.post("/webhook")
async def receber(request: Request, tarefas: BackgroundTasks):
    corpo = await request.body()
    webhook.conferir_assinatura(corpo, request.headers.get("x-hub-signature-256"))
    try:
        dados = json.loads(corpo)
    except ValueError:
        dados = None
    if not isinstance(dados, dict):
        raise AppError(422, "dados_invalidos", "Aviso da Meta em formato inválido.")
    with coletar_entregas() as entregas:
        depois = await run_in_threadpool(webhook.receber, dados)
    tarefas.add_task(webhook.concluir, depois, entregas)
    return {"ok": True}

from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, Query, Request, Response

from toqqi.core.deps import Contexto, requer_admin
from toqqi.core.rate_limit import LIMITE_INTEGRACAO, limiter
from toqqi.modulos.envios.processamento import processar_lista
from toqqi.modulos.integracoes import chave, empresas, pesquisas, webhooks
from toqqi.modulos.integracoes.chave import ContextoIntegracao, contexto_integracao, limite_por_chave
from toqqi.modulos.integracoes.esquemas import CsatIn, PesquisaIn, WebhookAlterarIn, WebhookIn

router = APIRouter(prefix="/integracoes", tags=["integracoes"])
router_chave = APIRouter(prefix="/integracao", tags=["integracao"])


# ---- chave da conta (perfil admin) -----------------------------------------

@router.get("/chave")
def ver_chave(ctx: Contexto = Depends(requer_admin)):
    return chave.ver(ctx)


@router.post("/chave", status_code=201)
def gerar_chave(ctx: Contexto = Depends(requer_admin)):
    return chave.gerar(ctx)


@router.delete("/chave", status_code=204)
def revogar_chave(ctx: Contexto = Depends(requer_admin)):
    chave.revogar(ctx)
    return Response(status_code=204)


# ---- webhooks de saída (perfil admin) --------------------------------------

@router.get("/webhooks")
def listar_webhooks(ctx: Contexto = Depends(requer_admin)):
    return webhooks.listar(ctx)


@router.post("/webhooks", status_code=201)
def criar_webhook(dados: WebhookIn, ctx: Contexto = Depends(requer_admin)):
    return webhooks.criar(ctx, dados)


@router.patch("/webhooks/{webhook_id}")
def alterar_webhook(webhook_id: int, dados: WebhookAlterarIn, ctx: Contexto = Depends(requer_admin)):
    return webhooks.alterar(ctx, webhook_id, dados)


@router.delete("/webhooks/{webhook_id}", status_code=204)
def excluir_webhook(webhook_id: int, ctx: Contexto = Depends(requer_admin)):
    webhooks.excluir(ctx, webhook_id)
    return Response(status_code=204)


@router.post("/webhooks/{webhook_id}/novo-segredo")
def novo_segredo(webhook_id: int, ctx: Contexto = Depends(requer_admin)):
    return webhooks.trocar_segredo(ctx, webhook_id)


@router.post("/webhooks/{webhook_id}/testar")
def testar_webhook(webhook_id: int, ctx: Contexto = Depends(requer_admin)):
    return webhooks.testar(ctx, webhook_id)


@router.get("/webhooks/{webhook_id}/entregas")
def entregas(webhook_id: int, pagina: Annotated[int, Query(ge=1, le=10000)] = 1,
             ctx: Contexto = Depends(requer_admin)):
    return webhooks.entregas(ctx, webhook_id, pagina)


# ---- rotas da chave (ERP, Zapier, Make, n8n) --------------------------------

def _responder(response: Response, tarefas: BackgroundTasks, resultado: tuple[dict, bool, list]) -> dict:
    corpo, nova, envios = resultado
    response.status_code = 201 if nova else 200
    if envios:
        tarefas.add_task(processar_lista, envios)
    return corpo


@router_chave.post("/pesquisas", status_code=201)
@limiter.limit(LIMITE_INTEGRACAO, key_func=limite_por_chave)
def pesquisa(request: Request, response: Response, dados: PesquisaIn, tarefas: BackgroundTasks,
             ci: ContextoIntegracao = Depends(contexto_integracao)):
    return _responder(response, tarefas, pesquisas.disparar(ci, dados))


@router_chave.post("/csat", status_code=201)
@limiter.limit(LIMITE_INTEGRACAO, key_func=limite_por_chave)
def csat(request: Request, response: Response, dados: CsatIn, tarefas: BackgroundTasks,
         ci: ContextoIntegracao = Depends(contexto_integracao)):
    if dados.enviar_email is not None:
        dados.enviar = dados.enviar_email
    return _responder(response, tarefas, pesquisas.disparar(ci, dados, "csat", dados.assunto))


@router_chave.post("/empresas")
@limiter.limit(LIMITE_INTEGRACAO, key_func=limite_por_chave)
def empresa(request: Request, response: Response, dados: empresas.EmpresaIntegracaoIn,
            ci: ContextoIntegracao = Depends(contexto_integracao)):
    """Etapa 5i: cria ou atualiza a empresa (valor, renovação) e marca a perda ou o retorno."""
    corpo, nova = empresas.salvar(ci, dados)
    response.status_code = 201 if nova else 200
    return corpo


@router_chave.get("/teste")
@limiter.limit(LIMITE_INTEGRACAO, key_func=limite_por_chave)
def teste(request: Request, ci: ContextoIntegracao = Depends(contexto_integracao)):
    return {"conta": ci.conta_nome, "ok": True}

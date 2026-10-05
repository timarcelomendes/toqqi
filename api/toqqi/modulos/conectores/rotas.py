"""Etapa 5j: conectores (Integrações › RD Station CRM). Configurar é do administrador da conta; o aviso do RD chega
sem login, pelo segredo no endereço."""
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, Request
from pydantic import BaseModel, Field

from toqqi.core.deps import Contexto, requer_admin
from toqqi.modulos.conectores import servico
from toqqi.modulos.envios.processamento import processar_lista

router = APIRouter(prefix="/integracoes/conectores", tags=["conectores"])
router_publico = APIRouter(prefix="/publico/conectores", tags=["conectores"])


class ConectarIn(BaseModel):
    token: Annotated[str, Field(min_length=10, max_length=200)]
    pesquisar_ao_ganhar: bool = True


class AlterarIn(BaseModel):
    pesquisar_ao_ganhar: bool


@router.get("")
def ver(ctx: Contexto = Depends(requer_admin)):
    return servico.ver(ctx)


@router.put("/rdstation-crm")
def conectar(dados: ConectarIn, ctx: Contexto = Depends(requer_admin)):
    """Confere o token no RD, guarda cifrado e (com `pesquisar_ao_ganhar`) cadastra o aviso de negócio ganho."""
    return servico.conectar(ctx, dados.token, dados.pesquisar_ao_ganhar)


@router.patch("/rdstation-crm")
def alterar(dados: AlterarIn, ctx: Contexto = Depends(requer_admin)):
    return servico.alterar(ctx, dados.pesquisar_ao_ganhar)


@router.post("/rdstation-crm/sincronizar")
def sincronizar(ctx: Contexto = Depends(requer_admin)):
    """Traz empresas e contatos do RD (cria o que falta; não apaga nem sobrescreve)."""
    return servico.sincronizar(ctx)


@router.delete("/rdstation-crm", status_code=204)
def desconectar(ctx: Contexto = Depends(requer_admin)):
    servico.desconectar(ctx)


@router_publico.post("/rdstation-crm/{segredo}")
async def aviso(segredo: str, request: Request, tarefas: BackgroundTasks):
    """Aviso do RD (webhook `crm_deal_updated`): negócio ganho → pesquisa aos contatos. Sempre 200."""
    try:
        corpo = await request.json()
    except ValueError:
        corpo = {}
    envios = servico.receber_aviso(segredo, corpo)
    if envios:
        tarefas.add_task(processar_lista, envios)
    return {"ok": True}

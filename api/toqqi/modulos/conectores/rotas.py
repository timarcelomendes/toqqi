"""Etapa 5j: conectores (Integrações › RD Station CRM). Configurar é do administrador da conta; o aviso do RD chega
sem login, pelo segredo no endereço."""
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, Request
from pydantic import BaseModel, Field

from toqqi.core.deps import Contexto, requer_admin
from toqqi.modulos.conectores import servico, servico_omie
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
    return servico.ver(ctx) | {"omie": servico_omie.ver(ctx)}


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


# ---- Omie (ERP) ---------------------------------------------------------------------------------

class ConectarOmieIn(BaseModel):
    app_key: Annotated[str, Field(min_length=5, max_length=100)]
    app_secret: Annotated[str, Field(min_length=10, max_length=200)]
    pesquisar_ao_faturar: bool = True


class AlterarOmieIn(BaseModel):
    pesquisar_ao_faturar: bool


@router.put("/omie")
def conectar_omie(dados: ConectarOmieIn, ctx: Contexto = Depends(requer_admin)):
    """Confere as chaves no Omie e guarda cifradas; devolve o endereço para cadastrar os avisos no Omie."""
    return servico_omie.conectar(ctx, dados.app_key, dados.app_secret, dados.pesquisar_ao_faturar)


@router.patch("/omie")
def alterar_omie(dados: AlterarOmieIn, ctx: Contexto = Depends(requer_admin)):
    return servico_omie.alterar(ctx, dados.pesquisar_ao_faturar)


@router.post("/omie/sincronizar")
def sincronizar_omie(ctx: Contexto = Depends(requer_admin)):
    """Traz os clientes do Omie (cria o que falta; não apaga nem sobrescreve)."""
    return servico_omie.sincronizar(ctx)


@router.delete("/omie", status_code=204)
def desconectar_omie(ctx: Contexto = Depends(requer_admin)):
    servico_omie.desconectar(ctx)


@router_publico.post("/omie/{segredo}")
async def aviso_omie(segredo: str, request: Request, tarefas: BackgroundTasks):
    """Aviso do Omie (pedido faturado ou nota autorizada) → pesquisa ao cliente. Sempre 200."""
    try:
        corpo = await request.json()
    except ValueError:
        corpo = {}
    envios = servico_omie.receber_aviso(segredo, corpo)
    if envios:
        tarefas.add_task(processar_lista, envios)
    return {"ok": True}

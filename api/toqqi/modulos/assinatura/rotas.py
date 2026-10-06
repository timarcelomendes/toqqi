import hmac
import json

from fastapi import APIRouter, BackgroundTasks, Depends, Request
from fastapi.concurrency import run_in_threadpool

from toqqi.core.deps import Contexto, requer
from toqqi.core.errors import AppError, nao_encontrado
from toqqi.core.planos import Contrato, planos_json, preco_mensal, valor_contrato
from toqqi.core.planos import descricao as descricao_contrato
from toqqi.core.rate_limit import LIMITE_ASAAS_WEBHOOK, limiter
from toqqi.modulos.assinatura import servico, webhook
from toqqi.modulos.assinatura.esquemas import AssinarIn, DadosCobrancaIn, PlanoIn

router = APIRouter(prefix="/assinatura", tags=["assinatura"])
router_asaas = APIRouter(prefix="/asaas", tags=["publico"])
GERENCIAR = requer("assinatura.gerenciar")


@router.get("/planos")
def planos(ctx: Contexto = Depends(requer())):
    """Preço e limite atuais de cada plano (etapa 5g: parâmetros da plataforma)."""
    return planos_json()


@router.get("/preco")
def preco(plano: str, ciclo: str = "mensal", forma: str = "qualquer", contatos: int | None = None,
          cota_ia: int | None = None, ctx: Contexto = Depends(requer())):
    """Etapa 5k: o valor de cada fatura de um contrato (a calculadora da tela faz a mesma conta; esta rota é a prova)."""
    c = servico.contrato_valido(Contrato(plano, ciclo, forma, contatos, cota_ia))
    return {"valor": valor_contrato(c), "por_mes": preco_mensal(c), "descricao": descricao_contrato(c)}


@router.get("")
def obter(ctx: Contexto = Depends(GERENCIAR)):
    return servico.obter(ctx)


@router.post("", status_code=201)
def assinar(dados: AssinarIn, ctx: Contexto = Depends(GERENCIAR)):
    return servico.assinar(ctx, dados)


@router.put("/plano")
def trocar_plano(dados: PlanoIn, ctx: Contexto = Depends(GERENCIAR)):
    return servico.trocar_plano(ctx, dados.plano, dados.preco, dados.contatos, dados.cota_ia)


@router.put("/dados")
def alterar_dados(dados: DadosCobrancaIn, ctx: Contexto = Depends(GERENCIAR)):
    return servico.alterar_dados(ctx, dados)


@router.post("/cancelar")
def cancelar(ctx: Contexto = Depends(GERENCIAR)):
    return servico.cancelar(ctx)


# ---- webhook do Asaas (sem login) ----------------------------------------------------------

@router_asaas.post("/webhook")
@limiter.limit(LIMITE_ASAAS_WEBHOOK)
async def receber(request: Request, tarefas: BackgroundTasks):
    esperado = webhook.token()
    if esperado is None:
        raise nao_encontrado()
    recebido = request.headers.get("asaas-access-token") or ""
    if not hmac.compare_digest(recebido.encode(), esperado.encode()):
        raise AppError(401, "token_invalido", "Token do webhook inválido.")
    try:
        dados = json.loads(await request.body())
    except ValueError:
        dados = None
    if not isinstance(dados, dict):
        raise AppError(422, "dados_invalidos", "Aviso do Asaas em formato inválido.")
    resposta, evento_id = await run_in_threadpool(webhook.receber, dados)
    if evento_id is not None:
        tarefas.add_task(webhook.processar_depois, evento_id)  # depois da resposta: o Asaas pede 200 depressa
    return resposta

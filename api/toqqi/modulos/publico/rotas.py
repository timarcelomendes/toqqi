from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Query, Request, Response
from fastapi.concurrency import run_in_threadpool
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError

from toqqi.core.errors import AppError
from toqqi.core.rate_limit import (
    LIMITE_DESCADASTRO,
    LIMITE_IMAGEM,
    LIMITE_PUBLICO_ABRIR,
    LIMITE_RESPONDER_CONVITE,
    LIMITE_RESPONDER_LINK,
    limiter,
)
from toqqi.modulos.acoes.automatica import coletar_alertas, enviar_alertas
from toqqi.modulos.envios import descadastro
from toqqi.modulos.envios.agradecimento import coletar_envios
from toqqi.modulos.envios.esquemas import DescadastroPublicoIn
from toqqi.modulos.envios.processamento import processar_lista
from toqqi.modulos.ia.servico import analisar as analisar_com_ia
from toqqi.modulos.ia.servico import coletar_analises
from toqqi.modulos.imagens import servico as imagens
from toqqi.modulos.integracoes.webhooks import coletar_entregas, entregar_lista
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
def responder_convite(request: Request, token: str, dados: ResponderIn, tarefas: BackgroundTasks):
    with (coletar_envios() as envios, coletar_entregas() as entregas, coletar_alertas() as alertas,
          coletar_analises() as analises):
        resultado = servico.responder_convite(token, dados.respostas, _ip(request))
    tarefas.add_task(processar_lista, envios)  # agradecimento, depois do commit
    tarefas.add_task(entregar_lista, entregas)  # webhooks de saída (resposta.criada)
    tarefas.add_task(enviar_alertas, alertas)  # "Alerta de risco" ao responsável (ação alta)
    tarefas.add_task(analisar_com_ia, analises)  # análise do comentário pela IA
    return resultado


@router.get("/formularios/{codigo}")
@limiter.limit(LIMITE_PUBLICO_ABRIR)
def abrir_formulario(request: Request, codigo: str,
                     referencia: Annotated[str | None, Query(max_length=120)] = None):
    return servico.abrir_formulario(codigo, referencia)


@router.post("/formularios/{codigo}/responder", status_code=201)
@limiter.limit(LIMITE_RESPONDER_LINK)
def responder_formulario(request: Request, codigo: str, dados: ResponderLinkIn, tarefas: BackgroundTasks):
    with (coletar_envios() as envios, coletar_entregas() as entregas, coletar_alertas() as alertas,
          coletar_analises() as analises):
        resultado = servico.responder_formulario(codigo, dados, _ip(request))
    tarefas.add_task(processar_lista, envios)
    tarefas.add_task(entregar_lista, entregas)
    tarefas.add_task(enviar_alertas, alertas)
    tarefas.add_task(analisar_com_ia, analises)
    return resultado


# ---- descadastro (link do rodapé e List-Unsubscribe) -------------------------

@router.get("/descadastro/{token}")
@limiter.limit(LIMITE_DESCADASTRO)
def abrir_descadastro(request: Request, token: str):
    return descadastro.abrir(token)


@router.post("/descadastro/{token}")
@limiter.limit(LIMITE_DESCADASTRO)
async def descadastrar(request: Request, token: str, tarefas: BackgroundTasks):
    """JSON {motivo?} ou {voltar: true} (página /sair); formulário `List-Unsubscribe=One-Click` (um clique,
    enviado pelo próprio programa de e-mail, RFC 8058)."""
    tipo = request.headers.get("content-type", "").split(";")[0].strip().lower()
    if tipo in ("application/x-www-form-urlencoded", "multipart/form-data"):
        formulario = await request.form()
        if formulario.get("List-Unsubscribe") != "One-Click":
            raise AppError(422, "dados_invalidos", "Pedido de descadastro inválido.")
        motivo, origem, voltar = None, "um_clique", False
    else:
        corpo = await request.body()
        try:
            dados = DescadastroPublicoIn.model_validate_json(corpo) if corpo.strip() else DescadastroPublicoIn()
        except ValidationError as e:
            raise RequestValidationError(e.errors())
        motivo, origem, voltar = dados.motivo, "link", dados.voltar
    if voltar:
        return await run_in_threadpool(descadastro.voltar, token)
    with coletar_entregas() as entregas:
        resultado = await run_in_threadpool(descadastro.descadastrar, token, motivo, origem)
    tarefas.add_task(entregar_lista, entregas)  # webhooks de saída (contato.descadastrado)
    return resultado


# ---- imagens (logo da conta e dos formulários) --------------------------------

@router.get("/imagens/{chave}")
@limiter.limit(LIMITE_IMAGEM)
def imagem(request: Request, chave: str):
    """A imagem, sem login. O conteúdo de uma chave nunca muda (trocar o logo gera chave nova): cache longo."""
    achada = imagens.abrir_publica(chave, request.headers.get("if-none-match"))
    if achada is None:
        raise AppError(404, "nao_encontrado", "Imagem não encontrada.")
    tipo, sha256, dados = achada
    cabecalhos = {"Cache-Control": imagens.CACHE, "ETag": f'"{sha256}"', "X-Content-Type-Options": "nosniff"}
    if dados is None:
        return Response(status_code=304, headers=cabecalhos)
    return Response(dados, media_type=tipo, headers=cabecalhos)

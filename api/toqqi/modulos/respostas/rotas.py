from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, Query, Response

from toqqi.core.deps import Contexto, requer, requer_admin
from toqqi.core.paginacao import Pagina, pagina
from toqqi.modulos.acoes.automatica import coletar_alertas, enviar_alertas
from toqqi.modulos.integracoes.webhooks import coletar_entregas, entregar_lista
from toqqi.modulos.respostas import servico, temas
from toqqi.modulos.respostas.esquemas import AnaliseIn, FiltrosRespostas, RespostaManualIn

router = APIRouter(tags=["respostas"])
VER = requer("respostas.ver")
EDITAR = requer("respostas.editar")


def csv_resposta(conteudo: str, nome: str) -> Response:
    return Response(conteudo.encode("utf-8"), media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="{nome}"'})


@router.get("/respostas/temas")
def listar_temas(ctx: Contexto = Depends(VER)):
    return temas.lista()


@router.get("/respostas.csv")
def exportar(filtros: Annotated[FiltrosRespostas, Query()], ctx: Contexto = Depends(requer("painel.exportar"))):
    return csv_resposta(servico.exportar_csv(ctx, filtros), servico.nome_csv())


@router.get("/respostas")
def listar(filtros: Annotated[FiltrosRespostas, Query()], pg: Pagina = Depends(pagina), ctx: Contexto = Depends(VER)):
    return servico.listar(ctx, filtros, pg)


@router.post("/respostas", status_code=201)
def registrar(dados: RespostaManualIn, tarefas: BackgroundTasks, ctx: Contexto = Depends(EDITAR)):
    with coletar_entregas() as entregas, coletar_alertas() as alertas:
        resultado = servico.registrar_manual(ctx, dados)
    tarefas.add_task(entregar_lista, entregas)  # webhooks de saída (resposta.criada), depois do commit
    tarefas.add_task(enviar_alertas, alertas)   # "Alerta de risco" ao responsável
    return resultado


@router.get("/respostas/{resposta_id}")
def obter(resposta_id: int, ctx: Contexto = Depends(VER)):
    return servico.obter(ctx, resposta_id)


@router.patch("/respostas/{resposta_id}")
def analisar(resposta_id: int, dados: AnaliseIn, ctx: Contexto = Depends(EDITAR)):
    return servico.analisar(ctx, resposta_id, dados)


@router.post("/respostas/{resposta_id}/arquivar")
def arquivar(resposta_id: int, ctx: Contexto = Depends(EDITAR)):
    return servico.arquivar(ctx, resposta_id, True)


@router.post("/respostas/{resposta_id}/restaurar")
def restaurar(resposta_id: int, ctx: Contexto = Depends(EDITAR)):
    return servico.arquivar(ctx, resposta_id, False)


@router.delete("/respostas/{resposta_id}", status_code=204)
def excluir(resposta_id: int, ctx: Contexto = Depends(requer_admin)):
    servico.excluir(ctx, resposta_id)
    return Response(status_code=204)

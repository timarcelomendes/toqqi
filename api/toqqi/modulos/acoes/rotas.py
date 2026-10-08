from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, Query, Response
from pydantic import BaseModel, Field

from toqqi.core.deps import Contexto, requer
from toqqi.core.paginacao import Pagina, pagina
from toqqi.modulos.acoes import detratores, panorama, servico
from toqqi.modulos.acoes.esquemas import AcaoAlterarIn, AcaoIn, ConfigAcoesIn, FiltrosAcoes, FiltrosListaAcoes
from toqqi.modulos.acoes.passos import coletar_passos, sugerir_passos
from toqqi.modulos.envios.processamento import processar_lista
from toqqi.modulos.painel.rotas import FiltrosPainel

router = APIRouter(prefix="/acoes", tags=["acoes"])
VER = requer("acoes.ver")
TRATAR = requer("acoes.tratar")


@router.get("/quadro")
def quadro(filtros: Annotated[FiltrosAcoes, Query()], ctx: Contexto = Depends(VER)):
    return servico.quadro(ctx, filtros)


@router.get("/panorama")
def ver_panorama(filtros: Annotated[FiltrosAcoes, Query()], ctx: Contexto = Depends(VER)):
    """O topo do quadro: prazos das abertas, carga por responsável e as concluídas nos últimos 30 dias."""
    return panorama.panorama(ctx, filtros)


@router.get("/configuracao")
def ver_config(ctx: Contexto = Depends(VER)):
    return servico.ver_config(ctx)


@router.put("/configuracao")
def salvar_config(dados: ConfigAcoesIn, ctx: Contexto = Depends(requer("configuracoes.gerenciar"))):
    return servico.salvar_config(ctx, dados)


@router.get("")
def listar(filtros: Annotated[FiltrosListaAcoes, Query()], pg: Pagina = Depends(pagina),
           ctx: Contexto = Depends(VER)):
    return servico.listar(ctx, filtros, pg)


@router.post("", status_code=201)
def criar(dados: AcaoIn, tarefas: BackgroundTasks, ctx: Contexto = Depends(TRATAR)):
    with coletar_passos() as passos:
        resultado = servico.criar(ctx, dados)
    tarefas.add_task(sugerir_passos, passos)  # passos sugeridos pela IA (ação de uma resposta), depois do commit
    return resultado


@router.post("/detratores")
def criar_para_detratores(tarefas: BackgroundTasks, dados: FiltrosPainel | None = None,
                          ctx: Contexto = Depends(TRATAR)):
    """Etapa 5h: um plano para cada empresa (ou contato sem empresa) com detrator no filtro do painel e sem plano
    aberto; corpo com os filtros do painel (de, ate, grupo_id, so_ativos; vazio = todo o histórico, só ativas)."""
    with coletar_passos() as passos:
        resultado = detratores.criar(ctx, *(dados or FiltrosPainel()).args())
    tarefas.add_task(sugerir_passos, passos)  # passos sugeridos pela IA, depois do commit
    return resultado


@router.get("/{acao_id}")
def obter(acao_id: int, ctx: Contexto = Depends(VER)):
    return servico.obter_acao(ctx, acao_id)


@router.patch("/{acao_id}")
def alterar(acao_id: int, dados: AcaoAlterarIn, ctx: Contexto = Depends(TRATAR)):
    return servico.alterar(ctx, acao_id, dados)


class RetornoIn(BaseModel):
    texto: Annotated[str, Field(max_length=1000)]


@router.post("/{acao_id}/retorno")
def retorno(acao_id: int, dados: RetornoIn, tarefas: BackgroundTasks, ctx: Contexto = Depends(TRATAR)):
    """Melhoria 4: avisa o cliente do que foi feito (e-mail, uma vez por ação concluída)."""
    acao, envios = servico.enviar_retorno(ctx, acao_id, dados.texto)
    tarefas.add_task(processar_lista, envios)
    return acao


@router.delete("/{acao_id}", status_code=204)
def excluir(acao_id: int, ctx: Contexto = Depends(requer("acoes.excluir"))):
    servico.excluir(ctx, acao_id)
    return Response(status_code=204)
